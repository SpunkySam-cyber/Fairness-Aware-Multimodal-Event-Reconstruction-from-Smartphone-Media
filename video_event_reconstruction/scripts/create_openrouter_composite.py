"""Create a compact 720p composite below OpenRouter's Google payload limit."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = PROJECT_ROOT / "data" / "experiment_01" / "model_inputs"
SOURCE = INPUT_ROOT / "all_21_clips_composite_visual_only.mp4"
OUTPUT = INPUT_ROOT / "all_21_clips_composite_openrouter_visual_only.mp4"
MANIFEST = INPUT_ROOT / "openrouter_composite_manifest.json"
MAX_RAW_BYTES = 14_500_000


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
    ffmpeg = matches[-1]
    ffprobe = ffmpeg.with_name("ffprobe.exe")
    if not ffprobe.exists():
        raise RuntimeError(f"ffprobe is missing beside {ffmpeg}")
    return ffmpeg, ffprobe


def probe(path: Path, ffprobe: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if OUTPUT.exists() or MANIFEST.exists():
        raise FileExistsError("Compact composite already exists; it was not overwritten")
    ffmpeg, ffprobe = locate_tools()
    subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(SOURCE),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            "700k",
            "-maxrate",
            "900k",
            "-bufsize",
            "1800k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ],
        check=True,
    )
    if OUTPUT.stat().st_size > MAX_RAW_BYTES:
        raise RuntimeError(
            f"Compact file is still too large: {OUTPUT.stat().st_size} bytes"
        )
    details = {
        "purpose": "OpenRouter transport copy below the Google provider payload limit",
        "source_filename": SOURCE.name,
        "source_sha256": sha256(SOURCE),
        "filename": OUTPUT.name,
        "sha256": sha256(OUTPUT),
        "file_size_bytes": OUTPUT.stat().st_size,
        "estimated_base64_bytes": int(OUTPUT.stat().st_size * 4 / 3),
        "maximum_raw_bytes": MAX_RAW_BYTES,
        "video_settings": {
            "resolution": "1280x720 unchanged",
            "frame_rate": "30 fps unchanged",
            "audio": "absent",
            "codec": "H.264",
            "target_bitrate": "700 kbps",
            "maximum_bitrate": "900 kbps",
        },
        "probe": probe(OUTPUT, ffprobe),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST.write_text(json.dumps(details, indent=2), encoding="utf-8")
    print(json.dumps(details, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

