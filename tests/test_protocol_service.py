"""
Unit tests for protocol_service.py.

Phase 3 will expand these to ≥16 tests.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import types
import unittest
from unittest.mock import MagicMock

_dwf_mock = types.ModuleType("digilent.dwf_adapter")
_dwf_mock.HDWF_NONE = MagicMock()
_dwf_mock.HDWF_NONE.value = -1
sys.modules.setdefault("digilent.dwf_adapter", _dwf_mock)

from digilent.capability_registry import CapabilityRecord
from digilent.errors import DigilentNotAvailable
from digilent.models import (
    CanConfigureRequest,
    I2cConfigureRequest,
    SpiConfigureRequest,
    UartConfigureRequest,
)
from digilent.protocol_service import ProtocolService


class TestProtocolServiceCapabilityGate(unittest.TestCase):
    def _make_service(self, has_protocols: bool) -> ProtocolService:
        cap = CapabilityRecord(devid=3, name="Test Device", has_protocols=has_protocols)
        return ProtocolService(MagicMock(), cap)

    def test_uart_configure_raises_not_available_without_protocols(self):
        svc = self._make_service(has_protocols=False)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.uart_configure(UartConfigureRequest())

    def test_spi_configure_raises_not_available_without_protocols(self):
        svc = self._make_service(has_protocols=False)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.spi_configure(SpiConfigureRequest())

    def test_i2c_configure_raises_not_available_without_protocols(self):
        svc = self._make_service(has_protocols=False)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.i2c_configure(I2cConfigureRequest())

    def test_can_configure_raises_not_available_without_protocols(self):
        svc = self._make_service(has_protocols=False)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.can_configure(CanConfigureRequest())

    def test_uart_configure_reaches_not_implemented_when_protocols_available(self):
        svc = self._make_service(has_protocols=True)
        with self.assertRaises(NotImplementedError):
            svc.uart_configure(UartConfigureRequest())

    def test_spi_configure_reaches_not_implemented_when_protocols_available(self):
        svc = self._make_service(has_protocols=True)
        with self.assertRaises(NotImplementedError):
            svc.spi_configure(SpiConfigureRequest())

    def test_i2c_configure_reaches_not_implemented_when_protocols_available(self):
        svc = self._make_service(has_protocols=True)
        with self.assertRaises(NotImplementedError):
            svc.i2c_configure(I2cConfigureRequest())

    def test_can_configure_reaches_not_implemented_when_protocols_available(self):
        svc = self._make_service(has_protocols=True)
        with self.assertRaises(NotImplementedError):
            svc.can_configure(CanConfigureRequest())


if __name__ == "__main__":
    unittest.main()
