# sre math: threshold guide

> **Note:** How to set correct thresholds for alerts using real data and statistics. Examples based on an authentication service handling 200 req/s.

## Why This Matters

Bad metrics make analysis impossible. Use the right metrics type for each data.

Bad thresholds create two problems:
- Alert when nothing is wrong (alert fatigue, ignored pages)
- Don't alert when things are broken (outages you don't know about)

This guide helps you find the middle ground using your actual service data.

## Statistical Notation Quick Reference

- μ (mu) = mean/average
- σ (sigma) = standard deviation (how spread out the data is)
- p95 = 95th percentile (95% of values are below this)
- n = sample size (number of data points)

## Validation Checklist

- [ ] **Zero denominators**: Does it handle `requests = 0` safely? (`errors / max(requests, 1)`)
- [ ] **Low volume**: Does it work with <100 samples? (Use longer windows or skip alerting)
- [ ] **High volume**: Does it work with >1M samples? (Thresholds still meaningful?)
- [ ] **Percentiles**: Are they computed correctly? (Use distributions, never `avg(p95)`)
- [ ] **Confidence intervals**: Are they wide enough at low volume? (Wilson score for proportions)
- [ ] **Statistical thresholds**: Set using data, not gut feel (μ ± 3σ, or capacity testing)
- [ ] **Seasonality**: Does it account for daily/weekly patterns? (Time-of-week baselines)
- [ ] **Cardinality**: Is it bounded? (No `user_id`, `session_id`, `request_id` in tags)
- [ ] **Aggregation**: Can it merge across hosts/regions? (Distributions yes, pre-computed percentiles no)
- [ ] **Math correctness**: No `rate(rate())`, no `avg(percentiles)`, no averaging averages
- [ ] **Sample size**: Minimum samples required before alerting? (`n ≥ 100` for rates)
- [ ] **Multi-window**: Uses both short and long windows to reduce false positives?
- [ ] **Business impact**: Is the threshold tied to user impact or SLO?
- [ ] **Documentation**: Threshold reasoning documented with last tuned date?
- [ ] **Historical testing**: Validated against last 30 days of data? (<5% false positive rate)

---



## The Process

### Four-Step Monitor Definition

Every monitor follows this process:

1. **What question are you answering?** 
   - "Is the service processing requests?" → measure request rate
   - "Are users experiencing errors?" → measure error rate
   - "Is the service responsive?" → measure latency

**Metrics are for systems** (automated alerting, investigation). **Visualizations are for humans** (dashboards, intuition).

2. **Identify the metric**: What are you measuring? (request rate, error rate, latency, CPU, memory, etc.)
   - Determine metric type: distribution, timer, counter, ratio

3. **Analyze distribution properties**: How does this metric behave?
   - Calculate statistical properties: mean, standard deviation, percentiles
   - Identify patterns: stable vs variable, seasonal vs constant, bimodal distribution
   - Check for outliers and anomalies in baseline data

4. **Choose threshold approach**: Based on properties, what detects failures best?
   - Static thresholds: simple, predictable, require manual tuning
   - Dynamic thresholds: adaptive, complex, require sufficient data volume
   - Validate thresholds by simulating historical incidents. Would alerts fire? Deploy to staging with lower thresholds.

### Static vs Dynamic Thresholds

**Static Thresholds:** Fixed values that don't change unless manually updated. Simple to understand and debug. Predictable. Can produce false positives if data distribution changes. Require manual tuning as system evolves. Examples: "alert if error_rate > 5%", "alert if latency > 200ms", pre-computed time-of-week baselines.

**Dynamic Thresholds:** Calculated from recent/rolling data. Adapt automatically. More complex to debug. Can mask real issues if baseline becomes polluted. Require sufficient data volume. Examples: "alert if value > rolling_avg(7d) + 3σ", anomaly detection algorithms.

Static thresholds work well for stable metrics. Dynamic thresholds handle changing traffic patterns better but are harder to reason about.

Each example below shows both approaches.

---

## Example Service

**Auth Service**: HTTP REST service handling authentication and authorization
- **Normal traffic**: 200 req/s 
- **Stack**: 6 hosts, load balanced
- **Dependencies**: PostgreSQL, Redis, external SSO providers (SAML/OAuth)
- **User base**: mix of free/pro/enterprise

**Goal**: Set thresholds that catch real problems without false positives.

