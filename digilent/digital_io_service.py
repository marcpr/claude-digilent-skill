"""
Digital I/O service (stub).

Implements static bit-banging via FDwfDigitalIO* SDK calls.
Full implementation in Phase 3.
"""

from __future__ import annotations

from .capability_registry import CapabilityRecord
from .device_manager import DeviceManager
from .errors import DigilentNotAvailable


class DigitalIOService:
    def __init__(self, manager: DeviceManager, capability: CapabilityRecord) -> None:
        self._manager = manager
        self._cap = capability

    def _require_digital_io(self) -> None:
        if self._cap.digital_io_ch == 0:
            raise DigilentNotAvailable(
                "Digital I/O is not available on this device",
                {"device": self._cap.name},
            )

    def configure(self, output_enable_mask: int, output_value: int) -> dict:
        raise NotImplementedError("DigitalIOService.configure — implemented in Phase 3")

    def read(self) -> dict:
        raise NotImplementedError("DigitalIOService.read — implemented in Phase 3")

    def write(self, value: int, mask: int) -> dict:
        raise NotImplementedError("DigitalIOService.write — implemented in Phase 3")
