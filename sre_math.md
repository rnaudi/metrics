# sre math: threshold guide

> **Note:** How to set correct thresholds for alerts using real data and statistics. Examples based on an authentication service handling 200 req/s.
>
> **AI Usage:** Some numerical examples and statistical formulas in this guide were generated with AI assistance to illustrate concepts. The methodologies and approaches are based on real SRE practices. Always validate with your own data.

## Why This Matters

Setting good thresholds is hard. Bad thresholds cause two problems:
- Alert when nothing is wrong (alert fatigue, ignored pages)
- Don't alert when things are broken (outages you don't know about)

This guide shows you how to find the middle ground using your actual service data and basic statistics.

## Statistical Notation Quick Reference

- **μ (mu)** = mean/average
- **σ (sigma)** = standard deviation (how spread out the data is)
- **p95** = 95th percentile (95% of values are below this)
- **n** = sample size (number of data points)

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

1. **What question are you answering?** Always start with the question, not the metric.
   - "Is the service processing requests?" → measure request rate
   - "Are users experiencing errors?" → measure error rate
   - "Is the service responsive?" → measure latency

   Metrics are for systems (automated alerting). Visualizations are for humans (dashboards, investigation).

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

**Static Thresholds:** Fixed values you set manually. Simple to understand and debug. Predictable. Can give false positives if your traffic patterns change. Need manual updates as your system grows.

Examples: "alert if error_rate > 5%", "alert if latency > 200ms", pre-computed time-of-week baselines.

**Dynamic Thresholds:** Calculated automatically from recent data. Adapt to traffic changes. More complex to debug. Can hide real problems if your baseline data includes bad periods. Need enough traffic to be reliable.

Examples: "alert if value > rolling_avg(7d) + 3σ", anomaly detection algorithms.

Static works well for stable metrics. Dynamic handles changing traffic better but is harder to understand when it fires.

Each example below shows both approaches so you can pick what fits your service.

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

RED and USE metrics are standard frameworks for monitoring. They're a good starting point for front-end services.

For backend and infrastructure services, use them as a guide but adapt to your specific needs. Data services have different constraints and context.

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
Traffic has strong daily/weekly patterns. Using simple mean + 3σ gives:
```
threshold = 200 + (3 × 85) = 455 req/s
```

This misses context. 50 req/s is normal on Sunday, catastrophic on Tuesday at 2pm.

You have two approaches: static and dynamic thresholds.

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
Error rate is a proportion. Think about three things: what error rate actually impacts users, how many samples you need to be confident, and whether changes are statistically significant or just noise.

#### Threshold Options

**Option A: Static SLO-Based Threshold**
```
# If you have a 99.95% availability SLO:
error_budget = 1 - 0.9995 = 0.05%
threshold = 0.05%
```
Directly tied to your business SLO. Easy to explain to anyone. Downside: doesn't adapt if your baseline error rate creeps up over time.

**Option B: Dynamic Baseline + Statistical Margin**
```
# Recalculate weekly from last 7 days of data
threshold = rolling_p99(7d) + 2 × rolling_stddev(7d)
threshold = 0.042% + (2 × 0.008%) = 0.058%
```
Adapts to gradual changes in error patterns. Downside: if last week had problems, this becomes your new "normal" and you won't catch it. Needs clean training data.

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
Latency has a long tail (heavily right-skewed). Mean and stddev mislead you:
```
μ + 3σ = 78 + (3 × 156) = 546ms
```

This fires at p99.5 latency, which happens all the time.

Never use mean ± σ for latency. Use percentiles.

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
Simple to understand. Tied directly to your SLO. Downside: won't catch gradual slowdowns if they stay under threshold. You'll need to adjust manually as your system changes.

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
Catches relative degradation even when you're under SLO. Adapts when you make improvements. Downside: if latency creeps up slowly, it becomes the new baseline. Harder to debug when it fires.

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
CPU is a capacity metric. You need to know two things: at what percentage does performance degrade? What percentage leaves you headroom for traffic spikes?

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

Based on load testing. At 75% CPU, p95 latency degrades to 350ms (1.9x normal). At 80% CPU, clear performance impact.

Don't use μ + 3σ for this:
```
μ + 3σ = 45 + (3 × 12) = 81%
```
At 81%, your service is already degraded. You need to alert earlier.

Based on actual load testing, so it's tied to real capacity limits. Downside: doesn't account for code changes that improve CPU efficiency.

**Option B: Dynamic Baseline + Headroom**

```
# Recalculate from last 7 days
baseline_p95 = rolling_p95(cpu_percent, 7d) = 65%
headroom = 15%

threshold_warning = baseline_p95 + headroom = 80%
threshold_critical = baseline_p95 + (2 × headroom) = 95%
```

Adapts when you optimize code and reduce CPU usage. Catches unusual spikes. Downside: can hide gradual CPU creep. You'll need to revalidate performance if thresholds shift.

For capacity metrics, static thresholds usually work better. They're tied to physical limits that don't change without new load tests.

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
Memory behaves differently than CPU:
- Increases gradually until OOM kills your process
- GC frequency and duration tell you when you're under pressure
- You need to catch this before OOM happens

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

Based on observed JVM behavior. At 75% heap, GC pauses increase (100-200ms). At 85% heap, constant GC thrashing (500ms+ pauses).

Tied to actual JVM behavior. Prevents OOM. Downside: doesn't adapt if you resize heap or optimize memory usage.

**Option B: Dynamic Baseline + GC Pressure**

