#!/usr/bin/env python3
"""
FFT analysis of a scope capture channel.
Produces:
  - <out>_fft.png   spectrum plot (linear + dB)
  - <out>_fft.md    analysis report
"""

import json
import pathlib
import argparse
from datetime import datetime, timezone


def analyze(ch_data, sample_rate, window_type="hanning"):
    import numpy as np

    n = len(ch_data)
    signal = np.array(ch_data)
    dc = float(np.mean(signal))

    if window_type == "hanning":
        window = np.hanning(n)
        coherent_gain = np.sum(window) / n
    else:
        window = np.ones(n)
        coherent_gain = 1.0

    F = np.fft.rfft(signal * window)
    freqs = np.fft.rfftfreq(n, d=1 / sample_rate)

    # peak-corrected amplitude spectrum (Vpk)
    amp = (2 / n) * np.abs(F) / coherent_gain
    amp[0] /= 2  # DC bin — no factor-of-2

    # dBV (re 1 Vrms = 0 dBV)
    amp_rms = amp / (2 ** 0.5)
    amp_rms[0] = amp[0]  # DC is already RMS
    dbv = 20 * np.log10(np.maximum(amp_rms, 1e-9))

    # find fundamental: highest amplitude peak
    fund_idx = int(np.argmax(amp[1:])) + 1
    fund_freq = float(freqs[fund_idx])
    fund_amp  = float(amp[fund_idx])

    # collect harmonics (2nd … 10th)
    harmonics = []
    for h in range(2, 11):
        target = fund_freq * h
        if target > freqs[-1]:
            break
        idx = int(np.argmin(np.abs(freqs - target)))
        harmonics.append({
            "order": h,
            "freq_hz": float(freqs[idx]),
            "amp_vpk": float(amp[idx]),
            "dbc": float(20 * np.log10(amp[idx] / fund_amp + 1e-12)),
        })

    # THD
    harm_power = sum(h["amp_vpk"] ** 2 for h in harmonics)
    thd_pct = 100 * (harm_power ** 0.5) / fund_amp

    # noise floor estimate (median excluding fundamental ± 3 bins)
    mask = np.ones(len(amp), dtype=bool)
    mask[max(0, fund_idx - 3): fund_idx + 4] = False
    noise_floor_dbv = float(np.median(dbv[mask]))

    # SFDR: highest spur other than fundamental
    spur_mask = mask.copy()
    spur_mask[0] = False
    sfdr_db = float(20 * np.log10(fund_amp / (amp[spur_mask].max() + 1e-12)))

    return {
        "n": n,
        "sample_rate_hz": sample_rate,
        "freq_resolution_hz": sample_rate / n,
        "window": window_type,
        "dc_v": dc,
        "fundamental": {"freq_hz": fund_freq, "amp_vpk": fund_amp,
                        "amp_vpp": fund_amp * 2, "amp_vrms": fund_amp / (2**0.5)},
        "harmonics": harmonics,
        "thd_pct": thd_pct,
        "sfdr_db": sfdr_db,
        "noise_floor_dbv": noise_floor_dbv,
        "freqs": freqs.tolist(),
        "amp": amp.tolist(),
        "dbv": dbv.tolist(),
    }


def make_plot(result, out_base, channel):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    freqs = result["freqs"]
    amp   = result["amp"]
    dbv   = result["dbv"]
    fund  = result["fundamental"]["freq_hz"]

    fig, (ax_lin, ax_db) = plt.subplots(2, 1, figsize=(12, 7), dpi=150)

    # linear
    ax_lin.plot(freqs, amp, color="#1f77b4", linewidth=0.8)
    ax_lin.axvline(fund, color="red", linestyle="--", linewidth=0.8, alpha=0.6, label=f"Fund {fund/1e3:.1f} kHz")
    for h in result["harmonics"]:
        if h["amp_vpk"] > 0.001:
            ax_lin.axvline(h["freq_hz"], color="orange", linestyle=":", linewidth=0.8, alpha=0.7)
    ax_lin.set_ylabel("Amplitude (Vpk)")
    ax_lin.set_title(f"FFT Spectrum — {channel.upper()}")
    ax_lin.set_xlim(0, result["sample_rate_hz"] / 2)
    ax_lin.legend(fontsize=8)
    ax_lin.grid(True, linestyle="--", alpha=0.4)

    # dB
    ax_db.plot(freqs, dbv, color="#1f77b4", linewidth=0.8)
    ax_db.axvline(fund, color="red", linestyle="--", linewidth=0.8, alpha=0.6)
    ax_db.axhline(result["noise_floor_dbv"], color="gray", linestyle=":", linewidth=0.8,
                  alpha=0.6, label=f"Noise floor ≈ {result['noise_floor_dbv']:.0f} dBV")
    for h in result["harmonics"]:
        if h["dbc"] > -80:
            ax_db.axvline(h["freq_hz"], color="orange", linestyle=":", linewidth=0.8, alpha=0.7,
                          label=f"H{h['order']} {h['dbc']:.0f} dBc")
    ax_db.set_xlabel("Frequency (Hz)")
    ax_db.set_ylabel("Amplitude (dBV)")
    ax_db.set_ylim(result["noise_floor_dbv"] - 20, 10)
    ax_db.set_xlim(0, result["sample_rate_hz"] / 2)
    ax_db.legend(fontsize=8)
    ax_db.grid(True, linestyle="--", alpha=0.4)

    import matplotlib.ticker as ticker
    for ax in (ax_lin, ax_db):
        ax.xaxis.set_major_formatter(ticker.EngFormatter(unit="Hz"))

    png_path = out_base + "_fft.png"
    fig.tight_layout()
    fig.savefig(png_path)
    print(f"PNG saved: {png_path}")
    return png_path


