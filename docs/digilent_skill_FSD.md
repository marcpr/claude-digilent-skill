# Functional Specification Document
## Digilent WaveForms Universal Skill for Claude Code

**Version:** 1.0  
**Date:** 2026-03-25  
**Status:** Draft  
**Reference Manual:** WaveForms SDK Reference Manual Rev. March 4, 2026 (163 pp.)  
**Based On:** `claude-digilent-skill` partial implementation (Analog Discovery 2, local HTTP server)

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [System Architecture](#2-system-architecture)
3. [Device Detection and Capability Mapping](#3-device-detection-and-capability-mapping)
4. [Instrument Modules](#4-instrument-modules)
   - 4.1 Analog In (Oscilloscope)
   - 4.2 Analog Out (AWG)
   - 4.3 Analog I/O (Power Supplies & Monitors)
   - 4.4 Digital I/O
   - 4.5 Digital In (Logic Analyzer)
   - 4.6 Digital Out (Pattern Generator)
   - 4.7 Analog Impedance Analyzer
   - 4.8 Digital Protocols
5. [HTTP API Specification](#5-http-api-specification)
6. [Skill Definition (SKILL.md)](#6-skill-definition-skillmd)
7. [Configuration and Safety Limits](#7-configuration-and-safety-limits)
8. [Error Handling](#8-error-handling)
9. [Analysis Tools](#9-analysis-tools)
10. [Testing Requirements](#10-testing-requirements)
11. [Known Limitations and Device-Specific Notes](#11-known-limitations-and-device-specific-notes)

---

## 1. Purpose and Scope

### 1.1 Goal

This skill enables Claude Code to directly operate **any Digilent WaveForms-compatible device** connected via USB (or network/AXI) to the developer's machine. Claude Code interacts via a local HTTP API (`http://127.0.0.1:7272`). The skill is device-agnostic: it detects which device is connected at startup and advertises only the capabilities that device actually supports.

### 1.2 Supported Devices

All devices enumerated by the WaveForms SDK (`libdwf`):

| DEVID | Constant | Device Name |
|-------|----------|-------------|
| 1 | `devidEExplorer` | Electronics Explorer |
| 2 | `devidDiscovery` | Analog Discovery (1) |
| 3 | `devidDiscovery2` | Analog Discovery 2 |
| 4 | `devidDDiscovery` | Digital Discovery |
| 6 | `devidADP3X50` | Analog Discovery Pro 3000 Series (ADP3450/3250) |
| 8 | `devidADP5250` | Analog Discovery Pro 5250 |
| 9 | `devidDPS3340` | Discovery Power Supply 3340 |
| 10 | `devidDiscovery3` | Analog Discovery 3 |
| 14 | `devidADP2230` | Analog Discovery Pro 2230 |
| 15 | `devidADSMax` | Analog Discovery Studio Max |
| 16 | `devidADP2440` | Analog Discovery Pro 2440 |
| 17 | `devidADP2450` | Analog Discovery Pro 2450 |

### 1.3 Out of Scope

- Eclypse Z7 / Zmod platform (too specialized; may be added as a separate extension)
- GUI-based WaveForms application (the server requires exclusive USB access)
- Remote/network-attached devices (future extension; architecture is ready)

---

## 2. System Architecture

```
Developer Machine
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  Claude Code  ──curl──►  digilent_local_server.py             │
│                          (HTTP :7272)                         │
│                              │                                │
│                    ┌─────────▼──────────┐                     │
│                    │  digilent/ package │                     │
│                    │  ┌──────────────┐  │                     │
│                    │  │device_manager│  │                     │
│                    │  │ + capability │  │                     │
│                    │  │   registry   │  │                     │
│                    │  └──────┬───────┘  │                     │
│                    │         │           │                     │
│                    │  ┌──────▼───────┐  │                     │
│                    │  │ dwf_adapter  │  │                     │
│                    │  │ (ctypes wrap)│  │                     │
│                    └──┴──────┬───────┴──┘                     │
│                              │ libdwf.so / dwf.dll            │
│                              │                                │
│                         USB / AXI                             │
│                              │                                │
│                    ┌─────────▼──────────┐                     │
│                    │  Digilent Device   │                     │
│                    │  (any supported)   │                     │
│                    └────────────────────┘                     │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 Package Structure (target)

```
claude-digilent-skill/
├── digilent/
│   ├── dwf_adapter.py          ctypes wrapper — unchanged
│   ├── device_manager.py       Session management + capability registry (EXTEND)
│   ├── capability_registry.py  NEW — device capability definitions
│   ├── scope_service.py        Analog In (EXTEND)
│   ├── wavegen_service.py      Analog Out (EXTEND)
│   ├── supplies_service.py     Analog I/O — power + monitors (EXTEND)
│   ├── digital_io_service.py   Digital I/O (NEW)
│   ├── logic_service.py        Digital In — Logic Analyzer (EXTEND)
│   ├── pattern_service.py      Digital Out — Pattern Generator (NEW)
│   ├── impedance_service.py    Analog Impedance Analyzer (NEW)
│   ├── protocol_service.py     Digital Protocols — UART/SPI/I2C/CAN (NEW)
│   ├── orchestration.py        High-level agent actions (EXTEND)
│   ├── api.py                  HTTP dispatch (EXTEND)
│   ├── config.py               Config loader (unchanged)
│   ├── models.py               Request/response dataclasses (EXTEND)
│   ├── errors.py               Typed error hierarchy (EXTEND)
│   └── utils.py                Metrics, downsampling (unchanged)
├── tools/
│   ├── digilent_local_server.py
│   ├── digilent_local_setup.py
│   ├── plot_waveform.py
│   ├── fft_analyze.py
│   ├── dut_identify.py
│   ├── impedance_sweep.py      NEW
│   └── protocol_decode.py      NEW
├── docs/
│   ├── extending-waveform-export.md
│   ├── integration-guide.md
│   └── device-capabilities.md  NEW
├── tests/
│   ├── test_digilent_api.py        (EXTEND)
│   ├── test_capability_registry.py (NEW)
│   ├── test_impedance_service.py   (NEW)
│   └── test_protocol_service.py    (NEW)
└── .claude/skills/digilent-local/SKILL.md  (REWRITE)
```

---

## 3. Device Detection and Capability Mapping

### 3.1 Startup Detection Flow

```
FDwfEnum(enumfilterAll, &nDev)
  → nDev == 0  →  raise DIGILENT_NOT_FOUND
  → nDev >= 1  →  for each idx in range(nDev):
                     FDwfEnumDeviceType(idx, &devid, &devver)
                     FDwfEnumDeviceName(idx, &name)
                     FDwfEnumUserName(idx, &username)
                     FDwfEnumSN(idx, &sn)
                     FDwfEnumConfig(idx, &nConfig)
                     for each cfg: FDwfEnumConfigInfo(cfg, DECI*, &val)
                     FDwfEnumDeviceIsOpened(idx, &isOpen)
  → select first non-opened device
  → FDwfDeviceOpen(idx, &hdwf)
  → build CapabilityRecord from devid + config info
```

### 3.2 Capability Registry

Each device entry in `capability_registry.py` defines which API modules are active:

```python
@dataclass
class CapabilityRecord:
    devid: int
    name: str
    analog_in_ch: int       # 0 = not present
    analog_out_ch: int
    analog_io_ch: int
    digital_in_ch: int
    digital_out_ch: int
    digital_io_ch: int
    has_impedance: bool
    has_protocols: bool     # UART, SPI, I2C, CAN
    has_dmm: bool           # ADP5250 only
    has_power_supply: bool
    max_scope_rate_hz: float
    max_scope_buffer: int
    max_logic_rate_hz: float
    max_logic_buffer: int
    supply_channels: list[SupplyChannelDef]
    notes: str              # device-specific caveats
```

The registry is populated from the WaveForms SDK section 14 tables and from `FDwfEnumConfigInfo` at runtime (which overrides static defaults). The `/api/digilent/status` endpoint returns the serialized `CapabilityRecord` so Claude Code always knows what is available before issuing commands.

### 3.3 Device-Specific Capability Highlights

| Device | AnalogIn | AnalogOut | Power | Logic | Pattern | Impedance | Protocols |
|--------|----------|-----------|-------|-------|---------|-----------|-----------|
| Electronics Explorer | 2ch | 2ch | ±9V + refs | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| Analog Discovery 1 | 2ch | 2ch | ±5V (fixed) | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| Analog Discovery 2 | 2ch | 2ch | ±5V (adj) | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| Digital Discovery | none | none | VIO (adj) | 24 DIN+16 DIO | 24 DIN+16 DIO | no | UART/SPI/I2C/CAN |
| ADP3000 series | 4ch | 2ch | VIO (adj) | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| ADP5250 | 2ch | 2ch | ±25V + +6V | 8ch | 8ch | no | I2C/SPI only |
| DPS3340 | monitoring | waveform | 3 channels | no | no | no | no |
| Analog Discovery 3 | 2ch | 2ch | ±5V (adj) | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| ADP2230 | 2ch | 2ch | ±5V (adj) | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |
| ADS Max | 2ch | 2ch | ±5V (adj) | 16ch | 16ch | dedicated IA connector | UART/SPI/I2C |
| ADP2440/2450 | 4ch | 2ch | adj | 16ch | 16ch | via AWG+scope | UART/SPI/I2C |

---

## 4. Instrument Modules

### 4.1 Analog In (Oscilloscope)

**Existing:** `scope_service.py` — capture, free-run, basic metrics  
**Extend:**

| Function Group | Key SDK Functions | New Endpoints |
|----------------|-------------------|---------------|
| Single sample | `FDwfAnalogInStatusSample` | `/scope/sample` |
| Triggered acquisition | `FDwfAnalogInConfigure(hdwf, 0, 1)` + status poll | `/scope/measure` (already exists, fix timeout) |
| Record (streaming) | `acqmodeRecord` + `FDwfAnalogInStatusRecord` | `/scope/record` |
| Oversampling (ADP3000) | `acqmodeOvers` | config option in `/scope/capture` |
| Channel config | `FDwfAnalogInChannelRangeSet`, `OffsetSet`, `FilterSet` | params in all scope endpoints |
| Trigger types | `trigtype*` — edge, pulse, transition, window | `trigger.type` param |
| Trigger detector | `FDwfAnalogInTriggerAutoTimeoutSet`, detector channels | `trigger.auto_timeout_s` |

**Parameters for `/scope/capture` and `/scope/measure`:**

```json
{
  "channels": [1, 2],
  "sample_rate_hz": 1000000,
  "duration_s": 0.005,
  "range_v": 5.0,
  "offset_v": 0.0,
  "filter": "none|decimate|average|minmax",
  "trigger": {
    "enabled": false,
    "source": "ch1|ch2|ext|pc",
    "type": "edge|pulse|transition|window",
    "level_v": 1.0,
    "edge": "rise|fall|either",
    "auto_timeout_s": 0.1
  },
  "return_waveform": true
}
```

**Notes:**
- Digital Discovery has no AnalogIn — endpoint must return `DIGILENT_NOT_AVAILABLE` (HTTP 405) if `capability.analog_in_ch == 0`.
- ADP5250 does not support shift, screen, record acquisition modes or trigger pulse/transition/window.

---

### 4.2 Analog Out (AWG — Arbitrary Waveform Generator)

**Existing:** `wavegen_service.py` — basic sine/square/triangle  
**Extend:**

| Function Group | Key SDK Functions |
|----------------|-------------------|
| Waveform types | `funcSine`, `funcSquare`, `funcTriangle`, `funcRampUp`, `funcRampDown`, `funcNoise`, `funcDC`, `funcCustom`, `funcPlay` |
| Modulation | `FDwfAnalogOutNodeModulationSet` — AM, FM (not ADP5250) |
| Synchronized channels | `FDwfAnalogOutMasterSet` |
| Sweep | `FDwfAnalogOutNodeFrequencySet` with run/repeat/wait |
| Custom waveform | `FDwfAnalogOutNodeDataSet` |
| Play (streaming) | `FDwfAnalogOutNodePlaySet` (ADP3000, ADP2230) |

**Endpoint:** `POST /api/digilent/wavegen/set`

```json
{
  "channel": 1,
  "enabled": true,
  "waveform": "sine|square|triangle|rampup|rampdown|noise|dc|custom",
  "frequency_hz": 1000.0,
  "amplitude_v": 1.0,
  "offset_v": 0.0,
  "symmetry_pct": 50.0,
  "phase_deg": 0.0,
  "custom_data": [0.0, 0.5, 1.0, ...],
  "modulation": {
    "type": "am|fm",
    "freq_hz": 10.0,
    "depth": 0.5
  }
}
```

**Safety:** amplitude clamped by `safe_limits.max_wavegen_amplitude_v` (default 5 V). Electronics Explorer channels 3/4 are power supply channels — block if `devid == devidEExplorer && channel >= 3`.

---

### 4.3 Analog I/O (Power Supplies and Monitors)

**Existing:** `supplies_service.py` — partial AD2 supply on/off  
**Rewrite for universality:**

The AnalogIO API is entirely channel/node based (`FDwfAnalogIOChannelNodeSet/Get/Status`). The `CapabilityRecord.supply_channels` list describes each device's specific topology (see Section 14 of the SDK manual). The service must be table-driven, not device-hardcoded.

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/digilent/supplies/info` | Returns `supply_channels` list from capability record |
| POST | `/api/digilent/supplies/set` | Enable/disable and set voltage/current on a named supply |
| GET | `/api/digilent/supplies/status` | Read all supply monitor nodes (voltage, current, temp) |
| POST | `/api/digilent/supplies/master` | Set master enable (`FDwfAnalogIOEnableSet`) |

**`/supplies/set` body:**

```json
{
  "channel_name": "V+",
  "enable": true,
  "voltage_v": 3.3,
  "current_limit_a": 0.5,
  "confirm_unsafe": true
}
```

**Safety:** All supply endpoints require `--allow-supplies` flag **and** `confirm_unsafe: true` in every request body.

---

### 4.4 Digital I/O

**New:** `digital_io_service.py`

Simple static bit-banging using `FDwfDigitalIOOutputEnableSet/Get`, `FDwfDigitalIOOutputSet/Get`, `FDwfDigitalIOInputStatus`.

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/digital-io/configure` | Set direction mask and output value |
| GET | `/api/digilent/digital-io/read` | Read current input state |
| POST | `/api/digilent/digital-io/write` | Set output bits |

```json
// POST /digital-io/configure
{ "output_enable_mask": "0x00FF", "output_value": "0x0000" }

// POST /digital-io/write
{ "value": "0x0055", "mask": "0x00FF" }

// GET response
{ "input": "0x00A3", "output": "0x0055", "output_enable": "0x00FF" }
```

**Notes:**
- Digital Discovery DIO pins start at index 24 in the `FDwfDigitalOut` API. The `CapabilityRecord` includes a `digital_io_offset` field to account for this.
- DIO voltage on Digital Discovery and ADP3000 is set via the AnalogIO channel, not here.

---

### 4.5 Digital In (Logic Analyzer)

**Existing:** `logic_service.py` — basic capture  
**Extend:**

| Function Group | Key SDK Functions |
|----------------|-------------------|
| Triggered capture | `FDwfDigitalInTriggerSet`, `FDwfDigitalInTriggerSourceSet` |
| Record (streaming) | `acqmodeRecord` + `FDwfDigitalInStatusRecord` |
| Protocol trigger | `FDwfDigitalInTriggerSlopeSet` |
| Input order | `FDwfDigitalInInputOrderSet` (Digital Discovery DIN/DIO ordering) |
| Sample format | `FDwfDigitalInSampleFormatSet` — 8/16/32 bit |

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/logic/capture` | Existing — extend with trigger params |
| POST | `/api/digilent/logic/record` | New streaming record |
| POST | `/api/digilent/logic/measure` | Edge timing / frequency on a single channel |

---

### 4.6 Digital Out (Pattern Generator)

**New:** `pattern_service.py`

Key SDK calls: `FDwfDigitalOutConfigure`, `FDwfDigitalOutReset`, `FDwfDigitalOutRunSet`, `FDwfDigitalOutDividerSet`, `FDwfDigitalOutDataSet`, `FDwfDigitalOutTypeSet` (pulse/BFS/custom/random/play).

**Endpoint:** `POST /api/digilent/pattern/set`

```json
{
  "channel": 0,
  "enabled": true,
  "type": "pulse|bfs|custom|random",
  "frequency_hz": 1000.0,
  "duty_pct": 50.0,
  "initial_value": 0,
  "idle_state": "low|high|zstate|initial",
  "custom_data": "0xA5B3...",
  "run_s": 0,
  "repeat": 0
}
```

Stopping: `POST /api/digilent/pattern/stop { "channel": 0 }` or `{ "channel": "all" }`.

**Notes:** `DwfDigitalOutTypePlay` is only available on Digital Discovery.

---

### 4.7 Analog Impedance Analyzer

**New:** `impedance_service.py`

Available on all devices with both AnalogIn and AnalogOut (except ADP5250). On ADS Max the dedicated `FDwfAnalogImpedanceEnableSet` switches routing to the IA connector.

**Measurement types** (from `DwfAnalogImpedance` enum):

| Measure | Description |
|---------|-------------|
| Impedance | \|Z\| in Ohms |
| ImpedancePhase | Phase in radians |
| Resistance | Rs (series) |
| Reactance | Xs |
| SeriesCapacitance | Cs in Farad |
| ParallelCapacitance | Cp in Farad |
| SeriesInductance | Ls in Henry |
| ParallelInductance | Lp in Henry |
| Dissipation | D = Rs/Xs |
| Quality | Q = Xs/Rs |
| Vrms / Irms | RMS voltage/current on DUT |

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/impedance/configure` | Set frequency, amplitude, probe, compensation |
| POST | `/api/digilent/impedance/measure` | Single-point measurement |
| POST | `/api/digilent/impedance/sweep` | Frequency sweep (returns array of measurements) |
| POST | `/api/digilent/impedance/compensation` | Open/short compensation |

```json
// POST /impedance/sweep
{
  "f_start_hz": 100,
  "f_stop_hz": 1000000,
  "steps": 100,
  "amplitude_v": 1.0,
  "offset_v": 0.0,
  "probe_resistance_ohm": 1000,
  "probe_capacitance_f": 0,
  "min_periods": 16,
  "measurements": ["Impedance", "ImpedancePhase", "Resistance", "Reactance"]
}
```

---

### 4.8 Digital Protocols

**New:** `protocol_service.py`

Only one protocol can be active at a time. DigitalOut generates signals; DigitalIn captures.

**Supported protocols:**

| Protocol | Availability | Key SDK Functions |
|----------|--------------|-------------------|
| UART | All except DPS3340 | `FDwfDigitalUart*` |
| SPI | All except DPS3340; ADP5250 master only | `FDwfDigitalSpi*` |
| I2C | All except DPS3340 | `FDwfDigitalI2c*` |
| CAN | All except DPS3340 | `FDwfDigitalCan*` |
| SWD | ADP3000+, AD3 | `FDwfDigitalSwd*` |

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/digilent/protocol/uart/configure` | Set baud rate, bits, parity, stop |
| POST | `/api/digilent/protocol/uart/send` | Transmit bytes |
| POST | `/api/digilent/protocol/uart/receive` | Receive bytes |
| POST | `/api/digilent/protocol/spi/configure` | Set freq, mode, channels |
| POST | `/api/digilent/protocol/spi/transfer` | Full-duplex write/read |
| POST | `/api/digilent/protocol/i2c/configure` | Set rate, SCL/SDA pins |
| POST | `/api/digilent/protocol/i2c/write` | Write to address |
| POST | `/api/digilent/protocol/i2c/read` | Read from address |
| POST | `/api/digilent/protocol/i2c/write_read` | Combined transaction |
| POST | `/api/digilent/protocol/can/configure` | Set rate, TX/RX pins |
| POST | `/api/digilent/protocol/can/send` | Send CAN frame |
| POST | `/api/digilent/protocol/can/receive` | Receive CAN frame |

**UART configure example:**

```json
{
  "baud_rate": 115200,
  "bits": 8,
  "parity": "none|even|odd|mark|space",
  "stop_bits": 1.0,
  "tx_channel": 0,
  "rx_channel": 1,
  "polarity": "normal|inverted"
}
```

**ADP5250 constraints:** I2C fixed to DIO-6/DIO-7; SPI fixed to DIO-0/1/2/3; word length 8 bits only; no delay adjustment.

---

## 5. HTTP API Specification

### 5.1 Complete Endpoint Table

| Method | Endpoint | Module | Status |
|--------|----------|--------|--------|
| GET | `/api/digilent/ping` | server | existing |
| GET | `/api/digilent/status` | device | existing + extend |
| POST | `/api/digilent/device/open` | device | existing |
| POST | `/api/digilent/device/close` | device | existing |
| POST | `/api/digilent/session/reset` | device | existing (fix NoneType bug) |
| GET | `/api/digilent/capabilities` | device | **new** — full CapabilityRecord |
| POST | `/api/digilent/scope/capture` | scope | existing + extend |
| POST | `/api/digilent/scope/measure` | scope | existing + fix trigger timeout |
| POST | `/api/digilent/scope/sample` | scope | **new** — single ADC sample |
| POST | `/api/digilent/scope/record` | scope | **new** — streaming record |
| POST | `/api/digilent/wavegen/set` | wavegen | existing + extend |
| POST | `/api/digilent/wavegen/stop` | wavegen | existing |
| GET | `/api/digilent/supplies/info` | supplies | **new** |
| POST | `/api/digilent/supplies/set` | supplies | existing + rewrite |
| GET | `/api/digilent/supplies/status` | supplies | **new** |
| POST | `/api/digilent/supplies/master` | supplies | **new** |
| POST | `/api/digilent/digital-io/configure` | digital_io | **new** |
| GET | `/api/digilent/digital-io/read` | digital_io | **new** |
| POST | `/api/digilent/digital-io/write` | digital_io | **new** |
| POST | `/api/digilent/logic/capture` | logic | existing + extend |
| POST | `/api/digilent/logic/record` | logic | **new** |
| POST | `/api/digilent/logic/measure` | logic | **new** |
| POST | `/api/digilent/pattern/set` | pattern | **new** |
| POST | `/api/digilent/pattern/stop` | pattern | **new** |
| POST | `/api/digilent/impedance/configure` | impedance | **new** |
| POST | `/api/digilent/impedance/measure` | impedance | **new** |
| POST | `/api/digilent/impedance/sweep` | impedance | **new** |
| POST | `/api/digilent/impedance/compensation` | impedance | **new** |
| POST | `/api/digilent/protocol/uart/configure` | protocol | **new** |
| POST | `/api/digilent/protocol/uart/send` | protocol | **new** |
| POST | `/api/digilent/protocol/uart/receive` | protocol | **new** |
| POST | `/api/digilent/protocol/spi/configure` | protocol | **new** |
| POST | `/api/digilent/protocol/spi/transfer` | protocol | **new** |
| POST | `/api/digilent/protocol/i2c/configure` | protocol | **new** |
| POST | `/api/digilent/protocol/i2c/write` | protocol | **new** |
| POST | `/api/digilent/protocol/i2c/read` | protocol | **new** |
| POST | `/api/digilent/protocol/i2c/write_read` | protocol | **new** |
| POST | `/api/digilent/protocol/can/configure` | protocol | **new** |
| POST | `/api/digilent/protocol/can/send` | protocol | **new** |
| POST | `/api/digilent/protocol/can/receive` | protocol | **new** |
| POST | `/api/digilent/measure/basic` | orchestration | existing + extend |
| POST | `/api/digilent/static-io/set` | supplies | existing (alias → digital-io) |

### 5.2 Capability-Gating Convention

Every endpoint that requires a specific capability must check `CapabilityRecord` before executing and return:

```json
HTTP 405 Method Not Allowed
{
  "error": "DIGILENT_NOT_AVAILABLE",
  "message": "Analog In is not available on Digital Discovery",
  "device": "Digital Discovery",
  "capability": "analog_in"
}
```

### 5.3 Standard Response Envelope

```json
{
  "ok": true,
  "device": "Analog Discovery 2",
  "data": { ... }
}
```

Error responses:

```json
{
  "ok": false,
  "error": "DIGILENT_CONFIG_INVALID",
  "message": "sample_rate_hz exceeds device maximum of 100000000 Hz",
  "device": "Analog Discovery 2"
}
```

---

## 6. Skill Definition (SKILL.md)

The `.claude/skills/digilent-local/SKILL.md` is the instruction document Claude Code reads to understand how to use the skill. It must be rewritten to cover all new capabilities.

### 6.1 Required Sections

1. **Purpose** — what the skill does, that it is device-universal
2. **Prerequisites** — WaveForms installed, server running, no WaveForms GUI open
3. **Device detection** — how to query capabilities before measuring
4. **Per-instrument usage guide** — concise curl examples for each module
5. **High-level action shortcuts** — `measure/basic` action list
6. **Error handling guide** — mapping error codes to corrective actions
7. **Safety rules** — power supplies, wavegen limits, concurrent access
8. **Analysis tools** — how to invoke plot_waveform.py, fft_analyze.py, etc.

### 6.2 Skill Trigger Keywords

The SKILL.md description must include terms that cause Claude Code to auto-trigger the skill:

> oscilloscope, scope, waveform, signal, ADC, logic analyzer, pattern generator, AWG, arbitrary waveform, function generator, power supply, digital protocol, UART, SPI, I2C, CAN, impedance analyzer, Bode plot, frequency sweep, DUT, test and measurement, Digilent, Analog Discovery, WaveForms, capture, trigger, frequency, duty cycle, PWM, voltage level, digital signal

---

## 7. Configuration and Safety Limits

### 7.1 Config File Schema (extended)

```json
{
  "port": 7272,
  "host": "127.0.0.1",
  "auto_open": true,
  "allow_supplies": false,
  "allow_pattern_gen": true,
  "allow_protocols": true,
  "device_index": -1,
  "max_scope_points": 20000,
  "max_logic_points": 100000,
  "safe_limits": {
    "max_scope_sample_rate_hz": 100000000,
    "max_wavegen_amplitude_v": 5.0,
    "max_wavegen_offset_v": 5.0,
    "max_supply_voltage_v": 5.0,
    "max_supply_current_a": 0.5,
    "max_pattern_frequency_hz": 100000000,
    "max_impedance_sweep_amplitude_v": 2.0
  },
  "labels": {
    "scope_ch1": "DUT_SIGNAL",
    "scope_ch2": "REFERENCE",
    "logic_dio0": "UART_TX",
    "logic_dio1": "UART_RX"
  }
}
```

### 7.2 Safety Rules

- `allow_supplies: false` by default; must be explicitly enabled in config or via `--allow-supplies`
- Every supply write requires `"confirm_unsafe": true` in request body
- Wavegen amplitude and offset validated against `safe_limits` before `FDwfAnalogOutConfigure`
- Pattern generator defaults to disabled until explicitly started
- Protocol endpoints do not require confirmation (digital signals only, low voltage)
- Impedance analyzer amplitude validated against `safe_limits.max_impedance_sweep_amplitude_v`

---

## 8. Error Handling

### 8.1 Error Code Registry

| Code | HTTP | Meaning |
|------|------|---------|
| `DIGILENT_NOT_FOUND` | 503 | No device connected or WaveForms GUI is open |
| `DIGILENT_BUSY` | 409 | Concurrent request rejected |
| `DIGILENT_CONFIG_INVALID` | 400 | Bad parameter value |
| `DIGILENT_RANGE_VIOLATION` | 400 | Value exceeds safe limit |
| `DIGILENT_NOT_ENABLED` | 403 | Feature disabled (supplies, etc.) |
| `DIGILENT_CAPTURE_TIMEOUT` | 504 | Acquisition did not complete |
| `DIGILENT_NOT_AVAILABLE` | 405 | Instrument not present on this device |
| `DIGILENT_SDK_ERROR` | 500 | libdwf returned error (message from `FDwfGetLastErrorMsg`) |
| `DIGILENT_PROTOCOL_ERROR` | 422 | Parity/framing/ACK error during protocol operation |
| `DIGILENT_SESSION_LOST` | 503 | Device disconnected mid-session |

### 8.2 SDK Error Propagation

Every `libdwf` call that returns `0` (failure) must be followed by:

```python
err = c_int()
dwf.FDwfGetLastError(byref(err))
msg = create_string_buffer(512)
dwf.FDwfGetLastErrorMsg(msg)
raise DwfSdkError(err.value, msg.value.decode())
```

This maps to `DIGILENT_SDK_ERROR` at the HTTP layer.

---

## 9. Analysis Tools

### 9.1 Existing Tools (unchanged interface)

- `tools/plot_waveform.py` — scope capture → PNG + CSV + Markdown
- `tools/fft_analyze.py` — Hanning FFT → spectrum PNG + Markdown
- `tools/dut_identify.py` — Bode sweep + DUT classification

### 9.2 New Tools

**`tools/impedance_sweep.py`**

Runs a frequency sweep via `/impedance/sweep`, saves results as CSV and plots |Z|, phase, Rs, Xs vs frequency. Classifies DUT as R, L, C, series-LC, parallel-LC, or unknown.

```bash
python tools/impedance_sweep.py \
  --fstart 100 --fstop 1000000 --steps 100 \
  --amplitude 1.0 --probe_r 1000 \
  --out /tmp/impedance
```

Output: `impedance.csv`, `impedance.png`, `impedance_report.md`

**`tools/protocol_decode.py`**

Receives and decodes a stream of bytes over a chosen protocol, formats as hex + ASCII table, writes to Markdown.

```bash
python tools/protocol_decode.py \
  --protocol uart --baud 115200 \
  --rx_channel 1 --duration 2 \
  --out /tmp/uart_capture
```

---

## 10. Testing Requirements

### 10.1 Unit Tests (no hardware)

All tests continue to use mock-based approach (mock `dwf_adapter`):

| Test File | Coverage |
|-----------|----------|
| `test_digilent_api.py` | existing 40 tests + new endpoint tests |
| `test_capability_registry.py` | CapabilityRecord for all 12 device types; capability-gating on missing features |
| `test_impedance_service.py` | configure, single-point measure, sweep, compensation |
| `test_protocol_service.py` | UART send/receive, SPI write-read, I2C write-read-combined, CAN send/receive |
| `test_digital_io_service.py` | configure, read, write, mask operations |
| `test_pattern_service.py` | pulse, custom, random; stop all |
| `test_safety_limits.py` | range violations for all new endpoints |

**Target:** ≥ 120 tests total, all passing without hardware.

### 10.2 Hardware Smoke Tests

A separate `tests/hw/` directory contains tests that require a connected device:

- `hw_test_scope.py` — capture 100 samples from CH1, verify non-zero values
- `hw_test_wavegen.py` — generate 1 kHz sine, capture on CH1, verify frequency
- `hw_test_logic.py` — toggle a DIO pin, capture on logic analyzer, verify edge
- `hw_test_impedance.py` — measure open-circuit impedance (should be high, no short)
- `hw_test_protocol_loopback.py` — UART TX→RX loopback

---

## 11. Known Limitations and Device-Specific Notes

| Device / Issue | Workaround / Note |
|----------------|-------------------|
| AD2: `scope/capture` with trigger → HTTP 504 | Always use `trigger.enabled: false` for raw waveform capture; use `scope/measure` for triggered metrics only |
| AD2: Buffer overflow at high sample rates | 10 MS/s → max ~0.1 ms; 1 MS/s → max ~5 ms; clamp `duration_s` in server |
| AD2: `channel` field returns `int` not `"ch1"` | Normalized in `utils.py`: `f"ch{ch['channel']}" if isinstance(...)` |
| Digital Discovery: no AnalogIn/Out | `/scope/*` and `/wavegen/*` return 405; digital-only workflows only |
| Digital Discovery: DIO index offset | `digital_io_offset = 24` in CapabilityRecord; server adds offset transparently |
| ADP5250: limited acquisition modes | Validate against device on configure; return 400 with device-specific message |
| ADP5250: I2C/SPI pin assignment fixed | Protocol configure endpoint ignores channel params and uses fixed pins; warns in response |
| DPS3340: AnalogIn for monitoring only | `/scope/capture` allowed but results are slow (power monitoring, not oscilloscope bandwidth) |
| `session/reset` + `device/open` → NoneType | Fixed in new `device_manager.py`: full reset including `hdwf = None` guard |
| WaveForms GUI open | `FDwfDeviceOpen` returns `hdwfNone`; mapped to `DIGILENT_NOT_FOUND` with explanatory message |
| Multiple devices connected | Server uses first available non-open device; `--device-index N` flag overrides |

---

*End of Functional Specification Document*
