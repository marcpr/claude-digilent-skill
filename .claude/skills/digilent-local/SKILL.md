# Digilent Local Skill

Use this skill when the user wants to use a Digilent Analog Discovery device
connected **directly via USB to this machine** (not via a Raspberry Pi workbench).

Trigger on: "scope", "oscilloscope", "logic analyzer", "wavegen", "waveform generator",
"analog measurement", "PWM messen", "Spannung messen", "digitale Aktivität",
"digilent", "Analog Discovery", "lokal messen", "measure locally",
"impedance", "protocol decode", "UART", "SPI", "I2C", "CAN", "pattern generator",
"digital I/O", "bode plot", "frequency sweep"

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

**Device capability info:**
```bash
curl -s http://127.0.0.1:7272/api/digilent/capability
```
Returns `analog_in_ch`, `analog_out_ch`, `digital_io_ch`, `digital_out_ch`,
`has_protocols`, `has_supplies`, `has_impedance`, `digital_io_offset`.

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

### Bode sweep (wavegen + scope)

Drive W1 into the DUT; measure CH1 (reference) and CH2 (DUT output).

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "bode_sweep",
    "params": {
      "f_start_hz": 100,
      "f_stop_hz": 100000,
      "steps": 30,
      "amplitude_v": 1.0,
      "ref_channel": 1,
      "dut_channel": 2,
      "range_v": 5.0
    }
  }'
```

Response: `frequencies_hz[]`, `gain_db[]`, `phase_deg[]`, `fc_3db_hz`

### UART loopback test

Connect DIO0 → DIO1 (loopback), or DIO0 → DUT TX / DIO1 → DUT RX.

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "uart_loopback_test",
    "params": {
      "baud": 115200,
      "tx_ch": 0,
      "rx_ch": 1,
      "test_string": "Hello",
      "timeout_s": 1.0
    }
  }'
```

Response: `sent`, `received`, `match`, `bytes_received`, `warnings`

### I2C bus scan

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "i2c_scan",
    "params": {
      "rate_hz": 100000,
      "scl_ch": 0,
      "sda_ch": 1
    }
  }'
```

Response: `devices_found` (list of hex addresses), `count`, `scan_range`

### Characterize power supply

Enables a supply rail and measures its actual output voltage. Requires `--allow-supplies`.

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "characterize_supply",
    "params": {
      "vplus_v": 3.3,
      "enable_vplus": true,
      "scope_channel": 1,
      "scope_range_v": 5.0,
      "settle_ms": 200
    }
  }'
```

Response: `target_vplus_v`, `measured_v`, `ripple_vpp`, `within_tolerance`

### Measure digital signal frequency

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/measure/basic \
  -H "Content-Type: application/json" \
  -d '{
    "action": "digital_frequency",
    "params": {
      "channel": 0,
      "sample_rate_hz": 10000000,
      "duration_samples": 100000,
      "expected_freq_hz": 1000,
      "tolerance_percent": 5.0
    }
  }'
```

Response: `freq_hz`, `duty_cycle_percent`, `edge_count`, `within_tolerance`

---

## Oscilloscope

### Scope capture (free-run — recommended)

**Important:** `scope/capture` with `trigger.enabled: true` consistently returns
HTTP 504 on Analog Discovery 2. Always use free-run mode for raw waveform data.
Use `scope/measure` when you only need metrics and want trigger support.

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

### Scope quick sample (single instantaneous reading per channel)

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/scope/sample \
  -H "Content-Type: application/json" \
  -d '{"channels": [1, 2], "range_v": 5.0}'
```

Returns `samples` dict keyed by channel number: `{"1": 3.28, "2": 0.01}`

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

---

## Logic Analyzer

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

---

## Waveform Generator

