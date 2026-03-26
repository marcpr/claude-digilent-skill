# Extending the Digilent Local Skill: Waveform Export

This document explains how the skill was extended to save scope captures as
a `.csv` data file, a `.png` waveform plot, and a `.md` settings/results
summary — and how to adapt or build on this further.

---

## Overview

The standard skill endpoints (`scope/capture`, `scope/measure`) return JSON.
By adding `"return_waveform": true` to a `scope/capture` request the server
also includes the raw sample arrays. The tool `tools/plot_waveform.py` reads
that JSON and produces the three output files.

```
scope/capture (return_waveform: true)
        │
        ▼
 ch1_capture.json
        │
        ├──► ch1_waveform.csv        raw time + voltage samples
        ├──► ch1_waveform.png        matplotlib plot
        └──► ch1_waveform_scope.md   scope settings + metrics
```

---

## Step-by-step: capturing with raw data

### 1. Ensure the wavegen is running (if needed)

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/set \
  -H "Content-Type: application/json" \
  -d '{
    "channel": 1,
    "waveform": "square",
    "frequency_hz": 5000,
    "amplitude_v": 1.5,
    "offset_v": 1.5,
    "symmetry_percent": 50,
    "enable": true
  }'
sleep 0.1
```

### 2. Capture with `return_waveform: true`

The key difference from a normal capture is the `"return_waveform": true`
flag. Without it the server discards the sample arrays after computing metrics.

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1],
    "range_v": 5.0,
    "offset_v": 0.0,
    "sample_rate_hz": 200000,
    "duration_ms": 10,
    "trigger": {
      "enabled": true,
      "source": "ch1",
      "edge": "rising",
      "level_v": 1.5,
      "timeout_ms": 2000
    },
    "return_waveform": true
  }' > capture.json
```

The response JSON has this structure:

```jsonc
{
  "ok": true,
  "device": "Analog Discovery 2",
  "ts": "2026-03-24T09:06:57Z",
  "duration_ms": 15.0,
  "metrics": {
    "ch1": { "vmin": -0.022, "vmax": 2.754, "vpp": 2.776, "vavg": 1.372,
             "vrms": 1.947, "freq_est_hz": 5000.0, "duty_cycle_percent": 50.0,
             "rise_time_s": 2e-4, "fall_time_s": 2e-4 }
  },
  "waveform": {
    "t_start_s": 0.0,
    "dt_s": 5e-06,           // 1 / sample_rate_hz
    "unit_x": "s",
    "unit_y": "V",
    "channels": [
      { "channel": 1, "y": [ 0.001, 2.753, ... ] }   // one float per sample
    ]
  }
}
```

> **Note:** `scope/measure` does **not** support `return_waveform`. Use
> `scope/capture` whenever you need raw samples.

### 3. Run the export tool

```bash
python tools/plot_waveform.py capture.json --out my_capture
```

Produces:

| File | Contents |
|------|----------|
| `my_capture.csv` | `time_s, ch1` — one row per sample |
| `my_capture.png` | Waveform plot with metrics annotation |
| `my_capture_scope.md` | Acquisition settings + per-channel metrics table |

---

## The export tool — `tools/plot_waveform.py`

### CSV output

Each row contains the reconstructed timestamp and the voltage for every
captured channel:

```
time_s,ch1
0.000000000,0.001234
0.000005000,2.753675
...
```

Time is reconstructed as `t_start_s + i * dt_s`.

### PNG output

Requires `matplotlib`. Install once with:

```bash
pip install matplotlib --break-system-packages   # system Python
# or inside a venv: pip install matplotlib
```

The plot uses `matplotlib.use("Agg")` (no display required) and saves at
150 dpi. An annotation box in the top-right corner shows frequency, Vpp and
duty cycle pulled from the `metrics` block.

### Markdown output

`build_markdown()` assembles two tables from the JSON:

- **Acquisition Settings** — derived from `waveform.dt_s`, `waveform.t_start_s`,
  and top-level `duration_ms`. Sample rate is back-calculated as `1 / dt_s`.
- **Measured Metrics** — sourced directly from the `metrics` block, one
  sub-section per channel.

It also lists the three output files at the bottom so the document is
self-contained.

---

## Adapting the tool

### Add a second channel

Capture both channels at once:

```bash
# in the curl body:
"channels": [1, 2]
```

`plot_waveform.py` already handles multiple channels: it iterates
`waveform.channels` and adds one column per channel to the CSV, one trace
per channel to the PNG, and one metrics sub-section per channel to the
Markdown. No code changes needed.

### Change sample rate or duration

Adjust `sample_rate_hz` and `duration_ms` in the capture request.
The tool recalculates everything from `dt_s` and `n_samples` automatically.

