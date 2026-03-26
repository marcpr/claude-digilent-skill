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
# Default no-op stubs for sniff functions (overridden per-test where needed)
_dwf_stub.i2c_spy_start = MagicMock()
_dwf_stub.i2c_spy_read = MagicMock(return_value=(False, False, b"", 0))
_dwf_stub.uart_configure = MagicMock()
_dwf_stub.uart_receive = MagicMock(return_value=(b"", 0))
_dwf_stub.can_configure = MagicMock()
_dwf_stub.can_receive = MagicMock(return_value=(0, b"", False, False, 1))
_dwf_stub.spi_sniff_raw = MagicMock(return_value=[])
sys.modules.setdefault("digilent.dwf_adapter", _dwf_stub)

from digilent.capability_registry import CapabilityRecord
from digilent.config import DigilentConfig
from digilent.errors import DigilentNotAvailable
from digilent.models import (
    CanConfigureRequest,
    CanSniffRequest,
    I2cConfigureRequest,
    I2cSpyConfigureRequest,
    I2cSpyReadRequest,
    SpiConfigureRequest,
    SpiSniffRequest,
    UartConfigureRequest,
    UartSniffRequest,
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


class TestSniffCapabilityGate(unittest.TestCase):
    """All sniff endpoints must raise DigilentNotAvailable when has_protocols=False."""

    def test_i2c_spy_configure_raises(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.i2c_spy_configure(I2cSpyConfigureRequest())

    def test_i2c_spy_read_raises(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.i2c_spy_read(I2cSpyReadRequest())

    def test_uart_sniff_raises(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.uart_sniff(UartSniffRequest())

    def test_can_sniff_raises(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.can_sniff(CanSniffRequest())

    def test_spi_sniff_raises(self):
        svc = _make_service(has_protocols=False)
        with self.assertRaises(DigilentNotAvailable):
            svc.spi_sniff(SpiSniffRequest())


class TestSniffServiceLogic(unittest.TestCase):
    """Happy-path and validation tests with stubbed dwf_adapter."""

    def setUp(self):
        # Re-sync protocol_service.dwf to whichever stub is currently in sys.modules.
        # test_capability_registry replaces sys.modules["digilent.dwf_adapter"] in its
        # setUp without restoring it, so the object bound as `dwf` inside protocol_service
        # can diverge from the one tests mutate.
        import digilent.protocol_service as _ps
        _stub = sys.modules["digilent.dwf_adapter"]
        _ps.dwf = _stub
        # Ensure all sniff/spy attributes exist on the active stub
        _defaults = {
            "i2c_spy_start": MagicMock(),
            "i2c_spy_read": MagicMock(return_value=(False, False, b"", 0)),
            "uart_configure": MagicMock(),
            "uart_receive": MagicMock(return_value=(b"", 0)),
            "can_configure": MagicMock(),
            "can_receive": MagicMock(return_value=(0, b"", False, False, 1)),
            "spi_sniff_raw": MagicMock(return_value=[]),
        }
        for attr, default in _defaults.items():
            if not hasattr(_stub, attr):
                setattr(_stub, attr, default)

    def _make_svc_with_dwf(self, **dwf_overrides):
        """Return a service whose dwf stub has specified return values."""
        stub = sys.modules["digilent.dwf_adapter"]
        for k, v in dwf_overrides.items():
            setattr(stub, k, v)
        return _make_service(has_protocols=True)

    # --- I2C spy ---

    def test_i2c_spy_configure_ok(self):
        sys.modules["digilent.dwf_adapter"].i2c_spy_start = MagicMock()
        svc = _make_service()
        resp = svc.i2c_spy_configure(I2cSpyConfigureRequest(rate_hz=400_000, scl_ch=2, sda_ch=3))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["mode"], "spy")
        self.assertEqual(resp["rate_hz"], 400_000)

    def test_i2c_spy_read_empty_returns_zero_frames(self):
        sys.modules["digilent.dwf_adapter"].i2c_spy_read = MagicMock(
            return_value=(False, False, b"", 0)
        )
        svc = _make_service()
        req = I2cSpyReadRequest(duration_s=0.05, max_frames=10)
        resp = svc.i2c_spy_read(req)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["frame_count"], 0)
        self.assertEqual(resp["bytes_captured"], 0)

    def test_i2c_spy_read_collects_frames(self):
        calls = [
            (True, False, b"\x48\x01", 0),
            (False, True, b"\xAB", 0),
            (False, False, b"", 0),
        ]
        sys.modules["digilent.dwf_adapter"].i2c_spy_read = MagicMock(side_effect=calls * 20)
        svc = _make_service()
        req = I2cSpyReadRequest(duration_s=0.05, max_frames=2)
        resp = svc.i2c_spy_read(req)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["frame_count"], 2)
        self.assertEqual(resp["bytes_captured"], 3)
        self.assertTrue(resp["frames"][0]["start"])
        self.assertTrue(resp["frames"][1]["stop"])

    # --- UART sniff ---

    def test_uart_sniff_returns_data(self):
        sys.modules["digilent.dwf_adapter"].uart_configure = MagicMock()
        sys.modules["digilent.dwf_adapter"].uart_receive = MagicMock(
            side_effect=[(b"hello", 0), (b"", 0)] * 20
        )
        svc = _make_service()
        req = UartSniffRequest(rx_ch=2, baud_rate=115200, duration_s=0.05, max_bytes=64)
        resp = svc.uart_sniff(req)
        self.assertTrue(resp["ok"])
        self.assertIn("hello", resp["data"])
        self.assertEqual(resp["baud_rate"], 115200)

    def test_uart_sniff_invalid_parity_raises(self):
        from digilent.errors import DigilentConfigInvalidError
        svc = _make_service()
        req = UartSniffRequest(parity="bad")
        with self.assertRaises(DigilentConfigInvalidError):
            svc.uart_sniff(req)

    # --- CAN sniff ---

    def test_can_sniff_collects_frames(self):
        sys.modules["digilent.dwf_adapter"].can_configure = MagicMock()
        sys.modules["digilent.dwf_adapter"].can_receive = MagicMock(side_effect=[
            (0x123, b"\x01\x02", False, False, 0),
            (0x456, b"\xFF", True, False, 0),
            (0, b"", False, False, 1),
        ] * 20)
        svc = _make_service()
        req = CanSniffRequest(rx_ch=1, rate_hz=500_000, duration_s=0.05, max_frames=2)
        resp = svc.can_sniff(req)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["frame_count"], 2)
        self.assertEqual(resp["frames"][0]["id"], "0x123")
        self.assertEqual(resp["frames"][1]["extended"], True)

    # --- SPI sniff ---

    def test_spi_sniff_invalid_mode_raises(self):
        from digilent.errors import DigilentConfigInvalidError
        svc = _make_service()
        req = SpiSniffRequest(mode=5)
        with self.assertRaises(DigilentConfigInvalidError):
            svc.spi_sniff(req)

    def test_spi_sniff_invalid_order_raises(self):
        from digilent.errors import DigilentConfigInvalidError
        svc = _make_service()
        req = SpiSniffRequest(order="bad")
        with self.assertRaises(DigilentConfigInvalidError):
            svc.spi_sniff(req)

    def test_spi_sniff_returns_transactions(self):
        sys.modules["digilent.dwf_adapter"].spi_sniff_raw = MagicMock(return_value=[
            {"mosi": [0xAB, 0xCD], "miso": [0x00, 0x00], "bits": 16},
            {"mosi": [0x12], "miso": [0x34], "bits": 8},
        ])
        svc = _make_service()
        req = SpiSniffRequest(spi_freq_hz=1_000_000, mode=0, duration_s=0.05)
        resp = svc.spi_sniff(req)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["transaction_count"], 2)
        self.assertEqual(resp["transactions"][0]["mosi"], [0xAB, 0xCD])
        self.assertEqual(resp["transactions"][1]["miso"], [0x34])