```bash
# Start sine wave on CH1
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/set \
  -H "Content-Type: application/json" \
  -d '{
    "channel": 1,
    "waveform": "sine",
    "frequency_hz": 1000,
    "amplitude_v": 1.0,
    "offset_v": 0.0,
    "symmetry_percent": 50,
    "phase_deg": 0.0,
    "enable": true
  }'

# Square wave with duty cycle
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/set \
  -H "Content-Type: application/json" \
  -d '{"channel": 1, "waveform": "square", "frequency_hz": 1000, "amplitude_v": 1.65, "offset_v": 1.65, "symmetry_percent": 50, "enable": true}'

# Custom waveform (normalized -1.0 to +1.0 samples)
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/custom \
  -H "Content-Type: application/json" \
  -d '{"channel": 1, "frequency_hz": 500, "amplitude_v": 1.0, "data": [0,0.5,1,0.5,0,-0.5,-1,-0.5]}'

# Stop
curl -s -X POST http://127.0.0.1:7272/api/digilent/wavegen/stop \
  -H "Content-Type: application/json" \
  -d '{"channel": 1}'
```

Valid waveforms: `sine`, `square`, `triangle`, `dc`, `noise`, `pulse`, `trapezium`, `sinePower`, `custom`

---

## Digital I/O (Pattern Generator + Static IO)

### Configure and read DIO pins

```bash
# Set DIO0 as output high, DIO1 as input
curl -s -X POST http://127.0.0.1:7272/api/digilent/digital-io/configure \
  -H "Content-Type: application/json" \
  -d '{"output_mask": 1, "output_value": 1, "pull_mask": 2}'

# Read all DIO pins
curl -s http://127.0.0.1:7272/api/digilent/digital-io/read

# Write output pins
curl -s -X POST http://127.0.0.1:7272/api/digilent/digital-io/write \
  -H "Content-Type: application/json" \
  -d '{"value": 1, "mask": 3}'
```

`digital-io/read` returns a `pins` dict: `{"0": 1, "1": 0, "2": 0, ...}`

### Static I/O (legacy, single-call set)

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/static-io/set \
  -H "Content-Type: application/json" \
  -d '{"pins": [{"index": 0, "mode": "output", "value": 1}, {"index": 1, "mode": "input"}]}'
```

### Pattern generator

Generate clock/PWM/counter patterns on DIO pins:

```bash
# 1 kHz square wave on DIO0
curl -s -X POST http://127.0.0.1:7272/api/digilent/pattern/set \
  -H "Content-Type: application/json" \
  -d '{
    "channel": 0,
    "type": "clock",
    "frequency_hz": 1000,
    "duty_pct": 50,
    "idle": "low"
  }'

# Stop all patterns
curl -s -X POST http://127.0.0.1:7272/api/digilent/pattern/stop \
  -H "Content-Type: application/json" \
  -d '{}'

# Stop single channel
curl -s -X POST http://127.0.0.1:7272/api/digilent/pattern/stop \
  -H "Content-Type: application/json" \
  -d '{"channel": 0}'
```

Valid pattern types: `clock`, `pulse`, `random`, `custom`, `bfs`
Valid idle states: `low`, `high`, `z` (high-impedance)

**Digital Discovery note:** Channel indices are physical (0-based). The driver
automatically applies the 24-pin offset for Digital Discovery devices.

---

## Impedance Analyzer

### Configure

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/impedance/configure \
  -H "Content-Type: application/json" \
  -d '{
    "freq_hz": 1000,
    "amplitude_v": 0.5,
    "offset_v": 0.0,
    "probe_resistance_ohm": 1000,
    "probe_capacitance_f": 0,
    "min_periods": 16
  }'
```

### Single-frequency measure

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/impedance/measure \
  -H "Content-Type: application/json" \
  -d '{"measurements": ["Impedance", "ImpedancePhase", "Resistance", "Reactance"]}'
```

### Frequency sweep

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/impedance/sweep \
  -H "Content-Type: application/json" \
  -d '{
    "f_start_hz": 100,
    "f_stop_hz": 1000000,
    "steps": 50,
    "amplitude_v": 0.5,
    "probe_resistance_ohm": 1000,
    "measurements": ["Impedance", "ImpedancePhase", "Resistance", "Reactance"]
  }'
```

