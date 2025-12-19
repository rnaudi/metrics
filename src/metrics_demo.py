import matplotlib.pyplot as plt
import numpy as np
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
	
	# Use custom labels for OAuth2 if detected
	if "OAuth2" in flow_a.name or "Device" in flow_a.name:
		labels = ["Device\nAuth\nRequest", "Verification\nURL Visit", "Authorization\nGrant", "Token\nRetrieval", "Token\nValidation"]
	else:
		labels = [f"Step {i + 1}" for i in range(len(arrivals_a))]
	
	plt.figure(figsize=(10, 5))
	bars = plt.bar(labels, arrivals_a, color="#2ca02c", alpha=0.8, edgecolor="black", linewidth=0.5)
	# Add value labels on bars
	for bar in bars:
		height = bar.get_height()
		plt.text(bar.get_x() + bar.get_width()/2., height,
				f'{int(height)}',
				ha='center', va='bottom', fontsize=9)
	
	title = flow_a.name if "OAuth2" in flow_a.name else "Healthy Flow: Per-Step Request Arrivals"
	plt.title(title, fontsize=12, fontweight="bold")
	plt.ylabel("Number of requests", fontsize=11)
	plt.xlabel("Flow step", fontsize=11)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot2_arrivals(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot2.png") -> None:
	"""Plot arrivals per step for the second scenario (flow_b)."""
	arrivals_b = flow_b.arrivals
	
	# Use custom labels for OAuth2 if detected
	if "OAuth2" in flow_b.name or "Device" in flow_b.name:
		labels = ["Device\nAuth\nRequest", "Verification\nURL Visit", "Authorization\nGrant", "Token\nRetrieval", "Token\nValidation"]
	else:
		labels = [f"Step {i + 1}" for i in range(len(arrivals_b))]
	
	plt.figure(figsize=(10, 5))
	bars = plt.bar(labels, arrivals_b, color="#d62728", alpha=0.8, edgecolor="black", linewidth=0.5)
	# Add value labels on bars
	for bar in bars:
		height = bar.get_height()
		plt.text(bar.get_x() + bar.get_width()/2., height,
				f'{int(height)}',
				ha='center', va='bottom', fontsize=9)
	
	title = flow_b.name if "OAuth2" in flow_b.name else "Broken Flow: Step 2 Failure (T2=0.2)"
	plt.title(title, fontsize=12, fontweight="bold")
	plt.ylabel("Number of requests", fontsize=11)
	plt.xlabel("Flow step", fontsize=11)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot3_arrivals_comparison(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot3.png") -> None:
	"""Plot arrivals per step for both scenarios on the same chart."""
	arrivals_a = flow_a.arrivals
	arrivals_b = flow_b.arrivals
	if len(arrivals_a) != len(arrivals_b):
		raise ValueError("Flow scenarios must have the same number of steps")
	labels = [f"Step {i + 1}" for i in range(len(arrivals_a))]
	positions = range(len(labels))
	width = 0.35
	plt.figure(figsize=(10, 5))
	plt.bar([p - width/2 for p in positions], arrivals_a, width=width, label="Healthy (T2=0.9)", color="#2ca02c", alpha=0.8, edgecolor="black", linewidth=0.5)
	plt.bar([p + width/2 for p in positions], arrivals_b, width=width, label="Broken (T2=0.2)", color="#d62728", alpha=0.8, edgecolor="black", linewidth=0.5)
	plt.xticks(list(positions), labels, fontsize=10)
	plt.title("Side-by-Side: Healthy vs. Broken Flow", fontsize=12, fontweight="bold")
	plt.ylabel("Number of requests", fontsize=11)
	plt.xlabel("Flow step", fontsize=11)
	plt.legend(fontsize=10)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot4_transition_ratios(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot4.png") -> None:
	"""Plot transition ratios T_i for both scenarios as grouped bars."""
	if len(flow_a.transitions) != len(flow_b.transitions):
		raise ValueError("Flow scenarios must have the same number of transitions")
	ratio_labels = [f"T{i + 1}" for i in range(len(flow_a.transitions))]
	positions = list(range(len(ratio_labels)))
	width = 0.35
	plt.figure(figsize=(8, 5))
	bars1 = plt.bar([p - width / 2 for p in positions], flow_a.transitions, width=width, label="Healthy", color="#2ca02c", alpha=0.8, edgecolor="black", linewidth=0.5)
	bars2 = plt.bar([p + width / 2 for p in positions], flow_b.transitions, width=width, label="Broken", color="#d62728", alpha=0.8, edgecolor="black", linewidth=0.5)
	
	# Add value labels
	for bars in [bars1, bars2]:
		for bar in bars:
			height = bar.get_height()
			plt.text(bar.get_x() + bar.get_width()/2., height + 0.02,
					f'{height:.1f}',
					ha='center', va='bottom', fontsize=8)
	
	plt.xticks(positions, ratio_labels, fontsize=10)
	plt.title("Per-Step Transition Ratios: Where Did It Break?", fontsize=12, fontweight="bold")
	plt.ylabel("Transition ratio (0-1)", fontsize=11)
	plt.xlabel("Transition step", fontsize=11)
	plt.ylim(0, 1.1)
	plt.legend(fontsize=10)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot5_conversion(flow_a: FlowScenario, flow_b: FlowScenario, filename: str = "images/plot5.png") -> None:
	"""Plot end-to-end conversion C for both scenarios."""
	C1 = flow_a.conversion
	C2 = flow_b.conversion
	plt.figure(figsize=(7, 5))
	bars = plt.bar(["Healthy Flow", "Broken Flow"], [C1, C2], color=["#2ca02c", "#d62728"], alpha=0.8, edgecolor="black", linewidth=1)
	
	# Add value labels
	for bar in bars:
		height = bar.get_height()
		plt.text(bar.get_x() + bar.get_width()/2., height + 0.02,
				f'{height:.1%}',
				ha='center', va='bottom', fontsize=11, fontweight="bold")
	
	# Add reference line at 70% SLO
	plt.axhline(y=0.70, color='black', linestyle='--', linewidth=1, alpha=0.5, label="Example SLO (70%)")
	
	plt.title("End-to-End Conversion: Your Flow SLI", fontsize=12, fontweight="bold")
	plt.ylabel("Conversion ratio C(t)", fontsize=11)
	plt.ylim(0, 1)
	plt.legend(fontsize=9)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
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


@dataclass
class SeasonalSimulation:
	"""Simulate C(t) with seasonal/diurnal volume patterns.
	
	Volume varies sinusoidally over the day (low at night, peak during business hours).
	Useful for demonstrating how control limits adapt to realistic traffic patterns.
	"""
	name: str
	base: FlowScenario
	base_length: int
	test: FlowScenario | None
	test_length: int
	min_volume: int  # Minimum A1 (night)
	max_volume: int  # Maximum A1 (peak hours)
	jitter: float = 0.05
	
	def simulate_C_series(self) -> List[float]:
		"""Return C(t) series with seasonal volume variation.
		
		Volume follows: A1(t) = min + (max-min) * sin²(π*t/period)
		This creates a realistic daily pattern: low → peak → low
		Can optionally inject a flow change (test) partway through.
		"""
		series: List[float] = []
		total_windows = self.base_length + self.test_length
		period = total_windows  # One full cycle over all windows
		
		for idx in range(total_windows):
			# Sinusoidal volume pattern (0 at start/end, peak at middle)
			phase = math.pi * idx / period
			volume_factor = math.sin(phase) ** 2
			A1 = int(self.min_volume + (self.max_volume - self.min_volume) * volume_factor)
			
			# Choose flow (base or test)
			flow = self.base if idx < self.base_length else (self.test or self.base)
			
			# Simulate flow with this volume
			A_current = A1
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
	stable_C = np.array(series[:stable_windows])
	if len(stable_C) < 2:
		return None

	mean_C = np.mean(stable_C)
	moving_ranges = np.abs(np.diff(stable_C))
	mr_bar = np.mean(moving_ranges)
	k = 2.66  # SPC constant for individuals chart
	ucl = np.clip(mean_C + k * mr_bar, 0.0, 1.0)
	lcl = np.clip(mean_C - k * mr_bar, 0.0, 1.0)
	return mean_C, ucl, lcl

def compute_moving_average(series: List[float], window: int) -> List[float]:
	"""Compute simple moving average over a window."""
	arr = np.array(series)
	ma = []
	for i in range(len(arr)):
		start = max(0, i - window + 1)
		ma.append(np.mean(arr[start:i+1]))
	return ma

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
	plt.figure(figsize=(10, 5))
	
	# Add shading for test phase first (so it's in background)
	if highlight_test_phase and sim.test_length > 0:
		plt.axvspan(sim.base_length + 0.5, len(windows) + 0.5, color="#ffcccc", alpha=0.3, label="Failure injected")
	
	# Plot control limits
	plt.hlines(mean_C, 1, len(windows), colors="#1f77b4", linestyles="dashed", label=f"Mean C = {mean_C:.3f}", linewidth=2)
	plt.hlines(ucl, 1, len(windows), colors="#666666", linestyles="dotted", label=f"Control limits", linewidth=1.5)
	plt.hlines(lcl, 1, len(windows), colors="#666666", linestyles="dotted", linewidth=1.5)
	
	# Plot C(t) series
	plt.plot(windows, C_series, marker="o", markersize=4, color="#1f77b4", label="C(t)", linewidth=1.5, alpha=0.8)
	
	plt.title(title or "End-to-End Conversion C(t) with Control Limits", fontsize=12, fontweight="bold")
	plt.xlabel("Time window", fontsize=11)
	plt.ylabel("Conversion Ratio C(t)", fontsize=11)
	plt.ylim(0, 1)
	plt.grid(axis="y", alpha=0.3)
	plt.legend(loc="best", fontsize=9)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()

def plot_C_with_moving_average_limits(
	sim: SimulationScenario,
	ma_window: int,
	filename: str = "images/plot15.png",
	title: str | None = None,
	highlight_test_phase: bool = False,
) -> None:
	"""Plot C(t) with control limits computed from moving average.
	
	Shows both raw C(t) and smoothed moving average, with control limits
	computed from the MA series to demonstrate how smoothing helps with jitter.
	"""
	C_series = sim.simulate_C_series()
	windows = list(range(1, len(C_series) + 1))
	
	# Compute moving average
	ma_series = compute_moving_average(C_series, ma_window)
	
	# Compute control limits from the moving average (using stable period)
	limits = compute_individuals_control_limits(ma_series, stable_windows=sim.base_length)
	if limits is None:
		return
	mean_C, ucl, lcl = limits
	
	plt.figure(figsize=(10, 5))
	
	# Add shading for test phase first (so it's in background)
	if highlight_test_phase and sim.test_length > 0:
		plt.axvspan(sim.base_length + 0.5, len(windows) + 0.5, color="#ffcccc", alpha=0.3, label="Degradation injected")
	
	# Plot raw C(t) with transparency
	plt.plot(windows, C_series, marker="o", markersize=3, color="#cccccc", 
			 label="Raw C(t)", linewidth=1, alpha=0.5, linestyle="-")
	
	# Plot moving average
	plt.plot(windows, ma_series, marker="o", markersize=4, color="#1f77b4", 
			 label=f"Moving avg (window={ma_window})", linewidth=2, alpha=0.9)
	
	# Plot control limits (computed from MA)
	plt.hlines(mean_C, 1, len(windows), colors="#1f77b4", linestyles="dashed", 
			   label=f"Mean MA = {mean_C:.3f}", linewidth=2)
	plt.hlines(ucl, 1, len(windows), colors="#666666", linestyles="dotted", 
			   label=f"Control limits (from MA)", linewidth=1.5)
	plt.hlines(lcl, 1, len(windows), colors="#666666", linestyles="dotted", linewidth=1.5)
	
	plt.title(title or "C(t) with Moving Average Control Limits", fontsize=12, fontweight="bold")
	plt.xlabel("Time window", fontsize=11)
	plt.ylabel("Conversion Ratio C(t)", fontsize=11)
	plt.ylim(0, 1)
	plt.grid(axis="y", alpha=0.3)
	plt.legend(loc="best", fontsize=9)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot_seasonal_volume_and_C(
	sim: SeasonalSimulation,
	ma_window: int,
	filename: str = "images/plot_seasonal.png",
	title: str | None = None,
) -> None:
	"""Plot both volume A1(t) and C(t) to show C is volume-independent.
	
	Dual-axis plot: volume on left axis, C(t) on right axis.
	Demonstrates that C(t) remains stable despite dramatic volume changes.
	"""
	# We need to re-simulate to capture volume at each step
	total_windows = sim.base_length + sim.test_length
	period = total_windows
	
	volume_series = []
	C_series = []
	
	for idx in range(total_windows):
		# Sinusoidal volume pattern
		phase = math.pi * idx / period
		volume_factor = math.sin(phase) ** 2
		A1 = int(sim.min_volume + (sim.max_volume - sim.min_volume) * volume_factor)
		volume_series.append(A1)
		
		# Choose flow
		flow = sim.base if idx < sim.base_length else (sim.test or sim.base)
		
		# Simulate C(t)
		A_current = A1
		A_initial = A_current
		if A_initial <= 0:
			C_series.append(float("nan"))
			continue
			
		for T in flow.transitions:
			low = max(0.0, T - sim.jitter)
			high = min(1.0, T + sim.jitter)
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
		C_series.append(C_t)
	
	windows = list(range(1, len(C_series) + 1))
	
	# Compute moving average of C(t)
	ma_series = compute_moving_average(C_series, ma_window)
	
	# Create figure with dual y-axes
	fig, ax1 = plt.subplots(figsize=(12, 6))
	
	# Plot volume on left axis
	ax1.set_xlabel("Time window (5-min intervals)", fontsize=11)
	ax1.set_ylabel("Volume: A1(t) requests/window", fontsize=11, color="#ff7f0e")
	ax1.fill_between(windows, volume_series, alpha=0.3, color="#ff7f0e", label="Traffic volume")
	ax1.plot(windows, volume_series, color="#ff7f0e", linewidth=2, alpha=0.8)
	ax1.tick_params(axis='y', labelcolor="#ff7f0e")
	ax1.set_ylim(0, max(volume_series) * 1.1)
	
	# Plot C(t) on right axis
	ax2 = ax1.twinx()
	ax2.set_ylabel("Conversion C(t)", fontsize=11, color="#1f77b4")
	ax2.plot(windows, C_series, marker="o", markersize=3, color="#cccccc", 
			 label="Raw C(t)", linewidth=1, alpha=0.5)
	ax2.plot(windows, ma_series, marker="o", markersize=4, color="#1f77b4", 
			 label=f"C(t) moving avg", linewidth=2.5, alpha=0.9)
	ax2.tick_params(axis='y', labelcolor="#1f77b4")
	ax2.set_ylim(0, 1)
	ax2.grid(axis="y", alpha=0.3)
	
	# Add title and legends
	plt.title(title or "Volume Changes, C(t) Stays Stable", fontsize=13, fontweight="bold", pad=20)
	
	# Combine legends
	lines1, labels1 = ax1.get_legend_handles_labels()
	lines2, labels2 = ax2.get_legend_handles_labels()
	ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
	
	fig.tight_layout()
	plt.savefig(filename, dpi=150)
	plt.close()


def plot_seasonal_C_with_ma(
	sim: SeasonalSimulation,
	ma_window: int,
	filename: str = "images/plot18.png",
	title: str | None = None,
	highlight_test_phase: bool = False,
) -> None:
	"""Plot C(t) for seasonal volume pattern with moving average control limits.
	
	Shows how control limits naturally widen/narrow as traffic volume changes
	throughout the day, demonstrating adaptive monitoring behavior.
	"""
	C_series = sim.simulate_C_series()
	windows = list(range(1, len(C_series) + 1))
	
	# Compute moving average
	ma_series = compute_moving_average(C_series, ma_window)
	
	# For seasonal data, compute rolling control limits (window-by-window)
	# Use a sliding window to compute limits that adapt to volume changes
	ucl_series = []
	lcl_series = []
	mean_series = []
	
	ma_array = np.array(ma_series)
	
	for i in range(len(ma_series)):
		# Use past 10 windows (or available) to compute current limits
		lookback = min(10, i + 1)
		window_data = ma_array[max(0, i - lookback + 1):i + 1]
		
		if len(window_data) >= 3:
			mean_val = np.mean(window_data)
			mr = np.abs(np.diff(window_data))
			if len(mr) > 0:
				mr_bar = np.mean(mr)
				sigma = mr_bar / 1.128
				ucl_val = np.clip(mean_val + 2.66 * sigma, 0.0, 1.0)
				lcl_val = np.clip(mean_val - 2.66 * sigma, 0.0, 1.0)
			else:
				ucl_val = mean_val
				lcl_val = mean_val
		else:
			mean_val = ma_series[i] if i < len(ma_series) else np.nan
			ucl_val = mean_val
			lcl_val = mean_val
			
		mean_series.append(mean_val)
		ucl_series.append(ucl_val)
		lcl_series.append(lcl_val)
	
	plt.figure(figsize=(10, 5))
	
	# Add shading for test phase first (so it's in background)
	if highlight_test_phase and sim.test_length > 0:
		plt.axvspan(sim.base_length + 0.5, len(windows) + 0.5, color="#ffcccc", alpha=0.3, label="Degradation injected")
	
	# Plot raw C(t) with transparency
	plt.plot(windows, C_series, marker="o", markersize=3, color="#cccccc", 
			 label="Raw C(t)", linewidth=1, alpha=0.5, linestyle="-")
	
	# Plot moving average
	plt.plot(windows, ma_series, marker="o", markersize=4, color="#1f77b4", 
			 label=f"Moving avg (window={ma_window})", linewidth=2, alpha=0.9)
	
	# Plot adaptive control limits
	plt.plot(windows, ucl_series, color="#666666", linestyle="dotted", 
			 label="Adaptive control limits", linewidth=1.5, alpha=0.7)
	plt.plot(windows, lcl_series, color="#666666", linestyle="dotted", linewidth=1.5, alpha=0.7)
	plt.plot(windows, mean_series, color="#1f77b4", linestyle="dashed", 
			 label="Rolling mean", linewidth=2, alpha=0.5)
	
	plt.title(title or "C(t) with Seasonal Volume Pattern", fontsize=12, fontweight="bold")
	plt.xlabel("Time window (5-min intervals)", fontsize=11)
	plt.ylabel("Conversion Ratio C(t)", fontsize=11)
	plt.ylim(0, 1)
	plt.grid(axis="y", alpha=0.3)
	plt.legend(loc="best", fontsize=9)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
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
			# Cap at 1.0 since A2 can exceed A1 due to timing effects
			# (users from previous windows completing in this window)
			T_series.append(min(1.0, A2[m] / A1[m]))
		else:
			T_series.append(float("nan"))

	return T_series

def plot8_timing_noise(p_success: float, filename: str = "images/plot8.png") -> None:
	"""Plot measured T1(t) in 1-minute windows at different volumes."""
	minutes = 60
	low_volume_T = simulate_windowed_T(num_users_per_minute=20, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	mid_volume_T = simulate_windowed_T(num_users_per_minute=200, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	high_volume_T = simulate_windowed_T(num_users_per_minute=2000, num_minutes=minutes, p_success=p_success, mean_delay=1.0)
	plt.figure(figsize=(10, 5))
	plt.plot(range(1, minutes + 1), low_volume_T, marker="o", markersize=3, linestyle="-", color="#d62728", alpha=0.7, label="20 users/min (low volume)", linewidth=1.5)
	plt.plot(range(1, minutes + 1), mid_volume_T, marker="o", markersize=3, linestyle="-", color="#ff7f0e", alpha=0.8, label="200 users/min (medium)", linewidth=1.5)
	plt.plot(range(1, minutes + 1), high_volume_T, marker="o", markersize=3, linestyle="-", color="#2ca02c", alpha=0.9, label="2000 users/min (high volume)", linewidth=1.5)
	plt.hlines(p_success, 1, minutes, colors="black", linestyles="dashed", label=f"True probability (p={p_success})", linewidth=2)
	plt.title("Impact of Volume on Timing Noise: Single Transition T1(t)", fontsize=12, fontweight="bold")
	plt.xlabel("Time window (1-minute buckets)", fontsize=11)
	plt.ylabel("Measured T1(t) = A2(t) / A1(t)", fontsize=11)
	plt.ylim(0, 1.1)
	plt.legend(loc="best", fontsize=9)
	plt.grid(axis="y", alpha=0.3)
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
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
	good_counts = [1000, 900, 810, 729, 729]  # Realistic gradual decline
	bad_counts = [1000, 10_000, 100, 500_000, 50]  # Clearly wrong
	positions = range(len(labels))
	width = 0.35
	plt.figure(figsize=(10, 5))
	plt.bar([p - width / 2 for p in positions], good_counts, width=width, label="Good: window fits user journeys", color="#2ca02c", alpha=0.8)
	plt.bar([p + width / 2 for p in positions], bad_counts, width=width, label="Bad: window too small", color="#d62728", alpha=0.8)
	plt.xticks(list(positions), labels, fontsize=10)
	plt.yscale("log")
	plt.title("Window Sizing: Good vs. Bad Per-Step Volumes", fontsize=12, fontweight="bold")
	plt.ylabel("Requests per step (log scale)", fontsize=11)
	plt.xlabel("Flow step", fontsize=11)
	plt.legend(fontsize=10)
	plt.grid(axis="y", alpha=0.3, which="both")
	plt.tight_layout()
	plt.savefig(filename, dpi=150)
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

	# Same base but with higher success rate (0.95) and jitter scenarios
	jitter_transitions = [0.95, 0.95, 0.95, 1.0]
	jitter_low = FlowScenario(name="Jitter 0.95, 100 req", A1=100, transitions=jitter_transitions)
	jitter_high = FlowScenario(name="Jitter 0.95, 1M req", A1=1_000_000, transitions=jitter_transitions)
	
	sim_base_low_jitter = SimulationScenario(
		name="Base, 100 req, jitter 0.05",
		base=jitter_low,
		base_length=40,
		test=jitter_low,
		test_length=0,
		jitter=0.05,
	)
	sim_base_high_jitter = SimulationScenario(
		name="Base, 1M req, jitter 0.05",
		base=jitter_high,
		base_length=40,
		test=jitter_high,
		test_length=0,
		jitter=0.05,
	)

	# Test-failure scenarios: T2 success drops to 0.8 (10% degradation) in the test phase
	test_fail_low = FlowScenario(name="Fail T2=0.8, 100 req", A1=100, transitions=[0.9, 0.8, 0.9, 1.0])
	test_fail_high = FlowScenario(name="Fail T2=0.8, 1M req", A1=1_000_000, transitions=[0.9, 0.8, 0.9, 1.0])

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
		title="C(t) with control limits - T=0.95, 100 requests/window, jitter 0.05",
	)
	plot_C_with_limits(
		sim_base_high_jitter,
		filename="images/plot10.png",
		title="C(t) with control limits - T=0.95, 1M requests/window, jitter 0.05",
	)
	plot_C_with_limits(
		sim_fail_low,
		filename="images/plot11.png",
		title="C(t) with control limits - T2 degrades 0.9->0.8, 100 requests/window",
		highlight_test_phase=True,
	)
	plot_C_with_limits(
		sim_fail_high,
		filename="images/plot12.png",
		title="C(t) with control limits - T2 degrades 0.9->0.8, 1M requests/window",
		highlight_test_phase=True,
	)

	# Optional extra plots (not all are used in the README)
	# Timing noise for a single transition T1(t)
	plot8_timing_noise(p_success=normal_scenario.transitions[1])
	# Per-step request volume consistency in one window
	plot_window_volume_consistency()
	
	# Moving average control limits demo (solves jitter problem)
	plot_C_with_moving_average_limits(
		sim_base_high_jitter,
		ma_window=5,
		filename="images/plot15.png",
		title="C(t) with Moving Average Control Limits - solves jitter problem",
	)
	
	# OAuth2 Device Flow Examples - Multiple scenarios with moving average limits
	
	# Baseline healthy flow
	oauth_healthy = FlowScenario(
		name="OAuth2 Healthy",
		A1=10_000,
		transitions=[0.95, 0.85, 0.98, 0.99],
		max_retries=0,
	)
	
	# Plot 15.5: Scenario 0 - Volume independence (dual-axis plot)
	sim_oauth_seasonal_demo = SeasonalSimulation(
		name="OAuth2 Seasonal Demo",
		base=oauth_healthy,
		base_length=40,
		test=None,
		test_length=0,
		min_volume=500,
		max_volume=10_000,
		jitter=0.02,
	)
	plot_seasonal_volume_and_C(
		sim_oauth_seasonal_demo,
		ma_window=5,
		filename="images/plot15_5.png",
		title="OAuth2: Volume changes 20×, C(t) remains stable",
	)
	
	# Plot 16: User behavior change - T1 drops (verification URL)
	oauth_t1_drop = FlowScenario(
		name="OAuth2 T1 Drop",
		A1=10_000,
		transitions=[0.80, 0.85, 0.98, 0.99],
		max_retries=0,
	)
	sim_oauth_t1 = SimulationScenario(
		name="OAuth2 T1 Drop",
		base=oauth_healthy,
		base_length=20,
		test=oauth_t1_drop,
		test_length=20,
		jitter=0.02,
	)
	plot_C_with_moving_average_limits(
		sim_oauth_t1,
		ma_window=5,
		filename="images/plot16.png",
		title="OAuth2: User behavior change (T1: 0.95→0.80)",
		highlight_test_phase=True,
	)
	
	# Plot 17: System behavior change with seasonal volume - T2 drops (authorization)
	oauth_t2_drop = FlowScenario(
		name="OAuth2 T2 Drop",
		A1=10_000,
		transitions=[0.95, 0.70, 0.98, 0.99],
		max_retries=0,
	)
	sim_oauth_t2_seasonal = SeasonalSimulation(
		name="OAuth2 T2 Drop Seasonal",
		base=oauth_healthy,
		base_length=20,
		test=oauth_t2_drop,
		test_length=20,
		min_volume=500,    # Night traffic
		max_volume=10_000, # Peak daytime traffic
		jitter=0.02,
	)
	plot_seasonal_C_with_ma(
		sim_oauth_t2_seasonal,
		ma_window=5,
		filename="images/plot17.png",
		title="OAuth2: System failure with seasonal traffic (T2: 0.85→0.70)",
		highlight_test_phase=True,
	)
	
	# Plot 18: Seasonal volume pattern only (no failure)
	sim_oauth_seasonal = SeasonalSimulation(
		name="OAuth2 Seasonal",
		base=oauth_healthy,
		base_length=40,
		test=None,
		test_length=0,
		min_volume=500,    # Night traffic
		max_volume=10_000, # Peak daytime traffic
		jitter=0.02,
	)
	plot_seasonal_C_with_ma(
		sim_oauth_seasonal,
		ma_window=5,
		filename="images/plot18.png",
		title="OAuth2: Seasonal volume pattern (daily cycle)",
	)
	
	# Plot 19: Polling infrastructure failure - T3 drops
	oauth_t3_drop = FlowScenario(
		name="OAuth2 T3 Drop",
		A1=10_000,
		transitions=[0.95, 0.85, 0.85, 0.99],
		max_retries=0,
	)
	sim_oauth_t3 = SimulationScenario(
		name="OAuth2 T3 Drop",
		base=oauth_healthy,
		base_length=20,
		test=oauth_t3_drop,
		test_length=20,
		jitter=0.02,
	)
	plot_C_with_moving_average_limits(
		sim_oauth_t3,
		ma_window=5,
		filename="images/plot19.png",
		title="OAuth2: Polling infrastructure failure (T3: 0.98→0.85)",
		highlight_test_phase=True,
	)
	
	# Plot 20: Token validation issues - T4 drops
	oauth_t4_drop = FlowScenario(
		name="OAuth2 T4 Drop",
		A1=10_000,
		transitions=[0.95, 0.85, 0.98, 0.90],
		max_retries=0,
	)
	sim_oauth_t4 = SimulationScenario(
		name="OAuth2 T4 Drop",
		base=oauth_healthy,
		base_length=20,
		test=oauth_t4_drop,
		test_length=20,
		jitter=0.02,
	)
	plot_C_with_moving_average_limits(
		sim_oauth_t4,
		ma_window=5,
		filename="images/plot20.png",
		title="OAuth2: Token validation issues (T4: 0.99→0.90)",
		highlight_test_phase=True,
	)
