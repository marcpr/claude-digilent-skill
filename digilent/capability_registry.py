"""
Device capability registry.

Provides:
  - SupplyChannelDef   — describes one named supply/monitor channel
  - CapabilityRecord   — full capability snapshot for one device type
  - DeviceEnumInfo     — raw info from FDwfEnum* (used during open)
  - DEVICE_CAPABILITIES — static table keyed by DEVID integer
  - get_capability(devid) — lookup with UNKNOWN_DEVICE_CAP fallback
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Supply channel definition
# ---------------------------------------------------------------------------

@dataclass
class SupplyChannelDef:
    name: str
    channel_idx: int          # FDwfAnalogIOChannelNode channel index (ch argument)
    node_enable: int | None   # node index for enable (None = use master enable only)
    node_voltage: int | None  # node index for voltage set (None = fixed voltage)
    node_current: int | None  # node index for current limit set
    node_v_mon: int | None    # node index for voltage monitor
    node_i_mon: int | None    # node index for current monitor
    min_v: float = 0.0
    max_v: float = 5.0
    is_negative: bool = False  # True → voltages are negative (V- rail)
    read_only: bool = False    # True → monitor only, no set

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "channel_idx": self.channel_idx,
            "min_v": self.min_v,
            "max_v": self.max_v,
            "is_negative": self.is_negative,
            "read_only": self.read_only,
            "has_enable": self.node_enable is not None,
            "has_voltage_set": self.node_voltage is not None,
            "has_current_limit": self.node_current is not None,
            "has_voltage_monitor": self.node_v_mon is not None,
            "has_current_monitor": self.node_i_mon is not None,
        }


# ---------------------------------------------------------------------------
# Capability record
# ---------------------------------------------------------------------------

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
    digital_io_offset: int = 0    # Digital Discovery adds 24 to DIO channel indices
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

    def to_dict(self) -> dict:
        return {
            "devid": self.devid,
            "name": self.name,
            "analog_in_ch": self.analog_in_ch,
            "analog_out_ch": self.analog_out_ch,
            "analog_io_ch": self.analog_io_ch,
            "digital_in_ch": self.digital_in_ch,
            "digital_out_ch": self.digital_out_ch,
            "digital_io_ch": self.digital_io_ch,
            "digital_io_offset": self.digital_io_offset,
            "has_impedance": self.has_impedance,
            "has_protocols": self.has_protocols,
            "has_dmm": self.has_dmm,
            "has_power_supply": self.has_power_supply,
            "max_scope_rate_hz": self.max_scope_rate_hz,
            "max_scope_buffer": self.max_scope_buffer,
            "max_logic_rate_hz": self.max_logic_rate_hz,
            "max_logic_buffer": self.max_logic_buffer,
            "supply_channels": [s.to_dict() for s in self.supply_channels],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Device enumeration info (populated at runtime by dwf_adapter)
# ---------------------------------------------------------------------------

@dataclass
class DeviceEnumInfo:
    idx: int          # enumeration index (passed to FDwfDeviceOpen)
    devid: int        # device type constant (devidDiscovery2 = 3, etc.)
    devver: int       # hardware revision
    name: str         # from FDwfEnumDeviceName
    sn: str           # serial number from FDwfEnumSN
    is_open: bool     # already opened by another process


# ---------------------------------------------------------------------------
# Reusable supply channel helpers
# ---------------------------------------------------------------------------

def _ad2_supplies() -> list[SupplyChannelDef]:
    """V+/V- adjustable supplies for AD1, AD2, AD3, ADP2230, ADS Max."""
    return [
        SupplyChannelDef(
            name="V+", channel_idx=0,
            node_enable=0, node_voltage=1, node_current=None,
            node_v_mon=2, node_i_mon=3,
            min_v=0.0, max_v=5.0,
        ),
        SupplyChannelDef(
            name="V-", channel_idx=1,
            node_enable=0, node_voltage=1, node_current=None,
            node_v_mon=2, node_i_mon=3,
            min_v=-5.0, max_v=0.0, is_negative=True,
        ),
        SupplyChannelDef(
            name="USB", channel_idx=2,
            node_enable=None, node_voltage=None, node_current=None,
            node_v_mon=0, node_i_mon=1,
            min_v=4.5, max_v=5.5, read_only=True,
        ),
    ]


def _vio_supply(max_v: float = 3.3) -> list[SupplyChannelDef]:
    """Single adjustable VIO supply (Digital Discovery, ADP3000 series)."""
    return [
        SupplyChannelDef(
            name="VIO", channel_idx=0,
            node_enable=0, node_voltage=1, node_current=None,
            node_v_mon=2, node_i_mon=None,
            min_v=1.2, max_v=max_v,
        ),
    ]


# ---------------------------------------------------------------------------
# Static capability table — keyed by DEVID integer
# ---------------------------------------------------------------------------

DEVICE_CAPABILITIES: dict[int, CapabilityRecord] = {

    # DEVID 1 — Electronics Explorer
    1: CapabilityRecord(
        devid=1, name="Electronics Explorer",
        analog_in_ch=8, analog_out_ch=4,
        analog_io_ch=4,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=40_000_000, max_scope_buffer=16384,
        max_logic_rate_hz=100_000_000, max_logic_buffer=16384,
        supply_channels=[
            SupplyChannelDef(
                name="V+", channel_idx=0,
                node_enable=0, node_voltage=1, node_current=None,
                node_v_mon=2, node_i_mon=None,
                min_v=0.0, max_v=9.0,
            ),
            SupplyChannelDef(
                name="V-", channel_idx=1,
                node_enable=0, node_voltage=1, node_current=None,
                node_v_mon=2, node_i_mon=None,
                min_v=-9.0, max_v=0.0, is_negative=True,
            ),
        ],
        notes="Channels 3/4 of AnalogOut are power supply outputs — blocked for waveform use.",
    ),

    # DEVID 2 — Analog Discovery 1 (fixed ±5 V)
    2: CapabilityRecord(
        devid=2, name="Analog Discovery",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=100_000_000, max_scope_buffer=8192,
        max_logic_rate_hz=100_000_000, max_logic_buffer=16384,
        supply_channels=_ad2_supplies(),
        notes="Fixed ±5 V supply (not adjustable on AD1).",
    ),

    # DEVID 3 — Analog Discovery 2 (adjustable ±5 V)
    3: CapabilityRecord(
        devid=3, name="Analog Discovery 2",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=100_000_000, max_scope_buffer=8192,
        max_logic_rate_hz=100_000_000, max_logic_buffer=16384,
        supply_channels=_ad2_supplies(),
    ),

    # DEVID 4 — Digital Discovery (no analog)
    4: CapabilityRecord(
        devid=4, name="Digital Discovery",
        analog_in_ch=0, analog_out_ch=0,
        analog_io_ch=1,
        digital_in_ch=24, digital_out_ch=16, digital_io_ch=16,
        digital_io_offset=24,  # DIO indices start at 24 in FDwfDigitalOut API
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=0, max_scope_buffer=0,
        max_logic_rate_hz=800_000_000, max_logic_buffer=1_073_741_824,
        supply_channels=_vio_supply(max_v=3.3),
        notes="No AnalogIn or AnalogOut. DIO channels are offset by 24 in DigitalOut API. "
              "Supports CAN in addition to UART/SPI/I2C. DwfDigitalOutTypePlay supported.",
    ),

    # DEVID 6 — Analog Discovery Pro 3000 Series (ADP3450/3250)
    6: CapabilityRecord(
        devid=6, name="Analog Discovery Pro 3450",
        analog_in_ch=4, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=131072,
        max_logic_rate_hz=800_000_000, max_logic_buffer=131072,
        supply_channels=_vio_supply(max_v=3.3),
        notes="ADP3450 has 4 AI channels; ADP3250 has 2. "
              "VIO adjustable. Oversampling mode (acqmodeOvers) supported.",
    ),

    # DEVID 8 — Analog Discovery Pro 5250
    8: CapabilityRecord(
        devid=8, name="Analog Discovery Pro 5250",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=3,
        digital_in_ch=8, digital_out_ch=8, digital_io_ch=8,
        has_impedance=False, has_protocols=True, has_dmm=True, has_power_supply=True,
        max_scope_rate_hz=500_000_000, max_scope_buffer=131072,
        max_logic_rate_hz=100_000_000, max_logic_buffer=131072,
        supply_channels=[
            SupplyChannelDef(
                name="V+25", channel_idx=0,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=0.0, max_v=25.0,
            ),
            SupplyChannelDef(
                name="V-25", channel_idx=1,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=-25.0, max_v=0.0, is_negative=True,
            ),
            SupplyChannelDef(
                name="V+6", channel_idx=2,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=0.0, max_v=6.0,
            ),
        ],
        notes="ADP5250: ±25V + 6V programmable supplies. I2C/SPI only (no UART, no CAN). "
              "Does not support trigger pulse/transition/window or record acquisition mode. "
              "ADP5250 has fixed protocol pins — check SDK §14.6 for pinout.",
    ),

    # DEVID 9 — Discovery Power Supply 3340
    9: CapabilityRecord(
        devid=9, name="Discovery Power Supply 3340",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=3,
        digital_in_ch=0, digital_out_ch=0, digital_io_ch=0,
        has_impedance=False, has_protocols=False, has_power_supply=True,
        max_scope_rate_hz=10_000_000, max_scope_buffer=4096,
        max_logic_rate_hz=0, max_logic_buffer=0,
        supply_channels=[
            SupplyChannelDef(
                name="CH1", channel_idx=0,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=0.0, max_v=30.0,
            ),
            SupplyChannelDef(
                name="CH2", channel_idx=1,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=0.0, max_v=30.0,
            ),
            SupplyChannelDef(
                name="CH3", channel_idx=2,
                node_enable=0, node_voltage=1, node_current=2,
                node_v_mon=3, node_i_mon=4,
                min_v=0.0, max_v=6.0,
            ),
        ],
        notes="DPS3340: 3-channel programmable power supply. No logic analyzer, no protocols.",
    ),

    # DEVID 10 — Analog Discovery 3
    10: CapabilityRecord(
        devid=10, name="Analog Discovery 3",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=32768,
        max_logic_rate_hz=100_000_000, max_logic_buffer=32768,
        supply_channels=_ad2_supplies(),
        notes="Supports SWD protocol (FDwfDigitalSwd*) in addition to UART/SPI/I2C/CAN.",
    ),

    # DEVID 14 — Analog Discovery Pro 2230
    14: CapabilityRecord(
        devid=14, name="Analog Discovery Pro 2230",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=32768,
        max_logic_rate_hz=100_000_000, max_logic_buffer=32768,
        supply_channels=_ad2_supplies(),
    ),

    # DEVID 15 — Analog Discovery Studio Max
    15: CapabilityRecord(
        devid=15, name="Analog Discovery Studio Max",
        analog_in_ch=2, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=True, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=32768,
        max_logic_rate_hz=100_000_000, max_logic_buffer=32768,
        supply_channels=_ad2_supplies(),
        notes="ADS Max: dedicated impedance analyzer connector (FDwfAnalogImpedanceEnableSet). "
              "Impedance mode switches routing from AWG+Scope to IA connector.",
    ),

    # DEVID 16 — Analog Discovery Pro 2440
    16: CapabilityRecord(
        devid=16, name="Analog Discovery Pro 2440",
        analog_in_ch=4, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=131072,
        max_logic_rate_hz=100_000_000, max_logic_buffer=131072,
        supply_channels=_ad2_supplies(),
    ),

    # DEVID 17 — Analog Discovery Pro 2450
    17: CapabilityRecord(
        devid=17, name="Analog Discovery Pro 2450",
        analog_in_ch=4, analog_out_ch=2,
        analog_io_ch=2,
        digital_in_ch=16, digital_out_ch=16, digital_io_ch=16,
        has_impedance=False, has_protocols=True, has_power_supply=True,
        max_scope_rate_hz=125_000_000, max_scope_buffer=131072,
        max_logic_rate_hz=100_000_000, max_logic_buffer=131072,
        supply_channels=_ad2_supplies(),
    ),
}

# Fallback for unknown DEVID — assume minimal scope/wavegen to avoid hard failures.
UNKNOWN_DEVICE_CAP = CapabilityRecord(
    devid=-1,
    name="Unknown Digilent Device",
    analog_in_ch=2,
    analog_out_ch=2,
    has_protocols=True,
    has_power_supply=False,
    notes="Unrecognised DEVID — capability information may be inaccurate. "
          "Runtime FDwfEnumConfigInfo overrides will be applied if available.",
)


def get_capability(devid: int) -> CapabilityRecord:
    """Return a *deep copy* of the CapabilityRecord for *devid*, falling back to UNKNOWN_DEVICE_CAP.

    A deep copy is returned so callers can safely apply runtime overrides
    (via _apply_config_overrides) without mutating the static table.
    """
    base = DEVICE_CAPABILITIES.get(devid, UNKNOWN_DEVICE_CAP)
    return copy.deepcopy(base)
