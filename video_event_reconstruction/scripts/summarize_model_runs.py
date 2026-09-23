"""Aggregate the completed three-run OpenRouter benchmark."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = PROJECT_ROOT / "data" / "experiment_01" / "model_runs"
OUTPUT_ROOT = PROJECT_ROOT / "research" / "outputs" / "model_benchmark_20260914"
EXPECTED_ALIASES = {"qwen-max", "gemini-pro", "gemini-flash", "seed-turbo"}
LABELS = {
    "qwen-max": "Qwen3.8-Max",
    "gemini-pro": "Gemini 3.1 Pro",
    "gemini-flash": "Gemini 3.8 Flash",
    "seed-turbo": "Seed 2.1 Turbo",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def successful_runs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(RUN_ROOT.glob("*/*/summary.json")):
        run_dir = summary_path.parent
        summary = load(summary_path)
        evaluation = load(run_dir / "evaluation.json")
        request = load(run_dir / "request_manifest.json")
        scores = evaluation["scores"]
        rows.append(
            {
                "model_alias": summary["model_alias"],
                "model": summary["served_model"],
                "provider": summary.get("provider"),
                "run": request["run_number"],
                "attempt": request["attempt"],
                "input_form": request["input_form"],
                "reasoning_effort": request["reasoning_effort"],
                "grouping_pairwise_f1": scores["grouping"]["pairwise_f1"],
                "adjusted_rand_index": scores["grouping"]["adjusted_rand_index"],
                "exact_groups": scores["grouping"]["exact_groups"],
                "exact_orders": scores["ordering"]["exact_orders"],
                "exact_order_rate": scores["ordering"]["exact_order_rate_all_events"],
                "mean_kendall_tau": scores["ordering"]["mean_kendall_tau_on_correct_groups"],
                "complete_reconstructions": scores["complete_reconstructions"],
                "latency_seconds": summary["elapsed_seconds"],
                "prompt_tokens": summary["usage"].get("prompt_tokens"),
                "completion_tokens": summary["usage"].get("completion_tokens"),
                "reasoning_tokens": summary["usage"].get("completion_tokens_details", {}).get("reasoning_tokens"),
                "successful_call_cost_usd": summary["usage"].get("cost"),
                "result_directory": str(run_dir.relative_to(PROJECT_ROOT)),
            }
        )
    return rows


def charged_attempts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_path in sorted(RUN_ROOT.glob("**/raw_api_response.json")):
        response = load(raw_path)
        usage = response.get("usage", {})
        cost = float(usage.get("cost") or 0.0)
        if cost <= 0:
            continue
        message: dict[str, Any] = {}
        choices = response.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
        rows.append(
            {
                "directory": str(raw_path.parent.relative_to(PROJECT_ROOT)),
                "model": response.get("model"),
                "provider": response.get("provider"),
                "finish_reason": choices[0].get("finish_reason") if choices else None,
                "content_returned": bool(message.get("content")),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens"),
                "cost_usd": cost,
            }
        )
    return rows


def aggregate_models(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["model_alias"]].append(row)

    aggregates: list[dict[str, Any]] = []
    for alias, model_rows in grouped.items():
        model_rows.sort(key=lambda item: item["run"])
        order_rates = [float(item["exact_order_rate"]) for item in model_rows]
        exact_orders = [float(item["exact_orders"]) for item in model_rows]
        aggregates.append(
            {
                "model_alias": alias,
                "model": model_rows[0]["model"],
                "provider": model_rows[0]["provider"],
                "successful_runs": len(model_rows),
                "input_form": model_rows[0]["input_form"],
                "reasoning_effort": model_rows[0]["reasoning_effort"],
                "mean_grouping_pairwise_f1": mean(float(item["grouping_pairwise_f1"]) for item in model_rows),
                "mean_adjusted_rand_index": mean(float(item["adjusted_rand_index"]) for item in model_rows),
                "mean_exact_groups": mean(float(item["exact_groups"]) for item in model_rows),
                "mean_exact_orders": mean(exact_orders),
                "minimum_exact_orders": min(exact_orders),
                "maximum_exact_orders": max(exact_orders),
                "mean_exact_order_rate": mean(order_rates),
                "exact_order_rate_stddev": pstdev(order_rates),
                "mean_kendall_tau": mean(float(item["mean_kendall_tau"]) for item in model_rows),
                "mean_latency_seconds": mean(float(item["latency_seconds"]) for item in model_rows),
                "total_successful_cost_usd": sum(float(item["successful_call_cost_usd"]) for item in model_rows),
                "mean_successful_cost_usd": mean(float(item["successful_call_cost_usd"]) for item in model_rows),
                "run_order_scores": ",".join(str(int(item["exact_orders"])) for item in model_rows),
            }
        )
    aggregates.sort(
        key=lambda item: (
            item["mean_exact_orders"],
            item["mean_grouping_pairwise_f1"],
            -item["mean_successful_cost_usd"],
        ),
        reverse=True,
    )
    return aggregates


def event_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[str, int] = defaultdict(int)
    event_ids: set[str] = set()
    for row in rows:
        evaluation = load(PROJECT_ROOT / row["result_directory"] / "evaluation.json")
        totals[row["model_alias"]] += 1
        for match in evaluation["scores"]["event_matches"]:
            event_id = match["truth_event_id"]
            event_ids.add(event_id)
            if match["order_correct"]:
                counts[event_id][row["model_alias"]] += 1

    events: list[dict[str, Any]] = []
    for event_id in sorted(event_ids):
        event: dict[str, Any] = {"truth_event_id": event_id}
        for alias in sorted(EXPECTED_ALIASES):
            event[alias] = f"{counts[event_id][alias]}/{totals[alias]}"
        events.append(event)
    return events


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = successful_runs()
    aliases = {row["model_alias"] for row in rows}
    run_sets = {
        alias: {int(row["run"]) for row in rows if row["model_alias"] == alias}
        for alias in aliases
    }
    if aliases != EXPECTED_ALIASES or any(runs != {1, 2, 3} for runs in run_sets.values()):
        raise RuntimeError(
            f"Expected successful runs 1-3 for four models; found aliases={sorted(aliases)}, runs={run_sets}"
        )

    rows.sort(key=lambda item: (item["model_alias"], item["run"]))
    aggregates = aggregate_models(rows)
    attempts = charged_attempts()
    events = event_matrix(rows)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_ROOT / "benchmark_runs.csv", rows)
    write_csv(OUTPUT_ROOT / "benchmark_comparison.csv", aggregates)
    write_csv(OUTPUT_ROOT / "charged_attempts.csv", attempts)
    write_csv(OUTPUT_ROOT / "event_order_matrix.csv", events)

    successful_cost = sum(float(row["successful_call_cost_usd"]) for row in rows)
    total_cost = sum(float(row["cost_usd"]) for row in attempts)
    report = {
        "status": "complete_three_run_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "successful_models": len(aggregates),
        "successful_runs": len(rows),
        "successful_call_cost_usd": round(successful_cost, 9),
        "all_charged_attempts_cost_usd": round(total_cost, 9),
        "model_aggregates": aggregates,
        "runs": rows,
        "charged_attempts": attempts,
        "event_order_matrix": events,
        "limitations": [
            "Qwen received 21 separate 720p clips; the other models received one lower-bitrate 720p composite because of provider payload limits.",
            "Reasoning settings differed where required to obtain a final answer.",
            "Event-description and evidence quality still require blinded manual review.",
        ],
    }
    (OUTPUT_ROOT / "benchmark_comparison.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    lines = [
        "# Three-Run Four-Model Event-Reconstruction Results",
        "",
        "Each model completed three successful visual-only trials using the same frozen clips, order, prompt, schema, and model-specific input settings.",
        "",
        "| Rank | Model | Grouping F1 | Correct orders per run | Mean order accuracy | Stability (SD) | Mean latency | Total successful cost |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(aggregates, start=1):
        lines.append(
            f"| {rank} | {LABELS[row['model_alias']]} | {row['mean_grouping_pairwise_f1']:.2f} | "
            f"{row['run_order_scores']} out of 7 | {row['mean_exact_order_rate']:.2%} | "
            f"{row['exact_order_rate_stddev']:.2%} | {row['mean_latency_seconds']:.2f}s | "
            f"${row['total_successful_cost_usd']:.6f} |"
        )
    lines.extend(
        [
            "",
            "All models recovered all seven event groups in every run. Chronological ordering was the meaningful discriminator.",
            "",
            "## Event-order consistency",
            "",
            "Each cell shows correct repetitions out of three.",
            "",
            "| Ground-truth event | Qwen3.8-Max | Gemini 3.1 Pro | Gemini 3.8 Flash | Seed 2.1 Turbo |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for event in events:
        lines.append(
            f"| {event['truth_event_id']} | {event['qwen-max']} | {event['gemini-pro']} | "
            f"{event['gemini-flash']} | {event['seed-turbo']} |"
        )
    lines.extend(
        [
            "",
            "## Cost accounting",
            "",
            f"- Twelve successful calls: ${successful_cost:.9f}",
            f"- All charged attempts, including the two earlier truncated outputs: ${total_cost:.9f}",
            "- Pre-inference schema and payload rejections cost $0 and remain preserved in the run folders.",
            "",
            "## Limitations",
            "",
            "- Qwen received 21 separate 720p clips. Gemini and Seed received one lower-bitrate 720p composite due to provider request-size limits.",
            "- Qwen used low reasoning effort, Gemini reported zero reasoning tokens, and Seed required reasoning to be disabled to return an answer.",
            "- Event-description and evidence quality still require blinded manual review.",
            "- The COIN-derived activities are visually distinct, so perfect grouping should not be generalized to more ambiguous smartphone events.",
        ]
    )
    (OUTPUT_ROOT / "PRELIMINARY_RESULTS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "successful_runs": len(rows),
                "successful_call_cost_usd": report["successful_call_cost_usd"],
                "all_charged_attempts_cost_usd": report["all_charged_attempts_cost_usd"],
                "ranking": [
                    {
                        "model": LABELS[row["model_alias"]],
                        "orders_per_run": row["run_order_scores"],
                        "mean_order_accuracy": round(row["mean_exact_order_rate"], 6),
                    }
                    for row in aggregates
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
