# Prometheus and Grafana Lab Tutorial

This tutorial teaches monitoring with Prometheus, Grafana, Alertmanager, exporters, PromQL, dashboards, and alert rules using the files in this repository.

The lab is designed for students who are new to observability. By the end, they should be able to explain how metrics are collected, write useful PromQL queries, build Grafana panels, and create alerts that route through Alertmanager.

## 1. Learning Goals

After completing this lab, students should be able to:

- Describe the role of Prometheus, Grafana, Alertmanager, and exporters.
- Run a complete local monitoring stack with Docker Compose.
- Inspect Prometheus targets and troubleshoot scrape failures.
- Understand counters, gauges, and histograms using the Python exporter.
- Write PromQL queries for CPU, memory, application metrics, and endpoint health.
- Use recording rules to precompute frequently used expressions.
- Use alerting rules to detect failures and abnormal behavior.
- Understand Grafana provisioning for data sources and dashboards.
- Extend the lab with new metrics, panels, and alerts.

## 2. Repository Tour

The important files are:

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | Starts Prometheus, Grafana, Alertmanager, Node Exporter, a Python metrics app, and Blackbox Exporter. |
| `prometheus/prometheus.yml` | Prometheus scrape configuration, rule files, and Alertmanager connection. |
| `prometheus/alert_rules.yml` | Alerting rules for CPU, Python app temperature, and blackbox endpoint checks. |
| `prometheus/recording_rules.yml` | Example recording rule for node CPU rate. |
| `alertmanager/alertmanager.yml` | Alert routing by severity to Slack-style receivers. |
| `grafana/provisioning/datasources/datasource.yml` | Automatically registers Prometheus as Grafana's default data source. |
| `grafana/provisioning/dashboards/dashboards.yml` | Tells Grafana where to load dashboard JSON files from. |
| `grafana/dashboards/node_exporter_dashboard.json` | Example dashboard with CPU and memory panels. |
| `app/python-exporter/app.py` | Simple Python app exposing custom Prometheus metrics. |
| `exporters/blackbox_exporter/blackbox.yml` | Blackbox HTTP probe module configuration. |

Note: the current `README.md` mentions optional `k8s/` and `scripts/` folders, but they are not present in this checkout. This tutorial focuses on the working examples that are currently in the codebase.

## 3. Architecture

The stack runs on one Docker bridge network named `monitor-net`.

```text
                            +----------------+
                            |    Grafana     |
                            | localhost:3000 |
                            +--------+-------+
                                     |
                                     | queries Prometheus
                                     v
+----------------+          +----------------+          +------------------+
| Node Exporter  | <------  |   Prometheus   | -------> |  Alertmanager    |
| :9100/metrics  | scrape   | localhost:9090 | alerts   | localhost:9093   |
+----------------+          +--------+-------+          +------------------+
                                     ^
                                     |
                    scrape           | scrape
                                     |
        +----------------+   +-------+--------+   +------------------+
        | Python App     |   | Blackbox       |   | Prometheus self  |
        | :8000/metrics  |   | :9115/probe    |   | :9090/metrics    |
        +----------------+   +----------------+   +------------------+
```

The key idea is pull-based monitoring:

1. Services expose metrics over HTTP.
2. Prometheus periodically scrapes those endpoints.
3. Prometheus stores the time series locally.
4. Grafana queries Prometheus and visualizes the data.
5. Prometheus evaluates alert rules and sends firing alerts to Alertmanager.
6. Alertmanager groups, routes, and sends notifications.

## 4. Prerequisites

Students need:

- Docker
- Docker Compose
- A terminal
- A browser

Optional tools:

- `curl` for inspecting metrics endpoints.
- `jq` for reading JSON dashboard files.

## 5. Start The Lab

From the repository root:

```bash
docker-compose up -d
```

Check running containers:

```bash
docker-compose ps
```

Open these URLs:

| Tool | URL | Login |
| --- | --- | --- |
| Prometheus | `http://localhost:9090` | none |
| Grafana | `http://localhost:3000` | `admin` / `admin` |
| Alertmanager | `http://localhost:9093` | none |
| Node Exporter metrics | `http://localhost:9100/metrics` | none |
| Python app metrics | `http://localhost:8000/metrics` | none |
| Blackbox Exporter | `http://localhost:9115` | none |

Stop the lab when finished:

```bash
docker-compose down
```

## 6. Prometheus Configuration

Open `prometheus/prometheus.yml`.

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
```

This means:

- Prometheus scrapes configured targets every 15 seconds.
- Prometheus evaluates recording and alerting rules every 15 seconds.

The rule files are loaded here:

```yaml
rule_files:
  - "/etc/prometheus/alert_rules.yml"
  - "/etc/prometheus/recording_rules.yml"
