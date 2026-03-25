"""
Device capability registry.

Provides a static table of CapabilityRecord entries keyed by DEVID integer.
Phase 1 will populate the full table and add runtime config-info overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SupplyChannelDef:
    name: str
    channel_idx: int          # FDwfAnalogIOChannelNode channel index
    node_enable: int | None   # node index for enable (None = master only)
    node_voltage: int | None  # node index for voltage set
    node_current: int | None  # node index for current limit set
    node_v_mon: int | None    # node index for voltage monitor
    node_i_mon: int | None    # node index for current monitor
    min_v: float = 0.0
    max_v: float = 5.0
    is_negative: bool = False


@dataclass
class CapabilityRecord:
    devid: int
    name: str
    analog_in_ch: int = 0
    analog_out_ch: int = 0
    analog_io_ch: int = 0
    digital_in_ch: int = 0
    digital_out_ch: int = 0
    digital_io_ch: int = 0
    digital_io_offset: int = 0   # DD adds 24 to DIO channel indices
    has_impedance: bool = False
    has_protocols: bool = False
    has_dmm: bool = False
    has_power_supply: bool = False
    max_scope_rate_hz: float = 100_000_000
    max_scope_buffer: int = 8192
    max_logic_rate_hz: float = 100_000_000
    max_logic_buffer: int = 16384
    supply_channels: list[SupplyChannelDef] = field(default_factory=list)
    notes: str = ""


# Populated in Phase 1.
DEVICE_CAPABILITIES: dict[int, CapabilityRecord] = {}

# Fallback for unknown DEVID — assume minimal scope/wavegen.
UNKNOWN_DEVICE_CAP = CapabilityRecord(
    devid=-1,
    name="Unknown Digilent Device",
    analog_in_ch=2,
    analog_out_ch=2,
    has_protocols=True,
    has_power_supply=False,
    notes="Unrecognised DEVID — capability information may be inaccurate.",
)


def get_capability(devid: int) -> CapabilityRecord:
    """Return the CapabilityRecord for *devid*, falling back to UNKNOWN_DEVICE_CAP."""
    return DEVICE_CAPABILITIES.get(devid, UNKNOWN_DEVICE_CAP)
