"""Build a reproducible 21-clip blind COIN event-reconstruction pilot.

Seven complete source videos are preserved unchanged. Three annotated steps are
cut from each source, shuffled with a fixed seed, and renamed so that neither
the event identity nor the correct order is visible to the evaluated model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT.parent / "videos"
DEFAULT_SOURCES = PROJECT_ROOT / "metadata" / "selected_coin_sources.csv"
DEFAULT_CLIPS = PROJECT_ROOT / "metadata" / "selected_coin_clips.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "experiment_01"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}


def canonical_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_ffmpeg_tools() -> tuple[Path, Path]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return Path(ffmpeg), Path(ffprobe)

    workspace = PROJECT_ROOT.parent.parent
    ffmpeg_matches = sorted(
        (workspace / "ffmpeg").glob("ffmpeg-*-essentials_build/bin/ffmpeg.exe")
    )
    if not ffmpeg_matches:
        raise RuntimeError("FFmpeg could not be located")
    selected_ffmpeg = ffmpeg_matches[-1]
    selected_ffprobe = selected_ffmpeg.with_name("ffprobe.exe")
    if not selected_ffprobe.exists():
        raise RuntimeError(f"ffprobe is missing beside {selected_ffmpeg}")
    return selected_ffmpeg, selected_ffprobe


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def match_source_files(
    sources: list[dict[str, str]], input_dir: Path
) -> dict[str, Path]:
    available = [
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    by_name: dict[str, list[Path]] = {}
    for path in available:
        by_name.setdefault(canonical_name(path.stem), []).append(path)

    matched: dict[str, Path] = {}
    for source in sources:
        candidates = by_name.get(canonical_name(source["title"]), [])
        if len(candidates) != 1:
            names = ", ".join(path.name for path in candidates) or "none"
            raise RuntimeError(
                f"Expected one file for {source['event_id']} ({source['title']}), "
                f"found: {names}"
            )
        matched[source["event_id"]] = candidates[0]
    return matched


def probe_duration(path: Path, ffprobe: Path) -> float:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def extract_clip(
    source: Path,
    destination: Path,
    start_seconds: float,
    end_seconds: float,
    ffmpeg: Path,
) -> None:
    duration = end_seconds - start_seconds
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_inputs(
    sources: list[dict[str, str]], clips: list[dict[str, str]]
) -> None:
    if len(sources) != 7:
        raise ValueError(f"Expected 7 sources, found {len(sources)}")
    if len(clips) != 21:
        raise ValueError(f"Expected 21 clip annotations, found {len(clips)}")

    source_ids = {source["event_id"] for source in sources}
    clip_ids = {clip["clip_id"] for clip in clips}
    if len(clip_ids) != 21:
        raise ValueError("Clip IDs are not unique")

    for event_id in source_ids:
        event_clips = [clip for clip in clips if clip["event_id"] == event_id]
        orders = sorted(int(clip["true_order"]) for clip in event_clips)
        if len(event_clips) != 3 or orders != [1, 2, 3]:
            raise ValueError(
                f"{event_id} must have exactly three clips ordered 1, 2, 3"
            )

    unknown_events = {clip["event_id"] for clip in clips}.difference(source_ids)
    if unknown_events:
        raise ValueError(f"Clips reference unknown events: {sorted(unknown_events)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--clips", type=Path, default=DEFAULT_CLIPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing experiment output directory.",
    )
    args = parser.parse_args()

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input video folder not found: {input_dir}")
    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"Output already exists: {output_dir}. Use --overwrite to rebuild it."
            )
        shutil.rmtree(output_dir)

    sources = read_csv(args.sources)
    clips = read_csv(args.clips)
    validate_inputs(sources, clips)
    source_by_event = {source["event_id"]: source for source in sources}
    source_files = match_source_files(sources, input_dir)
    ffmpeg, ffprobe = locate_ffmpeg_tools()

    # Confirm each annotation ends within its source video.
    source_durations = {
        event_id: probe_duration(path, ffprobe)
        for event_id, path in source_files.items()
    }
    for clip in clips:
        start = float(clip["start_seconds"])
        end = float(clip["end_seconds"])
        if start < 0 or end <= start:
            raise ValueError(f"Invalid interval for {clip['clip_id']}: {start}-{end}")
        if end > source_durations[clip["event_id"]] + 0.1:
            raise ValueError(f"{clip['clip_id']} extends beyond its source video")

    shuffled = list(clips)
    random.Random(args.seed).shuffle(shuffled)
    clip_dir = output_dir / "scrambled_clips"
    clip_dir.mkdir(parents=True)

    blind_rows: list[dict[str, object]] = []
    answer_rows: list[dict[str, object]] = []
    for position, clip in enumerate(shuffled, start=1):
        blind_id = f"V{position:03d}"
        filename = f"{blind_id}.mp4"
        destination = clip_dir / filename
        start = float(clip["start_seconds"])
        end = float(clip["end_seconds"])
        source_file = source_files[clip["event_id"]]
        print(f"[{position:02d}/21] Creating {filename}")
        extract_clip(source_file, destination, start, end, ffmpeg)
        actual_duration = probe_duration(destination, ffprobe)
        expected_duration = end - start
        if abs(actual_duration - expected_duration) > 0.25:
            raise RuntimeError(
                f"Duration check failed for {filename}: expected {expected_duration}, "
                f"found {actual_duration}"
            )
        digest = sha256(destination)
        blind_rows.append(
            {
                "blind_position": position,
                "blind_id": blind_id,
                "filename": filename,
                "duration_seconds": f"{actual_duration:.3f}",
                "file_size_bytes": destination.stat().st_size,
                "sha256": digest,
            }
        )
        source = source_by_event[clip["event_id"]]
        answer_rows.append(
            {
                **blind_rows[-1],
                "event_id": clip["event_id"],
                "activity_class": source["activity_class"],
                "source_video_id": source["video_id"],
                "source_filename": source_file.name,
                "true_order": int(clip["true_order"]),
                "step_label": clip["step_label"],
                "start_seconds": f"{start:.3f}",
                "end_seconds": f"{end:.3f}",
            }
        )

    blind_fields = [
        "blind_position",
        "blind_id",
        "filename",
        "duration_seconds",
        "file_size_bytes",
        "sha256",
    ]
    answer_fields = blind_fields + [
        "event_id",
        "activity_class",
        "source_video_id",
        "source_filename",
        "true_order",
        "step_label",
        "start_seconds",
        "end_seconds",
    ]
    write_csv(output_dir / "blind_manifest.csv", blind_rows, blind_fields)
    write_csv(output_dir / "PRIVATE_answer_key.csv", answer_rows, answer_fields)

    groups: dict[str, list[dict[str, object]]] = {}
    for row in answer_rows:
        groups.setdefault(str(row["event_id"]), []).append(row)
    hierarchy = []
    for event_id in sorted(groups):
        ordered = sorted(groups[event_id], key=lambda row: int(row["true_order"]))
        hierarchy.append(
            {
                "event_id": event_id,
                "activity_class": ordered[0]["activity_class"],
                "correct_sequence": [
                    {
                        "blind_id": row["blind_id"],
                        "order": row["true_order"],
                        "step": row["step_label"],
                    }
                    for row in ordered
                ],
            }
        )
    (output_dir / "PRIVATE_expected_hierarchy.json").write_text(
        json.dumps(hierarchy, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary = {
        "dataset": "COIN",
        "experiment_id": "experiment_01",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": args.seed,
        "source_video_count": len(sources),
        "event_count": len(sources),
        "clips_per_event": 3,
        "final_clip_count": len(blind_rows),
        "source_videos_preserved": True,
        "model_input": "scrambled_clips plus blind_manifest.csv",
        "private_files": [
            "PRIVATE_answer_key.csv",
            "PRIVATE_expected_hierarchy.json",
        ],
    }
    (output_dir / "build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"Created {len(blind_rows)} scrambled clips in {clip_dir}")
    print(f"Blind manifest: {output_dir / 'blind_manifest.csv'}")
    print(f"Private answer key: {output_dir / 'PRIVATE_answer_key.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
