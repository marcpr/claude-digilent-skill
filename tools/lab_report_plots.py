#!/usr/bin/env python3
"""Generate all plots for the DUT lab report."""

import json, math, pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import FancyArrowPatch

OUT = pathlib.Path("/tmp/lab")
OUT.mkdir(exist_ok=True)

# ── Sweep data ──────────────────────────────────────────────────────────────
sweep = [
    (672,    -0.00, -0.4),  (853,    -0.00, -0.5),  (1083,   -0.00, -0.6),
    (1374,   -0.00, -0.7),  (1743,   -0.00, -0.9),  (2212,   -0.00, -1.1),
    (2807,   -0.10, -1.3),  (3562,   -0.10, -1.6),  (4520,   -0.10, -1.9),
    (5736,   -0.10, -2.2),  (7279,   -0.10, -2.7),  (9237,   -0.10, -3.3),
    (11721,  -0.10, -4.2),  (14874,  -0.10, -5.3),  (18874,  -0.10, -6.8),
    (23950,  -0.20, -8.6),  (30392,  -0.20, -10.9), (38566,  -0.30, -13.8),
    (48939,  -0.50, -17.3), (62102,  -0.70, -21.6), (78805,  -1.00, -25.8),
]
freqs  = np.array([p[0] for p in sweep])
gains  = np.array([p[1] for p in sweep])
phases = np.array([p[2] for p in sweep])

FC = 159_000   # estimated cutoff

# ── Theoretical curves ───────────────────────────────────────────────────────
f_th = np.logspace(2, 6, 500)
gain_th  = 20 * np.log10(1 / np.sqrt(1 + (f_th / FC)**2))
phase_th = -np.degrees(np.arctan(f_th / FC))


# ════════════════════════════════════════════════════════════════════════════
# 1) BODE PLOT (annotated)
# ════════════════════════════════════════════════════════════════════════════
fig, (ax_g, ax_p) = plt.subplots(2, 1, figsize=(11, 7), dpi=150, sharex=True)
fig.suptitle("Bode-Diagramm — DUT (RC-Tiefpass 1. Ordnung)", fontsize=13, fontweight="bold")

# Gain
ax_g.semilogx(f_th, gain_th, "--", color="lightblue", linewidth=1.2, label="Theorie 1. Ordnung")
ax_g.semilogx(freqs, gains, "o-", color="#1f77b4", linewidth=1.8, markersize=5, label="Messung")
ax_g.axhline(-3, color="red", linestyle=":", linewidth=1, alpha=0.7)
ax_g.axvline(FC, color="red", linestyle="--", linewidth=1.2, alpha=0.8, label=f"fc ≈ {FC/1e3:.0f} kHz")
# -3 dB annotation
ax_g.annotate("−3 dB @ fc ≈ 159 kHz", xy=(FC, -3), xytext=(20000, -2.0),
    arrowprops=dict(arrowstyle="->", color="red", lw=0.9),
    fontsize=8, color="red")
ax_g.set_ylabel("Verstärkung (dB)", fontsize=10)
ax_g.set_ylim(-6, 1)
ax_g.set_yticks([0, -1, -2, -3, -4, -5, -6])
ax_g.legend(fontsize=8, loc="lower left")
ax_g.grid(True, which="both", linestyle="--", alpha=0.45)

# Phase
ax_p.semilogx(f_th, phase_th, "--", color="moccasin", linewidth=1.2, label="Theorie")
ax_p.semilogx(freqs, phases, "s-", color="#ff7f0e", linewidth=1.8, markersize=5, label="Messung")
ax_p.axhline(-45, color="red", linestyle=":", linewidth=1, alpha=0.7)
ax_p.axvline(FC, color="red", linestyle="--", linewidth=1.2, alpha=0.8)
ax_p.annotate("−45° @ fc", xy=(FC, -45), xytext=(40000, -35),
    arrowprops=dict(arrowstyle="->", color="red", lw=0.9),
    fontsize=8, color="red")
# annotate last measured point
ax_p.annotate(f"  {phases[-1]:.1f}° @ {freqs[-1]/1e3:.0f} kHz",
    xy=(freqs[-1], phases[-1]), fontsize=7.5, color="#ff7f0e", va="top")
ax_p.set_ylabel("Phase (°)", fontsize=10)
ax_p.set_xlabel("Frequenz (Hz)", fontsize=10)
ax_p.set_ylim(-100, 5)
ax_p.set_yticks([0, -15, -30, -45, -60, -75, -90])
ax_p.legend(fontsize=8, loc="lower left")
ax_p.grid(True, which="both", linestyle="--", alpha=0.45)
ax_p.xaxis.set_major_formatter(ticker.EngFormatter(unit="Hz"))

fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(OUT / "bode.png")
print("Saved: bode.png")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# 2) WAVEFORM — passband (1 kHz)
# ════════════════════════════════════════════════════════════════════════════
d = json.loads(pathlib.Path("/tmp/wave_1k.json").read_text())
w = d["waveform"]
dt = w["dt_s"]
ch = {f"ch{c['channel']}": np.array(c["y"]) for c in w["channels"]}
t = np.arange(len(ch["ch1"])) * dt * 1e3   # ms

