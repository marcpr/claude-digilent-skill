# claude-digilent-skill

A Claude Code skill and local HTTP server for using a **Digilent Analog Discovery** (or compatible WaveForms device) directly from your development machine — no Raspberry Pi required.

The server exposes the device over a local HTTP API at `http://127.0.0.1:7272`. Claude Code interacts with it via `curl` calls, giving it full access to the oscilloscope, logic analyzer, waveform generator, power supplies, and static I/O.

---

## Quick Start

### 1. Install WaveForms

Download and install from [digilent.com](https://digilent.com/reference/software/waveforms/waveforms-3/start) (provides `libdwf.so` / `dwf.dll` / `dwf.framework`).

### 2. Clone this repo

```bash
git clone https://github.com/marcpr/claude-digilent-skill.git
cd claude-digilent-skill
```

No additional Python packages are required — the server uses the standard library only.

### 3. Verify setup

```bash
python tools/digilent_local_setup.py
```

```
[OK]  Python 3.11.4
[OK]  WaveForms SDK (dwf library)  (/usr/lib/libdwf.so)
[OK]  Device detected (1 found)  (Analog Discovery 2)

✓  All checks passed.

Start the local server with:
    python tools/digilent_local_server.py
```

### 4. Start the server

```bash
python tools/digilent_local_server.py
```

```
[digilent-local] Server listening on http://127.0.0.1:7272
[digilent-local] Device: Analog Discovery 2 (open)
[digilent-local] Press Ctrl+C to stop
```

### 5. Use with Claude Code

Link the skill into your project:

```bash
mkdir -p .claude
ln -s /path/to/claude-digilent-skill/.claude/skills .claude/skills
```

Claude Code will now trigger the `digilent-local` skill automatically when you ask about scopes, oscilloscopes, PWM measurements, logic analysis, etc.

Or use the API directly with `curl`:

```bash
# Check status
curl -s http://127.0.0.1:7272/api/digilent/status

# Measure PWM
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{"action": "measure_esp32_pwm", "params": {"channel": 1, "expected_freq_hz": 1000}}'
```

---

## Platform Support

| Platform | Library location |
|----------|-----------------|
| Linux x86-64 | `/usr/lib/libdwf.so` (via WaveForms `.deb`) |
| Linux ARM (Raspberry Pi) | `/usr/lib/aarch64-linux-gnu/libdwf.so` |
| macOS Intel | `/Library/Frameworks/dwf.framework/dwf` |
| macOS Apple Silicon | Same — requires WaveForms ≥ 3.21.2 (universal binary) |
| Windows | `C:\Windows\System32\dwf.dll` (via WaveForms installer) |

---

## API Reference

All endpoints are under `http://127.0.0.1:7272/api/digilent/`.

### Status and device lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/digilent/ping` | Health check — returns `{"ok": true, "server": "digilent-local"}` |
| GET | `/api/digilent/status` | Device state, name, temperature, capabilities |
| POST | `/api/digilent/device/open` | Open USB device |
| POST | `/api/digilent/device/close` | Close USB device |
| POST | `/api/digilent/session/reset` | Force-close and reset after error |

### Measurements

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/scope/capture` | Analog capture with optional trigger and waveform data |
| POST | `/api/digilent/scope/measure` | Like capture, always suppresses raw waveform |
| POST | `/api/digilent/logic/capture` | Digital channel capture |
| POST | `/api/digilent/measure/basic` | Agent-friendly high-level action |

### Stimulus

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/wavegen/set` | Configure and start waveform generator |
| POST | `/api/digilent/wavegen/stop` | Stop waveform generator |
| POST | `/api/digilent/static-io/set` | Drive or read digital I/O pins |
| POST | `/api/digilent/supplies/set` | Set power supply voltages (requires `--allow-supplies`) |

### High-level actions (`measure/basic`)

| Action | Description |
|--------|-------------|
| `measure_esp32_pwm` | Measure PWM frequency and duty cycle, check against tolerance |
| `measure_voltage_level` | Measure DC/slow voltage, check against expected value |
| `detect_logic_activity` | Detect edge activity on digital channels |

---

## Server Options

```
python tools/digilent_local_server.py [OPTIONS]

  --port PORT          TCP port (default: 7272)
  --host HOST          Bind address (default: 127.0.0.1)
  --no-auto-open       Do not open device at startup
  --allow-supplies     Enable power supply endpoints
  --config PATH        Path to JSON config file
```

### Config file (optional)

Create `~/.config/digilent-local/config.json` (Linux/macOS) or
`%APPDATA%\digilent-local\config.json` (Windows):

```json
{
  "auto_open": true,
  "allow_supplies": false,
  "max_scope_points": 20000,
  "max_logic_points": 100000,
  "safe_limits": {
    "max_scope_sample_rate_hz": 50000000,
    "max_wavegen_amplitude_v": 5.0
  },
  "labels": {
    "scope_ch1": "DUT_SIGNAL",
    "logic_dio0": "UART_TX"
  }
}
```

---

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `DIGILENT_NOT_FOUND` | 503 | No device connected (or WaveForms GUI is open) |
| `DIGILENT_BUSY` | 409 | Concurrent request rejected |
| `DIGILENT_CONFIG_INVALID` | 400 | Bad parameter value |
| `DIGILENT_RANGE_VIOLATION` | 400 | Value exceeds configured safe limit |
| `DIGILENT_NOT_ENABLED` | 403 | Feature disabled (e.g. supplies) |
| `DIGILENT_CAPTURE_TIMEOUT` | 504 | Acquisition did not complete |

---

## Safety Notes

- **WaveForms GUI must be closed** while the server is running — both compete for exclusive USB access
- **Supplies are disabled by default** — pass `--allow-supplies` to enable, and always send `confirm_unsafe: true` in the request body
- **Wavegen amplitudes** are server-validated against `safe_limits.max_wavegen_amplitude_v`
- **Scope and Logic** are read-only instruments — safe to use freely

---

## Project Structure

```
claude-digilent-skill/
├── digilent/                   Python package — instrument services
│   ├── dwf_adapter.py          ctypes wrapper (Linux, macOS, Windows)
│   ├── device_manager.py       Exclusive session + state machine
│   ├── scope_service.py        Oscilloscope capture and metrics
│   ├── logic_service.py        Logic analyzer
│   ├── wavegen_service.py      Waveform generator
│   ├── supplies_service.py     Power supplies + static I/O
│   ├── orchestration.py        High-level agent actions
│   ├── api.py                  HTTP dispatch
│   ├── config.py               Config loader (platform-aware default path)
│   ├── models.py               Request/response dataclasses
│   ├── errors.py               Typed error hierarchy
│   └── utils.py                Metric calculation, downsampling
├── tools/
│   ├── digilent_local_server.py   Local HTTP server (main entry point)
│   └── digilent_local_setup.py    Setup verification script
├── tests/
│   └── test_digilent_api.py    40 unit tests (mock-based, no hardware needed)
└── .claude/
    └── skills/
        └── digilent-local/
            └── SKILL.md        Claude Code skill definition
```

---

## Running the Tests

No hardware required — all tests mock the DWF library:

```bash
python -m pytest tests/ -v
```

---

## Relation to Universal-ESP32-Workbench

This repo is a standalone extraction of the Digilent extension originally developed for the [Universal-ESP32-Workbench](https://github.com/marcpr/Universal-ESP32-Workbench). The workbench provides the same API via a Raspberry Pi over the network (`http://esp32-workbench.local:8080/api/digilent/*`). This repo targets direct local USB access from a developer's machine.

The `digilent/` package is shared code — the same Python modules work in both contexts.

---

## License

MIT
