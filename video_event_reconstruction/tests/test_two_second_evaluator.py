import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_two_second_response import evaluate


EXPECTED = ROOT / "data" / "experiment_02_two_second" / "PRIVATE_expected_hierarchy.json"


def perfect_response() -> dict:
    truth = json.loads(EXPECTED.read_text(encoding="utf-8"))
    return {
        "events": [
            {
                "event_id": f"event_{index}",
                "event_description": event["activity"],
                "ordered_clips": list(event["ordered_clips"]),
                "confidence": 1.0,
            }
            for index, event in enumerate(truth, start=1)
        ]
    }


def test_perfect_response_scores_one() -> None:
    result = evaluate(perfect_response())
    assert result["constraint_valid"] is True
    assert result["grouping"]["best_assignment_clip_accuracy"] == 1.0
    assert result["grouping"]["pairwise_f1"] == 1.0
    assert result["ordering"]["exact_reconstructed_events"] == 7
    assert result["ordering"]["full_reconstruction_exact"] is True


def test_reversed_event_keeps_grouping_but_reduces_ordering() -> None:
    response = perfect_response()
    response["events"][0]["ordered_clips"].reverse()
    result = evaluate(response)
    assert result["constraint_valid"] is True
    assert result["grouping"]["best_assignment_clip_accuracy"] == 1.0
    assert result["ordering"]["exact_reconstructed_events"] == 6
    assert result["ordering"]["full_reconstruction_exact"] is False


def test_duplicate_assignment_is_rejected() -> None:
    response = perfect_response()
    response["events"][0]["ordered_clips"][0] = response["events"][1]["ordered_clips"][0]
    result = evaluate(response)
    assert result["constraint_valid"] is False
    assert any("Repeated clip assignments" in error for error in result["constraint_errors"])


if __name__ == "__main__":
    test_perfect_response_scores_one()
    test_reversed_event_keeps_grouping_but_reduces_ordering()
    test_duplicate_assignment_is_rejected()
    print("3 evaluator checks passed")
