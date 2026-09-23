"""Evaluate and reconstruct a 509-clip experiment response."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = PROJECT_ROOT / "data" / "experiment_02_two_second"
ANSWER_KEY = EXPERIMENT / "PRIVATE_answer_key.json"
EXPECTED = EXPERIMENT / "PRIVATE_expected_hierarchy.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def locate_ffmpeg() -> Path:
    command = shutil.which("ffmpeg")
    if command:
        return Path(command)
    workspace = PROJECT_ROOT.parent.parent
    matches = sorted(
        (workspace / "ffmpeg").glob("ffmpeg-*-essentials_build/bin/ffmpeg.exe")
    )
    if not matches:
        raise RuntimeError("FFmpeg was not found")
    return matches[-1]


def choose(value: int, count: int = 2) -> int:
    return math.comb(value, count) if value >= count else 0


def best_assignment(
    predicted: list[list[str]], truth: list[dict[str, Any]]
) -> tuple[tuple[int, ...], int]:
    truth_sets = [set(event["ordered_clips"]) for event in truth]
    best: tuple[int, ...] | None = None
    best_overlap = -1
    for permutation in itertools.permutations(range(len(truth))):
        overlap = sum(
            len(set(predicted[index]) & truth_sets[truth_index])
            for index, truth_index in enumerate(permutation)
        )
        if overlap > best_overlap:
            best = permutation
            best_overlap = overlap
    if best is None:
        raise RuntimeError("Could not assign predicted groups to truth events")
    return best, best_overlap


def ordering_score(predicted: list[str], expected: list[str]) -> dict[str, Any]:
    expected_positions = {clip_id: index for index, clip_id in enumerate(expected)}
    common = [clip_id for clip_id in predicted if clip_id in expected_positions]
    comparable_pairs = choose(len(common))
    concordant = 0
    discordant = 0
    for left in range(len(common)):
        for right in range(left + 1, len(common)):
            if expected_positions[common[left]] < expected_positions[common[right]]:
                concordant += 1
            else:
                discordant += 1
    pairwise_accuracy = (
        concordant / comparable_pairs if comparable_pairs else None
    )
    kendall_tau = (
        (concordant - discordant) / comparable_pairs if comparable_pairs else None
    )
    return {
        "common_clips": len(common),
        "truth_clip_count": len(expected),
        "coverage": len(common) / len(expected) if expected else 0.0,
        "pairwise_order_accuracy": pairwise_accuracy,
        "kendall_tau": kendall_tau,
        "exact_sequence": predicted == expected,
    }


def evaluate(response: dict[str, Any]) -> dict[str, Any]:
    truth = load(EXPECTED)
    known_ids = {
        clip_id for event in truth for clip_id in event["ordered_clips"]
    }
    events = response.get("events")
    errors: list[str] = []
    if not isinstance(events, list):
        return {"constraint_valid": False, "constraint_errors": ["events is not an array"]}
    if len(events) != 7:
        errors.append(f"Expected 7 events, received {len(events)}")

    predicted_sequences: list[list[str]] = []
    all_ids: list[str] = []
    for index, event in enumerate(events):
        ordered = event.get("ordered_clips") if isinstance(event, dict) else None
        if not isinstance(ordered, list) or not all(
            isinstance(item, str) for item in ordered
        ):
            errors.append(f"Event {index + 1} has invalid ordered_clips")
            ordered = []
        predicted_sequences.append(ordered)
        all_ids.extend(ordered)

    unknown = sorted(set(all_ids) - known_ids)
    omitted = sorted(known_ids - set(all_ids))
    duplicate_count = len(all_ids) - len(set(all_ids))
    if unknown:
        errors.append(f"Unknown clip IDs: {unknown[:20]}")
    if omitted:
        errors.append(f"Omitted {len(omitted)} clip IDs")
    if duplicate_count:
        errors.append(f"Repeated clip assignments: {duplicate_count}")
    if len(all_ids) != len(known_ids):
        errors.append(
            f"Expected {len(known_ids)} total assignments, received {len(all_ids)}"
        )

    if len(events) != 7:
        return {
            "constraint_valid": False,
            "constraint_errors": errors,
            "known_clip_count": len(known_ids),
        }

    assignment, correctly_assigned = best_assignment(predicted_sequences, truth)
    truth_sets = [set(event["ordered_clips"]) for event in truth]
    predicted_sets = [set(sequence) & known_ids for sequence in predicted_sequences]
    true_positive_pairs = sum(
        choose(len(predicted_set & truth_set))
        for predicted_set in predicted_sets
        for truth_set in truth_sets
    )
    predicted_pairs = sum(choose(len(group)) for group in predicted_sets)
    truth_pairs = sum(choose(len(group)) for group in truth_sets)
    precision = true_positive_pairs / predicted_pairs if predicted_pairs else 0.0
    recall = true_positive_pairs / truth_pairs if truth_pairs else 0.0
    pairwise_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    total_pairs = choose(len(known_ids))
    expected_index = (
        predicted_pairs * truth_pairs / total_pairs if total_pairs else 0.0
    )
    max_index = 0.5 * (predicted_pairs + truth_pairs)
    ari = (
        (true_positive_pairs - expected_index) / (max_index - expected_index)
        if max_index != expected_index
        else 1.0
    )

    event_results: list[dict[str, Any]] = []
    for predicted_index, truth_index in enumerate(assignment):
        predicted_event = events[predicted_index]
        truth_event = truth[truth_index]
        overlap = len(predicted_sets[predicted_index] & truth_sets[truth_index])
        order = ordering_score(
            predicted_sequences[predicted_index], truth_event["ordered_clips"]
        )
        event_results.append(
            {
                "predicted_event_index": predicted_index + 1,
                "predicted_event_id": predicted_event.get("event_id"),
                "predicted_description": predicted_event.get("event_description"),
                "matched_truth_event_id": truth_event["event_id"],
                "matched_activity": truth_event["activity"],
                "predicted_clip_count": len(predicted_sequences[predicted_index]),
                "truth_clip_count": len(truth_event["ordered_clips"]),
                "group_overlap_count": overlap,
                "group_recall": overlap / len(truth_event["ordered_clips"]),
                **order,
            }
        )

    valid = not errors
    return {
        "constraint_valid": valid,
        "constraint_errors": errors,
        "known_clip_count": len(known_ids),
        "submitted_assignment_count": len(all_ids),
        "grouping": {
            "best_assignment_clip_accuracy": correctly_assigned / len(known_ids),
            "correctly_assigned_clips": correctly_assigned,
            "pairwise_precision": precision,
            "pairwise_recall": recall,
            "pairwise_f1": pairwise_f1,
            "adjusted_rand_index": ari,
        },
        "ordering": {
            "exact_reconstructed_events": sum(
                bool(event["exact_sequence"]) for event in event_results
            ),
            "mean_pairwise_order_accuracy": mean_present(
                event["pairwise_order_accuracy"] for event in event_results
            ),
            "mean_kendall_tau": mean_present(
                event["kendall_tau"] for event in event_results
            ),
            "full_reconstruction_exact": all(
                bool(event["exact_sequence"]) for event in event_results
            ),
        },
        "event_results": event_results,
    }


def mean_present(values: Any) -> float | None:
    present = [float(value) for value in values if value is not None]
    return sum(present) / len(present) if present else None


def reconstruct(
    response: dict[str, Any], evaluation: dict[str, Any], output_dir: Path
) -> list[str]:
    if not evaluation["constraint_valid"]:
        return []
    answer = load(ANSWER_KEY)
    path_by_id = {
        row["blind_id"]: EXPERIMENT / row["clean_segment"] for row in answer
    }
    ffmpeg = locate_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for index, event in enumerate(response["events"], start=1):
        matched = evaluation["event_results"][index - 1]["matched_truth_event_id"]
        concat_file = output_dir / f"event_{index:02d}_concat.txt"
        concat_file.write_text(
            "".join(
                f"file '{path_by_id[clip_id].resolve().as_posix()}'\n"
                for clip_id in event["ordered_clips"]
            ),
            encoding="utf-8",
        )
        destination = output_dir / f"predicted_event_{index:02d}_matched_{matched}.mp4"
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
                str(destination),
            ],
            check=True,
        )
        concat_file.unlink()
        outputs.append(str(destination))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reconstruct-dir", type=Path)
    args = parser.parse_args()
    response = load(args.response)
    result = evaluate(response)
    if args.reconstruct_dir:
        result["reconstructed_videos"] = reconstruct(
            response, result, args.reconstruct_dir
        )
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if result["constraint_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
