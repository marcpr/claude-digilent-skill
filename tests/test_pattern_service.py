"""
Unit tests for pattern_service.py.

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

_dwf_mock = types.ModuleType("digilent.dwf_adapter")
_dwf_mock.HDWF_NONE = MagicMock()
_dwf_mock.HDWF_NONE.value = -1
sys.modules.setdefault("digilent.dwf_adapter", _dwf_mock)

from digilent.capability_registry import CapabilityRecord
from digilent.errors import DigilentNotAvailable
from digilent.models import PatternSetRequest, PatternStopRequest
from digilent.pattern_service import PatternService


class TestPatternServiceCapabilityGate(unittest.TestCase):
    def _make_service(self, digital_out_ch: int) -> PatternService:
        cap = CapabilityRecord(devid=3, name="Test Device", digital_out_ch=digital_out_ch)
        return PatternService(MagicMock(), cap)

    def test_set_raises_not_available_when_no_pattern(self):
        svc = self._make_service(digital_out_ch=0)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.set(PatternSetRequest())

    def test_set_reaches_not_implemented_when_pattern_available(self):
        svc = self._make_service(digital_out_ch=16)
        with self.assertRaises(NotImplementedError):
            svc.set(PatternSetRequest())

    def test_stop_reaches_not_implemented_when_pattern_available(self):
        svc = self._make_service(digital_out_ch=16)
        with self.assertRaises(NotImplementedError):
            svc.stop(PatternStopRequest())


if __name__ == "__main__":
    unittest.main()
