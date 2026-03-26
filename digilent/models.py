"""Request and response data models for the Digilent HTTP API."""

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Trigger config
# ---------------------------------------------------------------------------

@dataclass
class TriggerConfig:
    enabled: bool = False
    source: str = "ch1"        # "ch1", "ch2", "ext", "pc"
    type: str = "edge"         # "edge", "pulse", "transition", "window"
    edge: str = "rising"       # "rising", "falling", "either"
    channel: int = 0           # for logic trigger
    level_v: float = 1.0
    timeout_ms: int = 1000
    auto_timeout_s: float = 0.5  # configurable trigger auto-timeout

    @classmethod
    def from_dict(cls, d: dict) -> "TriggerConfig":
        t = cls()
        for k, v in d.items():
            if hasattr(t, k):
                setattr(t, k, v)
        return t


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

@dataclass
class ScopeCaptureRequest:
    channels: list[int] = field(default_factory=lambda: [1])
    range_v: float = 5.0
    offset_v: float = 0.0
    sample_rate_hz: int = 1_000_000
    duration_ms: int = 10
    filter: str = "none"       # "none", "decimate", "average", "minmax"
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    return_waveform: bool = False
    max_points: int = 5000

    @classmethod
    def from_dict(cls, d: dict) -> "ScopeCaptureRequest":
        r = cls()
        trig_raw = d.pop("trigger", None)
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        if trig_raw:
            r.trigger = TriggerConfig.from_dict(trig_raw)
        return r


@dataclass
class ScopeSampleRequest:
    channels: list[int] = field(default_factory=lambda: [1])
    range_v: float = 5.0
    offset_v: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "ScopeSampleRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class ScopeRecordRequest:
    """Stream long recordings using FDwfAnalogIn record mode."""
    channels: list[int] = field(default_factory=lambda: [1])
    range_v: float = 5.0
    offset_v: float = 0.0
    sample_rate_hz: float = 1_000_000.0
    duration_ms: float = 100.0          # total record length
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    return_waveform: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "ScopeRecordRequest":
        r = cls()
        trig_raw = d.pop("trigger", None)
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        if trig_raw:
            r.trigger = TriggerConfig.from_dict(trig_raw)
        return r


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

@dataclass
class LogicCaptureRequest:
    channels: list[int] = field(default_factory=lambda: [0])
    sample_rate_hz: int = 10_000_000
    samples: int = 20_000
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    return_samples: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "LogicCaptureRequest":
        r = cls()
        trig_raw = d.pop("trigger", None)
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        if trig_raw:
            r.trigger = TriggerConfig.from_dict(trig_raw)
        return r


# ---------------------------------------------------------------------------
# Wavegen
# ---------------------------------------------------------------------------

@dataclass
class WavegenRequest:
    channel: int = 1
    waveform: str = "sine"      # sine, square, triangle, dc, rampup, rampdown, noise, custom
    frequency_hz: float = 1000.0
    amplitude_v: float = 1.0
    offset_v: float = 0.0
    symmetry_percent: float = 50.0
    phase_deg: float = 0.0
    enable: bool = True
    custom_data: list[float] = field(default_factory=list)
    modulation: dict = field(default_factory=dict)  # {"type": "am"|"fm", "freq_hz": float, "depth": float}

    @classmethod
    def from_dict(cls, d: dict) -> "WavegenRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Supplies
# ---------------------------------------------------------------------------

@dataclass
class SuppliesRequest:
    vplus_v: float = 3.3
    vminus_v: float = 0.0
    enable_vplus: bool = False
    enable_vminus: bool = False
    confirm_unsafe: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "SuppliesRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Static I/O
# ---------------------------------------------------------------------------

@dataclass
class StaticIoPin:
    index: int = 0
    mode: str = "input"     # "input", "output"
    value: int = 0          # 0 or 1

    @classmethod
    def from_dict(cls, d: dict) -> "StaticIoPin":
        return cls(
            index=d.get("index", 0),
            mode=d.get("mode", "input"),
            value=d.get("value", 0),
        )


@dataclass
class StaticIoRequest:
    pins: list[StaticIoPin] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "StaticIoRequest":
        pins = [StaticIoPin.from_dict(p) for p in d.get("pins", [])]
        return cls(pins=pins)


# ---------------------------------------------------------------------------
# Basic measure (orchestration)
# ---------------------------------------------------------------------------

@dataclass
class BasicMeasureRequest:
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "BasicMeasureRequest":
        return cls(
            action=d.get("action", ""),
            params=d.get("params", {}),
        )


# ---------------------------------------------------------------------------
# Digital I/O
# ---------------------------------------------------------------------------

@dataclass
class DigitalIOConfigureRequest:
    output_enable_mask: int = 0x0000   # bitmask: 1 = output, 0 = input
    output_value: int = 0x0000         # initial output state

    @classmethod
    def from_dict(cls, d: dict) -> "DigitalIOConfigureRequest":
        return cls(
            output_enable_mask=int(d.get("output_enable_mask", 0), 0)
                if isinstance(d.get("output_enable_mask"), str)
                else d.get("output_enable_mask", 0),
            output_value=int(d.get("output_value", 0), 0)
                if isinstance(d.get("output_value"), str)
                else d.get("output_value", 0),
        )


