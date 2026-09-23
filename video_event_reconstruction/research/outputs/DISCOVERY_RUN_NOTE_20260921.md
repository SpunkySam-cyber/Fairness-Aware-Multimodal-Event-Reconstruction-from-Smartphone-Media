# Event-discovery run on the 509 two-second clips (run note, 21 Sep 2026)

A short record of one run, not a report. Single run, single model, one dataset of 7 events.

## What was tested

The earlier staged run (18 Sep) gave Gemini 3.8 Flash the seven activity names, so it measured sorting into known events. This run gave the model **only the number of events (exactly 7), not what they are**. The clips are the same 509 shuffled COIN clips, in the same 10 shards.

**The caveat that matters:** the model was told there are 7 events. That is weaker than true discovery, where the event count would also be unknown.

## Prompt design (identical for every part, never changed)

- **Stage 1, one call per shard (10 shards, about 51 clips each).** The prompt says the whole experiment has exactly 7 different activities and that the model is not told what they are. The model must (1) group the clips in its part by activity (at most 7 groups), (2) write a one-sentence description per group, (3) give each clip `source_progress` 0-1000. Video in, JSON out, `temperature` 0, reasoning effort low.
- **Stage 2, one text-only call.** The model receives the 70 group descriptions from all parts (no clip IDs, no video) and merges them into exactly 7 events.
- Clips are ordered inside each event by `source_progress`, then scored by the shared evaluator's functions (`scripts/evaluate_two_second_response.py`, unchanged) via a wrapper (below). Event names do not matter to scoring, since predicted events are matched to true events by best overlap.
- The answer key was read only by the scorer, after all model calls, and never sent to any model.

## Results

| Metric | Discovery run (told "7 events") | Earlier run (names supplied) |
|---|---:|---:|
| Grouping accuracy (over all 509) | 97.84% (498/509) | 98.04% (499/509) |
| Pairwise F1 | 0.9614 | 0.9643 |
| Adjusted Rand index | 0.9542 | 0.9576 |
| Mean pairwise ordering accuracy | 76.82% | 76.63% |
| Mean Kendall tau | 0.5364 | 0.5327 |
| Exactly reconstructed events | 0 / 7 | 0 / 7 |
| Measured cost | $0.139742 | $0.128169 |

Per-event pairwise ordering, discovery vs earlier: chair 69.09 / 66.55, guitar 82.49 / 83.89, French fries 75.45 / 74.44, pinwheel 85.22 / 79.80, door knob 72.68 / 82.13, RAM 65.14 / 63.97, mango 87.69 / 85.66 (%). These come from one run each. Differences of a few points should not be read as a real effect.

**Merge stage:** correct. All 70 stage-1 groups were placed in the right event, ten groups per event (one from each part). No merge errors. The seven activities are visually very different, so identifying them was the easy part. The remaining errors are individual clips and fine ordering.

**Misgrouped clips (10, plus 1 dropped):**

| Clip | True event | Placed in | Stage-1 group |
|---|---|---|---|
| C0031 | mango seed | door knob | p01_G7 |
| C0296 | French fries | mango seed | p06_G7 |
| C0298 | mango seed | French fries | p06_G2 |
| C0299 | French fries | chair | p06_G6 |
| C0300 | chair | mango seed | p06_G7 |
| C0301 | mango seed | RAM | p06_G1 |
| C0302 | RAM | guitar | p06_G4 |
| C0303 | guitar | door knob | p06_G5 |
| C0304 | door knob | pinwheel | p06_G3 |
| C0305 | pinwheel | RAM | p06_G1 |
| C0185 (dropped) | French fries | none | not assigned in part 4 |

Nine of the ten misgrouped clips are the same clips the known-names run got wrong (C0031, C0298 to C0305). So most errors look like properties of the clips, not of withholding the names. Nine of the ten sit at IDs C0296 to C0305, the tail of part 6. C0031 (0.833 s) and C0296 (1.417 s) are shorter than the usual 2 s. Why part 6's tail fails is untested.