def make_report(result, out_base, channel, device, ts_raw, png_path):
    try:
        ts = datetime.fromisoformat(ts_raw).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        ts = ts_raw

    f = result["fundamental"]
    lines = [
        f"# FFT Analysis Report — {channel.upper()}",
        "",
        f"**Timestamp:** {ts}  ",
        f"**Device:** {device}  ",
        "",
        "---",
        "",
        "## Acquisition",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Channel | {channel.upper()} |",
        f"| Samples | {result['n']:,} |",
        f"| Sample rate | {result['sample_rate_hz']:,} Hz ({result['sample_rate_hz']/1e6:.3f} MS/s) |",
        f"| Frequency resolution | {result['freq_resolution_hz']:.1f} Hz |",
        f"| Window function | {result['window'].capitalize()} |",
        f"| DC offset | {result['dc_v']:.5f} V |",
        "",
        "---",
        "",
        "## Fundamental",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Frequency | {f['freq_hz']:,.1f} Hz ({f['freq_hz']/1e3:.4f} kHz) |",
        f"| Amplitude (peak) | {f['amp_vpk']:.5f} Vpk |",
        f"| Amplitude (peak-to-peak) | {f['amp_vpp']:.5f} Vpp |",
        f"| Amplitude (RMS) | {f['amp_vrms']:.5f} Vrms |",
        f"| Level (dBV) | {20*(f['amp_vrms']**0 and __import__('math').log10(f['amp_vrms'])):.2f} dBV |",
        "",
        "---",
        "",
        "## Harmonics",
        "",
        "| Order | Frequency | Amplitude (Vpk) | Relative (dBc) |",
        "|-------|-----------|-----------------|----------------|",
    ]

    import math
    for h in result["harmonics"]:
        lines.append(f"| H{h['order']} | {h['freq_hz']:,.0f} Hz | {h['amp_vpk']:.6f} V | {h['dbc']:.1f} dBc |")

    lines += [
        "",
        "---",
        "",
        "## Signal Quality",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| THD | {result['thd_pct']:.4f} % |",
        f"| SFDR | {result['sfdr_db']:.1f} dB |",
        f"| Noise floor (est.) | {result['noise_floor_dbv']:.1f} dBV |",
        "",
        "---",
        "",
        "## Spectrum Plot",
        "",
        f"![FFT Spectrum]({pathlib.Path(png_path).name})",
        "",
    ]

    md_path = out_base + "_fft.md"
    pathlib.Path(md_path).write_text("\n".join(lines))
    print(f"Report saved: {md_path}")
    return md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--out", default="fft_analysis")
    parser.add_argument("--window", default="hanning", choices=["hanning", "rectangular"])
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.json_file).read_text())
    w = data["waveform"]
    dt = w["dt_s"]
    sample_rate = round(1 / dt)

    ch_entry = next((c for c in w["channels"] if c["channel"] == args.channel), None)
    if ch_entry is None:
        print(f"Channel {args.channel} not found in capture.")
        return

    result = analyze(ch_entry["y"], sample_rate, window_type=args.window)

    channel = f"ch{args.channel}"
    png_path = make_plot(result, args.out, channel)
    make_report(result, args.out, channel, data.get("device", "unknown"),
                data.get("ts", ""), png_path)


if __name__ == "__main__":
    main()
