# **Journey Metrics**

Model multi-step **login and authentication journeys** (login, signup, MFA/OTP, etc.) using simple request counters and ratios. Watch end-to-end conversion with control charts. This README describes one way to define **operational SLOs and conversion metrics** for those flows, using only aggregate request metrics and without relying on funnel tooling or per-user analytics.

---


## Core idea

Most tools give you **funnels** based on individual users or sessions. They are great for product analysis, and we still rely on them for that. For day-to-day SLOs, alerts, and automation they often:
- Require custom events and schema work
- Depend on user/session identity
- Are awkward to plug directly into SLOs, alerts, and automation

Instead, this method uses **aggregate metrics only**:
- Count **requests** per step per window (no user IDs)
- Derive simple ratios that behave well at high volume
- Feed them into standard SPC-style monitoring

This turns auth journeys into **operational signals** with:
- Low cardinality (few tags, no per-user IDs)
- Simple math
- Easy integration in any metrics backend (Prometheus, Datadog, etc.)


## Concepts and notation

We work with time windows (for example, 1, 5, or 15 minutes). For each window $t$:

- **Step** $i$: a state in the auth journey ("login form", "OTP page", "/authorize", etc.).
- **Arrival** $A_i(t)$: number of requests entering step $i$ in window $t$.
- **Transition ratio** $T_i(t)$: fraction of requests that move from step $i$ to step $i+1$:
  $$T_i(t) = \frac{A_{i+1}(t)}{A_i(t)}.$$
- **Terminal Success**: last step with a clear success condition (for example final HTTP 2xx). We denote its index as step $S$.
- **Conversion** $C(t)$: fraction of requests that started in step 1 and ended in Success (step $S$):
  $$C(t) = \frac{A_{S}(t)}{A_1(t)} = \prod_{i=1}^{S-1} T_i(t).$$

Notes:
- We count **requests**, not unique users; retries are part of the signal.
- Ratios $T_i(t)$ and $C(t)$ are volume-agnostic, but their **noise** shrinks with more traffic.

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

## Beyond strictly linear auth flows

The examples above use a simple linear chain of steps (1 → 2 → 3 → 4 → Success).
Real authentication systems often have optional steps, retries, and branches (for example, different MFA methods).

This **Journey Metrics** model still applies within the login/auth domain: you can define multiple flows or subflows, or group
several controllers into a single logical step. As long as you can
count arrivals $A_i(t)$ and transitions $T_i(t)$ for the auth paths you care about,
you can build dashboards for your authentication journeys on top of the same
metric-based foundation.

Because this is based on metrics and tags, flows can naturally span multiple
services and components. Different services (frontend, API gateway,
backend) can all emit metrics with the same `flow` tag; the metrics backend
puts them together into a single end-to-end auth view.

## Visualizations

The demo script uses a simple scenario with:
- $A_1 = 1000$
- Normal case: $T_1 = T_2 = T_3 = 0.9$, $T_4 = 1.0$
- "Bad" case: only $T_2$ drops to 0.2

From this you get:
- Normal flow: $C_\text{normal} = 0.9^3 = 0.729$
- Bad $T_2$ flow: $C_\text{bad} = 0.9 · 0.2 · 0.9 = 0.162$

Below is what each plot is meant to show.

### 1. Arrivals per step – normal

![Arrivals per step – normal](images/plot1.png)
- View of $A_1, A_2, A_3, A_4, A_5$ for the normal case.

### 2. Arrivals per step – bad $T_2$

![Arrivals per step – bad $T_2$](images/plot2.png)
- Same view, but only $T_2$ is degraded to $0.2$.

### 3. Arrivals per step – normal vs bad (combined)

![Arrivals per step – normal vs bad](images/plot3.png)
- Bars for normal vs bad flow side by side for each step.

### 4. Transition ratios – normal vs bad

![Transition ratios – normal vs bad](images/plot4.png)
- Bars for $T_1, T_2, T_3, T_4$ in both scenarios.

### 5. End-to-end conversion – two windows

![End-to-end conversion – two windows](images/plot5.png)
- Two bars: $C_\text{normal}$ vs $C_\text{bad}$.

### 6. Time series of $C(t)$

![Time series of C(t) – SPC-style](images/plot6.png)
- $C(t)$ over time; first half uses healthy $T_2$, second half degraded $T_2$.

### 7. $C(t)$ with control limits

![C(t) with control limits](images/plot7.png)
- Same $C(t)$ points with mean and control limits overlaid.

### 8. Effect of adding more steps

![Effect of adding more steps](images/plot9.png)
- Plots $C(n) = 0.9^n$ for flows with 1–20 identical steps.

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

**Google SRE journey-based SLIs**: Google's [SRE Workbook](https://sre.google/workbook/implementing-slos/#modeling-user-journeys) describes modeling user journeys for SLOs, but provides limited implementation details. Here is one way to apply that idea:
- Explicit mathematical formulas 
- Statistical Process Control adaptation for time-windowed metrics
- Practical guidance on when the approach works and when it doesn't

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

The pieces already exist:
- Journey-based SLIs from the SRE world
- SPC and control charts from manufacturing and quality work
- Metrics backends like Prometheus, Datadog, and OpenTelemetry

What this README is trying to do is tie those ideas together into one small, practical pattern for flow SLIs you can alert on. The intent is to offer a proposal that teams can adapt to their own systems and tweak to fit their context.

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