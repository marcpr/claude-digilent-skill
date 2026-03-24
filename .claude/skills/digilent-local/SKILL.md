# Digilent Local Skill

Use this skill when the user wants to use a Digilent Analog Discovery device
connected **directly via USB to this machine** (not via a Raspberry Pi workbench).

Trigger on: "scope", "oscilloscope", "logic analyzer", "wavegen", "waveform generator",
"analog measurement", "PWM messen", "Spannung messen", "digitale Aktivität",
"digilent", "Analog Discovery", "lokal messen", "measure locally"

Do NOT use this skill when the user explicitly mentions a Raspberry Pi workbench
— use the `digilent-workbench` skill instead.

---

## Step 0: First Use Only — Verify Setup

Run this once to confirm WaveForms is installed and the device is connected:

```bash
python tools/digilent_local_setup.py
```

If any `[FAIL]` lines appear, resolve them before continuing. Common fixes:
- **Library not found**: Install WaveForms from https://digilent.com/reference/software/waveforms/waveforms-3/start
- **Device not detected**: Check USB, close WaveForms GUI (exclusive device access)
- **Apple Silicon + x86 library**: Install WaveForms ≥ 3.21.2 (universal binary)

---

## Step 1: Start the Server

The local server must be running before any measurements. It holds the device
open for the duration of the session.

**Check if already running:**
```bash
curl -s http://127.0.0.1:7272/api/digilent/ping
```
Expected response: `{"ok": true, "server": "digilent-local", "version": "1.0"}`

**Start in background (recommended for multi-step sessions):**
```bash
python tools/digilent_local_server.py &
DIGILENT_PID=$!
```

**Start in foreground (single measurement check):**
```bash
python tools/digilent_local_server.py
```

**Optional flags:**
```bash
python tools/digilent_local_server.py --port 7273          # use different port
python tools/digilent_local_server.py --no-auto-open       # don't open device at start
python tools/digilent_local_server.py --allow-supplies     # enable power supply endpoints
```

The server is ready when it prints:
```
[digilent-local] Server listening on http://127.0.0.1:7272
[digilent-local] Device: Analog Discovery 2 (open)
```

---

## Step 2: Check Device Status

```bash
curl -s http://127.0.0.1:7272/api/digilent/status
```

Key fields to verify:
- `device_present: true` — device is connected
- `device_open: true` — device handle is held
- `state: "idle"` — ready for measurements

If `device_present` is false → USB disconnected; replug and call:
```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/device/open
```

If `state` is `"error"` → reset the session:
```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/session/reset
curl -s -X POST http://127.0.0.1:7272/api/digilent/device/open
```

---

## Measurements

### Measure PWM frequency and duty cycle

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "measure_esp32_pwm",
    "params": {
      "channel": 1,
      "expected_freq_hz": 1000,
      "tolerance_percent": 5,
      "sample_rate_hz": 2000000,
      "duration_ms": 20
    }
  }'
```

Response: `within_tolerance`, `measured_freq_hz`, `duty_cycle_percent`, `vpp`

### Measure voltage level

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "measure_voltage_level",
    "params": {
      "channel": 1,
      "expected_v": 3.3,
      "tolerance_v": 0.1,
      "range_v": 5.0
    }
  }'
```

### Detect digital activity on a logic channel

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "detect_logic_activity",
    "params": {
      "channels": [0, 1],
      "sample_rate_hz": 1000000,
      "duration_samples": 10000,
      "min_edges": 2
    }
  }'
```

### Scope capture (free-run — recommended)

**Important:** `scope/capture` with `trigger.enabled: true` consistently returns
HTTP 504 on Analog Discovery 2. Always use free-run mode for raw waveform data.
Use `scope/measure` (not `scope/capture`) when you only need metrics and want trigger support.

**Buffer limits for `scope/capture`:**

| Sample rate | Max reliable duration | Max samples |
|-------------|----------------------|-------------|
| 10 MS/s     | 0.1 ms               | ~1 000      |
| 1 MS/s      | 5 ms                 | ~5 000      |
| 200 kHz     | 50 ms                | ~10 000     |

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1, 2],
    "range_v": 5.0,
    "offset_v": 0.0,
    "sample_rate_hz": 200000,
    "duration_ms": 10,
    "trigger": {"enabled": false},
    "return_waveform": true
  }'
```