Returns `{"ok": true, "frequencies": [...], "measurements": {"Impedance": [...], ...}}`

Available measurements: `Impedance`, `ImpedancePhase`, `Resistance`, `Reactance`,
`Admittance`, `AdmittancePhase`, `Conductance`, `Susceptance`,
`SeriesCapacitance`, `ParallelCapacitance`, `SeriesInductance`, `ParallelInductance`,
`Dissipation`, `Quality`

### Open/Short compensation

```bash
curl -s -X POST http://127.0.0.1:7272/api/digilent/impedance/compensation \
  -H "Content-Type: application/json" \
  -d '{"step": "open"}'   # then "short", then "load"
```

---

## Digital Protocols

All protocol endpoints require a device with `has_protocols: true` (Analog Discovery 2,
Digital Discovery). Check with `GET /api/digilent/capability`.

### UART

```bash
# Configure
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/uart/configure \
  -H "Content-Type: application/json" \
  -d '{"baud_rate": 115200, "bits": 8, "parity": "none", "stop_bits": 1.0, "tx_ch": 0, "rx_ch": 1}'

# Send
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/uart/send \
  -H "Content-Type: application/json" \
  -d '{"data": "Hello\r\n"}'

# Receive (with timeout)
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/uart/receive \
  -H "Content-Type: application/json" \
  -d '{"max_bytes": 256, "timeout_s": 2.0}'
```

Valid parity: `none`, `odd`, `even`, `mark`, `space`

### SPI

```bash
# Configure
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/spi/configure \
  -H "Content-Type: application/json" \
  -d '{"freq_hz": 1000000, "mode": 0, "clk_ch": 0, "mosi_ch": 1, "miso_ch": 2, "cs_ch": 3, "cs_idle": 1, "order": "msb"}'

# Transfer (TX and RX in one call)
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/spi/transfer \
  -H "Content-Type: application/json" \
  -d '{"tx_data": [0x01, 0x02, 0x03], "rx_len": 3}'
```

SPI modes 0–3. `order`: `msb` or `lsb`.

### I2C

```bash
# Configure
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/i2c/configure \
  -H "Content-Type: application/json" \
  -d '{"rate_hz": 100000, "scl_ch": 0, "sda_ch": 1}'

# Write to device
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/i2c/write \
  -H "Content-Type: application/json" \
  -d '{"address": 72, "data": [0x00]}'

# Read from device
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/i2c/read \
  -H "Content-Type: application/json" \
  -d '{"address": 72, "length": 2}'

# Write then read (register read pattern)
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/i2c/write-read \
  -H "Content-Type: application/json" \
  -d '{"address": 72, "tx_data": [0x00], "rx_len": 2}'
```

`nak: 0` in the response means the device ACKed; `nak: 1` means no device at that address.

### CAN bus

```bash
# Configure
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/can/configure \
  -H "Content-Type: application/json" \
  -d '{"rate_hz": 500000, "tx_ch": 0, "rx_ch": 1}'

# Send frame
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/can/send \
  -H "Content-Type: application/json" \
  -d '{"id": "0x123", "data": [1, 2, 3, 4], "extended": false, "remote": false}'

# Receive frame (non-blocking)
curl -s -X POST http://127.0.0.1:7272/api/digilent/protocol/can/receive \
  -H "Content-Type: application/json" \
  -d '{"timeout_s": 1.0}'
```

CAN data max 8 bytes. `extended: true` for 29-bit IDs.

---

## Power Supplies (requires `--allow-supplies` flag)

```bash
# Get supply capabilities
curl -s http://127.0.0.1:7272/api/digilent/supplies/info

# Get current supply status
curl -s http://127.0.0.1:7272/api/digilent/supplies/status

# Set and enable V+
curl -s -X POST http://127.0.0.1:7272/api/digilent/supplies/set \
  -H "Content-Type: application/json" \
  -d '{"vplus_v": 3.3, "enable_vplus": true, "confirm_unsafe": true}'

# Master enable / disable
curl -s -X POST http://127.0.0.1:7272/api/digilent/supplies/master \
  -H "Content-Type: application/json" \
  -d '{"master_enable": true}'
```

