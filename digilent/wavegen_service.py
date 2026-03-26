"""Waveform generator service."""

from __future__ import annotations

from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError, DigilentNotAvailable, DigilentRangeViolationError
from .models import WavegenRequest

_VALID_WAVEFORMS = {"sine", "square", "triangle", "dc", "rampup", "rampdown", "noise", "custom"}

# Electronics Explorer devid — channels 3/4 are power outputs, not AWG
_EE_DEVID = 1
_EE_AWG_MAX_CHANNEL = 2


class WavegenService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    def set(self, req: WavegenRequest) -> dict:
        """Configure and optionally start the waveform generator."""
        self._validate(req)

        warnings = []
        if req.enable:
            warnings.append(
                "Wavegen active — ensure amplitude and offset are safe for connected DUT"
            )

        with self._manager.session() as hdwf:
            # Upload custom data before configuring waveform
            if req.waveform == "custom" and req.custom_data:
                dwf.wavegen_set_custom_data(hdwf, req.channel, req.custom_data)

            dwf.wavegen_apply(
                hdwf=hdwf,
                channel=req.channel,
                waveform=req.waveform,
                frequency_hz=req.frequency_hz,
                amplitude_v=req.amplitude_v,
                offset_v=req.offset_v,
                symmetry_percent=req.symmetry_percent,
                phase_deg=req.phase_deg,
                enable=req.enable,
            )

            # Apply modulation if requested
            if req.modulation:
                mod_type = req.modulation.get("type", "")
                if mod_type in ("am", "fm"):
                    dwf.wavegen_set_modulation(
                        hdwf=hdwf,
                        channel=req.channel,
                        mod_type=mod_type,
                        freq_hz=float(req.modulation.get("freq_hz", 10.0)),
                        depth=float(req.modulation.get("depth", 0.5)),
                    )

        response: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": f"Wavegen CH{req.channel} {'started' if req.enable else 'stopped'}",
        }
        if warnings:
            response["warnings"] = warnings
        return response

    def stop(self, channel: int = 1) -> dict:
        """Stop the waveform generator on the specified channel."""
        cap = self._manager.capability
        max_ch = cap.analog_out_ch if cap is not None else 2
        if channel < 1 or channel > max(max_ch, 2):
            raise DigilentConfigInvalidError(f"Invalid wavegen channel: {channel}")

        with self._manager.session() as hdwf:
            dwf.wavegen_stop(hdwf=hdwf, channel=channel)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": f"Wavegen CH{channel} stopped",
        }

    def _validate(self, req: WavegenRequest) -> None:
        cap = self._manager.capability
        limits = self._cfg.safe_limits

        # Capability gate
        if cap is not None and cap.analog_out_ch == 0:
            raise DigilentNotAvailable(
                "Waveform generator not available on this device",
                {"device": cap.name},
            )

        # Channel range validation
        max_ch = cap.analog_out_ch if cap is not None else 2
        if req.channel < 1 or req.channel > max_ch:
            raise DigilentConfigInvalidError(
                f"Invalid wavegen channel: {req.channel}. Device supports channels 1–{max_ch}"
            )

        # Block Electronics Explorer channels 3/4 (they are power supply outputs)
        if cap is not None and cap.devid == _EE_DEVID and req.channel > _EE_AWG_MAX_CHANNEL:
            raise DigilentConfigInvalidError(
                f"Electronics Explorer channel {req.channel} is a power supply output, "
                "not a waveform generator channel. Use channels 1–2 for AWG."
            )

        if req.waveform not in _VALID_WAVEFORMS:
            raise DigilentConfigInvalidError(
                f"Invalid waveform '{req.waveform}'. Must be one of {sorted(_VALID_WAVEFORMS)}"
            )

        if req.waveform == "custom" and not req.custom_data:
            raise DigilentConfigInvalidError(
                "waveform='custom' requires non-empty custom_data list"
            )

        if req.frequency_hz < 0:
            raise DigilentConfigInvalidError("frequency_hz must be >= 0")

        if abs(req.amplitude_v) > limits.max_wavegen_amplitude_v:
            raise DigilentRangeViolationError(
                f"amplitude_v {req.amplitude_v} exceeds safe limit {limits.max_wavegen_amplitude_v}"
            )

        if abs(req.offset_v) > limits.max_wavegen_offset_v:
            raise DigilentRangeViolationError(
                f"offset_v {req.offset_v} exceeds safe limit ±{limits.max_wavegen_offset_v}"
            )

        # Peak output voltage check
        peak_pos = req.amplitude_v + abs(req.offset_v)
        peak_neg = -req.amplitude_v - abs(req.offset_v)
        if peak_pos > limits.max_wavegen_amplitude_v or peak_neg < -limits.max_wavegen_amplitude_v:
            raise DigilentRangeViolationError(
                f"Wavegen peak voltage ({peak_pos:.2f}V / {peak_neg:.2f}V) "
                f"exceeds safe limits ±{limits.max_wavegen_amplitude_v}V"
            )

        if not (0 <= req.symmetry_percent <= 100):
            raise DigilentConfigInvalidError("symmetry_percent must be in 0..100")

        if not (0 <= req.phase_deg < 360):
            raise DigilentConfigInvalidError("phase_deg must be in 0..360")

        if req.modulation:
            mod_type = req.modulation.get("type", "")
            if mod_type not in ("am", "fm", ""):
                raise DigilentConfigInvalidError(
                    f"Invalid modulation type '{mod_type}'. Must be 'am' or 'fm'"
                )
