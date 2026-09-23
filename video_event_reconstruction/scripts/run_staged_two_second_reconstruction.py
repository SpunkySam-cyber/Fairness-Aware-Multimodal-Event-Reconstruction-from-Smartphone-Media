"""Run staged Gemini classification and reconstruction for the 509-clip dataset."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_two_second_reconstruction import (
    API_URL,
    PROJECT_ROOT,
    extract_content,
    load_dotenv,
    request,
)


EXPERIMENT = PROJECT_ROOT / "data" / "experiment_02_two_second"
SHARD_DIR = EXPERIMENT / "model_input" / "shards_10"
SHARD_MANIFEST = SHARD_DIR / "shard_manifest.json"
BLIND_MANIFEST = EXPERIMENT / "model_input" / "blind_manifest.json"
OUTPUT = EXPERIMENT / "model_runs" / "staged-gemini-flash" / "run_01"
EVALUATOR = PROJECT_ROOT / "scripts" / "evaluate_two_second_response.py"
MODEL_ID = "google/gemini-3.8-flash"

EVENTS = {
    "office_chair_assembly": "assembling an office chair",
    "guitar_string_change": "changing strings on a guitar",
    "french_fries_preparation": "preparing and cooking French fries",
    "paper_pinwheel_craft": "making a paper pinwheel",
    "door_knob_installation": "installing or replacing a door knob",
    "laptop_ram_upgrade": "upgrading RAM in a laptop",
    "mango_seed_planting": "preparing and planting a mango seed",
}


def encoded_video(path: Path) -> str:
    return "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode(
        "ascii"
    )


def schema(expected_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["assignments"],
        "properties": {
            "assignments": {
                "type": "array",
                "minItems": len(expected_ids),
                "maxItems": len(expected_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "clip_id",
                        "event_label",
                        "source_progress",
                        "confidence",
                    ],
                    "properties": {
                        "clip_id": {"type": "string", "enum": expected_ids},
                        "event_label": {
                            "type": "string",
                            "enum": list(EVENTS),
                        },
                        "source_progress": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 1000,
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


def prompt(part: int, expected_ids: list[str]) -> str:
    category_lines = "\n".join(
        f"- {label}: {description}" for label, description in EVENTS.items()
    )
    return f"""You are processing part {part} of 10 from a larger event-reconstruction experiment.

This silent video contains {len(expected_ids)} shuffled clips. Every clip lasts approximately two seconds and displays a persistent ID. Classify every visible clip into exactly one of the seven event categories below, then estimate where it belongs in that event's original timeline.

Categories:
{category_lines}

Required clip IDs in this part:
{", ".join(expected_ids)}

For source_progress, use an integer from 0 (very beginning of the original event) to 1000 (very end). Use visual state and action progression, not the clip ID or its position in this shuffled part. Consecutive moments should receive nearby but distinguishable progress values. Include every required ID exactly once and do not invent IDs. Return only schema-conforming JSON.

