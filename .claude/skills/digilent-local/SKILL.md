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

### Full scope capture with trigger

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/capture \
  -H "Content-Type: application/json" \
  -d '{
    "channels": [1],
    "range_v": 5.0,
    "offset_v": 0.0,
    "sample_rate_hz": 1000000,
    "duration_ms": 10,
    "trigger": {
      "enabled": true,
      "source": "ch1",
      "edge": "rising",
      "level_v": 1.6,
      "timeout_ms": 1000
    },
    "return_waveform": false
  }'
```

Metrics in response: `vmin`, `vmax`, `vpp`, `vavg`, `vrms`, `freq_est_hz`,
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
