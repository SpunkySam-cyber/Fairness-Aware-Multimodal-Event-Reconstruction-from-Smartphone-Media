"""Score a 509-clip response in which the model never assigned some declared clips.

Used for the event-discovery run only. It reuses evaluate_two_second_response.py
UNCHANGED, so the known-names run and this run are scored by the same functions.

Scoring rule for declared ("dropped") clips:
  * Grouping accuracy counts each dropped clip as wrong, over all 509 clips
    (the evaluator already divides by every known clip).
  * Pairwise F1 and ARI treat a dropped clip as belonging to no predicted event.
  * Pairwise ordering accuracy and Kendall tau use assigned clips only.
  * An event that lost a clip cannot count as an exact reconstruction.
  * The number of dropped clips is reported.
  * Videos are rebuilt from the assigned clips only.

Any other problem (unknown IDs, repeats, an undeclared omission, not exactly 7
events) is still a constraint failure and yields no metrics. With no --dropped
this behaves exactly like the evaluator.

This file never opens the PRIVATE_* files itself; only the evaluator's functions do.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import evaluate_two_second_response as ev

# Errors the evaluator raises purely as a consequence of clips being omitted.
OMISSION_ERROR = re.compile(r"^(Omitted \d+ clip IDs|Expected \d+ total assignments, received \d+)$")

RULE = (
    "Dropped clips count as wrong for grouping accuracy over all clips; pairwise F1 and ARI treat "
    "them as unassigned; ordering accuracy and Kendall tau use assigned clips only; videos are "
    "rebuilt from assigned clips only."
)


def score(response: dict, dropped: list[str]) -> dict:
    evaluation = ev.evaluate(response)
    if not dropped:
        return evaluation
    errors = evaluation.get("constraint_errors", [])
    unexplained = [error for error in errors if not OMISSION_ERROR.match(error)]
    known = evaluation.get("known_clip_count")
    submitted = evaluation.get("submitted_assignment_count")
    if unexplained or known is None or submitted is None:
        raise ValueError(f"Response has problems beyond the declared omissions: {unexplained or errors}")

    submitted_ids = {clip for event in response["events"] for clip in event["ordered_clips"]}
    valid_ids = {f"C{index:04d}" for index in range(1, known + 1)}
    problems = []
    if set(dropped) & submitted_ids:
        problems.append(f"declared dropped clips that were assigned: {sorted(set(dropped) & submitted_ids)}")
    if not set(dropped) <= valid_ids:
        problems.append(f"declared dropped IDs outside the clip range: {sorted(set(dropped) - valid_ids)}")
    if known - submitted != len(set(dropped)):
        problems.append(
            f"{known - submitted} clips are missing but {len(set(dropped))} were declared dropped"
        )
    if problems:
        raise ValueError("; ".join(problems))

    evaluation["constraint_valid"] = True
    evaluation["constraint_errors_waived_as_declared_omissions"] = errors
    evaluation["constraint_errors"] = []
    evaluation["dropped_clips"] = {
        "count": len(dropped),
        "clip_ids": sorted(dropped),
        "assigned_clip_count": submitted,
        "total_clip_count": known,
        "rule": RULE,
    }
    return evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response", type=Path)
    parser.add_argument("--dropped", nargs="*", default=[], help="clip IDs the model never assigned")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reconstruct-dir", type=Path)
    args = parser.parse_args()

    response = ev.load(args.response)
    try:
        result = score(response, args.dropped)
    except ValueError as error:
        print(f"SCORING REFUSED: {error}", file=sys.stderr)
        return 1
    if args.reconstruct_dir:
        result["reconstructed_videos"] = ev.reconstruct(response, result, args.reconstruct_dir)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if result["constraint_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
