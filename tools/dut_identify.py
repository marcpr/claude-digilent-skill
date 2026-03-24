#!/usr/bin/env python3
"""
DUT identification via frequency sweep (Bode plot).

Sweeps W1 from start_hz to stop_hz, captures CH1 (input) and CH2 (output),
computes gain and phase at each frequency, then classifies the DUT and
produces a Bode plot + markdown report.
"""

import json
import time
import math
import pathlib
import argparse
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def post(base, path, body):
    return _call(f"{base}{path}", method="POST", body=body)


def get(base, path):
    return _call(f"{base}{path}")


# ---------------------------------------------------------------------------
# Single-frequency measurement
# ---------------------------------------------------------------------------

def measure_at(base, freq_hz, amplitude_v=1.5, sample_rate=500_000, cycles=10):
    # cap duration: enough cycles but never more than 50 ms
    duration_ms = min(50.0, max(5.0, (cycles / freq_hz) * 1000))
    # adapt sample rate so we get at least 20 samples/period
    min_rate = int(freq_hz * 20)
    actual_rate = max(min_rate, min(sample_rate, 1_000_000))

    post(base, "/api/digilent/wavegen/set", {
        "channel": 1,
        "waveform": "sine",
        "frequency_hz": freq_hz,
        "amplitude_v": amplitude_v,
        "offset_v": 0.0,
        "symmetry_percent": 50,
        "enable": True,
    })
    time.sleep(max(0.05, 3 / freq_hz))

    # free-run capture (most reliable across server versions)
    try:
        resp = post(base, "/api/digilent/scope/capture", {
            "channels": [1, 2],
            "range_v": 10.0,
            "offset_v": 0.0,
            "sample_rate_hz": actual_rate,
            "duration_ms": duration_ms,
            "trigger": {"enabled": False},
            "return_waveform": True,
        })
    except Exception as e:
        print(f"    capture error: {e}")
        return None

    if not resp.get("ok"):
        return None

    import numpy as np
    w = resp["waveform"]
    dt = w["dt_s"]
    ch_data = {f"ch{c['channel']}": np.array(c["y"]) for c in w["channels"]}

    if "ch1" not in ch_data or "ch2" not in ch_data:
        return None

    ch1, ch2 = ch_data["ch1"], ch_data["ch2"]
    n = len(ch1)
    fs = 1 / dt

    # FFT-based gain and phase at fundamental
    window = np.hanning(n)
    cg = np.sum(window) / n
    F1 = np.fft.rfft(ch1 * window)
    F2 = np.fft.rfft(ch2 * window)
    freqs = np.fft.rfftfreq(n, d=dt)

    idx = int(np.argmin(np.abs(freqs - freq_hz)))
    amp1 = (2 / (n * cg)) * abs(F1[idx])
    amp2 = (2 / (n * cg)) * abs(F2[idx])

    gain = amp2 / amp1 if amp1 > 1e-6 else 0.0
    gain_db = 20 * math.log10(gain) if gain > 1e-9 else -120.0

    phase_diff = math.degrees(math.atan2(F2[idx].imag, F2[idx].real) -
                              math.atan2(F1[idx].imag, F1[idx].real))
    phase_diff = (phase_diff + 180) % 360 - 180

    return {
        "freq_hz": freq_hz,
        "amp_in_vpk": float(amp1),
        "amp_out_vpk": float(amp2),
        "gain": float(gain),
        "gain_db": float(gain_db),
        "phase_deg": float(phase_diff),
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(points):
    import numpy as np

    freqs   = np.array([p["freq_hz"]  for p in points])
    gains   = np.array([p["gain_db"]  for p in points])
    phases  = np.array([p["phase_deg"] for p in points])

    gain_low  = float(np.mean(gains[:3]))    # low-freq average
    gain_high = float(np.mean(gains[-3:]))   # high-freq average
    gain_mid  = float(np.mean(gains[len(gains)//3 : 2*len(gains)//3]))
    gain_span = float(gains.max() - gains.min())

    # find -3 dB point relative to passband
    def find_cutoff(ref_db, direction="falling"):
        for i in range(1, len(gains)):
            if direction == "falling" and gains[i] < ref_db - 3:
                return float(freqs[i])
            if direction == "rising" and gains[i] > ref_db - 3:
                return float(freqs[i])
        return None

    label = "Unknown"
    notes = []
    fc = None

    slope_db_dec = None
    if len(freqs) >= 4:
        log_f = np.log10(freqs)
        slope_db_dec = float(np.polyfit(log_f, gains, 1)[0])

    if gain_span < 3:
        label = "Amplifier / Buffer"
        notes.append(f"Flat gain ≈ {gain_low:.1f} dB across sweep")
        if abs(gain_low) < 1:
            notes.append("Unity gain → likely a buffer/voltage follower")
        elif gain_low > 0:
            notes.append(f"Gain > 0 dB → amplifying ({gain_low:.1f} dB)")
        else:
            notes.append(f"Gain < 0 dB → attenuating ({gain_low:.1f} dB)")

    elif gain_low > gain_high + 5:
        label = "Low-pass filter"
        fc = find_cutoff(gain_low, "falling")
        if fc:
            notes.append(f"Cut-off frequency (−3 dB) ≈ {fc:.0f} Hz")
        if slope_db_dec is not None:
            order = round(abs(slope_db_dec) / 20)
            notes.append(f"Roll-off ≈ {slope_db_dec:.0f} dB/decade → ~{order}{'st' if order==1 else 'nd' if order==2 else 'th'} order")

    elif gain_high > gain_low + 5:
        label = "High-pass filter"
        fc = find_cutoff(gain_high, "rising")
        if fc:
            notes.append(f"Cut-off frequency (−3 dB) ≈ {fc:.0f} Hz")
        if slope_db_dec is not None:
            order = round(abs(slope_db_dec) / 20)
            notes.append(f"Roll-off ≈ {slope_db_dec:.0f} dB/decade → ~{order}{'st' if order==1 else 'nd' if order==2 else 'th'} order")

    elif gain_mid > gain_low + 3 and gain_mid > gain_high + 3:
        label = "Band-pass filter"
        peak_idx = int(np.argmax(gains))
        notes.append(f"Peak gain {gains[peak_idx]:.1f} dB at {freqs[peak_idx]:.0f} Hz")

    elif gain_mid < gain_low - 3 and gain_mid < gain_high - 3:
        label = "Band-stop (notch) filter"
        notch_idx = int(np.argmin(gains))
        notes.append(f"Notch at {freqs[notch_idx]:.0f} Hz ({gains[notch_idx]:.1f} dB)")

    # phase hint
    avg_phase = float(np.mean(phases))
    if abs(avg_phase) > 160:
        notes.append("Phase ≈ ±180° → inverting stage")
    elif abs(avg_phase) < 20:
        notes.append("Phase ≈ 0° → non-inverting")

    return {"label": label, "notes": notes, "fc_hz": fc,
            "gain_low_db": gain_low, "gain_high_db": gain_high,
            "slope_db_dec": slope_db_dec}


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def make_bode_plot(points, classification, out_base):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np

    freqs  = [p["freq_hz"]  for p in points]
    gains  = [p["gain_db"]  for p in points]
    phases = [p["phase_deg"] for p in points]

    fig, (ax_g, ax_p) = plt.subplots(2, 1, figsize=(11, 7), dpi=150, sharex=True)

    ax_g.semilogx(freqs, gains, "o-", color="#1f77b4", linewidth=1.5, markersize=4)
    if classification["fc_hz"]:
        ax_g.axvline(classification["fc_hz"], color="red", linestyle="--",
                     linewidth=1, label=f"fc ≈ {classification['fc_hz']:.0f} Hz")
        ax_g.legend(fontsize=9)
    ax_g.set_ylabel("Gain (dB)")
    ax_g.set_title(f"Bode Plot — DUT identified as: {classification['label']}")
    ax_g.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_g.axhline(-3, color="gray", linestyle=":", linewidth=0.8, alpha=0.7)

    ax_p.semilogx(freqs, phases, "s-", color="#ff7f0e", linewidth=1.5, markersize=4)
    ax_p.set_ylabel("Phase (°)")
    ax_p.set_xlabel("Frequency (Hz)")
    ax_p.set_ylim(-200, 200)
    ax_p.axhline(-45,  color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax_p.axhline(-90,  color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax_p.axhline(-135, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_p.xaxis.set_major_formatter(ticker.EngFormatter(unit="Hz"))

    fig.tight_layout()
    png_path = out_base + "_bode.png"
    fig.savefig(png_path)
    print(f"Bode plot saved: {png_path}")
    return png_path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def make_report(points, classification, png_path, out_base, device):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# DUT Identification Report",
        "",
        f"**Timestamp:** {ts}  ",
        f"**Device:** {device}  ",
        "",
        "---",
        "",
        "## Identification Result",
        "",
        f"**Circuit type: {classification['label']}**",
        "",
    ]
    for note in classification["notes"]:
        lines.append(f"- {note}")

    lines += [
        "",
        "---",
        "",
        "## Sweep Settings",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Input (W1) | Sine, 1.5 Vpk (3 Vpp) |",
        f"| Frequencies | {points[0]['freq_hz']:.0f} Hz – {points[-1]['freq_hz']:.0f} Hz |",
        f"| Points | {len(points)} |",
        f"| Channels | CH1 (input), CH2 (output) |",
        "",
        "---",
        "",
        "## Frequency Response",
        "",
        "| Frequency (Hz) | Gain (dB) | Phase (°) | Vin (Vpk) | Vout (Vpk) |",
        "|---------------|-----------|-----------|-----------|------------|",
    ]
    for p in points:
        lines.append(
            f"| {p['freq_hz']:>10,.0f} | {p['gain_db']:>9.2f} | "
            f"{p['phase_deg']:>9.1f} | {p['amp_in_vpk']:>9.4f} | {p['amp_out_vpk']:>10.4f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Bode Plot",
        "",
        f"![Bode Plot]({pathlib.Path(png_path).name})",
        "",
    ]

    md_path = out_base + "_report.md"
    pathlib.Path(md_path).write_text("\n".join(lines))
    print(f"Report saved: {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7272")
    parser.add_argument("--start", type=float, default=100)
    parser.add_argument("--stop",  type=float, default=100_000)
    parser.add_argument("--points", type=int, default=30)
    parser.add_argument("--amplitude", type=float, default=1.5)
    parser.add_argument("--out", default="/tmp/dut")
    args = parser.parse_args()

    status = get(args.url, "/api/digilent/status")
    device = status.get("device_name", "unknown")
    print(f"Device: {device}")
    print(f"Sweep: {args.start:.0f} Hz – {args.stop:.0f} Hz  ({args.points} points)\n")

    freqs = [args.start * (args.stop / args.start) ** (i / (args.points - 1))
             for i in range(args.points)]

    points = []
    for i, f in enumerate(freqs):
        r = measure_at(args.url, f, amplitude_v=args.amplitude)
        if r:
            points.append(r)
            print(f"  [{i+1:2d}/{args.points}] {f:8.0f} Hz  "
                  f"gain={r['gain_db']:+6.1f} dB  phase={r['phase_deg']:+7.1f}°")
        else:
            print(f"  [{i+1:2d}/{args.points}] {f:8.0f} Hz  FAILED")

    post(args.url, "/api/digilent/wavegen/stop", {"channel": 1})
    print("\nWavegen stopped.")

    if len(points) < 3:
        print("Not enough data points for classification.")
        return

    cl = classify(points)
    print(f"\nIdentified as: {cl['label']}")
    for n in cl["notes"]:
        print(f"  → {n}")

    png = make_bode_plot(points, cl, args.out)
    make_report(points, cl, png, args.out, device)


if __name__ == "__main__":
    main()