class TestSpiDecoder(unittest.TestCase):
    """Unit tests for the _spi_decode software decoder in dwf_adapter."""

    def setUp(self):
        # _spi_codec has no ctypes/libdwf dependency — import directly
        from digilent._spi_codec import spi_decode
        self._decode = spi_decode

    def _make_samples(self, clk, mosi, miso, cs):
        return {0: clk, 1: mosi, 2: miso, 3: cs}

    def test_no_cs_assert_returns_empty(self):
        n = 20
        samples = self._make_samples([0]*n, [0]*n, [0]*n, [1]*n)
        self.assertEqual(self._decode(samples, 0, 1, 2, 3, 0, "msb", True), [])

    def test_mode0_single_byte_mosi(self):
        # CS asserts, 8 rising CLK edges, CS deasserts
        cs   = [1, 0] + [0]*16 + [1]      # CS low for 16 clk-edges
        clk  = [0, 0] + [0,1]*8 + [0]     # 8 rising edges
        mosi = [0, 0] + [1,1,0,0,1,1,0,0,1,1,0,0,1,1,0,0] + [0]  # bits: 10101010
        miso = [0]*len(cs)
        samples = {0: clk, 1: mosi, 2: miso, 3: cs}
        result = self._decode(samples, 0, 1, 2, 3, mode=0, order="msb", cs_active_low=True)
        self.assertEqual(len(result), 1)
        # Each bit is sampled on rising edge: indices 3,5,7,9,11,13,15,17 → mosi values
        mosi_byte = result[0]["mosi"]
        self.assertIsInstance(mosi_byte, list)
        self.assertEqual(len(mosi_byte), 1)

    def test_lsb_vs_msb(self):
        # 8 bits: 0,0,0,0,0,0,0,1  → MSB=0x01, LSB=0x80
        cs   = [1, 0] + [0]*16 + [1]
        clk  = [0, 0] + [0,1]*8 + [0]
        bits = [0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0]  # values at each sample (rising CLK index)
        mosi = [0, 0] + bits + [0]
        miso = [0]*len(cs)
        samples = {0: clk, 1: mosi, 2: miso, 3: cs}
        res_msb = self._decode(samples, 0, 1, 2, 3, mode=0, order="msb", cs_active_low=True)
        res_lsb = self._decode(samples, 0, 1, 2, 3, mode=0, order="lsb", cs_active_low=True)
        # MSB: first bit is MSB (bit7)
        self.assertNotEqual(res_msb[0]["mosi"], res_lsb[0]["mosi"])

    def test_two_transactions(self):
        # Two back-to-back CS pulses, 8 bits each
        def one_xact(bit_val):
            return [1,0] + [0,bit_val]*8 + [1]
        cs   = one_xact(0)[:-1] + one_xact(0)
        clk  = [0,0] + [0,1]*8 + [0,0] + [0,1]*8 + [0]
        n = len(cs)
        mosi = [0]*n
        miso = [0]*n
        samples = {0: clk, 1: mosi, 2: miso, 3: cs}
        result = self._decode(samples, 0, 1, 2, 3, mode=0, order="msb", cs_active_low=True)
        self.assertEqual(len(result), 2)

    def test_cs_active_high(self):
        # With cs_active_low=False, CS high = asserted
        cs   = [0, 1] + [1]*16 + [0]
        clk  = [0, 0] + [0,1]*8 + [0]
        mosi = [0]*len(cs)
        miso = [0]*len(cs)
        samples = {0: clk, 1: mosi, 2: miso, 3: cs}
        result = self._decode(samples, 0, 1, 2, 3, mode=0, order="msb", cs_active_low=False)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