Response includes per-channel metrics (`vmin`, `vmax`, `vpp`, `vavg`, `vrms`,
`freq_est_hz`, `duty_cycle_percent`) and, when `return_waveform: true`, a
`waveform` array with `channel` (integer), `time_s`, and `voltage_v` arrays.

**Note:** The server returns `"channel": 1` (integer), not `"channel": "ch1"`.
Normalize when parsing: `ch_name = f"ch{ch['channel']}" if isinstance(ch['channel'], int) else ch['channel']`

### Scope capture at high frequencies (≥ 10 kHz signals)

For signals ≥ 10 kHz use 10 MS/s with a short duration (0.05–0.1 ms):

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1],
    "range_v": 5.0,
    "sample_rate_hz": 10000000,
    "duration_ms": 0.1,
    "trigger": {"enabled": false},
    "return_waveform": true
  }'
```

### Scope measure with trigger (metrics only, no raw samples)

Use `scope/measure` when you only need scalar metrics and want reliable trigger support:

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/measure \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1],
    "range_v": 5.0,
    "sample_rate_hz": 200000,
    "duration_ms": 10,
    "trigger": {
      "enabled": true,
      "source": "ch1",
      "edge": "rising",
      "level_v": 1.6,
      "timeout_ms": 1000
    }
  }'
```

Metrics: `vmin`, `vmax`, `vpp`, `vavg`, `vrms`, `freq_est_hz`,
`duty_cycle_percent`, `rise_time_s`, `fall_time_s`

### Scope quick measure (no raw data)

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/measure \
  -H "Content-Type: application/json" \
  -d '{"channels": [1], "range_v": 5.0, "sample_rate_hz": 100000, "duration_ms": 10}'
```

### Logic analyzer capture

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/logic/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [0, 1, 2],
    "sample_rate_hz": 10000000,
    "samples": 20000,
    "trigger": {
      "enabled": true,
      "channel": 0,
      "edge": "rising",
      "timeout_ms": 1000
    },
    "return_samples": false
  }'
```

Logic metrics per channel: `high_ratio`, `low_ratio`, `edge_count`,
`freq_est_hz`, `duty_cycle_percent`

### Waveform generator

```bash
# Start square wave on CH1
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/set \
  -H "Content-Type: application/json" \
  -d '{
    "channel": 1,
    "waveform": "square",
    "frequency_hz": 1000,
    "amplitude_v": 1.65,
    "offset_v": 1.65,
    "symmetry_percent": 50,
    "enable": true
  }'

# Stop
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/stop \
  -H "Content-Type: application/json" \
  -d '{"channel": 1}'
```

Valid waveforms: `sine`, `square`, `triangle`, `dc`

### Static I/O

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/static-io/set \
  -H "Content-Type: application/json" \
  -d '{"pins": [{"index": 0, "mode": "output", "value": 1}, {"index": 1, "mode": "input"}]}'
```

### Power Supplies (requires `--allow-supplies` flag)

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/supplies/set \
  -H "Content-Type: application/json" \
  -d '{"vplus_v": 3.3, "enable_vplus": true, "confirm_unsafe": true}'
```

---

## Waveform Export (PNG, CSV, Markdown)

Use `tools/plot_waveform.py` to capture raw waveform data and save it as PNG,
CSV, and a Markdown report in one step.

**Dependencies:** `pip install numpy matplotlib`

```bash
python tools/plot_waveform.py \
  --channels 1 2 \
  --rate 200000 \
  --duration 10 \
  --range 5.0 \
  --out /tmp/capture
```

This produces:
- `/tmp/capture.png` — multi-channel waveform plot
- `/tmp/capture.csv` — time + voltage columns
- `/tmp/capture.md` — Markdown report with embedded plot and scope settings

**Key options:**
```
--channels N [N ...]   scope channel numbers (default: 1)
--rate HZ              sample rate in Hz (default: 200000)
--duration MS          capture duration in ms (default: 10)
--range V              voltage range per channel (default: 5.0)
--out PATH             output path prefix (no extension)
--title STR            plot title
```

For high-frequency signals (≥ 10 kHz), use `--rate 10000000 --duration 0.1`.

---

## FFT Analysis

Use `tools/fft_analyze.py` to run spectral analysis on a captured channel.
Detects the fundamental frequency, harmonics H2–H10, THD, and SFDR.

