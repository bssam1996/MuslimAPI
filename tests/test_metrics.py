import asyncio
from functools import lru_cache
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
import pytest
import requests

from utils.metrics import Metrics, MetricsMiddleware, metrics


def value(collector, name, **labels):
    return collector.registry.get_sample_value("muslim_api_" + name, labels) or 0


@pytest.fixture
def instrumented():
    collector = Metrics()
    app = FastAPI()
    app.add_middleware(MetricsMiddleware, metrics=collector)

    @app.get("/items/{item_id}")
    @collector.track_function
    async def item(item_id: int):
        if item_id == 400:
            return JSONResponse({"error": "bad input"}, status_code=400)
        if item_id == 403:
            raise HTTPException(403, "forbidden")
        if item_id == 500:
            raise ValueError("sensitive exception message")
        return {"id": item_id}

    return collector, TestClient(app, raise_server_exceptions=False), item


def test_http_and_function_outcomes_include_returned_errors(instrumented):
    collector, client, item = instrumented
    name = item.__module__ + "." + item.__qualname__
    for item_id in (1, 400, 403, 500):
        expected = 200 if item_id == 1 else item_id
        assert client.get(f"/items/{item_id}").status_code == expected
        assert value(collector, "http_requests_total", method="GET", route="/items/{item_id}", status=str(expected)) == 1
    assert value(collector, "function_calls_total", function=name, outcome="success") == 1
    assert value(collector, "function_calls_total", function=name, outcome="error") == 3
    assert value(collector, "function_errors_total", function=name, type="HTTP400") == 1
    assert value(collector, "function_errors_total", function=name, type="ValueError") == 1
    assert value(collector, "http_exceptions_total", method="GET", route="/items/{item_id}", type="ValueError") == 1
    assert value(collector, "http_requests_in_progress") == 0
    assert value(collector, "function_calls_in_progress", function=name) == 0


def test_route_labels_are_bounded_and_do_not_leak_input(instrumented):
    collector, client, _ = instrumented
    for path in ("/items/12", "/items/99", "/not-found/private-a", "/not-found/private-b"):
        client.get(path, params={"searchQuery": "private-search-text"})
    client.request("SECRET-METHOD", "/not-found/private-c")
    assert value(collector, "http_requests_total", method="GET", route="/items/{item_id}", status="200") == 2
    assert value(collector, "http_requests_total", method="GET", route="unmatched", status="404") == 2
    assert value(collector, "http_requests_total", method="OTHER", route="unmatched", status="404") == 1
    output = generate_latest(collector.registry).decode()
    for secret in ("private-a", "private-b", "private-search-text", "SECRET-METHOD"):
        assert secret not in output


def test_request_validation_is_counted_as_http_error(instrumented):
    collector, client, item = instrumented
    assert client.get("/items/not-an-integer").status_code == 422
    assert value(collector, "http_requests_total", method="GET", route="/items/{item_id}", status="422") == 1
    name = item.__module__ + "." + item.__qualname__
    assert value(collector, "function_calls_total", function=name, outcome="error") == 0


def test_streaming_duration_covers_the_last_body_chunk():
    collector = Metrics()

    async def app(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/stream")
        assert value(collector, "http_requests_in_progress") == 1
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"first", "more_body": True})
        await asyncio.sleep(.01)
        await send({"type": "http.response.body", "body": b"last"})

    async def receive():
        return {"type": "http.request", "body": b"input"}

    async def send(message):
        pass

    asyncio.run(MetricsMiddleware(app, collector)({"type": "http", "method": "POST", "path": "/stream"}, receive, send))
    labels = {"method": "POST", "route": "/stream"}
    assert value(collector, "http_request_duration_seconds_sum", **labels) >= .01
    assert value(collector, "http_request_body_bytes_sum", **labels) == 5
    assert value(collector, "http_response_body_bytes_sum", **labels) == 9
    assert value(collector, "http_requests_in_progress") == 0


def test_cancellation_is_reraised_and_gauges_are_balanced():
    collector = Metrics()

    @collector.track_function
    async def cancelled():
        raise asyncio.CancelledError()

    async def app(scope, receive, send):
        await cancelled()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(MetricsMiddleware(app, collector)({"type": "http", "method": "GET", "path": "/cancelled"}, None, None))
    assert value(collector, "http_requests_total", method="GET", route="unmatched", status="499") == 1
    name = cancelled.__module__ + "." + cancelled.__qualname__
    assert value(collector, "function_calls_total", function=name, outcome="cancelled") == 1
    assert value(collector, "function_calls_in_progress", function=name) == 0
    assert value(collector, "http_requests_in_progress") == 0


def test_sync_cache_hits_are_instrumented_and_cache_api_is_preserved():
    collector = Metrics()

    @collector.track_function
    @lru_cache(maxsize=1)
    def calculate(number: int) -> int:
        return number * 2

    assert calculate(2) == calculate(2) == 4
    assert calculate.cache_info().hits == 1
    name = calculate.__module__ + "." + calculate.__qualname__
    assert value(collector, "function_duration_seconds_count", function=name, outcome="success") == 2
    calculate.cache_clear()
    assert calculate.cache_info().currsize == 0


def test_scraping_excludes_itself_and_exports_process_metrics():
    from main import app
    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.headers["cache-control"] == "no-store"
        assert "python_info" in response.text
        assert "muslim_api_app_info" in response.text
        assert 'route="/metrics"' not in response.text
        assert "/metrics" not in client.get("/openapi.json").json()["paths"]
        client.get("/v1/timings/25-11-2026?latitude=51.5072&longitude=-0.1276")
        output = client.get("/metrics").text
        assert 'function="utils.prayer_times.engine.calculate_prayer_times"' in output
        assert 'route="/v1/timings/{date_value}"' in output


@pytest.mark.parametrize("failure", ["timeout", "http", "invalid_json"])
def test_swallowed_dorar_errors_remain_visible(monkeypatch, capsys, failure):
    from utils.hadith import utils as hadith
    before = value(metrics, "external_request_duration_seconds_count", service="dorar", method="GET", outcome="error")
    name = "utils.hadith.utils.getSimilarHadiths"
    before_function = value(metrics, "function_calls_total", function=name, outcome="error")

    def get(*args, **kwargs):
        assert kwargs["timeout"] == (3.05, 10)
        if failure == "timeout":
            raise requests.Timeout("private-search-text")
        def parse_json():
            raise ValueError("private-search-text")
        return SimpleNamespace(status_code=503 if failure == "http" else 200, json=parse_json)

    monkeypatch.setattr(hadith.requests, "get", get)
    assert hadith.getSimilarHadiths("private-search-text") == {}
    assert value(metrics, "external_request_duration_seconds_count", service="dorar", method="GET", outcome="error") == before + 1
    assert value(metrics, "function_calls_total", function=name, outcome="error") == before_function + 1
    assert "private-search-text" not in capsys.readouterr().out
    assert "private-search-text" not in generate_latest(metrics.registry).decode()
