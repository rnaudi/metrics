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
Funnels are great for one-off analysis by segment (country, device, age, etc.), but
they usually need a lot of custom work:

- You must define events, pages, and flows by hand.
- You need to maintain segments and filters inside the UI.
- You often cannot reuse funnel numbers directly in SLOs, alerts, or code.

This approach takes a different angle: reuse metrics you already have.
Instead of tracking individual users, we track arrivals and transitions between steps.

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

- Funnels are usually UI-only: you see step conversions in a dashboard, but it is hard to plug them into SLOs or alerts.
- Funnels often need extra events: each step becomes a separate event, which adds instrumentation and schema work.
- Funnels depend on user identity: session/user ids can be fragile in OAuth flows (redirects, retries, cross-domain hops).
- Funnels hide the math: you cannot easily write down and reuse the exact formulas behind the numbers.
- Funnels track unique users and analyse segments; this model tracks flows, which are easier to reason about.
- Metric-based funnels reuse existing counters, so the same data powers dashboards, SLOs, alerts, and ad-hoc analysis.

## Metric definition

Very small glossary:

- **Step** ($i$): a state in the journey (for example: "login web site", "login from a device", "one time token page", "user-password validation").
- **Transition** ($T_i$): fraction of users that move from step $i$ to step $i+1$.
- **Arrival** ($A_i$): number of users that enter a step in a given time window.
- **Success transition** ($T_L$): HTTP 2xx at the Last step (step Last → Success).
- **Conversion** ($C$): fraction of users that started in step 1 and ended in Success.

### Why this is volume-agnostic

This model works the same if you have 1k users or 1M users.
The math is based on ratios ($T_i$, $C$), not on absolute counts.

- If traffic doubles at 18:00 compared to 09:00, the conversion math is still valid.
- Seasonality or daily patterns change $A_i(t)$, but not the definition of $T_i(t)$ or $C(t)$.
- Under a stable system you can put upper/lower bands around $C(t)$ and detect when
  behavior breaks away from the usual range.

### Time windows, funnels, and noise

Funnels follow individual users across time, so each user is counted once in each step,
no matter how long they take between steps.

In this model we do not track users; we only see flows per time window. If the window
is short (for example: 1 minute) and a user spends more than 1 minute between step 1
and step 2, they appear in $A_1(t)$ in one window and in $A_2(t')$ in the next window.
In that case, the per-window ratio $T_1(t) = A_2(t)/A_1(t)$ is a **noisy estimate** of
the true step-1→2 success probability.

This is similar in spirit to [exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/):
random timing spreads calls across time instead of creating big spikes. At low volume
and with very small windows, this timing noise makes $T_i(t)$ and $C(t)$ look noisy,
even when the underlying system is perfectly stable.

As volume grows (or you use slightly larger windows), the law of large numbers wins:
flows eventually move into the next step, and the window-level ratios settle around
their true values. The SPC-style view of $C(t)$ and the control limits help you focus
on structural changes instead of this natural timing noise.


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


### SPC and control limits

Once you have $C(t)$ over time, you can treat it like a control chart:

- Estimate the "normal" range of $C(t)$ when the system is stable.
- Define upper and lower control limits around that range.
- Alert only when $C(t)$ breaks those limits for a while (not on every small wiggle).

I recommend [Statistical Process Control: A Practitioner’s Guide](https://entropicthoughts.com/statistical-process-control-a-practitioners-guide) as a basic introduction.


## Metric definitions example (4-step flow)

Let the auth flow be 4 numbered steps plus a terminal Success outcome:

> Step 1 → Step 2 → Step 3 → Step 4 → Step 5 (Success)

For a given time window $t$:

- Arrival counts: $A_i(t)$ = number of users entering step $i$, $i \in \{1,2,3,4,5\}$.
- Success arrivals: $A_5(t)$ = number of users who completed the flow with HTTP 200 at step 4 (Success).
- Transition ratios between steps: $T_i(t) = \dfrac{A_{i+1}(t)}{A_i(t)}$, $i \in \{1,2,3,4\}$.
  - For $i \in \{1,2,3\}$, $T_i(t)$ is a normal "continue to next step" ratio.
  - For $i = 4$, $T_4(t)$ is the terminal success ratio (HTTP 2xx at step 4).

Notes:
- If a user drops between steps 3 and 4, that shows up in $T_3(t)$ regardless
  of whether step-3 HTTP codes are 200 or 500. The loss is in the transition.
- We only care about HTTP 200 on the last step (4). Once a user is in $A_5(t)$,
  it is a terminal state; there is no further transition.

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
