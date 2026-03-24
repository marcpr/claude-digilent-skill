# Integration Guide — Neue Tools und Erweiterungen

Dieses Dokument fasst alle Dateien zusammen, die in dieser Session neu erstellt
oder verändert wurden, damit sie in die originale Skill-Implementierung
übertragen werden können.

---

## Inhaltsverzeichnis

1. [Übersicht der Änderungen](#1-übersicht-der-änderungen)
2. [Abhängigkeiten](#2-abhängigkeiten)
3. [Bekannte Einschränkungen des Servers](#3-bekannte-einschränkungen-des-servers)
4. [tools/plot_waveform.py — NEU](#4-toolsplot_waveformpy--neu)
5. [tools/fft_analyze.py — NEU](#5-toolsfft_analyzepy--neu)
6. [tools/dut_identify.py — NEU](#6-toolsdut_identifypy--neu)
7. [tools/lab_report_plots.py — Hilfsskript](#7-toolslab_report_plotspy--hilfsskript)
8. [docs/extending-waveform-export.md — NEU](#8-docsextending-waveform-exportmd--neu)
9. [Skill-Instruktionen — Ergänzungen](#9-skill-instruktionen--ergänzungen)

---

## 1. Übersicht der Änderungen

| Datei | Status | Zweck |
|---|---|---|
| `tools/plot_waveform.py` | **NEU** | Scope-Capture → CSV + PNG + Markdown |
| `tools/fft_analyze.py` | **NEU** | FFT-Analyse eines Capture-Kanals → Spektrum-Plot + Bericht |
| `tools/dut_identify.py` | **NEU** | Unbekanntes Netzwerk identifizieren via Frequenz-Sweep (Bode-Plot) |
| `tools/lab_report_plots.py` | **NEU** | Alle Plots für ein Laborprotokoll auf einmal erzeugen |
| `docs/extending-waveform-export.md` | **NEU** | Entwicklerdoku: wie `plot_waveform.py` funktioniert und erweiterbar ist |

Keine bestehenden Dateien wurden verändert. `tests/loopback_test.py` war bereits vorhanden und wurde unverändert genutzt.

---

## 2. Abhängigkeiten

Alle neuen Tools benötigen neben der Python-Standardbibliothek:

```bash
pip install matplotlib numpy scipy
# oder auf system-Python:
pip install matplotlib numpy scipy --break-system-packages
```

| Paket | Benötigt von | Zweck |
|---|---|---|
| `numpy` | alle Tools | Array-Operationen, FFT |
| `matplotlib` | `plot_waveform.py`, `fft_analyze.py`, `dut_identify.py`, `lab_report_plots.py` | Plot-Erzeugung (headless via `Agg`-Backend) |
| `scipy` | `lab_report_plots.py` | `find_peaks` für Phasen-Annotation in Zeitbereichsplots |

`scipy` ist nur in `lab_report_plots.py` erforderlich und nur für die
Peak-Annotation; die anderen Tools kommen ohne aus.

---

## 3. Bekannte Einschränkungen des Servers

Diese Erkenntnisse aus der Session sind wichtig für die korrekte Verwendung:

### scope/capture vs. scope/measure

| Endpoint | Trigger | return_waveform | Zuverlässigkeit |
|---|---|---|---|
| `scope/measure` | ✓ (funktioniert) | ✗ nicht unterstützt | stabil |
| `scope/capture` | ✗ → 504 Timeout | ✓ unterstützt | nur **free-run** zuverlässig |

**Fazit:** Für Rohwaveform-Daten immer `scope/capture` mit `"trigger": {"enabled": false}` verwenden. Trigger auf `scope/capture` erzeugt regelmäßig HTTP 504.

### Abtastrate und Pufferlimit

| Abtastrate | Max. sichere Dauer | Samples |
|---|---|---|
| 200 kHz | 50 ms | 10 000 |
| 1 MS/s | 5 ms | 5 000 |
| 10 MS/s | 0,1 ms | 1 000 |

Oberhalb von ca. 5 000 Samples bei 1 MS/s treten Timeouts auf.

### Wavegen-Zustand nach Server-Neustart

Nach `session/reset` oder Neustart des Servers ist der Wavegen inaktiv —
er muss explizit neu gestartet werden, bevor ein Capture sinnvolle Daten liefert.

### Wartezeit nach Wavegen-Start

Mindestens `sleep 0.05 s` (besser: 3 Perioden) zwischen `wavegen/set` und
`scope/capture` einhalten, damit das Signal eingeschwungen ist.

---

## 4. tools/plot_waveform.py — NEU

**Zweck:** Liest eine `scope/capture`-JSON-Antwort (mit `return_waveform: true`)
und erzeugt CSV, PNG und Markdown.

**Aufruf:**
```bash
python tools/plot_waveform.py <capture.json> --out <basename>
# Erzeugt: <basename>.csv, <basename>.png, <basename>_scope.md
```

**Ausgaben:**

| Datei | Inhalt |
|---|---|
| `<out>.csv` | `time_s, ch1[, ch2, ...]` — eine Zeile pro Sample |
| `<out>.png` | Zeitbereichsplot, alle Kanäle, Metriken-Annotation |
| `<out>_scope.md` | Erfassungseinstellungen + Messtabelle pro Kanal |

**Vollständiger Quellcode:**

```python
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
```

---

## 5. tools/fft_analyze.py — NEU

**Zweck:** Hanning-gefensterte FFT eines einzelnen Scope-Kanals. Erkennt
Grundwelle, Harmonische (H2–H10), berechnet THD und SFDR.

**Aufruf:**
```bash
python tools/fft_analyze.py <capture.json> --channel 1 --out <basename>
# Erzeugt: <basename>_fft.png, <basename>_fft.md
# Voraussetzung: capture.json mit return_waveform: true, >= 2000 Samples
```

**Ausgaben:**

| Datei | Inhalt |
|---|---|
| `<out>_fft.png` | Zweigeteilt: lineares Spektrum (Vpk) + dBV-Spektrum |
| `<out>_fft.md` | Tabellen: Erfassung, Grundwelle, Harmonische, THD/SFDR |

**Empfohlene Capture-Parameter für FFT:**
- Abtastrate: 200 kHz (für Signale bis 10 kHz)
- Dauer: ≥ 10 ms (ergibt 100 Hz Frequenzauflösung)
- Trigger: free-run

**Vollständiger Quellcode:** siehe `tools/fft_analyze.py`

```python
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
    amp[0] /= 2  # DC bin

    amp_rms = amp / (2 ** 0.5)
    amp_rms[0] = amp[0]
    dbv = 20 * np.log10(np.maximum(amp_rms, 1e-9))

    fund_idx = int(np.argmax(amp[1:])) + 1
    fund_freq = float(freqs[fund_idx])
    fund_amp  = float(amp[fund_idx])

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

    harm_power = sum(h["amp_vpk"] ** 2 for h in harmonics)
    thd_pct = 100 * (harm_power ** 0.5) / fund_amp

    mask = np.ones(len(amp), dtype=bool)
    mask[max(0, fund_idx - 3): fund_idx + 4] = False
    noise_floor_dbv = float(np.median(dbv[mask]))

    spur_mask = mask.copy()
    spur_mask[0] = False
    sfdr_db = float(20 * np.log10(fund_amp / (amp[spur_mask].max() + 1e-12)))

    return {
        "n": n, "sample_rate_hz": sample_rate,
        "freq_resolution_hz": sample_rate / n,
        "window": window_type, "dc_v": dc,
        "fundamental": {"freq_hz": fund_freq, "amp_vpk": fund_amp,
                        "amp_vpp": fund_amp * 2, "amp_vrms": fund_amp / (2**0.5)},
        "harmonics": harmonics, "thd_pct": thd_pct,
        "sfdr_db": sfdr_db, "noise_floor_dbv": noise_floor_dbv,
        "freqs": freqs.tolist(), "amp": amp.tolist(), "dbv": dbv.tolist(),
    }


def make_plot(result, out_base, channel):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    freqs = result["freqs"]
    amp   = result["amp"]
    dbv   = result["dbv"]
    fund  = result["fundamental"]["freq_hz"]

    fig, (ax_lin, ax_db) = plt.subplots(2, 1, figsize=(12, 7), dpi=150)

    ax_lin.plot(freqs, amp, color="#1f77b4", linewidth=0.8)
    ax_lin.axvline(fund, color="red", linestyle="--", linewidth=0.8, alpha=0.6,
                   label=f"Fund {fund/1e3:.1f} kHz")
    for h in result["harmonics"]:
        if h["amp_vpk"] > 0.001:
            ax_lin.axvline(h["freq_hz"], color="orange", linestyle=":", linewidth=0.8, alpha=0.7)
    ax_lin.set_ylabel("Amplitude (Vpk)")
    ax_lin.set_title(f"FFT Spectrum — {channel.upper()}")
    ax_lin.set_xlim(0, result["sample_rate_hz"] / 2)
    ax_lin.legend(fontsize=8)
    ax_lin.grid(True, linestyle="--", alpha=0.4)

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

    for ax in (ax_lin, ax_db):
        ax.xaxis.set_major_formatter(ticker.EngFormatter(unit="Hz"))

    png_path = out_base + "_fft.png"
    fig.tight_layout()
    fig.savefig(png_path)
    print(f"PNG saved: {png_path}")
    return png_path


def make_report(result, out_base, channel, device, ts_raw, png_path):
    import math
    try:
        ts = datetime.fromisoformat(ts_raw).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        ts = ts_raw

    f = result["fundamental"]
    lines = [
        f"# FFT Analysis Report — {channel.upper()}",
        "", f"**Timestamp:** {ts}  ", f"**Device:** {device}  ", "",
        "---", "", "## Acquisition", "",
        "| Parameter | Value |", "|-----------|-------|",
        f"| Channel | {channel.upper()} |",
        f"| Samples | {result['n']:,} |",
        f"| Sample rate | {result['sample_rate_hz']:,} Hz ({result['sample_rate_hz']/1e6:.3f} MS/s) |",
        f"| Frequency resolution | {result['freq_resolution_hz']:.1f} Hz |",
        f"| Window function | {result['window'].capitalize()} |",
        f"| DC offset | {result['dc_v']:.5f} V |",
        "", "---", "", "## Fundamental", "",
        "| Parameter | Value |", "|-----------|-------|",
        f"| Frequency | {f['freq_hz']:,.1f} Hz ({f['freq_hz']/1e3:.4f} kHz) |",
        f"| Amplitude (peak) | {f['amp_vpk']:.5f} Vpk |",
        f"| Amplitude (peak-to-peak) | {f['amp_vpp']:.5f} Vpp |",
        f"| Amplitude (RMS) | {f['amp_vrms']:.5f} Vrms |",
        f"| Level (dBV) | {20*math.log10(f['amp_vrms']):.2f} dBV |",
        "", "---", "", "## Harmonics", "",
        "| Order | Frequency | Amplitude (Vpk) | Relative (dBc) |",
        "|-------|-----------|-----------------|----------------|",
    ]
    for h in result["harmonics"]:
        lines.append(f"| H{h['order']} | {h['freq_hz']:,.0f} Hz | {h['amp_vpk']:.6f} V | {h['dbc']:.1f} dBc |")
    lines += [
        "", "---", "", "## Signal Quality", "",
        "| Metric | Value |", "|--------|-------|",
        f"| THD | {result['thd_pct']:.4f} % |",
        f"| SFDR | {result['sfdr_db']:.1f} dB |",
        f"| Noise floor (est.) | {result['noise_floor_dbv']:.1f} dBV |",
        "", "---", "", "## Spectrum Plot", "",
        f"![FFT Spectrum]({pathlib.Path(png_path).name})", "",
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
```

---

## 6. tools/dut_identify.py — NEU

**Zweck:** Identifiziert ein unbekanntes Netzwerk (DUT) über einen
logarithmischen Frequenz-Sweep. W1 → DUT-Eingang, CH1 = Eingang (Referenz),
CH2 = Ausgang. Klassifiziert als Tiefpass, Hochpass, Bandpass, Bandsperre
oder Verstärker/Buffer.

**Aufruf:**
```bash
python tools/dut_identify.py \
  --start 100 --stop 100000 --points 30 \
  --amplitude 1.5 --out /tmp/dut
# Erzeugt: /tmp/dut_bode.png, /tmp/dut_report.md
```

**Wichtige Parameter:**

| Argument | Default | Beschreibung |
|---|---|---|
| `--start` | 100 | Startfrequenz (Hz) |
| `--stop` | 100 000 | Stopfrequenz (Hz) |
| `--points` | 30 | Anzahl log-verteilter Messpunkte |
| `--amplitude` | 1.5 | W1-Amplitude in Vpk (= Vpp/2) |
| `--out` | `/tmp/dut` | Ausgabe-Basename |
| `--url` | `http://127.0.0.1:7272` | Server-URL |

**Capture-Strategie (wichtig für Stabilität):**
- Free-run (kein Trigger) — Trigger auf `scope/capture` erzeugt 504
- Dauer automatisch begrenzt auf max. 50 ms
- Abtastrate automatisch angepasst: min. 20 Samples/Periode
- HTTP-Timeout: 60 s (nicht 15 s wie Standard)

**Vollständiger Quellcode:** `tools/dut_identify.py` (siehe Datei)

---

## 7. tools/lab_report_plots.py — Hilfsskript

**Zweck:** Einmaliges Skript zum Erzeugen aller Plots für ein Laborprotokoll
über einen RC-Tiefpass. Liest Capture-JSONs aus `/tmp/` und schreibt PNGs nach `/tmp/lab/`.

**Nicht für allgemeine Wiederverwendung gedacht** — enthält hardkodierte
Sweep-Daten und Pfade. Dient als Vorlage für zukünftige Laborprotokoll-Skripte.

Erzeugte Plots:
- `bode.png` / `bode_merged.png` — Bode-Diagramm mit Theorie-Overlay, fc-Markierung, −3 dB / −45°-Linien
- `wave_1k.png` — Zeitbereich Passband
- `wave_79k.png` — Zeitbereich nahe fc (mit Phasen-Annotation)
- `wave_fc.png` — Direktmessung bei fc
- `fc_estimate.png` — Streudiagramm der fc-Schätzung

**Vollständiger Quellcode:** `tools/lab_report_plots.py` (siehe Datei)

---

## 8. docs/extending-waveform-export.md — NEU

Entwicklerdokumentation für `plot_waveform.py`. Erklärt:
- `return_waveform: true` und die JSON-Struktur der Antwort
- Schritt-für-Schritt Workflow: Capture → Export
- Mehrere Kanäle, variable Abtastraten, trigger-freier Betrieb
- Ausgabepfade anpassen, PNG in Markdown einbetten
- Troubleshooting-Tabelle

Datei liegt bereits unter `docs/extending-waveform-export.md`.

---

## 9. Skill-Instruktionen — Ergänzungen

Die folgenden Abschnitte sollten in die Skill-Instruktionsdatei (`.md` des
`digilent-local`-Skills) eingefügt werden, damit Claude die neuen Tools
kennt und korrekt anwendet.

### Ergänzung: Waveform exportieren (CSV / PNG / Markdown)

```markdown
### Export waveform to CSV, PNG and Markdown

Always use `return_waveform: true` on `scope/capture` (NOT `scope/measure`).
Use **free-run** trigger (`"trigger": {"enabled": false}`) — triggered captures
on `scope/capture` produce HTTP 504 on this server version.

Capture example (200 kHz, 10 ms):
```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1],
    "range_v": 5.0,
    "offset_v": 0.0,
    "sample_rate_hz": 200000,
    "duration_ms": 10,
    "trigger": {"enabled": false},
    "return_waveform": true
  }' > capture.json
```

Then run:
```bash
python tools/plot_waveform.py capture.json --out my_capture
```
Produces: `my_capture.csv`, `my_capture.png`, `my_capture_scope.md`
```

### Ergänzung: FFT-Analyse

```markdown
### FFT analysis of a channel

Requires a capture with `return_waveform: true` and sufficient samples
(≥ 2000 recommended for good frequency resolution).

```bash
python tools/fft_analyze.py capture.json --channel 1 --out my_fft
```
Produces: `my_fft_fft.png` (linear + dB spectrum), `my_fft_fft.md` (THD, SFDR, harmonics)
```

### Ergänzung: Unbekanntes Netzwerk identifizieren

```markdown
### Identify unknown DUT via frequency sweep

Wiring: W1 → DUT input → CH1 (reference), DUT output → CH2.

```bash
python tools/dut_identify.py --start 100 --stop 100000 --points 30 --out /tmp/dut
```

The tool sweeps W1 logarithmically, captures both channels at each frequency,
computes gain and phase via Hanning-windowed FFT, classifies the circuit type
(low-pass / high-pass / band-pass / notch / amplifier) and produces a Bode plot
and markdown report.

For high-frequency sweeps (> 79 kHz), use 10 MS/s directly:
- Max reliable duration at 10 MS/s: 0.1 ms
- This covers signals up to ~500 kHz
```

### Ergänzung: Capture-Einschränkungen (kritisch)

```markdown
### Known capture limitations (Analog Discovery 2 + this server)

| Sample rate | Max reliable duration | Notes |
|---|---|---|
| 200 kHz | 50 ms | Standard sweep range |
| 1 MS/s | 5 ms | Waveform export, FFT |
| 10 MS/s | 0.1 ms | High-frequency (> 79 kHz) |

- **Always use free-run** (`trigger.enabled: false`) with `scope/capture`
- **Wait after wavegen start**: `sleep 0.05` minimum before capturing
- **After server restart**: wavegen state is lost — re-enable before capturing
- `scope/measure` supports triggers and is stable, but returns no raw samples
```
