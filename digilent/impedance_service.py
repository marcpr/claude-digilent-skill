"""
Analog Impedance Analyzer service (stub).

Uses FDwfAnalogImpedance* SDK calls.
Full implementation in Phase 3.
"""

from __future__ import annotations

from .capability_registry import CapabilityRecord
from .device_manager import DeviceManager
from .errors import DigilentNotAvailable
from .models import (
    ImpedanceCompensationRequest,
    ImpedanceConfigureRequest,
    ImpedanceMeasureRequest,
    ImpedanceSweepRequest,
)


class ImpedanceService:
    def __init__(self, manager: DeviceManager, capability: CapabilityRecord) -> None:
        self._manager = manager
        self._cap = capability

    def _require_impedance(self) -> None:
        # Impedance requires both AnalogIn and AnalogOut (AWG drives + scope measures)
        if self._cap.analog_in_ch == 0 or self._cap.analog_out_ch == 0:
            raise DigilentNotAvailable(
                "Impedance analyzer is not available on this device",
                {"device": self._cap.name},
            )

    def configure(self, req: ImpedanceConfigureRequest) -> dict:
        raise NotImplementedError("ImpedanceService.configure — implemented in Phase 3")

    def measure(self, req: ImpedanceMeasureRequest) -> dict:
        raise NotImplementedError("ImpedanceService.measure — implemented in Phase 3")

    def sweep(self, req: ImpedanceSweepRequest) -> dict:
        raise NotImplementedError("ImpedanceService.sweep — implemented in Phase 3")

    def set_compensation(self, req: ImpedanceCompensationRequest) -> dict:
        raise NotImplementedError("ImpedanceService.set_compensation — implemented in Phase 3")
