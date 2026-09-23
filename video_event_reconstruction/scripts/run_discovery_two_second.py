"""Event-DISCOVERY run for the 509-clip experiment (no activity names supplied).

Differences from run_staged_two_second_reconstruction.py:
  * The model is NOT told the seven activity names. It is told only that the full
    experiment contains exactly 7 different activities.
  * Stage 1 (10 API calls, one per shard): the model groups the clips in its part
    by what is happening, describes each group in free text, and estimates
    source_progress (0-1000) for every clip.
  * Stage 2 (1 text-only API call): the model merges the per-part group
    descriptions into exactly 7 events.
  * Clips are ordered inside each event by source_progress, then the existing
    evaluator scores grouping/ordering against the private key (it matches
    predicted groups to true events itself, so event names are irrelevant).

Nothing is sent to the API unless --execute is passed. The answer key is never
read by this script (only by the evaluator, after all model calls are finished).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_staged_two_second_reconstruction import (
    BLIND_MANIFEST,
    MODEL_ID,
    SHARD_DIR,
    SHARD_MANIFEST,
    encoded_video,
    expected_ids_by_part,
)
from run_two_second_reconstruction import (
    API_URL,
    EXPERIMENT,
    PROJECT_ROOT,
    extract_content,
    load_dotenv,
    request,
)

OUTPUT = EXPERIMENT / "model_runs" / "discovery-gemini-flash" / "run_01"
N_EVENTS = 7
SCORER = Path(__file__).resolve().parent / "score_discovery_with_dropped_clips.py"


def shard_prompt(part: int, expected_ids: list[str]) -> str:
    return f"""You are processing part {part} of 10 from a larger event-reconstruction experiment.

This silent video contains {len(expected_ids)} shuffled clips. Every clip lasts about two seconds and shows a persistent ID. Across ALL 10 parts there are exactly {N_EVENTS} different activities (each clip belongs to one of them). This part may contain clips from some or all of them. You are NOT told what the activities are: work it out from what you see.

Task:
1. Group the clips in this part by the activity being performed. Use at most {N_EVENTS} groups, and put every clip in exactly one group.
2. For each group, write a short, specific description (one sentence: the task, the main objects, the setting).
3. For every clip, estimate source_progress: an integer from 0 (very beginning of that activity) to 1000 (very end), from visual state and action progression, not from the clip ID or its position in this shuffled part. Consecutive moments should get nearby but distinguishable values.

Required clip IDs in this part:
{", ".join(expected_ids)}

Include every required ID exactly once and do not invent IDs. Return only JSON of this exact shape:
{{"groups":[{{"group_id":"G1","description":"one sentence","clips":[{{"clip_id":"C0001","source_progress":0,"confidence":0.0}}]}}]}}
The example values are placeholders. confidence must be between 0 and 1.
"""


def shard_payload(path: Path, part: int, expected_ids: list[str], max_tokens: int) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": shard_prompt(part, expected_ids)},
                    {"type": "video_url", "video_url": {"url": encoded_video(path)}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning": {"effort": "low", "exclude": True},
        "response_format": {"type": "json_object"},
        "provider": {"require_parameters": True},
    }


def normalize_groups(data: Any) -> Any:
    """Accept a bare top-level list of groups as well as {"groups": [...]} (shape only),
    as the earlier staged script's normalize_response did for assignments."""
    return {"groups": data} if isinstance(data, list) else data


