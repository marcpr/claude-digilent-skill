"""Pattern Generator service — FDwfDigitalOut* SDK calls."""

from __future__ import annotations

from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError, DigilentNotAvailable
from .models import PatternSetRequest, PatternStopRequest

_VALID_TYPES = {"pulse", "custom", "random", "bfs"}
_VALID_IDLE = {"low", "high", "zstate", "initial"}


class PatternService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_pattern(self) -> None:
        cap = self._manager.capability
        if cap is not None and cap.digital_out_ch == 0:
            raise DigilentNotAvailable(
                "Pattern generator is not available on this device",
                {"device": cap.name},
            )

    def _validate(self, req: PatternSetRequest) -> None:
        if req.type not in _VALID_TYPES:
            raise DigilentConfigInvalidError(
                f"Invalid pattern type '{req.type}'. Must be one of {sorted(_VALID_TYPES)}"
            )
        if req.idle_state not in _VALID_IDLE:
            raise DigilentConfigInvalidError(
                f"Invalid idle_state '{req.idle_state}'. Must be one of {sorted(_VALID_IDLE)}"
            )
        if req.frequency_hz <= 0:
            raise DigilentConfigInvalidError("frequency_hz must be > 0")
        if not (0 <= req.duty_pct <= 100):
            raise DigilentConfigInvalidError("duty_pct must be in 0..100")
        if req.type in ("custom", "bfs") and not req.custom_data:
            raise DigilentConfigInvalidError("custom_data is required for type 'custom'/'bfs'")
        cap = self._manager.capability
        max_ch = cap.digital_out_ch if cap is not None else 16
        if req.channel < 0 or req.channel >= max_ch:
            raise DigilentConfigInvalidError(
                f"Channel {req.channel} out of range 0-{max_ch - 1}"
            )

    # ------------------------------------------------------------------
    # POST /pattern/set
    # ------------------------------------------------------------------

    def set(self, req: PatternSetRequest) -> dict:
        """Configure and start a pattern on a digital output channel."""
        self._require_pattern()
        self._validate(req)

        with self._manager.session() as hdwf:
            clock_hz = dwf.pattern_get_system_freq(hdwf)
            divider = max(1, int(clock_hz / req.frequency_hz))
            total = max(2, divider)
            high_count = max(1, int(total * req.duty_pct / 100.0))
            low_count = max(1, total - high_count)
            dwf.pattern_configure_channel(
                hdwf, req.channel, req.type,
                divider, low_count, high_count,
                req.idle_state, req.custom_data,
            )
            if req.run_s > 0:
                dwf.pattern_run_set(hdwf, req.run_s)
            if req.repeat > 0:
                dwf.pattern_repeat_set(hdwf, req.repeat)
            dwf.pattern_start(hdwf)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel": req.channel,
            "type": req.type,
            "frequency_hz": req.frequency_hz,
            "duty_pct": req.duty_pct,
        }

    # ------------------------------------------------------------------
    # POST /pattern/stop
    # ------------------------------------------------------------------

    def stop(self, req: PatternStopRequest) -> dict:
        """Stop pattern output on one channel or all channels."""
        self._require_pattern()
        cap = self._manager.capability
        max_ch = cap.digital_out_ch if cap is not None else 16

        with self._manager.session() as hdwf:
            if req.channel == "all":
                dwf.pattern_stop(hdwf)
            else:
                ch = int(req.channel)
                if ch < 0 or ch >= max_ch:
                    raise DigilentConfigInvalidError(
                        f"Channel {ch} out of range 0-{max_ch - 1}"
                    )
                dwf.pattern_channel_disable(hdwf, ch)
                dwf.pattern_stop(hdwf)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "stopped": req.channel,
        }
