# MuslimAPI metrics, Prometheus and Grafana

The API exposes Prometheus metrics at `GET /metrics`. The optional
`compose.monitoring.yaml` stack scrapes them every 15 seconds, stores history,
and provisions a **MuslimAPI Overview** dashboard with endpoint and function
selectors. No manual datasource or dashboard import is needed.

## Use your existing monitoring stack on the mini PC

If Prometheus, Grafana and Node Exporter already run with `network_mode: host`,
keep those services and run only MuslimAPI from this repository's `compose.yaml`.
The optional `compose.monitoring.yaml` is for creating a new monitoring stack.

Add this job to the **existing** `prometheus.yml`, preserving its other jobs:

```yaml
scrape_configs:
  # Keep your existing jobs here too.
  - job_name: muslim-api
    metrics_path: /metrics
    static_configs:
      - targets: [127.0.0.1:8000]
```

Use the API's published host port if it differs from 8000. The API can stay on
its own Compose bridge network; the published port makes it reachable from
the host-network Prometheus container. Keep `job_name: muslim-api` because the
dashboard and API alert rules filter on it. A complete example including
Prometheus and Node Exporter jobs is in
[`monitoring/host-network/prometheus.yml`](monitoring/host-network/prometheus.yml).

Your existing Grafana Prometheus datasource should use
`url: http://127.0.0.1:9090`, rather than the bridge-network service hostname
`prometheus`. See the [host-network datasource example](monitoring/host-network/grafana-datasource.yml).
Update the existing datasource; do not duplicate its name/UID. The dashboard's
**Datasource** dropdown works with an existing datasource's UID.

Copy these files into the host directories already mounted by your monitoring
Compose file:

| Repository file | Destination in your existing monitoring directory |
| --- | --- |
| `monitoring/grafana/dashboards/muslim-api.json` | `grafana/dashboards/muslim-api.json` |
| `monitoring/grafana/provisioning/dashboards/muslim-api.yml` | `grafana/provisioning/dashboards/muslim-api.yml` |
| `monitoring/prometheus/alerts.yml` | `prometheus-alerts.yml` |

To load the API alerts, add this volume to your existing Prometheus service:

```yaml
volumes:
  # Keep the existing prometheus.yml and data mounts too.
  - ./prometheus-alerts.yml:/etc/prometheus/alerts.yml:ro
```

And merge this into the existing `prometheus.yml`:

```yaml
rule_files:
  - /etc/prometheus/alerts.yml
```

The example host-network config includes this rule file, so mount it before
using that complete example. For a bounded disk footprint, also add
`--storage.tsdb.retention.time=15d` and `--storage.tsdb.retention.size=2GB` to
your Prometheus command. Leave extra disk for its WAL and active blocks.

From your **existing monitoring directory**, apply Compose changes with
`docker compose up -d`, then restart Prometheus to reload any edited config:

```sh
docker compose restart prometheus
curl -fsS http://127.0.0.1:8000/metrics
```

Use Grafana's **MuslimAPI Overview** dashboard. Grafana, Prometheus and Node
Exporter remain loopback-only with your current listen addresses; keep using
your existing SSH tunnel or reverse proxy to reach Grafana. Node Exporter
provides machine metrics; the application supplies endpoint/function metrics.

## Start locally

Build the updated application image:

```sh
docker build -t muslim-api:local .
```

In `.env`, set a strong Grafana password and the image you built:

```dotenv
MUSLIM_API_IMAGE=muslim-api:local
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=REPLACE_WITH_A_STRONG_PASSWORD
```

Then start all three services:

```sh
docker compose -f compose.yaml -f compose.monitoring.yaml up -d
docker compose -f compose.yaml -f compose.monitoring.yaml ps
```

- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`
- Grafana: `http://localhost:3000`, using the credentials in `.env`.
- Prometheus targets: `http://localhost:9090/targets` (loopback access only).

In Grafana, open **Dashboards > MuslimAPI > MuslimAPI Overview**. Make a few
API calls and allow two or three scrapes (30–45 seconds) for rate charts.
Latency charts stay empty until the selected function or endpoint is called.

```sh
curl "http://localhost:8000/v1/timings/today?latitude=51.5072&longitude=-0.1276"
curl http://localhost:8000/quizes/get_random_quiz
curl http://localhost:8000/v1/timings/bad-date
```

## Deploy on the mini PC

After the updated image has been published by GitHub Actions, copy these files
from the same revision to the deployment directory on the mini PC:

- `compose.yaml`
- `compose.monitoring.yaml`
- The entire `monitoring/` directory, preserving its subdirectories.

Keep the mini PC's `.env` private, add the Grafana password, and use:

```dotenv
MUSLIM_API_IMAGE=ghcr.io/bssam1996/muslimapi:latest
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=REPLACE_WITH_A_STRONG_PASSWORD
```

```sh
docker compose -f compose.yaml -f compose.monitoring.yaml pull
docker compose -f compose.yaml -f compose.monitoring.yaml up -d
```

Open `http://MINI_PC_IP:3000`. If using the old standalone `docker run` service,
stop and remove that API container first so port 8000 is available to Compose.
Always use both Compose files for subsequent monitoring-stack commands.

Prometheus and Grafana configuration is mounted from the host; it is not baked
into the API image. An older image without `/metrics` cannot be monitored by
this configuration. Check Prometheus's targets page if charts remain empty.

## What is collected