def validate_groups(data: Any, expected_ids: list[str]) -> list[dict]:
    """Validate (and harmlessly normalise, in place) one stage-1 response."""
    data = normalize_groups(data)
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list) or not groups:
        raise ValueError("Response does not contain a groups array")
    # An empty group carries no clips; drop it instead of discarding a paid response.
    groups = data["groups"] = [g for g in groups if isinstance(g, dict) and g.get("clips")]
    if not groups:
        raise ValueError("Response contains no non-empty groups")
    if len(groups) > N_EVENTS:
        raise ValueError(f"More than {N_EVENTS} groups returned: {len(groups)}")
    seen: list[str] = []
    for group in groups:
        if not isinstance(group.get("description"), str) or not group["description"].strip():
            raise ValueError("A group has no description")
        for clip in group["clips"]:
            if not isinstance(clip, dict):
                raise ValueError("A clip entry is not an object")
            progress = clip.get("source_progress")
            if isinstance(progress, float) and progress.is_integer():
                clip["source_progress"] = progress = int(progress)
            if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 1000:
                raise ValueError(f"Invalid source_progress: {progress}")
            confidence = clip.get("confidence")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                clip["confidence"] = 0.5
            seen.append(clip.get("clip_id"))
    if len(seen) != len(set(seen)):
        raise ValueError("Duplicate clip IDs")
    if set(seen) != set(expected_ids):
        raise ValueError(
            f"ID mismatch; missing={sorted(set(expected_ids) - set(seen))[:10]}, "
            f"unexpected={sorted(set(seen) - set(expected_ids))[:10]}"
        )
    return groups


def merge_prompt(described: list[dict]) -> str:
    lines = "\n".join(
        f'- {row["key"]} ({row["count"]} clips): {row["description"]}' for row in described
    )
    return f"""A video experiment contains exactly {N_EVENTS} different activities. Ten separate parts were analysed independently. Each part produced groups of clips with a short text description. The same activity appears under different group IDs in different parts, and the wording differs.

Merge these groups into exactly {N_EVENTS} events, one per real activity. Every group must be assigned to exactly one event.

Groups:
{lines}

Return only JSON of this exact shape:
{{"events":[{{"event_description":"short description of the activity","group_keys":["p01_G1","p02_G3"]}}]}}
"""


def merge_payload(described: list[dict], max_tokens: int) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": merge_prompt(described)}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning": {"effort": "low", "exclude": True},
        "response_format": {"type": "json_object"},
    }


def validate_merge(data: Any, valid_keys: set[str]) -> list[dict]:
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list) or len(events) != N_EVENTS:
        raise ValueError(f"Merge must return exactly {N_EVENTS} events")
    used: list[str] = []
    for event in events:
        keys = event.get("group_keys") if isinstance(event, dict) else None
        if not isinstance(keys, list) or not keys:
            raise ValueError("Every event needs at least one group key")
        used.extend(keys)
    if len(used) != len(set(used)):
        raise ValueError("A group was assigned to more than one event")
    if set(used) != valid_keys:
        raise ValueError(
            f"Merge did not assign every group; missing={sorted(valid_keys - set(used))}, "
            f"unexpected={sorted(set(used) - valid_keys)}"
        )
    return events