---

## RED and USE Metrics

RED and USE metrics provide a standard framework for monitoring services. For front-end services, they are a good starting point.

For more heavy backend and infrastructure services, I don't recommend following them blindly as data has different constraints and context.

## RED Metrics (Request-Level)

### R = Rate (Requests per Second)

#### Baseline Data (1 week)
```
Monday-Friday peak hours (9am-5pm): 280-320 req/s
Monday-Friday off-hours: 80-120 req/s
Weekend: 40-60 req/s
Overall mean: 200 req/s
Overall stddev: 85 req/s
```

#### Analysis
Traffic has strong daily/weekly patterns. Using simple mean + 3σ would give:
```
threshold = 200 + (3 × 85) = 455 req/s
```

But this misses context - 50 req/s is normal on Sunday, catastrophic on Tuesday at 2pm.

We have two alternatives, **static** and **dynamic** thresholds.

#### Static Threshold
Calculate mean and σ for each hour-of-week bucket (7 days × 24 hours = **168 buckets**):
```
Tuesday 2pm: μ = 300, σ = 25
Sunday 2pm: μ = 50, σ = 12
```

**Implementation:** Configure this at the observability platform level (Datadog, Prometheus with recording rules). Pre-compute μ and σ for each of the 168 time-of-week buckets from historical data, then reference the current bucket in alert conditions.

#### Threshold Options

**Option A: Static Time-of-Week Baseline**
```
threshold(hour, day) = μ(hour, day) + 3σ(hour, day)

Tuesday 2pm: 300 + (3 × 25) = 375 req/s
Sunday 2pm: 50 + (3 × 12) = 86 req/s
```
Accounts for weekly patterns. Requires manual recalculation as traffic grows.

**Option B: Dynamic Rolling Baseline**
```
threshold(current_time) = rolling_avg(same_hour_last_7d) - 3 × rolling_stddev(same_hour_last_7d)

# Calculates mean and σ from the last 7 occurrences of current hour
# Tuesday 2pm uses data from: last 7 Tuesdays at 2pm
```
Adapts automatically to traffic growth. More complex to debug. Can mask gradual degradation if last week's baseline was already degraded (e.g., you deployed a slow library version last Tuesday, now it's "normal"). For traffic drops, you usually want to be alerted regardless of recent trends.

Adapts to daily patterns. 3σ gives 99.7% confidence (0.3% false positive rate). 5-minute duration filters transient dips.

---

### E = Errors (Error Rate Percentage)

#### Baseline Data (1 week)
```
Total requests: 120,960,000
Total errors (5xx): 24,192
Overall error rate: 0.02% (24,192 / 120,960,000)
```

Hourly breakdown:
```
Mean error rate: 0.02%
Stddev: 0.008%
p95: 0.032%
p99: 0.042%
Max: 0.075%
```

#### Analysis
Error rate is a proportion. Consider what error rate impacts users, what sample size gives confidence, and what's statistically significant.

#### Threshold Options

**Option A: Static SLO-Based Threshold**
```
# If you have a 99.95% availability SLO:
error_budget = 1 - 0.9995 = 0.05%
threshold = 0.05%
```
Directly tied to business SLO. Easy to understand and justify. Doesn't adapt if baseline error rate trends up due to system changes.

**Option B: Dynamic Baseline + Statistical Margin**
```
# Recalculate weekly from last 7 days of data
threshold = rolling_p99(7d) + 2 × rolling_stddev(7d)
threshold = 0.042% + (2 × 0.008%) = 0.058%
```
Adapts to gradual changes in error patterns. Can mask real degradation if baseline becomes polluted. Requires clean training data.

**Multi-Window Burn Rate** (often works best)
```
# Combines static SLO with multiple time windows
if error_rate_1h > 0.05% AND error_rate_6h > 0.03%:
    ALERT

# Short-term error rate 2.5x normal (0.02% → 0.05%)
# Sustained over 6 hours
# Reduces false positives from transient spikes
```

#### Alert Rule
```yaml
alert: AuthServiceErrorRateHigh
condition: |
  error_rate_1h > 0.05% AND 
  error_rate_6h > 0.03% AND
  requests_1h > 12000  # 200 req/min minimum
duration: 0  # Already using windows
severity: critical
```

