# metrics

## Getting started

Requires [uv](https://docs.astral.sh/uv/):
```sh
uv --version
```

Activate the virtual environment:
```sh
source ./.venv/bin/activate
```

`metrics_demo.py` generates the images used in this README:
```sh
python ./src/metrics_demo.py
```

## Motivation
The goal is to show a simple way to [model user journeys](https://sre.google/workbook/implementing-slos/#modeling-user-journeys).
You can apply this to any multi-step flow by defining steps and transitions on top of metrics.

Most tools already give you some sort of "funnels" that follow a user or session through a flow.
[Funnels](https://en.wikipedia.org/wiki/Conversion_funnel) are great for one-off analysis by segment (country, device, age, etc.), but
they usually need a lot of custom work:

- You must define events, pages, and flows by hand.
- You need to maintain segments and filters inside the UI.
- You often cannot reuse funnel numbers directly in SLOs, alerts, or code.

This approach takes a different angle: reuse metrics you already have.
Instead of tracking individual users, we track flows: arrivals and transitions between steps in your services.

What you get from this model:

- **Simple**: just counters and ratios.
- **Generic**: works for any multi-step flow (auth, checkout, onboarding, etc.).
- **Automatic**: no extra events or per-funnel setup; you only tag existing metrics.
- **Predictable**: once the system is stable, you can set control limits and spot real changes.

You can also use the same model for different journeys in one place:

- Login
- Signup
- Payment
- Cart / checkout

Each journey becomes "just another flow" with its own steps and transitions,
but the math and the dashboard are the same. You can run experiments on any
step (copy changes, extra checks, new screens) and see the impact on each
flow without adding new events or building a new funnel every time.

### Metrics vs Funnel comparison

- In many tools, funnels are mainly UI objects: you see step conversions in a dashboard, but it can be awkward to plug them directly into SLOs or alerts.
- Funnels often need extra events: each step becomes a separate event, which adds instrumentation and schema work.
- Funnels depend on user identity: session/user ids can be fragile in OAuth flows (redirects, retries, cross-domain hops).
- Funnels usually hide the math: you cannot easily write down and reuse the exact formulas behind the numbers.
- Funnels track unique users and analyse segments; this model tracks flows in time windows, which are often easier to reason about and automate.
- Metric-based models reuse existing metrics, so the same data powers dashboards, SLOs, alerts, and ad-hoc analysis.

This does **not** mean funnels are bad. They answer different questions:

- Funnels are great for path-level and cohort analysis: "what do users from country X do after step 3?".
- This metric-based model is great for operational SLOs and alerting: "is the login flow working end-to-end right now?".

In practice, you can run both side by side: use this flow model for real-time reliability signals and error budget policies, and use funnels for deeper product and segment analysis.

### Cost and cardinality

This model reuses metrics you already have, but you may need a small extra tag
to identify flows (for example: `flow=login-web` vs `flow=login-device`).
That tag increases metric cardinality, which can affect cost and query
performance in any metrics backend (Datadog, Prometheus, cloud-native systems).

This is not unique to this model: funnels and event-based analytics also need
identifiers for flows, steps, and segments. The practical tradeoff is usually:

- **Metric-based model**: add a small number of stable flow tags to existing
  counters. Cheaper when you already export infra metrics and want to reuse
  them for SLOs, alerts, and dashboards.
- **Funnels / events**: send richer, per-user event streams with many
  properties. More flexible for analysis, typically higher volume and cost.

In practice you can keep cost under control by:

- Limiting flow-related tags to the minimum needed for operational decisions
  (for example: flow name, region).
- Avoiding per-user or per-session tags in the metrics backend.

## Metric definition

Very small glossary:

- **Step** ($i$): a state in the journey (for example: "login web site", "login from a device", "one time token page", "user-password validation").
- **Transition** ($T_i$): fraction of users that move from step $i$ to step $i+1$.
- **Arrival** ($A_i$): number of users that enter a step in a given time window.
- **Success transition** ($T_L$): fraction of arrivals at the last step that end in a terminal "Success" outcome (for example, HTTP 2xx on the final endpoint).
- **Conversion** ($C$): fraction of users that started in step 1 and ended in Success.

### Why this is "volume-agnostic"

The definitions in this model are volume-agnostic: $T_i$ and $C$ are ratios, so
they do not change just because you have 1k users or 1M users. The math is based
on proportions ($T_i$, $C$), not on absolute counts.

However, the signal-to-noise ratio depends on volume: with more traffic, the ratios
become more stable and you can detect smaller changes. In practice, use larger time
windows (5–15 minutes) at low volume and shorter windows at high volume.

(See Appendix A for detailed statistical treatment.)

### Time windows, funnels, and noise

Funnels follow individual users across time, so each user is counted once in each step,
no matter how long they take between steps.

In this model we do not track users; we only count arrivals per time window. This means
$T_i(t) = A_{i+1}(t)/A_i(t)$ can be noisy if users take longer than one window to move
between steps. At high volume or with reasonably-sized windows (5-15 minutes), this
noise averages out and you get clean signals.

In practice:
- Use larger windows (5–15 minutes) to reduce noise.
- Require multiple bad windows before alerting.
- Focus on structural changes, not single-window spikes.

(See Appendix B for detailed timing analysis and window selection.)

#### Time-window noise vs funnels

![T1 in 1-minute windows: low vs high volume](images/plot8.png)

What it shows:
- A 2-step flow (Step 1 → Step 2) where each user has a fixed true success probability.
- We measure $T_1(t) = A_2(t)/A_1(t)$ in 1-minute windows for three cases:
  2 users/min, 200 users/min, and 2000 users/min.

Interpretation:
- At 2 users/min, per-window $T_1(t)$ jumps around a lot because users cross
  window boundaries; arrivals into step 2 are spread over time.
- At 200 users/min, the same randomness is already much smoother.
- At 2000 users/min, the measured $T_1(t)$ hugs the true underlying probability.

This is the practical difference between funnels (tracking each user) and this
flow-based model (tracking windows). Timing noise matters a lot at low volume
and tiny windows, but becomes mostly harmless once you have enough users or slightly
larger windows. The SPC $C(t)$ view lets you ignore this noise and focus on
real, structural changes in the flow.

In many real systems, metrics are available in near real time (within seconds
or a couple of minutes) from the source. Aggregating into 5–15 minute windows
is usually enough for this model: it keeps operational latency low while
reducing timing noise and making control limits more stable.


### SPC and control limits

Once you have $C(t)$ over time, you can treat it like a control chart:

- Estimate the "normal" range of $C(t)$ when the system is stable.
- Define upper and lower control limits around that range.
- Alert only when $C(t)$ breaks those limits for a while (not on every small wiggle).

I recommend [Statistical Process Control: A Practitioner’s Guide](https://entropicthoughts.com/statistical-process-control-a-practitioners-guide) as a basic introduction.

(See Appendix C for advanced control chart methods including p-chart formulation for varying traffic volumes.)

How this looks in real flows:

- **Login**
  - Metric: $C_{\text{login}}(t)$ = fraction of login attempts that end in a valid session.
  - Control limits: learn the usual range of $C_{\text{login}}(t)$ during normal operation.
  - Detects: auth outages (IdP down), bad CAPTCHA changes, cookie/session bugs that prevent users from staying logged in.

- **Signup**
  - Metric: $C_{\text{signup}}(t)$ = fraction of signup starts that end in an activated account.
  - Control limits: learn the normal band for your best-performing signup flow.
  - Detects: broken email verification, bad copy or UX experiments around consent/terms, higher friction when adding extra steps.

- **Payment**
  - Metric: $C_{\text{payment}}(t)$ = fraction of payment attempts that end in a successful charge.
  - Control limits: use a stable period (no experiments, normal provider behavior) to set the band.
  - Detects: PSP or bank issues, 3DS/strong-auth failures, currency/price bugs that block transactions.

- **Cart / checkout**
  - Metric: $C_{\text{checkout}}(t)$ = fraction of carts that end in a completed order.
  - Control limits: learn the usual conversion for your store (per region or product type, if needed).
  - Detects: broken shipping/tax calculation, bad discounts or promos, layout changes that accidentally hide key buttons.


## Metric definitions example (4-step flow)

Let the auth flow be 4 numbered steps plus a terminal Success outcome:

> Step 1 → Step 2 → Step 3 → Step 4 → Step 5 (Success)

For a given time window $t$:

- Arrival counts: $A_i(t)$ = number of users entering step $i$, $i \in \{1,2,3,4,5\}$.
- Success arrivals: $A_5(t)$ = number of users who completed the flow with a terminal Success outcome at step 4 (for example, HTTP 2xx on the last endpoint).
- Transition ratios between steps: $T_i(t) = \dfrac{A_{i+1}(t)}{A_i(t)}$, $i \in \{1,2,3,4\}$.
  - For $i \in \{1,2,3\}$, $T_i(t)$ is a normal "continue to next step" ratio.
  - For $i = 4$, $T_4(t)$ is the terminal success ratio (Success at step 4).

Notes:
- If a user drops between steps 3 and 4, that shows up in $T_3(t)$ regardless
  of whether step-3 HTTP codes are 200 or 500. The loss is in the transition.
- For conversion, we only care about the terminal "Success" condition on the last
  step (4), typically an HTTP 2xx. Once a user is in $A_5(t)$, it is a terminal
  state; there is no further transition.
- In parallel, you should still track per-step error rates and latency (for example,
  HTTP 5xx at step 2) as separate SLOs or SLIs. The transitions $T_i(t)$ complement
  these metrics; they do not replace them.
- Retries and repeated attempts show up as extra arrivals $A_i(t)$. At healthy
  volumes this mostly becomes additional noise that averages out over time. When
  retries spike because something is broken, that change in $A_i(t)$ and $T_i(t)$ is
  exactly what we want to surface.

End-to-end conversion for the flow is:

$$
\begin{aligned}
C(t)
  &= \frac{A_5(t)}{A_1(t)} \\
  &= \frac{A_2(t)}{A_1(t)} \cdot \frac{A_3(t)}{A_2(t)} \cdot \frac{A_4(t)}{A_3(t)} \cdot \frac{A_5(t)}{A_4(t)} \\
  &= T_1(t) \cdot T_2(t) \cdot T_3(t) \cdot T_4(t)
\end{aligned}
$$

This $C(t)$ is a single SLO-style number that is sensitive to
any drop in any transition, including the final success transition $T_4(t)$.

The code for the plots lives in [src/metrics_demo.py](src/metrics_demo.py).

### Beyond strictly linear flows

The examples above use a simple linear chain of steps (1 → 2 → 3 → 4 → Success)
because it is easy to see the math. In real systems, flows often have optional
steps, retries, and branches (for example, different payment providers).

This model still applies: you can define multiple flows or subflows, or group
several underlying endpoints into a single logical step. As long as you can
count arrivals $A_i(t)$ and transitions $T_i(t)$ for the paths you care about,
you can build dashboards for arbitrary user journeys on top of the same
metric-based foundation.

Because this is based on metrics and tags, flows can naturally span multiple
services and components. Different services (frontend, API gateway, IdP,
backend) can all emit metrics with the same `flow` tag; your metrics backend
then stitches them together into a single end-to-end view.

(See Appendix D for handling non-linear flows with branches and loops.)

## Visualizations

All examples use a simple deterministic scenario with:

- $A_1 = 1000$.
- Normal case: $T_1 = T_2 = T_3 = 0.9$, $T_4 = 1.0$.
- A/B test case: $T_2$ drops from $0.9$ to $0.2$ (users back off on step 2 → 3).

From this you get:

- Normal **flow**: $A_2 = 900$, $A_3 = 810$, $A_4 = 729$, $A_5 = 729$, $C_1 = 0.9^3 = 0.729$.
- With T2 drop: $A_3 = 180$, $A_4 = 162$, $A_5 = 162$, $C_2 = 0.9 \cdot 0.2 \cdot 0.9 = 0.162$.

So a local change in $T_2$ from $0.9$ to $0.2$ cuts end-to-end
conversion from $72.9\%$ to $16.2\%$ (about a 4.5x drop).

### 1. Arrivals per step: normal flow

![Arrivals per Step - Normal](images/plot1.png)

What it shows:
- Single flow with the normal parameters: $T_1 = T_2 = T_3 = 0.9$, $T_4 = 1.0$.
- You see a smooth, expected decline in users across the steps.

You can use this to explain the baseline: "this is what healthy looks like".

### 2. Arrivals per step: T2 drop flow

![Arrivals per Step - T2 drop](images/plot2.png)

What it shows:
- Single flow where only $T_2$ is changed to $0.2$.
- Steps 1 and 2 match the normal flow, but from Step 3 onward the counts collapse.

You can use this to anchor: "same start of the flow, but a bad step 2→3 change".

### 3. Arrivals per step: normal vs T2 drop (combined)

![Arrivals per Step - Combined](images/plot3.png)

What it shows:
- X-axis: the steps (1, 2, 3, 4, Success).
- Two bar sets: Normal vs Drop T2, overlaid for direct comparison.

Interpretation:
- Up to step 2 the bars are identical: $T_1$ is the same in both scenarios.
- From step 3 onward, the "Drop T2" bars are much smaller because $T_2$ fell
  from $0.9$ to $0.2$.
- This makes it visually obvious *where* users are disappearing in the flow.

### 4. Transition ratios: normal vs T2 drop (grouped bars)

![Transition Ratios](images/plot4.png)

What it shows:
- X-axis: $T_1, T_2, T_3, T_4$.
- For each metric you see **two side-by-side bars**: Normal vs Drop-T2.

Interpretation:
- $T_1$ and $T_3$ stay at $0.9$ in both scenarios.
- $T_4$ stays at $1.0$ (the last step always succeeds if reached).
- Only $T_2$ moves, from $0.9$ to $0.2$.

Because the bars are grouped (not overlaid), you can see that all
other transitions are stable; the only structural change is at step 2→3.

### 5. End-to-end conversion C (two windows)

![End-to-End Conversion](images/plot5.png)

What it shows:
- Two bars: $C_1$ (Normal) vs $C_2$ (Drop T2).
- You can read this as two time windows: before and after the A/B change.

Math behind it:

$$
\begin{aligned}
C_1 &= T_1 \cdot T_2 \cdot T_3 \cdot T_4 \\[-2pt]
  &= 0.9 \cdot 0.9 \cdot 0.9 \cdot 1.0 = 0.729 \\
C_2 &= T_1 \cdot T_2' \cdot T_3 \cdot T_4 \\
  &= 0.9 \cdot 0.2 \cdot 0.9 \cdot 1.0 = 0.162
\end{aligned}
$$

Why this is a good SLO:
- It compresses the whole flow into one number $C(t) = A_5(t) / A_1(t)$.
- Any change in any transition $T_i$ (including $T_4$) shows up as a change in $C(t)$.
- Here, a local $T_2$ experiment (step 2→3 A/B) produces a large, easy-to-see
  drop in the global conversion SLO.

### 6. Time series of C(t): SPC-style view

![End-to-End Conversion over Time](images/plot6.png)

What it shows:
- X-axis: time windows $t = 1, \dots, 20$.
- $C(t)$ as a line: first 10 windows use healthy $T_2 \in [0.9, 1.0]$, last 10 use
  a critical worse $T_2 \in [0.2, 0.5]$ while $T_1, T_3, T_4$ stay healthy.
- A vertical dashed line at the change point and a dotted horizontal line
  at the baseline $C_1$.

Interpretation:
- Windows 1–10 cluster around the stable baseline $C_1$ (stable system).
- After the A/B change on step 2→3, windows 11–20 drop to a clearly
  lower level of $C(t)$.

This is how $C(t)$ behaves as an SPC-style SLO:
- In a healthy, stable system, $C(t)$ should fluctuate around a constant mean.
- A structural change (like the T2 experiment) creates a sustained level shift
  in $C(t)$, which is exactly what SPC rules are designed to detect.

### 7. Time series of C(t) with control limits

![End-to-End Conversion with Control Limits](images/plot7.png)

What it shows:
- Same $C(t)$ points as in the previous chart.
- A horizontal line at the average $\bar C$.
- Upper and lower control limits (UCL/LCL) around that average.

How the limits are computed (individuals chart):

- Moving range: $MR_t = |C(t) - C(t-1)|$.
- Average moving range: $\overline{MR}$.
- Control limits:

  $$\text{UCL} = \bar C + 2.66 \cdot \overline{MR}, \quad
    	ext{LCL} = \bar C - 2.66 \cdot \overline{MR}$$

Under a stable system, almost all points should stay between UCL and LCL.
When the flow changes (for example, a bad T2 experiment), $C(t)$ will sit
outside this band for a while, which is a strong signal that something
structural has changed.

This individuals-chart approach is a pragmatic approximation for a bounded
proportion $C(t) \in [0,1]$ whose denominator $A_1(t)$ can vary over time.
In practice we also:

- Clamp the limits to the [0, 1] range (no negative conversion rates).
- Pay attention to windows with very small $A_1(t)$, where natural noise is high.

If you want a more formal treatment, you can also build a classic p-chart that
explicitly uses $A_1(t)$ as the denominator in the variance of $C(t)$. The
intuition stays the same: we are looking for sustained level shifts in $C(t)$,
not for every tiny random fluctuation.

### 8. Effect of adding more steps

![End-to-end conversion vs number of steps](images/plot9.png)

What it shows:
- A simple flow where every step has the same success ratio $T = 0.9$.
- We compute the overall conversion $C(n) = 0.9^n$ for flows with 1, 2, 3, …, 20 steps.

Interpretation:
- With 1 step, $C(1) = 0.9$ (90%).
- With 4 steps, $C(4) = 0.9^4 \approx 0.66$ (only ~66% of users make it through).
- As you keep adding steps, $C(n)$ keeps shrinking, even though each individual step
  looks “good” at 90%.

This is why it is important to keep flows as short as possible and to measure the
end-to-end $C(t)$, not just per-step success. Long, multi-step flows silently eat
conversion, and the product $C(t) = T_1(t) \cdot T_2(t) \cdots T_L(t)$ makes that visible.

## Traffic mix, bots, and abuse

In real systems, not all arrivals are equal: some traffic comes from real users,
some from automated clients, and some from abusive sources (bots, credential
stuffing, attacks). All of this contributes to the arrivals $A_i(t)$ and
therefore to the measured transitions $T_i(t)$ and conversion $C(t)$.

From the point of view of this model, abusive traffic is part of the
"environmental noise" of the system:

- When traffic mix is stable, its effect is baked into the normal range and
  control limits of $C(t)$ and $T_i(t)$.
- When abuse or bot traffic surges, you often see a change in $A_1(t)$ and a
  drop in one or more transitions, which is a real signal that something has
  changed in the flow.

Depending on your needs, you can either:

- Treat all traffic together and let the control limits learn the usual mix, or
- Define separate flows/tags for "trusted" vs "untrusted" segments, so you can
  monitor and react to them differently.

The key point is that this methodology does not require per-user identity to be
useful. It works on aggregate flows, and changes in traffic mix (including
abuse) show up as changes in the same $A_i(t)$, $T_i(t)$, and $C(t)$ signals.

---

## Appendices

### Appendix A: Statistical properties and volume dependence

The **definitions** in this model are volume-agnostic: $T_i$ and $C$ are ratios, so
they do not change just because you have 1k users or 1M users. In that sense, the math
is based on proportions ($T_i$, $C$), not on absolute counts.

However, the **uncertainty** of those ratios *does* depend on volume:

- With very small $A_1(t)$ (for example, a few users per window), $T_i(t)$ and $C(t)$
  have high binomial variance; individual windows can look noisy even in a stable system.
- As volume grows, the law of large numbers makes the per-window ratios concentrate
  around their true values.
- At very high volume, you will be able to detect tiny changes in $T_i$ and $C$; whether
  those changes are operationally important is a product decision, not a math question.

So the model itself is volume-agnostic, but the **signal-to-noise ratio** and statistical
power depend strongly on traffic. In practice you can:

- Use larger windows (for example, 5–15 minutes) at low volume.
- Keep shorter windows at high volume and let the control limits absorb normal variation.

#### Binomial variance

For a single transition $T_i(t) = A_{i+1}(t)/A_i(t)$ with true probability $p$:

$$\text{Var}(T_i) \approx \frac{p(1-p)}{A_i(t)}$$

This means:
- At $A_i(t) = 10$, standard deviation $\sigma \approx 0.15$ (very noisy).
- At $A_i(t) = 100$, $\sigma \approx 0.05$ (noticeable variance).
- At $A_i(t) = 1000$, $\sigma \approx 0.015$ (quite stable).

For the composite conversion $C(t) = \prod T_i(t)$, variances compound, so you need
even more volume to get stable estimates.

### Appendix B: Time-window selection and timing bias

#### The timing bias problem

Funnels follow individual users across time, so each user is counted once in each step,
no matter how long they take between steps.

In this model we do not track users; we only see flows per time window. If the window
is short (for example: 1 minute) and a user spends more than 1 minute between step 1
and step 2, they appear in $A_1(t)$ in one window and in $A_2(t')$ in the next window.
In that case, the per-window ratio $T_1(t) = A_2(t)/A_1(t)$ is a **biased estimator** of
the true step-1→2 success probability.

This is similar in spirit to [exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/):
random timing spreads calls across time instead of creating big spikes. At low volume
and with very small windows, this timing noise makes $T_i(t)$ and $C(t)$ look noisy,
even when the underlying system is perfectly stable.

As volume grows (or you use slightly larger windows), the law of large numbers wins:
flows eventually move into the next step, and the window-level ratios settle around
their true values. The SPC-style view of $C(t)$ and the control limits help you focus
on structural changes instead of this natural timing noise.

Denominators matter here: windows with very small $A_1(t)$ will naturally have more
volatile $C(t)$. We still treat those windows consistently, but when designing SLOs
and alerts we usually:

- Aggregate over bigger windows when traffic is low (for example, 5–15 minutes).
- Require persistence (multiple bad windows in a row) before paging, so we do not
  overreact to a single noisy low-volume interval.

#### Window size selection heuristic

To minimize timing bias, choose window size based on flow latency:

$$W \geq k \times p95(\text{step latency}), \quad k \in [5, 10]$$

Where:
- $W$ is the window size (in time units: seconds, minutes).
- $p95(\text{step latency})$ is the 95th percentile time users spend between steps.
- $k = 5$ gives faster incident detection but higher timing noise at low volume.
- $k = 10$ gives cleaner signals but slower alerting.

**Examples**:
- Login flow with p95 = 2 seconds → $W \geq 10-20$ seconds.
- OAuth flow with p95 = 30 seconds → $W \geq 2.5-5$ minutes.
- Checkout flow with p95 = 45 seconds → $W \geq 4-8$ minutes.

When $W \geq 5 \times p95$, roughly 95% of users complete steps within one window,
reducing the bias in $T_i(t) = A_{i+1}(t)/A_i(t)$. At very high volume, you can
use smaller $k$ (closer to 5) because the law of large numbers compensates for
timing noise. At low volume, use larger $k$ (closer to 10) or consider if this
model is appropriate.

**Important note**: The original methodology counts arrivals (number of requests)
per window, not based on operation timing. This heuristic is an advanced
optimization for when you want to align window size with typical user flow
duration to reduce timing bias. For most applications, using fixed 5-15 minute
windows based on request volume is simpler and works well.

### Appendix C: Advanced control chart methods

#### P-chart for varying volume

The individuals chart (shown in plot 7) assumes constant variance across windows.
When $A_1(t)$ varies significantly (daily/weekly traffic patterns), a **p-chart**
is more accurate.

**Formulation**:

For a given window $t$ with conversion $C(t) = A_5(t)/A_1(t)$ and arrivals $A_1(t)$:

$$
\begin{aligned}
\sigma(C) &\approx \sqrt{\frac{\bar{C}(1 - \bar{C})}{A_1(t)}} \\
\text{UCL}(t) &= \bar{C} + 3\sigma(C) \\
\text{LCL}(t) &= \bar{C} - 3\sigma(C)
\end{aligned}
$$

Where $\bar{C}$ is the mean conversion from a stable period. This gives:
- **Tighter limits** at high volume (high $A_1(t)$ → low variance → narrow band).
- **Wider limits** at low volume (low $A_1(t)$ → high variance → wide band).

This reduces false positives during low-traffic periods (nights, weekends) and
increases sensitivity during high-traffic periods (business hours, peak season).

**When to use each**:
- **Individuals chart** (moving range): simpler, works well when $A_1(t)$ is relatively stable (< 2x variation).
- **P-chart**: more accurate for systems with strong daily/weekly patterns (> 2x variation in $A_1(t)$).

For most production systems with typical traffic patterns, **p-chart is recommended**
as the default. Modern metrics backends can compute per-window limits efficiently.

#### Adaptive control limits

Fixed control limits computed once at deployment can become stale as systems evolve.
For long-lived systems (6+ months in production), consider adaptive limits:

**Algorithm**:
- Use a rolling 7-day or 30-day window of stable periods (excluding known incidents).
- Recompute $\bar{C}$, $\overline{MR}$, UCL, and LCL daily.
- Mark periods as "unstable" if they exceed current limits; exclude them from
  the next limit computation.

**Trade-off**:
- **Static limits**: simple, easy to reason about, but brittle over time.
- **Adaptive limits**: track system evolution, but can mask gradual degradation if
  the degradation is included in the rolling window.

**Recommendation**: Start with static limits from a known-good period, review and
manually update limits quarterly, and implement adaptive limits only if manual
updates become burdensome or if the system has strong seasonality.

### Appendix D: Non-linear flow handling

The simple linear chain (1 → 2 → 3 → 4 → Success) is easy to model, but real
flows often have branches, optional steps, and loops.

#### Approach for branches

Example: payment via credit card OR PayPal.

- Define two parallel subflows: `flow=checkout-cc` and `flow=checkout-paypal`.
- Track $C_{\text{cc}}(t)$ and $C_{\text{paypal}}(t)$ separately.
- Aggregate: $C_{\text{checkout}}(t) = \frac{A_5^{\text{cc}}(t) + A_5^{\text{paypal}}(t)}{A_1^{\text{cc}}(t) + A_1^{\text{paypal}}(t)}$.

#### Approach for optional steps

Example: step 2 can skip directly to step 4.

- Define $T_2^{\text{continue}} = A_3(t)/A_2(t)$ (continue to step 3).
- Define $T_2^{\text{skip}} = A_4(t)/A_2(t)$ where arrivals came directly from step 2.
- Ensure $T_2^{\text{continue}} + T_2^{\text{skip}} \leq 1$ (some users drop entirely).

#### Approach for loops

Example: step 2 can retry step 2 (CAPTCHA fail → retry).

- Count unique first-time arrivals $A_2^{\text{first}}(t)$ separately from retries $A_2^{\text{retry}}(t)$.
- Track success: $T_2(t) = A_3(t) / A_2^{\text{first}}(t)$ (eventual success from unique attempts).

**Note**: These extensions require careful metric design and more complex queries,
but the core principle (count flows, not users) remains intact.

### Appendix E: When not to use this model

This metric-based approach works well for many flows, but has clear limitations.

#### Do not use this model when:

1. **Low volume** (< 100 arrivals per window):
   - Timing noise dominates; $T_i(t)$ and $C(t)$ are too volatile for reliable alerting.
   - **Alternative**: Use larger windows (15-60 minutes), or switch to event-based funnels.

2. **Non-linear flows** with loops, optional steps, or complex DAGs:
   - The product model $C = \prod T_i$ assumes strictly sequential steps.
   - Loops (e.g., retry step 2 → step 2) and branches (e.g., step 3a OR step 3b) break this assumption.
   - **Alternative**: Decompose into parallel linear subflows (see Appendix D), or track success directly without intermediate transitions.

3. **High abuse/bot ratio** (> 30% of traffic) without segmentation:
   - Attack spikes can cause $T_i(t)$ drops that are not actionable for flow reliability.
   - If $A_1(t)$ suddenly contains 80% bots (was 10%), $T_1(t)$ collapses, but this is a security issue, not a flow issue.
   - **Alternative**: Segment flows by `traffic_type=trusted` vs `traffic_type=bot`, or add anomaly detection on $A_1(t)$ volume before reacting to $C(t)$ drops.

4. **Very long flows** (> 20 steps):
   - Even with $T_i = 0.9$, $C(20) = 0.9^{20} \approx 0.12$ (12% conversion).
   - Small changes in any $T_i$ cause large swings in $C(t)$, making limits unstable.
   - **Alternative**: Break into shorter subflows (e.g., "auth" + "profile setup" + "activation") and monitor each separately.

5. **Flows with significant sampling** (< 1% of traffic):
   - Sampling increases variance; at 0.1% sampling with 10k users, you have only 10 sampled users.
   - **Alternative**: Increase sampling rate for critical flows, or aggregate over longer windows.

#### When this model works best

The model is most effective for:
- **High-volume** flows (> 1000 arrivals/hour or > 100/window)
- **Sequential flows** with 2-10 steps
- **Systems that already emit per-step metrics**
- **Operational alerting** and SLO tracking (not deep user analysis)

### Appendix F: Integration with existing SLIs

How does $C(t)$ relate to traditional per-endpoint SLIs?

#### Typical SLI stack

- **Availability**: HTTP success rate per endpoint (e.g., `GET /api/login → 99.9% 2xx`).
- **Latency**: p95 response time per endpoint (e.g., `GET /api/login → p95 < 200ms`).
- **Flow conversion**: $C(t)$ for end-to-end journey (e.g., `login flow → 72% conversion`).

#### How they interact

- Availability per endpoint is a **necessary** condition for flow success, but not sufficient.
- A flow can fail even when all endpoints return 2xx (e.g., logic bug, bad UX,
  broken integration between steps).
- $C(t)$ is a **higher-level** SLI that captures end-to-end user experience.

#### SLO composition

- **Per-step SLO**: "Step 2 API returns 2xx for 99.9% of requests."
- **Flow SLO**: "End-to-end login conversion $C(t) \geq 70\%$ for 99% of windows."
- Both are needed; they answer different questions.

Per-step SLOs tell you *which component* is broken. Flow SLOs tell you whether
the *entire user journey* is working.

### Appendix G: Cardinality and cost estimation

Adding flow tags increases metric cardinality. Here's a concrete example:

**Setup**:
- **Flows**: 10 (login-web, login-mobile, signup-web, signup-mobile, checkout, payment, etc.)
- **Regions**: 5 (us-east, us-west, eu-west, eu-central, ap-southeast)
- **Metrics per flow**: 4 (A1, A2, A3, A4 arrival counters)
- **Total additional timeseries**: $10 \times 5 \times 4 = 200$

**Cost estimate (Datadog)**:
- Custom metric pricing: ~\$0.05 per timeseries per month.
- Total: $200 \times 0.05 = \$10/month$.

**Cost estimate (Prometheus self-hosted)**:
- Memory: ~2KB per timeseries → $200 \times 2KB = 400KB$ (negligible).
- Storage: depends on retention and cardinality; typically < \$1/month for 200 timeseries.

**Key insight**: A small, controlled tag like `flow` with 10-20 distinct values
is much cheaper than per-user or per-session tags. The cardinality impact is
manageable and predictable.
