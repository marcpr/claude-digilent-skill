"""
Unit tests for the Digilent extension.

These tests use mocking and do not require a physical device.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock the dwf_adapter at import time so tests run without libdwf.so
# ---------------------------------------------------------------------------

def _make_dwf_mock():
    from digilent.capability_registry import DeviceEnumInfo

    mod = types.ModuleType("digilent.dwf_adapter")
    mod.HDWF_NONE = MagicMock()
    mod.HDWF_NONE.value = -1

    mock_hdwf = MagicMock()
    mock_hdwf.value = 1

    _mock_device = DeviceEnumInfo(
        idx=0, devid=3, devver=1,
        name="Analog Discovery 2 (mock)", sn="SN000001", is_open=False,
    )

    mod.enumerate_devices = MagicMock(return_value=1)
    mod.enumerate_devices_full = MagicMock(return_value=[_mock_device])
    mod.get_device_name = MagicMock(return_value="Analog Discovery 2 (mock)")
    mod.get_device_type = MagicMock(return_value=(3, 1))
    mod.get_device_sn = MagicMock(return_value="SN000001")
    mod.get_device_is_opened = MagicMock(return_value=False)
    mod.get_enum_config_count = MagicMock(return_value=0)
    mod.get_enum_config_info = MagicMock(return_value=0)
    mod.DECI_ANALOG_IN_CHANNEL_COUNT = 1
    mod.DECI_ANALOG_OUT_CHANNEL_COUNT = 2
    mod.DECI_ANALOG_IO_CHANNEL_COUNT = 3
    mod.DECI_DIGITAL_IN_CHANNEL_COUNT = 4
    mod.DECI_DIGITAL_OUT_CHANNEL_COUNT = 5
    mod.DECI_DIGITAL_IO_CHANNEL_COUNT = 6
    mod.DECI_ANALOG_IN_BUFFER_SIZE = 7
    mod.DECI_ANALOG_OUT_BUFFER_SIZE = 8
    mod.DECI_DIGITAL_IN_BUFFER_SIZE = 9
    mod.DECI_DIGITAL_OUT_BUFFER_SIZE = 10
    mod.open_device = MagicMock(return_value=mock_hdwf)
    mod.close_device = MagicMock()
    mod.read_temperature = MagicMock(return_value=38.5)
    mod.scope_capture_raw = MagicMock()
    mod.scope_sample_raw = MagicMock(return_value={1: 3.3})
    mod.logic_capture_raw = MagicMock()
    mod.wavegen_apply = MagicMock()
    mod.wavegen_stop = MagicMock()
    mod.wavegen_set_custom_data = MagicMock()
    mod.wavegen_set_modulation = MagicMock()
    mod.supplies_apply = MagicMock()
    mod.supplies_off = MagicMock()
    mod.supplies_channel_node_set = MagicMock()
    mod.supplies_channel_node_get = MagicMock(return_value=3.3)
    mod.supplies_io_status = MagicMock()
    mod.supplies_master_enable = MagicMock()
    mod.static_io_apply = MagicMock(return_value={})
    mod.is_available = MagicMock(return_value=True)
    # Phase 3 — DigitalIO
    mod.digital_io_configure = MagicMock()
    mod.digital_io_read = MagicMock(return_value=0b0000_0101)
    mod.digital_io_output_get = MagicMock(return_value=0x00)
    mod.digital_io_write = MagicMock()
    # Phase 3 — Pattern
    mod.pattern_get_system_freq = MagicMock(return_value=100_000_000.0)
    mod.pattern_configure_channel = MagicMock()
    mod.pattern_run_set = MagicMock()
    mod.pattern_repeat_set = MagicMock()
    mod.pattern_start = MagicMock()
    mod.pattern_stop = MagicMock()
    mod.pattern_channel_disable = MagicMock()
    # Phase 3 — Impedance
    mod.IMP_MEASUREMENT_MAP = {
        "Impedance": 0, "ImpedancePhase": 1, "Resistance": 2, "Reactance": 3,
        "Admittance": 4, "AdmittancePhase": 5, "Conductance": 6, "Susceptance": 7,
        "SeriesCapacitance": 8, "ParallelCapacitance": 9, "SeriesInductance": 10,
        "ParallelInductance": 11, "Dissipation": 12, "Quality": 13,
    }
    mod.impedance_configure = MagicMock()
    mod.impedance_set_frequency = MagicMock()
    mod.impedance_measure = MagicMock(return_value={"Impedance": 1000.0, "ImpedancePhase": -45.0})
    mod.impedance_stop = MagicMock()
    mod.impedance_set_compensation = MagicMock()
    # Phase 3 — Protocol
    mod.uart_configure = MagicMock()
    mod.uart_send = MagicMock()
    mod.uart_receive = MagicMock(return_value=(b"hello", 0))
    mod.spi_configure = MagicMock()
    mod.spi_transfer = MagicMock(return_value=b"\xAB\xCD")
    mod.i2c_configure = MagicMock()
    mod.i2c_write = MagicMock(return_value=0)
    mod.i2c_read = MagicMock(return_value=(b"\x42", 0))
    mod.i2c_write_read = MagicMock(return_value=(b"\x01\x02", 0))
    mod.can_configure = MagicMock()
    mod.can_send = MagicMock()
    mod.can_receive = MagicMock(return_value=(0x123, b"\x01\x02\x03", False, False, 0))
    return mod


# Inject mock before any digilent import
_dwf_mock = _make_dwf_mock()
sys.modules["digilent.dwf_adapter"] = _dwf_mock

# Ensure repo root is on path so `import digilent` resolves correctly
from pathlib import Path
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from digilent.config import DigilentConfig, SafeLimits
from digilent.device_manager import DeviceManager
from digilent.errors import (
    DigilentBusyError,
    DigilentConfigInvalidError,
    DigilentNotEnabledError,
    DigilentRangeViolationError,
)
from digilent.models import (
    LogicCaptureRequest,
    ScopeCaptureRequest,
    ScopeSampleRequest,
    StaticIoPin,
    StaticIoRequest,
    SuppliesMasterRequest,
    SuppliesRequest,
    SuppliesSetRequest,
    TriggerConfig,
    WavegenRequest,
)
from digilent.scope_service import ScopeService
from digilent.logic_service import LogicService
from digilent.wavegen_service import WavegenService
from digilent.supplies_service import SuppliesService, StaticIoService
from digilent.digital_io_service import DigitalIOService
from digilent.pattern_service import PatternService
from digilent.impedance_service import ImpedanceService
from digilent.protocol_service import ProtocolService
from digilent.orchestration import OrchestrationService
from digilent.utils import compute_scope_metrics, compute_logic_metrics, downsample_minmax
from digilent.models import (
    DigitalIOConfigureRequest,
    DigitalIOWriteRequest,
    ImpedanceCompensationRequest,
    ImpedanceConfigureRequest,
    ImpedanceMeasureRequest,
    ImpedanceSweepRequest,
    PatternSetRequest,
    PatternStopRequest,
    SpiConfigureRequest,
    SpiTransferRequest,
    UartConfigureRequest,
    UartReceiveRequest,
    UartSendRequest,
    CanConfigureRequest,
    CanSendRequest,
    CanReceiveRequest,
    I2cConfigureRequest,
    I2cWriteRequest,
    I2cReadRequest,
    I2cWriteReadRequest,
)


# ---------------------------------------------------------------------------
# Utility: default config and manager
# ---------------------------------------------------------------------------

def _config(**kwargs) -> DigilentConfig:
    cfg = DigilentConfig()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _manager() -> DeviceManager:
    m = DeviceManager()
    m.open()
    return m


# ---------------------------------------------------------------------------
# Tests: metric computation
# ---------------------------------------------------------------------------

class TestScopeMetrics(unittest.TestCase):
    def _square_wave(self, n=1000, freq_hz=100.0, sample_rate=10000.0, amp=3.3):
        """Generate a synthetic square wave."""
        samples = []
        period_samples = int(sample_rate / freq_hz)
        for i in range(n):
            samples.append(amp if (i % period_samples) < period_samples // 2 else 0.0)
        return samples

    def test_vmin_vmax_vpp(self):
        samples = [0.0, 1.0, 2.0, 3.0]
        m = compute_scope_metrics(samples, 1000.0)
        self.assertAlmostEqual(m["vmin"], 0.0)
        self.assertAlmostEqual(m["vmax"], 3.0)
        self.assertAlmostEqual(m["vpp"], 3.0)

    def test_vavg(self):
        samples = [0.0, 2.0]
        m = compute_scope_metrics(samples, 1000.0)
        self.assertAlmostEqual(m["vavg"], 1.0)

    def test_vrms_dc(self):
        samples = [2.0] * 100
        m = compute_scope_metrics(samples, 1000.0)
        self.assertAlmostEqual(m["vrms"], 2.0, places=3)

    def test_freq_detection(self):
        samples = self._square_wave(n=2000, freq_hz=100.0, sample_rate=10000.0, amp=3.3)
        m = compute_scope_metrics(samples, 10000.0)
        self.assertIsNotNone(m["freq_est_hz"])
        self.assertAlmostEqual(m["freq_est_hz"], 100.0, delta=2.0)

    def test_duty_cycle(self):
        samples = self._square_wave(n=2000, freq_hz=100.0, sample_rate=10000.0, amp=3.3)
        m = compute_scope_metrics(samples, 10000.0)
        self.assertIsNotNone(m["duty_cycle_percent"])
        self.assertAlmostEqual(m["duty_cycle_percent"], 50.0, delta=3.0)

    def test_empty_samples(self):
        m = compute_scope_metrics([], 1000.0)
        self.assertEqual(m, {})


class TestLogicMetrics(unittest.TestCase):
    def test_high_low_ratio(self):
        samples = [1, 1, 0, 0]
        m = compute_logic_metrics(samples, 1000.0)
        self.assertAlmostEqual(m["high_ratio"], 0.5)
        self.assertAlmostEqual(m["low_ratio"], 0.5)

    def test_edge_count(self):
        samples = [0, 1, 0, 1, 0]
        m = compute_logic_metrics(samples, 1000.0)
        self.assertEqual(m["edge_count"], 4)

    def test_freq_estimation(self):
        # 1000 Hz at 100000 samples/s → 100 samples/period
        samples = ([0] * 50 + [1] * 50) * 10
        m = compute_logic_metrics(samples, 100000.0)
        self.assertIsNotNone(m["freq_est_hz"])
        self.assertAlmostEqual(m["freq_est_hz"], 1000.0, delta=50.0)


class TestDownsampling(unittest.TestCase):
    def test_passthrough_if_small(self):
        samples = [float(i) for i in range(100)]
        out = downsample_minmax(samples, 200)
        self.assertEqual(out, samples)

    def test_reduces_length(self):
        samples = [float(i) for i in range(10000)]
        out = downsample_minmax(samples, 200)
        self.assertLessEqual(len(out), 200)

    def test_preserves_extremes(self):
        samples = [0.0] * 500 + [5.0] * 500
        out = downsample_minmax(samples, 100)
        self.assertAlmostEqual(min(out), 0.0)
        self.assertAlmostEqual(max(out), 5.0)


# ---------------------------------------------------------------------------
# Tests: request validation
# ---------------------------------------------------------------------------

class TestScopeValidation(unittest.TestCase):
    def setUp(self):
        self.svc = ScopeService(_manager(), _config())

    def test_invalid_channel(self):
        req = ScopeCaptureRequest(channels=[3], range_v=5.0, sample_rate_hz=1000, duration_ms=10)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_negative_range(self):
        req = ScopeCaptureRequest(channels=[1], range_v=-1.0, sample_rate_hz=1000, duration_ms=10)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_sample_rate_too_high(self):
        cfg = _config()
        cfg.safe_limits.max_scope_sample_rate_hz = 1000
        svc = ScopeService(_manager(), cfg)
        req = ScopeCaptureRequest(channels=[1], range_v=5.0, sample_rate_hz=2000, duration_ms=10)
        with self.assertRaises(DigilentRangeViolationError):
            svc._validate(req)

    def test_trigger_channel_not_in_capture(self):
        req = ScopeCaptureRequest(
            channels=[1],
            range_v=5.0,
            sample_rate_hz=1000,
            duration_ms=10,
            trigger=TriggerConfig(enabled=True, source="ch2"),
        )
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_valid_request_passes(self):
        req = ScopeCaptureRequest(channels=[1, 2], range_v=5.0, sample_rate_hz=1000, duration_ms=10)
        self.svc._validate(req)  # must not raise


class TestLogicValidation(unittest.TestCase):
    def setUp(self):
        self.svc = LogicService(_manager(), _config())

    def test_channel_out_of_range(self):
        req = LogicCaptureRequest(channels=[16], sample_rate_hz=1000, samples=100)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_duplicate_channels(self):
        req = LogicCaptureRequest(channels=[0, 0], sample_rate_hz=1000, samples=100)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_trigger_channel_not_in_list(self):
        req = LogicCaptureRequest(
            channels=[0],
            sample_rate_hz=1000,
            samples=100,
            trigger=TriggerConfig(enabled=True, channel=3),
        )
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_samples_exceed_limit(self):
        cfg = _config()
        cfg.max_logic_points = 100
        svc = LogicService(_manager(), cfg)
        req = LogicCaptureRequest(channels=[0], sample_rate_hz=1000, samples=200)
        with self.assertRaises(DigilentRangeViolationError):
            svc._validate(req)


class TestWavegenValidation(unittest.TestCase):
    def setUp(self):
        self.svc = WavegenService(_manager(), _config())

    def test_invalid_waveform(self):
        req = WavegenRequest(channel=1, waveform="sawtooth", frequency_hz=1000, amplitude_v=1.0, offset_v=0.0, enable=True)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_amplitude_too_high(self):
        cfg = _config()
        cfg.safe_limits.max_wavegen_amplitude_v = 3.0
        svc = WavegenService(_manager(), cfg)
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=4.0, offset_v=0.0, enable=True)
        with self.assertRaises(DigilentRangeViolationError):
            svc._validate(req)

    def test_invalid_channel(self):
        req = WavegenRequest(channel=3, waveform="sine", frequency_hz=1000, amplitude_v=1.0, offset_v=0.0, enable=True)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)


class TestSuppliesValidation(unittest.TestCase):
    """Legacy set_legacy() path (AD2-style vplus/vminus API)."""

    def test_disabled_by_default(self):
        svc = SuppliesService(_manager(), _config())
        req = SuppliesRequest(vplus_v=3.3, enable_vplus=True, confirm_unsafe=True)
        with self.assertRaises(DigilentNotEnabledError):
            svc.set_legacy(req)

    def test_requires_confirm_unsafe(self):
        cfg = _config()
        cfg.allow_supplies = True
        svc = SuppliesService(_manager(), cfg)
        req = SuppliesRequest(vplus_v=3.3, enable_vplus=True, confirm_unsafe=False)
        with self.assertRaises(DigilentConfigInvalidError):
            svc.set_legacy(req)

    def test_vplus_too_high(self):
        cfg = _config()
        cfg.allow_supplies = True
        cfg.safe_limits.max_supply_plus_v = 5.0
        svc = SuppliesService(_manager(), cfg)
        req = SuppliesRequest(vplus_v=6.0, enable_vplus=True, confirm_unsafe=True)
        with self.assertRaises(DigilentRangeViolationError):
            svc.set_legacy(req)


class TestStaticIoValidation(unittest.TestCase):
    def setUp(self):
        self.svc = StaticIoService(_manager(), _config())

    def test_pin_out_of_range(self):
        req = StaticIoRequest(pins=[StaticIoPin(index=16, mode="output", value=1)])
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_invalid_mode(self):
        req = StaticIoRequest(pins=[StaticIoPin(index=0, mode="tristate", value=0)])
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_empty_pins(self):
        req = StaticIoRequest(pins=[])
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)


# ---------------------------------------------------------------------------
# Tests: DeviceManager state machine
# ---------------------------------------------------------------------------

class TestDeviceManager(unittest.TestCase):
    def test_open_sets_idle(self):
        m = DeviceManager()
        m.open()
        self.assertEqual(m.state, "idle")
        self.assertTrue(m.is_open)

    def test_close_sets_absent(self):
        m = DeviceManager()
        m.open()
        m.close()
        self.assertFalse(m.is_open)

    def test_busy_during_session(self):
        m = DeviceManager()
        m.open()
        with m.session():
            self.assertEqual(m.state, "busy")
            with self.assertRaises(DigilentBusyError):
                with m.session():
                    pass

    def test_idle_after_session(self):
        m = DeviceManager()
        m.open()
        with m.session():
            pass
        self.assertEqual(m.state, "idle")

    def test_auto_open_in_session(self):
        m = DeviceManager()
        # Not explicitly opened — session should auto-open
        with m.session() as hdwf:
            self.assertIsNotNone(hdwf)
        self.assertEqual(m.state, "idle")


# ---------------------------------------------------------------------------
# Tests: models / from_dict
# ---------------------------------------------------------------------------

class TestModels(unittest.TestCase):
    def test_scope_request_from_dict(self):
        d = {
            "channels": [1, 2],
            "range_v": 10.0,
            "sample_rate_hz": 5000000,
            "duration_ms": 20,
            "trigger": {"enabled": True, "source": "ch1", "edge": "falling", "level_v": 2.5},
        }
        req = ScopeCaptureRequest.from_dict(d)
        self.assertEqual(req.channels, [1, 2])
        self.assertAlmostEqual(req.range_v, 10.0)
        self.assertTrue(req.trigger.enabled)
        self.assertEqual(req.trigger.edge, "falling")

    def test_logic_request_from_dict(self):
        d = {"channels": [0, 1, 2], "sample_rate_hz": 10000000, "samples": 50000}
        req = LogicCaptureRequest.from_dict(d)
        self.assertEqual(req.channels, [0, 1, 2])

    def test_wavegen_request_from_dict(self):
        d = {"channel": 2, "waveform": "square", "frequency_hz": 500, "amplitude_v": 1.65, "offset_v": 1.65, "enable": True}
        req = WavegenRequest.from_dict(d)
        self.assertEqual(req.channel, 2)
        self.assertEqual(req.waveform, "square")


# ---------------------------------------------------------------------------
# Tests: config loading
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = DigilentConfig()
        self.assertTrue(cfg.enabled)
        self.assertFalse(cfg.allow_supplies)
        self.assertEqual(cfg.max_scope_points, 20_000)

    def test_load_nonexistent_returns_defaults(self):
        from digilent.config import load_config
        cfg = load_config("/nonexistent/path/digilent.json")
        self.assertIsInstance(cfg, DigilentConfig)


# ---------------------------------------------------------------------------
# Phase 2 tests: scope capability gate and new validations
# ---------------------------------------------------------------------------

class TestScopePhase2(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        self.svc = ScopeService(self.m, _config())

    def test_capability_gate_no_analog_in(self):
        """DigilentNotAvailable when device has no analog inputs."""
        from digilent.errors import DigilentNotAvailable
        self.m._capability.analog_in_ch = 0
        req = ScopeCaptureRequest(channels=[1], range_v=5.0, sample_rate_hz=1000, duration_ms=10)
        with self.assertRaises(DigilentNotAvailable):
            self.svc._validate(req)

    def test_channel_exceeds_device_cap(self):
        """Channel beyond device capability raises."""
        self.m._capability.analog_in_ch = 2
        req = ScopeCaptureRequest(channels=[3], range_v=5.0, sample_rate_hz=1000, duration_ms=10)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_rate_exceeds_device_cap(self):
        """Sample rate beyond device capability raises."""
        from digilent.errors import DigilentRangeViolationError
        self.m._capability.max_scope_rate_hz = 1_000_000
        req = ScopeCaptureRequest(channels=[1], range_v=5.0, sample_rate_hz=2_000_000, duration_ms=10)
        with self.assertRaises(DigilentRangeViolationError):
            self.svc._validate(req)

    def test_invalid_filter(self):
        req = ScopeCaptureRequest(channels=[1], range_v=5.0, sample_rate_hz=1000, duration_ms=10, filter="bad")
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_invalid_trigger_type(self):
        from digilent.models import TriggerConfig
        req = ScopeCaptureRequest(
            channels=[1], range_v=5.0, sample_rate_hz=1000, duration_ms=10,
            trigger=TriggerConfig(enabled=True, source="ch1", type="badtype"),
        )
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_scope_sample_valid(self):
        """sample() returns dict with channel keys."""
        req = ScopeSampleRequest(channels=[1], range_v=5.0)
        result = self.svc.sample(req)
        self.assertTrue(result["ok"])
        self.assertIn("ch1", result["samples"])

    def test_scope_sample_invalid_channel(self):
        req = ScopeSampleRequest(channels=[0], range_v=5.0)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.sample(req)

    def test_scope_sample_gate_no_analog_in(self):
        """sample() also respects capability gate."""
        from digilent.errors import DigilentNotAvailable
        self.m._capability.analog_in_ch = 0
        req = ScopeSampleRequest(channels=[1], range_v=5.0)
        with self.assertRaises(DigilentNotAvailable):
            self.svc.sample(req)


# ---------------------------------------------------------------------------
# Phase 2 tests: wavegen new waveforms, custom, modulation, EE block
# ---------------------------------------------------------------------------

class TestWavegenPhase2(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        self.svc = WavegenService(self.m, _config())

    def test_rampup_valid(self):
        req = WavegenRequest(channel=1, waveform="rampup", frequency_hz=1000, amplitude_v=1.0)
        self.svc._validate(req)  # must not raise

    def test_rampdown_valid(self):
        req = WavegenRequest(channel=1, waveform="rampdown", frequency_hz=1000, amplitude_v=1.0)
        self.svc._validate(req)

    def test_noise_valid(self):
        req = WavegenRequest(channel=1, waveform="noise", frequency_hz=1000, amplitude_v=1.0)
        self.svc._validate(req)

    def test_custom_requires_data(self):
        req = WavegenRequest(channel=1, waveform="custom", frequency_hz=1000, amplitude_v=1.0, custom_data=[])
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_custom_with_data_valid(self):
        req = WavegenRequest(channel=1, waveform="custom", frequency_hz=1000, amplitude_v=1.0,
                             custom_data=[0.0, 0.5, 1.0, 0.5])
        self.svc._validate(req)

    def test_offset_v_too_high(self):
        cfg = _config()
        cfg.safe_limits.max_wavegen_offset_v = 5.0
        svc = WavegenService(self.m, cfg)
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=1.0, offset_v=6.0)
        with self.assertRaises(DigilentRangeViolationError):
            svc._validate(req)

    def test_peak_voltage_exceeds_limit(self):
        cfg = _config()
        cfg.safe_limits.max_wavegen_amplitude_v = 5.0
        cfg.safe_limits.max_wavegen_offset_v = 5.0
        svc = WavegenService(self.m, cfg)
        # amplitude=4V + offset=3V → peak=7V > 5V
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=4.0, offset_v=3.0)
        with self.assertRaises(DigilentRangeViolationError):
            svc._validate(req)

    def test_ee_channel_3_blocked(self):
        """Electronics Explorer channels 3/4 are power supply outputs, not AWG."""
        from digilent import capability_registry
        self.m._capability = capability_registry.get_capability(1)  # EE devid=1
        svc = WavegenService(self.m, _config())
        req = WavegenRequest(channel=3, waveform="sine", frequency_hz=1000, amplitude_v=1.0)
        with self.assertRaises(DigilentConfigInvalidError):
            svc._validate(req)

    def test_ee_channels_1_2_valid(self):
        """EE channels 1 and 2 are valid AWG channels."""
        from digilent import capability_registry
        self.m._capability = capability_registry.get_capability(1)  # EE devid=1
        svc = WavegenService(self.m, _config())
        req = WavegenRequest(channel=2, waveform="sine", frequency_hz=1000, amplitude_v=1.0)
        svc._validate(req)  # must not raise

    def test_modulation_invalid_type(self):
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=1.0,
                             modulation={"type": "pm"})
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_phase_deg_out_of_range(self):
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=1.0, phase_deg=360.0)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc._validate(req)

    def test_capability_gate_no_awg(self):
        """DigilentNotAvailable when device has no AWG."""
        from digilent.errors import DigilentNotAvailable
        self.m._capability.analog_out_ch = 0
        req = WavegenRequest(channel=1, waveform="sine", frequency_hz=1000, amplitude_v=1.0)
        with self.assertRaises(DigilentNotAvailable):
            self.svc._validate(req)


# ---------------------------------------------------------------------------
# Phase 2 tests: supplies table-driven service
# ---------------------------------------------------------------------------

class TestSuppliesPhase2(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        # AD2 (devid=3) has V+, V-, USB_5V channels
        self.cfg_on = _config()
        self.cfg_on.allow_supplies = True
        self.svc = SuppliesService(self.m, self.cfg_on)

    def test_info_returns_channels(self):
        result = self.svc.info()
        self.assertTrue(result["ok"])
        self.assertIn("supply_channels", result)
        # AD2 has supply channels
        self.assertGreater(len(result["supply_channels"]), 0)

    def test_info_no_power_supply_raises(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.has_power_supply = False
        with self.assertRaises(DigilentNotAvailable):
            self.svc.info()

    def test_status_returns_readings(self):
        result = self.svc.status()
        self.assertTrue(result["ok"])
        self.assertIn("readings", result)

    def test_set_unknown_channel(self):
        req = SuppliesSetRequest(channel_name="NONEXISTENT", enable=False, confirm_unsafe=True)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_set_requires_confirm_unsafe_to_enable(self):
        req = SuppliesSetRequest(channel_name="V+", enable=True, confirm_unsafe=False)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_set_voltage_requires_confirm_unsafe(self):
        req = SuppliesSetRequest(channel_name="V+", enable=False, voltage_v=3.3, confirm_unsafe=False)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_set_voltage_out_of_range(self):
        req = SuppliesSetRequest(channel_name="V+", enable=False, voltage_v=100.0, confirm_unsafe=True)
        with self.assertRaises(DigilentRangeViolationError):
            self.svc.set(req)

    def test_set_read_only_channel(self):
        """USB_5V is a monitor-only channel — write must be rejected."""
        req = SuppliesSetRequest(channel_name="USB_5V", enable=False, confirm_unsafe=True)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_set_disabled_raises(self):
        svc_off = SuppliesService(self.m, _config())  # allow_supplies=False
        req = SuppliesSetRequest(channel_name="V+", enable=False, confirm_unsafe=True)
        with self.assertRaises(DigilentNotEnabledError):
            svc_off.set(req)

    def test_master_requires_confirm_unsafe(self):
        req = SuppliesMasterRequest(enable=True, confirm_unsafe=False)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.master(req)

    def test_master_disabled_raises(self):
        svc_off = SuppliesService(self.m, _config())
        req = SuppliesMasterRequest(enable=True, confirm_unsafe=True)
        with self.assertRaises(DigilentNotEnabledError):
            svc_off.master(req)

    def test_set_vplus_valid(self):
        """Valid V+ set call should succeed and return ok."""
        req = SuppliesSetRequest(channel_name="V+", enable=True, voltage_v=3.3, confirm_unsafe=True)
        result = self.svc.set(req)
        self.assertTrue(result["ok"])


# ---------------------------------------------------------------------------
# Phase 3 tests: Digital I/O
# ---------------------------------------------------------------------------

class TestDigitalIOPhase3(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        self.m._capability.digital_io_ch = 16
        self.svc = DigitalIOService(self.m, _config())

    def test_capability_gate_no_dio(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.digital_io_ch = 0
        with self.assertRaises(DigilentNotAvailable):
            self.svc.read()

    def test_configure_returns_ok(self):
        req = DigitalIOConfigureRequest(output_enable_mask=0xFF, output_value=0x0F)
        result = self.svc.configure(req)
        self.assertTrue(result["ok"])
        self.assertIn("input_word", result)

    def test_read_returns_pin_states(self):
        result = self.svc.read()
        self.assertTrue(result["ok"])
        self.assertIn("pins", result)
        self.assertEqual(len(result["pins"]), 16)

    def test_read_pin_values_from_mock(self):
        # mock returns 0b00000101 → pins 0 and 2 are high
        result = self.svc.read()
        self.assertEqual(result["pins"][0], 1)
        self.assertEqual(result["pins"][1], 0)
        self.assertEqual(result["pins"][2], 1)

    def test_write_returns_ok(self):
        req = DigitalIOWriteRequest(value=0xFF, mask=0xFF)
        result = self.svc.write(req)
        self.assertTrue(result["ok"])

    def test_dd_offset_shifts_mask(self):
        """Digital Discovery offset=24 shifts enable mask by 24 bits."""
        from digilent import capability_registry
        self.m._capability = capability_registry.get_capability(4)  # Digital Discovery
        req = DigitalIOConfigureRequest(output_enable_mask=0x01, output_value=0x01)
        self.svc.configure(req)
        call_args = _dwf_mock.digital_io_configure.call_args
        enable_mask_arg = call_args[0][1]  # second positional arg
        self.assertEqual(enable_mask_arg, 0x01 << 24)

    def test_no_offset_for_ad2(self):
        """AD2 has no offset — enable mask stays as-is."""
        req = DigitalIOConfigureRequest(output_enable_mask=0x03, output_value=0x01)
        self.svc.configure(req)
        call_args = _dwf_mock.digital_io_configure.call_args
        enable_mask_arg = call_args[0][1]
        self.assertEqual(enable_mask_arg, 0x03)


# ---------------------------------------------------------------------------
# Phase 3 tests: Pattern Generator
# ---------------------------------------------------------------------------

class TestPatternPhase3(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        self.m._capability.digital_out_ch = 16
        self.svc = PatternService(self.m, _config())

    def test_capability_gate_no_pattern(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.digital_out_ch = 0
        with self.assertRaises(DigilentNotAvailable):
            self.svc.set(PatternSetRequest())

    def test_set_pulse_returns_ok(self):
        req = PatternSetRequest(channel=0, type="pulse", frequency_hz=1000.0, duty_pct=50.0)
        result = self.svc.set(req)
        self.assertTrue(result["ok"])
        self.assertEqual(result["channel"], 0)

    def test_set_random_returns_ok(self):
        req = PatternSetRequest(channel=1, type="random", frequency_hz=500.0)
        result = self.svc.set(req)
        self.assertTrue(result["ok"])

    def test_custom_requires_data(self):
        req = PatternSetRequest(channel=0, type="custom", frequency_hz=1000.0, custom_data="")
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_invalid_type_raises(self):
        req = PatternSetRequest(channel=0, type="zigzag", frequency_hz=1000.0)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_invalid_idle_state_raises(self):
        req = PatternSetRequest(channel=0, type="pulse", frequency_hz=1000.0, idle_state="float")
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_channel_out_of_range(self):
        req = PatternSetRequest(channel=20, type="pulse", frequency_hz=1000.0)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)

    def test_stop_all_calls_sdk(self):
        req = PatternStopRequest(channel="all")
        result = self.svc.stop(req)
        self.assertTrue(result["ok"])
        _dwf_mock.pattern_stop.assert_called()

    def test_stop_channel_calls_disable(self):
        req = PatternStopRequest(channel=0)
        result = self.svc.stop(req)
        self.assertTrue(result["ok"])
        _dwf_mock.pattern_channel_disable.assert_called()

    def test_negative_freq_raises(self):
        req = PatternSetRequest(channel=0, type="pulse", frequency_hz=-1.0)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.set(req)


# ---------------------------------------------------------------------------
# Phase 3 tests: Impedance Analyzer
# ---------------------------------------------------------------------------

class TestImpedancePhase3(unittest.TestCase):
    def setUp(self):
        self.m = _manager()  # AD2 has both analog_in_ch=2 and analog_out_ch=2
        self.cfg = _config()
        self.cfg.safe_limits.max_impedance_sweep_amplitude_v = 1.0
        self.svc = ImpedanceService(self.m, self.cfg)

    def test_capability_gate_no_analog_in(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.analog_in_ch = 0
        with self.assertRaises(DigilentNotAvailable):
            self.svc.configure(ImpedanceConfigureRequest())

    def test_capability_gate_no_analog_out(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.analog_out_ch = 0
        with self.assertRaises(DigilentNotAvailable):
            self.svc.configure(ImpedanceConfigureRequest())

    def test_configure_calls_sdk(self):
        req = ImpedanceConfigureRequest(frequency_hz=10000.0, amplitude_v=0.5)
        result = self.svc.configure(req)
        self.assertTrue(result["ok"])
        _dwf_mock.impedance_configure.assert_called()

    def test_configure_amplitude_too_high(self):
        req = ImpedanceConfigureRequest(amplitude_v=2.0)
        with self.assertRaises(DigilentRangeViolationError):
            self.svc.configure(req)

    def test_measure_returns_dict(self):
        req = ImpedanceMeasureRequest(measurements=["Impedance", "ImpedancePhase"])
        result = self.svc.measure(req)
        self.assertTrue(result["ok"])
        self.assertIn("measurements", result)
        self.assertIn("Impedance", result["measurements"])

    def test_measure_invalid_measurement(self):
        req = ImpedanceMeasureRequest(measurements=["Foo"])
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.measure(req)

    def test_sweep_returns_frequencies(self):
        req = ImpedanceSweepRequest(
            f_start_hz=100.0, f_stop_hz=10000.0, steps=5,
            amplitude_v=0.5, measurements=["Impedance"],
        )
        result = self.svc.sweep(req)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["frequencies"]), 5)
        self.assertIn("Impedance", result["measurements"])
        self.assertEqual(len(result["measurements"]["Impedance"]), 5)

    def test_sweep_too_few_steps(self):
        req = ImpedanceSweepRequest(f_start_hz=100.0, f_stop_hz=10000.0, steps=1)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.sweep(req)

    def test_sweep_amplitude_too_high(self):
        req = ImpedanceSweepRequest(f_start_hz=100.0, f_stop_hz=10000.0, steps=5, amplitude_v=5.0)
        with self.assertRaises(DigilentRangeViolationError):
            self.svc.sweep(req)

    def test_set_compensation_calls_sdk(self):
        req = ImpedanceCompensationRequest(open_r=0.0, open_x=0.0, short_r=1.0, short_x=0.0)
        result = self.svc.set_compensation(req)
        self.assertTrue(result["ok"])
        _dwf_mock.impedance_set_compensation.assert_called()

    def test_sweep_log_spacing(self):
        """Sweep frequencies should be log-spaced."""
        req = ImpedanceSweepRequest(
            f_start_hz=100.0, f_stop_hz=100000.0, steps=3,
            amplitude_v=0.5, measurements=["Impedance"],
        )
        result = self.svc.sweep(req)
        freqs = result["frequencies"]
        self.assertAlmostEqual(freqs[0], 100.0, delta=1.0)
        self.assertAlmostEqual(freqs[-1], 100000.0, delta=1000.0)
        # middle should be geometric mean ≈ 3162
        self.assertAlmostEqual(freqs[1], 3162.0, delta=100.0)


# ---------------------------------------------------------------------------
# Phase 3 tests: Protocol Service
# ---------------------------------------------------------------------------

class TestProtocolPhase3(unittest.TestCase):
    def setUp(self):
        self.m = _manager()
        self.m._capability.has_protocols = True
        self.svc = ProtocolService(self.m, _config())

    def test_capability_gate_no_protocols(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.has_protocols = False
        with self.assertRaises(DigilentNotAvailable):
            self.svc.uart_configure(UartConfigureRequest())

    def test_uart_configure_returns_ok(self):
        req = UartConfigureRequest(baud_rate=115200)
        result = self.svc.uart_configure(req)
        self.assertTrue(result["ok"])
        self.assertEqual(result["baud_rate"], 115200)

    def test_uart_invalid_parity_raises(self):
        req = UartConfigureRequest(parity="super-even")
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.uart_configure(req)

    def test_uart_send_returns_byte_count(self):
        req = UartSendRequest(data="hello")
        result = self.svc.uart_send(req)
        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes_sent"], 5)

    def test_uart_receive_returns_data(self):
        req = UartReceiveRequest(max_bytes=64, timeout_s=0.0)
        result = self.svc.uart_receive(req)
        self.assertTrue(result["ok"])
        self.assertIn("data", result)

    def test_spi_configure_returns_ok(self):
        req = SpiConfigureRequest(freq_hz=1_000_000.0)
        result = self.svc.spi_configure(req)
        self.assertTrue(result["ok"])

    def test_spi_invalid_mode_raises(self):
        req = SpiConfigureRequest(mode=4)
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.spi_configure(req)

    def test_spi_invalid_order_raises(self):
        req = SpiConfigureRequest(order="weird")
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.spi_configure(req)

    def test_spi_transfer_returns_rx_data(self):
        req = SpiTransferRequest(tx_data=[0xAA, 0xBB], rx_len=2)
        result = self.svc.spi_transfer(req)
        self.assertTrue(result["ok"])
        self.assertIn("rx_data", result)

    def test_i2c_configure_returns_ok(self):
        req = I2cConfigureRequest(rate_hz=100_000.0)
        result = self.svc.i2c_configure(req)
        self.assertTrue(result["ok"])

    def test_i2c_write_returns_nak(self):
        req = I2cWriteRequest(address=0x48, data=[0x00])
        result = self.svc.i2c_write(req)
        self.assertTrue(result["ok"])
        self.assertEqual(result["nak"], 0)

    def test_i2c_read_returns_data(self):
        req = I2cReadRequest(address=0x48, length=1)
        result = self.svc.i2c_read(req)
        self.assertTrue(result["ok"])
        self.assertIn("data", result)

    def test_i2c_write_read_returns_rx(self):
        req = I2cWriteReadRequest(address=0x48, tx=[0x00], rx_len=2)
        result = self.svc.i2c_write_read(req)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rx_data"]), 2)

    def test_can_configure_returns_ok(self):
        req = CanConfigureRequest(rate_hz=500_000.0)
        result = self.svc.can_configure(req)
        self.assertTrue(result["ok"])

    def test_can_send_too_long_raises(self):
        req = CanSendRequest(id=0x123, data=list(range(9)))
        with self.assertRaises(DigilentConfigInvalidError):
            self.svc.can_send(req)

    def test_can_send_returns_ok(self):
        req = CanSendRequest(id=0x123, data=[0x01, 0x02, 0x03])
        result = self.svc.can_send(req)
        self.assertTrue(result["ok"])
        self.assertEqual(result["id"], "0x123")

    def test_can_receive_returns_frame(self):
        req = CanReceiveRequest(timeout_s=0.1)
        result = self.svc.can_receive(req)
        self.assertTrue(result["ok"])
        # mock returns status=0 with data, so frame received
        self.assertIsNotNone(result["id"])

    def test_spi_no_protocol_gate(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.has_protocols = False
        with self.assertRaises(DigilentNotAvailable):
            self.svc.spi_configure(SpiConfigureRequest())

    def test_i2c_no_protocol_gate(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.has_protocols = False
        with self.assertRaises(DigilentNotAvailable):
            self.svc.i2c_configure(I2cConfigureRequest())

    def test_can_no_protocol_gate(self):
        from digilent.errors import DigilentNotAvailable
        self.m._capability.has_protocols = False
        with self.assertRaises(DigilentNotAvailable):
            self.svc.can_configure(CanConfigureRequest())


if __name__ == "__main__":
    unittest.main()