```

Alertmanager is connected here:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

Because all containers are on the same Docker network, Prometheus can reach Alertmanager by service name: `alertmanager:9093`.

## 7. Prometheus Scrape Jobs

Prometheus collects metrics from jobs in `scrape_configs`.

### Prometheus Self-Monitoring

```yaml
- job_name: "prometheus"
  static_configs:
    - targets: ["prometheus:9090"]
```

Prometheus monitors itself. This is useful because Prometheus exposes metrics about its own scrape health, rule evaluation, storage, and HTTP server.

Try these queries in Prometheus:

```promql
up{job="prometheus"}
prometheus_http_requests_total
prometheus_rule_evaluation_duration_seconds
```

### Node Exporter

```yaml
- job_name: "node"
  metrics_path: /metrics
  static_configs:
    - targets: ["node-exporter:9100"]
```

Node Exporter exposes operating system and machine-level metrics such as CPU, memory, filesystem, and network stats.

Try:

```promql
up{job="node"}
node_cpu_seconds_total
node_memory_MemAvailable_bytes
```

### Python Application Exporter

```yaml
- job_name: "python-app"
  static_configs:
    - targets: ["python-app:8000"]
```

This job scrapes the custom Python app in `app/python-exporter/app.py`.

Try:

```promql
up{job="python-app"}
app_requests_total
app_temperature_celsius
app_latency_seconds_bucket
```

### External Datalake Stats Target

```yaml
- job_name: "datalake-stats"
  static_configs:
    - targets: ["149.40.228.124:6500"]
```

This target points to an external IP and port. It may or may not be reachable from a student's machine or classroom network.

Check it with:

```promql
up{job="datalake-stats"}
```

If the value is `0`, Prometheus cannot scrape it. Go to Prometheus `Status -> Targets` to inspect the error.

### Blackbox Exporter

```yaml
- job_name: "blackbox"
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - www.google.com
        - 172.20.160.21
```

Blackbox Exporter is different from normal exporters. Prometheus does not scrape the final target directly. Instead:

1. Prometheus sends a request to Blackbox Exporter.
2. The requested target is passed as a parameter.
3. Blackbox Exporter probes the target.
4. Blackbox Exporter returns probe metrics to Prometheus.

The relabeling section rewrites each target into a probe request:

```yaml
relabel_configs:
  - source_labels: [__address__]
    target_label: __param_target
  - source_labels: [__param_target]
    target_label: instance
  - target_label: __address__
    replacement: blackbox:9115
```

Try:

```promql
probe_success
probe_http_status_code
probe_duration_seconds
```

## 8. Inspect Targets

In Prometheus, open:

```text
Status -> Targets
```

Students should identify:

- Which jobs are up.
- Which jobs are down.
- The last scrape time.
- The last scrape duration.
- Any scrape error.

Useful query:

```promql
up
```

`up` is one of the most important Prometheus metrics:

- `1` means the last scrape succeeded.
- `0` means the last scrape failed.

Classroom exercise:

1. Stop the Python app container:

   ```bash
   docker-compose stop python-app
   ```

2. Query:

   ```promql
   up{job="python-app"}
   ```

3. Start it again:

   ```bash
   docker-compose start python-app
   ```

4. Watch the value return to `1`.

## 9. Metrics Types In The Python App

Open `app/python-exporter/app.py`.

The app defines three metric types:

```python
REQUESTS = Counter("app_requests_total", "Total app requests")
TEMPERATURE = Gauge("app_temperature_celsius", "Simulated temperature")
LATENCY = Histogram("app_latency_seconds", "Request latency seconds", buckets=[0.05,0.1,0.2,0.5,1,2])
```

### Counter

`app_requests_total` is a counter.

A counter only goes up, except when the process restarts. It is good for events:

- HTTP requests
- jobs processed
- errors seen
- messages consumed

Good queries:

```promql
app_requests_total
rate(app_requests_total[1m])
increase(app_requests_total[5m])
```

Teaching point: do not alert on the raw value of a counter unless the total itself matters. Alert on the rate or increase.

### Gauge

`app_temperature_celsius` is a gauge.

A gauge can go up or down. It is good for current state:

- temperature
- memory usage
- queue depth
- active connections

Good queries:

```promql
app_temperature_celsius
avg_over_time(app_temperature_celsius[5m])
max_over_time(app_temperature_celsius[5m])
```

### Histogram

`app_latency_seconds` is a histogram.

The Python client exposes several related time series:

```text
app_latency_seconds_bucket
app_latency_seconds_count
app_latency_seconds_sum
```

Good queries:

```promql
rate(app_latency_seconds_count[1m])
rate(app_latency_seconds_sum[1m]) / rate(app_latency_seconds_count[1m])
histogram_quantile(0.95, rate(app_latency_seconds_bucket[5m]))
```

Teaching point: histograms are how Prometheus commonly estimates latency percentiles.

## 10. PromQL Basics

PromQL is the query language used by both Prometheus and Grafana.

### Instant Vector

Returns the latest value for each matching time series:

```promql
app_temperature_celsius
```

### Range Vector

Selects values over a time window:

```promql
app_temperature_celsius[5m]
```

Range vectors are usually passed into functions:

```promql
avg_over_time(app_temperature_celsius[5m])
```

### Labels

Labels identify dimensions of a metric.

Example:

```promql
up{job="python-app"}
```

Common labels in this lab include:

- `job`
- `instance`
- `mode`
- `le`

### Rate

Use `rate()` with counters:

```promql
rate(app_requests_total[1m])
```

For CPU:

```promql
sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (instance)
```

This query means:

1. Select CPU seconds that are not idle.
2. Calculate per-second rate over one minute.
3. Sum by instance.

### Aggregation

Examples:

```promql
sum by (instance) (rate(node_cpu_seconds_total[1m]))
avg by (job) (up)
max by (instance) (app_temperature_celsius)
```

### Boolean Comparisons

Alerts often use comparisons:

```promql
app_temperature_celsius > 75
probe_success == 0
```

## 11. Recording Rules

Open `prometheus/recording_rules.yml`.

```yaml
groups:
  - name: recording_rules
    rules:
      - record: job:node_cpu_seconds:rate1m
        expr: sum by (instance) (rate(node_cpu_seconds_total[1m]))
