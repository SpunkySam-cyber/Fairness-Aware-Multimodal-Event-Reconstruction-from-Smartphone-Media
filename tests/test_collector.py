from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from photo_collector.clients import LocalFolderClient
from photo_collector.collector import CollectionConfig, PhotoCollector, destination_name


class CollectorTests(unittest.TestCase):
    def test_collision_name_is_stable_and_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            reserved: set[str] = set()
            first = destination_name("/sdcard/DCIM/photo.jpg", output, reserved)
            second = destination_name("/sdcard/Download/photo.jpg", output, reserved)
            self.assertEqual(first, "photo.jpg")
            self.assertRegex(second, r"^photo__[0-9a-f]{8}\.jpg$")
            self.assertNotEqual(first, second)

    def test_local_collection_flattens_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            phone = root / "phone"
            camera = phone / "DCIM" / "Camera"
            downloads = phone / "Download"
            camera.mkdir(parents=True)
            downloads.mkdir(parents=True)
            camera_photo = camera / "photo.jpg"
            duplicate_photo = downloads / "photo.jpg"
            camera_photo.write_bytes(b"same-image-bytes")
            duplicate_photo.write_bytes(b"same-image-bytes")
            (downloads / "ignore.txt").write_text("not an image", encoding="utf-8")

            output = root / "collected"
            reports = root / "reports"
            summary = PhotoCollector(
                LocalFolderClient(phone),
                CollectionConfig(output_dir=output, reports_dir=reports),
            ).collect()

            self.assertEqual(summary.discovered, 2)
            self.assertEqual(summary.copied, 2)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.duplicates_flagged, 1)
            self.assertTrue(camera_photo.exists())
            self.assertTrue(duplicate_photo.exists())
            self.assertEqual(len(list(output.iterdir())), 2)
            self.assertTrue(all(path.parent == output for path in output.iterdir()))

            report_dir = reports / summary.run_id
            with (report_dir / "manifest.csv").open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(bool(row["duplicate_of"]) for row in rows), 1)

            details = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(details["copied"], 2)


if __name__ == "__main__":
    unittest.main()
