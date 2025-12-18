import matplotlib.pyplot as plt
import os
import random

# Deterministic, simple example
# Scenario 1: All transitions are high
A1 = 1000
T1 = 0.9
T2 = 0.9
T3 = 0.9
T4 = 1.0
A2 = A1 * T1
A3 = A2 * T2
A4 = A3 * T3
A5 = A4 * T4
C1 = T1 * T2 * T3 * T4

# Scenario 2: T2 drops (A/B test impact on step 2 → 3)
T2_drop = 0.2
A2_drop = A1 * T1
A3_drop = A2_drop * T2_drop
A4_drop = A3_drop * T3
A5_drop = A4_drop * T4
C2 = T1 * T2_drop * T3 * T4

os.makedirs("images", exist_ok=True)

labels = ["Step 1", "Step 2", "Step 3", "Step 4", "Success"]
normal = [A1, A2, A3, A4, A5]
drop = [A1, A2_drop, A3_drop, A4_drop, A5_drop]

# 1) Arrivals per step: normal only
plt.figure(figsize=(7, 4))
plt.bar(labels, normal, color="#1f77b4")  # blue
plt.title("Arrivals per Step: Normal flow")
plt.ylabel("Users")
plt.tight_layout()
plt.savefig("images/plot1.png")
plt.close()

# 2) Arrivals per step: T2 drop only
plt.figure(figsize=(7, 4))
plt.bar(labels, drop, color="#7f7f7f")  # gray
plt.title("Arrivals per Step: T2 drop flow")
plt.ylabel("Users")
plt.tight_layout()
plt.savefig("images/plot2.png")
plt.close()

# 3) Arrivals per step: normal vs drop (combined)
plt.figure(figsize=(7, 4))
plt.bar(labels, normal, alpha=0.7, label="Normal T2=0.9", color="#1f77b4")
plt.bar(labels, drop, alpha=0.7, label="Drop T2=0.2", color="#7f7f7f")
plt.title("Arrivals per Step: Normal vs Drop in T2")
plt.ylabel("Users")
plt.legend()
plt.tight_layout()
plt.savefig("images/plot3.png")
plt.close()

# 4) Transition ratios: grouped bars
ratio_labels = ["T1", "T2", "T3", "T4"]
normal_ratios = [T1, T2, T3, T4]
drop_ratios = [T1, T2_drop, T3, T4]
positions = list(range(len(ratio_labels)))
width = 0.35

plt.figure(figsize=(6, 4))
plt.bar([p - width / 2 for p in positions], normal_ratios, width=width, label="Normal", color="#1f77b4")
plt.bar([p + width / 2 for p in positions], drop_ratios, width=width, label="Drop T2", color="#7f7f7f")
plt.xticks(positions, ratio_labels)
plt.title("Transition Ratios: Normal vs Drop in T2")
plt.ylim(0, 1)
plt.legend()
plt.tight_layout()
plt.savefig("images/plot4.png")
plt.close()

# 5) End-to-end conversion: normal vs T2 drop
plt.figure(figsize=(4, 4))
plt.bar(["Normal", "Drop T2"], [C1, C2], color=["#1f77b4", "#7f7f7f"])
plt.title("End-to-End Conversion (C)")
plt.ylabel("Conversion Ratio")
plt.ylim(0, 1)
plt.tight_layout()
plt.savefig("images/plot5.png")
plt.close()

# 6) Time series of C(t) across windows (SPC-style)
windows = list(range(1, 21))
C_series = []

for idx, _ in enumerate(windows, start=1):
	# Stable "good" behavior for T1, T3, T4 around 0.9-1.0
	t1 = random.uniform(0.9, 1.0)
	t3 = random.uniform(0.9, 1.0)
	t4 = random.uniform(0.9, 1.0)

	if idx <= 10:
		# Before experiment: T2 also healthy 0.9-1.0
		t2 = random.uniform(0.95, 1.0)
	else:
		# After experiment: T2 slightly degraded, between 0.7 and 1.0
		t2 = random.uniform(0.2, 0.5)

	C_series.append(t1 * t2 * t3 * t4)

