# Integration Guide

Reference documentation for all instruments, analysis tools, and API endpoints.

---

## Contents

1. [Universal Device Detection](#universal-device-detection)
2. [Oscilloscope](#oscilloscope)
3. [Logic Analyzer](#logic-analyzer)
4. [Waveform Generator](#waveform-generator)
5. [Digital I/O and Pattern Generator](#digital-io-and-pattern-generator)
6. [Power Supplies](#power-supplies)
7. [Impedance Analyzer](#impedance-analyzer)
8. [Digital Protocols (UART / SPI / I2C / CAN)](#digital-protocols)
9. [High-level Orchestration Actions](#high-level-orchestration-actions)
10. [Analysis Tools](#analysis-tools)
11. [Known Limitations](#known-limitations)

---

## Universal Device Detection

The server identifies the connected device using `FDwfEnumDeviceType` and
looks up the matching `CapabilityRecord` in `capability_registry.py`.

```bash
curl -s http://127.0.0.1:7272/api/digilent/capability
```

```json
{
  "ok": true,
  "devid": 3,
  "name": "Analog Discovery 2",
  "analog_in_ch": 2,
  "analog_out_ch": 2,
  "digital_in_ch": 16,
  "digital_out_ch": 16,
  "digital_io_ch": 16,
  "digital_io_offset": 0,
  "has_impedance": false,
  "has_protocols": true,
  "has_dmm": false,
  "has_power_supply": true,
  "max_scope_rate_hz": 100000000,
  "max_scope_buffer": 8192,
  "max_logic_rate_hz": 100000000,
  "max_logic_buffer": 16384,
  "supply_channels": [...]
}
```

When an instrument is not available on the connected device (e.g. requesting
impedance on an Analog Discovery 2), the server returns HTTP 405:

```json
{
  "ok": false,
  "error": {
    "code": "DIGILENT_NOT_AVAILABLE",
    "message": "This device does not support impedance analysis"
  }
}
```

See `docs/device-capabilities.md` for the full per-device capability table.

---

## Oscilloscope

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /scope/capture` | Full capture with optional raw waveform data |
| `POST /scope/measure` | Metrics only, trigger supported reliably |
| `POST /scope/sample` | Instantaneous single-sample per channel |
| `POST /scope/record` | Streaming long capture (record mode) |

### scope/capture

**Important for Analog Discovery 2:** `scope/capture` with `trigger.enabled: true`
consistently returns HTTP 504. Always use free-run mode for raw waveform data.

**Buffer limits:**

| Sample rate | Max reliable duration |
|-------------|----------------------|
| 10 MS/s | 0.1 ms |
| 1 MS/s | 5 ms |
| 200 kHz | 50 ms |

```json
{
  "channels": [1, 2],
  "range_v": 5.0,
  "offset_v": 0.0,
  "sample_rate_hz": 200000,
  "duration_ms": 10,
  "trigger": {"enabled": false},
  "return_waveform": true
}
```

Response includes `metrics` (per channel: `vmin`, `vmax`, `vpp`, `vavg`, `vrms`,
`freq_est_hz`, `duty_cycle_percent`) and, when `return_waveform: true`,
a `waveform` array.

**Channel normalization:** The server returns `"channel": 1` (integer).
Normalize with: `f"ch{ch['channel']}" if isinstance(ch['channel'], int) else ch['channel']`

### scope/sample

Quick single reading. Useful for DC voltage monitoring without a full capture.

```json
{"channels": [1, 2], "range_v": 5.0}
```

Returns: `{"ok": true, "samples": {"1": 3.28, "2": 0.01}}`

### scope/record

Use for captures longer than the device buffer allows (several hundred ms to
minutes). Internally uses FDwfAnalogIn record mode (acqmodeRecord=3) which
continuously streams samples to host RAM instead of the on-device buffer.

```json
{
  "channels": [1],
  "range_v": 5.0,
  "offset_v": 0.0,
  "sample_rate_hz": 100000,
  "duration_ms": 500,
  "trigger": {
    "enabled": true,
    "source": "ch1",
    "edge": "rising",
    "level_v": 1.0,
    "auto_timeout_s": 2.0
  },
  "return_waveform": true
}
```

Response extra fields vs `scope/capture`:

| Field | Type | Description |
|-------|------|-------------|
| `samples_valid` | int | Samples actually collected |
| `samples_lost` | int | Samples dropped due to host CPU lag |
| `samples_corrupted` | int | Corrupted samples flagged by hardware |

Non-zero `samples_lost` means the host cannot keep up at the requested sample
rate. Reduce `sample_rate_hz` or close other processes.

**Comparison:**

| | `scope/capture` | `scope/record` |
|---|---|---|
| Max duration | ~1 s at 1 MS/s | Minutes (host RAM) |
| Trigger types | edge / pulse / transition / window | edge only |
| Lost-sample detection | No | Yes |

---

## Logic Analyzer

### Endpoint

`POST /logic/capture`

```json
{
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
}
```

Metrics per channel: `high_ratio`, `low_ratio`, `edge_count`,
`freq_est_hz`, `duty_cycle_percent`.

**Digital Discovery:** supports 800 MS/s with a 1 GiB sample buffer.
Channels are 0-indexed physical channels — the server applies the 24-pin
offset automatically.

---

## Waveform Generator

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /wavegen/set` | Configure and start |
| `POST /wavegen/stop` | Stop output |
| `POST /wavegen/custom` | Upload custom waveform |

### wavegen/set

```json
{
  "channel": 1,
  "waveform": "sine",
  "frequency_hz": 1000,
  "amplitude_v": 1.0,
  "offset_v": 0.0,
  "symmetry_percent": 50,
  "phase_deg": 0.0,
  "enable": true
}
```

Valid waveforms: `sine`, `square`, `triangle`, `dc`, `noise`, `pulse`,
`trapezium`, `sinePower`, `custom`

### wavegen/custom

Upload normalized (−1.0 to +1.0) sample array:

```json
{
  "channel": 1,
  "frequency_hz": 500,
  "amplitude_v": 1.0,
  "data": [0, 0.5, 1.0, 0.5, 0, -0.5, -1.0, -0.5]
}
```

**Settle time:** Wait at least 3 periods (50 ms minimum) after `wavegen/set`
before capturing to allow the output to settle.

---

## Digital I/O and Pattern Generator

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /digital-io/configure` | Set output mask, initial values, pull-ups |
| `GET /digital-io/read` | Read all DIO pin states |
| `POST /digital-io/write` | Drive output pins |
| `POST /pattern/set` | Start pattern on a DIO channel |
| `POST /pattern/stop` | Stop pattern (all or single channel) |
| `POST /static-io/set` | Legacy: configure pins in one call |

### digital-io/configure

```json
{
  "output_mask": 3,
  "output_value": 1,
  "pull_mask": 0
}
```

`output_mask`: bitmask of pins configured as outputs (bit 0 = DIO0).
`output_value`: initial state for output pins.
`pull_mask`: pins with pull-up enabled.

### digital-io/read

`GET /digital-io/read` — returns `{"pins": {"0": 1, "1": 0, "2": 0, ...}}`

### digital-io/write

```json
{"value": 1, "mask": 3}
```

Only the bits set in `mask` are modified.

### pattern/set

```json
{
  "channel": 0,
  "type": "clock",
  "frequency_hz": 1000,
  "duty_pct": 50,
  "idle": "low",
  "run_count": 0,
  "repeat_count": 0
}
```

Valid types: `clock`, `pulse`, `random`, `custom`, `bfs`
Valid idle states: `low`, `high`, `z` (high-impedance)

`run_count: 0` = run forever. `repeat_count: 0` = repeat forever.

For `custom` and `bfs` types, include `custom_data` (list of 0/1 values).

**Digital Discovery note:** The server automatically applies the channel index
offset of 24. Use physical channel numbers (0-based).

**Voltage levels:** All DIO outputs are 3.3 V logic. For 5 V targets, use a
level-shifter.

---

## Power Supplies

Requires `--allow-supplies` server flag.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /supplies/info` | Available supply channels with voltage ranges |
| `GET /supplies/status` | Current voltage/current readings |
| `POST /supplies/set` | Set voltage for one channel |
| `POST /supplies/master` | Master enable/disable |

### supplies/info

Returns the `supply_channels` array from the device's `CapabilityRecord`:
channel name, voltage range, capability flags (`has_enable`, `has_voltage_set`,
`has_current_limit`, `has_voltage_monitor`, `has_current_monitor`).

### supplies/set

```json
{
  "channel_name": "V+",
  "voltage_v": 3.3,
  "enable": true,
  "confirm_unsafe": true
}
```

`confirm_unsafe: true` is required for all supply write operations.

### supplies/master

```json
{"enable": true, "confirm_unsafe": true}
```

### Legacy supplies/set (backward compat)

The old single-call format is still accepted:
```json
{"vplus_v": 3.3, "vminus_v": 0.0, "enable_vplus": true, "confirm_unsafe": true}
```

---

## Impedance Analyzer

Available on devices with `has_impedance: true` (Analog Discovery Studio Max,
DEVID 15). On other devices the impedance service uses the scope and wavegen
channels with a probe resistor.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /impedance/configure` | Set up excitation signal and probe |
| `POST /impedance/measure` | Single-frequency measurement |
| `POST /impedance/sweep` | Log-spaced frequency sweep |
| `POST /impedance/compensation` | Open/short/load calibration |

### Wiring

```
W1+  →  probe-R (e.g. 1 kΩ)  →  DUT (+)
C1+  →  DUT (+) node
C1−  →  DUT (−) / GND
DUT (−)  →  GND
```

### impedance/configure

```json
{
  "freq_hz": 1000,
  "amplitude_v": 0.5,
  "offset_v": 0.0,
  "probe_resistance_ohm": 1000,
  "probe_capacitance_f": 0,
  "min_periods": 16
}
```

### impedance/sweep

```json
{
  "f_start_hz": 100,
  "f_stop_hz": 1000000,
  "steps": 50,
  "amplitude_v": 0.5,
  "probe_resistance_ohm": 1000,
  "measurements": ["Impedance", "ImpedancePhase", "Resistance", "Reactance"]
}
```

Returns:
```json
{
  "ok": true,
  "frequencies": [100.0, 107.2, ...],
  "measurements": {
    "Impedance": [1050.3, 1048.7, ...],
    "ImpedancePhase": [-2.1, -2.3, ...],
    ...
  }
}
```

Available measurements: `Impedance`, `ImpedancePhase`, `Resistance`, `Reactance`,
`Admittance`, `AdmittancePhase`, `Conductance`, `Susceptance`,
`SeriesCapacitance`, `ParallelCapacitance`, `SeriesInductance`,
`ParallelInductance`, `Dissipation`, `Quality`

### impedance/compensation

```json
{"step": "open"}   // then "short", then "load"
```

Run open then short before sweeping for best accuracy.

---

## Digital Protocols

Requires `has_protocols: true` (see `docs/device-capabilities.md`).

All protocol endpoints hold the session lock for the full duration of the
transaction (including receive timeouts).

### UART

#### uart/configure

```json
{
  "baud_rate": 115200,
  "bits": 8,
  "parity": "none",
  "stop_bits": 1.0,
  "tx_ch": 0,
  "rx_ch": 1,
  "polarity": 0
}
```

Valid parity: `none`, `odd`, `even`, `mark`, `space`

#### uart/send

```json
{"data": "Hello\r\n"}
```

#### uart/receive

```json
{"max_bytes": 256, "timeout_s": 2.0}
```

Returns: `{"ok": true, "data": "...", "bytes_received": 7, "warnings": []}`

Warnings include `"parity_error"` or `"framing_error"` if detected.

### SPI

#### spi/configure

```json
{
  "freq_hz": 1000000,
  "mode": 0,
  "clk_ch": 0,
  "mosi_ch": 1,
  "miso_ch": 2,
  "cs_ch": 3,
  "cs_idle": 1,
  "order": "msb",
  "duty_pct": 50.0
}
```

SPI modes 0–3. `order`: `msb` or `lsb`. `cs_idle: 1` = CS idles high.

#### spi/transfer

```json
{"tx_data": [0x01, 0x02, 0x03], "rx_len": 3}
```

Returns: `{"ok": true, "rx_data": [0x00, 0x00, 0x00], "bytes_transferred": 3}`

### I2C

#### i2c/configure

```json
{"rate_hz": 100000, "scl_ch": 0, "sda_ch": 1}
```

**Pull-ups:** The Analog Discovery does not provide internal I2C pull-ups.
Add external 4.7 kΩ resistors to 3.3 V on both SCL and SDA.

#### i2c/write

```json
{"address": 72, "data": [0x00]}
```

Returns `"nak": 0` if the device ACKed, `"nak": 1` if no device present.

#### i2c/read

```json
{"address": 72, "length": 2}
```

Returns: `{"ok": true, "data": [0x00, 0x8F], "nak": 0}`

#### i2c/write-read

Write register address then read response in one transaction:

```json
{"address": 72, "tx_data": [0x00], "rx_len": 2}
```

### CAN bus

#### can/configure

```json
{"rate_hz": 500000, "tx_ch": 0, "rx_ch": 1}
```

#### can/send

```json
{
  "id": "0x123",
  "data": [1, 2, 3, 4],
  "extended": false,
  "remote": false
}
```

Data max 8 bytes. `extended: true` for 29-bit IDs.

#### can/receive

```json
{"timeout_s": 1.0}
```

Returns: `{"ok": true, "id": "0x123", "data": [1, 2, 3, 4], "extended": false, "remote": false, "timeout": false}`

`"timeout": true` if no frame was received within `timeout_s`.

---

## High-level Orchestration Actions

All actions are dispatched via `POST /measure/basic`:

```json
{"action": "<action_name>", "params": {...}}
```

Response format:
```json
{
  "ok": true,
  "ts": "2026-03-25T10:00:00+00:00",
  "action": "<action_name>",
  "within_tolerance": true,
  "result": {...}
}
```

### measure_pwm

Measure PWM frequency and duty cycle.

```json
{
  "action": "measure_pwm",
  "params": {
    "channel": 1,
    "expected_freq_hz": 1000,
    "tolerance_percent": 5,
    "sample_rate_hz": 2000000,
    "duration_ms": 20,
    "range_v": 5.0
  }
}
```

Result: `measured_freq_hz`, `expected_freq_hz`, `duty_cycle_percent`, `vpp`, `within_tolerance`

### measure_voltage_level

```json
{
  "action": "measure_voltage_level",
  "params": {"channel": 1, "expected_v": 3.3, "tolerance_v": 0.1, "range_v": 5.0}
}
```

Result: `measured_v`, `expected_v`, `vmin`, `vmax`, `vrms`

### detect_logic_activity

```json
{
  "action": "detect_logic_activity",
  "params": {"channels": [0, 1], "sample_rate_hz": 1000000, "duration_samples": 10000, "min_edges": 2}
}
```

Result: `active_channels`, per-channel `edge_count`, `freq_est_hz`, `duty_cycle_percent`

### bode_sweep

Drive W1 and measure gain/phase between CH1 (reference) and CH2 (DUT).

```json
{
  "action": "bode_sweep",
  "params": {
    "f_start_hz": 100, "f_stop_hz": 100000, "steps": 30,
    "amplitude_v": 1.0, "ref_channel": 1, "dut_channel": 2, "range_v": 5.0
  }
}
```

Result: `frequencies_hz[]`, `gain_db[]`, `phase_deg[]`, `fc_3db_hz`

### uart_loopback_test

```json
{
  "action": "uart_loopback_test",
  "params": {"baud": 115200, "tx_ch": 0, "rx_ch": 1, "test_string": "Hello", "timeout_s": 1.0}
}
```

Result: `sent`, `received`, `match`, `bytes_received`, `warnings`

### i2c_scan

```json
{
  "action": "i2c_scan",
  "params": {"rate_hz": 100000, "scl_ch": 0, "sda_ch": 1}
}
```

Result: `devices_found` (list of hex strings), `count`, `scan_range`

### characterize_supply

Requires `--allow-supplies`. Enables a supply rail and measures the output.

```json
{
  "action": "characterize_supply",
  "params": {
    "vplus_v": 3.3, "enable_vplus": true,
    "scope_channel": 1, "scope_range_v": 5.0, "settle_ms": 200
  }
}
```

Result: `target_vplus_v`, `measured_v`, `ripple_vpp`, `within_tolerance`

### digital_frequency

Measure frequency of a digital signal via the logic analyzer.

```json
{
  "action": "digital_frequency",
  "params": {
    "channel": 0, "sample_rate_hz": 10000000,
    "duration_samples": 100000, "expected_freq_hz": 1000, "tolerance_percent": 5.0
  }
}
```

Result: `freq_hz`, `duty_cycle_percent`, `edge_count`, `within_tolerance`

---

## Analysis Tools

Standalone CLI scripts — no server running required after data collection.

### plot_waveform.py

Capture raw scope data and export to CSV, PNG, Markdown.

```bash
python tools/plot_waveform.py \
  --channels 1 2 --rate 200000 --duration 10 --range 5.0 --out /tmp/capture
```

Output: `capture.png`, `capture.csv`, `capture.md`

### fft_analyze.py

Hanning-windowed FFT, harmonic detection (H2–H10), THD, SFDR.

```bash
python tools/fft_analyze.py --channel 1 --rate 1000000 --duration 5 --out /tmp/fft
```

Output: `fft.png` (linear + dB), `fft.md`

### impedance_sweep.py

Log-spaced impedance sweep with DUT classification.

```bash
python tools/impedance_sweep.py \
  --fstart 100 --fstop 1000000 --steps 100 \
  --amplitude 0.5 --probe-r 1000 --out results/sweep
```

Output: `sweep.csv`, `sweep.png`, `sweep.md`

DUT classifier: resistor (slope ≈ 0, phase ≈ 0°), capacitor (slope ≈ −1,
phase ≈ −90°), inductor (slope ≈ +1, phase ≈ +90°), RC/RL networks, complex.

### protocol_decode.py

Protocol capture with hex+ASCII dump.

```bash
python tools/protocol_decode.py uart --baud 115200 --tx 0 --rx 1 --duration 2.0 --out uart_capture
python tools/protocol_decode.py i2c  --rate 100000 --scl 0 --sda 1 --out i2c_capture
python tools/protocol_decode.py spi  --freq 1000000 --clk 0 --mosi 1 --miso 2 --cs 3 --out spi_capture
python tools/protocol_decode.py can  --rate 500000 --tx 0 --rx 1 --duration 2.0 --out can_capture
```

Output: `<out>.hex` (hex+ASCII), `<out>.md` (Markdown with frame table)

### dut_identify.py

Automated Bode sweep and DUT filter classification.

**Wiring:** W1 → DUT input → CH1 (ref), DUT output → CH2

```bash
python tools/dut_identify.py --fstart 100 --fstop 500000 --steps 40 --amplitude 1.0 --out /tmp/bode
```

Output: `bode.png`, `bode_report.md`

---

## Known Limitations

| Issue | Device | Workaround |
|-------|--------|-----------|
| `scope/capture` trigger → HTTP 504 | AD2 | Use `trigger: {enabled: false}` |
| High sample rate buffer overflow | AD2 | 10 MS/s → max 0.1 ms |
| `channel` field is integer not string | All | Normalize in client code |
| DIO offset for pattern generator | DD | Server applies offset automatically |
| ADP5250: no UART/CAN | ADP5250 | Use I2C/SPI only |
| Impedance mode locks scope/wavegen | ADS Max | Disable impedance before switching |
| I2C requires external pull-ups | All | 4.7 kΩ to 3.3 V on SCL and SDA |
