"""Prepare the full seven-video, two-second reconstruction experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT.parent / "videos"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "experiment_02_two_second"
SEGMENT_SECONDS = 2.0
SHUFFLE_SEED = 20260918
MAX_MODEL_FILE_BYTES = 15_000_000

SOURCES = [
    {
        "event_id": "E01",
        "activity": "AssembleOfficeChair",
        "filename": "ERGOHUMAN BASE mesh - Assembly.mp4",
    },
    {
        "event_id": "E02",
        "activity": "ChangeGuitarStrings",
        "filename": "Palit-Kwerdas (String change).mp4",
    },
    {
        "event_id": "E03",
        "activity": "MakeFrenchFries",
        "filename": "French Fries - How to Make Crispy French Fries.mp4",
    },
    {
        "event_id": "E04",
        "activity": "MakePaperWindMill",
        "filename": "DIY Safe Pinwheels - Pin Free Pinwheels That Really Spin!.mp4",
    },
    {
        "event_id": "E05",
        "activity": "ReplaceDoorKnob",
        "filename": "Install Door Locks - Décor Moulding.mp4",
    },
    {
        "event_id": "E06",
        "activity": "ReplaceMemoryChip",
        "filename": "How to upgrade RAM in your Apple iBook G4.mp4",
    },
    {
        "event_id": "E07",
        "activity": "Sow",
        "filename": "How to Grow a Mango Tree from Seed.mp4",
    },
]


def locate_tools() -> tuple[Path, Path]:
    ffmpeg_command = shutil.which("ffmpeg")
    ffprobe_command = shutil.which("ffprobe")
    if ffmpeg_command and ffprobe_command:
        return Path(ffmpeg_command), Path(ffprobe_command)
    workspace = PROJECT_ROOT.parent.parent
    matches = sorted(
        (workspace / "ffmpeg").glob("ffmpeg-*-essentials_build/bin/ffmpeg.exe")
    )
    if not matches:
        raise RuntimeError("FFmpeg was not found")
    ffmpeg = matches[-1]
    ffprobe = ffmpeg.with_name("ffprobe.exe")
    if not ffprobe.exists():
        raise RuntimeError(f"ffprobe is missing beside {ffmpeg}")
    return ffmpeg, ffprobe


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def duration(path: Path, ffprobe: Path) -> float:
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ass_time(seconds: float) -> str:
    centiseconds = int(round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def ffmpeg_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def standardize_source(source: Path, output: Path, ffmpeg: Path) -> None:
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "scale=640:360:force_original_aspect_ratio=decrease,"
            "pad=640:360:(ow-iw)/2:(oh-ih)/2:black,fps=12,setsar=1",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "24",
            "-keyint_min",
            "24",
            "-sc_threshold",
            "0",
            "-force_key_frames",
            "expr:gte(t,n_forced*2)",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def segment_source(reference: Path, pattern: Path, ffmpeg: Path) -> None:
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(reference),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            "2",
            "-segment_time_delta",
            "0.05",
            "-reset_timestamps",
            "1",
            str(pattern),
        ]
    )


def merge_tiny_tail(event_dir: Path, ffmpeg: Path, ffprobe: Path) -> bool:
    segments = sorted(event_dir.glob("segment_*.mp4"))
    if len(segments) < 2 or duration(segments[-1], ffprobe) >= 0.5:
        return False
    previous, tail = segments[-2], segments[-1]
    concat_file = event_dir / "merge_tail.txt"
    merged = event_dir / "merged_tail.mp4"
    concat_file.write_text(
        f"file '{previous.resolve().as_posix()}'\nfile '{tail.resolve().as_posix()}'\n",
        encoding="utf-8",
    )
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(merged),
        ]
    )
    previous.unlink()
    tail.unlink()
    merged.rename(previous)
    concat_file.unlink()
    return True


def write_ass(path: Path, rows: list[dict[str, Any]]) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ClipID,Arial,34,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,2,0,7,18,18,16,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    cursor = 0.0
    for row in rows:
        start = cursor
        end = cursor + float(row["duration_seconds"])
        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},ClipID,,0,0,0,,{row['blind_id']}\n"
        )
        cursor = end
    path.write_text("".join(lines), encoding="utf-8")


def make_model_composite(
    clean_composite: Path,
    subtitle_file: Path,
    output: Path,
    ffmpeg: Path,
    bitrate_kbps: int,
) -> None:
    video_filter = (
        f"subtitles='{ffmpeg_filter_path(subtitle_file)}',"
        "scale=480:270:force_original_aspect_ratio=decrease,"
        "pad=480:270:(ow-iw)/2:(oh-ih)/2:black,fps=8,setsar=1"
    )
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(clean_composite),
            "-an",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            f"{bitrate_kbps}k",
            "-maxrate",
            f"{bitrate_kbps + 15}k",
            "-bufsize",
            f"{bitrate_kbps * 2}k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def schema(total_clips: int) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Two-second clip reconstruction response",
        "type": "object",
        "additionalProperties": False,
        "required": ["events"],
        "properties": {
            "events": {
                "type": "array",
                "minItems": 7,
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "event_id",
                        "event_description",
                        "ordered_clips",
                        "confidence",
                    ],
                    "properties": {
                        "event_id": {"type": "string", "minLength": 1},
                        "event_description": {"type": "string", "minLength": 1},
                        "ordered_clips": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": total_clips,
                            "items": {"type": "string", "pattern": r"^C\d{4}$"},
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                },
            }
        },
    }


def prompt(total_clips: int) -> str:
    return f"""You are given one silent composite video containing {total_clips} shuffled two-second clips. Each clip has a persistent neutral identifier from C0001 to C{total_clips:04d}.