@dataclass
class DigitalIOWriteRequest:
    value: int = 0x0000   # new output bit values
    mask: int = 0xFFFF    # bits to update (1 = update this bit)

    @classmethod
    def from_dict(cls, d: dict) -> "DigitalIOWriteRequest":
        return cls(
            value=int(d.get("value", 0), 0)
                if isinstance(d.get("value"), str) else d.get("value", 0),
            mask=int(d.get("mask", 0xFFFF), 0)
                if isinstance(d.get("mask"), str) else d.get("mask", 0xFFFF),
        )


# ---------------------------------------------------------------------------
# Pattern Generator
# ---------------------------------------------------------------------------

@dataclass
class PatternSetRequest:
    channel: int = 0
    enabled: bool = True
    type: str = "pulse"             # "pulse", "bfs", "custom", "random"
    frequency_hz: float = 1000.0
    duty_pct: float = 50.0
    initial_value: int = 0
    idle_state: str = "low"         # "low", "high", "zstate", "initial"
    custom_data: str = ""           # hex string e.g. "0xA5B3..."
    run_s: float = 0.0              # 0 = run indefinitely
    repeat: int = 0                 # 0 = repeat indefinitely

    @classmethod
    def from_dict(cls, d: dict) -> "PatternSetRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class PatternStopRequest:
    channel: Any = "all"   # int channel index or "all"

    @classmethod
    def from_dict(cls, d: dict) -> "PatternStopRequest":
        return cls(channel=d.get("channel", "all"))


# ---------------------------------------------------------------------------
# Impedance Analyzer
# ---------------------------------------------------------------------------

@dataclass
class ImpedanceConfigureRequest:
    frequency_hz: float = 1000.0
    amplitude_v: float = 1.0
    offset_v: float = 0.0
    probe_resistance_ohm: float = 1000.0
    probe_capacitance_f: float = 0.0
    min_periods: int = 16

    @classmethod
    def from_dict(cls, d: dict) -> "ImpedanceConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class ImpedanceMeasureRequest:
    measurements: list[str] = field(default_factory=lambda: [
        "Impedance", "ImpedancePhase", "Resistance", "Reactance"
    ])

    @classmethod
    def from_dict(cls, d: dict) -> "ImpedanceMeasureRequest":
        return cls(measurements=d.get("measurements", [
            "Impedance", "ImpedancePhase", "Resistance", "Reactance"
        ]))


@dataclass
class ImpedanceSweepRequest:
    f_start_hz: float = 100.0
    f_stop_hz: float = 1_000_000.0
    steps: int = 100
    amplitude_v: float = 1.0
    offset_v: float = 0.0
    probe_resistance_ohm: float = 1000.0
    probe_capacitance_f: float = 0.0
    min_periods: int = 16
    measurements: list[str] = field(default_factory=lambda: [
        "Impedance", "ImpedancePhase", "Resistance", "Reactance"
    ])

    @classmethod
    def from_dict(cls, d: dict) -> "ImpedanceSweepRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class ImpedanceCompensationRequest:
    open_r: float = 0.0    # open-circuit resistance compensation
    open_x: float = 0.0    # open-circuit reactance compensation
    short_r: float = 0.0   # short-circuit resistance compensation
    short_x: float = 0.0   # short-circuit reactance compensation

    @classmethod
    def from_dict(cls, d: dict) -> "ImpedanceCompensationRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Protocol — UART
# ---------------------------------------------------------------------------

@dataclass
class UartConfigureRequest:
    baud_rate: int = 115200
    bits: int = 8
    parity: str = "none"    # "none", "even", "odd", "mark", "space"
    stop_bits: float = 1.0
    tx_ch: int = 0
    rx_ch: int = 1
    polarity: int = 0       # 0 = normal, 1 = inverted

    @classmethod
    def from_dict(cls, d: dict) -> "UartConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class UartSendRequest:
    data: str = ""          # UTF-8 string or hex-encoded bytes

    @classmethod
    def from_dict(cls, d: dict) -> "UartSendRequest":
        return cls(data=d.get("data", ""))


@dataclass
class UartReceiveRequest:
    max_bytes: int = 256
    timeout_s: float = 1.0

    @classmethod
    def from_dict(cls, d: dict) -> "UartReceiveRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Protocol — SPI
# ---------------------------------------------------------------------------

