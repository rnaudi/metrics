# metrics

Model multi-step user journeys (login, signup, checkout, payment, etc.) using **plain metrics** and **Statistical Process Control (SPC)** instead of heavy funnel/event tooling.

The goal of this document is to explain **why** this works and **when** it is a good idea, in a way that is practical and easy to read.

---

## Getting started

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

---

## TL;DR

We want an SLO-style signal that answers a simple question:

> "Is this user journey working end-to-end right now?"

Instead of tracking individual users or sessions, we:

- Count **requests per step** of the journey in fixed time windows.
- Compute **step-to-step conversion ratios** and the **overall end-to-end conversion**.
- Watch that overall conversion with an **SPC-style control chart** and alert on real changes.

This works best for:

- High-volume, mostly sequential flows (login, signup, checkout, payment, etc.).
- Operational SLOs and alerting (error budgets, incident detection).

This is **not** a replacement for product funnels or deep analytics. It is a simple, cheap, and robust way to get **flow-level SLIs** out of the metrics you already have.

---

## 1. Intuition

Most tools give you some form of **funnel**: they follow users or sessions across a series of events and tell you where people drop off.

Funnels are great when you want to ask questions like:

- "What do users from country X do after step 3?"
- "How do mobile users behave differently from desktop?"

But funnels often come with tradeoffs:

- You must define custom events, pages, and flows.
- You need user or session identity to stitch steps together.
- The results are usually **hard to plug directly into SLOs and alerts**.

This model takes a different angle:

- We **do not track users**, only **flows of requests**.
- We reuse the **metrics you already emit** (HTTP counters, RPC call counts, etc.).
- We compute **simple ratios** that behave like a funnel but are easy to automate and alert on.

The key outcome is a single number per flow and per window:

> **C(t)** = "fraction of requests that started the journey in this window and ended in Success."

If C(t) suddenly drops and stays low, something meaningful is wrong in that flow.

---

## 2. The basic model

Consider a simple journey with 4 numbered steps and a terminal Success outcome:

> Step 1 → Step 2 → Step 3 → Step 4 → Success

For each fixed time window t (for example 5 minutes), we define:

- **Arrivals**:  
  Aᵢ(t) = number of requests that **enter step i** in window t.
- **Transitions**:  
  Tᵢ(t) = Aᵢ₊₁(t) / Aᵢ(t) — fraction of arrivals at step i that make it to step i+1.  
  (For the last step, T₄(t) is the terminal success ratio.)
- **End-to-end conversion**:

$$
\begin{aligned}
C(t) &= \frac{A_{Success}(t)}{A_1(t)} \\
     &= T_1(t) \cdot T_2(t) \cdot T_3(t) \cdot T_4(t)
\end{aligned}
$$

We call C(t) the **flow conversion SLI** for that journey.

Notes:

- We count **requests per window**, not unique users. Retries and repeated attempts show up as extra arrivals. This is intentional: they are part of the operational signal.
- Transitions Tᵢ(t) tell you **where** people drop out. C(t) tells you **how bad** the end-to-end impact is.
- You should still keep per-endpoint SLIs (latency, error rate). This model **adds** a journey-level SLI; it does not replace existing ones.

The demo script in [src/metrics_demo.py](src/metrics_demo.py) generates plots that make these ideas concrete.

---

## 3. Windows, volume, and noise

The formulas above are **ratios**, so the definitions do not change with traffic volume. In practice, though, volume matters a lot for **noise**:

- With very few arrivals in a window, any ratio Aᵢ₊₁ / Aᵢ will bounce around.
- With more arrivals, the ratios become much more stable.

You can think of each arrival into step 1 as a Bernoulli trial that either reaches Success in that window or does not. For a stable system with true conversion p and A₁ arrivals in window t:

$$\text{Var}(C(t)) \approx \frac{p (1 - p)}{A_1(t)}$$

Rule of thumb:

- Try to have at least **100–200 arrivals per window** for flows you want to alert on.
- At lower volumes, use **larger windows** (for example 15–60 minutes) and be conservative about paging.

### Timing and window size

Because we work in fixed windows, a user can start in one window and finish in the next. That makes per-window ratios **noisy estimates** of the underlying step success probabilities, especially when:

- Windows are very small, and
- Users take a long time between steps.

Simple heuristic for window size W:

$$
W \geq k \times p95(\text{time between steps}), \quad k \in [5, 10]
$$

Examples:

- Login with p95 ≈ 2s → W around 10–20s.
- OAuth with p95 ≈ 30s → W around 2.5–5 min.
- Checkout with p95 ≈ 45s → W around 4–8 min.

At high volume you can get away with smaller windows. At low volume you will need larger ones, or a different approach (for example, event-based funnels).

---

## 4. Using SPC as an alerting layer

Once you compute C(t) for each window, you can treat it like a **control chart**:

