"""Unit tests for protocol_service.py."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_dwf_stub = types.ModuleType("digilent.dwf_adapter")
_dwf_stub.HDWF_NONE = MagicMock()
_dwf_stub.HDWF_NONE.value = -1
_dwf_stub.IMP_MEASUREMENT_MAP = {}
sys.modules.setdefault("digilent.dwf_adapter", _dwf_stub)

from digilent.capability_registry import CapabilityRecord
from digilent.config import DigilentConfig
from digilent.errors import DigilentNotAvailable
from digilent.models import (
    CanConfigureRequest,
    I2cConfigureRequest,
    SpiConfigureRequest,
    UartConfigureRequest,
)
from digilent.protocol_service import ProtocolService


def _make_service(has_protocols: bool = True) -> ProtocolService:
    cap = CapabilityRecord(devid=3, name="Test Device", has_protocols=has_protocols)
    manager = MagicMock()
    manager.capability = cap
    return ProtocolService(manager, DigilentConfig())


class TestProtocolServiceCapabilityGate(unittest.TestCase):
    def test_uart_configure_raises_not_available_without_protocols(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.uart_configure(UartConfigureRequest())

    def test_spi_configure_raises_not_available_without_protocols(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.spi_configure(SpiConfigureRequest())

    def test_i2c_configure_raises_not_available_without_protocols(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.i2c_configure(I2cConfigureRequest())

    def test_can_configure_raises_not_available_without_protocols(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.can_configure(CanConfigureRequest())


if __name__ == "__main__":
    unittest.main()