```
# Recalculate from last 7 days
baseline_heap_p95 = rolling_p95(heap_used_percent, 7d) = 70%
threshold_warning = baseline_heap_p95 + 10% = 80%
threshold_critical = baseline_heap_p95 + 20% = 90%

# Combined with GC pressure (always monitor)
gc_pause_threshold = rolling_p99(gc_pause_seconds, 7d) × 2
```

Adapts when you optimize memory usage. Catches unusual memory growth. Downside: can hide memory leaks if baseline creeps up slowly. Risky when you're close to OOM.

For memory, static thresholds are safer. OOM is a hard limit and GC behavior is predictable at specific heap levels.

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

Don't use μ + 3σ (25 + 24 = 49%) here. Performance degrades at 60%, so alert before that happens.

---

### Layer 2: API Metrics (Per-Endpoint)

#### Example: Login Endpoint Error Rate

Login is more critical than other endpoints and has a different baseline:
```
Baseline:
- /api/login: 0.01% error rate (better than overall 0.02%)
- Traffic: 60 req/s (30% of total)
- User impact: blocks access entirely if broken
```

Set a tighter threshold than your overall API:
```yaml
alert: AuthServiceLoginErrors
condition: |
  error_rate{endpoint="/api/login"} > 0.03% AND
  requests{endpoint="/api/login"} > 3600/min
duration: 5 minutes
severity: critical
```

Why stricter? Login is business critical, has a lower baseline (0.01% vs 0.02%), and directly blocks user access when broken.

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

70% gives you early warning while you still have capacity to investigate. 90% means imminent failure - needs immediate action. At 90%, use a short duration because you can't wait 5 minutes.

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

With 95% confidence, the true error rate is between 0.48% and 2.14%.

Your baseline is 0.02%, which is way outside this range. This is statistically significant - something changed.

But notice how wide that interval is (0.48% to 2.14%). With only 600 samples, you can't pin down the exact rate. Could be a real problem or just a transient spike.

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

Same symptom (high latency) but different root causes need different actions.

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

---

## Diagnostic Tools: When Alerts Behave Unexpectedly

When your alerts don't work right, use these tools to figure out why. Don't guess.

### Tool 1: Confidence Intervals (Wilson Score)

**Problem:** Alert fires on low traffic, but is it real or noise?

**Method:** Calculate confidence interval for the observed rate.
```
If CI includes baseline → insufficient evidence, need more samples
If CI excludes baseline → statistically significant, real change
```

See Wilson Score section above for formula. Use this for error rates, conversion rates, any proportion.

### Tool 2: Correlation Analysis

**Problem:** Alert fires but you don't know the root cause.

**Method:** Check correlation between metrics.
```python
# Calculate Pearson correlation coefficient
r = correlation(latency, cpu_usage)

r > 0.7  → strong positive correlation (CPU causes latency)
r < 0.3  → weak/no correlation (look elsewhere)
```

**In practice:** Plot metrics on same time axis. If they move together, they're related. Correlation ≠ causation, but it narrows search space.

### Tool 3: Distribution Analysis

**Problem:** Mean-based threshold doesn't work.

**Method:** Plot histogram of your metric. Check shape.
```
Normal distribution → μ ± 3σ works
Right-skewed (latency) → use percentiles (p95, p99)
Bimodal (two peaks) → separate by condition (cache hit/miss)
High variance (CV > 0.5) → use percentile thresholds
```

**Coefficient of Variation (CV):** CV = σ / μ
- CV < 0.1: tight distribution, μ ± 2σ works
- CV > 0.5: high variance, use percentiles

### Tool 4: Time Series Decomposition

**Problem:** Alert fires at specific times (weekends, nights).

**Method:** Decompose metric into trend + seasonality + noise.
```
Trend: long-term increase/decrease (growth, capacity)
Seasonal: daily/weekly patterns (business hours)
Residual: random noise
```

If seasonal component is large → need time-of-week baseline, not global threshold.

### Tool 5: Statistical Significance Testing

**Problem:** Is this degradation real or random fluctuation?

**Method:** Compare two samples (before/after, control/treatment).

**For rates/proportions (error rate, conversion):**
```python
# Two-proportion z-test
z = (p1 - p2) / sqrt(p*(1-p)*(1/n1 + 1/n2))
p = (successes1 + successes2) / (n1 + n2)

If |z| > 1.96 → 95% confident difference is real
```

**For continuous metrics (latency, CPU):**
```python
# T-test (compares means)
# Mann-Whitney U test (compares distributions, non-parametric)
```

### Tool 6: Change Point Detection

**Problem:** When did the system behavior change?

**Method:** Use CUSUM (Cumulative Sum) or similar algorithms to detect shifts in mean/variance.

```
Detect: exact moment when baseline shifted
Action: investigate deployments, config changes, traffic shifts at that time
```

Available in most observability platforms as "anomaly detection" or "change detection".

### Tool 7: Sample Size Requirements

**Problem:** How much data do I need before alerting?

**Method:** Calculate minimum sample size for desired confidence.

**For error rates:**
```
Minimum n = (z² × p × (1-p)) / E²

z = 1.96 (95% confidence)
p = expected error rate
E = margin of error you can tolerate

Example: p=0.01, E=0.005 → n = 1,537 requests minimum
```

If you have fewer samples, wait longer or use wider thresholds.

### Summary: Use Math

When alerts don't work right:
1. Calculate confidence intervals → is it statistically significant?
2. Check distribution shape → is mean/stddev the right approach?
3. Analyze correlation → which metrics move together?
4. Decompose time series → is there seasonality?
5. Test significance → is the change real?
6. Check sample size → do you have enough data?

These tools help you understand what's actually happening instead of tweaking thresholds randomly.
