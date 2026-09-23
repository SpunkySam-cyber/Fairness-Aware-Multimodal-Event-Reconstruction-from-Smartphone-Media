# Best Video Models for Multimodal Event Reconstruction in September 2026

## Executive conclusion

For the current experiment—21 shuffled clips representing seven events, with three clips per event—the strongest practical candidates are **Qwen3.8-Max**, **Gemini 3.1 Pro**, **Seed2.1 Pro**, **Gemini 3.8 Flash**, and **InternVideo3-8B-Instruct**. They should not be presented as a universal leaderboard. They are the best-supported shortlist for this particular combination of blind grouping, temporal ordering, and hierarchy generation.

The first model to test should be **Qwen3.8-Max**. Its API accepts as many as 64 videos in one request, so it can receive all 21 clips separately and reason across them without first joining them into one file.[^1] **Gemini 3.1 Pro** is the strongest quality-oriented comparison, but Gemini accepts at most 10 videos in one request. The 21 clips must therefore be combined into one labelled composite video or processed in stages.[^2] **Gemini 3.8 Flash** is the strongest speed-and-cost comparison, while **Seed2.1 Pro** is a promising temporal-reasoning candidate whose published performance figures are currently vendor-reported.[^3] **InternVideo3-8B-Instruct** is the recommended open-weight, reproducible specialist baseline.[^4]

The recommended first benchmark is:

1. Qwen3.8-Max — strongest operational fit for one-call, 21-clip reasoning.
2. Gemini 3.1 Pro — quality-oriented commercial comparison.
3. Gemini 3.8 Flash — lower-cost, fast commercial comparison.
4. InternVideo3-8B-Instruct — reproducible open-weight video specialist.
5. Seed2.1 Pro — add if API access is practical.

Run each model three times with the same shuffled inputs, fixed prompt, and strict JSON response schema. Measure grouping, ordering, hierarchy accuracy, consistency, latency, and cost. This experiment—not a generic benchmark score—will determine which model is best for the project.

## What “best” means for this project

Most video benchmarks ask questions about one video. This project asks a harder combined question:

- infer which separate clips belong to the same event;
- group 21 shuffled clips into seven unknown groups;
- order the three clips within every group;
- construct a hierarchy of event, stage, and clip;
- return machine-readable evidence for every decision.

No reviewed benchmark measures this exact combination. Video-MME-v2, one of the strongest current general video-understanding benchmarks, evaluates long-context perception, temporal dynamics, multi-point evidence aggregation, and reasoning, but not blind cross-video clustering followed by reconstruction.[^5] Consequently, benchmark results are useful screening evidence, not proof that a model will solve this dataset.

The shortlist uses six criteria:

| Criterion | Why it matters |
|---|---|
| Native video input | Frame-only models can miss motion and transitions. |
| Multiple-video support | The model must compare clips, not merely describe each one independently. |
| Temporal reasoning | Ordering depends on actions, state changes, and prerequisites. |
| Long context | All clip evidence and the output hierarchy must fit coherently. |
| Structured output | Strict JSON is needed for automatic scoring. |
| Reproducibility and cost | The study must be repeatable and financially realistic. |

## Recommended model chart

Availability and specifications in this table were checked on 13 September 2026.

