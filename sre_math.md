# SRE Math: Practical Threshold Setting Guide

> How to set correct thresholds for alerts using real data and statistics. Examples based on an authentication service handling 200 req/s.

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

## Example Service

**Auth Service**: HTTP REST service handling authentication and authorization
- **Normal traffic**: 200 req/s (17.3M requests/day)
- **Stack**: 6 hosts, load balanced
- **Dependencies**: PostgreSQL (user store), Redis (session cache), external SSO providers (SAML/OAuth)
- **User base**: Multi-tenant SaaS (mix of free/pro/enterprise)

**Goal**: Set thresholds that catch real problems without false positives.

---

## The Process

### Step 1: Collect Baseline Data
- Run service in production for 1-2 weeks
- Ensure this period is "healthy" (no major incidents)
- Capture all metrics at 1-minute resolution
- Export to CSV or query from metrics backend

### Step 2: Analyze Distribution
For each metric:
- Calculate mean (μ), standard deviation (σ)
- Calculate percentiles: p50, p90, p95, p99
- Check for patterns: daily cycles, weekly patterns, trends
- Identify outliers

### Step 3: Set Thresholds
Based on metric type and characteristics:
- **Stable metrics** (low variance): μ + 3σ
- **Variable metrics** (high variance): percentile-based (p95 or p99)
- **Ratios** (error rates): absolute thresholds with statistical significance
- **Capacity** (CPU, memory): based on saturation point

### Step 4: Validate
- Simulate historical incidents - would alerts fire?
- Deploy to staging with lower thresholds
- Tune based on false positive rate

---

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

#### Better Approach: Time-of-Week Baseline
Calculate mean and σ for each hour-of-week bucket:
```
Tuesday 2pm: μ = 300, σ = 25
Sunday 2pm: μ = 50, σ = 12
```

#### Threshold Formula
```
threshold(hour, day) = μ(hour, day) + 3σ(hour, day)

Tuesday 2pm: 300 + (3 × 25) = 375 req/s
Sunday 2pm: 50 + (3 × 12) = 86 req/s
```

#### Alert Rule
```yaml
# Low traffic alert (potential outage)
alert: AuthServiceTrafficDropped
condition: rate < μ(current_time) - 3σ(current_time)
duration: 5 minutes
severity: critical

# Example: Tuesday 2pm
# μ - 3σ = 300 - 75 = 225 req/s
# Alert if rate < 225 for 5+ minutes
```

**Why this works**: 
- Adapts to daily patterns
- 3σ = 99.7% confidence (0.3% false positive rate)
- 5-minute duration filters transient dips

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
Error rate is a proportion. Need to consider:
1. What error rate impacts users?
2. What sample size gives confidence?
3. What's statistically significant?

#### Threshold Setting

**Method 1: SLO-Based**
If you have a 99.95% availability SLO (stricter for auth):
```
error_budget = 1 - 0.9995 = 0.05%

threshold = error_budget = 0.05%
```

Alert when error rate > 0.05% for 5+ minutes.

**Method 2: Statistical (Baseline + Margin)**
```
threshold = p99 + margin
threshold = 0.042% + 0.008% = 0.05%
```

**Method 3: Multi-Window Burn Rate** (RECOMMENDED)
```
# Fast burn: 1-hour window
if error_rate_1h > 0.05% AND error_rate_6h > 0.03%:
    ALERT

# This means:
# - Short-term error rate 2.5x normal (0.02% → 0.05%)
# - Sustained over 6 hours
# - Reduces false positives from transient spikes
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

#### Threshold Setting: Percentile-Based

**For SLO**: "95% of requests complete in < 200ms"
```
threshold = 200ms at p95

if p95_latency_5min > 200ms:
    ALERT
```

**For degradation detection**: "p95 increases by 50%"
```
baseline_p95 = 180ms
threshold = baseline_p95 × 1.5 = 270ms

if p95_latency_5min > 270ms:
    ALERT
```

**For severe degradation**: Monitor p99
```
baseline_p99 = 450ms
threshold = 1000ms  (round number, 2.2x baseline)

if p99_latency_5min > 1000ms:
    ALERT CRITICAL
