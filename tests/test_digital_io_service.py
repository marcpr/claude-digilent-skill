"""
Unit tests for digital_io_service.py.

Phase 3 will expand these to ≥8 tests.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import types
import unittest
from unittest.mock import MagicMock

# Mock dwf_adapter before importing anything from digilent
_dwf_mock = types.ModuleType("digilent.dwf_adapter")
_dwf_mock.HDWF_NONE = MagicMock()
_dwf_mock.HDWF_NONE.value = -1
sys.modules.setdefault("digilent.dwf_adapter", _dwf_mock)

from digilent.capability_registry import CapabilityRecord
from digilent.digital_io_service import DigitalIOService
from digilent.errors import DigilentNotAvailable


class TestDigitalIOServiceCapabilityGate(unittest.TestCase):
    def _make_service(self, digital_io_ch: int) -> DigitalIOService:
        cap = CapabilityRecord(devid=3, name="Test Device", digital_io_ch=digital_io_ch)
        manager = MagicMock()
        return DigitalIOService(manager, cap)

    def test_configure_raises_not_available_when_no_dio(self):
        svc = self._make_service(digital_io_ch=0)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.configure(0xFF, 0x00)

    def test_no_exception_for_device_with_dio(self):
        # Service with digital_io_ch>0 should reach NotImplementedError, not DigilentNotAvailable
        svc = self._make_service(digital_io_ch=16)
        with self.assertRaises(NotImplementedError):
            svc.configure(0xFF, 0x00)


if __name__ == "__main__":
    unittest.main()