| Priority | Model | Access | Native video | Important limit | Best role in this project | Main caution |
|---:|---|---|---|---|---|---|
| 1 | Qwen3.8-Max | Alibaba Model Studio API | Yes | Up to 64 videos; up to 2 hours/2 GB per video request; 1M context | Primary single-call experiment using all 21 separate clips | The visual API does not use the videos' audio tracks |
| 2 | Gemini 3.1 Pro Preview | Gemini API / Vertex AI | Yes, including audio | Maximum 10 videos per prompt; 1M context | Quality-oriented reasoning comparison | Preview status and 10-video limit; use a labelled composite or staged method |
| 3 | Seed2.1 Pro | Doubao / Volcano Engine | Yes | Access and regional availability must be confirmed | High-end temporal and physical-reasoning comparison | Public results are largely vendor-reported |
| 4 | Gemini 3.8 Flash | Gemini API / Vertex AI | Yes, including audio | Maximum 10 videos per prompt; 1M context | Fast, lower-cost native-video comparison | Same composite/staging requirement as Gemini Pro |
| 5 | Qwen3.8-Flash | Alibaba Model Studio API; related open weights available | Yes | Up to 64 videos; 1M context | Economical one-call baseline | Visual endpoint ignores audio |
| 6 | InternVideo3-8B-Instruct | Open weights | Yes | Local GPU and inference setup required | Main reproducible video-specialist baseline | Less convenient than hosted APIs; deployment performance depends on hardware |
| 7 | Cosmos-Reason2-32B or 8B | Open weights | Yes | NVIDIA recommends substantial GPU memory | Physical-action and state-transition baseline | More specialized than a general semantic grouping model |
| 8 | Qwen3.8-Flash-Next | Open weights and hosted derivative | Yes | 125B total parameters, 6B active per token | Strong open generalist if suitable hardware is available | Large storage/runtime footprint despite sparse activation |
| 9 | MiniCPM-o 4.5 | Open weights | Yes, with audio | Approximately 19 GB GPU memory according to its repository | Efficient audio-visual open baseline | Expected accuracy below frontier hosted models |
| 10 | TwelveLabs Pegasus 1.5 + Marengo 3.5 | Specialized video APIs | Yes | Pipeline uses generation plus embeddings rather than one general prompt | Marengo for clip clustering; Pegasus for scene structure and descriptions | Not a like-for-like general VLM comparison |

## Detailed assessment

### 1. Qwen3.8-Max: best operational fit

Qwen3.8-Max is Alibaba's current hosted flagship and accepts text, images, and video with a one-million-token context window.[^6] More importantly, the visual-understanding API permits as many as 64 videos in one request.[^1] This is unusually well matched to the dataset: all 21 clips can retain separate clip IDs and be supplied together.

Recommended use:

- upload the 21 independent clips;
- scramble their API order with a saved random seed;
- ask for seven groups, three clips per group;
- require within-group order, event labels, confidence, and evidence;
- validate the response against a strict JSON schema.

The main experimental caveat is audio. Qwen's visual endpoint does not understand a video's audio track.[^1] This may actually help the first experiment: using visual-only evidence prevents narration or spoken task names from leaking the answer. If audio is part of the intended final system, run a separate audio-visual condition with an Omni model rather than silently comparing audio-enabled Gemini against visual-only Qwen.

### 2. Gemini 3.1 Pro: strongest quality-oriented comparison

Google describes Gemini 3.1 Pro Preview as its most intelligent model for complex tasks and multimodal understanding. It accepts text, image, video, audio, and PDF inputs with a one-million-token input window.[^7] It is the most appropriate Gemini quality baseline even though Gemini 3.8 Flash has a later version number: Flash is optimized around speed and value, whereas Pro is positioned for the most demanding reasoning.

Gemini cannot receive all 21 independent video files in one request because Gemini 2.5 and later models accept no more than 10 videos per prompt.[^2] There are two valid adaptations:

1. **Composite method:** concatenate all shuffled clips into one video and place a persistent visible identifier such as `CLIP_01` on every segment. This preserves a single global reasoning context.
2. **Staged method:** describe or embed clips in batches, then provide all structured clip representations to a final grouping call. This is scalable but tests a pipeline rather than pure end-to-end video reasoning.

The composite method is the fairer first comparison. Gemini normally samples video at approximately one frame per second, although newer models can use agentic video processing to inspect relevant portions dynamically.[^2] Short or fast actions should therefore be checked carefully.

### 3. Seed2.1 Pro: strong temporal candidate

ByteDance positions Seed2.1 as a native multimodal model designed for hour-long video, temporal change, action understanding, and physical motion.[^3] These capabilities align closely with ordering procedural clips. ByteDance reports Video-MME and temporal benchmark results above several contemporary Gemini variants, but these figures are vendor evaluations and have not yet established performance on the project's exact cross-clip reconstruction task.[^3]

Seed2.1 Pro belongs in the full comparison if API access through Doubao or Volcano Engine is straightforward. Before making it part of the mandatory benchmark, confirm regional access, pricing, file limits, data-retention terms, and whether the exact model snapshot can remain pinned for reproducibility.

