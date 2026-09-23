"""Record the storyboard-based qualitative audit and update the final report."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "data" / "experiment_01"
RUN_ROOT = EXPERIMENT / "model_runs"
OUTPUT = ROOT / "research" / "outputs" / "model_benchmark_20260914"
REPORT_PATH = OUTPUT / "PRELIMINARY_RESULTS.md"
REVIEW_JSON = OUTPUT / "qualitative_review.json"
REVIEW_MD = OUTPUT / "QUALITATIVE_REVIEW.md"
CHART_PATH = OUTPUT / "final_model_comparison.png"
START_MARKER = "<!-- QUALITATIVE_REVIEW_START -->"
END_MARKER = "<!-- QUALITATIVE_REVIEW_END -->"

LABELS = {
    "qwen-max": "Qwen3.8-Max",
    "gemini-flash": "Gemini 3.8 Flash",
    "gemini-pro": "Gemini 3.1 Pro",
    "seed-turbo": "Seed 2.1 Turbo",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def review_overrides() -> dict[tuple[str, int, str], tuple[int, int, str]]:
    """Scores manually assigned after checking start/middle/end storyboards.

    Unlisted events receive 2/2 for description and evidence because the complete
    activity and both adjacent transitions were visually supported.
    """

    issues: dict[tuple[str, int, str], tuple[int, int, str]] = {}
    for run in (1, 2, 3):
        issues[("qwen-max", run, "E06")] = (
            1,
            1,
            "Description focuses on reinstalling the keyboard and omits the central RAM replacement; only part of the evidence aligns with the submitted clip order.",
        )
        issues[("gemini-flash", run, "E01")] = (
            2,
            1,
            "Office-chair description is correct, but V013 is a caster/base step and was incorrectly explained as a later armrest step.",
        )
        issues[("gemini-flash", run, "E05")] = (
            1,
            0,
            "Identifies the door-lock components but describes removal/disassembly; the clips and reference show installation in the opposite direction.",
        )
        issues[("gemini-pro", run, "E01")] = (
            2,
            1,
            "Office-chair description is correct, but the explanation treats the caster/base clip V013 as a final headrest step.",
        )
        issues[("gemini-pro", run, "E05")] = (
            1,
            0,
            "Correctly identifies a door knob, but describes removing it and gives transition evidence opposite to the installation sequence.",
        )
        issues[("seed-turbo", run, "E06")] = (
            1,
            1,
            "Description over-focuses on keyboard installation; the RAM removal-to-install observation is useful but does not support the submitted keyboard-first order.",
        )
        issues[("seed-turbo", run, "E04")] = (
            2,
            1,
            "Paper-pinwheel description is correct, but one transition places folding the intact square after cutting rather than before it.",
        )
        issues[("seed-turbo", run, "E01")] = (
            2,
            1,
            "Office-chair description is correct, but V013 shows installing a caster on the base and is incorrectly treated as a final step.",
        )
        issues[("seed-turbo", run, "E03")] = (
            2,
            0,
            "French-fries description is correct, but the explanation mistakes soaking water for hot oil and raw strips being dried for cooked fries being drained.",
        )

    issues[("gemini-pro", 1, "E06")] = (
        2,
        1,
        "Correctly identifies RAM replacement, but describes V001 as keyboard removal and places it before RAM removal instead of final reassembly.",
    )
    issues[("seed-turbo", 1, "E05")] = (
        2,
        1,
        "Door-lock installation is identified correctly, but the second transition reverses insertion and final tightening.",
    )
    issues[("seed-turbo", 3, "E05")] = (
        2,
        1,
        "Door-lock installation is identified correctly, but V011 tightening is placed before V012 knob insertion.",
    )
    issues[("seed-turbo", 3, "E02")] = (
        2,
        1,
        "Guitar restringing is identified correctly, but the bridge anchoring clip V021 is incorrectly placed after headstock winding.",
    )
    return issues


def collect_reviews() -> list[dict[str, Any]]:
    hierarchy = load(EXPERIMENT / "PRIVATE_expected_hierarchy.json")
    truth_by_group = {
        frozenset(step["blind_id"] for step in event["correct_sequence"]): event
        for event in hierarchy
    }
    overrides = review_overrides()
    rows: list[dict[str, Any]] = []

    for response_path in sorted(RUN_ROOT.glob("*/*/model_response.json")):
        run_dir = response_path.parent
        summary = load(run_dir / "summary.json")
        request = load(run_dir / "request_manifest.json")
        response = load(response_path)
        alias = summary["model_alias"]
        run_number = int(request["run_number"])
        for predicted in response["events"]:
            truth = truth_by_group[frozenset(predicted["ordered_clips"])]
            event_id = truth["event_id"]
            score = overrides.get((alias, run_number, event_id))
            if score is None:
                description_score, evidence_score = 2, 2
                note = (
                    "The event description matches the visible activity and both transition explanations "
                    "are consistent with the adjacent clips."
                )
            else:
                description_score, evidence_score, note = score
            rows.append(
                {
                    "model_alias": alias,
                    "model": LABELS[alias],
                    "run": run_number,
                    "truth_event_id": event_id,
                    "reference_activity": truth["activity_class"],
                    "predicted_event_id": predicted["event_id"],
                    "event_description": predicted["event_description"],
                    "ordered_clips": predicted["ordered_clips"],
                    "ordering_evidence": predicted["ordering_evidence"],
                    "description_score_0_to_2": description_score,
                    "evidence_score_0_to_2": evidence_score,
                    "review_note": note,
                    "source_result_directory": str(run_dir.relative_to(ROOT)),
                }
            )
    rows.sort(key=lambda row: (row["model_alias"], row["run"], row["truth_event_id"]))
    return rows


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["model_alias"]].append(row)
    summaries: list[dict[str, Any]] = []
    for alias, model_rows in grouped.items():
        descriptions = [row["description_score_0_to_2"] for row in model_rows]
        evidence = [row["evidence_score_0_to_2"] for row in model_rows]
        summaries.append(
            {
                "model_alias": alias,
                "model": LABELS[alias],
                "reviewed_event_outputs": len(model_rows),
                "description_points": sum(descriptions),
                "description_points_possible": len(descriptions) * 2,
                "description_accuracy_percent": mean(descriptions) / 2 * 100,
                "evidence_points": sum(evidence),
                "evidence_points_possible": len(evidence) * 2,
                "evidence_quality_percent": mean(evidence) / 2 * 100,
            }
        )
    quantitative = load(OUTPUT / "benchmark_comparison.json")["model_aggregates"]
    order_by_alias = {row["model_alias"]: row["mean_exact_order_rate"] for row in quantitative}
    summaries.sort(key=lambda row: order_by_alias[row["model_alias"]], reverse=True)
    return summaries


def qualitative_section(summaries: list[dict[str, Any]]) -> str:
    lines = [
        START_MARKER,
        "## Structured qualitative review",
        "",
        "All 84 event outputs (four models × three runs × seven events) were checked against start/middle/end storyboards made from the actual clips.",
        "",
        "Scoring rubric:",
        "",
        "- **Event description, 2:** correct complete activity and action direction; **1:** correct object/domain but materially incomplete or reversed; **0:** unrelated or incorrect.",
        "- **Ordering evidence, 2:** both adjacent transitions are visibly supported; **1:** one transition is supported or the explanation is only partly consistent; **0:** both are unsupported or materially contradict the clips.",
        "",
        "| Model | Event-description score | Ordering-evidence score | Reviewed outputs |",
        "|---|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['model']} | {row['description_accuracy_percent']:.2f}% "
            f"({row['description_points']}/{row['description_points_possible']}) | "
            f"{row['evidence_quality_percent']:.2f}% "
            f"({row['evidence_points']}/{row['evidence_points_possible']}) | "
            f"{row['reviewed_event_outputs']} |"
        )
    lines.extend(
        [
            "",
            "### Manual findings",
            "",
            "- **Qwen3.8-Max:** strongest evidence overall. Its repeated RAM output described only keyboard reinstallation and its evidence partly disagreed with its submitted clip order.",
            "- **Gemini 3.8 Flash:** concise and generally well grounded. It repeatedly treated the caster clip as a late chair step and interpreted door-lock installation as disassembly.",
            "- **Gemini 3.1 Pro:** similar recurring chair and door-lock errors; its first RAM run also placed keyboard reassembly before the memory work.",
            "- **Seed 2.1 Turbo:** event names were usually recognizable, but evidence was substantially weaker. It repeatedly mistook water-soaking for frying and reversed several visible prerequisites.",
            "",
            "![Final model comparison](final_model_comparison.png)",
            "",
            "This is a structured single-reviewer audit, not an independent multi-rater human study. A second blinded reviewer would be required for inter-rater reliability claims.",
            END_MARKER,
        ]
    )
    return "\n".join(lines)


def create_chart(summaries: list[dict[str, Any]]) -> None:
    quantitative = load(OUTPUT / "benchmark_comparison.json")["model_aggregates"]
    quantitative_by_alias = {row["model_alias"]: row for row in quantitative}
    labels = [row["model"] for row in summaries]
    grouping = [
        quantitative_by_alias[row["model_alias"]]["mean_grouping_pairwise_f1"] * 100
        for row in summaries
    ]
    ordering = [
        quantitative_by_alias[row["model_alias"]]["mean_exact_order_rate"] * 100
        for row in summaries
    ]
    descriptions = [row["description_accuracy_percent"] for row in summaries]
    evidence = [row["evidence_quality_percent"] for row in summaries]

    x = np.arange(len(labels))
    width = 0.19
    fig, axis = plt.subplots(figsize=(12, 6.8))
    colors = ["#1D4ED8", "#0F766E", "#D97706", "#7C3AED"]
    series = [
        ("Event grouping", grouping),
        ("Chronological order", ordering),
        ("Event description", descriptions),
        ("Ordering evidence", evidence),
    ]
    for index, ((name, values), color) in enumerate(zip(series, colors)):
        bars = axis.bar(x + (index - 1.5) * width, values, width, label=name, color=color)
        axis.bar_label(bars, labels=[f"{value:.0f}" for value in values], padding=3, fontsize=8)

    axis.set_title("Event Reconstruction Benchmark — Three-Run Results", fontsize=16, weight="bold")
    axis.set_ylabel("Score (%)")
    axis.set_ylim(0, 112)
    axis.set_xticks(x)
    axis.set_xticklabels(labels)
    axis.grid(axis="y", alpha=0.22)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(ncols=2, loc="upper center", bbox_to_anchor=(0.5, -0.10), frameon=False)
    fig.text(
        0.5,
        0.01,
        "21 silent clips · 7 events · 3 runs per model · qualitative scores from 84 storyboard-checked outputs",
        ha="center",
        fontsize=9,
        color="#4B5563",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(CHART_PATH, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    rows = collect_reviews()
    if len(rows) != 84:
        raise RuntimeError(f"Expected 84 reviewed event outputs, found {len(rows)}")
    summaries = aggregate(rows)
    review = {
        "status": "complete_structured_single_reviewer_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_outputs": len(rows),
        "rubric": {
            "event_description": {
                "2": "Correct complete activity and action direction.",
                "1": "Correct object/domain but materially incomplete or reversed.",
                "0": "Unrelated or incorrect.",
            },
            "ordering_evidence": {
                "2": "Both adjacent transitions are visibly supported.",
                "1": "One transition is supported or the explanation is only partly consistent.",
                "0": "Both are unsupported or materially contradict the clips.",
            },
        },
        "review_method": "Start/middle/end storyboard inspection of each reference event; one structured reviewer.",
        "model_summaries": summaries,
        "event_reviews": rows,
    }
    REVIEW_JSON.write_text(json.dumps(review, indent=2), encoding="utf-8")

    section = qualitative_section(summaries)
    REVIEW_MD.write_text(
        "# Qualitative Event-Output Review\n\n" + section.replace(START_MARKER + "\n", "").replace("\n" + END_MARKER, "") + "\n",
        encoding="utf-8",
    )
    report = REPORT_PATH.read_text(encoding="utf-8")
    if START_MARKER in report:
        report = report.split(START_MARKER, 1)[0].rstrip()
    REPORT_PATH.write_text(report + "\n\n" + section + "\n", encoding="utf-8")
    create_chart(summaries)
    print(
        json.dumps(
            {
                "reviewed_outputs": len(rows),
                "summaries": summaries,
                "review_json": str(REVIEW_JSON.relative_to(ROOT)),
                "review_markdown": str(REVIEW_MD.relative_to(ROOT)),
                "chart": str(CHART_PATH.relative_to(ROOT)),
                "updated_report": str(REPORT_PATH.relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
