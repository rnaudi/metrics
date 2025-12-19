# **Journey Metrics**

Model multi-step **login and authentication journeys** (login, signup, MFA/OTP, etc.) using simple request counters and ratios. Watch end-to-end conversion with control charts. This README describes one way to define **operational SLOs and conversion metrics** for those flows, using only aggregate request metrics and without relying on funnel tooling or per-user analytics.

---


## Core idea

Many tools give you **funnels** based on individual users or sessions. They're excellent for product analysis, and we rely on them for that. For day-to-day SLOs, alerts, and automation, we've found some challenges:
- Often require custom events and schema work
- Depend on user/session identity
- Can be tricky to plug directly into SLOs, alerts, and automation

This approach explores using **aggregate metrics only**:
- Count **requests** per step per window (no user IDs)
- Derive simple ratios that behave well at high volume
- Feed them into standard SPC-style monitoring

This aims to turn auth journeys into **operational signals** with:
- Low cardinality (few tags, no per-user IDs)
- Relatively simple math
- Straightforward integration in most metrics backends (Prometheus, Datadog, etc.)


## Concepts and notation

We work with time windows (for example, 1, 5, or 15 minutes). For each window $t$:

- **Step** $i$: a state in the auth journey ("login form", "OTP page", "/authorize", etc.).
- **Arrival** $A_i(t)$: number of requests entering step $i$ in window $t$.
- **Transition ratio** $T_i(t)$: fraction of requests that move from step $i$ to step $i+1$:
  $$T_i(t) = \frac{A_{i+1}(t)}{A_i(t)}.$$
- **Terminal Success**: last step with a clear success condition (for example final HTTP 2xx). We denote its index as step $S$.
- **Conversion** $C(t)$: ratio of requests in window $t$ that reached Success (step $S$) to requests that entered step 1 in the same window:
  $$C(t) = \frac{A_{S}(t)}{A_1(t)} = \prod_{i=1}^{S-1} T_i(t).$$

Notes:
- We count **requests**, not unique users; retries are part of the signal.
- Ratios $T_i(t)$ and $C(t)$ are volume-agnostic, but their **noise** shrinks with more traffic.
- This is a request-level signal (including retries), not a per-user funnel metric.

**Assumptions (briefly)**
- Flows are sequential along the path you are modeling (for example controller chain `/login -> /otp -> /success`).
- Typical latency between steps is small compared to the chosen window, or at least well bounded. Long-running steps (for example, email verification over hours) either need larger windows and acceptance of lagged signals, or a different tool (funnels, events).
- Each window has enough traffic that individual requests do not dominate $T_i(t)$ and $C(t)$.

---

## Example: 4-step auth flow

Example flow:

> Step 1 → Step 2 → Step 3 → Step 4 → Success

For a window $t$:
- $A_i(t)$: arrivals into step $i$, for $i ∈ \{1,2,3,4,5\}$, where step 5 is the terminal success step.
- $T_i(t) = A_{i+1}(t)/A_i(t)$ for $i ∈ \{1,2,3,4\}$.
- End-to-end conversion:
  - $C(t) = A_5(t)/A_1(t)$
  - $= \bigl(A_2(t)/A_1(t)\bigr)\cdot\bigl(A_3(t)/A_2(t)\bigr)\cdot\bigl(A_4(t)/A_3(t)\bigr)\cdot\bigl(A_5(t)/A_4(t)\bigr)$
  - $= T_1(t)\cdot T_2(t)\cdot T_3(t)\cdot T_4(t)$

Interpretation:
- Any drop in any $T_i(t)$ shows up as a drop in $C(t)$.
- $C(t)$ is a single SLO-style number that captures the whole journey.
- You still keep normal per-endpoint SLIs (success rate, latency); $C(t)$ sits on top as the flow SLI.

See [src/metrics_demo.py](src/metrics_demo.py) for code that generates the example plots.

---

## Visualizations

The following visualizations tell a story about how this approach behaves under different conditions. We'll start with basic concepts, then explore how **volume**, **jitter**, and **failures** affect what you see.

All simulations use a 4-step auth flow with these baseline transitions:
- $T_1 = T_2 = T_3 = 0.9$ (90% success per step)
- $T_4 = 1.0$ (final step always succeeds if reached)
- Baseline conversion: $C = 0.9^3 = 0.729$ (~73%)