### 4. Gemini 3.8 Flash: best speed/value comparison

Gemini 3.8 Flash became generally available in September 2026 and supports text, image, video, audio, and PDF input with a 1,048,576-token input context.[^8] Google lists introductory paid pricing of $0.75 per million input tokens and $3.75 per million output tokens through 31 December 2026, after which the published prices increase.[^9]

This makes it a good candidate for prompt development, repeated trials, and ablation studies. It has the same 10-video-per-request constraint as Gemini 3.1 Pro, so it also needs the labelled composite or staged input method. It should not replace the Pro run: testing both reveals whether extra reasoning quality materially improves grouping and ordering.

### 5. Qwen3.8-Flash: best economical multi-video candidate

Qwen3.8-Flash retains the operational advantage of up to 64 videos and a one-million-token context while offering a lower-cost route than the Max model.[^10] Qwen reports that the related Qwen3.8-Flash-Next open model uses a sparse mixture-of-experts architecture with 6B active parameters per token and supports native long-context multimodal processing.[^11]

It is the best economical alternative if Qwen3.8-Max succeeds technically but is unnecessarily expensive. As with Max, its standard visual endpoint is visual-only; the evaluation protocol must state this explicitly.

### 6. InternVideo3-8B-Instruct: best reproducible specialist baseline

InternVideo3-8B-Instruct is an Apache-2.0 open-weight model designed around long-horizon video understanding and agentic reasoning.[^4] Its repository provides weights, evaluation instructions, configurable sampling, and reported results on Video-MME, MLVU, VRBench, and EgoSchema. That makes it more scientifically useful than relying exclusively on closed APIs that may change without notice.

It should be the primary open baseline. Save the exact model revision, runtime library versions, sampling rate, precision, and hardware. Its output may not match the largest hosted models, but it provides a reproducible anchor and allows later fine-tuning.

### 7. Cosmos-Reason2: best open physical-reasoning specialist

NVIDIA's Cosmos-Reason2 family targets physical, spatial, and temporal reasoning over video. Open checkpoints are available in 2B, 8B, and 32B sizes.[^12] The 8B model is a realistic secondary local baseline; NVIDIA's published setup indicates about 32 GB minimum GPU memory for that checkpoint, while the 2B model is lighter.[^12]

Cosmos-Reason2 is especially relevant when ordering depends on physical state transitions—for example, an object being unassembled, assembled, and then used. It is not the best sole model for semantic event grouping, so it is better used as a specialist comparison or verification stage.

### 8. Qwen3.8-Flash-Next: strongest ambitious open generalist

Qwen3.8-Flash-Next is open-weight, natively multimodal, and has a 262K native context extendable to one million tokens.[^11] Its mixture-of-experts design activates only a fraction of its total parameters per token, but the complete model remains large to store and serve. It is valuable for a properly resourced research environment, not the easiest laptop baseline.

Vendor-reported benchmark comparisons are promising, including long-video results, but they should be labelled as developer-reported until independently reproduced. For this project, the hosted Qwen3.8-Flash endpoint is the quicker first test; the open checkpoint becomes useful when reproducibility, adaptation, or private deployment matters.

### 9. MiniCPM-o 4.5 and MiniCPM-V 4.6: efficient open baselines

OpenBMB's current MiniCPM family offers smaller multimodal systems that can run with much less hardware than frontier open models. MiniCPM-o 4.5 supports video and audio jointly, while MiniCPM-V 4.6 is a highly compact image/video model with quantized deployment options.[^13]

These are valuable efficiency baselines, especially for a future laptop or edge prototype. They should not be expected to win the initial accuracy comparison. MiniCPM-o is the more relevant of the two when audio is intentionally included.

### 10. TwelveLabs Pegasus 1.5 and Marengo 3.5: best specialized pipeline

TwelveLabs offers two complementary systems rather than one general chat model. Marengo 3.5 produces embeddings for video, audio, images, text, and documents, making it suitable for similarity-based clustering of the 21 clips.[^14] Pegasus 1.5 generates structured time-based descriptions and scene segmentation.[^15]

A specialized pipeline could use Marengo to propose seven clusters and Pegasus to describe or segment each cluster before a reasoning model orders the clips. This may outperform a single prompt and offers interpretable intermediate data. However, it is a different architecture, so its results should be reported as a pipeline condition rather than directly equated with an end-to-end VLM.

