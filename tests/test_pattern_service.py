"""Unit tests for pattern_service.py."""

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
from digilent.models import PatternSetRequest, PatternStopRequest
from digilent.pattern_service import PatternService


def _make_service(digital_out_ch: int = 16) -> PatternService:
    cap = CapabilityRecord(devid=3, name="Test Device", digital_out_ch=digital_out_ch)
    manager = MagicMock()
    manager.capability = cap
    return PatternService(manager, DigilentConfig())


class TestPatternServiceCapabilityGate(unittest.TestCase):
    def test_set_raises_not_available_when_no_pattern(self):
        svc = _make_service(digital_out_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.set(PatternSetRequest())

    def test_stop_raises_not_available_when_no_pattern(self):
        svc = _make_service(digital_out_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.stop(PatternStopRequest())


if __name__ == "__main__":
    unittest.main()
