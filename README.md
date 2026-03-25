# claude-digilent-skill

A Claude Code skill and local HTTP server for using a **Digilent Analog Discovery** (or compatible WaveForms device) directly from your development machine — no Raspberry Pi required.

The server exposes the device over a local HTTP API at `http://127.0.0.1:7272`. Claude Code interacts with it via `curl` calls, giving it full access to the oscilloscope, logic analyzer, waveform generator, pattern generator, impedance analyzer, digital protocols (UART/SPI/I2C/CAN), power supplies, and digital I/O.

---

## Quick Start

### 1. Install WaveForms

Download and install from [digilent.com](https://digilent.com/reference/software/waveforms/waveforms-3/start) (provides `libdwf.so` / `dwf.dll` / `dwf.framework`).

### 2. Clone this repo

```bash
git clone https://github.com/marcpr/claude-digilent-skill.git
cd claude-digilent-skill
```

No additional Python packages are required for the server — it uses the standard library only.

The optional analysis tools require:

```bash
pip install numpy matplotlib scipy
```

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

Claude Code will now trigger the `digilent-local` skill automatically when you ask about scopes, oscilloscopes, PWM measurements, logic analysis, impedance, UART/SPI/I2C/CAN, etc.

Or use the API directly with `curl`:

```bash
# Check status
curl -s http://127.0.0.1:7272/api/digilent/status

# Measure PWM
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{"action": "measure_esp32_pwm", "params": {"channel": 1, "expected_freq_hz": 1000}}'

# I2C bus scan
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{"action": "i2c_scan", "params": {"rate_hz": 100000, "scl_ch": 0, "sda_ch": 1}}'
```

---

## Platform Support

| Platform | Library location |
|----------|-----------------|
| Linux x86-64 | `/usr/lib/libdwf.so` (via WaveForms `.deb`) |
| Linux ARM64 (Raspberry Pi 4 / ADP3x) | `/usr/lib/aarch64-linux-gnu/libdwf.so` |
| macOS Intel | `/Library/Frameworks/dwf.framework/dwf` |
| macOS Apple Silicon | Same — requires WaveForms ≥ 3.21.2 (universal binary) |
| Windows | `C:\Windows\System32\dwf.dll` (via WaveForms installer) |

---

## API Reference

All endpoints are under `http://127.0.0.1:7272/api/digilent/`.

### Device and session

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ping` | Health check |
| GET | `/status` | Device state, name, temperature |
| GET | `/capability` | Full capability record for connected device |
| POST | `/device/open` | Open USB device |
| POST | `/device/close` | Close USB device |
| POST | `/session/reset` | Force-close and reset after error |

### Oscilloscope

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scope/capture` | Analog capture; returns raw waveform when `return_waveform: true` |
| POST | `/scope/measure` | Metrics only; supports trigger reliably |
| POST | `/scope/sample` | Instantaneous single-sample read per channel |

### Logic Analyzer

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/logic/capture` | Digital channel capture |

### Waveform Generator

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/wavegen/set` | Configure and start waveform (sine, square, triangle, dc, noise, custom, …) |
| POST | `/wavegen/stop` | Stop waveform generator |
| POST | `/wavegen/custom` | Upload custom waveform data |

### Digital I/O and Pattern Generator

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/digital-io/configure` | Set output mask, output value, pull mask |
| GET | `/digital-io/read` | Read all DIO pin states |
| POST | `/digital-io/write` | Drive output pins |
| POST | `/pattern/set` | Start clock/PWM/random/custom pattern on a DIO channel |
| POST | `/pattern/stop` | Stop pattern output (all channels or single) |
| POST | `/static-io/set` | Legacy: set/read pins in one call |

### Power Supplies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/supplies/info` | List supply channels and their voltage ranges |
| GET | `/supplies/status` | Read current voltage/current from all supply monitors |
| POST | `/supplies/set` | Set one supply channel voltage and enable/disable |
| POST | `/supplies/master` | Master enable/disable (all rails at once) |

Requires `--allow-supplies` server flag.

### Impedance Analyzer

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/impedance/configure` | Set frequency, amplitude, probe resistance/capacitance |
| POST | `/impedance/measure` | Single-frequency measurement (returns named quantities) |
| POST | `/impedance/sweep` | Log-spaced frequency sweep; returns arrays of all measurements |
| POST | `/impedance/compensation` | Open/short/load calibration step |

Requires `has_impedance: true` or uses scope+wavegen path for non-IA devices.

### Digital Protocols

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/protocol/uart/configure` | Configure UART (baud, bits, parity, stop bits, TX/RX pins) |
| POST | `/protocol/uart/send` | Send string data |
| POST | `/protocol/uart/receive` | Receive with timeout |
| POST | `/protocol/spi/configure` | Configure SPI (freq, mode, CLK/MOSI/MISO/CS pins) |
| POST | `/protocol/spi/transfer` | Full-duplex TX/RX |
| POST | `/protocol/i2c/configure` | Configure I2C (rate, SCL/SDA pins) |
| POST | `/protocol/i2c/write` | Write to device address |
| POST | `/protocol/i2c/read` | Read from device address |
| POST | `/protocol/i2c/write-read` | Write then read (register read pattern) |
| POST | `/protocol/can/configure` | Configure CAN (bit rate, TX/RX pins) |
| POST | `/protocol/can/send` | Send CAN frame |
| POST | `/protocol/can/receive` | Receive CAN frame (with timeout) |

Requires `has_protocols: true`. See `docs/device-capabilities.md`.

### High-level actions (`measure/basic`)

| Action | Description |
|--------|-------------|
| `measure_esp32_pwm` | Measure PWM frequency and duty cycle |
| `measure_voltage_level` | Measure DC/slow voltage, check tolerance |
| `detect_logic_activity` | Detect edge activity on digital channels |
| `bode_sweep` | Wavegen + scope frequency sweep; returns gain/phase arrays and −3 dB point |
| `uart_loopback_test` | Configure UART, send string, receive back, check match |
| `i2c_scan` | Scan I2C bus (0x08–0x77), return responding addresses |
| `characterize_supply` | Enable supply, measure output voltage with scope |
| `digital_frequency` | Measure frequency of a digital signal on a DIO channel |

---

## Analysis Tools

Standalone Python scripts for offline analysis. All require `pip install numpy matplotlib scipy` except `protocol_decode.py` (stdlib only).

### plot_waveform.py — Waveform export

Captures raw scope data and saves as PNG, CSV, and Markdown report.

```bash
python tools/plot_waveform.py --channels 1 2 --rate 200000 --duration 10 --out /tmp/capture
```

Output: `capture.png`, `capture.csv`, `capture.md`

### fft_analyze.py — Spectral analysis

Runs a Hanning-windowed FFT. Detects fundamental, harmonics H2–H10, THD, SFDR.

```bash
python tools/fft_analyze.py --channel 1 --rate 1000000 --duration 5 --out /tmp/fft
```

Output: `fft.png` (linear + dB panels), `fft.md`

### impedance_sweep.py — DUT characterization

Log-spaced frequency sweep using the impedance analyzer (or scope+wavegen on devices without a dedicated IA). Classifies DUT as resistor / capacitor / inductor / RC / RL / complex and estimates component value.

**Wiring:** W1+ → probe-R → DUT → GND; C1+ at DUT node; C1− at GND.

```bash
python tools/impedance_sweep.py \
  --fstart 100 --fstop 1000000 --steps 100 \
  --amplitude 0.5 --probe-r 1000 --out results/sweep
```

Output: `sweep.csv`, `sweep.png` (|Z| dBΩ + phase Bode chart), `sweep.md`

### protocol_decode.py — Protocol capture and decode

Captures a digital protocol bus, writes hex+ASCII dump and Markdown report.

```bash
python tools/protocol_decode.py uart --baud 115200 --tx 0 --rx 1 --duration 2.0 --out uart_capture
python tools/protocol_decode.py i2c  --rate 100000 --scl 0 --sda 1 --out i2c_capture
python tools/protocol_decode.py spi  --freq 1000000 --clk 0 --mosi 1 --miso 2 --cs 3 --out spi_capture
python tools/protocol_decode.py can  --rate 500000 --tx 0 --rx 1 --duration 2.0 --out can_capture
```

Output: `<out>.hex` (hex+ASCII dump), `<out>.md` (Markdown report with frame table)

### dut_identify.py — Bode sweep via scope + wavegen

Automated frequency sweep and DUT filter classification.

**Wiring:** `W1 → DUT input → CH1` (reference), `DUT output → CH2` (response)

```bash
python tools/dut_identify.py --fstart 100 --fstop 500000 --steps 40 --amplitude 1.0 --out /tmp/bode
```

Output: `bode.png` (gain + phase), `bode_report.md` (type, fc, roll-off)

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
    "max_wavegen_amplitude_v": 5.0,
    "max_impedance_sweep_amplitude_v": 1.0
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
| `DIGILENT_NOT_ENABLED` | 403 | Feature disabled (e.g. supplies without `--allow-supplies`) |
| `DIGILENT_NOT_AVAILABLE` | 405 | Instrument not present on this device |
| `DIGILENT_DWF_ERROR` | 422 | WaveForms SDK returned an error |
| `DIGILENT_INTERNAL` | 500 | Unexpected server error |
| `DIGILENT_CAPTURE_TIMEOUT` | 504 | Acquisition did not complete (trigger never fired) |

---

## Safety Notes

- **WaveForms GUI must be closed** while the server is running — both compete for exclusive USB access
- **Supplies are disabled by default** — pass `--allow-supplies` to enable, and always send `confirm_unsafe: true` in the request body
- **Wavegen amplitudes** are server-validated against `safe_limits.max_wavegen_amplitude_v`
- **Impedance excitation** ≤ 1 V recommended; do not use on powered circuits
- **Protocol TX pins** drive DIO lines as outputs — verify voltage compatibility before connecting
- **Scope and Logic** are read-only instruments — safe to use freely

---

## Project Structure

```
claude-digilent-skill/
├── digilent/                      Python package — instrument services
│   ├── dwf_adapter.py             ctypes wrapper (Linux, macOS, Windows)
│   ├── device_manager.py          Exclusive session + state machine
│   ├── capability_registry.py     Static capability table (12 device types)
│   ├── scope_service.py           Oscilloscope capture and metrics
│   ├── logic_service.py           Logic analyzer
│   ├── wavegen_service.py         Waveform generator
│   ├── supplies_service.py        Power supplies + static I/O
│   ├── digital_io_service.py      Digital I/O (configure/read/write)
│   ├── pattern_service.py         Pattern generator (clock/PWM/random/custom)
│   ├── impedance_service.py       Impedance analyzer (single + sweep)
│   ├── protocol_service.py        UART / SPI / I2C / CAN
│   ├── orchestration.py           High-level agent actions (8 actions)
│   ├── api.py                     HTTP dispatch (45+ endpoints)
│   ├── config.py                  Config loader (platform-aware default path)
│   ├── models.py                  Request/response dataclasses
│   ├── errors.py                  Typed error hierarchy
│   └── utils.py                   Metric calculation, downsampling
├── tools/
│   ├── digilent_local_server.py   Local HTTP server (main entry point)
│   ├── digilent_local_setup.py    Setup verification script
│   ├── plot_waveform.py           Capture → PNG + CSV + Markdown report
│   ├── fft_analyze.py             FFT analysis → spectrum PNG + Markdown report
│   ├── dut_identify.py            Automated Bode sweep + DUT classification
│   ├── impedance_sweep.py         Impedance frequency sweep + DUT classification
│   ├── protocol_decode.py         Protocol capture → hex dump + Markdown report
│   └── lab_report_plots.py        Helper: regenerate lab report plots from data
├── docs/
│   ├── device-capabilities.md     Device capability reference table
│   ├── integration-guide.md       Integration reference for all instruments
│   └── extending-waveform-export.md  Developer guide for analysis tools
├── tests/
│   ├── test_digilent_api.py       API integration tests (168 tests)
│   ├── test_orchestration_service.py  Orchestration action tests (18 tests)
│   ├── test_capability_registry.py
│   ├── test_digital_io_service.py
│   ├── test_impedance_service.py
│   ├── test_pattern_service.py
│   └── test_protocol_service.py
└── .claude/
    └── skills/
        └── digilent-local/
            └── SKILL.md           Claude Code skill definition
```

---

## Running the Tests

No hardware required — all tests mock the DWF library:

```bash
python -m pytest tests/ -v
# 186 tests, 0 failures
```

---

## Known Limitations

| Issue | Workaround |
|-------|-----------|
| `scope/capture` with `trigger.enabled: true` → HTTP 504 on AD2 | Use `trigger: {enabled: false}` (free-run) for raw captures |
| `scope/measure` trigger works but returns no raw waveform | Use `scope/capture` free-run when samples are needed |
| Buffer overflow at high sample rates (AD2) | 10 MS/s → max ~0.1 ms; 1 MS/s → max ~5 ms; 200 kHz → max ~50 ms |
| Server returns `"channel": 1` (int), not `"channel": "ch1"` | Normalize: `f"ch{ch['channel']}" if isinstance(ch['channel'], int)` |
| Digital Discovery DIO channels offset by 24 | Handled automatically by `digital_io_service.py` — use physical channel 0-based indices |
| ADP5250 supports only I2C/SPI (no UART, no CAN) | Check `capability.has_protocols` and device notes |
| Impedance mode (ADS Max) is mutually exclusive with scope/wavegen | Disable impedance before using scope or wavegen |

---

## Relation to Universal-ESP32-Workbench

This repo is a standalone extraction of the Digilent extension originally developed for the [Universal-ESP32-Workbench](https://github.com/marcpr/Universal-ESP32-Workbench). The workbench provides the same API via a Raspberry Pi over the network (`http://esp32-workbench.local:8080/api/digilent/*`). This repo targets direct local USB access from a developer's machine.

The `digilent/` package is shared code — the same Python modules work in both contexts.

---

## License

MIT
