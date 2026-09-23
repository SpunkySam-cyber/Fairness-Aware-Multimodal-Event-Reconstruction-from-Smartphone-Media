"""Create a labelled middle-frame contact sheet for blind clip QA."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT = PROJECT_ROOT / "data" / "experiment_01"


def locate_ffmpeg() -> Path:
    installed = shutil.which("ffmpeg")
    if installed:
        return Path(installed)
    workspace = PROJECT_ROOT.parent.parent
    matches = sorted(
        (workspace / "ffmpeg").glob("ffmpeg-*-essentials_build/bin/ffmpeg.exe")
    )
    if not matches:
        raise RuntimeError("FFmpeg could not be located")
    return matches[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=DEFAULT_EXPERIMENT)
    args = parser.parse_args()

    experiment = args.experiment.resolve()
    manifest_path = experiment / "blind_manifest.csv"
    clip_dir = experiment / "scrambled_clips"
    output_path = experiment / "QA_contact_sheet.jpg"
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 21:
        raise ValueError(f"Expected 21 manifest rows, found {len(rows)}")

    ffmpeg = locate_ffmpeg()
    cell_width, cell_height = 320, 210
    columns, rows_count = 4, 6
    sheet = Image.new(
        "RGB", (columns * cell_width, rows_count * cell_height), "#111111"
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)

    with tempfile.TemporaryDirectory(prefix="coin_clip_qa_") as temp_dir:
        temp = Path(temp_dir)
        for index, row in enumerate(rows):
            clip = clip_dir / row["filename"]
            frame = temp / f"{row['blind_id']}.jpg"
            midpoint = float(row["duration_seconds"]) / 2
            subprocess.run(
                [
                    str(ffmpeg),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{midpoint:.3f}",
                    "-i",
                    str(clip),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    "-y",
                    str(frame),
                ],
                check=True,
            )
            with Image.open(frame) as source:
                image = source.convert("RGB")
                image.thumbnail((cell_width, cell_height - 30), Image.Resampling.LANCZOS)
                x = (index % columns) * cell_width
                y = (index // columns) * cell_height
                paste_x = x + (cell_width - image.width) // 2
                paste_y = y + 28 + (cell_height - 30 - image.height) // 2
                sheet.paste(image, (paste_x, paste_y))
                draw.text((x + 8, y + 5), row["blind_id"], fill="white", font=font)

    sheet.save(output_path, quality=92)
    print(f"Contact sheet: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