## Models that should not be primary video candidates

### GPT-6 Astra and GPT-5.6 Sol

OpenAI's current flagship GPT-6 Astra has a 1.05-million-token context and accepts images, but its official API model card lists video and audio input as unsupported.[^16] GPT-5.6 Sol has the same limitation.[^17] They can reason over extracted frames or contact sheets, but that is not native video understanding and may lose motion, timing, and brief actions.

GPT-6 Astra can be included as a frame-based control if the research asks whether frontier general reasoning compensates for missing native video. It should not be described as one of the best direct video models.

### Claude Fable 5.1, Opus 5, and Sonnet 5

Anthropic's current Claude family can reason over multiple images, but Anthropic's own guidance handles video by decomposing it into frames.[^18] These models are therefore useful frame-based reasoning controls, not like-for-like native-video candidates. The same warning applies: frame selection becomes part of the pipeline and may determine the result.

### Gemma 4

Gemma 4 is an open multimodal family, but Google's current video guidance treats video as sequences of frames and lists a maximum video duration of roughly 60 seconds at one frame per second.[^19] It may be a useful small open baseline for individual clips, but it is not the preferred system for global reconstruction over the complete set.

### Amazon Nova 2 Lite

Amazon Nova remains a practical cloud multimodal option, but Amazon's video interface is oriented around one video per payload.[^20] It is less naturally suited than Qwen to comparing 21 independent clips in one reasoning context. It can be used as an additional cloud baseline, not as a first-priority model.

## Experimental protocol for the 21 clips

### Input condition

Use a saved random seed to scramble the clips once for the main comparison. Assign neutral IDs (`clip_01` through `clip_21`) that reveal nothing about the source event or correct order. Remove filenames, folder names, and metadata that could leak the answer.

Because some APIs use audio and others do not, the cleanest primary condition is **visual-only**. Mute every clip. If audio matters to the product, add a separately reported **audio-visual** condition using only models that support it. Do not combine those results into a single leaderboard.

For models limited to 10 videos, create one composite video containing the 21 clips in the same shuffled order. Add a persistent clip ID and a short neutral separator between clips. Do not add captions or event labels.

### Required JSON output

Each model should return exactly seven event objects:

```json
{
  "events": [
    {
      "event_id": "event_1",
      "event_label": "short inferred description",
      "ordered_clips": ["clip_07", "clip_02", "clip_19"],
      "ordering_evidence": [
        "visible state or action supporting transition 1",
        "visible state or action supporting transition 2"
      ],
      "confidence": 0.0
    }
  ]
}
```

The prompt must forbid reusing a clip, omitting a clip, or creating groups of sizes other than three. Schema validation should happen before scoring.

### Metrics

| Output | Recommended measure |
|---|---|
| Group membership | Pairwise precision, recall, and F1; Adjusted Rand Index |
| Three-clip order | Exact sequence accuracy; Kendall's tau |
| Event hierarchy | Parent-child edge precision, recall, and F1 |
| Evidence quality | Human rubric: unsupported, weak, adequate, strong |
| Reliability | Valid-JSON rate and constraint-violation count |
| Stability | Agreement across three repeated runs |
| Efficiency | End-to-end latency and actual API cost |

Run three repetitions per model at the lowest practical temperature. Store model name, exact snapshot, date, prompt, clip order, frame rate or media resolution, response, validation errors, latency, and cost.

## Recommended execution order

1. Freeze the 21-clip ground truth and the JSON schema before testing any model.
2. Run Qwen3.8-Max on all 21 separate muted clips.
3. Create the labelled composite and run Gemini 3.1 Pro.
4. Run the same composite with Gemini 3.8 Flash.
5. Run InternVideo3-8B-Instruct with a documented sampling configuration.
6. Add Seed2.1 Pro if access is available.
7. Only after the end-to-end baseline, test a specialized Marengo-plus-reasoning pipeline.

The minimum credible comparison is Qwen3.8-Max, Gemini 3.1 Pro, Gemini 3.8 Flash, and InternVideo3-8B-Instruct. This set covers the best direct multi-video fit, a premium native-video reasoner, a cost-efficient current model, and a reproducible open baseline.

