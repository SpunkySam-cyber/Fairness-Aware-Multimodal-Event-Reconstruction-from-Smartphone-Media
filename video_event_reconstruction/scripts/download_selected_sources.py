"""Download only the seven COIN source videos selected for the pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = PROJECT_ROOT / "metadata" / "selected_coin_sources.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "source_videos"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "downloaded_sources_manifest.csv"


def locate_ffmpeg() -> Path | None:
    installed = shutil.which("ffmpeg")
    if installed:
        return Path(installed).parent

    workspace = PROJECT_ROOT.parent.parent
    matches = sorted((workspace / "ffmpeg").glob("ffmpeg-*-essentials_build/bin/ffmpeg.exe"))
    return matches[-1].parent if matches else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_video(path: Path, ffmpeg_dir: Path | None) -> dict[str, str]:
    ffprobe = (ffmpeg_dir / "ffprobe.exe") if ffmpeg_dir else Path(shutil.which("ffprobe") or "ffprobe")
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration:stream=width,height,codec_name",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    stream = payload.get("streams", [{}])[0]
    return {
        "actual_duration_seconds": f"{float(payload['format']['duration']):.3f}",
        "width": str(stream.get("width", "")),
        "height": str(stream.get("height", "")),
        "video_codec": str(stream.get("codec_name", "")),
    }


def download(row: dict[str, str], output_dir: Path, ffmpeg_dir: Path | None) -> Path:
    stem = f"{row['event_id']}_{row['video_id']}"
    existing = sorted(output_dir.glob(f"{stem}.*"))
    if existing:
        print(f"[{row['event_id']}] already present: {existing[0].name}")
        return existing[0]

    yt_dlp = shutil.which("yt-dlp")
    if not yt_dlp:
        raise RuntimeError("yt-dlp is not installed or not on PATH")
    node = shutil.which("node")

    command = [
        yt_dlp,
        "--no-playlist",
        "--continue",
        "--format",
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[height<=720]",
        "--merge-output-format",
        "mp4",
        "--output",
        str(output_dir / f"{stem}.%(ext)s"),
    ]
    if node:
        command.extend(["--js-runtimes", f"node:{node}"])
    if ffmpeg_dir:
        command.extend(["--ffmpeg-location", str(ffmpeg_dir)])
    command.append(row["video_url"])

    print(f"[{row['event_id']}] downloading {row['activity_class']}...")
    subprocess.run(command, check=True)

    downloaded = sorted(output_dir.glob(f"{stem}.*"))
    if len(downloaded) != 1:
        raise RuntimeError(f"Expected one output for {stem}, found {len(downloaded)}")
    return downloaded[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_dir = locate_ffmpeg()
    if not ffmpeg_dir:
        raise RuntimeError("FFmpeg/ffprobe could not be located")

    with args.sources.open(newline="", encoding="utf-8-sig") as handle:
        sources = list(csv.DictReader(handle))

    manifest_rows: list[dict[str, str]] = []
    for row in sources:
        path = download(row, args.output, ffmpeg_dir)
        details = probe_video(path, ffmpeg_dir)
        manifest_rows.append(
            {
                **row,
                "local_path": str(path.resolve()),
                "file_size_bytes": str(path.stat().st_size),
                "sha256": sha256(path),
                **details,
            }
        )

    fieldnames = list(manifest_rows[0])
    with args.manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    total_bytes = sum(int(row["file_size_bytes"]) for row in manifest_rows)
    print(f"Downloaded and verified {len(manifest_rows)} videos ({total_bytes / 1024 / 1024:.1f} MiB).")
    print(f"Manifest: {args.manifest.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
