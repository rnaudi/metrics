import matplotlib.pyplot as plt
import os
import random
import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class FlowScenario:
	"""Simple helper to derive arrivals and conversion from per-step transitions.

	`A1` is the number of *requests* entering step 1 in a window.
	Given per-step transition ratios, we derive **expected** per-step
	arrivals that satisfy the algebra in the README:
		A_{i+1}(t) ≈ T_i(t) · A_i(t).
	If `max_retries > 0`, we treat retries at each step using a simple
	expected-attempts factor when computing arrivals.
	"""
	name: str
	A1: int
	transitions: List[float]
	max_retries: int = 0

	@property
	def arrivals(self) -> List[float]:
		"""Deterministic per-step *request* arrivals [A1, A2, ..., AS].

		These are synthetic, **noise-free** counts that obey the
		A_{i+1} = T_i · A_i relationship exactly. In real systems you
		measure each A_i(t) directly per window; here we just generate a
		clean toy world consistent with the math so the plots are easy to
		interpret.
		"""
		passes: List[float] = [float(self.A1)]
		for T in self.transitions:
			passes.append(passes[-1] * T)

		requests: List[float] = []
		for i, base in enumerate(passes):
			if i < len(self.transitions):
				T_i = self.transitions[i]
				if self.max_retries > 0:
					attempts_factor = min(1.0 / T_i, 1.0 + self.max_retries)
				else:
					attempts_factor = 1.0
			else:
				attempts_factor = 1.0
			requests.append(base * attempts_factor)

		return requests

	@property
	def conversion(self) -> float:
		c = 1.0
		for T in self.transitions:
			c *= T
		return c


