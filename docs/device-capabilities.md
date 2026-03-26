# Device Capabilities Reference

This document describes the capabilities of each supported Digilent WaveForms
device. The data is sourced from `digilent/capability_registry.py` and is
used at runtime to gate instrument endpoints and apply safe-limit defaults.

---

## Capability Fields

| Field | Type | Description |
|-------|------|-------------|
| `devid` | int | WaveForms DEVID constant |
| `name` | str | Human-readable device name |
| `analog_in_ch` | int | Number of oscilloscope input channels |
| `analog_out_ch` | int | Number of waveform generator channels |
| `digital_in_ch` | int | Number of logic analyzer channels |
| `digital_out_ch` | int | Number of pattern generator channels |
| `digital_io_ch` | int | Number of digital I/O channels |
| `digital_io_offset` | int | Channel index offset in DigitalOut API (24 for Digital Discovery) |
| `has_impedance` | bool | Dedicated impedance analyzer connector |
| `has_protocols` | bool | UART / SPI / I2C / CAN protocol engines |
| `has_dmm` | bool | Built-in DMM mode |
| `has_power_supply` | bool | Programmable power supply |
| `max_scope_rate_hz` | float | Maximum ADC sample rate |
| `max_scope_buffer` | int | Hardware sample buffer depth |
| `max_logic_rate_hz` | float | Maximum digital capture sample rate |
| `max_logic_buffer` | int | Hardware logic buffer depth (samples) |
| `supply_channels` | list | Per-channel supply definitions (see below) |

---

## Supported Devices

| DEVID | Device | Scope CH | Wavegen CH | DIO | Protocols | Impedance | Supplies |
|-------|--------|----------|------------|-----|-----------|-----------|----------|
| 1 | Electronics Explorer | 8 | 4 | 16 | ✓ | — | V+ 0–9 V, V− 0–(−9) V |
| 2 | Analog Discovery | 2 | 2 | 16 | ✓ | — | V+ ±5 V (fixed) |
| 3 | Analog Discovery 2 | 2 | 2 | 16 | ✓ | — | V+ 0–5 V, V− 0–(−5) V |
| 4 | Digital Discovery | — | — | 16 (+24 offset) | ✓ | — | VIO 1.2–3.3 V |
| 6 | Analog Discovery Pro 3450 | 4 | 2 | 16 | ✓ | — | VIO |
| 8 | Analog Discovery Pro 5250 | 2 | 2 | 8 | ✓ (I2C/SPI only) | — | V+ 0–25 V, V− 0–(−25) V, V+ 0–6 V |
| 9 | Discovery Power Supply 3340 | 2 | 2 | — | — | — | CH1/CH2 0–30 V, CH3 0–6 V |
| 10 | Analog Discovery 3 | 2 | 2 | 16 | ✓ + SWD | — | V+ ±5 V |
| 14 | Analog Discovery Pro 2230 | 2 | 2 | 16 | ✓ | — | V+ ±5 V |
| 15 | Analog Discovery Studio Max | 2 | 2 | 16 | ✓ | ✓ | V+ ±5 V |
| 16 | Analog Discovery Pro 2440 | 4 | 2 | 16 | ✓ | — | V+ ±5 V |
| 17 | Analog Discovery Pro 2450 | 4 | 2 | 16 | ✓ | — | V+ ±5 V |

---

## Per-Device Detail

### DEVID 1 — Electronics Explorer

| Parameter | Value |
|-----------|-------|
| Scope | 8 ch, 40 MS/s, 16 384 sample buffer |
| Wavegen | 4 ch (channels 3/4 are supply outputs — blocked for waveform use) |
| Logic | 16 DIO, 100 MS/s, 16 384 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | V+ 0–9 V, V− 0–(−9) V |

### DEVID 2 — Analog Discovery (original)

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 100 MS/s, 8 192 sample buffer |
| Wavegen | 2 ch |
| Logic | 16 DIO, 100 MS/s, 16 384 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | V+ fixed ±5 V (not adjustable) |

### DEVID 3 — Analog Discovery 2

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 100 MS/s, 8 192 sample buffer |
| Wavegen | 2 ch |
| Logic | 16 DIO, 100 MS/s, 16 384 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | V+ 0–5 V, V− 0–(−5) V (adjustable) |

**Known limitations:** `scope/capture` with trigger → HTTP 504 (use free-run).
Buffer overflow at high sample rates: 10 MS/s → max ~0.1 ms; 1 MS/s → max ~5 ms.

### DEVID 4 — Digital Discovery