AD2 supply range: V+ 0–5 V, V− 0 to −5 V.

---

## Analysis Tools (CLI scripts)

### Waveform Export (PNG, CSV, Markdown)

```bash
python tools/plot_waveform.py \
  --channels 1 2 \
  --rate 200000 \
  --duration 10 \
  --range 5.0 \
  --out /tmp/capture
```

Produces `/tmp/capture.png`, `/tmp/capture.csv`, `/tmp/capture.md`.

Key options: `--channels N [N...]`, `--rate HZ`, `--duration MS`, `--range V`, `--out PATH`

For high-frequency signals (≥ 10 kHz): `--rate 10000000 --duration 0.1`

### FFT Analysis

```bash
python tools/fft_analyze.py \
  --channel 1 \
  --rate 1000000 \
  --duration 5 \
  --range 5.0 \
  --out /tmp/fft
```

Produces `/tmp/fft.png` (two-panel: amplitude + dBFS) and `/tmp/fft.md`
(fundamental, harmonics H2–H10, THD, SFDR).

### Impedance Sweep (DUT characterization)

Runs a log-spaced frequency sweep using the built-in impedance analyzer.
Classifies DUT as resistor / capacitor / inductor / RC / RL / complex.

**Wiring:** W1+ → probe resistor → DUT → GND; C1+ at DUT node; C1− at GND.

```bash
python tools/impedance_sweep.py \
  --fstart 100 \
  --fstop 1000000 \
  --steps 100 \
  --amplitude 0.5 \
  --probe-r 1000 \
  --out results/sweep
```

Produces:
- `results/sweep.csv` — frequency, impedance, phase, resistance, reactance
- `results/sweep.png` — two-panel Bode chart (|Z| dBΩ + phase °)
- `results/sweep.md` — DUT classification, estimated value, key metrics table

Key options:
```
--fstart HZ          Start frequency (default: 100)
--fstop HZ           Stop frequency (default: 1000000)
--steps N            Log-spaced steps (default: 100)
--amplitude V        Excitation amplitude (default: 0.5)
--probe-r OHM        Probe resistor value (default: 1000)
--probe-c F          Probe parasitic capacitance (default: 0)
--measurements ...   Space-separated measurement names
--out PATH           Output stem (no extension)
```

### Protocol Capture & Decode

Captures a digital protocol bus, formats as hex+ASCII dump, writes Markdown report.

```bash
# UART capture at 115200 baud, 2 seconds
python tools/protocol_decode.py uart \
  --baud 115200 --tx 0 --rx 1 --duration 2.0 --out uart_capture

# I2C bus scan at 100 kHz
python tools/protocol_decode.py i2c \
  --rate 100000 --scl 0 --sda 1 --duration 1.0 --out i2c_capture

# SPI test-pattern transfer at 1 MHz
python tools/protocol_decode.py spi \
  --freq 1000000 --clk 0 --mosi 1 --miso 2 --cs 3 --out spi_capture

# CAN bus capture at 500 kbps
python tools/protocol_decode.py can \
  --rate 500000 --tx 0 --rx 1 --duration 2.0 --out can_capture
```

Produces `<out>.hex` (hex+ASCII dump) and `<out>.md` (Markdown report with frame table).

### DUT Identification (Bode Plot — Scope + Wavegen)

```bash
python tools/dut_identify.py \
  --fstart 100 \
  --fstop 500000 \
  --steps 40 \
  --amplitude 1.0 \
  --out /tmp/bode
```

**Wiring:** W1 → DUT input → CH1 (ref); DUT output → CH2 (response).

Produces `/tmp/bode.png` (gain + phase) and `/tmp/bode_report.md`
(classification: `low_pass`, `high_pass`, `band_pass`, `notch`, `amplifier`; fc, rolloff, passband gain).

---

## Error Handling

