# Changelog

All notable changes to this project are documented here.

---

## [2.0.0-universal] — 2026-03-25

### Summary

Full rewrite of the Digilent local skill to support all Digilent WaveForms
devices universally, including Digital Discovery, Analog Discovery Pro series,
and Analytics Discovery Studio Max. Adds digital I/O, pattern generator,
impedance analyzer, digital protocols (UART/SPI/I2C/CAN), five new
orchestration actions, two new analysis tools, and comprehensive unit tests.

### Added

#### Device Support
- `capability_registry.py` — static capability table for 12 device types
  (DEVID 1–17), with per-device supply topology, sample rates, buffer depths,
  and feature flags (`has_protocols`, `has_impedance`, `has_dmm`, etc.)
- Universal device detection: `get_capability(devid)` with deep-copy and
  fallback to `UNKNOWN_DEVICE_CAP` for unrecognised devices
- `CapabilityRecord.digital_io_offset` — Digital Discovery DIO channel
  index offset (24), applied automatically by `digital_io_service.py`

#### New Instrument Services
- `digital_io_service.py` — configure output mask and pull-ups, read all
  DIO pins, write output pins; offset-aware for Digital Discovery
- `pattern_service.py` — pattern generator: `clock`, `pulse`, `random`,
  `custom`, `bfs` waveform types; divider/counter frequency calculation
- `impedance_service.py` — single-frequency measure, log-spaced frequency
  sweep, open/short/load compensation; validates against `safe_limits`
- `protocol_service.py` — UART (configure/send/receive), SPI (transfer),
  I2C (write/read/write-read), CAN (send/receive); all gated on
  `has_protocols` capability flag

#### New API Endpoints (21 new routes)
- `GET  /digital-io/read`
- `POST /digital-io/configure`, `/digital-io/write`
- `POST /pattern/set`, `/pattern/stop`
- `POST /impedance/configure`, `/impedance/measure`, `/impedance/sweep`,
  `/impedance/compensation`
- `POST /protocol/uart/configure`, `/uart/send`, `/uart/receive`
- `POST /protocol/spi/configure`, `/spi/transfer`
- `POST /protocol/i2c/configure`, `/i2c/write`, `/i2c/read`, `/i2c/write-read`
- `POST /protocol/can/configure`, `/can/send`, `/can/receive`

#### Extended API Endpoints (Phase 2)
- `POST /scope/sample` — instantaneous single-sample read per channel
- `GET  /supplies/info` — supply channel list with voltage ranges
- `GET  /supplies/status` — current voltage/current monitor readings
- `POST /supplies/master` — master enable/disable all rails
- `POST /wavegen/custom` — upload custom normalized waveform data
- Wavegen: added `phase_deg`, `custom_data`, `modulation` fields

#### Orchestration Actions (5 new)
- `bode_sweep` — wavegen + scope log-spaced frequency sweep; returns
  `gain_db[]`, `phase_deg[]`, `fc_3db_hz`
- `uart_loopback_test` — configure, send, receive, compare
- `i2c_scan` — probe 0x08–0x77, return responding hex addresses
- `characterize_supply` — enable rail, settle, measure with scope
- `digital_frequency` — logic capture → `freq_hz`, `duty_cycle_percent`

#### Analysis Tools
- `tools/impedance_sweep.py` — log-spaced impedance sweep CLI; DUT
  classifier (resistor/capacitor/inductor/RC/RL/complex with estimated value);
  produces `.csv`, `.png` (|Z| + phase Bode chart), `.md`
- `tools/protocol_decode.py` — protocol capture CLI (UART/I2C/SPI/CAN);
  hex+ASCII dump formatter; produces `.hex`, `.md` (frame table)

#### Documentation
- `docs/device-capabilities.md` — per-device capability reference table
- `docs/integration-guide.md` — updated with all new instruments
- `docs/extending-waveform-export.md` — new section for `impedance_sweep.py`
  and `protocol_decode.py`
- `README.md` — complete API reference, all analysis tools, error code table,
  updated project structure, platform notes
- `.claude/skills/digilent-local/SKILL.md` — full rewrite covering all
  instruments with curl examples, safety rules, wiring reference

#### Error Codes
- `DIGILENT_NOT_AVAILABLE` (HTTP 405) — instrument not present on this device
- `DIGILENT_DWF_ERROR` (HTTP 422) — WaveForms SDK returned an error
- `DIGILENT_INTERNAL` (HTTP 500) — unexpected server error

#### Tests
- 186 unit tests total (all mock-based, no hardware required)
- New test classes: `TestScopePhase2`, `TestWavegenPhase2`, `TestSuppliesPhase2`,
  `TestDigitalIOPhase3`, `TestPatternPhase3`, `TestImpedancePhase3`,
  `TestProtocolPhase3` (in `test_digilent_api.py`)
- New files: `test_orchestration_service.py` (18 tests),
  `test_capability_registry.py`, `test_digital_io_service.py`,
  `test_impedance_service.py`, `test_pattern_service.py`,
  `test_protocol_service.py`

### Changed

- `supplies_service.py` — full rewrite: table-driven node operations using
  `CapabilityRecord.supply_channels`; `set_legacy()` for old
  `SuppliesRequest` API; `set()` for new channel-based `SuppliesSetRequest`
- `scope_service.py` — capability gate (requires `analog_in_ch > 0`);
  channel/rate validation; filter support; new `sample()` method
- `wavegen_service.py` — capability gate; new waveform types; custom data
  and modulation support
- `orchestration.py` — imports and instantiates all new services;
  `measure_basic` dispatch extended to 8 actions
- `api.py` — 21 new routes registered; existing routes aligned with new
  service signatures

### Fixed

- `session/reset` NoneType error — `device_manager.py` now sets `hdwf = None`
  after `FDwfDeviceClose` and guards subsequent operations
- Trigger timeout — configurable `auto_timeout_s` (default 0.5 s) in scope
  poll loop

---

## [1.0.0] — initial release

- Analog Discovery 2 support
- Oscilloscope (`scope/capture`, `scope/measure`)
- Logic analyzer (`logic/capture`)
- Waveform generator (`wavegen/set`, `wavegen/stop`)
- Static I/O (`static-io/set`)
- Power supplies (`supplies/set`)
- High-level actions: `measure_esp32_pwm`, `measure_voltage_level`,
  `detect_logic_activity`
- Analysis tools: `plot_waveform.py`, `fft_analyze.py`, `dut_identify.py`
- 40 unit tests