| Parameter | Value |
|-----------|-------|
| Scope | None |
| Wavegen | None |
| Logic | 24 DI + 16 DIO, 800 MS/s, 1 GiB sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | VIO 1.2–3.3 V (adjustable) |
| DIO offset | 24 — all DigitalOut channel indices are shifted by 24 |

**Note:** `digital_io_offset = 24` — the server applies this shift automatically.
`DwfDigitalOutTypePlay` is supported.

### DEVID 6 — Analog Discovery Pro 3000 Series (ADP3450 / ADP3250)

| Parameter | Value |
|-----------|-------|
| Scope | 4 ch (ADP3450) or 2 ch (ADP3250), 125 MS/s, 131 072 sample buffer |
| Logic | 16 DIO, 800 MS/s, 131 072 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | VIO adjustable |

Oversampling mode (`acqmodeOvers`) supported.

### DEVID 8 — Analog Discovery Pro 5250

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 500 MS/s, 131 072 sample buffer |
| Logic | 8 DIO, 100 MS/s, 131 072 sample buffer |
| Protocols | I2C, SPI only (no UART, no CAN) |
| Supplies | V+ 0–25 V, V− 0–(−25) V, V+ 0–6 V (all with current limit) |
| DMM | Yes |

Fixed protocol pins — see WaveForms SDK §14.6 for pinout.
Does not support trigger pulse/transition/window or record acquisition mode.

### DEVID 9 — Discovery Power Supply 3340

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 10 MS/s, 4 096 sample buffer |
| Logic | None |
| Protocols | None |
| Supplies | CH1/CH2 0–30 V (with current limit), CH3 0–6 V |

### DEVID 10 — Analog Discovery 3

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 125 MS/s, 32 768 sample buffer |
| Wavegen | 2 ch |
| Logic | 16 DIO, 100 MS/s, 32 768 sample buffer |
| Protocols | UART, SPI, I2C, CAN, **SWD** (`FDwfDigitalSwd*`) |
| Supplies | V+ ±5 V (adjustable) |

### DEVID 14 — Analog Discovery Pro 2230

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 125 MS/s, 32 768 sample buffer |
| Logic | 16 DIO, 100 MS/s, 32 768 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | V+ ±5 V |

### DEVID 15 — Analog Discovery Studio Max

| Parameter | Value |
|-----------|-------|
| Scope | 2 ch, 125 MS/s, 32 768 sample buffer |
| Logic | 16 DIO, 100 MS/s, 32 768 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Impedance | ✓ — dedicated IA connector (`FDwfAnalogImpedanceEnableSet`) |
| Supplies | V+ ±5 V |

**Note:** Impedance mode routes AWG and scope to the IA connector — it is
mutually exclusive with normal scope/wavegen use.

### DEVID 16 — Analog Discovery Pro 2440

| Parameter | Value |
|-----------|-------|
| Scope | 4 ch, 125 MS/s, 131 072 sample buffer |
| Logic | 16 DIO, 100 MS/s, 131 072 sample buffer |
| Protocols | UART, SPI, I2C, CAN |
| Supplies | V+ ±5 V |

### DEVID 17 — Analog Discovery Pro 2450

Same as DEVID 16 (ADP2450 vs ADP2440 — different hardware revision).

---

## Supply Channel Fields

| Field | Description |
|-------|-------------|
| `name` | Supply rail name (e.g. `"V+"`, `"VIO"`, `"CH1"`) |
| `channel_idx` | `FDwfAnalogIO` channel index |
| `min_v` / `max_v` | Voltage range (negative for V−/V−25) |
| `is_negative` | True if rail is a negative supply |
| `read_only` | True for monitor-only rails (e.g. USB voltage sense) |
| `has_enable` | Whether the rail has an enable/disable node |
| `has_voltage_set` | Whether the voltage is programmable |
| `has_current_limit` | Whether a current limit can be set |
| `has_voltage_monitor` | Whether output voltage can be read back |
| `has_current_monitor` | Whether output current can be read back |

---

## Capability Gate Behavior

When a request is made for an instrument the device does not support, the
server returns HTTP 405 with error code `DIGILENT_NOT_AVAILABLE`:

```json
{
  "ok": false,
  "error": {
    "code": "DIGILENT_NOT_AVAILABLE",
    "message": "This device does not support impedance analysis"
  }
}
```

Use `GET /api/digilent/capability` to query the connected device's capabilities
before making instrument-specific requests.

---

## Runtime Override

At device open, the server calls `FDwfEnumConfigInfo` and `FDwfDeviceGetVersion`
to apply any runtime corrections to the static table (e.g. actual buffer sizes
reported by the firmware). The overrides are applied to a deep copy of the
static record — the `DEVICE_CAPABILITIES` table is never mutated.
