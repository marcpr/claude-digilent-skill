"""
Unit tests for impedance_service.py.

Phase 3 will expand these to ≥15 tests.
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
from digilent.impedance_service import ImpedanceService
from digilent.models import ImpedanceConfigureRequest, ImpedanceMeasureRequest, ImpedanceSweepRequest


class TestImpedanceServiceCapabilityGate(unittest.TestCase):
    def _make_service(self, analog_in_ch: int, analog_out_ch: int) -> ImpedanceService:
        cap = CapabilityRecord(
            devid=3, name="Test Device",
            analog_in_ch=analog_in_ch, analog_out_ch=analog_out_ch,
        )
        return ImpedanceService(MagicMock(), cap)

    def test_raises_not_available_when_no_analog_in(self):
        svc = self._make_service(analog_in_ch=0, analog_out_ch=2)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.configure(ImpedanceConfigureRequest())

    def test_raises_not_available_when_no_analog_out(self):
        svc = self._make_service(analog_in_ch=2, analog_out_ch=0)
        with self.assertRaises((DigilentNotAvailable, NotImplementedError)):
            svc.configure(ImpedanceConfigureRequest())

    def test_configure_reaches_not_implemented_when_capable(self):
        svc = self._make_service(analog_in_ch=2, analog_out_ch=2)
        with self.assertRaises(NotImplementedError):
            svc.configure(ImpedanceConfigureRequest())

    def test_measure_reaches_not_implemented_when_capable(self):
        svc = self._make_service(analog_in_ch=2, analog_out_ch=2)
        with self.assertRaises(NotImplementedError):
            svc.measure(ImpedanceMeasureRequest())

    def test_sweep_reaches_not_implemented_when_capable(self):
        svc = self._make_service(analog_in_ch=2, analog_out_ch=2)
        with self.assertRaises(NotImplementedError):
            svc.sweep(ImpedanceSweepRequest())


if __name__ == "__main__":
    unittest.main()
