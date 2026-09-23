from __future__ import annotations

import argparse
import json
from pathlib import Path

from .clients import AdbClient, CollectionError, LocalFolderClient
from .collector import CollectionConfig, PhotoCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy images from accessible Android storage into one laptop folder "
            "without deleting phone files."
        )
    )
    parser.add_argument("--output", type=Path, default=Path("collected_photos"))
    parser.add_argument("--reports", type=Path, default=Path("run_reports"))
    parser.add_argument("--adb-path", help="Path to adb.exe; otherwise PATH or ADB_PATH is used.")
    parser.add_argument("--serial", help="ADB serial when multiple devices are connected.")
    parser.add_argument("--source-root", default="/sdcard")
    parser.add_argument(
        "--local-source",
        type=Path,
        help="Use a local folder to test the complete flow without an Android phone.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inventory images without copying.")
    parser.add_argument("--limit", type=int, help="Process only the first N images.")
    parser.add_argument(
        "--verify-source",
        action="store_true",
        help="Confirm every phone file remains after copying; slower for large collections.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    try:
        if args.local_source:
            client = LocalFolderClient(args.local_source)
            source_label = str(args.local_source.resolve())
        else:
            client = AdbClient(adb_path=args.adb_path, serial=args.serial)
            device = client.select_device()
            source_label = f"Android device {device.serial}"

        print(f"Source: {source_label}")
        print(f"Destination: {args.output.resolve()}")
        print("Mode: inventory only" if args.dry_run else "Mode: copy; originals remain in place")

        collector = PhotoCollector(
            client,
            CollectionConfig(
                output_dir=args.output,
                reports_dir=args.reports,
                source_root=args.source_root,
                dry_run=args.dry_run,
                limit=args.limit,
                verify_source=args.verify_source,
            ),
        )
        summary = collector.collect()
        print(json.dumps(summary.__dict__, indent=2))
        return 0 if summary.failed == 0 else 2
    except CollectionError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
