# sre

> **Note:** This is a reference guide covering observability concepts and patterns. Not everything applies to every situation - use what makes sense for your scale and context. Concepts and ideas are universal; implementation details are flexible.
>
> **AI Usage:** Some examples in this guide were generated with AI assistance to illustrate concepts. The patterns and approaches are based on real SRE practices. Always validate with your own context.

## References
- [AWS Observability Best Practices](https://aws-observability.github.io/observability-best-practices/)
- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [Netflix Application Monitoring](https://netflixtechblog.com/telltale-netflix-application-monitoring-simplified-5c08bfa780ba)
- [Site Reliability Engineering with Java Microservices](https://github.com/mrbajaj/books/blob/master/sre-with-java-microservices.pdf)
- [Brendan Gregg - Linux Performance](https://www.brendangregg.com/linuxperf.html)
- [A Practitioner's Guide to Wide Events](https://jeremymorrell.dev/blog/a-practitioners-guide-to-wide-events/)
- [All you need is wide events, not metrics](https://isburmistrov.substack.com/p/all-you-need-is-wide-events-not-metrics)

---

## Core

### Metric Types
- Distributions > histograms > gauges for latency/duration

### Observability Strategy
- Wide events + structured logs give you the most flexibility
- Normalize tags across services/environments
- Instrument at boundaries (HTTP handlers, DB calls, external APIs)
- Golden Signals: latency, traffic, errors, saturation
- Observability layers:
  - **Node/Host**: CPU, memory, disk/network I/O, JVM/Go runtime
  - **API**: Latency, throughput, errors per endpoint
  - **Dependencies**: DB, HTTP clients, cache, external APIs
  - **Product**: Feature usage, conversion funnels, user behavior
* (Note: This is a layer I personally like, see AWS and Netflix references for similar alternatives)

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
- Ask yourself: Can you aggregate meaningfully by this tag?
- Tags are for aggregation and filtering
- Enforce tag changes via PR review

## Cost Considerations

### Datadog Pricing
- Custom metrics are billed per unique time series (metric name + unique tag combination)
- Example: `http.requests{endpoint:/api/checkout, method:POST, status:200, env:prod, region:us-east-1}` = 1 time series
- High cardinality tags multiply costs exponentially
- Real example: Add `user_id` tag (1000 users) × existing tags (100 combos) = 100k time series
- Check your custom metrics count in Datadog → Usage & Cost

### Cost Control
- Track cardinality: Review top metrics by time series count monthly
- Remove unused metrics after 30 days
- Group tags: `status:5xx` not `status:500|501|502|503`


### Custom Metrics vs Wide Events

Since around 2020, new tools like Honeycomb have been built on OLAP databases (like ClickHouse) to improve log and event analysis. This led to the wide events approach - structured events, usually built on OpenTelemetry.

Still in the innovation stage, worth looking into. In my experience (I've worked with an in-house Datadog/Honeycomb), wide events eliminate most custom metrics and replace traditional tracing tools.

The same tagging principles apply to wide events. Wide events work like distributions/timers. The main trade-off is log sampling.

---

The following sections summarize key concepts from "SRE with Java Microservices" (see references above). Takes about 2-3 hours to read, and you can skim some sections.

### Anti-Patterns

Common mistakes that break monitoring:

- **Losing tags across layers**: If k8s node has `service:foo`, preserve it in API/Product layer
- **Averaging percentiles**: `avg(p95)` across hosts is meaningless - use distributions
- **Averaging averages**: Don't average CPU across unequal time windows or request volumes
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
- Multi-line: p50/p95/p99 latency on same chart (separate y-axes if scales differ)
- Overlay error rate on traffic graph to correlate issues with load
- Area stacked: breakdown by endpoint, status code, tenant tier
- Use log scale for wide ranges (1-10000)

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

### Full example: Dashboard Organization by Layer

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

### SLO Burn Rate Alerting

**Formula:**
```
Error Budget = 1 - SLO target
Burn Rate = (errors in window) / (total requests in window) / Error Budget

Example: 99.9% SLO (0.1% error budget)
- Observed error rate: 0.5% over 1hr
- Burn Rate = 0.5% / 0.1% = 5x
- At 5x burn rate, budget exhausted in: 30 days / 5 = 6 days
```

**Alert Thresholds:**
- **Critical (Page)**: 1hr window burn rate >14.4x (budget gone in 2 hrs)
- **Warning (Ticket)**: 6hr window burn rate >6x (budget gone in 5 days)
- **Multi-window**: Require BOTH short + long window breached to reduce false positives

**At low traffic:**
- Use longer windows (6hr+) for statistical significance
- Don't alert on <100 requests - sample size is too small

### Critical (Page)
- SLO burn rate >14.4x (1hr window)
- Complete outage (0 successful requests in 5min)

### Warning (Ticket)
- SLO burn rate >6x (6hr window)
- Error rate >1% sustained (15min+)
- Saturation >80% sustained (30min+)
- Dependency circuit breaker open

### Structure
```
Alert: [Service] - [What]
Threshold: [Current] vs [Expected]
Impact: [User-facing|Internal]
Runbook: [Link]
Dashboard: [Link]
```

---

### Metric Naming
```
<namespace>.<component>.<metric>
payment.api.request.duration
payment.db.query.duration
payment.cache.hit.count
```

Keep metric naming consistent across services and layers.

### Monitor Types
- **Metric**: Threshold crossing
- **Anomaly**: Unusual behavior detection
- **Outlier**: One host behaving differently
- **Forecast**: Predict threshold crossing
- **Composite**: Boolean logic across monitors

---

## Signal & Noise

### Signal-to-Noise Ratio
- Signal = real system behavior, Noise = random fluctuations
- High SNR = actionable alerts, Low SNR = alert fatigue
- Increase SNR: use longer windows, smoothing, percentiles instead of averages

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
- MAD: more robust to extremes
- Better approach: use distributions (p95, p99) instead of filtering outliers

### Seasonality
- Compare to same time last week: `week_before(metric)`
- Alert on deviation from baseline, not absolute threshold
- Forecast: "disk full in 3d at current trend"

### Alert Windows
- Too short = false positives, too long = delayed detection
- Rule of thumb: window ≥ 3-5× noise frequency (30s fluctuation → 2-3min window)
- Multi-window: require 1min AND 10min both breached to reduce false positives

### Sample Size
- Small sample = wide confidence interval, low confidence (10 requests vs 10k requests)
- 1 error / 2 requests = 50% ± 70% - meaningless
- Use Wilson score interval for proportions (see sre_math.md)
- Don't alert when you don't have enough samples

### Statistical Tests
- Chi-squared: categorical (conversion rates)
- T-test: continuous (latency)
- Need sufficient traffic for minimum detectable effect
- Verify significance before alerting on "degradation"