Return one JSON object with this exact shape:
{{"assignments":[{{"clip_id":"C0001","event_label":"one category label listed above","source_progress":0,"confidence":0.0}}]}}
The example values are placeholders. Every assignment must contain exactly those four fields, and confidence must be between 0 and 1.
"""


def payload(path: Path, part: int, expected_ids: list[str], max_tokens: int) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt(part, expected_ids)},
                    {
                        "type": "video_url",
                        "video_url": {"url": encoded_video(path)},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning": {"effort": "low", "exclude": True},
        # The Google route rejects the 51-ID enum schema as INVALID_ARGUMENT.
        # Request JSON mode and enforce the stronger constraints locally instead.
        "response_format": {"type": "json_object"},
        "provider": {"require_parameters": True},
    }


def validate_assignments(data: dict, expected_ids: list[str]) -> list[dict]:
    assignments = data.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("Response does not contain an assignments array")
    ids = [row.get("clip_id") for row in assignments if isinstance(row, dict)]
    if len(assignments) != len(expected_ids):
        raise ValueError(
            f"Expected {len(expected_ids)} assignments, received {len(assignments)}"
        )
    if len(set(ids)) != len(ids):
        raise ValueError("Response contains duplicate clip IDs")
    if set(ids) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(ids))
        unexpected = sorted(set(ids) - set(expected_ids))
        raise ValueError(f"ID mismatch; missing={missing}, unexpected={unexpected}")
    for row in assignments:
        if row.get("event_label") not in EVENTS:
            raise ValueError(f"Unexpected event label: {row.get('event_label')}")
        progress = row.get("source_progress")
        if not isinstance(progress, int) or not 0 <= progress <= 1000:
            raise ValueError(f"Invalid source progress: {progress}")
    return assignments


def normalize_response(data: Any) -> dict:
    """Normalize harmless JSON-mode variations before strict local validation."""
    assignments = data if isinstance(data, list) else data.get("assignments")
    if not isinstance(assignments, list):
        return data
    normalized = []
    for raw in assignments:
        row = dict(raw)
        if "event_label" not in row and "category" in row:
            row["event_label"] = row.pop("category")
        if "confidence" not in row:
            row["confidence"] = 0.5
        normalized.append(
            {
                "clip_id": row.get("clip_id"),
                "event_label": row.get("event_label"),
                "source_progress": row.get("source_progress"),
                "confidence": row.get("confidence"),
            }
        )
    return {"assignments": normalized}


def expected_ids_by_part() -> dict[int, list[str]]:
    manifest = json.loads(SHARD_MANIFEST.read_text(encoding="utf-8-sig"))
    result = {}
    for row in manifest["parts"]:
        result[int(row["part"])] = [
            f"C{position:04d}"
            for position in range(
                int(row["first_blind_position"]),
                int(row["last_blind_position"]) + 1,
            )
        ]
    return result


def run_part(
    part: int,
    path: Path,
    expected_ids: list[str],
    key: str,
    max_tokens: int,
) -> None:
    part_dir = OUTPUT / f"part_{part:02d}"
    if (part_dir / "assignments.json").exists():
        saved = json.loads(
            (part_dir / "assignments.json").read_text(encoding="utf-8-sig")
        )
        validate_assignments(saved, expected_ids)
        print(f"[{part}/10] Existing validated result; skipping API call.", flush=True)
        return
    if (part_dir / "raw_api_response.json").exists():
        response = json.loads(
            (part_dir / "raw_api_response.json").read_text(encoding="utf-8-sig")
        )
        parsed = normalize_response(json.loads(extract_content(response)))
        validate_assignments(parsed, expected_ids)
        (part_dir / "assignments.json").write_text(
            json.dumps(parsed, indent=2), encoding="utf-8"
        )
        summary = {
            "recovered_locally": True,
            "generation_id": response.get("id"),
            "served_model": response.get("model"),
            "provider": response.get("provider"),
            "usage": response.get("usage", {}),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (part_dir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(f"[{part}/10] Recovered and validated existing API response.", flush=True)
        return
    if part_dir.exists():
        raise FileExistsError(
            f"Incomplete prior part directory requires inspection: {part_dir}"
        )
    part_dir.mkdir(parents=True)
    request_manifest = {
        "model": MODEL_ID,
        "part": part,
        "input_file": str(path.relative_to(PROJECT_ROOT)),
        "expected_clip_ids": expected_ids,
        "maximum_output_tokens": max_tokens,
        "response_format": "json_object_with_local_validation",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_stored": False,
    }
    (part_dir / "request_manifest.json").write_text(
        json.dumps(request_manifest, indent=2), encoding="utf-8"
    )
    response: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        response = request(
            API_URL,
            key,
            payload(path, part, expected_ids, max_tokens),
        )
        (part_dir / "raw_api_response.json").write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )
        parsed = normalize_response(json.loads(extract_content(response)))
        validate_assignments(parsed, expected_ids)
        (part_dir / "assignments.json").write_text(
            json.dumps(parsed, indent=2), encoding="utf-8"
        )
        summary = {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "generation_id": response.get("id"),
            "served_model": response.get("model"),
            "provider": response.get("provider"),
            "usage": response.get("usage", {}),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (part_dir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(
            f"[{part}/10] Validated; cost=${summary['usage'].get('cost', 0):.6f}",
            flush=True,
        )
    except Exception as error:
        if response and not (part_dir / "raw_api_response.json").exists():
            (part_dir / "raw_api_response.json").write_text(
                json.dumps(response, indent=2), encoding="utf-8"
            )
        (part_dir / "error.json").write_text(
            json.dumps(
                {
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "usage": response.get("usage", {}),
                    "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


def finalize(expected: dict[int, list[str]]) -> dict:
    rows = []
    costs = []
    for part in range(1, 11):
        part_dir = OUTPUT / f"part_{part:02d}"
        data = json.loads(
            (part_dir / "assignments.json").read_text(encoding="utf-8-sig")
        )
        rows.extend(validate_assignments(data, expected[part]))
        summary = json.loads(
            (part_dir / "summary.json").read_text(encoding="utf-8-sig")
        )
        costs.append(float(summary.get("usage", {}).get("cost", 0)))
    all_ids = [row["clip_id"] for row in rows]
    if len(rows) != 509 or len(set(all_ids)) != 509:
        raise ValueError("Aggregated response does not contain 509 unique clip IDs")

    events = []
    for label, description in EVENTS.items():
        event_rows = sorted(
            (row for row in rows if row["event_label"] == label),
            key=lambda row: (
                int(row["source_progress"]),
                -float(row["confidence"]),
                row["clip_id"],
            ),
        )
        confidence = (
            sum(float(row["confidence"]) for row in event_rows) / len(event_rows)
            if event_rows
            else 0
        )
        events.append(
            {
                "event_id": label,
                "event_description": description,
                "ordered_clips": [row["clip_id"] for row in event_rows],
                "confidence": round(confidence, 4),
            }
        )
    response = {"events": events}
    response_path = OUTPUT / "combined_model_response.json"
    response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(EVALUATOR),
            str(response_path),
            "--output",
            str(OUTPUT / "evaluation.json"),
            "--reconstruct-dir",
            str(OUTPUT / "reconstructed_videos"),
        ],
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    result = {
        "part_count": 10,
        "clip_count": len(rows),
        "measured_api_cost_usd": round(sum(costs), 9),
        "evaluator_exit_code": completed.returncode,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUTPUT / "staged_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--part", type=int, choices=range(1, 11))
    parser.add_argument("--max-output-tokens", type=int, default=5000)
    parser.add_argument("--max-total-estimated-cost", type=float, default=0.30)
    args = parser.parse_args()

    load_dotenv()
    import os

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not SHARD_MANIFEST.exists() or not BLIND_MANIFEST.exists():
        raise FileNotFoundError("Staged inputs have not been prepared")
    expected = expected_ids_by_part()
    parts = [args.part] if args.part else list(range(1, 11))
    assumed_input_tokens_per_part = 12_000
    estimated_per_part = (
        assumed_input_tokens_per_part * 0.75 / 1_000_000
        + args.max_output_tokens * 3.75 / 1_000_000
    )
    estimate = estimated_per_part * len(parts)
    preflight = {
        "mode": "execute" if args.execute else "dry_run",
        "model": MODEL_ID,
        "parts": parts,
        "known_event_categories_supplied": True,
        "maximum_output_tokens_per_part": args.max_output_tokens,
        "estimated_cost_per_part_usd": round(estimated_per_part, 6),
        "estimated_total_cost_usd": round(estimate, 6),
        "cost_guardrail_usd": args.max_total_estimated_cost,
    }
    print(json.dumps(preflight, indent=2), flush=True)
    if estimate > args.max_total_estimated_cost:
        raise RuntimeError("Estimated cost exceeds the configured guardrail")
    if not args.execute:
        print("DRY RUN ONLY: no API request was made.")
        return 0
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for part in parts:
        path = SHARD_DIR / f"scrambled_part_{part:02d}_of_10_labelled.mp4"
        run_part(part, path, expected[part], key, args.max_output_tokens)
    if all((OUTPUT / f"part_{part:02d}" / "assignments.json").exists() for part in range(1, 11)):
        print(json.dumps(finalize(expected), indent=2), flush=True)
    else:
        print("Requested parts completed; aggregate awaits all ten parts.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
