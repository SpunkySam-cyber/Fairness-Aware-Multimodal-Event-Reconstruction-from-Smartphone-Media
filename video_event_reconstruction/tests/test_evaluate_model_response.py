"""Tests for structural validation and deterministic event scoring."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "evaluate_model_response.py"
SPEC = importlib.util.spec_from_file_location("evaluate_model_response", MODULE_PATH)
assert SPEC and SPEC.loader
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.truth = json.loads(
            (
                ROOT
                / "data"
                / "experiment_01"
                / "PRIVATE_expected_hierarchy.json"
            ).read_text(encoding="utf-8-sig")
        )

    def perfect_response(self) -> dict[str, object]:
        events = []
        for index, truth_event in enumerate(self.truth, start=1):
            events.append(
                {
                    "event_id": f"predicted_{index}",
                    "event_description": truth_event["activity_class"],
                    "ordered_clips": [
                        item["blind_id"]
                        for item in truth_event["correct_sequence"]
                    ],
                    "ordering_evidence": ["visible transition", "visible result"],
                    "confidence": 0.9,
                }
            )
        return {"events": events}

    def test_perfect_response_scores_one(self) -> None:
        response = self.perfect_response()
        events, errors = EVALUATOR.validate_prediction(response)
        self.assertEqual(errors, [])
        scores = EVALUATOR.score(self.truth, events)
        self.assertEqual(scores["grouping"]["pairwise_f1"], 1.0)
        self.assertEqual(scores["grouping"]["adjusted_rand_index"], 1.0)
        self.assertEqual(scores["ordering"]["exact_order_rate_all_events"], 1.0)
        self.assertEqual(scores["complete_reconstructions"], 7)

    def test_reversed_order_preserves_grouping_but_fails_order(self) -> None:
        response = self.perfect_response()
        for event in response["events"]:
            event["ordered_clips"].reverse()
        events, errors = EVALUATOR.validate_prediction(response)
        self.assertEqual(errors, [])
        scores = EVALUATOR.score(self.truth, events)
        self.assertEqual(scores["grouping"]["pairwise_f1"], 1.0)
        self.assertEqual(scores["ordering"]["exact_order_rate_all_events"], 0.0)
        self.assertEqual(scores["ordering"]["mean_kendall_tau_on_correct_groups"], -1.0)

    def test_duplicate_clip_is_rejected(self) -> None:
        response = self.perfect_response()
        response["events"][0]["ordered_clips"][0] = response["events"][1][
            "ordered_clips"
        ][0]
        _, errors = EVALUATOR.validate_prediction(response)
        self.assertTrue(any("reused" in error for error in errors))
        self.assertTrue(any("omitted" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