```

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

**Why percentiles**:
- Directly measure user experience
- Not skewed by outliers (p95 ignores worst 5%)
- Can aggregate across hosts using distributions

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
CPU is a capacity metric. Key questions:
1. At what % does performance degrade?
2. What % leaves headroom for load spikes?

Load testing results:
```
At 60% CPU: p95 latency = 180ms (normal)
At 75% CPU: p95 latency = 350ms (degraded)
At 85% CPU: p95 latency = 1200ms (severe)
At 95% CPU: requests timing out
```

#### Threshold Setting: Capacity-Based
```
Warning: 70% (approaching saturation)
Critical: 80% (degraded performance confirmed)
```

NOT using μ + 3σ because:
```
μ + 3σ = 45 + (3 × 12) = 81%
```

At 81%, service is already degraded. We need to alert earlier.

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

**Why these thresholds**:
- 70%: Time to investigate or scale (15min allows for human response)
- 80%: Immediate action needed (5min catches fast degradation)
- Forecast: Proactive capacity management

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

#### Threshold Setting: Multi-Signal
```
# Memory usage thresholds
Warning: heap > 75% sustained (3.0 GB)
Critical: heap > 85% sustained (3.4 GB)

# GC pressure thresholds
Warning: p99 GC pause > 100ms
Critical: p99 GC pause > 500ms
```

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

**Composite signal**: High heap + frequent GC = real pressure, not just normal usage spike.

---

### E = Errors (System-Level)

#### Baseline Data (Disk I/O errors, network errors)
```
Disk read errors: 0.002 errors/hour (rare)
Network connection resets: 1.5/minute (background noise)
```

#### Threshold Setting: Count-Based
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

**Scenario**: Weekend night, traffic drops to 10 req/s
```
5-min window: 600 requests
6 errors observed
Error rate: 6/600 = 1%
```

Normal error rate is 0.02%. Should we alert?

### Wilson Score Confidence Interval
```
p = 0.01 (observed)
n = 300 (sample size)
z = 1.96 (95% confidence)

center = (p + z²/(2n)) / (1 + z²/n)
       = (0.01 + 3.84/600) / (1 + 3.84/300)
       = 0.0164 / 1.0128
       = 0.0162

margin = z × sqrt(p(1-p)/n + z²/(4n²)) / (1 + z²/n)
       = 1.96 × sqrt(0.01×0.99/300 + 3.84/(4×90000)) / 1.0128
       = 1.96 × 0.00574 / 1.0128
       = 0.011

CI = [0.0162 - 0.011, 0.0162 + 0.011]
   = [0.5%, 2.7%]
```

**Analysis**: With 95% confidence, true error rate is somewhere between 0.5% and 2.7%.

**Baseline**: 0.02% is far outside this interval → statistically significant increase.

**BUT**: Wide confidence interval due to small n. Could be transient.

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

**Key**: At low traffic, require longer duration OR multiple windows to confirm.

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

## Practical Tips

### 1. Start Conservative
- Set thresholds wider than calculated
- Tune based on false positive rate
- Better to miss minor issues than wake up for noise

### 2. Use Multi-Window Logic
```
ALERT = (short_window breached) AND (long_window breached)

Example: 
  (error_rate_5min > 0.1%) AND (error_rate_30min > 0.05%)
```

Reduces false positives by 80-90%.

### 3. Require Minimum Sample Size
```
ALERT = (metric > threshold) AND (sample_size > minimum)

Example:
  (error_rate > 0.1%) AND (requests > 100)
```

Avoids alerting on 1 error out of 5 requests.

### 4. Seasonal Baselines
For metrics with strong patterns:
- Weekday vs weekend thresholds
- Business hours vs off-hours thresholds
- Holiday period adjustments

### 5. Test with Historical Data
Before deploying:
```
# Query last 30 days
# Apply threshold logic
# Count how many alerts would have fired
# Investigate each one:
#   - Was it a real issue? (true positive)
#   - Was it noise? (false positive)
# 
# Target: <5% false positive rate
```

### 6. Document Reasoning
For each alert, document:
```yaml
alert: AuthServiceErrorRateHigh
threshold: 0.05%
reasoning: |
  - Baseline: 0.02% (last 90 days)
  - p99: 0.042%
  - 0.05% = 2.5x baseline = clear degradation
  - At 200 req/s, 0.05% = 6 errors/min = user-impacting
  - SLO: 99.95% (0.05% budget)
last_tuned: 2024-01-15
false_positive_rate: 2% (last 30 days)
```

---

## Further Reading

- [sre.md](sre.md) - Observability patterns, dashboards, anti-patterns
- [README.md](README.md) - Journey metrics methodology with detailed math
- [Google SRE Book - Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
