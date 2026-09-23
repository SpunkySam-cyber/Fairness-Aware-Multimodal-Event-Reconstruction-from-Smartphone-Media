"""Prepare the files needed to request official COIN dataset access.

The script deliberately does not edit the official licence agreement. Legal and
identity fields must be completed and signed by the appropriate person.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_CSV = PROJECT_DIR / "metadata" / "selected_coin_sources.csv"
OFFICIAL_LICENCE = PROJECT_DIR / "COIN_License_Agreement.docx"
OUTPUT_DIR = PROJECT_DIR / "coin_access_request"


def read_selected_sources() -> list[dict[str, str]]:
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 7:
        raise ValueError(f"Expected 7 selected COIN videos, found {len(rows)}")

    required = {"event_id", "activity_class", "video_id", "video_url", "title"}
    missing = required.difference(rows[0]) if rows else required
    if missing:
        raise ValueError(f"Missing source columns: {', '.join(sorted(missing))}")
    return rows


def write_requested_videos(rows: list[dict[str, str]]) -> None:
    output_path = OUTPUT_DIR / "requested_coin_videos.csv"
    fields = ["event_id", "activity_class", "video_id", "video_url", "title"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)


def write_email(rows: list[dict[str, str]]) -> None:
    video_ids = "\n".join(f"- {row['video_id']} ({row['activity_class']})" for row in rows)
    email = f"""To: tys15@tsinghua.org.cn
Subject: COIN dataset access request for academic event reconstruction research

Dear COIN Dataset Team,

I am working on an academic research project on multimodal event reconstruction from smartphone media under the supervision of [ADVISOR NAME] at [AFFILIATION].

Please find attached the completed and signed COIN licence agreement. For our initial experiment, we require only the following seven COIN source videos rather than the full dataset:

{video_ids}

If providing only these selected files is not possible, please let us know how we can access the official archived dataset.

Thank you.

Kind regards,
[YOUR FULL NAME]
[TITLE OR ROLE]
[AFFILIATION]
[EMAIL ADDRESS]
"""
    (OUTPUT_DIR / "email_to_coin_team.txt").write_text(email, encoding="utf-8")


def write_instructions() -> None:
    instructions = """# COIN Official Access Request

This folder contains the official COIN licence agreement, the seven requested
video IDs, and a ready-to-send email.

## What must be completed manually

1. Open `COIN_License_Agreement.docx`.
2. Complete the user information fields: Name, Title, Affiliation, Address, and Date.
3. Ask the research advisor or an eligible professor at a university or research
   institution to review and sign the agreement. The COIN form specifically
   requires this type of signature.
4. Replace the bracketed placeholders in `email_to_coin_team.txt`.
5. Attach the signed licence and `requested_coin_videos.csv`.
6. Send the request to `tys15@tsinghua.org.cn`.

## Licence restriction

The official agreement permits scientific research use only and prohibits
commercial use and redistribution. Do not place downloaded COIN videos in Git,
public cloud folders, or a shared project archive. Store only derived experiment
metadata that the agreement permits.

## After access is granted

Place the seven authorised source videos in:

`video_event_reconstruction/data/source_videos/`

Then run the clip-extraction and scrambling stage. Keep the filenames or a
manifest that maps each downloaded file to its COIN video ID.
"""
    (OUTPUT_DIR / "README.md").write_text(instructions, encoding="utf-8")


def main() -> None:
    if not OFFICIAL_LICENCE.exists():
        raise FileNotFoundError(f"Official licence not found: {OFFICIAL_LICENCE}")

    rows = read_selected_sources()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OFFICIAL_LICENCE, OUTPUT_DIR / "COIN_License_Agreement.docx")
    write_requested_videos(rows)
    write_email(rows)
    write_instructions()
    print(f"Prepared COIN access package: {OUTPUT_DIR}")
    print(f"Selected source videos: {len(rows)}")


if __name__ == "__main__":
    main()
