"""
Unit tests for capability_registry.py.

Phase 1 will populate these tests fully (≥20 tests).
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest
from digilent.capability_registry import DEVICE_CAPABILITIES, UNKNOWN_DEVICE_CAP, get_capability


class TestCapabilityRegistryStub(unittest.TestCase):
    def test_get_capability_unknown_devid_returns_fallback(self):
        cap = get_capability(9999)
        self.assertEqual(cap, UNKNOWN_DEVICE_CAP)

    def test_unknown_cap_has_name(self):
        self.assertIn("Unknown", UNKNOWN_DEVICE_CAP.name)

    def test_device_capabilities_is_dict(self):
        self.assertIsInstance(DEVICE_CAPABILITIES, dict)


if __name__ == "__main__":
    unittest.main()
