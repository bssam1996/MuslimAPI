"""Prometheus instrumentation with bounded, non-sensitive labels."""

import asyncio
from contextlib import contextmanager
from functools import wraps
import inspect
from time import perf_counter
from types import SimpleNamespace

from prometheus_client import (
    CollectorRegistry, Counter, Gauge, GCCollector, Histogram, Info,
    PlatformCollector, ProcessCollector,
)


DURATION_BUCKETS = (.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60)
FUNCTION_BUCKETS = (.00001, .00005, .0001, .0005, *DURATION_BUCKETS)
SIZE_BUCKETS = (0, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 10485760)
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "CONNECT", "TRACE"}


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        self.info = Info("muslim_api_app", "Application version", registry=self.registry)

        def metric(kind, name, help_text, labels=(), **kwargs):
            return kind("muslim_api_" + name, help_text, labels, registry=self.registry, **kwargs)

        self.requests = metric(Counter, "http_requests_total", "Completed HTTP requests", ("method", "route", "status"))
        self.request_duration = metric(Histogram, "http_request_duration_seconds", "Time to finish an HTTP response", ("method", "route"), buckets=DURATION_BUCKETS)
        self.in_flight = metric(Gauge, "http_requests_in_progress", "HTTP requests currently being processed")
        self.request_size = metric(Histogram, "http_request_body_bytes", "Request body bytes consumed by the app", ("method", "route"), buckets=SIZE_BUCKETS)
        self.response_size = metric(Histogram, "http_response_body_bytes", "Response body bytes sent by the app", ("method", "route"), buckets=SIZE_BUCKETS)
        self.exceptions = metric(Counter, "http_exceptions_total", "Unhandled exceptions and cancellations", ("method", "route", "type"))
        self.function_calls = metric(Counter, "function_calls_total", "Function calls by outcome", ("function", "outcome"))
        self.function_duration = metric(Histogram, "function_duration_seconds", "Inclusive function duration by outcome", ("function", "outcome"), buckets=FUNCTION_BUCKETS)
        self.function_errors = metric(Counter, "function_errors_total", "Function errors by exception or returned HTTP status", ("function", "type"))
        self.function_in_flight = metric(Gauge, "function_calls_in_progress", "Active function calls, including nested calls", ("function",))
        self.external_requests = metric(Counter, "external_requests_total", "Outbound dependency calls", ("service", "method", "status"))
        self.external_duration = metric(Histogram, "external_request_duration_seconds", "Outbound dependency duration", ("service", "method", "outcome"), buckets=DURATION_BUCKETS)
        self.external_errors = metric(Counter, "external_errors_total", "Outbound dependency failures", ("service", "type"))
        self.loop_lag = metric(Gauge, "event_loop_lag_seconds", "Most recent event-loop scheduling delay")

    @contextmanager
    def _function_call(self, name):
        started = perf_counter()
        state = SimpleNamespace(outcome="success", error=None)
        self.function_in_flight.labels(name).inc()
        try:
            yield state
        except BaseException as error:
            state.outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
            state.error = type(error).__name__
            raise
        finally:
            self.function_calls.labels(name, state.outcome).inc()
            self.function_duration.labels(name, state.outcome).observe(perf_counter() - started)
            if state.error:
                self.function_errors.labels(name, state.error).inc()
            self.function_in_flight.labels(name).dec()

    def track_function(self, function=None, *, failure_predicate=None):
        """Observe sync/async calls; preserve FastAPI annotations and cache APIs."""
        if function is None:
            return lambda fn: self.track_function(fn, failure_predicate=failure_predicate)
        name = function.__module__ + "." + function.__qualname__
        for outcome in ("success", "error", "cancelled"):
            self.function_calls.labels(name, outcome)

        def classify(state, result):
            status = getattr(result, "status_code", None)
            if isinstance(status, int) and status >= 400:
                state.outcome, state.error = "error", f"HTTP{status}"
            elif failure_predicate and failure_predicate(result):
                state.outcome, state.error = "error", "failed_result"
            return result

        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def wrapper(*args, **kwargs):
                with self._function_call(name) as state:
                    return classify(state, await function(*args, **kwargs))
        else:
            @wraps(function)
            def wrapper(*args, **kwargs):
                with self._function_call(name) as state:
                    return classify(state, function(*args, **kwargs))

        # FastAPI evaluates forward annotations in the wrapper's globals unless
        # we supply the original function's already-resolved signature.
        wrapper.__signature__ = inspect.signature(function, eval_str=True)
        for attribute in ("cache_clear", "cache_info", "cache_parameters"):
            if hasattr(function, attribute):
                setattr(wrapper, attribute, getattr(function, attribute))
        return wrapper

    @contextmanager
    def external_call(self, service, method):
        """Use static service names; never label with URLs or query strings."""
        state = SimpleNamespace(status="exception")
        started, outcome = perf_counter(), "success"
        try:
            yield state
            if not 200 <= int(state.status) < 400:
                outcome = "error"
                self.external_errors.labels(service, f"HTTP{state.status}").inc()
        except BaseException as error:
            outcome = "error"
            self.external_errors.labels(service, type(error).__name__).inc()
            raise
        finally:
            self.external_requests.labels(service, method, str(state.status)).inc()
            self.external_duration.labels(service, method, outcome).observe(perf_counter() - started)

    async def watch_event_loop(self, interval=1.0):
        while True:
            started = perf_counter()
            await asyncio.sleep(interval)
            self.loop_lag.set(max(0, perf_counter() - started - interval))


class MetricsMiddleware:
    """Pure ASGI middleware: includes streaming and unhandled errors in timing."""

    def __init__(self, app, metrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").rstrip("/") == "/metrics":
            return await self.app(scope, receive, send)

        started = perf_counter()
        status, exception = 500, None
        request_bytes = response_bytes = 0
        self.metrics.in_flight.inc()

        async def measured_receive():
            nonlocal request_bytes
            message = await receive()
            if message["type"] == "http.request":
                request_bytes += len(message.get("body", b""))
            return message

        async def measured_send(message):
            nonlocal status, response_bytes
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, measured_receive, measured_send)
        except BaseException as error:
            status = 499 if isinstance(error, asyncio.CancelledError) else 500
            exception = type(error).__name__
            raise
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope["method"] if scope["method"] in METHODS else "OTHER"
            self.metrics.requests.labels(method, route, str(status)).inc()
            self.metrics.request_duration.labels(method, route).observe(perf_counter() - started)
            self.metrics.request_size.labels(method, route).observe(request_bytes)
            self.metrics.response_size.labels(method, route).observe(response_bytes)
            if exception:
                self.metrics.exceptions.labels(method, route, exception).inc()
            self.metrics.in_flight.dec()


metrics = Metrics()
