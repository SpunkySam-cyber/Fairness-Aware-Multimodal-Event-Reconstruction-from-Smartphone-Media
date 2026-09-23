# Frozen 21-clip evaluation protocol

This directory defines the model-independent protocol for the first event-reconstruction experiment. It does not contain model outputs or API code.

## Frozen decisions

- Dataset: 21 COIN-derived clips representing seven source events.
- Group size: exactly three clips per event.
- Blind identifiers: `V001` through `V021`.
- Random seed used by the existing pilot: `20260913`.
- Primary condition: visual-only. Audio is removed from every standardized clip.
- Repetitions: three runs per model.
- Prompt: `MODEL_PROMPT.txt`.
- Response contract: `model_response.schema.json`.
- Selected systems: recorded in `model_registry.json`.

The private files one directory above are the scoring truth and must never be uploaded to a model:

- `PRIVATE_answer_key.csv`
- `PRIVATE_expected_hierarchy.json`

## Standardized model inputs

Run `scripts/prepare_model_benchmark.py`. It creates `model_inputs/` containing:

- `individual_visual_only/`: 21 silent, 1280x720, 30 fps clips with persistent blind IDs;
- `all_21_clips_composite_visual_only.mp4`: the same clips concatenated in blind order for APIs limited to fewer than 21 separate videos;
- `all_21_clips_composite_openrouter_visual_only.mp4`: a lower-bitrate 720p transport copy kept below OpenRouter's Google provider request-size limit;
- `input_manifest.csv`: safe upload manifest with hashes and durations;
- `composite_timeline.csv`: start timestamps for each clip in the composite;
- `experiment_manifest.json`: reproducibility settings and source hashes.

Only `model_inputs/`, `MODEL_PROMPT.txt`, and `model_response.schema.json` may be supplied to a model. Never upload either private answer file.

Create the compact OpenRouter transport copy with:

```powershell
python scripts/create_openrouter_composite.py
```

## Scoring

Save each raw response as JSON and run:

```powershell
python scripts/evaluate_model_response.py path\to\response.json
```

The evaluator checks all structural constraints, grouping, ordering, and complete reconstruction. Event descriptions and evidence remain blinded human ratings because their factual quality cannot be established from group membership alone.

## Guarded OpenRouter runner

The runner never makes a paid request unless `--execute` is explicitly supplied.

Check the configured key and current model IDs without running inference:

```powershell
python scripts/run_openrouter_benchmark.py --check-key
python scripts/run_openrouter_benchmark.py --check-models
```

Preview a trial without spending credit:

```powershell
python scripts/run_openrouter_benchmark.py --model qwen-max
```

After approval, execute one trial:

```powershell
python scripts/run_openrouter_benchmark.py --model qwen-max --run-number 1 --execute
```

If a provider rejects a request before inference, preserve that failed folder
and retry the same experimental run with `--attempt 2`. Failed pre-inference
requests do not count as completed repetitions.

Reasoning models can consume the complete output allowance before producing the
JSON answer. When this occurs, preserve the failed attempt and retry with a
documented setting such as `--reasoning-effort low` and a larger output ceiling.
Reasoning tokens are charged as output tokens.

Supported aliases are `qwen-max`, `gemini-pro`, `gemini-flash`, and `seed-turbo`. Seed 2.1 Turbo is explicitly recorded as an OpenRouter substitute for Seed2.1 Pro. InternVideo3 remains a separate local or cloud-GPU experiment.
