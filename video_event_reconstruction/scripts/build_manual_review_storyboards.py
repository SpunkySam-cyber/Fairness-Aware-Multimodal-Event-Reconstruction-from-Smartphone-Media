"""Build event storyboards for blinded qualitative review of model evidence."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "data" / "experiment_01"
VIDEO_DIR = EXPERIMENT / "model_inputs" / "individual_visual_only"
OUTPUT_DIR = (
    ROOT
    / "research"
    / "outputs"
    / "model_benchmark_20260914"
    / "manual_review_storyboards"
)
SAMPLE_POSITIONS = (0.08, 0.29, 0.50, 0.71, 0.92)
FRAME_WIDTH = 300
FRAME_HEIGHT = 169
LABEL_HEIGHT = 54


def font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def sampled_frames(path: Path) -> list[Image.Image]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {path}")
    frame_count = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
    frames: list[Image.Image] = []
    for fraction in SAMPLE_POSITIONS:
        index = min(round((frame_count - 1) * fraction), frame_count - 1)
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot read frame {index} from {path}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)
        image.thumbnail((FRAME_WIDTH, FRAME_HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), "black")
        canvas.paste(
            image,
            ((FRAME_WIDTH - image.width) // 2, (FRAME_HEIGHT - image.height) // 2),
        )
        frames.append(canvas)
    capture.release()
    return frames


def main() -> int:
    hierarchy = json.loads(
        (EXPERIMENT / "PRIVATE_expected_hierarchy.json").read_text(encoding="utf-8")
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title_font = font(25)
    label_font = font(18)
    for event in hierarchy:
        rows = event["correct_sequence"]
        width = FRAME_WIDTH * len(SAMPLE_POSITIONS)
        height = 52 + len(rows) * (LABEL_HEIGHT + FRAME_HEIGHT)
        sheet = Image.new("RGB", (width, height), "#111111")
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (12, 10),
            f"{event['event_id']} — {event['activity_class']}",
            fill="white",
            font=title_font,
        )
        y = 52
        for step in rows:
            draw.rectangle((0, y, width, y + LABEL_HEIGHT), fill="#263238")
            draw.text(
                (12, y + 7),
                f"Order {step['order']} · {step['blind_id']} · {step['step']}",
                fill="white",
                font=label_font,
            )
            y += LABEL_HEIGHT
            for column, frame in enumerate(
                sampled_frames(VIDEO_DIR / f"{step['blind_id']}.mp4")
            ):
                sheet.paste(frame, (column * FRAME_WIDTH, y))
            y += FRAME_HEIGHT
        output = OUTPUT_DIR / f"{event['event_id']}_{event['activity_class']}.jpg"
        sheet.save(output, quality=92)
        print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