1. Pick a **stable reference period** (no known incidents or big experiments).
2. Estimate the **typical value** of C (its average over that period).
3. Estimate how much C(t) normally moves around.
4. Draw **control limits** around the typical value.
5. Alert only when C(t) **breaks those limits in a sustained way**.

There are two useful variants:

- **Individuals chart (I-chart)**
  - Good when traffic per window A₁(t) is roughly stable.
  - Uses the average **moving range** of C(t) to set symmetric upper/lower limits.
  - Simple to implement in most metrics systems.

- **P-chart (proportion chart)**
  - Better when traffic per window varies a lot (day/night cycles, weekday/weekend).
  - Treats C(t) as a proportion with denominator A₁(t) and sets **per-window limits** that are tighter at high volume and wider at low volume.

You do not need to be an SPC expert to get value here. The key idea is:

> Let the system show you what “normal” C(t) looks like, and alert on **persistent deviations**, not on every small wiggle.

For a friendly introduction, see:  
https://entropicthoughts.com/statistical-process-control-a-practitioners-guide

---

## 5. When this works well

This approach is a good fit when **most** of these are true:

- The flow is **mostly sequential**, with a small number of clear steps (2–10).
- You see at least **100–200 arrivals per window** for the flows you care about.
- You already have per-step metrics (HTTP/RPC counters, etc.) or can add them.
- You want **operational signals** and SLOs, not detailed user analytics.

Typical good candidates:

- Login, OAuth, SSO, device linking
- Signup and account activation
- Cart / checkout
- Payment and billing flows

---

## 6. When it is a poor fit

You should be cautious or choose a different method when:

- **Low volume**: fewer than ~100 arrivals per window.
  - Ratios are too noisy for reliable alerting.
  - Use bigger windows, or switch to event-based funnels.

- **Very complex or long-lived flows**: many branches, loops, or steps that span hours/days.
  - The simple product C = ∏Tᵢ stops being a clean model.
  - Break the flow into shorter subflows, or use tracing and analytics tools.

- **High or spiky abuse/bot traffic** mixing with real users.
  - Attack traffic can dominate A₁(t) and make C(t) reflect security issues more than product/infra quality.
  - If abusive traffic can be a large fraction of arrivals, segment by traffic type (for example, flow=login & traffic=trusted).

- **Aggressive sampling** (for example, < 1% of traffic).
  - Sampling increases variance; with very low effective counts, SPC signals become unreliable.

This model is not meant to handle every journey. It is intentionally **simple**, and it is OK to say "this flow is too weird or too small for this tool".

---

## 7. How this relates to other observability tools

This model is meant to **complement**, not replace, existing tools:

- **Per-endpoint SLIs** (availability and latency)
  - Tell you whether a specific API is working.
  - Do not capture the full user journey.

- **RUM and funnels** (Grafana Faro, Datadog RUM, GA, Amplitude, Mixpanel)
  - Follow individual users and sessions.
  - Great for segmentation and product questions.
  - Heavier to instrument and more expensive at large scale.

- **Synthetic monitoring** (Datadog Synthetics, Pingdom, Checkly)
  - Run scripted journeys from bots.
  - Great for smoke tests and third-party checks.
  - Not real user traffic; cannot see load-dependent issues.

- **APM and tracing** (Datadog APM, Honeycomb, Lightstep, Jaeger)
  - Trace individual requests across services.
  - Excellent for debugging specific failures.
  - More complex and expensive as a primary SLO signal.

Where this model shines:

- You want a **cheap, low-cardinality, flow-level SLI**.
- You want to reuse the **same metrics** for dashboards, SLOs, and alerts.
- You want something that is easy to explain to engineers and product teams.

---

## 8. Implementation sketch (very high level)

This document is a **spec**, not a full implementation guide, but a basic rollout often looks like this:

1. **Pick one flow** to start with (for example, web login).
2. **Name the steps** (login form, OTP page, session creation, etc.).
3. For each step, emit a **request counter** tagged with the flow and step.
4. In your metrics backend, compute Aᵢ(t), Tᵢ(t), and C(t) per window.
5. Plot C(t) over time and add **simple control limits**.
6. When you trust the signal, wire C(t) into an **SLO and alert**.

You can then copy the pattern to more flows by reusing the same math and charts.

---

## 9. References and inspiration

- Google SRE Workbook — "Modeling user journeys"  
  https://sre.google/workbook/implementing-slos/#modeling-user-journeys

- Statistical Process Control (SPC) in tech operations  
  https://entropicthoughts.com/statistical-process-control-a-practitioners-guide

- Classic SPC texts (for deeper math and chart variants)
  - Montgomery, *Introduction to Statistical Quality Control*.
  - Wheeler, *Understanding Variation*.

This project is about making those ideas **practical and approachable** for modern web systems by leaning on the metrics infrastructure you already have.