## Research limitations

- Current public leaderboards do not directly test blind grouping plus ordering plus hierarchy generation.
- Several September 2026 releases are too new for broad independent evaluation; developer-reported numbers must be identified as such.
- API models can change. Exact version pins and access dates are essential.
- Frame sampling can hide short actions and materially affect temporal ordering.
- Audio can leak task identity, while removing it may discard valid evidence. The two conditions must be reported separately.
- The current COIN-derived pilot cannot support demographic fairness conclusions. Fairness evaluation requires a separate, balanced dataset with defined demographic and environmental strata.

## Final recommendation

Use **Qwen3.8-Max as the first model**, because it is the only top-tier candidate in this review whose documented interface cleanly accepts all 21 independent clips in one request. Use **Gemini 3.1 Pro** as the primary quality comparison through a labelled composite video, **Gemini 3.8 Flash** as the cost/latency comparison, and **InternVideo3-8B-Instruct** as the open reproducibility baseline. Add **Seed2.1 Pro** once access is confirmed.

The report should not claim in advance that one of these is the best model. It should state that they are the strongest candidates available in September 2026 and that the controlled 21-clip benchmark will identify the best model for this event-reconstruction task.

## Sources

[^1]: Alibaba Cloud, [Qwen visual understanding API documentation](https://help.aliyun.com/en/model-studio/vision-model/).
[^2]: Google, [Video understanding in the Gemini API](https://ai.google.dev/gemini-api/docs/video-understanding).
[^3]: ByteDance Seed, [Seed2.1 model overview](https://seed.bytedance.com/en/seed2_1) and [Seed2.1 release announcement](https://seed.bytedance.com/en/blog/seed2-1-officially-released-advancing-ai-productivity).
[^4]: OpenGVLab, [InternVideo3 official repository and documentation](https://github.com/OpenGVLab/InternVideo/blob/main/InternVideo3/README.md).
[^5]: MME-Benchmarks, [Video-MME-v2 official repository](https://github.com/MME-Benchmarks/Video-MME-v2) and [official leaderboard](https://video-mme-v2.netlify.app/).
[^6]: Alibaba Cloud, [Qwen3.8-Max model documentation](https://help.aliyun.com/en/model-studio/qwen3-8-max).
[^7]: Google, [Gemini 3 model guide](https://ai.google.dev/gemini-api/docs/gemini-3).
[^8]: Google, [Gemini 3.8 Flash model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
[^9]: Google, [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).
[^10]: Alibaba Cloud, [Qwen3.8-Flash model documentation](https://help.aliyun.com/en/model-studio/qwen3-8-flash).
[^11]: Qwen Team, [Qwen3.8-Flash-Next release](https://qwen.ai/blog?id=qwen3.8-flash-next).
[^12]: NVIDIA, [Cosmos-Reason2 official repository](https://github.com/nvidia-cosmos/cosmos-reason2) and [Cosmos-Reason2-8B model card](https://huggingface.co/nvidia/Cosmos-Reason2-8B).
[^13]: OpenBMB, [MiniCPM-V and MiniCPM-o official repository](https://github.com/OpenBMB/MiniCPM-V).
[^14]: TwelveLabs, [Marengo model documentation](https://docs.twelvelabs.io/docs/concepts/models/marengo).
[^15]: TwelveLabs, [Introducing Pegasus 1.5](https://www.twelvelabs.io/blog/introducing-pegasus-1-5).
[^16]: OpenAI, [GPT-6 Astra API model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).
[^17]: OpenAI, [GPT-5.6 Sol API model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
[^18]: Anthropic, [Claude prompt and multimodal input guidance](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables) and [Claude Fable and Mythos 5.1 announcement](https://www.anthropic.com/claude-fable-and-mythos-5-1).
[^19]: Google, [Gemma video capabilities](https://ai.google.dev/gemma/docs/capabilities/vision/video) and [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4).
[^20]: Amazon Web Services, [Amazon Nova video understanding](https://docs.aws.amazon.com/nova/latest/userguide/modalities-video.html) and [Amazon Nova model cards](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards-amazon.html).