```

A recording rule saves the result of a PromQL expression as a new time series.

Instead of repeatedly typing:

```promql
sum by (instance) (rate(node_cpu_seconds_total[1m]))
```

Students can query:

```promql
job:node_cpu_seconds:rate1m
```

Use recording rules when:

- A query is used frequently.
- A query is expensive.
- Dashboards need faster loading.
- Alerts need a cleaner expression.

Classroom exercise:

Add a recording rule for Python app request rate:

```yaml
- record: job:app_requests:rate1m
  expr: sum by (instance) (rate(app_requests_total[1m]))
```

Then reload Prometheus by restarting the service:

```bash
docker-compose restart prometheus
```

Query:

```promql
job:app_requests:rate1m
```

## 12. Alerting Rules

Open `prometheus/alert_rules.yml`.

### High CPU Alert

```yaml
- alert: HighCPUUsage
  expr: sum(rate(node_cpu_seconds_total{mode!="idle"}[2m])) by (instance) > 0.8
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High CPU usage on {{ $labels.instance }}"
    description: "CPU usage is > 80% for more than 2 minutes."
```

Important fields:

- `alert`: alert name.
- `expr`: PromQL condition.
- `for`: condition must remain true for this long.
- `labels`: metadata used for routing and grouping.
- `annotations`: human-readable message content.

### Python Temperature Alert

```yaml
- alert: PythonAppHighTemp
  expr: app_temperature_celsius > 75
  for: 1m
  labels:
    severity: critical
```

The app randomly sets temperature between 30 and 80 Celsius. This alert can fire naturally when the generated value stays above 75 for one minute.

Teaching point: random demo metrics are useful in labs, but production alerts should be based on meaningful service-level symptoms.

### Endpoint Down Alert

```yaml
- alert: EndpointDown
  expr: probe_success == 0
  for: 1m
  labels:
    severity: critical
```

This checks whether Blackbox Exporter probes are failing.

To inspect alerts:

```text
Prometheus -> Alerts
```

Also check:

```text
Alertmanager -> Alerts
```

Classroom exercise:

1. Temporarily add a fake blackbox target to `prometheus/prometheus.yml`.
2. Restart Prometheus.
3. Watch `probe_success` become `0`.
4. Watch the `EndpointDown` alert move from pending to firing.

## 13. Alertmanager Routing

Open `alertmanager/alertmanager.yml`.

The root route defines grouping and repeat timing:

```yaml
route:
  receiver: 'default-slack'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h
```

Nested routes send alerts to different receivers based on severity:

```yaml
routes:
  - match:
      severity: critical
    receiver: 'critical-slack'
    continue: true

  - match:
      severity: warning
    receiver: 'warning-slack'
    continue: true
```

In this repository, Slack receivers exist but `api_url` is empty:

```yaml
slack_configs:
  - api_url: ""
