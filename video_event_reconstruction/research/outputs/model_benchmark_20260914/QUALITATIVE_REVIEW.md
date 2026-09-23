# Qualitative Event-Output Review

## Structured qualitative review

All 84 event outputs (four models × three runs × seven events) were checked against start/middle/end storyboards made from the actual clips.

Scoring rubric:

- **Event description, 2:** correct complete activity and action direction; **1:** correct object/domain but materially incomplete or reversed; **0:** unrelated or incorrect.
- **Ordering evidence, 2:** both adjacent transitions are visibly supported; **1:** one transition is supported or the explanation is only partly consistent; **0:** both are unsupported or materially contradict the clips.

| Model | Event-description score | Ordering-evidence score | Reviewed outputs |
|---|---:|---:|---:|
| Qwen3.8-Max | 92.86% (39/42) | 92.86% (39/42) | 21 |
| Gemini 3.8 Flash | 92.86% (39/42) | 78.57% (33/42) | 21 |
| Gemini 3.1 Pro | 92.86% (39/42) | 76.19% (32/42) | 21 |
| Seed 2.1 Turbo | 92.86% (39/42) | 57.14% (24/42) | 21 |

### Manual findings

- **Qwen3.8-Max:** strongest evidence overall. Its repeated RAM output described only keyboard reinstallation and its evidence partly disagreed with its submitted clip order.
- **Gemini 3.8 Flash:** concise and generally well grounded. It repeatedly treated the caster clip as a late chair step and interpreted door-lock installation as disassembly.
- **Gemini 3.1 Pro:** similar recurring chair and door-lock errors; its first RAM run also placed keyboard reassembly before the memory work.
- **Seed 2.1 Turbo:** event names were usually recognizable, but evidence was substantially weaker. It repeatedly mistook water-soaking for frying and reversed several visible prerequisites.

![Final model comparison](final_model_comparison.png)

This is a structured single-reviewer audit, not an independent multi-rater human study. A second blinded reviewer would be required for inter-rater reliability claims.
