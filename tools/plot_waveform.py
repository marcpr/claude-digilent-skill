#!/usr/bin/env python3
"""
Read a scope capture JSON (with return_waveform=true) and produce:
  - a CSV file        (time_s, ch1_v, ...)
  - a PNG image       of the waveform
  - a Markdown file   with all scope settings and measured metrics
"""

import json
import csv
import pathlib
import argparse
from datetime import datetime, timezone


def build_markdown(data: dict, ch_names: list, dt: float, n: int,
                   csv_path: str, png_path: str) -> str:
    ts_raw = data.get("ts", "")
    try:
        ts = datetime.fromisoformat(ts_raw).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        ts = ts_raw

    sample_rate_hz = round(1 / dt) if dt else 0
    duration_ms = data.get("duration_ms", n * dt * 1000)
    device = data.get("device", "unknown")
    w = data["waveform"]

    lines = [
        "# Scope Capture — Settings & Results",
        "",
        f"**Timestamp:** {ts}  ",
        f"**Device:** {device}  ",
        f"**Request ID:** {data.get('request_id', 'n/a')}  ",
        "",
        "---",
        "",
        "## Acquisition Settings",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Channels captured | {', '.join(c.upper() for c in ch_names)} |",
        f"| Sample rate | {sample_rate_hz:,} Hz ({sample_rate_hz/1e6:.3f} MS/s) |",
        f"| Duration | {duration_ms:.1f} ms |",
        f"| Samples per channel | {n:,} |",
        f"| Time step (dt) | {dt:.2e} s |",
        f"| Time axis unit | {w.get('unit_x', 's')} |",
        f"| Voltage axis unit | {w.get('unit_y', 'V')} |",
        f"| t_start | {w.get('t_start_s', 0):.6f} s |",
        "",
        "---",
        "",
        "## Measured Metrics",
        "",
    ]

    metrics = data.get("metrics", {})
    for ch in ch_names:
        m = metrics.get(ch, {})
        lines += [
            f"### {ch.upper()}",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Vmin | {m.get('vmin', 'n/a'):.4f} V |" if m.get('vmin') is not None else "| Vmin | n/a |",
            f"| Vmax | {m.get('vmax', 'n/a'):.4f} V |" if m.get('vmax') is not None else "| Vmax | n/a |",
            f"| Vpp | {m.get('vpp', 'n/a'):.4f} V |" if m.get('vpp') is not None else "| Vpp | n/a |",
            f"| Vavg | {m.get('vavg', 'n/a'):.4f} V |" if m.get('vavg') is not None else "| Vavg | n/a |",
            f"| Vrms | {m.get('vrms', 'n/a'):.4f} V |" if m.get('vrms') is not None else "| Vrms | n/a |",
        ]
        if m.get("freq_est_hz") is not None:
            hz = m["freq_est_hz"]
            freq_str = f"{hz/1e3:.4f} kHz" if hz >= 1000 else f"{hz:.2f} Hz"
            lines.append(f"| Frequency (est.) | {freq_str} |")
        if m.get("period_est_s") is not None:
            lines.append(f"| Period (est.) | {m['period_est_s']:.6f} s |")
        if m.get("duty_cycle_percent") is not None:
            lines.append(f"| Duty cycle | {m['duty_cycle_percent']:.1f} % |")
        if m.get("rise_time_s") is not None:
            lines.append(f"| Rise time | {m['rise_time_s']:.2e} s |")
        if m.get("fall_time_s") is not None:
            lines.append(f"| Fall time | {m['fall_time_s']:.2e} s |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Output Files",
        "",
        f"| File | Description |",
        f"|------|-------------|",
        f"| `{pathlib.Path(csv_path).name}` | Raw sample data (time + voltage columns) |",
        f"| `{pathlib.Path(png_path).name}` | Waveform plot |",
        f"| `{pathlib.Path(csv_path).stem}_scope.md` | This file |",
        "",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", help="Capture JSON file")
    parser.add_argument("--out", default="waveform", help="Output basename (no extension)")
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.json_file).read_text())
    w = data["waveform"]
    dt = w["dt_s"]
    t_start = w["t_start_s"]
    channels = w["channels"]

    ch_names = [f"ch{ch['channel']}" if isinstance(ch["channel"], int) else ch["channel"]
                for ch in channels]
    samples = [ch["y"] for ch in channels]
    n = len(samples[0])
    times = [t_start + i * dt for i in range(n)]

    csv_path = args.out + ".csv"
    png_path = args.out + ".png"
    md_path  = args.out + "_scope.md"

    # --- CSV ---
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s"] + ch_names)
        for i in range(n):
            writer.writerow([f"{times[i]:.9f}"] + [f"{samples[c][i]:.6f}" for c in range(len(channels))])
    print(f"CSV saved: {csv_path}  ({n} rows)")

    # --- Markdown ---
    md = build_markdown(data, ch_names, dt, n, csv_path, png_path)
    pathlib.Path(md_path).write_text(md)
    print(f"Markdown saved: {md_path}")

    # --- Plot ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print("matplotlib not installed — skipping PNG")
        return

    metrics = data.get("metrics", {})
    fig, ax = plt.subplots(figsize=(12, 4), dpi=150)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for idx, (name, ys) in enumerate(zip(ch_names, samples)):
        ax.plot(times, ys, linewidth=1.0, color=colors[idx % len(colors)], label=name.upper())

    m = metrics.get(ch_names[0], {})
    info = []
    if m.get("freq_est_hz"):
        hz = m["freq_est_hz"]
        info.append(f"f = {hz/1e3:.2f} kHz" if hz >= 1000 else f"f = {hz:.1f} Hz")
    if m.get("vpp") is not None:
        info.append(f"Vpp = {m['vpp']:.3f} V")
    if m.get("duty_cycle_percent") is not None:
        info.append(f"DC = {m['duty_cycle_percent']:.1f}%")
    if info:
        ax.text(0.98, 0.95, "\n".join(info), transform=ax.transAxes,
                fontsize=9, verticalalignment="top", horizontalalignment="right",
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.8))

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"Scope Capture — {', '.join(c.upper() for c in ch_names)}")
    ax.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.xaxis.set_major_formatter(ticker.EngFormatter(unit="s"))

    fig.tight_layout()
    fig.savefig(png_path)
    print(f"PNG saved: {png_path}")


if __name__ == "__main__":
    main()
