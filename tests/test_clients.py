from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from photo_collector.clients import is_image_path, parse_adb_devices


class ClientTests(unittest.TestCase):
    def test_parse_adb_devices(self) -> None:
        output = """List of devices attached
ABC123 device product:test model:Phone transport_id:1
XYZ789 unauthorized usb:1-2 transport_id:2

"""
        devices = parse_adb_devices(output)
        self.assertEqual([device.serial for device in devices], ["ABC123", "XYZ789"])
        self.assertEqual(devices[0].state, "device")
        self.assertEqual(devices[1].state, "unauthorized")

    def test_image_extensions_are_case_insensitive(self) -> None:
        self.assertTrue(is_image_path("/sdcard/DCIM/PHOTO.JPG"))
        self.assertTrue(is_image_path("/sdcard/Download/photo.heic"))
        self.assertFalse(is_image_path("/sdcard/Download/notes.pdf"))


if __name__ == "__main__":
    unittest.main()