def plot1_arrivals(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot1.png") -> None:
	"""Plot arrivals per step for the first scenario (flow_a)."""
	arrivals_a = flow_a.arrivals
	labels = [f"Step {i + 1}" for i in range(len(arrivals_a))]
	plt.figure(figsize=(7, 4))
	plt.bar(labels, arrivals_a, color="#1f77b4")
	plt.title(f"Arrivals per Step: {flow_a.name}")
	plt.ylabel("Requests")
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot2_arrivals(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot2.png") -> None:
	"""Plot arrivals per step for the second scenario (flow_b)."""
	arrivals_b = flow_b.arrivals
	labels = [f"Step {i + 1}" for i in range(len(arrivals_b))]
	plt.figure(figsize=(7, 4))
	plt.bar(labels, arrivals_b, color="#7f7f7f")
	plt.title(f"Arrivals per Step: {flow_b.name}")
	plt.ylabel("Requests")
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot3_arrivals_comparison(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot3.png") -> None:
	"""Plot arrivals per step for both scenarios on the same chart."""
	arrivals_a = flow_a.arrivals
	arrivals_b = flow_b.arrivals
	if len(arrivals_a) != len(arrivals_b):
		raise ValueError("Flow scenarios must have the same number of steps")
	labels = [f"Step {i + 1}" for i in range(len(arrivals_a))]
	plt.figure(figsize=(7, 4))
	plt.bar(labels, arrivals_a, alpha=0.7, label=flow_a.name, color="#1f77b4")
	plt.bar(labels, arrivals_b, alpha=0.7, label=flow_b.name, color="#7f7f7f")
	plt.title(f"Arrivals per Step: {flow_a.name} vs {flow_b.name}")
	plt.ylabel("Requests")
	plt.legend()
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot4_transition_ratios(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot4.png") -> None:
	"""Plot transition ratios T_i for both scenarios as grouped bars."""
	if len(flow_a.transitions) != len(flow_b.transitions):
		raise ValueError("Flow scenarios must have the same number of transitions")
	ratio_labels = [f"T{i + 1}" for i in range(len(flow_a.transitions))]
	positions = list(range(len(ratio_labels)))
	width = 0.35
	plt.figure(figsize=(6, 4))
	plt.bar([p - width / 2 for p in positions], flow_a.transitions, width=width, label=flow_a.name, color="#1f77b4")
	plt.bar([p + width / 2 for p in positions], flow_b.transitions, width=width, label=flow_b.name, color="#7f7f7f")
	plt.xticks(positions, ratio_labels)
	plt.title(f"Transition Ratios: {flow_a.name} vs {flow_b.name}")
	plt.ylim(0, 1)
	plt.legend()
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot5_conversion(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot5.png") -> None:
	"""Plot end-to-end conversion C for both scenarios."""
	C1 = flow_a.conversion
	C2 = flow_b.conversion
	plt.figure(figsize=(4, 4))
	plt.bar([flow_a.name, flow_b.name], [C1, C2], color=["#1f77b4", "#7f7f7f"])
	plt.title("End-to-End Conversion (C)")
	plt.ylabel("Conversion Ratio")
	plt.ylim(0, 1)
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()

@dataclass
class SimulationScenario:
	"""Simulate C(t) over time for a base and test FlowScenario.

	The simulation runs a `base` flow for `base_length` windows, then a `test`
	flow for `test_length` windows. Each transition is jittered uniformly
	within `±jitter` around its nominal value (clamped to [0, 1]). This is only
	for visualising how C(t) and control limits behave; it is not a production
	simulator.
	"""
	name: str
	base: FlowScenario
	base_length: int
	test: FlowScenario
	test_length: int
	jitter: float = 0.05

	def simulate_C_series(self) -> List[float]:
		"""Return a C(t) series: base phase then optional test phase.

		For each window we:
		- Start with A1 = flow.A1 (requests entering step 1).
		- For each step, jitter T_i within ±`jitter`, then approximate
		  binomial(A_i, T_i) with a normal distribution so that volume
		  controls how noisy the next-step arrivals are.
		- Compute C(t) = A_S / A_1 from the simulated counts.
		"""
		series: List[float] = []
		total_windows = self.base_length + self.test_length
		for idx in range(total_windows):
			flow = self.base if idx < self.base_length else self.test
			A_current = flow.A1
			A_initial = A_current
			if A_initial <= 0:
				series.append(float("nan"))
				continue
			for T in flow.transitions:
				low = max(0.0, T - self.jitter)
				high = min(1.0, T + self.jitter)
				p = random.uniform(low, high)
				mean = A_current * p
				var = A_current * p * (1.0 - p)
				std = math.sqrt(var)
				noise = random.gauss(0.0, std) if std > 0 else 0.0
				A_next = int(round(mean + noise))
				if A_next < 0:
					A_next = 0
				if A_next > A_current:
					A_next = A_current
				A_current = A_next
			C_t = A_current / A_initial if A_initial > 0 else float("nan")
			series.append(C_t)
		return series


def compute_individuals_control_limits(series: List[float], stable_windows: int) -> Tuple[float, float, float] | None:
	"""Compute mean and individuals-chart control limits from the stable prefix.

	The first `stable_windows` points are treated as representing stable behavior.
	Returns (mean, UCL, LCL), clamped to [0, 1], or None if not enough data.
	"""
	stable_C = series[:stable_windows]
	if len(stable_C) < 2:
		return None

	mean_C = sum(stable_C) / len(stable_C)
	moving_ranges = [abs(stable_C[i] - stable_C[i - 1]) for i in range(1, len(stable_C))]
	mr_bar = sum(moving_ranges) / len(moving_ranges)
	k = 2.66  # SPC constant for individuals chart
	ucl = mean_C + k * mr_bar
	lcl = mean_C - k * mr_bar
	# Clamp to [0, 1]
	ucl = min(1.0, ucl)
	lcl = max(0.0, lcl)
	return mean_C, ucl, lcl

def plot_C_with_limits(
	sim: SimulationScenario,
	filename: str = "images/plot7.png",
	title: str | None = None,
	highlight_test_phase: bool = False,
) -> None:
	"""Plot C(t) with SPC-style control limits for any SimulationScenario.

	If `highlight_test_phase` is True, the test phase (windows after the
	base_length) is shaded to make step changes or storms visually obvious.
	"""
	C_series = sim.simulate_C_series()
	windows = list(range(1, len(C_series) + 1))
	limits = compute_individuals_control_limits(C_series, stable_windows=sim.base_length)
	if limits is None:
		return
	mean_C, ucl, lcl = limits
	plt.figure(figsize=(8, 4))
	plt.plot(windows, C_series, marker="o", color="#1f77b4", label="C(t)")
	if highlight_test_phase:
		for w in range(sim.base_length + 1, len(windows) + 1):
			plt.axvspan(w - 0.5, w + 0.5, color="red", alpha=0.05)
	plt.hlines(mean_C, 1, len(windows), colors="#1f77b4", linestyles="dashed", label="Average C (base phase)")
	plt.hlines(ucl, 1, len(windows), colors="#7f7f7f", linestyles="dotted", label="Upper limit (base phase)")
	plt.hlines(lcl, 1, len(windows), colors="#7f7f7f", linestyles="dotted", label="Lower limit (base phase)")
	plt.title(title or "End-to-End Conversion C(t) with control limits")
	plt.xlabel("Time window")
	plt.ylabel("Conversion Ratio C(t)")
	plt.ylim(0, 1)
	plt.legend()
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def simulate_windowed_T(num_users_per_minute: int, num_minutes: int, p_success: float = 0.9, mean_delay: float = 1.0):
	"""Simulate a single transition (Step 1 -> Step 2) in 1-minute windows.

	Each minute we get `num_users_per_minute` new users entering step 1.
	Each user has probability `p_success` of eventually reaching step 2, with
	a random delay drawn from an exponential distribution with mean `mean_delay`.

	We then count step-1 and step-2 arrivals per minute and return the measured
	T1(t) = A2(t)/A1(t) time series.
	"""
	step1_times = []
	step2_times = []

	for minute in range(num_minutes):
		for _ in range(num_users_per_minute):
			# User enters step 1 at some point within this minute
			t1 = minute + random.random()
			step1_times.append(t1)
			if random.random() < p_success:
				# Exponential delay before reaching step 2
				delay = random.expovariate(1.0 / mean_delay)
				t2 = t1 + delay
				step2_times.append(t2)

	A1 = [0] * num_minutes
	A2 = [0] * num_minutes

	for t in step1_times:
		m = int(t)
		if 0 <= m < num_minutes:
			A1[m] += 1

	for t in step2_times:
		m = int(t)
		if 0 <= m < num_minutes:
			A2[m] += 1

	T_series = []
	for m in range(num_minutes):
		if A1[m] > 0:
			T_series.append(A2[m] / A1[m])
		else:
			T_series.append(float("nan"))

	return T_series

def plot8_timing_noise(p_success: float, filename: str = "images/plot8.png") -> None:
	"""Plot measured T1(t) in 1-minute windows at different volumes."""
	minutes = 60
	low_volume_T = simulate_windowed_T(num_users_per_minute=20, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	mid_volume_T = simulate_windowed_T(num_users_per_minute=200, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	high_volume_T = simulate_windowed_T(num_users_per_minute=2000, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	plt.figure(figsize=(8, 4))
	plt.plot(range(1, minutes + 1), low_volume_T, marker="o", linestyle="-", color="#1f77b4", alpha=0.7, label="2 users/min")
	plt.plot(range(1, minutes + 1), mid_volume_T, marker="o", linestyle="-", color="#7f7f7f", alpha=0.8, label="200 users/min")
	plt.plot(range(1, minutes + 1), high_volume_T, marker="o", linestyle="-", color="#2ca02c", alpha=0.9, label="2000 users/min")
	plt.hlines(p_success, 1, minutes, colors="black", linestyles="dotted", label="True step-1->2 probability")
	plt.title("Measured T1(t) in 1-minute windows (timing noise)")
	plt.xlabel("Minute window")
	plt.ylabel("T1(t) = A2(t)/A1(t)")
	plt.ylim(0, 1.1)
	plt.legend()
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot9_steps_effect(per_step_success: float = 0.9, max_steps: int = 20, filename: str = "images/plot9.png") -> None:
	"""Plot end-to-end conversion vs number of steps for a fixed T."""
	steps = list(range(1, max_steps + 1))
	conversions = [per_step_success ** n for n in steps]
	plt.figure(figsize=(8, 4))
	plt.plot(steps, conversions, color="#1f77b4")
	plt.title(f"End-to-end conversion vs number of steps (T = {per_step_success})")
	plt.xlabel("Number of steps in the flow")
	plt.ylabel("Overall conversion C")
	plt.ylim(0, 1.05)
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


def plot_window_volume_consistency(filename: str = "images/plot13.png") -> None:
	"""Illustrate consistent vs inconsistent per-step request volumes in one window.

	We construct two synthetic examples of A_i(t) for a single time window:
	- a "good" window where each step sees roughly similar volume
	- a clearly "bad" window where some steps have wildly different counts.
	"""
	labels = ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
	good_counts = [100, 100, 100, 100, 100]
	bad_counts = [100, 10_000, 100, 500_000, 100]
	positions = range(len(labels))
	width = 0.35
	plt.figure(figsize=(8, 4))
	plt.bar([p - width / 2 for p in positions], good_counts, width=width, label="Good window", color="#1f77b4")
	plt.bar([p + width / 2 for p in positions], bad_counts, width=width, label="Bad window", color="#7f7f7f")
	plt.xticks(list(positions), labels)
	plt.yscale("log")
	plt.title("Per-step request volume in a single time window")
	plt.ylabel("Requests (log scale)")
	plt.legend()
	plt.tight_layout()
	plt.savefig(filename)
	plt.close()


if __name__ == "__main__":
	os.makedirs("images", exist_ok=True)

	# Deterministic example flows
	normal_scenario = FlowScenario(
		name="Normal T2=0.9",
		A1=1000,
		transitions=[0.9, 0.9, 0.9, 1.0],
		max_retries=0,
	)

	drop_scenario = FlowScenario(
		name="Drop T2=0.2",
		A1=1000,
		transitions=[0.9, 0.2, 0.9, 1.0],
		max_retries=0,
	)
	# Plots 1-5: FlowScenario comparisons
	plot1_arrivals(normal_scenario, drop_scenario)
	plot2_arrivals(normal_scenario, drop_scenario)
	plot3_arrivals_comparison(normal_scenario, drop_scenario)
	plot4_transition_ratios(normal_scenario, drop_scenario)
	plot5_conversion(normal_scenario, drop_scenario)

	# Simulations for time-series plots (C(t) with control limits)
	base_transitions = [0.9, 0.9, 0.9, 1.0]

	# Base-only scenarios at different volumes (no extra jitter)
	base_low = FlowScenario(name="Base 0.9, 100 req", A1=100, transitions=base_transitions)
	base_mid = FlowScenario(name="Base 0.9, 10k req", A1=10_000, transitions=base_transitions)
	base_high = FlowScenario(name="Base 0.9, 1M req", A1=1_000_000, transitions=base_transitions)

	sim_base_low = SimulationScenario(
		name="Base, 100 req",
		base=base_low,
		base_length=40,
		test=base_low,
		test_length=0,
		jitter=0.0,
	)
	sim_base_mid = SimulationScenario(
		name="Base, 10k req",
		base=base_mid,
		base_length=40,
		test=base_mid,
		test_length=0,
		jitter=0.0,
	)
	sim_base_high = SimulationScenario(
		name="Base, 1M req",
		base=base_high,
		base_length=40,
		test=base_high,
		test_length=0,
		jitter=0.0,
	)

	# Same base, but with additional per-window jitter on each T_i
	sim_base_low_jitter = SimulationScenario(
		name="Base, 100 req, jitter 0.1",
		base=base_low,
		base_length=40,
		test=base_low,
		test_length=0,
		jitter=0.1,
	)
	sim_base_high_jitter = SimulationScenario(
		name="Base, 1M req, jitter 0.1",
		base=base_high,
		base_length=40,
		test=base_high,
		test_length=0,
		jitter=0.1,
	)

	# Test-failure scenarios: T2 success drops to 0.3 (70% failure) in the test phase
	test_fail_low = FlowScenario(name="Fail T2=0.3, 100 req", A1=100, transitions=[0.9, 0.3, 0.9, 1.0])
	test_fail_high = FlowScenario(name="Fail T2=0.3, 1M req", A1=1_000_000, transitions=[0.9, 0.3, 0.9, 1.0])

	sim_fail_low = SimulationScenario(
		name="Failure in T2, 100 req",
		base=base_low,
		base_length=40,
		test=test_fail_low,
		test_length=40,
		jitter=0.0,
	)
	sim_fail_high = SimulationScenario(
		name="Failure in T2, 1M req",
		base=base_high,
		base_length=40,
		test=test_fail_high,
		test_length=40,
		jitter=0.0,
	)

	# Generate C(t) control-chart examples (titles use plain ASCII only)
	plot_C_with_limits(
		sim_base_low,
		filename="images/plot6.png",
		title="C(t) with control limits - base, 100 requests/window",
	)
	plot_C_with_limits(
		sim_base_mid,
		filename="images/plot7.png",
		title="C(t) with control limits - base, 10k requests/window",
	)
	plot_C_with_limits(
		sim_base_high,
		filename="images/plot14.png",
		title="C(t) with control limits - base, 1M requests/window",
	)
	plot_C_with_limits(
		sim_base_low_jitter,
		filename="images/plot9.png",
		title="C(t) with control limits - base, 100 requests/window, jitter 0.1",
	)
	plot_C_with_limits(
		sim_base_high_jitter,
		filename="images/plot10.png",
		title="C(t) with control limits - base, 1M requests/window, jitter 0.1",
	)
	plot_C_with_limits(
		sim_fail_low,
		filename="images/plot11.png",
		title="C(t) with control limits - failure in T2, 100 requests/window",
		highlight_test_phase=True,
	)
	plot_C_with_limits(
		sim_fail_high,
		filename="images/plot12.png",
		title="C(t) with control limits - failure in T2, 1M requests/window",
		highlight_test_phase=True,
	)

	# Optional extra plots (not all are used in the README)
	# Timing noise for a single transition T1(t)
	plot8_timing_noise(p_success=normal_scenario.transitions[1])
	# Effect of adding more steps
	plot9_steps_effect(filename="images/plot15.png")
	# Per-step request volume consistency in one window
	plot_window_volume_consistency()
