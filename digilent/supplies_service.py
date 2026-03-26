"""Power supplies and static I/O service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .capability_registry import SupplyChannelDef
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import (
    DigilentConfigInvalidError,
    DigilentNotAvailable,
    DigilentNotEnabledError,
    DigilentRangeViolationError,
)
from .models import StaticIoRequest, SuppliesMasterRequest, SuppliesRequest, SuppliesSetRequest

_log = logging.getLogger("digilent.supplies")


class SuppliesService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _supply_channels(self) -> list[SupplyChannelDef]:
        cap = self._manager.capability
        return cap.supply_channels if cap is not None else []

    def _find_channel(self, channel_name: str) -> SupplyChannelDef:
        channels = self._supply_channels()
        supply = next((s for s in channels if s.name == channel_name), None)
        if supply is None:
            available = [s.name for s in channels]
            raise DigilentConfigInvalidError(
                f"Unknown supply channel '{channel_name}'. "
                f"Available: {available}"
            )
        return supply

    def _require_supplies_enabled(self) -> None:
        if not self._cfg.allow_supplies:
            raise DigilentNotEnabledError(
                "Power supply control is disabled. "
                "Set allow_supplies=true in digilent.json to enable."
            )

    # ------------------------------------------------------------------
    # GET /supplies/info
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return the list of supply channels for the connected device."""
        cap = self._manager.capability
        if cap is not None and not cap.has_power_supply:
            raise DigilentNotAvailable(
                "This device has no configurable power supply",
                {"device": cap.name},
            )
        channels = self._supply_channels()
        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "device": self._manager.device_info.name or "unknown",
            "supply_channels": [s.to_dict() for s in channels],
        }

    # ------------------------------------------------------------------
    # GET /supplies/status  (monitor readings)
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Read all supply monitor nodes."""
        channels = self._supply_channels()
        readings: dict[str, dict] = {}

        with self._manager.session() as hdwf:
            dwf.supplies_io_status(hdwf)   # update all monitor readings
            for supply in channels:
                ch_data: dict = {}
                if supply.node_v_mon is not None:
                    try:
                        v = dwf.supplies_channel_node_get(hdwf, supply.channel_idx, supply.node_v_mon)
                        ch_data["voltage_v"] = round(v, 4)
                    except Exception:
                        ch_data["voltage_v"] = None
                if supply.node_i_mon is not None:
                    try:
                        i = dwf.supplies_channel_node_get(hdwf, supply.channel_idx, supply.node_i_mon)
                        ch_data["current_a"] = round(i, 6)
                    except Exception:
                        ch_data["current_a"] = None
                readings[supply.name] = ch_data

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "readings": readings,
        }

    # ------------------------------------------------------------------
    # POST /supplies/set
    # ------------------------------------------------------------------

    def set(self, req: SuppliesSetRequest) -> dict:
        """Enable/disable and configure voltage/current on a named supply channel."""
        self._require_supplies_enabled()

        supply = self._find_channel(req.channel_name)

        if supply.read_only:
            raise DigilentConfigInvalidError(
                f"Supply channel '{req.channel_name}' is a monitor — it cannot be written"
            )

        if req.enable and not req.confirm_unsafe:
            raise DigilentConfigInvalidError(
                "confirm_unsafe=true is required to activate a supply channel"
            )

        if req.voltage_v is not None:
            if not req.confirm_unsafe:
                raise DigilentConfigInvalidError(
                    "confirm_unsafe=true is required for any supply voltage change"
                )
            v = req.voltage_v
            if v < supply.min_v or v > supply.max_v:
                raise DigilentRangeViolationError(
                    f"voltage_v {v} out of range [{supply.min_v}, {supply.max_v}] "
                    f"for channel '{supply.name}'"
                )

        _log.warning(
            "Supply set: channel=%s enable=%s voltage_v=%s",
            req.channel_name, req.enable, req.voltage_v,
        )

        with self._manager.session() as hdwf:
            if supply.node_enable is not None:
                dwf.supplies_channel_node_set(
                    hdwf, supply.channel_idx, supply.node_enable,
                    1.0 if req.enable else 0.0,
                )
            if req.voltage_v is not None and supply.node_voltage is not None:
                dwf.supplies_channel_node_set(
                    hdwf, supply.channel_idx, supply.node_voltage, req.voltage_v
                )
            if req.current_limit_a is not None and supply.node_current is not None:
                dwf.supplies_channel_node_set(
                    hdwf, supply.channel_idx, supply.node_current, req.current_limit_a
                )

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel": req.channel_name,
            "enabled": req.enable,
            "voltage_v": req.voltage_v,
        }

    # ------------------------------------------------------------------
    # POST /supplies/master
    # ------------------------------------------------------------------

    def master(self, req: SuppliesMasterRequest) -> dict:
        """Set the AnalogIO master enable."""
        self._require_supplies_enabled()

        if req.enable and not req.confirm_unsafe:
            raise DigilentConfigInvalidError(
                "confirm_unsafe=true is required to enable the supply master"
            )

        _log.warning("Supply master enable=%s", req.enable)

        with self._manager.session() as hdwf:
            dwf.supplies_master_enable(hdwf, req.enable)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "master_enabled": req.enable,
        }

    # ------------------------------------------------------------------
    # Legacy set() overload — accepts old SuppliesRequest for backward compat
    # ------------------------------------------------------------------

    def set_legacy(self, req: SuppliesRequest) -> dict:
        """Legacy AD2-only supply set (vplus/vminus). Kept for backward compatibility."""
        self._require_supplies_enabled()
        limits = self._cfg.safe_limits

        if req.enable_vplus and not req.confirm_unsafe:
            raise DigilentConfigInvalidError(
                "Supply activation requires confirm_unsafe=true in the request"
            )
        if req.enable_vminus and not req.confirm_unsafe:
            raise DigilentConfigInvalidError(
                "Supply activation requires confirm_unsafe=true in the request"
            )
        if req.vplus_v > limits.max_supply_plus_v:
            raise DigilentRangeViolationError(
                f"vplus_v {req.vplus_v} exceeds safe limit {limits.max_supply_plus_v}"
            )
        if req.vminus_v < limits.min_supply_minus_v:
            raise DigilentRangeViolationError(
                f"vminus_v {req.vminus_v} below safe limit {limits.min_supply_minus_v}"
            )
        if req.vplus_v < 0:
            raise DigilentConfigInvalidError("vplus_v must be >= 0")
        if req.vminus_v > 0:
            raise DigilentConfigInvalidError("vminus_v must be <= 0")

        warnings = ["Power supply activated — verify wiring before enabling output"]

        with self._manager.session() as hdwf:
            dwf.supplies_apply(
                hdwf=hdwf,
                vplus_v=req.vplus_v,
                vminus_v=req.vminus_v,
                enable_vplus=req.enable_vplus,
                enable_vminus=req.enable_vminus,
            )

        active = req.enable_vplus or req.enable_vminus
        response: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": "Supplies configured",
            "vplus_active": req.enable_vplus,
            "vminus_active": req.enable_vminus,
        }
        if active:
            response["warnings"] = warnings
        return response


class StaticIoService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    def set(self, req: StaticIoRequest) -> dict:
        """Configure static I/O pins."""
        self._validate(req)

        pin_tuples = [(p.index, p.mode, p.value) for p in req.pins]

        with self._manager.session() as hdwf:
            input_states = dwf.static_io_apply(hdwf=hdwf, pins=pin_tuples)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "input_states": input_states,
        }

    def _validate(self, req: StaticIoRequest) -> None:
        if not req.pins:
            raise DigilentConfigInvalidError("pins list must not be empty")
        for pin in req.pins:
            if not (0 <= pin.index <= 15):
                raise DigilentConfigInvalidError(f"Pin index {pin.index} out of range 0-15")
            if pin.mode not in ("input", "output"):
                raise DigilentConfigInvalidError(f"Invalid mode '{pin.mode}' for pin {pin.index}")
            if pin.mode == "output" and pin.value not in (0, 1):
                raise DigilentConfigInvalidError(f"Pin {pin.index} value must be 0 or 1")