plt.figure(figsize=(8, 4))
plt.plot(windows, C_series, marker="o", label="C(t)", color="#1f77b4")
plt.axvline(10.5, color="gray", linestyle="--", label="T2 change")
plt.hlines(C1, 1, 20, colors="#7f7f7f", linestyles="dotted", label="Baseline C1")
plt.title("End-to-End Conversion C(t) over time windows")
plt.xlabel("Time window")
plt.ylabel("Conversion Ratio C(t)")
plt.ylim(0, 1)
plt.legend()
plt.tight_layout()
plt.savefig("images/plot6.png")
plt.close()

# 7) Time series of C(t) with SPC control limits
# Use only the stable part (first 10 windows) to estimate limits
stable_C = C_series[:10]
if len(stable_C) >= 2:
	mean_C = sum(stable_C) / len(stable_C)
	moving_ranges = [abs(stable_C[i] - stable_C[i - 1]) for i in range(1, len(stable_C))]
	mr_bar = sum(moving_ranges) / len(moving_ranges)
	k = 2.66  # SPC constant for individuals chart
	ucl = mean_C + k * mr_bar
	lcl = mean_C - k * mr_bar
	# Clamp to [0, 1]
	ucl = min(1.0, ucl)
	lcl = max(0.0, lcl)

	plt.figure(figsize=(8, 4))
	plt.plot(windows, C_series, marker="o", color="#1f77b4", label="C(t)")
	plt.hlines(mean_C, 1, len(windows), colors="#1f77b4", linestyles="dashed", label="Average C (stable)")
	plt.hlines(ucl, 1, len(windows), colors="#7f7f7f", linestyles="dotted", label="Upper limit (stable)")
	plt.hlines(lcl, 1, len(windows), colors="#7f7f7f", linestyles="dotted", label="Lower limit (stable)")
	plt.title("End-to-End Conversion C(t) with control limits")
	plt.xlabel("Time window")
	plt.ylabel("Conversion Ratio C(t)")
	plt.ylim(0, 1)
	plt.legend()
	plt.tight_layout()
	plt.savefig("images/plot7.png")
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


# 8) Time-window noise vs funnels
minutes = 60
low_volume_T = simulate_windowed_T(num_users_per_minute=2, num_minutes=minutes, p_success=T2, mean_delay=1.0)
mid_volume_T = simulate_windowed_T(num_users_per_minute=200, num_minutes=minutes, p_success=T2, mean_delay=1.0)
high_volume_T = simulate_windowed_T(num_users_per_minute=2000, num_minutes=minutes, p_success=T2, mean_delay=1.0)

plt.figure(figsize=(8, 4))
plt.plot(range(1, minutes + 1), low_volume_T, marker="o", linestyle="-", color="#1f77b4", alpha=0.7, label="2 users/min")
plt.plot(range(1, minutes + 1), mid_volume_T, marker="o", linestyle="-", color="#7f7f7f", alpha=0.8, label="200 users/min")
plt.plot(range(1, minutes + 1), high_volume_T, marker="o", linestyle="-", color="#2ca02c", alpha=0.9, label="2000 users/min")
plt.hlines(T2, 1, minutes, colors="black", linestyles="dotted", label="True step-1→2 probability")
plt.title("Measured T1(t) in 1-minute windows (timing noise)")
plt.xlabel("Minute window")
plt.ylabel("T1(t) = A2(t)/A1(t)")
plt.ylim(0, 1.1)
plt.legend()
plt.tight_layout()
plt.savefig("images/plot8.png")
plt.close()

# 9) Effect of adding more steps (constant per-step success)
max_steps = 20
per_step_success = 0.9
steps = list(range(1, max_steps + 1))
conversions = [per_step_success ** n for n in steps]

plt.figure(figsize=(8, 4))
plt.plot(steps, conversions, color="#1f77b4")
plt.title("End-to-end conversion vs number of steps (T = 0.9)")
plt.xlabel("Number of steps in the flow")
plt.ylabel("Overall conversion C = 0.9^n")
plt.ylim(0, 1.05)
plt.tight_layout()
plt.savefig("images/plot9.png")
plt.close()

# Print math for clarity (optional, not in plot)
print(f"Normal: C = {T1} * {T2} * {T3} * {T4} = {C1:.2f}")
print(f"Drop:   C = {T1} * {T2_drop} * {T3} * {T4} = {C2:.2f}")
