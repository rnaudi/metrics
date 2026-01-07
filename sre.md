# SRE Observability: Best Practices & Rules of Thumb

## References
- [AWS Observability Best Practices](https://aws-observability.github.io/observability-best-practices/)
- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [Netflix Application Monitoring](https://netflixtechblog.com/telltale-netflix-application-monitoring-simplified-5c08bfa780ba)
- [Site Reliability Engineering with Java Microservices](https://github.com/mrbajaj/books/blob/master/sre-with-java-microservices.pdf)
- [Brendan Gregg - Linux Performance](https://www.brendangregg.com/linuxperf.html)
- [A Practitioner's Guide to Wide Events](https://jeremymorrell.dev/blog/a-practitioners-guide-to-wide-events/)
- [All you need is wide events, not metrics](https://isburmistrov.substack.com/p/all-you-need-is-wide-events-not-metrics)

---

## Core Principles

### Metric Types
- Distributions > histograms > gauges for latency/duration
- Counters for events (requests, errors, completions)
- Gauges for snapshots (pool sizes, queue depth, utilization) - mostly obsolete with wide events
- Distributions: accurate percentiles post-collection, global aggregation across hosts

### Observability Strategy
- If possible adopt: Wide events + structured logs
- Normalize tags across services/environments
- Instrument at boundaries (HTTP handlers, DB calls, external APIs)
- Golden Signals: latency, traffic, errors, saturation
- Observability layers:
  - **Node/Host**: CPU, memory, disk/network I/O, JVM/Go runtime
  - **API**: Latency, throughput, errors per endpoint
  - **Dependencies**: DB, HTTP clients, cache, external APIs
  - **Product**: Feature usage, conversion funnels, user behavior

## Tagging Strategy

### Standard Tags
- `env:production|staging|dev`
- `region:us-east-1`, `az:us-east-1a`
- `version:2.1.0` (canary analysis)
- `cluster:prod-1`, `namespace:payments`
- `tenant_id:acme` (bounded cardinality only)
- `tenant_tier:enterprise|pro|free`
- `user_tier:premium|free`

### Bad Tagging
- ❌ Redundant: `service:payment-api` when already in metric namespace
- ❌ High cardinality: `user_id`, `session_id`, `order_id`, `request_id`, `ip_address`
- ❌ IDs in paths: `endpoint:/api/orders/12345` → use `/api/orders/:id`
- ❌ Host-specific: `database_host:prod-db-1.aws.com` → use logical name
- ❌ Unbounded: `error_message:Connection timeout` → use `error_type:timeout`

### Good Tagging
- Consistent naming (lowercase, underscores)
- Cardinality < 100 (safe), < 1000 (manageable)
- Group values: `status:5xx` not individual codes
- Test: Can you aggregate meaningfully by this tag?
- Enforce: Tag changes via PR review

---

### Anti-Patterns
- High cardinality tags (user_id, order_id, session_id, timestamps)
- Losing tags across layers (if node has `service:foo`, API layer must preserve it)
- Bad math:
  - **Averaging percentiles**: `avg(p95)` across hosts is meaningless - use distributions that aggregate correctly
  - **Averaging averages**: Don't average CPU across unequal time windows or different request volumes
  - **Rates on rates**: Taking rate of a rate compounds errors - start from raw counters
  - **Division by zero**: `error_rate = errors / requests` breaks when requests = 0, use `errors / max(requests, 1)`
  - **Sample size ignorance**: 1 error out of 2 requests ≠ 1000 errors out of 2000 requests (confidence intervals matter)
  - **Simpson's Paradox**: Aggregating across different populations can reverse trends
  - **Survivorship bias**: Only measuring successful requests ignores failed/timed-out ones
  - **Alert on noise**: Thresholds without considering variance/seasonality

---

## Visualization Best Practices

| Metric Type | Visualization | Use Case |
|-------------|---------------|----------|
| Counter → Rate | Line graph | Request rate, error rate over time |
| Distribution | Line (multi-percentile) | p50, p95, p99 latency on same chart |
| Distribution | Heatmap | See latency distribution shift over time |
| Gauge | Line graph | Resource utilization trends |
| Top N | Table/Bar | Slowest endpoints, highest error sources |
| SLO | Single number + trend | Current compliance vs target |

---

## Alert Design

### Critical (Page)
- SLO burn rate critical (budget exhausted in < 1hr)
- Complete outage
- Error rate >5% or p99 >5x baseline

### Warning (Ticket)
- SLO burn rate elevated (budget exhausted in 6-24hrs)
- Error rate >1%
- Saturation >80%
- Dependency degraded

### Structure
```
Alert: [Service] - [What]
Threshold: [Current] vs [Expected]
Impact: [User-facing|Internal]
Runbook: [Link]
Dashboard: [Link]
```

---

## Signal & Noise

### Signal-to-Noise Ratio
- Signal = real system behavior, Noise = random fluctuations/errors
- High SNR = actionable, Low SNR = alert fatigue
- Increase SNR: longer windows, smoothing, percentiles not averages

### Variance & Thresholds
- Set thresholds using σ: `threshold = baseline + (N × σ)`
  - N=2: 95% confidence
  - N=3: 99.7% confidence
- Coefficient of Variation (CV = σ/mean):
  - CV <0.1: tight thresholds ok
  - CV >0.5: need wide thresholds

### Smoothing
- Moving average: 5min for high-freq, 1hr for daily patterns
- Exponential: weight recent data more
- Rollup for storage:
  - 1s → 24hrs
  - 1min → 7d
  - 1hr → 90d+

### Outliers
- Z-score: `(value - mean) / σ`, flag if |Z| >3
- IQR: outlier if `value < Q1 - 1.5×IQR` or `value > Q3 + 1.5×IQR`
- MAD: robust to extremes
- Better: use distributions (p95, p99) instead of filtering

### Seasonality
- Compare to same time last week: `week_before(metric)`
- Alert on deviation from baseline, not absolute threshold
- Forecast: "disk full in 3d at current trend"

### Alert Windows
- Too short = false positives, too long = delayed detection
- Rule: window ≥ 3-5× noise frequency (30s fluctuation → 2-3min window)
- Multi-window: 1min AND 10min both breached (reduces false positives)

### Sample Size
- Small N = wide CI, low confidence (10 requests vs 10k requests)
- 1 error / 2 requests = 50% ± 70% (meaningless)
- Use Wilson score interval for proportions
- Don't alert on insufficient samples

### Statistical Tests
- Chi-squared: categorical (conversion rates)
- T-test: continuous (latency)
- Need sufficient traffic for minimum detectable effect
- Verify significance before alerting on "degradation"

---

### Metric Naming
```
<namespace>.<component>.<metric>
payment.api.request.duration
payment.db.query.duration
payment.cache.hit.count
```

Make sure metric naming is consistent across services and layers

### Monitor Types
- **Metric**: Threshold crossing
- **Anomaly**: Unusual behavior detection
- **Outlier**: One host behaving differently
- **Forecast**: Predict threshold crossing
- **Composite**: Boolean logic across monitors
