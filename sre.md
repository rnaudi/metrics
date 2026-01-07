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
- Prefer distributions/timers over histograms for latency measurement
- Prefer distributions/timers over gauges for duration tracking
- Use counters for event counts (requests, errors, completions)
- Use gauges for point-in-time snapshots (pool sizes, queue depths, utilization)
- **Note**: Gauges largely obsolete with wide events - prefer structured events with context
- Distributions provide accurate percentiles (p50, p95, p99) post-collection
- Distributions aggregate globally across hosts without data loss

### Observability Strategy
- Prefer wide events and structured logs
- Normalize tags across all services and environments
- Instrument at service boundaries (HTTP handlers, DB calls, external APIs)
- Monitor Golden Signals: latency, traffic, errors, saturation (bounded resources)
- Track business metrics alongside technical metrics
- Split observability in layers:
  - Node / Host: CPU, Memory, Disk I/O, Network I/O, JVM/Golang VM
  - API Network: Latency, Throughput, Errors per endpoint
  - IO Clients: DB clients, HTTP clients, Messaging clients, Queue clients, any external clients
  - Product metrics: Metrics that answer product questions
    - How many users are using this feature?
    - When are users using this feature? Do we notice any pattern? Seasonality?

### Anti-Patterns
- Never use user_id, order_id, session_id, or timestamps as tags (high cardinality)
- Do not lose data tags across layers:
  - If we have a node in Kubernetes, tagged for a service `service:my-service`, we should we able to aggregate data for that tag in superior layers
  - Layers acts as wrappers around the data, so we always and should preserve data and tags
- Bad math, common statistical errors:
  - **Averaging percentiles**: `avg(p95)` across hosts is meaningless - use distributions that aggregate correctly
  - **Averaging averages**: Don't average CPU across unequal time windows or different request volumes
  - **Rates on rates**: Taking rate of a rate compounds errors - start from raw counters
  - **Division by zero**: `error_rate = errors / requests` breaks when requests = 0, use `errors / max(requests, 1)`
  - **Sample size ignorance**: 1 error out of 2 requests ≠ 1000 errors out of 2000 requests (confidence intervals matter)
  - **Simpson's Paradox**: Aggregating across different populations can reverse trends
  - **Survivorship bias**: Only measuring successful requests ignores failed/timed-out ones
  - **Alert on noise**: Setting thresholds without considering variance 

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
- SLO burn rate critical (exhaust budget in < 1 hour)
- Complete service outage
- Error rate > 5%
- p99 latency > 5x baseline

### Warning (Ticket)
- SLO burn rate elevated (exhaust budget in 6-24 hours)
- Error rate > 1%
- Resource saturation > 80%
- Dependency degradation

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

Make sure metric naming is consistent across services and layers

### Monitor Types
- **Metric**: Threshold crossing
- **Anomaly**: Unusual behavior detection
- **Outlier**: One host behaving differently
- **Forecast**: Predict threshold crossing
- **Composite**: Boolean logic across monitors