**Sample size check**:
```
At 200 req/s:
- 1-hour window: 720,000 requests
- 0.05% error rate: 360 errors expected
- Confidence interval: ±0.0005% (very tight)
```

With 720k samples, we can reliably detect 0.05% vs 0.02%.

---

### D = Duration (Latency)

#### Baseline Data (1 week)
```
p50: 45ms
p90: 120ms
p95: 180ms
p99: 450ms
p999: 1200ms
Mean: 78ms
Stddev: 156ms
```

#### Analysis
Latency is heavily right-skewed (long tail). Mean and stddev are misleading:
```
μ + 3σ = 78 + (3 × 156) = 546ms
```

This would alert on p99.5 latency, which happens regularly.

**NEVER use mean ± σ for latency.**

#### Threshold Options

**Option A: Static Percentile Thresholds**

Based on SLO: "95% of requests complete in < 200ms"
```
p95_threshold = 200ms
p99_threshold = 1000ms

if p95_latency_5min > 200ms:
    ALERT WARNING

if p99_latency_5min > 1000ms:
    ALERT CRITICAL
```
Simple to understand. Directly tied to SLO. Doesn't detect gradual degradation if it stays under threshold. Requires manual adjustment as system changes.

**Option B: Dynamic Baseline + Percentage Increase**

```
# Recalculate baseline from last 7 days
baseline_p95 = rolling_p95(7d) = 180ms
baseline_p99 = rolling_p99(7d) = 450ms

# Alert on relative degradation
threshold_p95 = baseline_p95 × 1.5 = 270ms
threshold_p99 = baseline_p99 × 2.0 = 900ms

if p95_latency_5min > threshold_p95:
    ALERT WARNING

if p99_latency_5min > threshold_p99:
    ALERT CRITICAL
```
Detects relative degradation even if under SLO. Adapts to system improvements. Can mask gradual degradation if baseline trends up. More complex to debug.

#### Alert Rules
```yaml
# SLO breach
alert: AuthServiceLatencyP95High
condition: p95(http_request_duration_seconds) > 0.2
duration: 10 minutes
severity: warning

# Severe degradation
alert: AuthServiceLatencyP99Critical
condition: p99(http_request_duration_seconds) > 1.0
duration: 5 minutes
severity: critical
```

Percentiles directly measure user experience. Not skewed by outliers (p95 ignores worst 5%). Can aggregate across hosts using distributions.

---

## USE Metrics (Resource-Level)

### U = Utilization (CPU)

#### Baseline Data (4 hosts, 1 week)
Per-host CPU usage:
```
Mean: 45%
Stddev: 12%
p95: 65%
p99: 72%
Max observed: 78%
```

#### Analysis
CPU is a capacity metric. At what percentage does performance degrade? What percentage leaves headroom for load spikes?

Load testing results:
```
At 60% CPU: p95 latency = 180ms (normal)
At 75% CPU: p95 latency = 350ms (degraded)
At 85% CPU: p95 latency = 1200ms (severe)
At 95% CPU: requests timing out
```

#### Threshold Options

**Option A: Static Capacity Thresholds**

```
Warning: 70% (approaching saturation)
Critical: 80% (degraded performance confirmed)
```

Based on load testing. At 75% CPU, p95 latency degrades to 350ms (1.9x normal). At 80% CPU, clear performance impact observed.

NOT using μ + 3σ because:
```
μ + 3σ = 45 + (3 × 12) = 81%
```
At 81%, service is already degraded. Need to alert earlier.

Based on actual load testing. Clear capacity planning. Doesn't account for efficiency improvements or code changes that reduce CPU usage.

**Option B: Dynamic Baseline + Headroom**

```
# Recalculate from last 7 days
baseline_p95 = rolling_p95(cpu_percent, 7d) = 65%
headroom = 15%

threshold_warning = baseline_p95 + headroom = 80%
threshold_critical = baseline_p95 + (2 × headroom) = 95%
```

Adapts to code optimizations that reduce CPU usage. Detects unusual spikes. Can mask gradual CPU creep. Requires re-validation of performance at new thresholds.

For capacity metrics, static thresholds usually work better. They're tied to physical limits and performance characteristics that don't change without load testing.