We'll compare this to a "degraded" scenario where only $T_2$ drops to $0.8$:
- Degraded conversion: $C_\text{degraded} = 0.9 \times 0.8 \times 0.9 = 0.648$ (~65%)

### Part 1: Basic concepts—what are we measuring?

These first plots show the fundamental building blocks: arrivals, transitions, and conversion.

#### 1.1 Arrivals per step – healthy flow

![Arrivals per step – normal](images/plot1.png)

Starting with 1,000 requests at Step 1, we watch how many make it to each subsequent step. With 90% success per step, we see a gradual decline: Step 1 → 1,000, Step 2 → 900, Step 3 → 810, Step 4 → 729, Final → 729.

#### 1.2 Arrivals per step – broken step

![Arrivals per step – bad $T_2$](images/plot2.png)

Same starting volume, but when $T_2$ drops to 20%, Step 3 onward sees dramatically fewer requests. The drop at Step 2 creates a "cliff" that persists through the rest of the flow.

#### 1.3 Side-by-side comparison

![Arrivals per step – normal vs bad](images/plot3.png)

Comparing both scenarios makes the broken step obvious. This is what you'd investigate when $C(t)$ drops: which $A_i(t)$ shows the biggest change?

#### 1.4 Transition ratios

![Transition ratios – normal vs bad](images/plot4.png)

The per-step view: all transitions look healthy except $T_2$. This pinpoints exactly where the flow broke.

#### 1.5 End-to-end conversion

![End-to-end conversion – two windows](images/plot5.png)

The single number you'd track as your flow SLI: 73% healthy → 16% broken. This is what triggers your alert.

---

### Part 2: Volume matters—sampling noise vs. signal

Now we simulate $C(t)$ over time with control charts. The key question: **how does traffic volume affect our ability to detect problems?**

We use the same healthy flow ($T_i = 0.9$), but vary the number of requests per window. Control limits (dashed lines) are computed from the data using Statistical Process Control methods.

#### 2.1 Low volume: 100 requests/window

![C(t) with control limits – base, 100 requests](images/plot6.png)

With only 100 requests entering the flow per window, you can see noticeable bounce even though nothing actually changed. This is pure **sampling noise**—like flipping 100 coins vs. 10,000 coins. The control limits are fairly wide to account for this natural variation.

#### 2.2 Medium volume: 10k requests/window

![C(t) with control limits – base, 10k requests](images/plot7.png)

At 10,000 requests per window, $C(t)$ becomes much smoother. The control limits tighten significantly. This is a comfortable operating range for most production auth flows—enough volume to be confident in the signal.

#### 2.3 High volume: 1M requests/window

![C(t) with control limits – base, 1M requests](images/plot14.png)

At 1 million requests per window, $C(t)$ is nearly a flat line. Sampling noise is negligible. Even tiny degradations would be immediately obvious. This is what high-scale systems experience—problems become very easy to detect.

**Takeaway**: More traffic = tighter signal. At low volume you need wider thresholds and longer observation periods before alerting.

---

### Part 3: Real-world variability—when success rates actually fluctuate

Production systems aren't perfectly stable. Step success rates genuinely vary window-to-window due to:
- Minor performance fluctuations
- Different user cohorts
- Time-of-day effects  
- Network conditions
- Load variations

This isn't measurement noise—it's **real variation in the process itself**. We model this as **jitter**: each $T_i$ varies randomly within $\pm 0.05$ (±5 percentage points) around its nominal value per window.

To demonstrate this, we use a healthier baseline flow ($T_i = 0.95$, giving mean $C \approx 86\%$) with realistic jitter added. The key question: **does higher volume make this variation disappear?**

#### 3.1 Timing noise in a single transition

![Measured T1(t) in 1-minute windows (timing noise)](images/plot8.png)

Before looking at full flows, let's see what happens to a single transition $T_1(t)$ measured in 1-minute windows. Three volume levels (20, 200, 2000 users/min) all have the same true success rate (90%, dotted line), but low volume shows dramatic window-to-window swings. This is mostly **timing noise**—requests arriving near window boundaries get counted in one window or the next somewhat randomly.

