#!/usr/bin/env python3
"""
Impedance frequency sweep tool.

Configures the Digilent impedance analyzer, runs a log-spaced sweep from
f_start to f_stop, saves the results to CSV, optionally plots a two-panel
Bode-style chart (|Z| and Phase vs frequency), and writes a Markdown report
with DUT classification.

Usage:
    python impedance_sweep.py --fstart 100 --fstop 1e6 --steps 100 \\
        --amplitude 0.5 --probe-r 1000 --out results/sweep

    # Result files:
    #   results/sweep.csv
    #   results/sweep.png   (if matplotlib is available)
    #   results/sweep.md
"""

import argparse
import csv
import json
import math
import pathlib
import sys
import urllib.request
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def post(base, path, body):
    return _call(f"{base}{path}", method="POST", body=body)


def get(base, path):
    return _call(f"{base}{path}")


# ---------------------------------------------------------------------------
# DUT classifier
# ---------------------------------------------------------------------------

def classify_dut(frequencies, impedances, phases):
    """
    Classify the DUT from impedance magnitude and phase data.

    Returns a dict with keys: type, description, estimated_value, unit.
    """
    if len(frequencies) < 3:
        return {"type": "unknown", "description": "Too few data points", "estimated_value": None, "unit": None}

    # Mid-band statistics
    mid = len(frequencies) // 2
    z_mid = impedances[mid]
    ph_mid = phases[mid]

    # Slope of log|Z| vs log(f): resistor≈0, capacitor≈-1, inductor≈+1
    log_f = [math.log10(f) for f in frequencies]
    log_z = [math.log10(max(abs(z), 1e-12)) for z in impedances]

    n = len(log_f)
    sum_x = sum(log_f)
    sum_y = sum(log_z)
    sum_xy = sum(log_f[i] * log_z[i] for i in range(n))
    sum_x2 = sum(x * x for x in log_f)
    denom = n * sum_x2 - sum_x ** 2
    slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0.0

    avg_phase = sum(phases) / len(phases)

    if abs(slope) < 0.15 and abs(avg_phase) < 15:
        # Resistor
        r_est = sum(impedances) / len(impedances)
        return {
            "type": "resistor",
            "description": f"Resistive DUT — flat impedance, near-zero phase",
            "estimated_value": round(r_est, 2),
            "unit": "Ω",
        }
    elif slope < -0.7 and avg_phase < -45:
        # Capacitor: Z = 1/(2πfC) → C = 1/(2πf|Z|) at mid-band
        f_mid = frequencies[mid]
        c_est = 1.0 / (2 * math.pi * f_mid * z_mid)
        unit = "F"
        val = c_est
        if c_est < 1e-9:
            val, unit = c_est * 1e12, "pF"
        elif c_est < 1e-6:
            val, unit = c_est * 1e9, "nF"
        elif c_est < 1e-3:
            val, unit = c_est * 1e6, "µF"
        return {
            "type": "capacitor",
            "description": f"Capacitive DUT — impedance decreases with frequency, phase ≈ -90°",
            "estimated_value": round(val, 4),
            "unit": unit,
        }
    elif slope > 0.7 and avg_phase > 45:
        # Inductor: Z = 2πfL → L = Z/(2πf) at mid-band
        f_mid = frequencies[mid]
        l_est = z_mid / (2 * math.pi * f_mid)
        unit = "H"
        val = l_est
        if l_est < 1e-6:
            val, unit = l_est * 1e9, "nH"
        elif l_est < 1e-3:
            val, unit = l_est * 1e6, "µH"
        elif l_est < 1.0:
            val, unit = l_est * 1e3, "mH"
        return {
            "type": "inductor",
            "description": f"Inductive DUT — impedance increases with frequency, phase ≈ +90°",
            "estimated_value": round(val, 4),
            "unit": unit,
        }
    elif slope < -0.3 and avg_phase > -45:
        return {
            "type": "rc_network",
            "description": "RC network or lossy capacitor — mixed resistive/capacitive",
            "estimated_value": None,
            "unit": None,
        }
    elif slope > 0.3 and avg_phase < 45:
        return {
            "type": "rl_network",
            "description": "RL network or lossy inductor — mixed resistive/inductive",
            "estimated_value": None,
            "unit": None,
        }
    else:
        return {
            "type": "complex",
            "description": "Complex impedance — resonant network or active component",
            "estimated_value": None,
            "unit": None,
        }


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(out_path: pathlib.Path, frequencies, measurements):
    fieldnames = ["frequency_hz"] + list(measurements.keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        n = len(frequencies)
        for i in range(n):
            row = {"frequency_hz": frequencies[i]}
            for m, vals in measurements.items():
                row[m] = vals[i] if i < len(vals) else ""
            writer.writerow(row)
    print(f"  CSV saved: {out_path}")


# ---------------------------------------------------------------------------
# Plotter
# ---------------------------------------------------------------------------

def plot_sweep(out_path: pathlib.Path, frequencies, impedances, phases, dut):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available — skipping plot")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    fig.suptitle(f"Impedance Sweep — {dut['type'].title()}", fontsize=14)

    # Upper panel: |Z| in dB re 1Ω
    z_db = [20 * math.log10(max(z, 1e-12)) for z in impedances]
    ax1.semilogx(frequencies, z_db, "b-", linewidth=1.5)
    ax1.set_ylabel("|Z| (dBΩ)")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.set_title("|Z| vs Frequency")

    # Lower panel: phase
    ax2.semilogx(frequencies, phases, "r-", linewidth=1.5)
    ax2.set_ylabel("Phase (°)")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylim(-100, 100)
    ax2.axhline(0, color="k", linewidth=0.5, linestyle="--")
    ax2.grid(True, which="both", alpha=0.3)
    ax2.set_title("Phase vs Frequency")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved: {out_path}")


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_report(out_path: pathlib.Path, args, device_name, dut, frequencies, measurements, png_path=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(frequencies)

    z_vals = measurements.get("Impedance", [])
    ph_vals = measurements.get("ImpedancePhase", [])
    z_min = min(z_vals) if z_vals else 0
    z_max = max(z_vals) if z_vals else 0
    ph_min = min(ph_vals) if ph_vals else 0
    ph_max = max(ph_vals) if ph_vals else 0

    val_str = ""
    if dut.get("estimated_value") is not None:
        val_str = f"\n- **Estimated value:** {dut['estimated_value']} {dut['unit']}"

    lines = [
        f"# Impedance Sweep Report",
        f"",
        f"**Generated:** {ts}  ",
        f"**Device:** {device_name}  ",
        f"**Frequency range:** {args.fstart:.1f} Hz – {args.fstop:.1f} Hz  ",
        f"**Steps:** {n}  ",
        f"**Probe resistance:** {args.probe_r:.0f} Ω  ",
        f"**Excitation amplitude:** {args.amplitude:.3f} V  ",
        f"",
        f"## DUT Classification",
        f"",
        f"- **Type:** {dut['type']}",
        f"- **Description:** {dut['description']}",
        val_str,
        f"",
        f"## Key Metrics",
        f"",
        f"| Metric | Min | Max |",
        f"|--------|-----|-----|",
        f"| \|Z\| (Ω) | {z_min:.4g} | {z_max:.4g} |",
        f"| Phase (°) | {ph_min:.1f} | {ph_max:.1f} |",
        f"",
    ]

    if png_path and png_path.exists():
        lines += [
            f"## Bode Plot",
            f"",
            f"![Impedance Sweep]({png_path.name})",
            f"",
        ]

    lines += [
        f"## Data",
        f"",
        f"Full sweep data saved to `{out_path.stem}.csv` ({n} rows).",
        f"",
        f"Measurements: {', '.join(measurements.keys())}",
        f"",
        f"---",
        f"*Generated by impedance_sweep.py*",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Report saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Digilent impedance analyzer frequency sweep"
    )
    parser.add_argument("--base", default="http://localhost:8765",
                        help="Local server base URL (default: http://localhost:8765)")
    parser.add_argument("--fstart", type=float, default=100.0,
                        help="Start frequency Hz (default: 100)")
    parser.add_argument("--fstop", type=float, default=1_000_000.0,
                        help="Stop frequency Hz (default: 1000000)")
    parser.add_argument("--steps", type=int, default=100,
                        help="Number of frequency steps (default: 100)")
    parser.add_argument("--amplitude", type=float, default=0.5,
                        help="Excitation amplitude V (default: 0.5)")
    parser.add_argument("--offset", type=float, default=0.0,
                        help="DC offset V (default: 0.0)")
    parser.add_argument("--probe-r", type=float, default=1000.0,
                        help="Probe resistance Ω (default: 1000)")
    parser.add_argument("--probe-c", type=float, default=0.0,
                        help="Probe parasitic capacitance F (default: 0)")
    parser.add_argument("--periods", type=int, default=16,
                        help="Minimum measurement periods (default: 16)")
    parser.add_argument("--out", default="impedance_sweep",
                        help="Output filename stem (default: impedance_sweep)")
    parser.add_argument("--measurements", nargs="+",
                        default=["Impedance", "ImpedancePhase", "Resistance", "Reactance"],
                        help="Measurements to record")
    args = parser.parse_args()

    out_stem = pathlib.Path(args.out)
    out_stem.parent.mkdir(parents=True, exist_ok=True)

    # Get device info
    try:
        status = get(args.base, "/api/digilent/status")
        device_name = status.get("device_name") or "unknown"
    except Exception:
        device_name = "unknown"

    print(f"Impedance sweep: {args.fstart:.1f} Hz → {args.fstop:.1f} Hz, {args.steps} steps")
    print(f"Device: {device_name}")
    print(f"Amplitude: {args.amplitude} V, Probe R: {args.probe_r} Ω")

    # Run sweep
    try:
        resp = post(args.base, "/api/digilent/impedance/sweep", {
            "f_start_hz": args.fstart,
            "f_stop_hz": args.fstop,
            "steps": args.steps,
            "amplitude_v": args.amplitude,
            "offset_v": args.offset,
            "probe_resistance_ohm": args.probe_r,
            "probe_capacitance_f": args.probe_c,
            "min_periods": args.periods,
            "measurements": args.measurements,
        })
    except Exception as exc:
        print(f"ERROR: sweep failed — {exc}", file=sys.stderr)
        sys.exit(1)

    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error', {}).get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    frequencies = resp["frequencies"]
    measurements = resp["measurements"]
    print(f"  Sweep complete: {len(frequencies)} points")

    # Classify DUT
    z_vals = measurements.get("Impedance", [])
    ph_vals = measurements.get("ImpedancePhase", [])
    dut = classify_dut(frequencies, z_vals, ph_vals)
    print(f"  DUT: {dut['type']} — {dut['description']}")
    if dut.get("estimated_value") is not None:
        print(f"  Estimated: {dut['estimated_value']} {dut['unit']}")

    # Write outputs
    csv_path = out_stem.with_suffix(".csv")
    png_path = out_stem.with_suffix(".png")
    md_path = out_stem.with_suffix(".md")

    write_csv(csv_path, frequencies, measurements)
    plot_sweep(png_path, frequencies, z_vals, ph_vals, dut)
    write_report(md_path, args, device_name, dut, frequencies, measurements, png_path)

    print("Done.")


if __name__ == "__main__":
    main()