```

That means this configuration is useful for teaching routing structure, but real Slack delivery requires a webhook URL.

For a real classroom or production setup:

1. Create a Slack incoming webhook.
2. Store it as an environment variable or secret.
3. Reference it in Alertmanager configuration.
4. Avoid committing webhook URLs to Git.

Teaching point: never commit real webhook URLs, passwords, API keys, or tokens.

## 14. Grafana Provisioning

Grafana is automatically configured from files under `grafana/provisioning`.

### Data Source

Open `grafana/provisioning/datasources/datasource.yml`.

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

This creates a default Prometheus data source in Grafana.

Because Grafana runs inside Docker, it uses the Docker service name `prometheus`, not `localhost`.

### Dashboard Provider

Open `grafana/provisioning/dashboards/dashboards.yml`.

```yaml
providers:
  - name: 'default'
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

The Compose file mounts local dashboards into that path:

```yaml
- ./grafana/dashboards:/var/lib/grafana/dashboards
```

So Grafana loads dashboards from `grafana/dashboards`.

### Example Dashboard

Open `grafana/dashboards/node_exporter_dashboard.json`.

The dashboard title is:

```text
Node Exporter Overview
```

It contains two panels:

| Panel | Query |
| --- | --- |
| CPU Usage on request of the class (non-idle) | `sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (instance)` |
| Memory Available | `node_memory_MemAvailable_bytes` |

Classroom exercise:

1. Open Grafana at `http://localhost:3000`.
2. Log in with `admin` / `admin`.
3. Open the provisioned Node Exporter dashboard.
4. Change the time range to last 15 minutes.
5. Compare the CPU query in Grafana with the same query in Prometheus.

## 15. Build A New Grafana Panel

Create a panel for Python app temperature:

1. Open Grafana.
2. Open a dashboard or create a new one.
3. Add a panel.
4. Select the Prometheus data source.
5. Use this query:

   ```promql
   app_temperature_celsius
   ```

6. Set the panel title to:

   ```text
   Python App Temperature
   ```

7. Choose a time series visualization.
8. Add threshold lines at 75 Celsius.

Create a request rate panel:

```promql
rate(app_requests_total[1m])
```

Create a latency panel:

```promql
histogram_quantile(0.95, rate(app_latency_seconds_bucket[5m]))
```

## 16. Blackbox Monitoring

Open `exporters/blackbox_exporter/blackbox.yml`.

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: [200, 302]
      valid_http_versions: ["HTTP/1.1", "HTTP/2"]
      preferred_ip_protocol: "ip4"
```

The `http_2xx` module:

- Uses HTTP probing.
- Times out after 5 seconds.
- Accepts status codes `200` and `302`.
- Allows HTTP/1.1 and HTTP/2.
- Prefers IPv4.

Manual probe example:

```text
http://localhost:9115/probe?target=www.google.com&module=http_2xx
```

Useful Blackbox queries:

```promql
probe_success
probe_duration_seconds
probe_http_status_code
```

Classroom discussion:

- Why is blackbox monitoring useful even if an app exports internal metrics?
- What is the difference between "the process is running" and "users can reach the website"?
- Why might `up{job="python-app"}` be `1` while a user-facing endpoint is still broken?

## 17. Common Troubleshooting

### Prometheus Target Is Down

Check:

```text
Prometheus -> Status -> Targets
```

Possible causes:

- Container is stopped.
- Wrong port.
- Wrong Docker service name.
- App does not expose `/metrics`.
- Network issue.
- External IP is unreachable.

### Grafana Cannot Query Prometheus

Check:

- Grafana data source URL is `http://prometheus:9090`.
- The Prometheus container is running.
- Both containers are on `monitor-net`.
- The data source is marked healthy in Grafana.

### Alerts Do Not Appear

Check:

- Rule file is mounted into Prometheus.
- Rule syntax is valid.
- Prometheus was restarted after config changes.
- The alert condition is actually true.
- The `for` duration has elapsed.

### Slack Notifications Do Not Send

In this repo, `api_url` is empty in `alertmanager/alertmanager.yml`.

For real delivery, configure a valid webhook securely. Do not commit it to the repository.

## 18. Lab Exercises

### Exercise 1: Explore Existing Metrics

In Prometheus, run:

```promql
up
app_requests_total
app_temperature_celsius
node_memory_MemAvailable_bytes
probe_success
```

Answer:

- Which jobs are healthy?
- Which metric is a counter?
- Which metric is a gauge?
- Which metric comes from Blackbox Exporter?

### Exercise 2: Create PromQL Queries

Write queries for:

- Python app request rate over one minute.
- Maximum app temperature over five minutes.
- Available memory in megabytes.
- Endpoint probe duration.
- All down targets.

