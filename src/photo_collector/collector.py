from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .clients import CollectionError, MediaClient


WINDOWS_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class CollectionConfig:
    output_dir: Path
    reports_dir: Path
    source_root: str = "/sdcard"
    dry_run: bool = False
    limit: int | None = None
    verify_source: bool = False


@dataclass
class CopyRecord:
    run_id: str
    source_type: str
    source_path: str
    original_filename: str
    destination_filename: str | None
    extension: str
    size_bytes: int | None
    sha256: str | None
    duplicate_of: str | None
    source_still_exists: bool | None
    status: str
    error: str | None


@dataclass(frozen=True)
class CollectionSummary:
    run_id: str
    source_type: str
    discovered: int
    copied: int
    failed: int
    duplicates_flagged: int
    total_bytes: int
    scan_warnings: tuple[str, ...]
    dry_run: bool
    output_dir: str
    report_dir: str
    started_at: str
    finished_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(name: str) -> str:
    cleaned = WINDOWS_INVALID_FILENAME.sub("_", name).strip().rstrip(". ")
    return cleaned or "image"


def destination_name(source_path: str, output_dir: Path, reserved: set[str]) -> str:
    original = _safe_filename(Path(source_path).name)
    candidate = original
    key = candidate.casefold()
    if key not in reserved and not (output_dir / candidate).exists():
        reserved.add(key)
        return candidate

    original_path = Path(original)
    path_tag = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:8]
    candidate = f"{original_path.stem}__{path_tag}{original_path.suffix}"
    counter = 2
    while candidate.casefold() in reserved or (output_dir / candidate).exists():
        candidate = (
            f"{original_path.stem}__{path_tag}_{counter}{original_path.suffix}"
        )
        counter += 1
    reserved.add(candidate.casefold())
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PhotoCollector:
    def __init__(self, client: MediaClient, config: CollectionConfig):
        self.client = client
        self.config = config

    def collect(self) -> CollectionSummary:
        started = _utc_now()
        run_id = started.strftime("%Y%m%dT%H%M%SZ")
        output_dir = self.config.output_dir.resolve()
        report_dir = (self.config.reports_dir / run_id).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)

        sources = self.client.list_images(self.config.source_root)
        if self.config.limit is not None:
            sources = sources[: self.config.limit]

        reserved: set[str] = set()
        known_hashes: dict[str, str] = {}
        records: list[CopyRecord] = []

        for index, source_path in enumerate(sources, start=1):
            print(f"[{index}/{len(sources)}] {source_path}")
            filename = destination_name(source_path, output_dir, reserved)
            if self.config.dry_run:
                records.append(
                    CopyRecord(
                        run_id=run_id,
                        source_type=self.client.source_name,
                        source_path=source_path,
                        original_filename=Path(source_path).name,
                        destination_filename=filename,
                        extension=Path(source_path).suffix.lower(),
                        size_bytes=None,
                        sha256=None,
                        duplicate_of=None,
                        source_still_exists=None,
                        status="discovered",
                        error=None,
                    )
                )
                continue

            destination = output_dir / filename
            partial = output_dir / f".{filename}.partial"
            try:
                if partial.exists():
                    partial.unlink()
                self.client.copy_file(source_path, partial)
                if not partial.is_file():
                    raise CollectionError("Copy command completed without creating a file.")
                partial.replace(destination)
                file_hash = sha256_file(destination)
                duplicate_of = known_hashes.get(file_hash)
                if duplicate_of is None:
                    known_hashes[file_hash] = filename
                source_exists = (
                    self.client.source_exists(source_path)
                    if self.config.verify_source
                    else None
                )
                records.append(
                    CopyRecord(
                        run_id=run_id,
                        source_type=self.client.source_name,
                        source_path=source_path,
                        original_filename=Path(source_path).name,
                        destination_filename=filename,
                        extension=Path(source_path).suffix.lower(),
                        size_bytes=destination.stat().st_size,
                        sha256=file_hash,
                        duplicate_of=duplicate_of,
                        source_still_exists=source_exists,
                        status="copied",
                        error=None,
                    )
                )
            except Exception as exc:  # Continue so one bad file does not end the run.
                if partial.exists():
                    partial.unlink()
                records.append(
                    CopyRecord(
                        run_id=run_id,
                        source_type=self.client.source_name,
                        source_path=source_path,
                        original_filename=Path(source_path).name,
                        destination_filename=filename,
                        extension=Path(source_path).suffix.lower(),
                        size_bytes=None,
                        sha256=None,
                        duplicate_of=None,
                        source_still_exists=None,
                        status="failed",
                        error=str(exc),
                    )
                )

        finished = _utc_now()
        copied = sum(record.status == "copied" for record in records)
        failed = sum(record.status == "failed" for record in records)
        duplicate_count = sum(record.duplicate_of is not None for record in records)
        total_bytes = sum(record.size_bytes or 0 for record in records)
        summary = CollectionSummary(
            run_id=run_id,
            source_type=self.client.source_name,
            discovered=len(sources),
            copied=copied,
            failed=failed,
            duplicates_flagged=duplicate_count,
            total_bytes=total_bytes,
            scan_warnings=tuple(getattr(self.client, "scan_warnings", [])),
            dry_run=self.config.dry_run,
            output_dir=str(output_dir),
            report_dir=str(report_dir),
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
        )
        self._write_reports(report_dir, records, summary)
        return summary

    @staticmethod
    def _write_reports(
        report_dir: Path,
        records: list[CopyRecord],
        summary: CollectionSummary,
    ) -> None:
        rows = [asdict(record) for record in records]
        fieldnames = list(CopyRecord.__dataclass_fields__)
        with (report_dir / "manifest.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        with (report_dir / "manifest.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        with (report_dir / "summary.json").open("w", encoding="utf-8") as handle:
            json.dump(asdict(summary), handle, ensure_ascii=False, indent=2)
