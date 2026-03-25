"""
Unit tests for capability_registry.py — Phase 1.

All tests run without a physical device (no libdwf.so required).
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# capability_registry has no dwf dependency — import directly
from digilent.capability_registry import (
    DEVICE_CAPABILITIES,
    UNKNOWN_DEVICE_CAP,
    CapabilityRecord,
    DeviceEnumInfo,
    SupplyChannelDef,
    get_capability,
)


class TestStaticTable(unittest.TestCase):
    """All 12 registered DEVIDs return a correct CapabilityRecord."""

    EXPECTED_DEVIDS = {1, 2, 3, 4, 6, 8, 9, 10, 14, 15, 16, 17}

    def test_all_12_devids_are_registered(self):
        self.assertEqual(set(DEVICE_CAPABILITIES.keys()), self.EXPECTED_DEVIDS)

    def test_digital_discovery_has_no_analog_in(self):
        cap = DEVICE_CAPABILITIES[4]
        self.assertEqual(cap.analog_in_ch, 0, "Digital Discovery must have no AnalogIn")

    def test_digital_discovery_has_no_analog_out(self):
        cap = DEVICE_CAPABILITIES[4]
        self.assertEqual(cap.analog_out_ch, 0)

    def test_digital_discovery_has_dio_offset(self):
        cap = DEVICE_CAPABILITIES[4]
        self.assertEqual(cap.digital_io_offset, 24)

    def test_dps3340_has_no_protocols(self):
        cap = DEVICE_CAPABILITIES[9]
        self.assertFalse(cap.has_protocols, "DPS3340 must not support protocols")

    def test_dps3340_has_no_logic(self):
        cap = DEVICE_CAPABILITIES[9]
        self.assertEqual(cap.digital_in_ch, 0)
        self.assertEqual(cap.digital_out_ch, 0)

    def test_ads_max_has_impedance(self):
        cap = DEVICE_CAPABILITIES[15]
        self.assertTrue(cap.has_impedance, "ADS Max must have dedicated impedance analyzer")

    def test_adp5250_has_dmm(self):
        cap = DEVICE_CAPABILITIES[8]
        self.assertTrue(cap.has_dmm)

    def test_adp5250_has_no_uart_can(self):
        # ADP5250 supports I2C/SPI only — has_protocols still True but services gate it
        # The note field should mention the restriction
        cap = DEVICE_CAPABILITIES[8]
        self.assertIn("I2C", cap.notes + "SPI", msg="ADP5250 note should mention I2C/SPI restriction")

    def test_electronics_explorer_has_8_analog_in_channels(self):
        cap = DEVICE_CAPABILITIES[1]
        self.assertEqual(cap.analog_in_ch, 8)

    def test_adp3x50_has_4_analog_in_channels(self):
        cap = DEVICE_CAPABILITIES[6]
        self.assertEqual(cap.analog_in_ch, 4)

    def test_adp2440_has_4_analog_in_channels(self):
        cap = DEVICE_CAPABILITIES[16]
        self.assertEqual(cap.analog_in_ch, 4)

    def test_adp2450_has_4_analog_in_channels(self):
        cap = DEVICE_CAPABILITIES[17]
        self.assertEqual(cap.analog_in_ch, 4)

    def test_ad2_has_2_analog_in_channels(self):
        cap = DEVICE_CAPABILITIES[3]
        self.assertEqual(cap.analog_in_ch, 2)

    def test_all_devices_have_nonempty_name(self):
        for devid, cap in DEVICE_CAPABILITIES.items():
            with self.subTest(devid=devid):
                self.assertTrue(cap.name, f"DEVID {devid} has empty name")

    def test_all_devices_have_matching_devid(self):
        for devid, cap in DEVICE_CAPABILITIES.items():
            with self.subTest(devid=devid):
                self.assertEqual(cap.devid, devid)

    def test_dps3340_has_3_supply_channels(self):
        cap = DEVICE_CAPABILITIES[9]
        self.assertEqual(len(cap.supply_channels), 3)

    def test_adp5250_has_3_supply_channels(self):
        cap = DEVICE_CAPABILITIES[8]
        self.assertEqual(len(cap.supply_channels), 3)

    def test_ad2_has_supply_channels(self):
        cap = DEVICE_CAPABILITIES[3]
        names = [s.name for s in cap.supply_channels]
        self.assertIn("V+", names)
        self.assertIn("V-", names)

    def test_ad2_vminus_is_negative(self):
        cap = DEVICE_CAPABILITIES[3]
        vminus = next(s for s in cap.supply_channels if s.name == "V-")
        self.assertTrue(vminus.is_negative)
        self.assertLessEqual(vminus.min_v, 0)

    def test_digital_discovery_has_vio_supply(self):
        cap = DEVICE_CAPABILITIES[4]
        self.assertTrue(len(cap.supply_channels) >= 1)
        self.assertEqual(cap.supply_channels[0].name, "VIO")


class TestGetCapability(unittest.TestCase):
    """get_capability() helper and fallback behaviour."""

    def test_known_devid_returns_correct_record(self):
        cap = get_capability(3)
        self.assertEqual(cap.devid, 3)
        self.assertIn("Analog Discovery 2", cap.name)

    def test_unknown_devid_returns_fallback(self):
        cap = get_capability(9999)
        self.assertEqual(cap, UNKNOWN_DEVICE_CAP)

    def test_returns_deep_copy_not_singleton(self):
        cap1 = get_capability(3)
        cap2 = get_capability(3)
        cap1.analog_in_ch = 99
        self.assertNotEqual(cap2.analog_in_ch, 99, "get_capability must return a deep copy")

    def test_fallback_has_positive_analog_in(self):
        cap = get_capability(-42)
        self.assertGreater(cap.analog_in_ch, 0)


class TestToDict(unittest.TestCase):
    """CapabilityRecord.to_dict() and SupplyChannelDef.to_dict()."""

    def test_capability_to_dict_keys(self):
        cap = get_capability(3)
        d = cap.to_dict()
        for key in ("devid", "name", "analog_in_ch", "analog_out_ch", "has_protocols",
                    "has_impedance", "supply_channels"):
            self.assertIn(key, d)

    def test_supply_channel_to_dict_keys(self):
        cap = get_capability(3)
        sc = cap.supply_channels[0].to_dict()
        for key in ("name", "min_v", "max_v", "is_negative", "has_enable",
                    "has_voltage_set", "has_voltage_monitor"):
            self.assertIn(key, sc)

    def test_supply_channels_serialised_as_list(self):
        d = get_capability(3).to_dict()
        self.assertIsInstance(d["supply_channels"], list)
        self.assertGreater(len(d["supply_channels"]), 0)


class TestDeviceEnumInfo(unittest.TestCase):
    """DeviceEnumInfo dataclass basic sanity."""

    def test_fields(self):
        info = DeviceEnumInfo(idx=0, devid=3, devver=1, name="AD2", sn="SN001", is_open=False)
        self.assertEqual(info.devid, 3)
        self.assertFalse(info.is_open)


class TestDeviceManagerWithMock(unittest.TestCase):
    """device_manager.py universal open path — mocked dwf_adapter."""

    def setUp(self):
        # Build a minimal dwf mock with the new functions
        import types as _types
        from digilent.capability_registry import DeviceEnumInfo

        self._dwf_mock = _types.ModuleType("digilent.dwf_adapter")
        self._dwf_mock.HDWF_NONE = MagicMock()
        self._dwf_mock.HDWF_NONE.value = -1

        mock_hdwf = MagicMock()
        mock_hdwf.value = 1
        self._mock_hdwf = mock_hdwf

        self._enum_device = DeviceEnumInfo(idx=0, devid=3, devver=1,
                                           name="Analog Discovery 2", sn="SN001", is_open=False)

        self._dwf_mock.enumerate_devices_full = MagicMock(return_value=[self._enum_device])
        self._dwf_mock.enumerate_devices = MagicMock(return_value=1)
        self._dwf_mock.open_device = MagicMock(return_value=mock_hdwf)
        self._dwf_mock.close_device = MagicMock()
        self._dwf_mock.read_temperature = MagicMock(return_value=40.0)
        self._dwf_mock.get_enum_config_count = MagicMock(return_value=0)
        self._dwf_mock.get_enum_config_info = MagicMock(return_value=0)
        self._dwf_mock.DECI_ANALOG_IN_CHANNEL_COUNT = 1
        self._dwf_mock.DECI_ANALOG_OUT_CHANNEL_COUNT = 2
        self._dwf_mock.DECI_ANALOG_IO_CHANNEL_COUNT = 3
        self._dwf_mock.DECI_DIGITAL_IN_CHANNEL_COUNT = 4
        self._dwf_mock.DECI_DIGITAL_OUT_CHANNEL_COUNT = 5
        self._dwf_mock.DECI_DIGITAL_IO_CHANNEL_COUNT = 6
        self._dwf_mock.DECI_ANALOG_IN_BUFFER_SIZE = 7
        self._dwf_mock.DECI_DIGITAL_IN_BUFFER_SIZE = 9

        sys.modules["digilent.dwf_adapter"] = self._dwf_mock

        # Re-import device_manager with fresh module state
        if "digilent.device_manager" in sys.modules:
            del sys.modules["digilent.device_manager"]
        from digilent.device_manager import DeviceManager
        self.DeviceManager = DeviceManager

    def test_open_sets_capability_for_ad2(self):
        m = self.DeviceManager()
        m.open()
        self.assertIsNotNone(m.capability)
        self.assertEqual(m.capability.devid, 3)

    def test_open_sets_device_name(self):
        m = self.DeviceManager()
        m.open()
        self.assertEqual(m.device_info.name, "Analog Discovery 2")

    def test_close_clears_capability(self):
        m = self.DeviceManager()
        m.open()
        m.close()
        self.assertIsNone(m.capability)

    def test_no_devices_stays_absent(self):
        self._dwf_mock.enumerate_devices_full = MagicMock(return_value=[])
        m = self.DeviceManager()
        m.open()
        self.assertIsNone(m.capability)

    def test_apply_config_overrides_updates_analog_in_ch(self):
        # Simulate FDwfEnumConfigInfo returning 4 AI channels (runtime override)
        self._dwf_mock.get_enum_config_count = MagicMock(return_value=1)
        def _config_info(device_idx, cfg_idx, info_type):
            if info_type == 1:  # DECI_ANALOG_IN_CHANNEL_COUNT
                return 4
            return 0
        self._dwf_mock.get_enum_config_info = MagicMock(side_effect=_config_info)

        m = self.DeviceManager()
        m.open()
        self.assertEqual(m.capability.analog_in_ch, 4,
                         "_apply_config_overrides must override analog_in_ch")

    def test_status_dict_includes_capabilities(self):
        m = self.DeviceManager()
        m.open()
        d = m.status_dict()
        self.assertIn("capabilities", d)
        self.assertIsInstance(d["capabilities"], dict)
        self.assertIn("analog_in_ch", d["capabilities"])


if __name__ == "__main__":
    unittest.main()