Practical limits for the Analog Discovery 2:

| Parameter | Recommended range |
|-----------|------------------|
| `sample_rate_hz` | 1 000 – 100 000 000 |
| `duration_ms` | 1 – 1 000 (device-RAM limited at high rates) |

### Trigger-free capture

Set `"trigger": {"enabled": false}` for a free-running capture. Useful when
the signal level is unknown or when measuring DC voltages.

### Rename output files

Pass `--out` with a full path and prefix:

```bash
python tools/plot_waveform.py capture.json --out /data/2026-03-24/run01
# → /data/2026-03-24/run01.csv
# → /data/2026-03-24/run01.png
# → /data/2026-03-24/run01_scope.md
```

### Embed the PNG in the Markdown

Edit `build_markdown()` in `plot_waveform.py` and add a line after the
Output Files table:

```python
lines += [
    "",
    "## Waveform",
    "",
    f"![Waveform]({pathlib.Path(png_path).name})",
    "",
]
```

The relative path works when all three files sit in the same directory.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `KeyError: 'waveform'` | Capture sent without `return_waveform: true` | Re-run with the flag |
| `DIGILENT_CAPTURE_TIMEOUT` | Trigger never fired | Lower `level_v` or set `trigger.enabled: false` |
| `matplotlib not installed` | Missing dependency | `pip install matplotlib` |
| PNG is blank / all zero | Wavegen not running at capture time | Start wavegen, add `sleep 0.1`, then capture |
| Rise/fall time shows `2e-4` for a 5 kHz square wave | Too-low sample rate (only ~1 edge captured) | Increase `sample_rate_hz` to ≥ 1 MS/s for accurate edge timing |

---

## Impedance Sweep Tool (`impedance_sweep.py`)

`tools/impedance_sweep.py` extends the analysis workflow to the impedance
analyzer. It calls `POST /impedance/sweep` and produces `.csv`, `.png`, and
`.md` output files in the same style as `plot_waveform.py`.

### Workflow

```
POST /impedance/sweep
        │
        ▼
   sweep response (frequencies + named measurement arrays)
        │
        ├──► sweep.csv          frequency, impedance, phase, R, X (per step)
        ├──► sweep.png          two-panel Bode chart (|Z| dBΩ + phase °)
        └──► sweep.md           DUT classification, estimated value, key metrics
```

### DUT classifier

The classifier performs a linear regression of log|Z| vs log(f) to estimate
the impedance slope, then combines with mean phase to identify the DUT:

| Slope | Mean phase | Classification |
|-------|-----------|----------------|
| ≈ 0 | ≈ 0° | Resistor |
| ≈ −1 | ≈ −90° | Capacitor |
| ≈ +1 | ≈ +90° | Inductor |
| −0.3 to −0.7 | mixed | RC network |
| +0.3 to +0.7 | mixed | RL network |
| other | | Complex / resonant |

For capacitors, the estimated value is `C = 1 / (2π·f_mid·|Z_mid|)`.
For inductors: `L = |Z_mid| / (2π·f_mid)`. Both are auto-scaled to pF/nF/µF
or nH/µH/mH as appropriate.

### Extending the plot

To add annotation (e.g. resonant frequency marker) to the Bode chart, edit
`plot_sweep()` in `tools/impedance_sweep.py`. The function receives:
- `frequencies` — list of Hz values
- `impedances` — list of |Z| values in Ω
- `phases` — list of phase values in °
- `dut` — dict from `classify_dut()`

---

## Protocol Decode Tool (`protocol_decode.py`)

`tools/protocol_decode.py` captures a digital protocol bus and writes a
hex+ASCII dump plus a Markdown report with a protocol-specific frame table.

### Workflow

```
POST /protocol/uart/configure + receive  (or spi/i2c/can equivalent)
        │
        ▼
   capture result (bytes / frames)
        │
        ├──► capture.hex    hex+ASCII dump (16 bytes/line, like xxd)
        └──► capture.md     Markdown report with frame table
```

### Hex dump format

```
00000000  48 65 6C 6C 6F 20 57 6F  72 6C 64 0D 0A 00 00 00  |Hello World.....|
00000010  ...
```

### Adding a new protocol

To add a new protocol (e.g. SWD on Analog Discovery 3):
1. Add a new `capture_<protocol>()` function following the pattern in
   `capture_uart()` — call configure then capture, return a dict with keys:
   `protocol`, `bytes_received`, `raw`, `frames`, `errors`, `warnings`, `meta`
2. Add the subcommand parser in `build_parser()`
3. Register the function in the `CAPTURE_FNS` dict in `main()`
4. Add a `elif protocol == "SWD":` branch in `write_report()` for the
   protocol-specific table format