fig, ax = plt.subplots(figsize=(11, 3.5), dpi=150)
ax.plot(t, ch["ch1"], color="#1f77b4", linewidth=1.5, label="CH1 — Eingang (W1)")
ax.plot(t, ch["ch2"], color="#ff7f0e", linewidth=1.5, label="CH2 — Ausgang (DUT)", linestyle="--")
ax.set_xlabel("Zeit (ms)", fontsize=10)
ax.set_ylabel("Spannung (V)", fontsize=10)
ax.set_title("Zeitbereich — Passband (f = 1 kHz)", fontsize=11)
ax.set_ylim(-2.0, 2.0)
ax.legend(fontsize=9)
ax.grid(True, linestyle="--", alpha=0.45)
# annotate Vpp
ax.annotate("", xy=(t[0], 1.5), xytext=(t[0], -1.5),
    arrowprops=dict(arrowstyle="<->", color="gray", lw=1.0))
ax.text(t[5], 0, " Vpp = 3.0 V", fontsize=8, color="gray", va="center")
fig.tight_layout()
fig.savefig(OUT / "wave_1k.png")
print("Saved: wave_1k.png")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# 3) WAVEFORM — near fc (79 kHz)
# ════════════════════════════════════════════════════════════════════════════
d = json.loads(pathlib.Path("/tmp/wave_79k.json").read_text())
w = d["waveform"]
dt = w["dt_s"]
ch = {f"ch{c['channel']}": np.array(c["y"]) for c in w["channels"]}
t = np.arange(len(ch["ch1"])) * dt * 1e6   # µs

# show first 4 periods ≈ 4/79kHz = 50.6 µs
mask = t <= 52
t_s, ch1_s, ch2_s = t[mask], ch["ch1"][mask], ch["ch2"][mask]

fig, ax = plt.subplots(figsize=(11, 3.5), dpi=150)
ax.plot(t_s, ch1_s, color="#1f77b4", linewidth=1.5, label="CH1 — Eingang (W1)")
ax.plot(t_s, ch2_s, color="#ff7f0e", linewidth=1.5, label="CH2 — Ausgang (DUT)", linestyle="--")

# find first positive peak of ch1 and ch2 to annotate phase shift
from scipy.signal import find_peaks as _fp
try:
    p1, _ = _fp(ch1_s, height=0.5, distance=5)
    p2, _ = _fp(ch2_s, height=0.5, distance=5)
    if len(p1) and len(p2):
        dt_phase = (t_s[p2[0]] - t_s[p1[0]])
        phase_est = dt_phase / (1e6/79000) * 360
        ax.annotate("", xy=(t_s[p2[0]], ch2_s[p2[0]]+0.15),
                    xytext=(t_s[p1[0]], ch1_s[p1[0]]+0.15),
                    arrowprops=dict(arrowstyle="<->", color="purple", lw=1.2))
        ax.text((t_s[p1[0]]+t_s[p2[0]])/2, max(ch1_s[p1[0]], ch2_s[p2[0]])+0.25,
                f"Δt ≈ {dt_phase:.1f} µs\n(φ ≈ {phase_est:.0f}°)",
                ha="center", fontsize=8, color="purple")
except Exception:
    pass

# amplitude annotation
vpp_out = float(ch2_s.max() - ch2_s.min())
vpp_in  = float(ch1_s.max() - ch1_s.min())
ax.text(0.98, 0.97,
    f"Vin  = {vpp_in:.2f} Vpp\nVout = {vpp_out:.2f} Vpp\nGain = {20*math.log10(vpp_out/vpp_in):.1f} dB",
    transform=ax.transAxes, fontsize=8, va="top", ha="right",
    bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.85))

ax.set_xlabel("Zeit (µs)", fontsize=10)
ax.set_ylabel("Spannung (V)", fontsize=10)
ax.set_title("Zeitbereich — Nahe Grenzfrequenz (f = 79 kHz)", fontsize=11)
ax.set_ylim(-2.2, 2.6)
ax.legend(fontsize=9)
ax.grid(True, linestyle="--", alpha=0.45)
fig.tight_layout()
fig.savefig(OUT / "wave_79k.png")
print("Saved: wave_79k.png")
plt.close()


# ════════════════════════════════════════════════════════════════════════════
# 4) fc ESTIMATION SCATTER PLOT
# ════════════════════════════════════════════════════════════════════════════
use = [(f, g, p) for f, g, p in sweep if f >= 7000]
fc_est = [f / math.tan(math.radians(-p)) for f, g, p in use]
f_use  = [f for f, g, p in use]

fig, ax = plt.subplots(figsize=(9, 3.5), dpi=150)
ax.semilogx(f_use, [v/1e3 for v in fc_est], "o-", color="#2ca02c",
            markersize=6, linewidth=1.4, label="fc-Schätzung aus Phase")
ax.axhline(FC/1e3, color="red", linestyle="--", linewidth=1.2,
           label=f"Mittelwert fc = {FC/1e3:.0f} kHz")
ax.fill_between([f_use[0], f_use[-1]], [FC/1e3-5]*2, [FC/1e3+5]*2,
                color="red", alpha=0.10, label="±5 kHz Band")
ax.set_xlabel("Messfrequenz (Hz)", fontsize=10)
ax.set_ylabel("Geschätzte fc (kHz)", fontsize=10)
ax.set_title("Grenzfrequenz-Schätzung: fc = f / tan(−φ)", fontsize=11)
ax.set_ylim(140, 180)
ax.legend(fontsize=8)
ax.grid(True, which="both", linestyle="--", alpha=0.45)
ax.xaxis.set_major_formatter(ticker.EngFormatter(unit="Hz"))
fig.tight_layout()
fig.savefig(OUT / "fc_estimate.png")
print("Saved: fc_estimate.png")
plt.close()

print("\nAll plots saved to /tmp/lab/")
