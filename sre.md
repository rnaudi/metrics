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
- Redundant: `service:payment-api` when already in metric namespace
- High cardinality: `user_id`, `session_id`, `order_id`, `request_id`, `ip_address`
- IDs in paths: `endpoint:/api/orders/12345` → use `/api/orders/:id`
- Host-specific: `database_host:prod-db-1.aws.com` → use logical name
- Unbounded: `error_message:Connection timeout` → use `error_type:timeout`

### Good Tagging
- Consistent naming (lowercase, underscores)
- Cardinality < 100 (safe), < 1000 (manageable)
- Group values: `status:5xx` not individual codes
- Test: Can you aggregate meaningfully by this tag? 
- Tags are used for aggregation and filtering
- Enforce: Tag changes via PR review

---

### Anti-Patterns
- Losing tags across layers (if k8s node has `service:foo`, API/Product layer must preserve it)
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

## Visualization & Dashboard Design

### Chart Types by Purpose

**Time Series (Line/Area)**
- Request rate, error rate, throughput over time
- Multi-line: p50/p95/p99 latency on same chart (use separate y-axes if scales differ)
- Overlay error rate on traffic graph (correlate issues with load)
- Area stacked: breakdown by endpoint, status code, tenant tier
- Use log scale for metrics with wide ranges (1-10000)

**Heatmaps**
- Latency distribution over time (reveals bimodal patterns, gradual degradation)
- Request volume by hour/day (seasonality patterns)
- Error density across time + endpoints
- Better than line charts for showing distribution shape changes

**Time Comparisons**
- Current vs last week: `metric / week_before(metric)` as percentage
- Before/after deploy: vertical line annotation at deploy time
- Multi-series: this hour vs same hour yesterday/last week
- Use for: traffic patterns, conversion rates, error rates

**Correlation Charts**
- Dual y-axis: latency + error rate (spot correlations)
- Dual y-axis: traffic + CPU/memory (bounded resource) (capacity planning)
- Scatter: request volume vs p99 latency (find breaking points)
- Avoid: >3 metrics on one chart (cognitive overload)

**Distribution Snapshots**
- Histogram: current latency distribution (last 5min)
- Percentile bars: p50/p90/p95/p99 side-by-side
- Box plot: show median, IQR, outliers
- Use for: current state analysis, not trends

**Aggregation Views**
- Top N table: slowest endpoints, highest error rates, busiest tenants
- Top N bar: side-by-side comparison
- Tree map: proportional space allocation (which endpoint gets most traffic)
- Pie charts: avoid

**Status Indicators**
- Single value: current error rate, active users, queue depth
- Change indicator: +/-% vs last hour/day
- Traffic light: green/yellow/red based on thresholds
- SLO compliance: % + time remaining in error budget

### Dashboard Organization by Layer

**Node/Host Layer Dashboard**
```
Row 1: Resource Utilization
  - CPU % | Memory % | Disk I/O | Network I/O
Row 2: Runtime Metrics
  - JVM heap used/max | GC pause time (p95/p99) | Thread count
Row 3: Trends & Forecasts
  - CPU trend (7d) + forecast | Memory trend + forecast | Disk trend + forecast
Row 4: Outliers
  - Hosts with abnormal CPU | Hosts with high GC pause | Hosts with errors
```

**API Layer Dashboard**
```
Row 1: Golden Signals
  - Traffic (RPS) | Latency (p50/p95/p99) | Error Rate % | Saturation
Row 2: Time Comparisons
  - Traffic now vs last week | Latency now vs baseline | Error rate trend
Row 3: Endpoint Breakdown
  - Top endpoints by traffic | Top endpoints by latency | Top error types
Row 4: Status Codes
  - 2xx rate | 4xx rate | 5xx rate | Status code distribution
```

**Dependencies Layer Dashboard**
```
Row 1: Database
  - Query latency (p50/p95/p99) | Connection pool utilization | Query errors
Row 2: External APIs
  - API latency by service | Error rate by service | Circuit breaker state
Row 3: Cache
  - Hit rate % | Cache latency | Eviction rate | Memory usage
Row 4: Dependency Health
  - All dependencies status | Slowest dependency | Most failing dependency
```

**Product Layer Dashboard**
```
Row 1: Business KPIs
  - Revenue today | Orders/hour | Conversion rate | Active users
Row 2: Conversion Funnels
  - Checkout funnel (steps as bars) | Signup funnel | Feature adoption
Row 3: User Segmentation
  - Traffic by tenant tier | Revenue by tier | Errors by tier
Row 4: Growth & Trends
  - Revenue vs last week | Conversion trend (30d) | User growth rate
```

**Incident Response Dashboard (Cross-Layer)**
```
Row 1: Current State (last 15min)
  - Error rate | p99 latency | Active alerts | Traffic
Row 2: Recent Changes
  - Deploys (annotations) | Config changes | Traffic shifts
Row 3: Layer Drill-down
  - API errors by endpoint | Dependency errors | Host outliers
Row 4: Impact Analysis
  - Affected tenants | Affected endpoints | Blast radius
```

### Best Practices

**Annotations**
- Mark deployments (version, who, when)
- Mark incidents (start/end, severity, cause)
- Mark config changes (feature flags, scaling events)
- Mark A/B test windows

**Color Usage**
- Green: healthy, success, < threshold
- Yellow: warning, degraded, approaching threshold
- Red: critical, failure, > threshold
- Gray: no data, disabled, unknown
- Consistent across all dashboards

**Time Windows**
- Incident response: 15min, 1hr, 4hr
- Operations: 1hr, 6hr, 24hr
- Capacity planning: 7d, 30d, 90d
- Business metrics: today, this week, this month

---

## Alert Design

### Critical (Page)
- SLO burn rate critical (budget exhausted in < threshold)
- Complete outage (circuit breaker open)

### Warning (Ticket)
- SLO burn rate elevated (budget exhausted in warning_threshold)
- Error rate >Threshold
- Saturation >Threshold
- Dependency degraded, error rate >Threshold

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