def call_and_save(name: str, payload: dict, key: str, directory: Path) -> Any:
    """One API call. The raw response and usage are saved BEFORE parsing or validation,
    because a response that fails validation was still paid for."""
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    response = request(API_URL, key, payload)
    (directory / f"{name}_raw_api_response.json").write_text(
        json.dumps(response, indent=2), encoding="utf-8"
    )
    (directory / f"{name}_summary.json").write_text(
        json.dumps(
            {
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "generation_id": response.get("id"),
                "served_model": response.get("model"),
                "usage": response.get("usage", {}),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return json.loads(extract_content(response))


def archive_failed(directory: Path, name: str) -> Path:
    """Move a failed attempt's files aside (never delete them: they hold its cost record)."""
    number = len(list(directory.glob("failed_attempt_*"))) + 1
    target = directory / f"failed_attempt_{number:02d}_{name}"
    target.mkdir()
    for path in directory.glob(f"{name}_*"):
        if path.is_file():
            path.rename(target / path.name)
    return target


def obtain(name, directory, done_path, make_payload, validate, key, retry_failed, normalize=lambda d: d):
    """Return validated data for one call without ever paying twice for the same result.

    1. validated result already on disk -> reuse it
    2. paid raw response on disk but not validated -> re-validate locally (free);
       if it still fails, stop, unless --retry-failed archives it and pays for a new call
    3. otherwise make the API call, recording any failure in {name}_error.json
    """
    if done_path.exists():
        data = json.loads(done_path.read_text(encoding="utf-8"))
        validate(data)
        return data, "existing"
    raw_path = directory / f"{name}_raw_api_response.json"
    if raw_path.exists():
        try:
            data = normalize(json.loads(extract_content(json.loads(raw_path.read_text(encoding="utf-8")))))
            validate(data)
        except Exception as error:
            if not retry_failed:
                raise FileExistsError(
                    f"{raw_path} holds a paid response that fails validation ({error}). "
                    "Inspect it; --retry-failed archives it and makes a NEW paid call."
                ) from error
            print(f"Archived failed attempt to {archive_failed(directory, name)}", flush=True)
        else:
            done_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            error_path = directory / f"{name}_error.json"
            (directory / f"{name}_recovered_locally.json").write_text(
                json.dumps(
                    {
                        "note": "Paid response re-validated locally from its saved raw file; no API call was made.",
                        "earlier_error": (
                            json.loads(error_path.read_text(encoding="utf-8")).get("error")
                            if error_path.exists()
                            else None
                        ),
                        "recovered_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return data, "recovered"
    try:
        data = normalize(call_and_save(name, make_payload(), key, directory))
        validate(data)
    except Exception as error:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}_error.json").write_text(
            json.dumps(
                {
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise
    done_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data, "called"


def saved_cost(directory: Path) -> float:
    """Sum measured cost over every call summary below `directory`, archived failures included."""
    total = 0.0
    for path in directory.rglob("*_summary.json"):
        total += float(json.loads(path.read_text(encoding="utf-8")).get("usage", {}).get("cost", 0))
    return total


def accepted_omissions() -> dict[int, list[str]]:
    """Clips the user explicitly accepted as omitted by the model, per part.

    Read from run_01/accepted_omissions.json ({"parts": {"4": ["C0185"]}, ...}). Only the listed
    IDs may be missing from that part; any other omission still fails validation.
    """
    path = OUTPUT / "accepted_omissions.json"
    if not path.exists():
        return {}
    parts = json.loads(path.read_text(encoding="utf-8"))["parts"]
    return {int(part): list(ids) for part, ids in parts.items()}


def validation_ids(part: int, expected: dict[int, list[str]]) -> list[str]:
    """IDs a part's response must contain: the required IDs minus explicitly accepted omissions."""
    dropped = set(accepted_omissions().get(part, []))
    return [clip_id for clip_id in expected[part] if clip_id not in dropped]


def stage1(parts: list[int], expected: dict[int, list[str]], key: str, max_tokens: int, retry_failed: bool) -> None:
    for part in parts:
        directory = OUTPUT / f"part_{part:02d}"
        path = SHARD_DIR / f"scrambled_part_{part:02d}_of_10_labelled.mp4"
        data, how = obtain(
            "stage1",
            directory,
            directory / "groups.json",
            # The prompt always lists the FULL required ID set; only validation honours accepted omissions.
            lambda: shard_payload(path, part, expected[part], max_tokens),
            lambda d: validate_groups(d, validation_ids(part, expected)),
            key,
            retry_failed,
            normalize=normalize_groups,
        )
        summary_path = directory / "stage1_summary.json"
        cost = (
            float(json.loads(summary_path.read_text(encoding="utf-8")).get("usage", {}).get("cost", 0))
            if summary_path.exists()
            else 0.0
        )
        print(f"[{part}/10] {how}; {len(data['groups'])} groups; cost=${cost:.6f}", flush=True)
        for index, group in enumerate(data["groups"], start=1):
            print(f"    G{index} ({len(group['clips'])} clips): {group['description']}", flush=True)


def stage2_and_score(expected: dict[int, list[str]], key: str, retry_failed: bool) -> dict:
    described: list[dict] = []
    clips_by_key: dict[str, list[dict]] = {}
    for part in range(1, 11):
        data = json.loads((OUTPUT / f"part_{part:02d}" / "groups.json").read_text(encoding="utf-8"))
        for index, group in enumerate(validate_groups(data, validation_ids(part, expected)), start=1):
            group_key = f"p{part:02d}_G{index}"
            clips_by_key[group_key] = group["clips"]
            described.append(
                {"key": group_key, "count": len(group["clips"]), "description": group["description"]}
            )
    valid_keys = set(clips_by_key)
    merged, how = obtain(
        "stage2_merge",
        OUTPUT,
        OUTPUT / "merge_events.json",
        lambda: merge_payload(described, 4000),
        lambda d: validate_merge(d, valid_keys),
        key,
        retry_failed,
    )
    print(f"Merge stage: {how}", flush=True)
    events_in = validate_merge(merged, valid_keys)

    events_out = []
    for number, event in enumerate(events_in, start=1):
        rows = [clip for group_key in event["group_keys"] for clip in clips_by_key[group_key]]
        rows.sort(key=lambda r: (int(r["source_progress"]), -float(r["confidence"]), r["clip_id"]))
        events_out.append(
            {
                "event_id": f"discovered_{number}",
                "event_description": event.get("event_description", ""),
                "ordered_clips": [r["clip_id"] for r in rows],
            }
        )
    response_path = OUTPUT / "combined_model_response.json"
    response_path.write_text(json.dumps({"events": events_out}, indent=2), encoding="utf-8")

    dropped = sorted(clip for ids in accepted_omissions().values() for clip in ids)
    # The shared evaluator is untouched; the wrapper reuses its functions and declares dropped clips.
    completed = subprocess.run(
        [
            sys.executable, str(SCORER), str(response_path),
            "--output", str(OUTPUT / "evaluation.json"),
            "--reconstruct-dir", str(OUTPUT / "reconstructed_videos"),
            *(["--dropped", *dropped] if dropped else []),
        ],
        text=True, capture_output=True,
    )
    print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    summary = {
        "assigned_clip_count": sum(len(e["ordered_clips"]) for e in events_out),
        "dropped_clips": dropped,
        "measured_api_cost_usd": round(saved_cost(OUTPUT), 6),
        "scorer_exit_code": completed.returncode,
        "known_event_categories_supplied": False,
        "event_count_supplied": N_EVENTS,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUTPUT / "discovery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="make paid API calls")
    parser.add_argument("--part", type=int, choices=range(1, 11), help="run a single part only")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="archive a previously failed (paid) attempt and make a NEW paid call for it",
    )
    parser.add_argument("--max-output-tokens", type=int, default=5000)
    parser.add_argument("--max-total-estimated-cost", type=float, default=0.30)
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not SHARD_MANIFEST.exists() or not BLIND_MANIFEST.exists():
        raise FileNotFoundError("Staged inputs have not been prepared")
    expected = expected_ids_by_part()
    parts = [args.part] if args.part else list(range(1, 11))

    per_part = 12_000 * 0.75 / 1e6 + args.max_output_tokens * 3.75 / 1e6
    merge_cost = 6_000 * 0.75 / 1e6 + 4_000 * 3.75 / 1e6
    estimate = per_part * len(parts) + (merge_cost if not args.part else 0)
    print(json.dumps({
        "mode": "execute" if args.execute else "dry_run",
        "model": MODEL_ID,
        "parts": parts,
        "known_event_categories_supplied": False,
        "event_count_supplied": N_EVENTS,
        "worst_case_estimated_total_cost_usd": round(estimate, 4),
        "cost_guardrail_usd": args.max_total_estimated_cost,
        "output_dir": str(OUTPUT.relative_to(PROJECT_ROOT)),
    }, indent=2), flush=True)
    if estimate > args.max_total_estimated_cost:
        raise RuntimeError("Estimated cost exceeds the configured guardrail")
    if not args.execute:
        print("DRY RUN ONLY: no API request was made.")
        return 0
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    stage1(parts, expected, key, args.max_output_tokens, args.retry_failed)
    if all((OUTPUT / f"part_{p:02d}" / "groups.json").exists() for p in range(1, 11)):
        print(json.dumps(stage2_and_score(expected, key, args.retry_failed), indent=2), flush=True)
    else:
        print("Requested parts completed; merge and scoring await all ten parts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