#### 3.2 Low volume with jitter

![C(t) with control limits – base, 100 requests, jitter 0.05](images/plot9.png)

With 100 requests per window and real operational jitter (±5% on each step), $C(t)$ varies significantly. The mean stays around 83% as expected, but individual windows range widely. Control limits must be wide to accommodate this genuine variation.

#### 3.3 High volume with jitter—same problem persists

![C(t) with control limits – base, 1M requests, jitter 0.05](images/plot10.png)

Same flow, same jitter (±5% per step), but with 1M requests per window. The mean is still ~83%, and notice: **the control limits barely tighten**. The variation is still there because it's REAL—each window genuinely has different success rates.

**Critical insight**: Higher volume reduces **sampling noise**, but it does NOT eliminate **real process variation**. If your success rates genuinely fluctuate ±5% window-to-window (due to load, time-of-day, etc.), that variation persists at any traffic level. Jitter is signal, not noise.

#### 3.4 What can you do about jitter?

If your production metrics look like this—wide control limits even at high volume—you have real operational variability. Options:

**Option 1: Increase window size**
- Use 15 or 30-minute windows instead of 5-minute windows
- Averages out short-term fluctuations
- Trade-off: slower detection of real problems

**Option 2: Use moving averages** ⭐
- Track rolling average of $C(t)$ over last N windows
- Compute control limits from the smoothed series, not raw values
- Smooths the signal, easier to spot trends
- Trade-off: adds lag to detection

Let's see this in action:

#### 3.5 Moving average control limits—the solution

![C(t) with moving average control limits](images/plot15.png)

Here's the same high-volume jittered scenario (1M requests, ±5% jitter), but now we:
1. Compute a 5-window moving average of $C(t)$ (blue line)
2. Calculate control limits from the smoothed series, not the raw values (gray dots)

**Result**: The control limits are now MUCH tighter! The moving average filters out the jitter, revealing the true underlying trend. If a real degradation occurs, it will stand out clearly against these tighter limits.

**How to implement**:
```python
# Compute 5-window moving average
ma_C = rolling_mean(C_series, window=5)

# Use MA for control limits, alert when MA crosses threshold
if ma_C < lower_limit:
    alert("Flow degraded")
```

