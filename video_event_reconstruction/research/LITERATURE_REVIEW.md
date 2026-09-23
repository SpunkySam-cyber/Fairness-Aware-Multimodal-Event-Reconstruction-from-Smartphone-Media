# Literature Review: Multimodal Event Reconstruction from Video

Updated: 13 September 2026

## Scope

This targeted review covers 12 peer-reviewed papers and major benchmarks that inform the current 21-clip pilot. Five papers study procedural or hierarchical video understanding, five study temporal reasoning in video models, and two provide fairness-evaluation methods.

The current pilot asks a model to receive 21 clips in a scrambled order, recover seven three-clip events, place the three clips in the correct order within each event, and describe the resulting hierarchy. The clips were built from COIN source videos and use blind identifiers so that filenames do not reveal the answer.

## Paper comparison

| Paper | Publication | Main contribution | Direct value to this project |
| --- | --- | --- | --- |
| COIN: A Large-Scale Dataset for Comprehensive Instructional Video Analysis | CVPR, June 2019 | Introduces 11,827 instructional videos across 180 tasks and 12 domains with step boundaries and hierarchical labels. | Supplies the source data and ground-truth task/step structure for the pilot. |
| Cross-Task Weakly Supervised Learning From Instructional Videos | CVPR, June 2019 | Introduces CrossTask, with about 4,700 videos, 83 tasks and 374 hours, and learns steps from ordered task lists plus narration. | Shows that shared action components and narration help transfer across related tasks. |
| Ego4D Goal-Step: Toward Hierarchical Understanding of Procedural Activities | NeurIPS 2023 | Adds goal-step-substep annotations for 48,000 segments and 430 hours, plus goal annotations for 2,807 hours. | Provides the clearest precedent for evaluating a hierarchy instead of only individual actions. |
| HT-Step: Aligning Instructional Articles with How-To Videos | NeurIPS 2023 | Provides 122,000 segment annotations over 20,000 narrated cooking videos and 4,958 step labels. | Shows how step text, ASR, temporal boundaries and seen/unseen task splits can be combined. |
| Video-Mined Task Graphs for Keystep Recognition in Instructional Videos | NeurIPS 2023 | Mines probabilistic task graphs from video and uses them to correct initial keystep assignments. | Most directly supports using relations between steps to improve ordering and event structure. |
| Perception Test: A Diagnostic Benchmark for Multimodal Video Models | NeurIPS 2023 | Provides 11,600 short videos with six annotation types for broad perceptual testing. | Demonstrates that human performance remains far above model performance on controlled video reasoning. |
| TempCompass: Do Video LLMs Really Understand Videos? | arXiv, 1 March 2024 | Tests action, speed, direction, attribute change and event order using conflicting clips and four task formats. | Directly motivates an event-order test that cannot be solved from a single frame or filename. |
| TimeChat: A Time-sensitive Multimodal Large Language Model for Long Video Understanding | CVPR, June 2024 | Adds timestamp-aware encoding and a sliding video Q-Former for long-video localization and reasoning. | Supports retaining timestamps and testing video-only against video-plus-transcript inputs. |
| VTimeLLM: Empower LLM to Grasp Video Moments | CVPR, June 2024 | Uses boundary-aware training for temporal grounding and dense event captioning. | Supplies temporal localization and dense-captioning measures that can be adapted to event reconstruction. |
| Video-MME: The First-Ever Comprehensive Evaluation Benchmark of Multi-modal LLMs in Video Analysis | CVPR, June 2025 | Evaluates short, medium and long video understanding with video, subtitles and audio. | Provides a modern multimodal ablation pattern and evidence that performance drops with duration. |
| Casual Conversations: A Dataset for Measuring Fairness in AI | CVPR Workshops, June 2021 | Introduces more than 45,000 consented videos from 3,011 people with age, gender, apparent skin tone and lighting annotations. | Provides a subgroup evaluation method for later fairness testing of video performance. |
| FACET: Fairness in Computer Vision Evaluation Benchmark | ICCV 2023; released 31 August 2023 | Provides 32,000 images containing 50,000 people and intersectional demographic annotations. | Shows how to report performance gaps across individual and intersecting attributes. |

## Main findings

1. Event reconstruction should be evaluated as several separate abilities. The reviewed work distinguishes recognition, temporal localization, ordering, grounding and hierarchy. A single overall score would hide which part failed.
2. Temporal structure provides useful evidence. COIN task consistency, CrossTask component sharing and Video-Mined Task Graphs all improve predictions by using relations between steps instead of treating clips independently.
3. Modern video-language models still have weak temporal reasoning. TempCompass reports poor performance on controlled temporal changes, while Perception Test reports a human score of 91.4% against 45.8% for the evaluated video-QA models.
4. Audio and text are useful but should be tested as separate conditions. Video-MME finds that subtitles and audio improve results. TimeChat also accepts optional transcribed speech. This supports a video-only condition and a video-plus-transcript condition rather than mixing modalities without measurement.
5. Long duration is a separate difficulty. Video-MME reports lower performance as duration increases, and Ego4D Goal-Step finds that goal-level segments require much longer context than step-level segments.
6. Fairness cannot be concluded from overall accuracy. Casual Conversations and FACET report performance by demographic or contextual subgroup and by attribute intersections. The current COIN pilot lacks the controlled demographic annotations required for this analysis.