| Metric | Labels | Meaning |
| --- | --- | --- |
| `muslim_api_http_requests_total` | method, route, status | HTTP response counts; distinguish 2xx/3xx, 4xx and 5xx. |
| `muslim_api_http_request_duration_seconds` | method, route | Histogram from request entry through final response body and handler cleanup. |
| `muslim_api_http_requests_in_progress` | none | Concurrent active requests. |
| `muslim_api_http_request_body_bytes` | method, route | Histogram of body bytes actually consumed by the app. |
| `muslim_api_http_response_body_bytes` | method, route | Histogram of emitted response body bytes, excluding HTTP headers. |
| `muslim_api_http_exceptions_total` | method, route, type | Unhandled failures, stream errors and cancellations. |
| `muslim_api_function_calls_total` | function, outcome | Success, error or cancelled calls. |
| `muslim_api_function_duration_seconds` | function, outcome | Inclusive wall-time histogram, including awaited work. |
| `muslim_api_function_errors_total` | function, type | Exception class, returned HTTP error status, or failed result. |
| `muslim_api_function_calls_in_progress` | function | Active calls per instrumented function, including nested calls. |
| `muslim_api_external_requests_total` | service, method, status | Dorar HTTP statuses or `exception` when no response arrives. |
| `muslim_api_external_request_duration_seconds` | service, method, outcome | Upstream duration histogram, separated by success/error. |
| `muslim_api_external_errors_total` | service, type | Dependency failures, including timeouts, HTTP errors and invalid JSON. |
| `muslim_api_event_loop_lag_seconds` | none | Most recent scheduling delay, sampled once a second. |
| `muslim_api_app_info` | version | Application version metadata. |
| `process_*`, `python_*` | collector-specific | API process CPU, memory, uptime, open descriptors, Python version and garbage collection. |

Histogram families expose `_bucket`, `_sum` and `_count` series. All duration
values are in seconds. Function histograms include every endpoint, prayer
request parsing and formatting, prayer calculation, timezone resolution,
location defaults, Hijri formatting, quiz loading, and Hadith fetch/parsing.
Tiny astronomical arithmetic helpers and unused mock-data functions are not
instrumented individually. Cached operations count cache hits as calls too.

Nested timings overlap: calendar generation includes its daily calculations.
Do not add function durations together to calculate total request latency.
Function errors include expected validation failures and returned HTTP 4xx;
use HTTP **5xx** for server-error alerts. FastAPI validation that rejects a
request before its endpoint runs increments HTTP metrics only.

Dorar errors remain visible even though the existing Hadith API translates
an unavailable upstream into an empty result/404. Its request now has a 3.05s
connection timeout and 10s read timeout. These bound connection/read stalls,
not total wall time across redirects or a response that keeps streaming.

Routes use templates such as `/v1/timings/{date_value}`. All unknown routes
share `unmatched`; nonstandard HTTP methods share `OTHER`. Labels never include
coordinates, search text, raw URLs, exception messages, IPs, or credentials.
`/metrics` scrapes are excluded from request metrics. `/` health checks remain
available in raw metrics but are excluded from dashboard traffic/latency panels
and request-based alert thresholds.

## Latency queries

Endpoint p95 over five minutes:

```promql
histogram_quantile(0.95,
  sum by (le, route) (
    rate(muslim_api_http_request_duration_seconds_bucket{job="muslim-api",route!="/"}[5m])
  )
)
```

Mean function duration, split by success/error:

```promql
sum by (function, outcome) (rate(muslim_api_function_duration_seconds_sum[5m]))
/
sum by (function, outcome) (rate(muslim_api_function_duration_seconds_count[5m]))
```

The dashboard also includes HTTP p50/p95/p99, HTTP/function histogram heatmaps,
status-code traffic, function errors, body sizes, Dorar health, CPU, resident
memory, event-loop delay, uptime and open descriptors.

## Alerts and storage

Six Prometheus rules cover scrape failure, sustained HTTP 5xx, slow endpoint
p95, sustained event-loop lag, process memory above 512 MiB, and Dorar failures.
Traffic thresholds prevent isolated low-volume errors from paging. Tune the
thresholds in `monitoring/prometheus/alerts.yml` for your mini PC and traffic.

These rules evaluate in Prometheus and appear in its **Alerts** page and the
dashboard. Email/Slack/push delivery is not configured: connect an Alertmanager
or create Grafana-managed alert rules and contact points for notifications.

Named volumes preserve Prometheus history and Grafana state across restarts
and `docker compose down`. **Adding `-v` deletes these volumes.** Prometheus
retains at most 15 days or about 2 GB of samples by default (whichever limit
is reached first; allow additional disk for its WAL and active blocks).
Override `PROMETHEUS_RETENTION` and `PROMETHEUS_RETENTION_SIZE` in `.env`.
The initial Grafana admin password is set only when its database is created;
change an existing password through Grafana rather than changing `.env` alone.

Use one Uvicorn worker per API container, as enforced by the monitoring Compose
override. Counters reset on restart; Prometheus `rate`/`increase` account for
resets. Multiple worker processes need explicit Prometheus multiprocess
configuration and are not supported by this setup. Process metrics describe
the API process, not total mini-PC usage or Docker container resource limits.

Prometheus binds only to `127.0.0.1`. Use an SSH tunnel to its port if needed.
Grafana requires login and binds to the home network by default; optionally
set `GRAFANA_BIND_ADDRESS=127.0.0.1` when using a local reverse proxy/tunnel.
Block `/metrics` at your public reverse proxy if you expose the API publicly;
the endpoint intentionally has no app-level authentication for internal scraping.

## Validation

The GitHub workflow runs the application tests and container smoke checks,
validates the Compose configuration and Prometheus rules, and tests downtime,
high-error-rate, and low-traffic alert behavior before publishing.

References: [Prometheus histograms](https://prometheus.io/docs/practices/histograms/),
[Python client collectors](https://prometheus.github.io/client_python/collector/),
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
