"""Unit tests for impedance_service.py."""

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
_dwf_stub.IMP_MEASUREMENT_MAP = {
    "Impedance": 0, "ImpedancePhase": 1, "Resistance": 2, "Reactance": 3,
    "Admittance": 4, "AdmittancePhase": 5, "Conductance": 6, "Susceptance": 7,
    "SeriesCapacitance": 8, "ParallelCapacitance": 9, "SeriesInductance": 10,
    "ParallelInductance": 11, "Dissipation": 12, "Quality": 13,
}
sys.modules.setdefault("digilent.dwf_adapter", _dwf_stub)

from digilent.capability_registry import CapabilityRecord
from digilent.config import DigilentConfig
from digilent.errors import DigilentNotAvailable
from digilent.impedance_service import ImpedanceService
from digilent.models import ImpedanceConfigureRequest, ImpedanceMeasureRequest, ImpedanceSweepRequest


def _make_service(analog_in_ch: int = 2, analog_out_ch: int = 2) -> ImpedanceService:
    cap = CapabilityRecord(
        devid=3, name="Test Device",
        analog_in_ch=analog_in_ch, analog_out_ch=analog_out_ch,
    )
    manager = MagicMock()
    manager.capability = cap
    return ImpedanceService(manager, DigilentConfig())


class TestImpedanceServiceCapabilityGate(unittest.TestCase):
    def test_raises_not_available_when_no_analog_in(self):
        svc = _make_service(analog_in_ch=0, analog_out_ch=2)
        with self.assertRaises(DigilentNotAvailable):
            svc.configure(ImpedanceConfigureRequest())

    def test_raises_not_available_when_no_analog_out(self):
        svc = _make_service(analog_in_ch=2, analog_out_ch=0)
        with self.assertRaises(DigilentNotAvailable):
            svc.configure(ImpedanceConfigureRequest())

    def test_measure_raises_not_available_when_no_analog_in(self):
        svc = _make_service(analog_in_ch=0, analog_out_ch=2)
        with self.assertRaises(DigilentNotAvailable):
            svc.measure(ImpedanceMeasureRequest())

    def test_sweep_raises_not_available_when_no_analog_in(self):
        svc = _make_service(analog_in_ch=0, analog_out_ch=2)
        with self.assertRaises(DigilentNotAvailable):
            svc.sweep(ImpedanceSweepRequest())


if __name__ == "__main__":
    unittest.main()
