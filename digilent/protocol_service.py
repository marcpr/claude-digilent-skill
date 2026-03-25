"""
Digital Protocol service (stub).

Supports UART, SPI, I2C, CAN via FDwfDigitalUart/Spi/I2c/Can* SDK calls.
Full implementation in Phase 3.
"""

from __future__ import annotations

from .capability_registry import CapabilityRecord
from .device_manager import DeviceManager
from .errors import DigilentNotAvailable
from .models import (
    CanConfigureRequest,
    CanReceiveRequest,
    CanSendRequest,
    I2cConfigureRequest,
    I2cReadRequest,
    I2cWriteReadRequest,
    I2cWriteRequest,
    SpiConfigureRequest,
    SpiTransferRequest,
    UartConfigureRequest,
    UartReceiveRequest,
    UartSendRequest,
)


class ProtocolService:
    def __init__(self, manager: DeviceManager, capability: CapabilityRecord) -> None:
        self._manager = manager
        self._cap = capability

    def _require_protocols(self) -> None:
        if not self._cap.has_protocols:
            raise DigilentNotAvailable(
                "Digital protocols are not available on this device",
                {"device": self._cap.name},
            )

    # ------------------------------------------------------------------
    # UART
    # ------------------------------------------------------------------

    def uart_configure(self, req: UartConfigureRequest) -> dict:
        raise NotImplementedError("ProtocolService.uart_configure — implemented in Phase 3")

    def uart_send(self, req: UartSendRequest) -> dict:
        raise NotImplementedError("ProtocolService.uart_send — implemented in Phase 3")

    def uart_receive(self, req: UartReceiveRequest) -> dict:
        raise NotImplementedError("ProtocolService.uart_receive — implemented in Phase 3")

    # ------------------------------------------------------------------
    # SPI
    # ------------------------------------------------------------------

    def spi_configure(self, req: SpiConfigureRequest) -> dict:
        raise NotImplementedError("ProtocolService.spi_configure — implemented in Phase 3")

    def spi_transfer(self, req: SpiTransferRequest) -> dict:
        raise NotImplementedError("ProtocolService.spi_transfer — implemented in Phase 3")

    # ------------------------------------------------------------------
    # I2C
    # ------------------------------------------------------------------

    def i2c_configure(self, req: I2cConfigureRequest) -> dict:
        raise NotImplementedError("ProtocolService.i2c_configure — implemented in Phase 3")

    def i2c_write(self, req: I2cWriteRequest) -> dict:
        raise NotImplementedError("ProtocolService.i2c_write — implemented in Phase 3")

    def i2c_read(self, req: I2cReadRequest) -> dict:
        raise NotImplementedError("ProtocolService.i2c_read — implemented in Phase 3")

    def i2c_write_read(self, req: I2cWriteReadRequest) -> dict:
        raise NotImplementedError("ProtocolService.i2c_write_read — implemented in Phase 3")

    # ------------------------------------------------------------------
    # CAN
    # ------------------------------------------------------------------

    def can_configure(self, req: CanConfigureRequest) -> dict:
        raise NotImplementedError("ProtocolService.can_configure — implemented in Phase 3")

    def can_send(self, req: CanSendRequest) -> dict:
        raise NotImplementedError("ProtocolService.can_send — implemented in Phase 3")

    def can_receive(self, req: CanReceiveRequest) -> dict:
        raise NotImplementedError("ProtocolService.can_receive — implemented in Phase 3")