The clips came from exactly seven original source videos. Reconstruct those seven videos.

Rules:
1. Create exactly seven event groups.
2. Assign every clip ID to exactly one event. Do not omit or repeat a clip.
3. Group sizes are unknown and may differ.
4. Within each event, arrange all assigned clip IDs in chronological order.
5. Infer a short neutral description for each reconstructed event.
6. Use only visible evidence; audio is unavailable.
7. Return only JSON conforming to the supplied schema.

The event IDs are arbitrary and do not need to match hidden reference IDs.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    expected_parent = (PROJECT_ROOT / "data").resolve()
    if output.parent != expected_parent:
        raise ValueError(f"Output must be a direct child of {expected_parent}")
    if output.exists():
        if not args.overwrite:
            raise FileExistsError(f"Output already exists: {output}")
        if output.name != "experiment_02_two_second":
            raise ValueError("Refusing to overwrite an unexpected directory")
        shutil.rmtree(output)

    for source in SOURCES:
        source_path = SOURCE_DIR / source["filename"]
        if not source_path.exists():
            raise FileNotFoundError(source_path)

    ffmpeg, ffprobe = locate_tools()
    references = output / "standardized_references"
    segments = output / "clean_segments_private"
    model_input = output / "model_input"
    protocol = output / "experiment_protocol"
    for directory in (references, segments, model_input, protocol):
        directory.mkdir(parents=True, exist_ok=True)

    source_rows: list[dict[str, Any]] = []
    natural_segments: list[dict[str, Any]] = []
    print("Standardizing seven complete source videos...", flush=True)
    for source_index, source in enumerate(SOURCES, start=1):
        source_path = SOURCE_DIR / source["filename"]
        reference = references / f"{source['event_id']}.mp4"
        print(f"[{source_index}/7] {source['filename']}", flush=True)
        standardize_source(source_path, reference, ffmpeg)
        reference_duration = duration(reference, ffprobe)
        event_dir = segments / source["event_id"]
        event_dir.mkdir()
        segment_source(reference, event_dir / "segment_%04d.mp4", ffmpeg)
        event_segments = sorted(event_dir.glob("segment_*.mp4"))
        expected_count = math.ceil(reference_duration / SEGMENT_SECONDS)
        merged_tail = merge_tiny_tail(event_dir, ffmpeg, ffprobe)
        if merged_tail:
            print(
                f"  Merged a sub-0.5-second tail into the preceding {source['event_id']} clip.",
                flush=True,
            )
        event_segments = sorted(event_dir.glob("segment_*.mp4"))
        allowed_counts = {expected_count, expected_count - 1}
        if len(event_segments) not in allowed_counts:
            raise RuntimeError(
                f"{source['event_id']} produced {len(event_segments)} segments; expected one of {sorted(allowed_counts)}"
            )
        event_cursor = 0.0
        for order, segment in enumerate(event_segments, start=1):
            segment_duration = duration(segment, ffprobe)
            natural_segments.append(
                {
                    "event_id": source["event_id"],
                    "activity": source["activity"],
                    "source_filename": source["filename"],
                    "source_order": order,
                    "source_start_seconds": round(event_cursor, 3),
                    "source_end_seconds": round(
                        min(event_cursor + segment_duration, reference_duration), 3
                    ),
                    "duration_seconds": round(segment_duration, 3),
                    "clean_segment": str(segment.relative_to(output)),
                    "segment_sha256": sha256(segment),
                }
            )
            event_cursor += segment_duration
        source_rows.append(
            {
                **source,
                "source_duration_seconds": round(duration(source_path, ffprobe), 3),
                "standardized_duration_seconds": round(reference_duration, 3),
                "segment_count": len(event_segments),
                "source_sha256": sha256(source_path),
                "reference_sha256": sha256(reference),
            }
        )

    shuffled = list(natural_segments)
    random.Random(SHUFFLE_SEED).shuffle(shuffled)
    for position, row in enumerate(shuffled, start=1):
        row["blind_position"] = position
        row["blind_id"] = f"C{position:04d}"

    concat_list = output / "PRIVATE_scrambled_concat.txt"
    concat_list.write_text(
        "".join(
            f"file '{(output / row['clean_segment']).resolve().as_posix()}'\n"
            for row in shuffled
        ),
        encoding="utf-8",
    )
    clean_composite = output / "PRIVATE_scrambled_clean_composite.mp4"
    print(f"Concatenating {len(shuffled)} shuffled clean clips...", flush=True)
    run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(clean_composite),
        ]
    )

    subtitle_file = output / "PRIVATE_clip_labels.ass"
    write_ass(subtitle_file, shuffled)
    final_composite = model_input / f"scrambled_{len(shuffled)}_clips_labelled.mp4"
    print("Encoding compact labelled model input...", flush=True)
    make_model_composite(clean_composite, subtitle_file, final_composite, ffmpeg, 85)
    if final_composite.stat().st_size > MAX_MODEL_FILE_BYTES:
        print("Model input exceeded 15 MB; retrying at 65 kbps...", flush=True)
        make_model_composite(clean_composite, subtitle_file, final_composite, ffmpeg, 65)
    if final_composite.stat().st_size > MAX_MODEL_FILE_BYTES:
        raise RuntimeError(
            f"Model composite remains too large: {final_composite.stat().st_size} bytes"
        )

    hierarchy = []
    for source in SOURCES:
        event_rows = sorted(
            (row for row in shuffled if row["event_id"] == source["event_id"]),
            key=lambda row: row["source_order"],
        )
        hierarchy.append(
            {
                "event_id": source["event_id"],
                "activity": source["activity"],
                "ordered_clips": [row["blind_id"] for row in event_rows],
            }
        )

    (output / "PRIVATE_answer_key.json").write_text(
        json.dumps(shuffled, indent=2), encoding="utf-8"
    )
    (output / "PRIVATE_expected_hierarchy.json").write_text(
        json.dumps(hierarchy, indent=2), encoding="utf-8"
    )
    safe_manifest = [
        {
            "blind_position": row["blind_position"],
            "blind_id": row["blind_id"],
            "duration_seconds": row["duration_seconds"],
        }
        for row in shuffled
    ]
    (model_input / "blind_manifest.json").write_text(
        json.dumps(safe_manifest, indent=2), encoding="utf-8"
    )
    (protocol / "MODEL_PROMPT.txt").write_text(
        prompt(len(shuffled)), encoding="utf-8"
    )
    (protocol / "model_response.schema.json").write_text(
        json.dumps(schema(len(shuffled)), indent=2), encoding="utf-8"
    )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "segment_seconds": SEGMENT_SECONDS,
        "shuffle_seed": SHUFFLE_SEED,
        "source_video_count": len(SOURCES),
        "total_clip_count": len(shuffled),
        "total_source_duration_seconds": round(
            sum(row["source_duration_seconds"] for row in source_rows), 3
        ),
        "total_segment_duration_seconds": round(
            sum(row["duration_seconds"] for row in shuffled), 3
        ),
        "model_input": {
            "filename": str(final_composite.relative_to(output)),
            "size_bytes": final_composite.stat().st_size,
            "sha256": sha256(final_composite),
            "audio_removed": True,
            "width": 480,
            "height": 270,
            "fps": 8,
        },
        "sources": source_rows,
    }
    (output / "experiment_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