@dataclass
class SpiConfigureRequest:
    freq_hz: float = 1_000_000.0
    mode: int = 0           # SPI mode 0–3 (CPOL/CPHA)
    clk_ch: int = 0
    mosi_ch: int = 1
    miso_ch: int = 2
    cs_ch: int = 3
    cs_idle: int = 1        # idle state of CS: 1 = high (active-low), 0 = low
    order: str = "msb"      # "msb" or "lsb"
    duty_pct: float = 50.0

    @classmethod
    def from_dict(cls, d: dict) -> "SpiConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class SpiTransferRequest:
    tx_data: list[int] = field(default_factory=list)   # bytes as int list
    rx_len: int = 0                                     # number of bytes to receive

    @classmethod
    def from_dict(cls, d: dict) -> "SpiTransferRequest":
        return cls(
            tx_data=d.get("tx_data", []),
            rx_len=d.get("rx_len", 0),
        )


# ---------------------------------------------------------------------------
# Protocol — I2C
# ---------------------------------------------------------------------------

@dataclass
class I2cConfigureRequest:
    rate_hz: float = 100_000.0
    scl_ch: int = 0
    sda_ch: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "I2cConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class I2cWriteRequest:
    address: int = 0x00
    data: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "I2cWriteRequest":
        return cls(address=d.get("address", 0), data=d.get("data", []))


@dataclass
class I2cReadRequest:
    address: int = 0x00
    length: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "I2cReadRequest":
        return cls(address=d.get("address", 0), length=d.get("length", 1))


@dataclass
class I2cWriteReadRequest:
    address: int = 0x00
    tx: list[int] = field(default_factory=list)
    rx_len: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "I2cWriteReadRequest":
        return cls(
            address=d.get("address", 0),
            tx=d.get("tx", []),
            rx_len=d.get("rx_len", 1),
        )


# ---------------------------------------------------------------------------
# Protocol — I2C Spy (passive sniffer)
# ---------------------------------------------------------------------------

@dataclass
class I2cSpyConfigureRequest:
    """Configure I2C spy mode. Pins are monitored passively — no bus traffic generated."""
    rate_hz: float = 100_000.0
    scl_ch: int = 0
    sda_ch: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "I2cSpyConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class I2cSpyReadRequest:
    """Collect I2C spy frames for a given duration."""
    duration_s: float = 1.0
    max_bytes: int = 256    # per-poll receive buffer
    max_frames: int = 256   # stop early after this many frames

    @classmethod
    def from_dict(cls, d: dict) -> "I2cSpyReadRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Protocol — Sniff (passive receive)
# ---------------------------------------------------------------------------

@dataclass
class UartSniffRequest:
    """Passively listen on a UART RX line without driving TX."""
    rx_ch: int = 1
    baud_rate: int = 9600
    bits: int = 8
    parity: str = "none"
    stop_bits: float = 1.0
    duration_s: float = 1.0
    max_bytes: int = 4096

    @classmethod
    def from_dict(cls, d: dict) -> "UartSniffRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class CanSniffRequest:
    """Passively receive CAN frames without transmitting."""
    rx_ch: int = 1
    rate_hz: float = 500_000.0
    duration_s: float = 2.0
    max_frames: int = 64

    @classmethod
    def from_dict(cls, d: dict) -> "CanSniffRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class SpiSniffRequest:
    """Passively capture SPI bus using logic analyzer + software decode."""
    clk_ch: int = 0
    mosi_ch: int = 1
    miso_ch: int = 2
    cs_ch: int = 3
    spi_freq_hz: float = 1_000_000.0
    mode: int = 0           # SPI mode 0-3 (CPOL/CPHA)
    order: str = "msb"
    duration_s: float = 1.0
    cs_active_low: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "SpiSniffRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ---------------------------------------------------------------------------
# Protocol — CAN
# ---------------------------------------------------------------------------

@dataclass
class CanConfigureRequest:
    rate_hz: float = 500_000.0
    tx_ch: int = 0
    rx_ch: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "CanConfigureRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class CanSendRequest:
    id: int = 0x000
    data: list[int] = field(default_factory=list)
    extended: bool = False   # True = 29-bit ID
    remote: bool = False     # True = remote frame

    @classmethod
    def from_dict(cls, d: dict) -> "CanSendRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class CanReceiveRequest:
    timeout_s: float = 1.0

    @classmethod
    def from_dict(cls, d: dict) -> "CanReceiveRequest":
        return cls(timeout_s=d.get("timeout_s", 1.0))


# ---------------------------------------------------------------------------
# Supplies (new universal model alongside existing SuppliesRequest)
# ---------------------------------------------------------------------------

@dataclass
class SuppliesSetRequest:
    channel_name: str = ""        # e.g. "V+", "V-", "VIO"
    enable: bool = False
    voltage_v: float | None = None
    current_limit_a: float | None = None
    confirm_unsafe: bool = False  # must be True to execute any supply write

    @classmethod
    def from_dict(cls, d: dict) -> "SuppliesSetRequest":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


@dataclass
class SuppliesMasterRequest:
    enable: bool = False
    confirm_unsafe: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "SuppliesMasterRequest":
        return cls(
            enable=d.get("enable", False),
            confirm_unsafe=d.get("confirm_unsafe", False),
        )