Suggested answers:

```promql
rate(app_requests_total[1m])
max_over_time(app_temperature_celsius[5m])
node_memory_MemAvailable_bytes / 1024 / 1024
probe_duration_seconds
up == 0
```

### Exercise 3: Add A Recording Rule

Add this to `prometheus/recording_rules.yml`:

```yaml
- record: job:python_app_requests:rate1m
  expr: sum by (instance) (rate(app_requests_total[1m]))
```

Restart Prometheus:

```bash
docker-compose restart prometheus
```

Query:

```promql
job:python_app_requests:rate1m
```

### Exercise 4: Add An Alert

Add an alert for high request rate:

```yaml
- alert: PythonAppHighRequestRate
  expr: rate(app_requests_total[1m]) > 1
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Python app request rate is high"
    description: "The Python app is processing more than 1 request per second."
```

Restart Prometheus:

```bash
docker-compose restart prometheus
```

Open:

```text
Prometheus -> Alerts
```

### Exercise 5: Build A Grafana Dashboard

Create a dashboard named:

```text
Python App Overview
```

Add panels:

| Panel | Query |
| --- | --- |
| Request Rate | `rate(app_requests_total[1m])` |
| Temperature | `app_temperature_celsius` |
| Average Latency | `rate(app_latency_seconds_sum[1m]) / rate(app_latency_seconds_count[1m])` |
| P95 Latency | `histogram_quantile(0.95, rate(app_latency_seconds_bucket[5m]))` |

### Exercise 6: Break And Fix A Target

Stop the Python app:

```bash
docker-compose stop python-app
```

Observe:

```promql
up{job="python-app"}
```

Start it again:

```bash
docker-compose start python-app
```

Explain why the graph shows a gap or outage period.

### Exercise 7: Add A New Custom Metric

Modify `app/python-exporter/app.py` to add a gauge:

```python
QUEUE_DEPTH = Gauge("app_queue_depth", "Simulated queue depth")
```

Inside the loop:

```python
QUEUE_DEPTH.set(random.randint(0, 100))
```

Rebuild and restart:

```bash
docker-compose up -d --build python-app
```

Query:

```promql
app_queue_depth
```

Then create a Grafana panel and an alert for queue depth greater than 80.

## 19. Suggested Teaching Flow

For a 2-hour class:

| Time | Topic |
| --- | --- |
| 0-10 min | Observability concepts: metrics, labels, time series. |
| 10-25 min | Start Docker Compose stack and inspect services. |
| 25-45 min | Prometheus targets and metrics exploration. |
| 45-65 min | PromQL basics with counters, gauges, and histograms. |
| 65-80 min | Grafana dashboard walkthrough. |
| 80-95 min | Alert rules and Alertmanager routing. |
| 95-110 min | Blackbox monitoring and endpoint checks. |
| 110-120 min | Student challenge and recap. |

For a 4-hour workshop:

| Time | Topic |
| --- | --- |
| 0-30 min | Architecture and setup. |
| 30-75 min | Prometheus scraping, targets, labels, and exporters. |
| 75-120 min | PromQL deep dive. |
| 120-150 min | Grafana dashboard design. |
| 150-190 min | Alert rules, Alertmanager, and notification routing. |
| 190-220 min | Blackbox monitoring and failure simulation. |
| 220-240 min | Student project: add metric, panel, and alert. |

## 20. Student Challenge

Build a mini monitoring feature from end to end:

1. Add one new metric to the Python app.
2. Make Prometheus scrape it.
3. Write three PromQL queries for it.
4. Create one Grafana panel.
5. Create one alert rule.
6. Trigger the alert.
7. Explain the full path from metric generation to alert notification.

Students should be able to describe:

```text
Python app -> /metrics -> Prometheus scrape -> PromQL -> Grafana panel -> alert rule -> Alertmanager route
```

## 21. Cleanup

Stop all containers:

```bash
docker-compose down
```

If students want to remove built images and volumes, discuss the consequences first. For this lab, `docker-compose down` is usually enough.

## 22. Key Takeaways

- Prometheus stores numeric time series identified by metric names and labels.
- Exporters expose metrics in a format Prometheus can scrape.
- `up` is the fastest way to check scrape health.
- Counters need `rate()` or `increase()` for most operational queries.
- Gauges represent current values that can go up or down.
- Histograms support latency distributions and percentile estimates.
- Grafana visualizes PromQL queries from Prometheus.
- Alert rules detect conditions; Alertmanager handles routing and notification behavior.
- Blackbox monitoring checks user-visible endpoint behavior from the outside.