**Trade-off**: A 5-window MA adds ~2-3 windows of lag to detection (if windows are 5 minutes, that's ~10-15 min delay). But you get much cleaner signals and fewer false positives.

**Option 3: Accept wider limits**
- Set alert thresholds well below the jitter band
- Only alert on clear, sustained degradation (e.g., "5 consecutive windows below 75%")
- Requires distinguishing "normal jitter" from "real failure"

**Option 4: Reduce the jitter itself**
- Investigate and fix the root causes of variability
- Load balancing, caching, performance optimization
- This is often the best long-term solution

**Takeaway**: Jitter is real variation in your system's behavior. Volume alone won't fix it—you need to either smooth the signal (bigger windows, moving averages) or fix the underlying variability.

---

### Part 4: Detecting real failures

Finally, let's see what happens when something actually degrades. At window 40, we inject a failure: $T_2$ drops from 0.9 to 0.8 (step 2 success drops by 10 percentage points). The shaded region shows the post-failure windows.

#### 4.1 Failure detection at low volume

![C(t) with control limits – failure in T2, 100 requests](images/plot11.png)

With 100 requests per window, the degradation is detectable but noisy. $C(t)$ drops from ~73% to ~65%, and most post-failure windows sit below the baseline, but there's enough natural variation that a few windows might not trigger a threshold-based alert. You'd want to require multiple consecutive bad windows before paging.

#### 4.2 Failure detection at high volume

![C(t) with control limits – failure in T2, 1M requests](images/plot12.png)

With 1M requests per window, even this relatively small degradation (10 percentage points) is immediately obvious. $C(t)$ drops cleanly below the control limits and stays there. Every single post-failure window would trigger an alert. Detection is instant and unambiguous.

**Takeaway**: Real failures are detectable at any volume, but high volume gives you faster, cleaner detection with fewer false positives.

---

### Part 5: Window sizing—does your data make sense?

One common mistake is choosing windows that are too small relative to step timing. Here's how to tell if your window size is wrong:

#### 5.1 Good vs. bad window choices

![Per-step request volume in a single window](images/plot13.png)

- **Good window (blue)**: Each step sees roughly similar request volume. This suggests most user journeys fit within a single window.
- **Bad window (gray)**: Wildly different volumes per step, with some steps seeing 1000× more traffic than others. This usually means your window is too small and user journeys are getting split across multiple windows.

If your production metrics look like the "bad" example, your transition ratios $T_i(t)$ won't make sense because you're comparing requests from different user cohorts.

**Fix**: Increase window size until step volumes become roughly consistent (within 2-3× of each other for sequential flows).

---

## Advanced notes (optional)

These notes help when you roll this out in production.

**Volume and variance**
- Ratios are mathematically volume-agnostic, but variance shrinks with more traffic.
- With very low arrivals per window, $T_i(t)$ and $C(t)$ are noisy; use larger windows or a different tool (funnels, events).

**Time-window selection**
- At low volume: prefer 5–15 minute windows and require multiple bad windows before paging.
- If you know typical step latency, choose window size $W$ roughly $5–10×$ the p95 between steps.
- That way most users finish a step within one window, so $A_i(t)$ and $A_{i+1}(t)$ stay aligned and timing noise is smaller.
- If you ever applied this pattern to flows with very long or highly variable gaps between steps (for example email verification that may take hours, human review, or async jobs), this method would become a coarse, laggy signal for conversion, and you would need a different, event-based approach for precise per-journey analysis.

**Control charts**
- Individuals chart: simple, works when volume per window is roughly stable.
- P‑chart: better when traffic swings a lot; limits widen at low volume and tighten at high.
- You can keep limits static from a known-good period and update them occasionally as the system evolves.
 - If you prefer, you can instead use simple alert rules (for example static SLO-style thresholds on $C(t)$) or built-in anomaly detection / forecasting in your metrics backend, still using the same $T_i(t)$ and $C(t)$ as inputs.

**Non-linear flows**
- In practice each major branch is its own mostly sequential flow (for example `flow=login_password`, `flow=login_sso`, `flow=login_webauthn`).
- For loops and retries, you can usually treat retries as extra noise in $A_i(t)$ and $T_i(t)$; with enough traffic they average out and a retry storm will naturally show up as a drop in $C(t)$. Split out first attempts vs retries only if you need to distinguish "hard failures" from "eventual success after many retries".

**SLIs, SLOs, and cost**
- Typical stack: per-endpoint availability + latency **and** flow conversion $C(t)$.
- A practical flow SLI is the volume-weighted mean conversion over a period $P$: $\text{SLI}_\text{flow}(P) = \frac{\sum_t A_1(t)\,C(t)}{\sum_t A_1(t)}$, which approximates the fraction of attempts that eventually succeed under the assumptions above.
- Per-step SLOs locate the broken component; End to end conversion flow SLOs say whether the journey works.
- A small, controlled `flow` tag adds predictable metric cardinality and is usually cheap in managed backends.


**Traffic mix, bots, and abuse**

- In real systems, not all arrivals are equal: some traffic comes from real users,
some from automated clients, some from abusive sources. All of it contributes to
$A_i(t)$, $T_i(t)$, and $C(t)$.
- If the mix is **stable**, its effect is baked into your baseline and limits.
- When abuse/bot traffic surges, you often see $A_1(t)$ spike and transitions drop.

## Existing approaches and alternatives

### Conceptual foundation

**Google SRE journey-based SLIs**: Google's [SRE Workbook](https://sre.google/workbook/implementing-slos/#modeling-user-journeys) describes modeling user journeys for SLOs, but provides limited implementation details. This is our attempt at one way to apply that idea:
- Explicit mathematical formulas 
- Statistical Process Control adaptation for time-windowed metrics
- Practical guidance on when the approach might work and when it might not

**Statistical Process Control (SPC)**: Control charts for quality monitoring come from manufacturing. We use these ideas for:
- Time-windowed request flows 
- Proportions bounded in [0,1] 
- Systems with variable traffic volume

### Comparison with existing tools

| Approach                         | How it works                                                | What it is best at                              | Main tradeoffs                              |
|----------------------------------|-------------------------------------------------------------|-------------------------------------------------|---------------------------------------------|
| Real User Monitoring / Funnels   | Client events per user/session, queried as funnels         | Product analytics, paths, cohorts, UX questions | Needs identity, higher cost, awkward for SLOs |
| Synthetic monitoring             | Bots run scripted journeys                                  | Smoke tests, external checks, third parties     | Fake traffic, limited scenarios, no load info |
| APM / distributed tracing        | Per-request traces across services                          | Deep debugging of specific failures             | High cardinality, sampling, complex queries  |
| High-cardinality observability   | Stores rich, high-cardinality events and fields            | Ad-hoc "show me all requests where…" queries   | Cost grows with cardinality and usage        |
| This **Journey Metrics** model       | Aggregate request counters per step and time window        | Cheap, simple flow SLIs and SLOs               | Less flexible for arbitrary ad-hoc questions |

#### Real User Monitoring (RUM) / Funnels
**Tools**: Grafana Faro, Datadog RUM, Google Analytics, Amplitude, Mixpanel

- **How they work**: Track individual user sessions with client-side instrumentation. Build funnels by querying event streams per user.
- **Strengths**: Rich path analysis, segmentation, "what happened to user X?"
- **Weaknesses**: Expensive at scale (per-user events), requires user identity, hard to use directly in SLOs.
- **When to use**: Product analytics, A/B testing with deep segmentation.
- **This Journey Metrics model**: Can be cheaper (aggregate counters), needs no user tracking, and is aimed at operational SLOs and alerts. It is not a replacement for product analytics funnels.

#### Synthetic Monitoring
**Tools**: Datadog Synthetics, Pingdom, Checkly

- **How they work**: Bots run scripted user journeys; alert if they fail.
- **Strengths**: Proactive (catches issues before users), consistent baseline.
- **Weaknesses**: Fake traffic (not real users), limited coverage, can't detect load-dependent issues.
- **When to use**: Smoke tests, monitoring from multiple regions, testing third-party dependencies.
- **This Journey Metrics model**: Monitors real user traffic flows and can complement synthetic checks, especially for load-dependent issues.

#### APM / Distributed Tracing
**Tools**: Datadog APM, Honeycomb, Lightstep, Jaeger

- **How they work**: Trace individual requests across services; reconstruct full journey per request.
- **Strengths**: Deep per-request visibility, great for debugging specific failures.
- **Weaknesses**: Expensive (high cardinality), requires sampling at scale, complex queries for aggregate patterns.
- **When to use**: Incident investigation ("why did this specific request fail?").
- **This Journey Metrics model**: Uses aggregate metrics that can be cheaper at scale and are intended for SLOs and alerting alongside tracing.

#### High-cardinality observability
**Tools**: Honeycomb, Lightstep, Elastic Observability

- **How they work**: Store high-cardinality events; slice by arbitrary dimensions.
- **Strengths**: Extreme flexibility ("show me all requests where..." queries).
- **Weaknesses**: Cost scales with cardinality and query complexity; need to know what to ask.
- **When to use**: Exploratory analysis, ad-hoc investigation of unknown unknowns.
- **This Journey Metrics model**: Uses fixed, low-cardinality metrics ($\approx$10-20 flow values) that are often cheaper, but support only pre-defined questions. It is best suited to regular flow health checks, not open-ended exploration.

### Closest existing implementation

**Google's internal SRE tools**: Public material describes Google using journey-based SLIs and flow-style metrics internally. This approach is inspired by that style (flow-based SLIs with SPC), but their tools are proprietary and not documented.

### Are we reinventing the wheel?

Not really—the pieces already exist:
- Journey-based SLIs from the SRE world
- SPC and control charts from manufacturing and quality work
- Metrics backends like Prometheus, Datadog, and OpenTelemetry

What we're hoping to do is share one way we've tied those ideas together. We'd love feedback on whether this resonates with your experience, and we expect teams will want to adapt and tweak this to fit their specific context.

## Refresh visualizations

Requires [uv](https://docs.astral.sh/uv/):

```sh
uv --version
```

Activate the virtual environment:

```sh
source ./.venv/bin/activate
```

Generate the example plots used in this README:

```sh
python ./src/metrics_demo.py
```