#### Alert Rules
```yaml
# Warning: sustained high CPU
alert: AuthServiceHostCPUHigh
condition: avg(cpu_percent) > 70
duration: 15 minutes
severity: warning

# Critical: CPU saturation
alert: AuthServiceHostCPUSaturated
condition: avg(cpu_percent) > 80
duration: 5 minutes
severity: critical

# Forecast: will hit 80% in next hour
alert: AuthServiceHostCPUTrending
condition: forecast(cpu_percent, 1h) > 80
severity: warning
```

70%: Time to investigate or scale (15min allows for human response). 80%: Immediate action needed (5min catches fast degradation). Forecast: Proactive capacity management.

---

### S = Saturation (Memory Pressure)

#### Baseline Data (JVM heap, 4GB max per host)
```
Mean heap used: 2.1 GB (52%)
Stddev: 0.4 GB
p95: 2.8 GB (70%)
p99: 3.1 GB (77%)
GC pause time p99: 45ms
```

#### Analysis
Memory is different from CPU:
- Gradual increase until OOM
- GC frequency/duration indicates pressure
- Need to catch before OOM occurs

Observed behavior:
```
< 75% heap: Normal GC (20-50ms pauses)
75-85% heap: Frequent GC (100-200ms pauses)
> 85% heap: Constant GC (500ms+ pauses)
> 95% heap: OOM imminent
```

#### Threshold Options

**Option A: Static Capacity Thresholds**

```
# Memory usage thresholds
Warning: heap > 75% sustained (3.0 GB)
Critical: heap > 85% sustained (3.4 GB)

# GC pressure thresholds
Warning: p99 GC pause > 100ms
Critical: p99 GC pause > 500ms
```

Based on observed behavior. At 75% heap, GC pauses start increasing (100-200ms). At 85% heap, constant GC thrashing (500ms+ pauses).

Based on actual JVM behavior. Prevents OOM. Doesn't adapt if heap size changes or memory usage patterns improve.

**Option B: Dynamic Baseline + GC Pressure**

```
# Recalculate from last 7 days
baseline_heap_p95 = rolling_p95(heap_used_percent, 7d) = 70%
threshold_warning = baseline_heap_p95 + 10% = 80%
threshold_critical = baseline_heap_p95 + 20% = 90%

# Combined with GC pressure (always monitor)
gc_pause_threshold = rolling_p99(gc_pause_seconds, 7d) × 2
```

Adapts to memory optimizations. Detects unusual memory growth. Can mask memory leaks if baseline trends up gradually. Risky near OOM limits.

For memory, static thresholds are safer. OOM is a hard limit and GC behavior is predictable at specific utilization levels.

#### Alert Rules
```yaml
# High heap usage
alert: AuthServiceMemoryHigh
condition: |
  (heap_used / heap_max) > 0.75 AND
  rate(gc_pause_seconds) > 10/min
duration: 10 minutes
severity: warning

# Memory saturation
alert: AuthServiceMemorySaturated
condition: |
  (heap_used / heap_max) > 0.85 OR
  p99(gc_pause_seconds) > 0.5
duration: 5 minutes
severity: critical
```

Composite signal: High heap + frequent GC = real pressure, not just normal usage spike.

---

### E = Errors (System-Level)

#### Baseline Data (Disk I/O errors, network errors)
```
Disk read errors: 0.002 errors/hour (rare)
Network connection resets: 1.5/minute (background noise)
```

#### Thresholds
For rare events, use absolute counts:

```yaml
# Disk errors (should be zero)
alert: AuthServiceHostDiskErrors
condition: disk_read_errors > 0
duration: 0
severity: critical

# Network errors (expect some background noise)
alert: AuthServiceHostNetworkErrors
condition: rate(network_errors) > 10/min
duration: 5 minutes
severity: warning
```

**Why**: System errors are discrete events. Any disk error is concerning. Network errors need rate threshold due to retries/transients.

---

## Layered Metrics (From sre.md)

### Layer 1: Host/Node Metrics

#### Example: Disk I/O Saturation
```
Metric: disk_io_util_percent
Baseline: Mean 25%, stddev 8%, p95 38%, p99 45%
```

**Load test findings**:
```
< 60%: Normal latency
60-80%: Increased latency (2x)
> 80%: Severe latency (10x), queue building
```

**Threshold**:
```yaml
alert: AuthServiceHostDiskSaturated
condition: disk_io_util_percent > 60
duration: 10 minutes
severity: warning
```

