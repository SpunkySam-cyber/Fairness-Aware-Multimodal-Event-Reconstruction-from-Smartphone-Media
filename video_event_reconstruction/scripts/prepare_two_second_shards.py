"""Split the 509-clip shuffled experiment into ten labelled model-input videos.

The clip identities and global shuffle order are unchanged.  Sharding only avoids
sending one long inline video to providers that reject significant-duration
inline media.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from prepare_two_second_reconstruction import (
    PROJECT_ROOT,
    ffmpeg_filter_path,
    locate_tools,
    run,
    write_ass,
)


EXPERIMENT = PROJECT_ROOT / "data" / "experiment_02_two_second"
ANSWER_KEY = EXPERIMENT / "PRIVATE_answer_key.json"
OUTPUT = EXPERIMENT / "model_input" / "shards_10"
SHARD_COUNT = 10


def make_shard(rows: list[dict], index: int, ffmpeg: Path) -> dict:
    stem = f"scrambled_part_{index:02d}_of_{SHARD_COUNT:02d}"
    concat_file = OUTPUT / f"PRIVATE_{stem}_concat.txt"
    clean_file = OUTPUT / f"PRIVATE_{stem}_clean.mp4"
    subtitle_file = OUTPUT / f"PRIVATE_{stem}_labels.ass"
    model_file = OUTPUT / f"{stem}_labelled.mp4"

    concat_file.write_text(
        "".join(
            f"file '{(EXPERIMENT / row['clean_segment']).resolve().as_posix()}'\n"
            for row in rows
        ),
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
            str(clean_file),
        ]
    )
    write_ass(subtitle_file, rows)
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
            str(clean_file),
            "-an",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            "85k",
            "-maxrate",
            "100k",
            "-bufsize",
            "170k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(model_file),
        ]
    )
    clean_file.unlink()
    concat_file.unlink()
    subtitle_file.unlink()
    return {
        "part": index,
        "filename": model_file.name,
        "clip_count": len(rows),
        "first_blind_position": rows[0]["blind_position"],
        "last_blind_position": rows[-1]["blind_position"],
        "first_clip_id": rows[0]["blind_id"],
        "last_clip_id": rows[-1]["blind_id"],
        "duration_seconds": round(sum(float(row["duration_seconds"]) for row in rows), 3),
        "size_bytes": model_file.stat().st_size,
    }


def main() -> int:
    if not ANSWER_KEY.exists():
        raise FileNotFoundError(ANSWER_KEY)
    rows = sorted(
        json.loads(ANSWER_KEY.read_text(encoding="utf-8-sig")),
        key=lambda row: row["blind_position"],
    )
    if len(rows) != 509:
        raise RuntimeError(f"Expected 509 clips, found {len(rows)}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    ffmpeg, _ = locate_tools()

    base, remainder = divmod(len(rows), SHARD_COUNT)
    manifest = []
    cursor = 0
    for index in range(1, SHARD_COUNT + 1):
        size = base + (1 if index <= remainder else 0)
        shard_rows = rows[cursor : cursor + size]
        cursor += size
        print(f"[{index}/{SHARD_COUNT}] Encoding {len(shard_rows)} clips...", flush=True)
        manifest.append(make_shard(shard_rows, index, ffmpeg))

    result = {
        "purpose": "transport-only sharding of one globally shuffled sequence",
        "clip_duration_seconds": 2,
        "clip_count": len(rows),
        "part_count": SHARD_COUNT,
        "all_clip_ids_present_once": len(
            {row["blind_id"] for row in rows}
        ) == len(rows),
        "parts": manifest,
        "total_size_bytes": sum(part["size_bytes"] for part in manifest),
    }
    (OUTPUT / "shard_manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