**Dependencies:** `pip install numpy matplotlib scipy`

```bash
python tools/fft_analyze.py \
  --channel 1 \
  --rate 1000000 \
  --duration 5 \
  --range 5.0 \
  --out /tmp/fft
```

This produces:
- `/tmp/fft.png` — two-panel plot (linear amplitude + dB spectrum)
- `/tmp/fft.md` — Markdown report with fundamental, harmonics table, THD, SFDR

---

## DUT Identification (Bode Plot)

Use `tools/dut_identify.py` for automated frequency sweep and DUT classification.

**Wiring:**
```
W1  →  DUT input  →  CH1 (reference)
           DUT output  →  CH2 (response)
```

**Dependencies:** `pip install numpy matplotlib scipy`

```bash
python tools/dut_identify.py \
  --fstart 100 \
  --fstop 500000 \
  --steps 40 \
  --amplitude 1.0 \
  --out /tmp/bode
```

This produces:
- `/tmp/bode.png` — Bode plot (gain dB + phase °) with annotated −3 dB point
- `/tmp/bode_report.md` — classification, fc, roll-off slope, passband gain

**Classification output:** `low_pass`, `high_pass`, `band_pass`, `notch`, or `amplifier`

**Grenzfrequenz estimation** uses the phase method: `fc = f / tan(−φ)` which is
more stable than the gain method when only partial rolloff is visible.

**Capture strategy inside dut_identify:** free-run only, duration capped at 50 ms,
sample rate auto-scaled to ≥ 20 samples/period. HTTP timeout set to 60 s.

---

## Error Handling

Always check `ok` and `error.code` in the response:

| HTTP | `error.code` | Meaning | Action |
|------|-------------|---------|--------|
| 400 | `DIGILENT_CONFIG_INVALID` | Bad parameter | Fix the request |
| 400 | `DIGILENT_RANGE_VIOLATION` | Value exceeds safe limit | Reduce amplitude/rate |
| 403 | `DIGILENT_NOT_ENABLED` | Feature disabled | Use `--allow-supplies` flag |
| 409 | `DIGILENT_BUSY` | Concurrent request | Wait and retry |
| 503 | `DIGILENT_NOT_FOUND` | No device | Check USB, call device/open |
| 504 | `DIGILENT_CAPTURE_TIMEOUT` | Trigger never fired | Disable trigger or check signal |

---

## Safety Rules

1. **Scope and Logic**: read-only, safe to use freely
2. **Wavegen**: always warn the user before enabling — amplitude must be safe for the connected circuit
3. **Supplies**: disabled by default — start server with `--allow-supplies` and always use `confirm_unsafe: true`
4. Request raw waveforms (`return_waveform: true`) only when explicitly needed
5. **WaveForms GUI**: must be closed while the server is running (exclusive USB access)

---

## Wiring (standard passive observation)

```
Analog Discovery GND  →  DUT GND   (mandatory)
Scope CH1+           →  Signal to measure
Scope CH1-           →  GND (or differential signal)
Logic DIO0           →  Digital line (e.g. UART TX)
Logic DIO1           →  Digital line (e.g. UART RX)
```

For ESP32 boot/reset sequencing: use GPIO 17/18 directly on the Pi workbench
(separate skill). The Analog Discovery is for observation, not for driving
reset/boot pins.

---

## Step 3: Stop the Server

```bash
kill $DIGILENT_PID      # if started with &
# or Ctrl-C if running in foreground
```

The device handle is released on shutdown. WaveForms GUI can be opened again afterwards.

**Stale server check** (if you get unexpected errors):
```bash
# Linux / macOS
lsof -i :7272

# Windows
netstat -ano | findstr 7272
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl: Connection refused` | Server not running | Start with `python tools/digilent_local_server.py` |
| `device_present: false` | No USB device | Check cable; replug; call device/open |
| `state: error` | DWF error | Call session/reset, then device/open |
| `409 DIGILENT_BUSY` | Concurrent request | Wait; or session/reset if stuck |
| `503` from server start | libdwf not found | Run `python tools/digilent_local_setup.py` |
| WaveForms GUI won't open | Server holds device | Stop server first (kill / Ctrl-C) |
| Trigger timeout | Signal not present | Set `trigger.enabled: false` for free-run |
