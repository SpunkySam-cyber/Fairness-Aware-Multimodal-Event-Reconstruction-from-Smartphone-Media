"""Create standardized visual-only inputs for the frozen 21-clip benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = PROJECT_ROOT / "data" / "experiment_01"
DEFAULT_SOURCE = DEFAULT_EXPERIMENT / "scrambled_clips"
DEFAULT_OUTPUT = DEFAULT_EXPERIMENT / "model_inputs"
EXPECTED_IDS = [f"V{index:03d}" for index in range(1, 22)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    ffmpeg_path = matches[-1]
    ffprobe_path = ffmpeg_path.with_name("ffprobe.exe")
    if not ffprobe_path.exists():
        raise RuntimeError(f"ffprobe is missing beside {ffmpeg_path}")
    return ffmpeg_path, ffprobe_path


def probe_duration(path: Path, ffprobe: Path) -> float:
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


def find_font() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("A font for the persistent clip labels could not be found")


def ffmpeg_font_path(path: Path) -> str:
    return path.as_posix().replace(":", r"\:")


def standardize(
    source: Path, output: Path, blind_id: str, ffmpeg: Path, font: Path
) -> None:
    video_filter = (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,"
        "fps=30,setsar=1,"
        "drawbox=x=18:y=18:w=160:h=58:color=black@0.70:t=fill,"
        f"drawtext=fontfile='{ffmpeg_font_path(font)}':text='{blind_id}':"
        "fontcolor=white:fontsize=34:x=35:y=28"
    )
    subprocess.run(
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
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source_dir = args.source.resolve()
    output_dir = args.output.resolve()
    inputs = [source_dir / f"{blind_id}.mp4" for blind_id in EXPECTED_IDS]
    missing = [path.name for path in inputs if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen clips: {missing}")

    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"Output exists: {output_dir}; use --overwrite to rebuild"
            )
        shutil.rmtree(output_dir)

    individual_dir = output_dir / "individual_visual_only"
    individual_dir.mkdir(parents=True)
    ffmpeg, ffprobe = locate_tools()
    font = find_font()

    manifest_rows: list[dict[str, object]] = []
    timeline_rows: list[dict[str, object]] = []
    cursor = 0.0
    standardized_paths: list[Path] = []

    for index, (blind_id, source) in enumerate(zip(EXPECTED_IDS, inputs), start=1):
        destination = individual_dir / source.name
        print(f"[{index:02d}/21] Standardizing {source.name}")
        standardize(source, destination, blind_id, ffmpeg, font)
        duration = probe_duration(destination, ffprobe)
        standardized_paths.append(destination)
        manifest_rows.append(
            {
                "blind_position": index,
                "blind_id": blind_id,
                "filename": destination.name,
                "duration_seconds": f"{duration:.3f}",
                "file_size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "audio_removed": True,
                "width": 1280,
                "height": 720,
                "fps": 30,
            }
        )
        timeline_rows.append(
            {
                "blind_position": index,
                "blind_id": blind_id,
                "composite_start_seconds": f"{cursor:.3f}",
                "composite_end_seconds": f"{cursor + duration:.3f}",
            }
        )
        cursor += duration

    concat_file = output_dir / "concat_inputs.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in standardized_paths),
        encoding="utf-8",
    )
    composite = output_dir / "all_21_clips_composite_visual_only.mp4"
    subprocess.run(
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
            "-movflags",
            "+faststart",
            str(composite),
        ],
        check=True,
    )
    concat_file.unlink()

    write_csv(
        output_dir / "input_manifest.csv",
        manifest_rows,
        [
            "blind_position",
            "blind_id",
            "filename",
            "duration_seconds",
            "file_size_bytes",
            "sha256",
            "audio_removed",
            "width",
            "height",
            "fps",
        ],
    )
    write_csv(
        output_dir / "composite_timeline.csv",
        timeline_rows,
        [
            "blind_position",
            "blind_id",
            "composite_start_seconds",
            "composite_end_seconds",
        ],
    )
    experiment_manifest = {
        "experiment_id": "experiment_01",
        "condition": "visual_only",
        "blind_order": EXPECTED_IDS,
        "random_seed_from_pilot": 20260913,
        "clip_count": 21,
        "event_count": 7,
        "clips_per_event": 3,
        "standardization": {
            "resolution": "1280x720",
            "fps": 30,
            "video_codec": "H.264",
            "audio": "removed",
            "persistent_clip_id": True,
        },
        "composite": {
            "filename": composite.name,
            "duration_seconds": round(probe_duration(composite, ffprobe), 3),
            "sha256": sha256(composite),
        },
        "source_clip_hashes": {path.name: sha256(path) for path in inputs},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "experiment_manifest.json").write_text(
        json.dumps(experiment_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(experiment_manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