Not using μ + 3σ (25 + 24 = 49%) because performance degrades at 60%.

---

### Layer 2: API Metrics (Per-Endpoint)

#### Example: Login Endpoint Error Rate

Login is critical, has different baseline than overall API:
```
Baseline:
- /api/login: 0.01% error rate (stricter than overall 0.02%)
- Traffic: 60 req/s (30% of total)
- User impact: Blocks access entirely
```

**Threshold**: Tighter than overall API
```yaml
alert: AuthServiceLoginErrors
condition: |
  error_rate{endpoint="/api/login"} > 0.03% AND
  requests{endpoint="/api/login"} > 3600/min
duration: 5 minutes
severity: critical
```

**Why stricter**: 
- Business critical
- Lower baseline (0.01% vs 0.02%)
- Direct user access impact

---

### Layer 3: Dependencies

#### Example: PostgreSQL Connection Pool

```
Metric: db_connection_pool_utilization
Max connections: 50
Baseline: Mean 12 (24%), p95 28 (56%), p99 35 (70%)
```

**Threshold setting**:
```
At 80% (40 connections): Queue starts building
At 90% (45 connections): Requests timing out
At 100% (50 connections): Complete failure
```

```yaml
# Connection pool pressure
alert: AuthServiceDatabasePoolHigh
condition: db_connection_pool_utilization > 0.7
duration: 5 minutes
severity: warning

# Connection pool exhaustion
alert: AuthServiceDatabasePoolExhausted
condition: db_connection_pool_utilization > 0.9
duration: 1 minute
severity: critical
```

