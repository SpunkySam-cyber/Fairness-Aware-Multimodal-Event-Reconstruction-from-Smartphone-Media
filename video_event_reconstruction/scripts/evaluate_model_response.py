"""Validate and score one model response against the private frozen answer key."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRUTH = (
    PROJECT_ROOT / "data" / "experiment_01" / "PRIVATE_expected_hierarchy.json"
)
EXPECTED_IDS = {f"V{index:03d}" for index in range(1, 22)}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def validate_prediction(payload: Any) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [], ["Top-level response must be an object"]
    events = payload.get("events")
    if not isinstance(events, list):
        return [], ["'events' must be an array"]
    if len(events) != 7:
        errors.append(f"Expected 7 events, found {len(events)}")

    seen_event_ids: set[str] = set()
    all_clips: list[str] = []
    valid_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        prefix = f"events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be an object")
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(f"{prefix}.event_id must be a non-empty string")
        elif event_id in seen_event_ids:
            errors.append(f"Duplicate event_id: {event_id}")
        else:
            seen_event_ids.add(event_id)
        description = event.get("event_description")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{prefix}.event_description must be a non-empty string")
        clips = event.get("ordered_clips")
        if not isinstance(clips, list) or len(clips) != 3:
            errors.append(f"{prefix}.ordered_clips must contain exactly 3 IDs")
            continue
        if not all(isinstance(clip, str) for clip in clips):
            errors.append(f"{prefix}.ordered_clips contains a non-string value")
            continue
        if len(set(clips)) != 3:
            errors.append(f"{prefix}.ordered_clips repeats a clip")
        unknown = set(clips).difference(EXPECTED_IDS)
        if unknown:
            errors.append(f"{prefix}.ordered_clips has unknown IDs: {sorted(unknown)}")
        evidence = event.get("ordering_evidence")
        if (
            not isinstance(evidence, list)
            or len(evidence) != 2
            or not all(isinstance(item, str) and item.strip() for item in evidence)
        ):
            errors.append(f"{prefix}.ordering_evidence must contain 2 non-empty strings")
        confidence = event.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= float(confidence) <= 1.0
        ):
            errors.append(f"{prefix}.confidence must be between 0.0 and 1.0")
        all_clips.extend(clips)
        valid_events.append(event)

    duplicates = sorted({clip for clip in all_clips if all_clips.count(clip) > 1})
    missing = sorted(EXPECTED_IDS.difference(all_clips))
    if duplicates:
        errors.append(f"Clips reused across events: {duplicates}")
    if missing:
        errors.append(f"Clips omitted: {missing}")
    return valid_events, errors


def pairs(group: list[str]) -> set[frozenset[str]]:
    return {frozenset(pair) for pair in itertools.combinations(group, 2)}


def choose2(value: int) -> int:
    return value * (value - 1) // 2


def adjusted_rand_index(
    truth_groups: list[list[str]], predicted_groups: list[list[str]]
) -> float:
    truth_index = {
        clip: index for index, group in enumerate(truth_groups) for clip in group
    }
    pred_index = {
        clip: index for index, group in enumerate(predicted_groups) for clip in group
    }
    common = sorted(set(truth_index).intersection(pred_index))
    count = len(common)
    if count < 2:
        return 0.0

    contingency = [[0 for _ in predicted_groups] for _ in truth_groups]
    for clip in common:
        contingency[truth_index[clip]][pred_index[clip]] += 1
    sum_cells = sum(choose2(cell) for row in contingency for cell in row)
    row_sums = [sum(row) for row in contingency]
    col_sums = [
        sum(contingency[row][column] for row in range(len(truth_groups)))
        for column in range(len(predicted_groups))
    ]
    sum_rows = sum(choose2(value) for value in row_sums)
    sum_cols = sum(choose2(value) for value in col_sums)
    total_pairs = choose2(count)
    expected = (sum_rows * sum_cols) / total_pairs if total_pairs else 0.0
    maximum = 0.5 * (sum_rows + sum_cols)
    denominator = maximum - expected
    return (sum_cells - expected) / denominator if denominator else 1.0


def kendall_for_permutation(truth: list[str], predicted: list[str]) -> float:
    positions = {clip: index for index, clip in enumerate(predicted)}
    concordant = 0
    discordant = 0
    for left, right in itertools.combinations(truth, 2):
        if positions[left] < positions[right]:
            concordant += 1
        else:
            discordant += 1
    return (concordant - discordant) / (concordant + discordant)


def truth_sequences(truth: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [str(item["blind_id"]) for item in event["correct_sequence"]]
        for event in truth
    ]


def score(
    truth: list[dict[str, Any]], prediction: list[dict[str, Any]]
) -> dict[str, Any]:
    correct = truth_sequences(truth)
    predicted = [
        [str(clip) for clip in event["ordered_clips"]] for event in prediction
    ]
    correct_pairs = set().union(*(pairs(group) for group in correct))
    predicted_pairs = set().union(*(pairs(group) for group in predicted))
    true_positive = len(correct_pairs.intersection(predicted_pairs))
    precision = true_positive / len(predicted_pairs) if predicted_pairs else 0.0
    recall = true_positive / len(correct_pairs) if correct_pairs else 0.0
    pairwise_f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )

    exact_group_count = 0
    exact_order_count = 0
    kendall_scores: list[float] = []
    event_matches: list[dict[str, Any]] = []
    used_predictions: set[int] = set()
    for truth_index, correct_sequence in enumerate(correct):
        correct_set = set(correct_sequence)
        candidates = [
            (pred_index, sequence)
            for pred_index, sequence in enumerate(predicted)
            if pred_index not in used_predictions and set(sequence) == correct_set
        ]
        if not candidates:
            event_matches.append(
                {
                    "truth_event_id": truth[truth_index]["event_id"],
                    "predicted_event_id": None,
                    "group_correct": False,
                    "order_correct": False,
                    "kendall_tau": None,
                }
            )
            continue
        pred_index, predicted_sequence = candidates[0]
        used_predictions.add(pred_index)
        exact_group_count += 1
        order_correct = predicted_sequence == correct_sequence
        exact_order_count += int(order_correct)
        tau = kendall_for_permutation(correct_sequence, predicted_sequence)
        kendall_scores.append(tau)
        event_matches.append(
            {
                "truth_event_id": truth[truth_index]["event_id"],
                "predicted_event_id": prediction[pred_index].get("event_id"),
                "group_correct": True,
                "order_correct": order_correct,
                "kendall_tau": round(tau, 6),
            }
        )

    return {
        "grouping": {
            "pairwise_precision": round(precision, 6),
            "pairwise_recall": round(recall, 6),
            "pairwise_f1": round(pairwise_f1, 6),
            "adjusted_rand_index": round(
                adjusted_rand_index(correct, predicted), 6
            ),
            "exact_groups": exact_group_count,
            "exact_group_rate": round(exact_group_count / 7, 6),
        },
        "ordering": {
            "exact_orders": exact_order_count,
            "exact_order_rate_all_events": round(exact_order_count / 7, 6),
            "mean_kendall_tau_on_correct_groups": (
                round(sum(kendall_scores) / len(kendall_scores), 6)
                if kendall_scores
                else None
            ),
        },
        "complete_reconstructions": exact_order_count,
        "event_matches": event_matches,
        "manual_review_required": {
            "event_description_alignment": True,
            "ordering_evidence_quality": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response", type=Path)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        prediction_payload = load_json(args.response)
    except (OSError, json.JSONDecodeError) as error:
        result: dict[str, Any] = {
            "valid_json": False,
            "constraint_valid": False,
            "constraint_errors": [str(error)],
            "scores": None,
        }
    else:
        prediction, errors = validate_prediction(prediction_payload)
        result = {
            "valid_json": True,
            "constraint_valid": not errors,
            "constraint_errors": errors,
            "scores": score(load_json(args.truth), prediction) if not errors else None,
        }

    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result.get("scores") is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

