"""Qwen3.8-Max run of the event-discovery experiment (no activity names, told only "7 activities").

This reuses run_discovery_two_second.py UNCHANGED (prompt, validation and normalisation, call
recording, archiving, cost accounting, merge, scoring) and changes only:
  * the model ID,
  * the price constants used for the cost estimate,
  * the output folder (model_runs/discovery-qwen-max/run_01).

Same shard videos, same prompt text, same request parameters. Nothing is sent to the API unless
--execute is passed. A failed paid call is recorded and archived, never deleted or silently
retried. The answer key is never read here (only the scorer reads it, after all model calls).

Qwen3.8-Max on OpenRouter has mandatory reasoning that cannot be disabled; reasoning tokens are
billed as output tokens and count toward max_tokens. The estimate therefore assumes the whole
--max-output-tokens allowance may be used.
"""

from __future__ import annotations

import argparse
import json
import os

import run_discovery_two_second as g

QWEN_MODEL_ID = "qwen/qwen3.8-max-0902"
INPUT_USD_PER_MILLION = 2.0
OUTPUT_USD_PER_MILLION = 6.0
# Measured on this dataset: 122,242 prompt tokens for the 1,018 s one-shot video (about 120 per second).
VIDEO_TOKENS_PER_SECOND = 120
PROMPT_TEXT_TOKENS = 1_500
MERGE_INPUT_TOKENS = 3_000
MERGE_MAX_OUTPUT_TOKENS = 4_000  # fixed inside the reused merge call
EXPERIMENT_CEILING_USD = 0.50

OUTPUT = g.EXPERIMENT / "model_runs" / "discovery-qwen-max" / "run_01"

# Rebind the module-level names the reused functions read. Nothing else is changed.
g.MODEL_ID = QWEN_MODEL_ID
g.OUTPUT = OUTPUT


def part_input_tokens(duration_seconds: float) -> int:
    return int(duration_seconds * VIDEO_TOKENS_PER_SECOND) + PROMPT_TEXT_TOKENS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="make paid API calls")
    parser.add_argument("--part", type=int, choices=range(1, 11), help="run a single part only")
    parser.add_argument(
        "--allow-full-run",
        action="store_true",
        help="required to run without --part (all ten parts, then the merge call)",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="archive a previously failed (paid) attempt and make a NEW paid call for it",
    )
    parser.add_argument("--max-output-tokens", type=int, default=12_000)
    parser.add_argument("--max-total-estimated-cost", type=float, default=0.10)
    args = parser.parse_args()

    if not args.part and not args.allow_full_run:
        raise SystemExit("Refusing to run all parts without --allow-full-run (use --part N).")

    g.load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not g.SHARD_MANIFEST.exists() or not g.BLIND_MANIFEST.exists():
        raise FileNotFoundError("Staged inputs have not been prepared")
    expected = g.expected_ids_by_part()
    manifest = json.loads(g.SHARD_MANIFEST.read_text(encoding="utf-8-sig"))
    duration = {int(row["part"]): float(row["duration_seconds"]) for row in manifest["parts"]}
    parts = [args.part] if args.part else list(range(1, 11))

    out_cost = args.max_output_tokens * OUTPUT_USD_PER_MILLION / 1e6
    part_estimates = {
        part: part_input_tokens(duration[part]) * INPUT_USD_PER_MILLION / 1e6 + out_cost for part in parts
    }
    merge_estimate = (
        MERGE_INPUT_TOKENS * INPUT_USD_PER_MILLION / 1e6
        + MERGE_MAX_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION / 1e6
        if not args.part
        else 0.0
    )
    estimate = sum(part_estimates.values()) + merge_estimate
    spent = g.saved_cost(OUTPUT) if OUTPUT.exists() else 0.0

    print(json.dumps({
        "mode": "execute" if args.execute else "dry_run",
        "model": QWEN_MODEL_ID,
        "prices_usd_per_million_input_output": [INPUT_USD_PER_MILLION, OUTPUT_USD_PER_MILLION],
        "parts": parts,
        "known_event_categories_supplied": False,
        "event_count_supplied": g.N_EVENTS,
        "assumed_input_tokens_per_part": {str(p): part_input_tokens(duration[p]) for p in parts},
        "max_output_tokens": args.max_output_tokens,
        "note": "reasoning is mandatory, billed as output, and counted inside max_output_tokens",
        "worst_case_estimated_cost_usd": round(estimate, 4),
        "cost_guardrail_usd": args.max_total_estimated_cost,
        "measured_cost_already_in_this_output_dir_usd": round(spent, 6),
        "experiment_ceiling_usd": EXPERIMENT_CEILING_USD,
        "output_dir": str(OUTPUT.relative_to(g.PROJECT_ROOT)),
    }, indent=2), flush=True)
    if estimate > args.max_total_estimated_cost:
        raise RuntimeError("Estimated cost exceeds the configured guardrail")
    if spent + estimate > EXPERIMENT_CEILING_USD:
        raise RuntimeError("Measured spend plus this run's worst case would exceed the experiment ceiling")
    if not args.execute:
        print("DRY RUN ONLY: no API request was made.")
        return 0
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    g.stage1(parts, expected, key, args.max_output_tokens, args.retry_failed)
    if all((OUTPUT / f"part_{p:02d}" / "groups.json").exists() for p in range(1, 11)):
        print(json.dumps(g.stage2_and_score(expected, key, args.retry_failed), indent=2), flush=True)
    else:
        print("Requested parts completed; merge and scoring await all ten parts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
