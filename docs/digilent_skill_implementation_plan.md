# Implementation Plan
## Digilent WaveForms Universal Skill for Claude Code

**Version:** 1.0  
**Date:** 2026-03-25  
**Estimated Total Effort:** ~10–14 developer-days  
**Prerequisite:** FSD v1.0 approved

---

## Table of Contents

1. [Overview and Phasing](#1-overview-and-phasing)
2. [Phase 0 — Foundation (Days 1–2)](#2-phase-0--foundation)
3. [Phase 1 — Device Detection and Capabilities (Days 2–3)](#3-phase-1--device-detection-and-capabilities)
4. [Phase 2 — Extend Existing Modules (Days 3–5)](#4-phase-2--extend-existing-modules)
5. [Phase 3 — New Instrument Modules (Days 5–8)](#5-phase-3--new-instrument-modules)
6. [Phase 4 — Analysis Tools (Days 8–9)](#6-phase-4--analysis-tools)
7. [Phase 5 — Skill Definition and Integration (Days 9–10)](#7-phase-5--skill-definition-and-integration)
8. [Phase 6 — Testing and Hardening (Days 10–12)](#8-phase-6--testing-and-hardening)
9. [Phase 7 — Documentation and Release (Days 12–14)](#9-phase-7--documentation-and-release)
10. [Risk Register](#10-risk-register)
11. [Definition of Done](#11-definition-of-done)

---

## 1. Overview and Phasing

The implementation follows a layered bottom-up approach: SDK wrapper → device detection → instrument services → HTTP API → skill. Each phase ends with runnable tests. Hardware is only required for Phase 6 smoke tests.

```
Phase 0  Foundation fixes + repo prep
   │
Phase 1  capability_registry.py + universal device detection
   │
Phase 2  Extend scope, wavegen, supplies (fix known bugs)
   │
Phase 3  New services: digital_io, pattern, impedance, protocol
   │
Phase 4  New analysis tools: impedance_sweep.py, protocol_decode.py
   │
Phase 5  SKILL.md rewrite + api.py routing for all endpoints
   │
Phase 6  Unit tests (≥120) + hardware smoke tests
   │
Phase 7  Docs, changelog, release tag
```

---

## 2. Phase 0 — Foundation

**Duration:** 1–2 days  
**Goal:** Clean baseline; fix known bugs; prepare structure for new modules.

### Tasks

#### 0.1 Repository Prep

- [ ] Create feature branch `feature/universal-skill`
- [ ] Add `capability_registry.py`, `digital_io_service.py`, `pattern_service.py`, `impedance_service.py`, `protocol_service.py` as empty stubs
- [ ] Add `tests/test_capability_registry.py`, `tests/test_digital_io_service.py`, `tests/test_pattern_service.py`, `tests/test_impedance_service.py`, `tests/test_protocol_service.py` as empty stubs
- [ ] Update `digilent/__init__.py` to export new modules

#### 0.2 Bug Fixes (from Known Limitations)

- [ ] **Fix `session/reset` NoneType bug** in `device_manager.py`:
  - After `FDwfDeviceClose`, set `self.hdwf = None` and `self._device_name = None` before returning
  - Guard all subsequent operations with `if self.hdwf is None` check
- [ ] **Fix trigger timeout in `scope/measure`**: Current implementation uses a fixed 2s poll loop. Replace with configurable `auto_timeout_s` (default 0.5 s) respected in the poll
- [ ] **Normalize `channel` field** from int → `"ch{n}"` string in all scope response serializers in `utils.py`

#### 0.3 `errors.py` Extension

Add new error codes:

```python
class DigilentNotAvailable(DigilentError):
    """Instrument not present on this device."""
    code = "DIGILENT_NOT_AVAILABLE"
    http_status = 405

class DigilentSdkError(DigilentError):
    """libdwf returned an error code."""
    code = "DIGILENT_SDK_ERROR"
    http_status = 500

class DigilentProtocolError(DigilentError):
    """Parity/framing/ACK failure during protocol operation."""
    code = "DIGILENT_PROTOCOL_ERROR"
    http_status = 422

class DigilentSessionLost(DigilentError):
    """Device disconnected mid-session."""
    code = "DIGILENT_SESSION_LOST"
    http_status = 503
```

#### 0.4 `models.py` Extension

Add request/response dataclasses for all new endpoints (shapes defined in FSD §4 and §5).

---

## 3. Phase 1 — Device Detection and Capabilities

**Duration:** 1 day  
**Goal:** The server correctly detects any connected Digilent device, builds a `CapabilityRecord`, and returns it from `/api/digilent/capabilities`.

### Tasks

#### 1.1 `capability_registry.py` — Static Table

Create static `DEVICE_CAPABILITIES: dict[int, CapabilityRecord]` keyed by `DEVID` integer, populated from FSD §3.3 and SDK manual §14 tables.

Cover all 12 devices:

```python
DEVICE_CAPABILITIES = {
    1:  CapabilityRecord(devid=1,  name="Electronics Explorer",       analog_in_ch=8,  analog_out_ch=4, ...),
    2:  CapabilityRecord(devid=2,  name="Analog Discovery",           analog_in_ch=2,  analog_out_ch=2, ...),
    3:  CapabilityRecord(devid=3,  name="Analog Discovery 2",         analog_in_ch=2,  analog_out_ch=2, ...),
    4:  CapabilityRecord(devid=4,  name="Digital Discovery",          analog_in_ch=0,  analog_out_ch=0, ...),
    6:  CapabilityRecord(devid=6,  name="Analog Discovery Pro 3450",  analog_in_ch=4,  analog_out_ch=2, ...),
    8:  CapabilityRecord(devid=8,  name="Analog Discovery Pro 5250",  analog_in_ch=2,  analog_out_ch=2, has_dmm=True, ...),
    9:  CapabilityRecord(devid=9,  name="Discovery Power Supply 3340",analog_in_ch=2,  analog_out_ch=2, has_power_supply=True, ...),
    10: CapabilityRecord(devid=10, name="Analog Discovery 3",         analog_in_ch=2,  analog_out_ch=2, ...),
    14: CapabilityRecord(devid=14, name="Analog Discovery Pro 2230",  analog_in_ch=2,  analog_out_ch=2, ...),
    15: CapabilityRecord(devid=15, name="Analog Discovery Studio Max",analog_in_ch=2,  analog_out_ch=2, has_impedance=True, ...),
    16: CapabilityRecord(devid=16, name="Analog Discovery Pro 2440",  analog_in_ch=4,  analog_out_ch=2, ...),
    17: CapabilityRecord(devid=17, name="Analog Discovery Pro 2450",  analog_in_ch=4,  analog_out_ch=2, ...),
}
```

#### 1.2 `device_manager.py` — Universal Enumeration

Replace AD2-specific open logic with universal flow:

```python
def enumerate_devices(self) -> list[DeviceInfo]:
    """Call FDwfEnum, return list of DeviceInfo for all found devices."""
    nDev = c_int()
    self.dwf.FDwfEnum(enumfilterAll, byref(nDev))
    devices = []
    for idx in range(nDev.value):
        devid, devver = c_int(), c_int()
        self.dwf.FDwfEnumDeviceType(idx, byref(devid), byref(devver))
        name_buf = create_string_buffer(32)
        self.dwf.FDwfEnumDeviceName(idx, name_buf)
        sn_buf = create_string_buffer(32)
        self.dwf.FDwfEnumSN(idx, sn_buf)
        is_open = c_int()
        self.dwf.FDwfEnumDeviceIsOpened(idx, byref(is_open))
        devices.append(DeviceInfo(idx=idx, devid=devid.value, devver=devver.value,
                                   name=name_buf.value.decode(), sn=sn_buf.value.decode(),
                                   is_open=bool(is_open.value)))
    return devices

def open_device(self, device_index: int = -1) -> CapabilityRecord:
    devices = self.enumerate_devices()
    if not devices:
        raise DigilentNotFound("No WaveForms-compatible device found.")
    # select: -1 = first non-open; otherwise explicit index
    target = next((d for d in devices if not d.is_open), None) if device_index == -1 \
             else devices[device_index]
    if target is None:
        raise DigilentNotFound("All devices are in use by another process.")
    hdwf = c_int()
    self.dwf.FDwfDeviceOpen(target.idx, byref(hdwf))
    if hdwf.value == hdwfNone:
        raise DigilentNotFound("FDwfDeviceOpen failed — is WaveForms GUI open?")
    self.hdwf = hdwf
    # Build capability record, overriding static defaults with runtime config info
    cap = copy.deepcopy(DEVICE_CAPABILITIES.get(target.devid, UNKNOWN_DEVICE_CAP))
    self._apply_config_overrides(cap, target.idx)
    self.capability = cap
    return cap

def _apply_config_overrides(self, cap: CapabilityRecord, idx: int):
    """Use FDwfEnumConfigInfo to override static channel counts with actual values."""
    nCfg = c_int()
    self.dwf.FDwfEnumConfig(idx, byref(nCfg))
    if nCfg.value > 0:
        val = c_int()
        self.dwf.FDwfEnumConfigInfo(0, DECIAnalogInChannelCount, byref(val))
        if val.value > 0:
            cap.analog_in_ch = val.value
        # repeat for AnalogOut, DigitalIn, DigitalOut, DigitalIO, buffers
```

#### 1.3 `/api/digilent/capabilities` Endpoint

Returns serialized `CapabilityRecord` as JSON. No arguments required.

```json
{
  "ok": true,
  "device": "Analog Discovery 2",
  "data": {
    "devid": 3,
    "name": "Analog Discovery 2",
    "analog_in_ch": 2,
    "analog_out_ch": 2,
    "has_impedance": true,
    "has_protocols": true,
    "has_power_supply": true,
    "supply_channels": [...],
    "max_scope_rate_hz": 100000000,
    ...
  }
}
```

#### 1.4 `/api/digilent/status` Extension

Append `"capabilities": {...}` to existing status response so Claude Code gets device + capabilities in one call.

#### 1.5 Tests for Phase 1

In `test_capability_registry.py`:

- All 12 device IDs return a `CapabilityRecord` from static table
- Digital Discovery has `analog_in_ch == 0`
- DPS3340 has `has_protocols == False`
- ADS Max has `has_impedance == True`
- Mock-based test for `enumerate_devices` and `open_device` path
- `_apply_config_overrides` correctly overwrites `analog_in_ch` when `FDwfEnumConfigInfo` returns a different value

---

## 4. Phase 2 — Extend Existing Modules

**Duration:** 2 days  
**Goal:** All existing endpoints are universal (not AD2-specific), bugs fixed, capability-gated.

### Tasks

#### 2.1 `scope_service.py` — Capability Gate + Extensions

- [ ] Add `self.cap = device_manager.capability` reference
- [ ] Gate all methods: `if self.cap.analog_in_ch == 0: raise DigilentNotAvailable(...)`
- [ ] Add `filter` parameter (`FDwfAnalogInChannelFilterSet` with `filterDecimate`, `filterAverage`, `filterMinMax`)
- [ ] Add `/scope/sample` endpoint (single `FDwfAnalogInStatusSample` call per channel)
- [ ] Add `/scope/record` endpoint: set `acqmodeRecord`, poll with `FDwfAnalogInStatusRecord`, stream chunks
- [ ] Implement full trigger type support (`trigtype*` enum) with parameter validation
- [ ] Validate `sample_rate_hz` against `cap.max_scope_rate_hz` and `safe_limits`
- [ ] Respect `cap.analog_in_ch` for channel range validation (reject channel 3 on AD2)

#### 2.2 `wavegen_service.py` — Capability Gate + Extensions

- [ ] Gate: `if self.cap.analog_out_ch == 0: raise DigilentNotAvailable(...)`
- [ ] Add waveform types: `funcNoise`, `funcDC`, `funcCustom`, `funcRampUp`, `funcRampDown`
- [ ] Add custom waveform support via `FDwfAnalogOutNodeDataSet`
- [ ] Add modulation: AM (`modulationAM`), FM (`modulationFM`) with `FDwfAnalogOutNodeModulationSet`
- [ ] Add `FDwfAnalogOutMasterSet` for channel synchronization
- [ ] Validate against `safe_limits.max_wavegen_amplitude_v` and `max_wavegen_offset_v`
- [ ] Block EExplorer channels 3/4 for waveform (they are power outputs)

#### 2.3 `supplies_service.py` — Full Rewrite

Replace AD2-hardcoded supply logic with table-driven approach:

- [ ] Read `cap.supply_channels` list at initialization
- [ ] `GET /supplies/info` → return `cap.supply_channels` serialized
- [ ] `POST /supplies/set` → look up `channel_name` in `supply_channels`, call `FDwfAnalogIOChannelNodeSet`
- [ ] `GET /supplies/status` → iterate all channel nodes with `FDwfAnalogIOStatus` + `FDwfAnalogIOChannelNodeStatus`
- [ ] `POST /supplies/master` → `FDwfAnalogIOEnableSet`
- [ ] All supply writes: check `allow_supplies` flag; require `confirm_unsafe: true`
- [ ] Populate `supply_channels` for all 12 devices based on SDK §14 tables

---

## 5. Phase 3 — New Instrument Modules

**Duration:** 3 days  
**Goal:** Four new service modules with full HTTP integration.

### Tasks

#### 3.1 `digital_io_service.py` (0.5 day)

Three SDK calls: `FDwfDigitalIOOutputEnableSet`, `FDwfDigitalIOOutputSet`, `FDwfDigitalIOInputStatus`.

- [ ] `DigitalIOService.__init__` stores `cap` and `dwf`
- [ ] `configure(output_enable_mask, output_value)` → `FDwfDigitalIOOutputEnableSet` + `FDwfDigitalIOOutputSet` + `FDwfDigitalIOConfigure`
- [ ] `read()` → `FDwfDigitalIOStatus` + `FDwfDigitalIOInputStatus`
- [ ] `write(value, mask)` → read-modify-write with mask
- [ ] Handle `digital_io_offset` for Digital Discovery (add 24 to channel indices)
- [ ] Add 3 endpoints to `api.py`

#### 3.2 `pattern_service.py` (0.5 day)

- [ ] `PatternService.__init__` — gate on `cap.digital_out_ch > 0`
- [ ] `set(channel, type, frequency_hz, duty_pct, custom_data, run_s, repeat, idle_state)`:
  - `FDwfDigitalOutEnableSet`, `FDwfDigitalOutTypeSet`, `FDwfDigitalOutDividerSet`
  - For custom type: `FDwfDigitalOutDataSet`
  - For play type: gate on `devid == devidDDiscovery`
  - `FDwfDigitalOutConfigure(hdwf, 1)` to start
- [ ] `stop(channel_or_all)` → `FDwfDigitalOutConfigure(hdwf, 0)`
- [ ] Add 2 endpoints to `api.py`

#### 3.3 `impedance_service.py` (1 day)

This is the most complex new module.

- [ ] `ImpedanceService.__init__` — gate on `cap.has_impedance` (checks `analog_in_ch > 0 and analog_out_ch > 0`)
- [ ] `configure(frequency_hz, amplitude_v, offset_v, probe_resistance_ohm, probe_capacitance_f, min_periods)`:
  - `FDwfAnalogImpedanceReset`
  - `FDwfAnalogImpedanceFrequencySet`
  - `FDwfAnalogImpedanceAmplitudeSet`
  - `FDwfAnalogImpedanceOffsetSet`
  - `FDwfAnalogImpedanceProbeSet`
  - `FDwfAnalogImpedancePeriodSet`
  - For ADS Max: `FDwfAnalogImpedanceEnableSet(1)`
- [ ] `measure(measurements: list[str]) -> dict`:
  - `FDwfAnalogImpedaceConfigure(hdwf, 1)`
  - Poll `FDwfAnalogImpedanceStatus` until `DwfStateDone`
  - For each requested measurement: `FDwfAnalogImpedanceStatusMeasure(hdwf, enum_val, &value)`
  - Check `FDwfAnalogImpedanceStatusWarning` for range overflow
  - Return dict with measurement names → values
- [ ] `sweep(f_start, f_stop, steps, amplitude_v, ...)`:
  - Loop over log-spaced frequencies
  - `FDwfAnalogImpedanceFrequencySet` for each step
  - Wait for acquisition to complete
  - Append measurement dict to results array
  - Return `{"frequencies": [...], "measurements": {"Impedance": [...], ...}}`
- [ ] `set_compensation(open_r, open_x, short_r, short_x)`:
  - `FDwfAnalogImpedanceCompSet`
- [ ] Add 4 endpoints to `api.py`; validate `amplitude_v` against `safe_limits.max_impedance_sweep_amplitude_v`

#### 3.4 `protocol_service.py` (1 day)

Structure: one service class per protocol, all living in `protocol_service.py`. A top-level `ProtocolService` routes to the correct sub-service.

**UART:**

```python
class UartProtocol:
    def configure(self, baud_rate, bits, parity, stop_bits, tx_ch, rx_ch, polarity): ...
        # FDwfDigitalUartReset, RateSet, BitsSet, ParitySet, StopSet, TxSet, RxSet, PolaritySet
    def send(self, data: bytes): ...
        # FDwfDigitalUartTx
    def receive(self, max_bytes: int, timeout_s: float) -> tuple[bytes, int]: ...
        # FDwfDigitalUartRx — poll until data arrives or timeout
```

**SPI:**

```python
class SpiProtocol:
    def configure(self, freq_hz, mode, clk_ch, mosi_ch, miso_ch, cs_ch, cs_idle, order, duty_pct): ...
        # FDwfDigitalSpiReset, FrequencySet, ClockSet, DataSet, ModeSet, OrderSet, SelectSet, DutySet
    def transfer(self, tx_data: bytes, rx_len: int) -> bytes: ...
        # FDwfDigitalSpiWriteRead
```

**I2C:**

```python
class I2cProtocol:
    def configure(self, rate_hz, scl_ch, sda_ch): ...
        # FDwfDigitalI2cReset, RateSet, SclSet, SdaSet
    def write(self, address, data: bytes) -> int: ...
        # FDwfDigitalI2cWrite — returns NAK count
    def read(self, address, length: int) -> bytes: ...
        # FDwfDigitalI2cRead
    def write_read(self, address, tx: bytes, rx_len: int) -> bytes: ...
        # FDwfDigitalI2cWriteRead
```

**CAN:**

```python
class CanProtocol:
    def configure(self, rate_hz, tx_ch, rx_ch): ...
        # FDwfDigitalCanReset, RateSet, TxSet, RxSet
    def send(self, id: int, data: bytes, extended: bool, remote: bool): ...
        # FDwfDigitalCanTx
    def receive(self, timeout_s: float) -> CanFrame: ...
        # FDwfDigitalCanRx
```

- [ ] ADP5250 constraint enforcement (fixed pins; warn in response `"device_note"` field)
- [ ] Add all 12 protocol endpoints to `api.py`
- [ ] Gate all protocol endpoints: `if not cap.has_protocols: raise DigilentNotAvailable(...)`

---

## 6. Phase 4 — Analysis Tools

**Duration:** 1 day

### Tasks

#### 4.1 `tools/impedance_sweep.py`

- [ ] Parse CLI args (fstart, fstop, steps, amplitude, probe_r, probe_c, out)
- [ ] Call `POST /impedance/configure` then `POST /impedance/sweep`
- [ ] Save results to CSV (frequency, |Z|, phase, Rs, Xs, Cs, Ls columns)
- [ ] Plot with matplotlib: two-panel (|Z| dB + Phase deg vs log frequency)
- [ ] Simple DUT classifier: analyze slope and phase to return type label
- [ ] Write Markdown report: device name, params, DUT type, key metrics

#### 4.2 `tools/protocol_decode.py`

- [ ] Parse CLI args (protocol, baud/rate, channels, duration, out)
- [ ] Configure and receive data via HTTP API
- [ ] Format output as 16-byte-wide hex + ASCII table
- [ ] Write Markdown with protocol summary, frame count, error count

---

## 7. Phase 5 — Skill Definition and Integration

**Duration:** 1 day

### Tasks

#### 5.1 `api.py` — Route Registration

- [ ] Register all new endpoints from FSD §5.1 (26 new routes)
- [ ] Add capability-gate middleware: decorator `@require_capability("analog_in")` that checks `device_manager.capability` before dispatching
- [ ] Add standard response envelope wrapper
- [ ] Handle `DigilentNotAvailable` → 405 with structured JSON error

#### 5.2 `orchestration.py` — Extended High-Level Actions

Add new `measure/basic` actions:

| Action | Description |
|--------|-------------|
| `measure_voltage_dc` | Existing — now device-universal |
| `measure_pwm` | Existing — fixed trigger timeout |
| `detect_logic_activity` | Existing — extended channel range |
| `bode_sweep` | New — calls impedance sweep, returns gain/phase at given freq |
| `uart_loopback_test` | New — configure UART, send pattern, verify echo |
| `i2c_scan` | New — scan 0x00–0x7F, return list of responding addresses |
| `characterize_supply` | New — enable supply, measure actual voltage, check regulation |
| `digital_frequency` | New — toggle DIO pin, measure with logic analyzer |

#### 5.3 `.claude/skills/digilent-local/SKILL.md` — Full Rewrite

Structure of new SKILL.md:

```markdown
# digilent-local skill

## Purpose
## Prerequisites
## Quick start: check what device is connected
  curl .../capabilities → explains available instruments
## Oscilloscope
  - capture waveform (curl example)
  - measure metrics (curl example)
  - record long signal (curl example)
## Waveform Generator
  - generate sine/square/custom (curl example)
## Power Supplies
  - read monitor (curl example)
  - enable supply (curl example with confirm_unsafe)
## Logic Analyzer
  - capture digital signals (curl example)
## Pattern Generator
  - drive digital pin at frequency (curl example)
## Analog Impedance Analyzer
  - measure component value (curl example)
  - run frequency sweep (curl example)
## Digital Protocols
  - UART send/receive (curl example)
  - I2C scan (curl example)
  - SPI transfer (curl example)
## High-level shortcuts (measure/basic)
  - action list with params
## Analysis scripts
  - plot_waveform.py, fft_analyze.py, dut_identify.py, impedance_sweep.py, protocol_decode.py
## Error reference
## Safety rules
```

---

## 8. Phase 6 — Testing and Hardening

**Duration:** 2 days

### Tasks

#### 6.1 Unit Tests

Achieve ≥ 120 unit tests all passing without hardware. Run via:

```bash
python -m pytest tests/ -v --tb=short
```

Coverage targets (mock-based):

| Module | Min Tests |
|--------|-----------|
| capability_registry | 20 |
| device_manager (enumerate + open) | 10 |
| scope_service (existing + new) | 15 |
| wavegen_service (existing + new) | 10 |
| supplies_service (rewrite) | 12 |
| digital_io_service | 8 |
| pattern_service | 8 |
| impedance_service | 15 |
| protocol_service (UART+SPI+I2C+CAN) | 16 |
| api.py routing + capability gates | 12 |
| orchestration (new actions) | 8 |
| error handling + safety limits | 10 |

#### 6.2 Hardware Smoke Tests

Run on each available physical device (at minimum on AD2):

```bash
python -m pytest tests/hw/ -v --device ad2
```

Smoke test checklist:

- [ ] Server starts and `/ping` returns 200
- [ ] `/capabilities` returns correct device name and channel counts
- [ ] `/scope/capture` returns non-empty waveform data on CH1
- [ ] `/scope/measure` returns Vpp and frequency within tolerance
- [ ] `/wavegen/set` generates 1 kHz sine; verified by scope capture
- [ ] `/supplies/status` returns valid USB voltage (4.5–5.5 V on AD2)
- [ ] `/logic/capture` detects edges when a DIO is toggled
- [ ] `/pattern/set` + `/pattern/stop` completes without error
- [ ] `/impedance/measure` returns non-zero impedance for 1 kΩ resistor
- [ ] `/protocol/uart/send` + `/receive` loopback test passes
- [ ] All 405 endpoints return correct error for missing capability (Digital Discovery)

#### 6.3 Concurrent Request Test

Verify `DIGILENT_BUSY` (409) is returned when two requests hit the server simultaneously:

```bash
curl .../scope/capture & curl .../wavegen/set &
# One should succeed, one should return 409
```

---

## 9. Phase 7 — Documentation and Release

**Duration:** 2 days

### Tasks

#### 7.1 `docs/device-capabilities.md`

Reference table of all device capabilities, supply topologies, and known constraints. Generated from `capability_registry.py`.

#### 7.2 `docs/integration-guide.md` — Update

Add sections for: impedance analyzer, digital protocols, pattern generator, universal device detection.

#### 7.3 `docs/extending-waveform-export.md` — Update

Add section for `impedance_sweep.py` and `protocol_decode.py`.

#### 7.4 `README.md` — Update

- New API reference table (all endpoints)
- New analysis tools section
- Update platform support table (verify ADP3000 Linux ARM path)
- Update Known Limitations table

#### 7.5 `CHANGELOG.md`

Document all changes from the initial partial implementation.

#### 7.6 Release Tag

```bash
git tag v2.0.0-universal
git push origin feature/universal-skill
# Open PR → review → merge → tag on main
```

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ADP5250 has undocumented constraints beyond SDK §14.6 | Medium | Medium | Test against hardware; add device-specific notes dynamically via error messages |
| `FDwfAnalogImpedanceStatus` poll loop hangs on some devices | Medium | High | Add hard timeout (default 5 s), catch and raise `DIGILENT_CAPTURE_TIMEOUT` |
| Digital Discovery channel index offset causes silent miscapture | Medium | High | Unit test with mock verifying offset is applied before SDK calls |
| `FDwfEnum` blocks for several seconds on some OS/USB configurations | Low | Medium | Wrap in thread with 10 s timeout; surface as `DIGILENT_NOT_FOUND` if exceeded |
| Concurrent requests between protocol TX and RX cause race condition | Medium | Medium | Hold session lock for the duration of a full protocol transaction |
| ADS Max impedance enable (`FDwfAnalogImpedanceEnableSet`) permanently alters device config | Low | High | Always reset impedance (`FDwfAnalogImpedanceReset`) on device close |
| Protocol decode on fast UART (≥ 1 Mbaud) fills buffer between polls | Medium | Medium | Use `FDwfDigitalUartRx` in tight poll loop with 10 ms interval; warn if buffer overflow (parity < 0) |

---

## 11. Definition of Done

The implementation is complete and releasable when all of the following are true:

- [ ] All 26 new endpoints return correct responses (verified by unit tests)
- [ ] All 12 device types return a correct `CapabilityRecord` (static table unit tests)
- [ ] Capability-gating returns 405 for missing instruments (unit tests for each capability gate)
- [ ] ≥ 120 unit tests pass with zero hardware (`python -m pytest tests/`)
- [ ] Hardware smoke tests pass on at minimum 1 physical device (AD2 or AD3)
- [ ] Both new analysis tools (`impedance_sweep.py`, `protocol_decode.py`) produce expected output files
- [ ] `SKILL.md` covers all instruments with at least one curl example each
- [ ] `README.md` is up to date with the complete API table
- [ ] All three previously known bugs are fixed (session/reset NoneType, trigger timeout, channel normalization)
- [ ] `python -m pytest tests/ -v` produces 0 failures, 0 errors
- [ ] The skill triggers correctly in Claude Code when asked about oscilloscopes, logic analyzers, impedance, UART, SPI, I2C, and CAN

---

*End of Implementation Plan*
