"""Unit tests for OrchestrationService — new Phase 5 actions."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_dwf_stub = types.ModuleType("digilent.dwf_adapter")
_dwf_stub.HDWF_NONE = MagicMock()
_dwf_stub.HDWF_NONE.value = -1
_dwf_stub.IMP_MEASUREMENT_MAP = {
    "Impedance": 0, "ImpedancePhase": 1, "Resistance": 2, "Reactance": 3,
}
sys.modules.setdefault("digilent.dwf_adapter", _dwf_stub)

from digilent.config import DigilentConfig
from digilent.errors import DigilentConfigInvalidError
from digilent.orchestration import OrchestrationService


def _make_orchestration():
    """Return OrchestrationService with all sub-services mocked."""
    manager = MagicMock()
    svc = OrchestrationService(manager, DigilentConfig())
    # Replace all sub-services with mocks
    svc._scope = MagicMock()
    svc._logic = MagicMock()
    svc._wavegen = MagicMock()
    svc._supplies = MagicMock()
    svc._protocol = MagicMock()
    return svc


class TestOrchestrationDispatch(unittest.TestCase):
    def test_unknown_action_raises_config_invalid(self):
        svc = _make_orchestration()
        with self.assertRaises(DigilentConfigInvalidError):
            svc.measure_basic("does_not_exist", {})

    def test_all_actions_in_dispatch(self):
        svc = _make_orchestration()
        # Patch each sub-handler to return a minimal result
        for attr in ("_measure_pwm", "_measure_voltage_level",
                     "_detect_logic_activity", "_bode_sweep",
                     "_uart_loopback_test", "_i2c_scan",
                     "_characterize_supply", "_digital_frequency"):
            setattr(svc, attr, lambda p: {"ok": True})
        actions = [
            "measure_pwm", "measure_voltage_level", "detect_logic_activity",
            "bode_sweep", "uart_loopback_test", "i2c_scan",
            "characterize_supply", "digital_frequency",
        ]
        for action in actions:
            result = svc.measure_basic(action, {})
            self.assertTrue(result.get("ok"), f"action {action!r} returned non-ok")


class TestOrchestrationI2cScan(unittest.TestCase):
    def _make_svc_with_devices(self, devices: list[int]) -> OrchestrationService:
        svc = _make_orchestration()

        def i2c_write_mock(req):
            if req.address in devices:
                return {"ok": True, "nak": 0}
            return {"ok": True, "nak": 1}

        svc._protocol.i2c_write.side_effect = i2c_write_mock
        return svc

    def test_scan_finds_devices(self):
        svc = self._make_svc_with_devices([0x48, 0x68])
        result = svc.measure_basic("i2c_scan", {"rate_hz": 100000, "scl_ch": 0, "sda_ch": 1})
        self.assertTrue(result["ok"])
        found = result["result"]["devices_found"]
        self.assertIn("0x48", found)
        self.assertIn("0x68", found)
        self.assertEqual(result["result"]["count"], 2)

    def test_scan_empty_bus(self):
        svc = self._make_svc_with_devices([])
        result = svc.measure_basic("i2c_scan", {})
        self.assertEqual(result["result"]["count"], 0)
        self.assertEqual(result["result"]["devices_found"], [])

    def test_scan_ignores_exceptions(self):
        svc = _make_orchestration()
        svc._protocol.i2c_write.side_effect = RuntimeError("NAK")
        result = svc.measure_basic("i2c_scan", {})
        self.assertEqual(result["result"]["count"], 0)


class TestOrchestrationUartLoopback(unittest.TestCase):
    def test_successful_loopback(self):
        svc = _make_orchestration()
        svc._protocol.uart_receive.return_value = {
            "data": "Hello",
            "bytes_received": 5,
            "warnings": [],
        }
        result = svc.measure_basic("uart_loopback_test", {
            "baud": 115200, "tx_ch": 0, "rx_ch": 1, "test_string": "Hello",
        })
        self.assertTrue(result["result"]["match"])
        self.assertTrue(result["within_tolerance"])

    def test_loopback_mismatch(self):
        svc = _make_orchestration()
        svc._protocol.uart_receive.return_value = {
            "data": "Garbage",
            "bytes_received": 7,
            "warnings": [],
        }
        result = svc.measure_basic("uart_loopback_test", {
            "test_string": "Hello",
        })
        self.assertFalse(result["result"]["match"])
        self.assertFalse(result["within_tolerance"])

    def test_loopback_configures_uart(self):
        svc = _make_orchestration()
        svc._protocol.uart_receive.return_value = {"data": "", "bytes_received": 0, "warnings": []}
        svc.measure_basic("uart_loopback_test", {"baud": 9600, "tx_ch": 2, "rx_ch": 3})
        call_args = svc._protocol.uart_configure.call_args[0][0]
        self.assertEqual(call_args.baud_rate, 9600)
        self.assertEqual(call_args.tx_ch, 2)
        self.assertEqual(call_args.rx_ch, 3)


class TestOrchestrationDigitalFrequency(unittest.TestCase):
    def test_within_tolerance(self):
        svc = _make_orchestration()
        svc._logic.capture.return_value = {
            "metrics": {"0": {"freq_est_hz": 1005.0, "duty_cycle_percent": 50.0, "edge_count": 20}},
        }
        result = svc.measure_basic("digital_frequency", {
            "channel": 0, "expected_freq_hz": 1000, "tolerance_percent": 5.0,
        })
        self.assertTrue(result["within_tolerance"])
        self.assertAlmostEqual(result["result"]["freq_hz"], 1005.0)

    def test_outside_tolerance(self):
        svc = _make_orchestration()
        svc._logic.capture.return_value = {
            "metrics": {"0": {"freq_est_hz": 2000.0, "duty_cycle_percent": 50.0, "edge_count": 40}},
        }
        result = svc.measure_basic("digital_frequency", {
            "channel": 0, "expected_freq_hz": 1000, "tolerance_percent": 5.0,
        })
        self.assertFalse(result["within_tolerance"])

    def test_no_expected_freq(self):
        svc = _make_orchestration()
        svc._logic.capture.return_value = {
            "metrics": {"0": {"freq_est_hz": 500.0, "duty_cycle_percent": 50.0, "edge_count": 10}},
        }
        result = svc.measure_basic("digital_frequency", {"channel": 0})
        self.assertIsNone(result["within_tolerance"])
        self.assertIsNone(result["result"]["expected_freq_hz"])


class TestOrchestrationCharacterizeSupply(unittest.TestCase):
    def test_within_tolerance(self):
        svc = _make_orchestration()
        svc._scope.capture.return_value = {
            "metrics": {"ch1": {"vavg": 3.29, "vmin": 3.27, "vmax": 3.31, "vrms": 3.29, "vpp": 0.04}},
        }
        result = svc.measure_basic("characterize_supply", {
            "vplus_v": 3.3, "enable_vplus": True, "scope_channel": 1,
        })
        self.assertTrue(result["within_tolerance"])
        self.assertAlmostEqual(result["result"]["measured_v"], 3.29)

    def test_outside_tolerance(self):
        svc = _make_orchestration()
        svc._scope.capture.return_value = {
            "metrics": {"ch1": {"vavg": 4.5, "vmin": 4.4, "vmax": 4.6, "vrms": 4.5, "vpp": 0.2}},
        }
        result = svc.measure_basic("characterize_supply", {
            "vplus_v": 3.3, "enable_vplus": True,
        })
        self.assertFalse(result["within_tolerance"])

    def test_sets_supply_and_master(self):
        svc = _make_orchestration()
        svc._scope.capture.return_value = {
            "metrics": {"ch1": {"vavg": 3.3, "vmin": 3.3, "vmax": 3.3, "vrms": 3.3, "vpp": 0.0}},
        }
        svc.measure_basic("characterize_supply", {"vplus_v": 5.0, "enable_vplus": True})
        svc._supplies.set_legacy.assert_called_once()
        svc._supplies.master.assert_called_once()


class TestOrchestrationBodeSweep(unittest.TestCase):
    def _scope_capture_for_bode(self, ref_rms, dut_rms, ref_ch=1, dut_ch=2):
        def capture(req):
            return {
                "metrics": {
                    f"ch{ref_ch}": {"vrms": ref_rms, "vmin": -ref_rms, "vmax": ref_rms,
                                     "vavg": 0, "vpp": 2 * ref_rms},
                    f"ch{dut_ch}": {"vrms": dut_rms, "vmin": -dut_rms, "vmax": dut_rms,
                                     "vavg": 0, "vpp": 2 * dut_rms},
                },
                "waveform": [],
            }
        return capture

    def test_bode_sweep_returns_frequencies_and_gain(self):
        svc = _make_orchestration()
        svc._scope.capture.side_effect = self._scope_capture_for_bode(1.0, 1.0)
        result = svc.measure_basic("bode_sweep", {
            "f_start_hz": 100, "f_stop_hz": 1000, "steps": 5,
            "amplitude_v": 1.0,
        })
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["result"]["frequencies_hz"]), 5)
        self.assertEqual(len(result["result"]["gain_db"]), 5)
        # Unity gain → 0 dB
        for g in result["result"]["gain_db"]:
            self.assertAlmostEqual(g, 0.0, places=2)

    def test_bode_sweep_3db_detection(self):
        import math
        svc = _make_orchestration()
        # Simulate gain dropping below -3 dB at step 3
        gains = [1.0, 1.0, 0.7, 0.5, 0.3]
        call_count = [0]

        def capture(req):
            i = call_count[0]
            call_count[0] += 1
            g = gains[i] if i < len(gains) else 0.5
            return {
                "metrics": {
                    "ch1": {"vrms": 1.0}, "ch2": {"vrms": g},
                },
                "waveform": [],
            }

        svc._scope.capture.side_effect = capture
        result = svc.measure_basic("bode_sweep", {
            "f_start_hz": 100, "f_stop_hz": 10000, "steps": 5,
        })
        self.assertIsNotNone(result["result"]["fc_3db_hz"])

    def test_bode_sweep_invalid_params_raises(self):
        svc = _make_orchestration()
        with self.assertRaises(DigilentConfigInvalidError):
            svc.measure_basic("bode_sweep", {"f_start_hz": 1000, "f_stop_hz": 100, "steps": 5})

    def test_bode_sweep_stops_wavegen(self):
        svc = _make_orchestration()
        svc._scope.capture.side_effect = self._scope_capture_for_bode(1.0, 1.0)
        svc.measure_basic("bode_sweep", {"f_start_hz": 100, "f_stop_hz": 200, "steps": 2})
        svc._wavegen.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