## Research gap

Inference from this targeted set: the reviewed papers do not directly test one general-purpose multimodal model on all four parts of the proposed task at once:

1. cluster independent shuffled clips into events;
2. recover the order within each event;
3. generate event, step and substep labels; and
4. compare performance across controlled demographic or recording-context groups.

The project can therefore be framed as an evaluation of hierarchical reconstruction from an unordered set of smartphone-style media, rather than as ordinary action recognition or long-video question answering.

## Recommended pilot evaluation

### Experimental conditions

- Keep the same 21 clips and hidden answer key for every model.
- Run at least three prompt variants per model to estimate prompt sensitivity.
- Compare video only with video plus audio/transcript when the model supports both.
- Reset the model context between runs and record model version, date, parameters, prompt, output and failure status.

### Metrics

- Grouping: pairwise precision, recall and F1; Adjusted Rand Index as a secondary measure.
- Ordering: pairwise precedence accuracy, exact three-clip sequence accuracy and Kendall's tau within matched groups.
- Hierarchy and labels: blinded human ratings for event-label correctness, step-label correctness and parent-child consistency.
- End to end: exact event reconstruction rate and a component score that reports grouping, ordering and labeling separately.
- Reliability: mean, standard deviation and bootstrap confidence interval across repeated runs.

### Fairness extension

The 21-clip COIN pilot can establish whether the reconstruction protocol works, but it should not be called a fairness experiment. A later dataset should contain matched events that vary one documented factor at a time, such as lighting, camera motion, skin-tone group, age group, clothing or indoor/outdoor setting. The same metrics should then be reported for every group and intersection, with sample sizes and uncertainty.

## Practical direction

The immediate next experiment should use the existing pilot to compare current accessible multimodal models under one fixed prompt and output schema. The model should return machine-readable JSON containing predicted groups, within-group order, event labels, step labels and evidence. This creates a measurable baseline before expanding the dataset or adding fairness claims.

## Primary sources

1. [COIN](https://openaccess.thecvf.com/content_CVPR_2019/html/Tang_COIN_A_Large-Scale_Dataset_for_Comprehensive_Instructional_Video_Analysis_CVPR_2019_paper.html)
2. [CrossTask](https://openaccess.thecvf.com/content_CVPR_2019/html/Zhukov_Cross-Task_Weakly_Supervised_Learning_From_Instructional_Videos_CVPR_2019_paper.html)
3. [Ego4D Goal-Step](https://proceedings.neurips.cc/paper_files/paper/2023/hash/7a65606fa1a6849450550325832036e5-Abstract-Datasets_and_Benchmarks.html)
4. [HT-Step](https://proceedings.neurips.cc/paper_files/paper/2023/hash/9d58d85bfc041b4f901c62ba37a3f322-Abstract-Datasets_and_Benchmarks.html)
5. [Video-Mined Task Graphs](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d62e65cfdba247e0cd7cac5964f9fbd9-Abstract-Conference.html)
6. [Perception Test](https://proceedings.neurips.cc/paper_files/paper/2023/hash/8540fba4abdc7f9f7a7b1cc6cd60e409-Abstract-Datasets_and_Benchmarks.html)
7. [TempCompass](https://arxiv.org/abs/2403.00476)
8. [TimeChat](https://openaccess.thecvf.com/content/CVPR2024/html/Ren_TimeChat_A_Time-sensitive_Multimodal_Large_Language_Model_for_Long_Video_CVPR_2024_paper.html)
9. [VTimeLLM](https://openaccess.thecvf.com/content/CVPR2024/html/Huang_VTimeLLM_Empower_LLM_to_Grasp_Video_Moments_CVPR_2024_paper.html)
10. [Video-MME](https://openaccess.thecvf.com/content/CVPR2025/html/Fu_Video-MME_The_First-Ever_Comprehensive_Evaluation_Benchmark_of_Multi-modal_LLMs_in_CVPR_2025_paper.html)
11. [Casual Conversations](https://openaccess.thecvf.com/content/CVPR2021W/RCV/html/Hazirbas_Casual_Conversations_A_Dataset_for_Measuring_Fairness_in_AI_CVPRW_2021_paper.html)
12. [FACET](https://ai.meta.com/research/publications/facet-fairness-in-computer-vision-evaluation-benchmark/)

## Review limitation

This is a targeted literature review chosen to guide the pilot, not a systematic review. It does not claim complete coverage of event reconstruction, procedural video understanding or algorithmic fairness research.