**Pinwheel check:** the pinwheel event has 30 true clips; the predicted pinwheel event has 30 and 29 are correct. Part 5 described its single pinwheel clip as "Folding an origami figure using orange paper", and the merge still placed it correctly with the other pinwheel groups. The one pinwheel clip missed is C0305 (placed with RAM). Part 6's pinwheel group also contained one door-knob clip (C0304).

## Dropped-clip rule (this run only)

In both part 4 attempts the model omitted `C0185` (attempt 1 also omitted `C0183`). Using the 50/51 retry response, `C0185` was counted as unassigned:

- grouping accuracy counts it as wrong, over all 509 clips
- pairwise F1 and ARI treat it as unassigned
- pairwise ordering accuracy and Kendall tau use assigned clips only
- an event that lost a clip cannot be an exact reconstruction
- reconstructed videos use the assigned clips only
- dropped clips: **1**; assigned clips: **508**

The shared evaluator was not edited. `scripts/score_discovery_with_dropped_clips.py` reuses its functions. On the earlier run it reproduces the earlier metrics exactly, and it refuses anything other than the declared omission. The earlier run had all 509 clips valid, so this rule makes the comparison slightly less like-for-like.

## Every paid call

Cross-check: the OpenRouter key's total usage rose by exactly $0.139742 across this run (read before the first call and after the last), equal to the measured per-call total below. That confirms the 402 attempt was not billed.

| # | Call | Outcome | Cost |
|---|---|---|---:|
| - | Part 1, first attempt | HTTP 402, rejected, **unbilled**: "requires at least $1.00 in balance for video" (key limit). The limit was raised and part 1 re-run. | $0.000000 |
| 1 | Part 1 | validated | $0.013175 |
| 2 | Part 2 | validated | $0.011248 |
| 3 | Part 3 | validated | $0.013146 |
| 4 | Part 4, attempt 1 | **failed validation** (49/51 clips; `C0183`, `C0185` missing) | $0.012561 |
| 5 | Part 4, attempt 2 (the one retry) | **failed validation** (50/51; `C0185` missing) | $0.013172 |
| 6 | Part 5 | validated | $0.013127 |
| 7 | Part 6 | validated | $0.013142 |
| 8 | Part 7 | validated | $0.013348 |
| 9 | Part 8 | validated | $0.009407 |
| 10 | Part 9 | validated | $0.011225 |
| 11 | Part 10 | **failed validation**: model returned a bare top-level list instead of `{"groups": [...]}`; content was complete (50/50) | $0.011015 |
| 12 | Merge | validated | $0.005175 |
| | **Total measured** | | **$0.139742** |

Two failed calls were part 4; one was part 10. Together they cost $0.036748.

## How the failures were handled

- **Part 10: locally recovered, shape only.** No new API call. The validator was changed to accept a bare list of groups (same normalisation the earlier staged script used), the saved response was re-validated, and `groups.json` was written. Parts 1 to 9 were then re-validated under the same final rules. The prompt was never changed.
- **Part 4: no third attempt.** After the second failure the 50/51 response was accepted with `C0185` declared dropped (`accepted_omissions.json`; the prompt still listed all 51 IDs). The first failed attempt is kept in `part_04/failed_attempt_01_stage1/`.
- The validator was also relaxed before the first paid call: whole-number floats accepted as integers, empty groups dropped, non-numeric confidence defaulted to 0.5. Stricter checks (exact ID set, no duplicates, `source_progress` 0-1000, exactly 7 merged events, every group assigned) were unchanged.

## Limits

- One run, one model, temperature 0, 7 events. No error bars; small differences are not evidence of an effect.
- The model was told the event count. Discovery of an unknown number of events is untested.
- Fine ordering is still weak (0/7 exact events, mean Kendall tau 0.54), the same as with names.
- COIN has no demographic annotations, so this run says nothing about fairness.

## Files

Run output: `data/experiment_02_two_second/model_runs/discovery-gemini-flash/run_01/` (`merge_events.json`, `evaluation.json`, `misgrouping_analysis.json`, `accepted_omissions.json`, per-part raw responses, `reconstructed_videos/`). This directory holds media and the answer-key-derived analysis: do not commit or share it. Scripts: `scripts/run_discovery_two_second.py`, `scripts/score_discovery_with_dropped_clips.py`.