**Why these thresholds**:
- 70%: Early warning (still has capacity, time to investigate)
- 90%: Imminent failure (immediate action)
- Short duration for 90% (can't wait 5 minutes)

#### Example: External API Latency (SSO Provider)

```
Metric: external_api_latency{service="sso_provider"}
Baseline: p50 150ms, p95 600ms, p99 1200ms
SLA from vendor: p95 < 800ms
```

**Threshold**: Based on vendor SLA + margin
```yaml
alert: SSOProviderLatencySLABreach
condition: |
  p95(external_api_latency{service="sso_provider"}) > 1000ms
duration: 10 minutes
severity: warning
```

1000ms = vendor p95 SLA (800ms) + 25% margin

**Why**: Don't alert on vendor's p99 (1200ms) - that's expected. Alert when they breach their SLA commitment.

---

### Layer 4: Product/Business Metrics

#### Example: Success Rate (End-to-End Login Flow)

Using journey metrics from README.md:
```
Flow: login_request → validate_credentials → check_mfa → create_session → success
Baseline: C(t) = 0.92 (92% success rate)
Traffic: 200 attempts/min
```

**Baseline success by step**:
```
Step 1→2 (T1): 0.98 (validate credentials)
Step 2→3 (T2): 0.97 (check MFA)
Step 3→4 (T3): 0.99 (create session)
Step 4→5 (T4): 0.98 (success)

C = 0.98 × 0.97 × 0.99 × 0.98 = 0.92
```

**Observed data (1 week)**:
```
C(t) varies between 0.88 - 0.95
Mean C: 0.92
Stddev C: 0.015
```

**Variance calculation**:
```
At 200 attempts/min, 5-min window:
n = 1000 attempts
Var(C) ≈ C(1-C)/n = 0.92 × 0.08 / 1000 = 0.0000736
SE(C) = sqrt(0.0000736) = 0.0086 = 0.86%
```

**Control limits (3σ)**:
```
UCL = 0.92 + (3 × 0.0086) = 0.946
LCL = 0.92 - (3 × 0.0086) = 0.894
```

**Threshold**:
```yaml
alert: AuthServiceLoginSuccessLow
condition: |
  login_success_rate < 0.89 AND
  login_attempts_last_5min > 200
duration: 15 minutes  # 3 consecutive windows
severity: warning
```

**Why**:
- 0.89 is LCL (statistically significant drop)
- Requires 200+ attempts (statistical significance)
- 15 minutes = 3 windows (avoids single-window noise)

---

## Statistical Significance: When to Alert

### Problem: Low Traffic Edge Case

**Scenario**: Weekend night, traffic drops to 2 req/s
```
5-min window: 600 requests (2 req/s × 60s × 5min)
6 errors observed
Error rate: 6/600 = 1%
```

Normal error rate is 0.02%. Should we alert?

### Wilson Score Confidence Interval

When you have low traffic, a single error can make the error rate look terrible. Wilson Score tells you: "given this sample size, what's the real error rate likely to be?"

**When to use this:** Traffic < 1000 requests in your alert window.

**Simple rule:** If n < 100, don't alert on error rate alone. Require longer duration or multiple windows.

```
p = 0.01 (observed error rate: 6/600)
n = 600 (sample size: total requests)
z = 1.96 (95% confidence level)

center = (p + z²/(2n)) / (1 + z²/n)
       = (0.01 + 3.84/1200) / (1 + 3.84/600)
       = (0.01 + 0.0032) / 1.0064
       = 0.0131

margin = z × sqrt(p(1-p)/n + z²/(4n²)) / (1 + z²/n)
       = 1.96 × sqrt(0.01×0.99/600 + 3.84/1440000) / 1.0064
       = 1.96 × sqrt(0.0000165 + 0.00000267) / 1.0064
       = 1.96 × 0.00427 / 1.0064
       = 0.0083

CI = [0.0131 - 0.0083, 0.0131 + 0.0083]
   = [0.48%, 2.14%]
```

**Analysis**: With 95% confidence, true error rate is somewhere between 0.48% and 2.14%.

**Baseline**: 0.02% is far outside this interval → statistically significant increase.

**BUT**: Wide confidence interval due to small sample size. Could be transient.

### Alert Logic with Sample Size
```yaml
alert: AuthServiceErrorRateHighLowTraffic
condition: |
  error_rate_5min > 0.1% AND
  requests_5min >= 600 AND
  error_rate_15min > 0.05%  # Require sustained over longer window
duration: 0
severity: warning
```

At low traffic, require longer duration OR multiple windows to confirm.

---

## Composite Alerts: Correlating Signals

### Example: High Latency Root Cause

When p95 latency > 200ms, what's the cause?

```yaml
alert: AuthServiceLatencyHighCPU
condition: |
  p95(latency) > 0.2 AND
  cpu_percent > 70
message: "High latency caused by CPU saturation"
severity: critical
action: "Scale horizontally"

alert: AuthServiceLatencyHighDatabaseSlow
condition: |
  p95(latency) > 0.2 AND
  p95(db_query_duration) > 0.1 AND
  cpu_percent < 60
message: "High latency caused by slow database queries"
severity: critical
action: "Check database performance, review slow queries"

alert: AuthServiceLatencyHighExternalSSO
condition: |
  p95(latency) > 0.2 AND
  p95(external_api_latency{service="sso_provider"}) > 1.0 AND
  cpu_percent < 60 AND
  p95(db_query_duration) < 0.05
message: "High latency caused by external SSO provider"
severity: warning
action: "Contact SSO provider support"
```

**Why**: Same symptom (high latency), different root causes, different actions.

---

## Summary: Threshold Setting Decision Tree

```
0. Just starting? Don't have baseline data yet?
   → Use conservative absolute thresholds:
     - Error rate > 1%
     - p99 latency > 1s
     - CPU > 80%
   → Tune after 1-2 weeks of data

1. Is it a CAPACITY metric (CPU, memory, connections)?
   → Use load testing to find saturation point
   → Set threshold below saturation (e.g., 70% for 80% saturation)
   
2. Is it a LATENCY metric?
   → Use percentiles (p95, p99), never mean + stddev
   → Set based on SLO or baseline × 1.5-2x
   
3. Is it an ERROR RATE?
   → Use SLO-based threshold (error budget)
   → Require minimum sample size (n ≥ 100)
   → Use multi-window burn rate for accuracy
   
4. Is it a TRAFFIC metric with daily patterns?
   → Use time-of-week baseline: μ(hour, day) ± 3σ
   → Adapt thresholds to expected patterns
   
5. Is it a RARE EVENT (disk errors, OOM)?
   → Use absolute count thresholds (> 0 for critical)
   → Low tolerance for system-level errors
   
6. Is it HIGH VARIANCE (CV > 0.5)?
   → Use moving averages or percentile thresholds
   → Require sustained breach (longer duration)
   
7. Is it BUSINESS-CRITICAL (revenue, conversion)?
   → Use journey metrics (conversion rate)
   → Set control limits using μ ± 3σ
   → Require statistical significance (confidence intervals)
```
