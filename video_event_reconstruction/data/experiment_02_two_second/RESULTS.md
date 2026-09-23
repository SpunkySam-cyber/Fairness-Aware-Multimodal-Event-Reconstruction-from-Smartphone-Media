# Two-second clip reconstruction experiment

Date: 2026-09-18

## Fixed dataset

- Seven complete source videos.
- 509 clips after splitting at approximately two seconds.
- One sub-0.5-second source tail was merged into its preceding clip; no source
  frames were discarded.
- Clip identifiers are `C0001` through `C0509`.
- Global shuffle seed: `20260918`.
- Audio was removed from model inputs.
- The private answer key was not included in any model request.

## Input forms

1. One labelled composite video containing all 509 shuffled clips
   (`scrambled_509_clips_labelled.mp4`, 10,659,087 bytes).
2. Ten transport-only labelled parts containing the same global shuffled
   sequence and the same 509 clip IDs (`shards_10`, 10,288,752 bytes total).
   Sharding did not alter the underlying two-second clips or their shuffle.

## API trials

| Model | Attempt | Input | Outcome | Charged cost |
|---|---:|---|---|---:|
| Qwen3.8-Max | 1 | One composite | 12,000 completion tokens were consumed as reasoning; no final answer | $0.316486 |
| Gemini 3.8 Flash | 1 | One composite | Provider rejected the request as `INVALID_ARGUMENT` before inference | $0.000000 |
| Gemini 3.8 Flash | 2 | Ten parts | Provider rejected the request as `INVALID_ARGUMENT` before inference | $0.000000 |
| Qwen3.8-Max | 3 | One composite | Reached the 30,000-token limit; returned truncated JSON and invalid IDs above `C0509` | $0.424472 |

Total measured charge for this experiment so far: **$0.740958**.

## Current conclusion

The 509-clip dataset and evaluator are valid, but neither tested one-shot route
produced a reconstructable answer. Gemini's OpenRouter/Google route rejected the
long inline input before inference. Qwen accepted the video but could not finish
a valid 509-clip hierarchy within either a 12,000- or 30,000-token generation
allowance. Its second response also violated the allowed ID range despite the
structured-output request.

Therefore no model-generated reconstructed videos are claimed for this run.
Generating videos directly from the private answer key would be an oracle output,
not a model result, and is intentionally not reported as success.

## Recommended next experiment

Keep the two-second clips, but use a staged reconstruction protocol:

1. Send each short transport part separately for clip-level visual labelling and
   local grouping.
2. Consolidate the local groups into seven global events.
3. Send one predicted event at a time for chronological ordering.
4. Concatenate the predicted order and score it against the untouched private
   answer key.

This changes only the inference strategy, not the 509-clip dataset.

## Staged reconstruction result

The recommended staged protocol was subsequently implemented with Gemini 3.8
Flash. The ten transport parts were processed independently. To keep event names
consistent across calls, the seven known activity categories were supplied to the
model. For each clip, Gemini predicted a category and a normalized position in
the source event. The script combined these predictions, ordered clips by the
predicted position, rendered seven videos, and evaluated them against the private
answer key.

- Constraint validation: passed; all 509 clip IDs were submitted exactly once.
- Correct event assignments: 499/509 (**98.04%**).
- Pairwise grouping F1: **96.43%**.
- Adjusted Rand index: **95.76%**.
- Mean pairwise ordering accuracy: **76.63%**.
- Mean Kendall tau: **0.5327**.
- Exact reconstructed events: **0/7**.
- Full reconstruction exact: **false**.
- Measured staged API cost: **$0.128169**.

Seven model-predicted videos were generated under
`model_runs/staged-gemini-flash/run_01/reconstructed_videos`.

This result shows that short-part classification largely solves event grouping,
but scalar visual-progress estimates are not sufficient for exact two-second
clip ordering. The videos are reconstructed model outputs, but they are not the
same as the originals and must not be reported as exact reconstructions.