Always check `ok` and `error.code` in the response:

| HTTP | `error.code` | Meaning | Action |
|------|-------------|---------|--------|
| 400 | `DIGILENT_CONFIG_INVALID` | Bad parameter | Fix the request |
| 400 | `DIGILENT_RANGE_VIOLATION` | Value exceeds safe limit | Reduce amplitude/rate |
| 403 | `DIGILENT_NOT_ENABLED` | Feature disabled | Use `--allow-supplies` flag |
| 405 | `DIGILENT_NOT_AVAILABLE` | Hardware lacks capability | Check `/api/digilent/capability` |
| 409 | `DIGILENT_BUSY` | Concurrent request | Wait and retry |
| 422 | `DIGILENT_DWF_ERROR` | WaveForms SDK error | Check wiring; call session/reset |
| 500 | `DIGILENT_INTERNAL` | Unexpected server error | Check server log |
| 503 | `DIGILENT_NOT_FOUND` | No device | Check USB, call device/open |
| 504 | `DIGILENT_CAPTURE_TIMEOUT` | Trigger never fired | Disable trigger or check signal |

---

## Safety Rules

1. **Scope and Logic**: read-only, safe to use freely
2. **Wavegen**: always warn the user before enabling — amplitude must be safe for the connected circuit; stop with `wavegen/stop` when done
3. **Pattern generator**: outputs are 3.3 V logic levels; do not connect directly to 5 V or higher logic without level-shifter
4. **Supplies**: disabled by default — start server with `--allow-supplies` and always use `confirm_unsafe: true`; do not exceed rated current (100 mA per rail)
5. **Impedance analyzer**: excitation amplitude ≤ 1 V recommended for passive DUTs; do not use on powered circuits
6. **Protocol TX pins**: UART/SPI/I2C/CAN drive the DIO pins as outputs — verify voltage compatibility before connecting
7. Request raw waveforms (`return_waveform: true`) only when explicitly needed
8. **WaveForms GUI**: must be closed while the server is running (exclusive USB access)

---

## Wiring Reference

### Standard passive observation
```
Analog Discovery GND  →  DUT GND   (mandatory)
Scope CH1+           →  Signal to measure
Scope CH1-           →  GND (or differential signal)
Logic DIO0           →  Digital line (e.g. UART TX)
Logic DIO1           →  Digital line (e.g. UART RX)
```

### Impedance sweep
```
W1+   →  probe-R (1 kΩ)  →  DUT (+)
C1+   →  DUT (+) node
C1−   →  DUT (−) / GND
DUT (−)  →  GND
```

### Bode sweep (DUT Identification)
```
W1    →  DUT input
CH1+  →  DUT input  (reference)
CH2+  →  DUT output (response)
GND   →  Common GND
```

### Protocol wiring
```
DIO0 (TX/SCL/CLK)  →  DUT RX/SDA/SCL (match protocol)
DIO1 (RX/SDA/MOSI) →  DUT TX/SCL/SDA
DIO2 (MISO)        →  DUT MISO  (SPI only)
DIO3 (CS)          →  DUT CS    (SPI only)
GND                →  DUT GND
```

**Voltage levels:** Analog Discovery 2 DIO logic levels are 3.3 V. Use level-shifters for 5 V devices.

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
| `405 DIGILENT_NOT_AVAILABLE` | No hardware capability | Check `/api/digilent/capability`; wrong device? |
| `503` from server start | libdwf not found | Run `python tools/digilent_local_setup.py` |
| `UART receive timeout` | No data on RX | Check wiring, baud rate, TX→RX loopback |
| `I2C NAK on all addresses` | Wrong wiring or bus conflict | Check SCL/SDA; add pull-ups (4.7 kΩ to 3.3 V) |
| WaveForms GUI won't open | Server holds device | Stop server first (kill / Ctrl-C) |
| Trigger timeout | Signal not present | Set `trigger.enabled: false` for free-run |
| Pattern output wrong frequency | Divider rounding | Use power-of-2 frequencies for best accuracy |
