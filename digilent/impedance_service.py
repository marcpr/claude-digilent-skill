"""Analog Impedance Analyzer service — FDwfAnalogImpedance* SDK calls."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError, DigilentNotAvailable, DigilentRangeViolationError
from .models import (
    ImpedanceCompensationRequest,
    ImpedanceConfigureRequest,
    ImpedanceMeasureRequest,
    ImpedanceSweepRequest,
)

_VALID_MEASUREMENTS = set(dwf.IMP_MEASUREMENT_MAP.keys())


class ImpedanceService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_impedance(self) -> None:
        cap = self._manager.capability
        if cap is not None and (cap.analog_in_ch == 0 or cap.analog_out_ch == 0):
            raise DigilentNotAvailable(
                "Impedance analyzer is not available on this device",
                {"device": cap.name},
            )

    def _check_amplitude(self, amplitude_v: float) -> None:
        limit = self._cfg.safe_limits.max_impedance_sweep_amplitude_v
        if amplitude_v > limit:
            raise DigilentRangeViolationError(
                f"amplitude_v {amplitude_v} exceeds safe limit {limit}"
            )

    def _check_measurements(self, names: list[str]) -> None:
        invalid = [m for m in names if m not in _VALID_MEASUREMENTS]
        if invalid:
            raise DigilentConfigInvalidError(
                f"Unknown measurement(s): {invalid}. "
                f"Valid: {sorted(_VALID_MEASUREMENTS)}"
            )

    # ------------------------------------------------------------------
    # POST /impedance/configure
    # ------------------------------------------------------------------

    def configure(self, req: ImpedanceConfigureRequest) -> dict:
        self._require_impedance()
        self._check_amplitude(req.amplitude_v)

        with self._manager.session() as hdwf:
            dwf.impedance_configure(
                hdwf,
                req.frequency_hz, req.amplitude_v, req.offset_v,
                req.probe_resistance_ohm, req.probe_capacitance_f,
                req.min_periods,
            )

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "frequency_hz": req.frequency_hz,
            "amplitude_v": req.amplitude_v,
            "probe_resistance_ohm": req.probe_resistance_ohm,
        }

    # ------------------------------------------------------------------
    # POST /impedance/measure
    # ------------------------------------------------------------------

    def measure(self, req: ImpedanceMeasureRequest) -> dict:
        self._require_impedance()
        self._check_measurements(req.measurements)

        with self._manager.session() as hdwf:
            values = dwf.impedance_measure(hdwf, req.measurements)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "measurements": values,
        }

    # ------------------------------------------------------------------
    # POST /impedance/sweep
    # ------------------------------------------------------------------

    def sweep(self, req: ImpedanceSweepRequest) -> dict:
        self._require_impedance()
        self._check_amplitude(req.amplitude_v)
        self._check_measurements(req.measurements)
        if req.steps < 2:
            raise DigilentConfigInvalidError("steps must be >= 2")
        if req.f_start_hz <= 0 or req.f_stop_hz <= req.f_start_hz:
            raise DigilentConfigInvalidError("f_stop_hz must be > f_start_hz > 0")

        log_start = math.log10(req.f_start_hz)
        log_stop = math.log10(req.f_stop_hz)
        frequencies = [
            10 ** (log_start + i * (log_stop - log_start) / (req.steps - 1))
            for i in range(req.steps)
        ]

        sweep_data: dict[str, list[float]] = {m: [] for m in req.measurements}

        with self._manager.session() as hdwf:
            dwf.impedance_configure(
                hdwf,
                frequencies[0], req.amplitude_v, req.offset_v,
                req.probe_resistance_ohm, req.probe_capacitance_f,
                req.min_periods,
            )
            for freq in frequencies:
                dwf.impedance_set_frequency(hdwf, freq)
                values = dwf.impedance_measure(hdwf, req.measurements)
                for m in req.measurements:
                    sweep_data[m].append(values.get(m, 0.0))
            dwf.impedance_stop(hdwf)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "steps": req.steps,
            "frequencies": [round(f, 3) for f in frequencies],
            "measurements": {m: [round(v, 9) for v in vals] for m, vals in sweep_data.items()},
        }

    # ------------------------------------------------------------------
    # POST /impedance/compensation
    # ------------------------------------------------------------------

    def set_compensation(self, req: ImpedanceCompensationRequest) -> dict:
        self._require_impedance()

        with self._manager.session() as hdwf:
            dwf.impedance_set_compensation(
                hdwf, req.open_r, req.open_x, req.short_r, req.short_x,
            )

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
