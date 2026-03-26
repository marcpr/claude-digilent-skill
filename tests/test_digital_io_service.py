"""Unit tests for digital_io_service.py."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Minimal mock — setdefault won't overwrite the main mock if loaded first
_dwf_stub = types.ModuleType("digilent.dwf_adapter")
_dwf_stub.HDWF_NONE = MagicMock()
_dwf_stub.HDWF_NONE.value = -1
_dwf_stub.IMP_MEASUREMENT_MAP = {}
sys.modules.setdefault("digilent.dwf_adapter", _dwf_stub)

from digilent.capability_registry import CapabilityRecord
from digilent.config import DigilentConfig
from digilent.digital_io_service import DigitalIOService
from digilent.errors import DigilentNotAvailable


def _make_service(digital_io_ch: int = 16, offset: int = 0) -> DigitalIOService:
    cap = CapabilityRecord(
        devid=3, name="Test Device",
        digital_io_ch=digital_io_ch,
        digital_io_offset=offset,
    )
    manager = MagicMock()
    manager.capability = cap
    return DigitalIOService(manager, DigilentConfig())


class TestDigitalIOServiceCapabilityGate(unittest.TestCase):
    def test_configure_raises_not_available_when_no_dio(self):
        svc = _make_service(digital_io_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.configure(MagicMock(output_enable_mask=0, output_value=0))

    def test_read_raises_not_available_when_no_dio(self):
        svc = _make_service(digital_io_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.read()

    def test_write_raises_not_available_when_no_dio(self):
        svc = _make_service(digital_io_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.write(MagicMock(value=0, mask=0))


if __name__ == "__main__":
    unittest.main()
