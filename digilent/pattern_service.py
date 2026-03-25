"""
Pattern Generator service (stub).

Drives digital output channels via FDwfDigitalOut* SDK calls.
Full implementation in Phase 3.
"""

from __future__ import annotations

from .capability_registry import CapabilityRecord
from .device_manager import DeviceManager
from .errors import DigilentNotAvailable
from .models import PatternSetRequest, PatternStopRequest


class PatternService:
    def __init__(self, manager: DeviceManager, capability: CapabilityRecord) -> None:
        self._manager = manager
        self._cap = capability

    def _require_pattern(self) -> None:
        if self._cap.digital_out_ch == 0:
            raise DigilentNotAvailable(
                "Pattern generator is not available on this device",
                {"device": self._cap.name},
            )

    def set(self, req: PatternSetRequest) -> dict:
        raise NotImplementedError("PatternService.set — implemented in Phase 3")

    def stop(self, req: PatternStopRequest) -> dict:
        raise NotImplementedError("PatternService.stop — implemented in Phase 3")
