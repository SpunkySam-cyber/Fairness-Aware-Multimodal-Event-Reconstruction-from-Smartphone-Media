import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = path.resolve(import.meta.dirname, "..");
const outputDir = path.join(projectRoot, "outputs", "literature_review_20260913");
const outputPath = path.join(outputDir, "literature_review_comparison.xlsx");
const previewDir = path.join(outputDir, "previews");

const papers = [
  {
    id: 1,
    theme: "Procedural hierarchy",
    paper: "COIN: A Large-Scale Dataset for Comprehensive Instructional Video Analysis",
    publication: "CVPR, June 2019",
    problem: "Large-scale instructional-video analysis with hierarchical task and step annotations.",
    dataset: "COIN: 11,827 videos; 180 tasks; 12 domains; 476 hours; step descriptions and temporal boundaries.",
    models: "R-C3D, SSN and task-consistency variants for localization; action-segmentation baselines including TCFPN-ISBA.",
    design: "Supervised step localization and action segmentation; compares standard detectors with task-consistency constraints.",
    metrics: "mAP and mAR at temporal IoU 0.1-0.5; frame accuracy for segmentation.",
    findings: "Task consistency improved localization. For SSN Fusion at IoU 0.5, mAP rose from 8.12 to 9.05 and mAR from 26.79 to 29.79.",
    limitations: "Fixed task taxonomy; YouTube availability changes; does not test free-form grouping of independent files or fairness.",
    relevance: "Direct source of the 21 pilot clips and their task-step ground truth.",
    priority: "Essential",
    source: "https://openaccess.thecvf.com/content_CVPR_2019/html/Tang_COIN_A_Large-Scale_Dataset_for_Comprehensive_Instructional_Video_Analysis_CVPR_2019_paper.html",
  },
  {
    id: 2,
    theme: "Procedural hierarchy",
    paper: "Cross-Task Weakly Supervised Learning From Instructional Videos",
    publication: "CVPR, June 2019",
    problem: "Learning task steps with weak supervision from narration and ordered step lists while sharing knowledge across tasks.",
    dataset: "CrossTask: about 4,700 videos; 83 tasks; 374 hours; 18 primary and 65 related tasks.",
    models: "Component-sharing model; task-specific step model; DIFFRAC baseline; RGB I3D, ResNet-152 and audio VGG features.",
    design: "Tests task-specific learning, cross-task sharing and parsing of previously unseen tasks.",
    metrics: "Step recall for the 18 primary tasks; F1 on a smaller five-task comparison.",
    findings: "The full component-sharing model reached 22.4% average recall versus 18.6% for the task-specific model and improved 17 of 18 tasks.",
    limitations: "Assumes an ordered step list and instructional narration; annotations focus on primary tasks; not a shuffled multi-event test.",
    relevance: "Supports using shared action components and narration to connect related clips and transfer to new events.",
    priority: "High",
    source: "https://openaccess.thecvf.com/content_CVPR_2019/html/Zhukov_Cross-Task_Weakly_Supervised_Learning_From_Instructional_Videos_CVPR_2019_paper.html",
  },
  {
    id: 3,
    theme: "Procedural hierarchy",
    paper: "Ego4D Goal-Step: Toward Hierarchical Understanding of Procedural Activities",
    publication: "NeurIPS 2023",
    problem: "Recognizing goals, steps and substeps and their long-term hierarchical and temporal relationships.",
    dataset: "Ego4D Goal-Step: 48,000 step segments covering 430 hours; goal annotations for 2,807 hours.",
    models: "ActionFormer, EgoOnly, LSTR and VSLNet using Omnivore or egocentric video features.",
    design: "Goal/step localization, online detection, open-vocabulary grounding and hierarchy ablations.",
    metrics: "Detection mAP over tIoU 0.1-0.5; per-frame mAP; Recall@1 at IoU 0.3.",
    findings: "Step localization remained difficult: best test mAP was 14.0. Joint step-substep training improved grounding, but goal-step integration remained unresolved.",
    limitations: "Egocentric single-stream video; substantial training requirements; does not cluster separate unordered media files.",
    relevance: "Best precedent for a goal-event-step-substep hierarchy and for reporting each hierarchy level separately.",
    priority: "Essential",
    source: "https://proceedings.neurips.cc/paper_files/paper/2023/hash/7a65606fa1a6849450550325832036e5-Abstract-Datasets_and_Benchmarks.html",
  },
  {
    id: 4,
    theme: "Procedural hierarchy",
    paper: "HT-Step: Aligning Instructional Articles with How-To Videos",
    publication: "NeurIPS 2023",
    problem: "Grounding article steps in narrated how-to videos, including steps and tasks unseen during training.",
    dataset: "HT-Step: 122,000 segment annotations; 20,000 narrated cooking videos; about 2,300 hours; 4,958 unique steps.",
    models: "ActionFormer, ActionFormer-T, UMT, VINA and MT+BCE with S3D/TimeSformer video and Word2Vec/CLIP/MPNet text features.",
    design: "Strongly supervised article grounding with seen and unseen splits; tests weak ASR pretraining followed by supervised fine-tuning.",
    metrics: "Article-grounding mAP at temporal IoU 0.3, 0.5 and 0.7 and averaged across thresholds.",
    findings: "ASR pretraining plus HT-Step labels produced the best average results: 30.2 mAP on seen tasks and 20.4 on unseen tasks.",
    limitations: "Cooking-focused; depends on instructional articles and a step taxonomy; 73% of labels are partial matches.",
    relevance: "Shows how transcripts, textual step descriptions and precise temporal labels can complement each other.",
    priority: "High",
    source: "https://proceedings.neurips.cc/paper_files/paper/2023/hash/9d58d85bfc041b4f901c62ba37a3f322-Abstract-Datasets_and_Benchmarks.html",
  },
  {
    id: 5,
    theme: "Procedural hierarchy",
    paper: "Video-Mined Task Graphs for Keystep Recognition in Instructional Videos",
    publication: "NeurIPS 2023",
    problem: "Learning probabilistic relations between steps directly from video and using them to correct keystep predictions.",
    dataset: "COIN and CrossTask for recognition; HowTo100M for representation learning.",
    models: "Video-mined task graph; VideoCLIP, DistantSupervision, linear-step, autoregressive, Drop-DTW and Graph2Vid baselines.",
    design: "Zero-shot keystep recognition with text, video and video-text inputs; downstream step, task and forecasting evaluations.",
    metrics: "Frame-wise accuracy and IoU for segmentation; accuracy for classification and forecasting.",
    findings: "The graph improved all modality variants, with gains up to 6.5 percentage points, and improved downstream representations.",
    limitations: "Operates within a keystep vocabulary and instructional-video distributions; does not generate arbitrary event clusters.",
    relevance: "Most direct evidence that a learned graph can repair locally plausible but globally inconsistent step assignments.",
    priority: "Essential",
    source: "https://proceedings.neurips.cc/paper_files/paper/2023/hash/d62e65cfdba247e0cd7cac5964f9fbd9-Abstract-Conference.html",
  },
  {
    id: 6,
    theme: "Temporal reasoning",
    paper: "Perception Test: A Diagnostic Benchmark for Multimodal Video Models",
    publication: "NeurIPS 2023",
    problem: "Broad diagnostic testing of multimodal perception under controlled real-world video scenarios.",
    dataset: "11,600 videos; 23-second average; about 100 participants; object/point tracks, action/sound segments and video QA.",
    models: "Tracking and detection baselines plus ActionFormer, Flamingo and SeViLA for temporal and video-QA tasks.",
    design: "Zero-shot, few-shot and limited-fine-tuning transfer tests across six annotation types.",
    metrics: "Task-specific IoU/Jaccard, mAP, HOTA and video-QA accuracy; combined diagnostic score.",
    findings: "Human video-QA performance was 91.4% versus 45.8% for the evaluated model baseline.",
    limitations: "Mostly short, staged diagnostic scenes; separate tasks rather than end-to-end reconstruction.",
    relevance: "Supports controlled tests, human baselines and failure analysis instead of relying only on natural videos.",
    priority: "High",
    source: "https://proceedings.neurips.cc/paper_files/paper/2023/hash/8540fba4abdc7f9f7a7b1cc6cd60e409-Abstract-Datasets_and_Benchmarks.html",
  },
  {
    id: 7,
    theme: "Temporal reasoning",
    paper: "TempCompass: Do Video LLMs Really Understand Videos?",
    publication: "arXiv, 1 March 2024",
    problem: "Measuring whether video LLMs understand temporal changes rather than exploiting single frames or language priors.",
    dataset: "7,540 instructions across action, speed, direction, attribute change and event-order aspects using conflicting clips.",
    models: "Eight video LLMs, including Video-LLaVA, LLaMA-VID and VideoChat2; three image LLMs; GPT-3.5-based answer evaluator.",
    design: "Multiple choice, yes/no, caption matching and caption generation on controlled conflicting video pairs or triplets.",
    metrics: "Accuracy and answer-match rate by temporal aspect and task format.",
    findings: "Evaluated video LLMs showed weak temporal perception, and several failed to consistently exceed random baselines across formats.",
    limitations: "Short stock clips and benchmark-specific questions; model set reflects 2024 availability; no event hierarchy.",
    relevance: "Directly motivates testing event order with clips that share static content but differ temporally.",
    priority: "Essential",
    source: "https://arxiv.org/abs/2403.00476",
  },
  {
    id: 8,
    theme: "Temporal reasoning",
    paper: "TimeChat: A Time-sensitive Multimodal Large Language Model for Long Video Understanding",
    publication: "CVPR, June 2024",
    problem: "Timestamp-aware localization and reasoning over videos of different durations.",
    dataset: "TimeIT: 125,000 instruction-tuning instances across six temporal tasks; evaluated on YouCook2, QVHighlights and Charades-STA.",
    models: "TimeChat with timestamp-aware frame encoder, sliding video Q-Former and LLM; compared with prior video LLMs.",
    design: "Zero-shot dense captioning, temporal grounding and highlight detection; optional transcript input.",
    metrics: "F1 and CIDEr; HIT@1 and mAP; Recall@1 at temporal IoU thresholds.",
    findings: "Reported gains include +9.2 F1 and +2.8 CIDEr on YouCook2, +5.8 HIT@1 on QVHighlights and +27.5 R@1 at IoU 0.5 on Charades-STA.",
    limitations: "Focuses on moments within one video, not grouping separate files; practical access may require local model deployment.",
    relevance: "Supports timestamped evidence and a transcript ablation for long or ambiguous event clips.",
    priority: "High",
    source: "https://openaccess.thecvf.com/content/CVPR2024/html/Ren_TimeChat_A_Time-sensitive_Multimodal_Large_Language_Model_for_Long_Video_CVPR_2024_paper.html",
  },
  {
    id: 9,
    theme: "Temporal reasoning",
    paper: "VTimeLLM: Empower LLM to Grasp Video Moments",
    publication: "CVPR, June 2024",
    problem: "Teaching a video LLM to identify fine-grained temporal boundaries and describe multiple events.",
    dataset: "Training combines image-text alignment, boundary-aware multi-event videos and instruction data; evaluation uses ActivityNet Captions and Charades-STA.",
    models: "VTimeLLM-7B and VTimeLLM-13B built on Vicuna 1.5 with three-stage training and LoRA.",
    design: "Temporal video grounding and dense video captioning against video-LLM baselines.",
    metrics: "mIoU; Recall@1 at IoU 0.3, 0.5 and 0.7; SODA_c, CIDEr and METEOR.",
    findings: "VTimeLLM-7B substantially outperformed similarly sized video LLMs on temporal grounding and dense captioning; scaling to 13B gave smaller additional gains.",
    limitations: "Designed for moments inside one video; results depend on specialized staged training and generated instruction data.",
    relevance: "Provides metrics for temporal boundaries and event captions, useful when the pilot expands beyond three fixed clips.",
    priority: "Medium",
    source: "https://openaccess.thecvf.com/content/CVPR2024/html/Huang_VTimeLLM_Empower_LLM_to_Grasp_Video_Moments_CVPR_2024_paper.html",
  },
  {
    id: 10,
    theme: "Temporal reasoning",
    paper: "Video-MME: The First-Ever Comprehensive Evaluation Benchmark of Multi-modal LLMs in Video Analysis",
    publication: "CVPR, June 2025",
    problem: "Comprehensive evaluation of multimodal LLMs across video duration, domain and input modality.",
    dataset: "Video-MME: videos from 11 seconds to one hour; six domains and 30 subfields; video, subtitle and audio conditions.",
    models: "Commercial and open models including Gemini 1.5 Pro/Flash, GPT-4o, GPT-4V, VITA, VILA and LLaVA-NeXT-Video.",
    design: "Multiple-choice evaluation by duration and domain, with and without subtitle/audio inputs.",
    metrics: "Average answer accuracy overall and by duration, domain and modality condition.",
    findings: "Gemini 1.5 Pro scored 75.0% and GPT-4o 71.9%. Subtitles/audio helped, while performance declined as duration increased.",
    limitations: "Multiple-choice QA does not evaluate clustering, ordering or generated hierarchy; model rankings age quickly.",
    relevance: "Provides the strongest template for model comparison, duration analysis and multimodal ablations.",
    priority: "Essential",
    source: "https://openaccess.thecvf.com/content/CVPR2025/html/Fu_Video-MME_The_First-Ever_Comprehensive_Evaluation_Benchmark_of_Multi-modal_LLMs_in_CVPR_2025_paper.html",
  },
  {
    id: 11,
    theme: "Fairness evaluation",
    paper: "Casual Conversations: A Dataset for Measuring Fairness in AI",
    publication: "CVPR Workshops, June 2021",
    problem: "Measuring model robustness across age, gender, apparent skin tone and lighting in consented videos.",
    dataset: "More than 45,000 videos from 3,011 participants across multiple U.S. states; about 15 videos per person.",
    models: "State-of-the-art apparent age and gender classification systems.",
    design: "Reports classification behavior across self-reported age/gender, annotated apparent skin tone and low-light conditions.",
    metrics: "Classification accuracy and error patterns disaggregated by demographic and lighting groups.",
    findings: "The evaluations reveal that aggregate performance can conceal substantial variation across participant groups and conditions.",
    limitations: "Speaking-face videos and U.S.-focused collection; fairness attributes are limited; no event or temporal reconstruction task.",
    relevance: "Provides a consent-aware protocol for subgroup reporting in a later smartphone-video fairness dataset.",
    priority: "High",
    source: "https://openaccess.thecvf.com/content/CVPR2021W/RCV/html/Hazirbas_Casual_Conversations_A_Dataset_for_Measuring_Fairness_in_AI_CVPRW_2021_paper.html",
  },
  {
    id: 12,
    theme: "Fairness evaluation",
    paper: "FACET: Fairness in Computer Vision Evaluation Benchmark",
    publication: "ICCV 2023; released 31 August 2023",
    problem: "Standardized intersectional fairness evaluation for common person-related computer-vision tasks.",
    dataset: "FACET: 32,000 images; 50,000 people; 52 person classes; expert labels for demographic and other attributes.",
    models: "State-of-the-art classification, object detection, instance segmentation and visual-grounding models.",
    design: "Compares task performance across single demographic attributes and intersections of multiple attributes.",
    metrics: "Task metrics such as classification accuracy, detection/segmentation performance and subgroup performance gaps.",
    findings: "Models across all four task families exhibit performance disparities across demographic attributes and their intersections.",
    limitations: "Still images, perceived attributes and evaluation-only licensing; no temporal or multimodal event reasoning.",
    relevance: "Provides the clearest reporting pattern for intersectional performance gaps and sample-size disclosure.",
    priority: "High",
    source: "https://ai.meta.com/research/publications/facet-fairness-in-computer-vision-evaluation-benchmark/",
  },
];

const workbook = Workbook.create();
const matrix = workbook.worksheets.add("Literature Matrix");
const synthesis = workbook.worksheets.add("Research Synthesis");
matrix.showGridLines = false;
synthesis.showGridLines = false;
matrix.tabColor = "#244A64";
synthesis.tabColor = "#4F7A8B";

const font = "Arial";
const navy = "#244A64";
const blue = "#DCEAF2";
const paleBlue = "#EEF5F8";
const amber = "#FFF1CC";
const green = "#E2F0D9";
const gray = "#667085";
const lightGray = "#E6E9ED";

matrix.getRange("A2:N2").merge();
matrix.getRange("A2").values = [["Literature review: multimodal event reconstruction from video"]];
matrix.getRange("A2").format.font = { name: font, size: 15, bold: true, color: "#172B3A" };
matrix.getRange("A3:N3").merge();
matrix.getRange("A3").values = [["Twelve papers selected to guide the 21-clip grouping, ordering, hierarchy and fairness study. Updated 13 September 2026."]];
matrix.getRange("A3").format.font = { name: font, size: 10, italic: true, color: gray };
matrix.getRange("A4:N4").format.borders = { bottom: { style: "thin", color: navy } };

const headers = ["ID", "Theme", "Paper", "Publication", "Research problem", "Dataset and scale", "Models or methods", "Experimental design", "Metrics", "Main findings", "Limitations", "Relevance to this project", "Priority", "Primary source"];
matrix.getRange("A6:N6").values = [headers];
matrix.getRange("A6:N6").format = {
  fill: navy,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideVertical: { style: "thin", color: "#FFFFFF" }, bottom: { style: "thin", color: navy } },
};
matrix.getRange("A6:N6").format.rowHeight = 34;

const rows = papers.map((p) => [p.id, p.theme, p.paper, p.publication, p.problem, p.dataset, p.models, p.design, p.metrics, p.findings, p.limitations, p.relevance, p.priority, p.source]);
matrix.getRange("A7:N18").values = rows;
matrix.getRange("A7:N18").format.font = { name: font, size: 10, color: "#1F2933" };
matrix.getRange("A7:N18").format.verticalAlignment = "top";
matrix.getRange("A7:N18").format.wrapText = true;
matrix.getRange("A7:N18").format.borders = { insideHorizontal: { style: "thin", color: lightGray }, bottom: { style: "thin", color: lightGray } };
for (let row = 7; row <= 18; row += 2) matrix.getRange(`A${row}:N${row}`).format.fill = "#F8FAFB";
matrix.getRange("A7:A18").format.horizontalAlignment = "center";
matrix.getRange("D7:D18").format.horizontalAlignment = "center";
matrix.getRange("M7:M18").format.horizontalAlignment = "center";
matrix.getRange("M7:M18").conditionalFormats.add("containsText", { text: "Essential", format: { fill: green, font: { bold: true, color: "#315B2A" } } });
matrix.getRange("M7:M18").conditionalFormats.add("containsText", { text: "High", format: { fill: blue, font: { bold: true, color: navy } } });
matrix.getRange("M7:M18").conditionalFormats.add("containsText", { text: "Medium", format: { fill: amber, font: { bold: true, color: "#7A5714" } } });
matrix.getRange("A6:N18").format.verticalAlignment = "top";
matrix.freezePanes.freezeRows(6);
matrix.freezePanes.freezeColumns(3);

const widths = [6, 20, 38, 22, 34, 39, 39, 37, 31, 43, 37, 39, 12, 48];
for (let col = 0; col < widths.length; col++) matrix.getRangeByIndexes(0, col, 18, 1).format.columnWidth = widths[col];
for (let row = 7; row <= 18; row++) matrix.getRange(`A${row}:N${row}`).format.rowHeight = 100;
matrix.getRange("N7:N18").format.font = { name: font, size: 9, color: "#1E5A7A" };
matrix.getRange("A2:N18").format.verticalAlignment = "top";
matrix.tables.add("A6:N18", true, "LiteratureMatrixTable").style = "TableStyleMedium2";

synthesis.getRange("A2:H2").merge();
synthesis.getRange("A2").values = [["Research synthesis and pilot implications"]];
synthesis.getRange("A2").format.font = { name: font, size: 15, bold: true, color: "#172B3A" };
synthesis.getRange("A3:H3").merge();
synthesis.getRange("A3").values = [["The literature supports a component-based evaluation of grouping, temporal order, hierarchy and later fairness analysis."]];
synthesis.getRange("A3").format.font = { name: font, size: 10, italic: true, color: gray };
synthesis.getRange("A4:H4").format.borders = { bottom: { style: "thin", color: navy } };

synthesis.getRange("A6:B6").values = [["Review coverage", "Count"]];
synthesis.getRange("A7:A10").values = [["Papers reviewed"], ["Procedural hierarchy"], ["Temporal reasoning"], ["Fairness evaluation"]];
synthesis.getRange("B7").formulas = [["=COUNTA('Literature Matrix'!C7:C18)"]];
synthesis.getRange("B8").formulas = [["=COUNTIFS('Literature Matrix'!B7:B18,A8)"]];
synthesis.getRange("B8:B10").fillDown();
synthesis.getRange("A6:B10").format.font = { name: font, size: 10 };
synthesis.getRange("A6:B6").format = { fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", borders: { insideVertical: { style: "thin", color: "#FFFFFF" } } };
synthesis.getRange("B7:B10").format.horizontalAlignment = "right";
synthesis.getRange("A7:B10").format.borders = { insideHorizontal: { style: "thin", color: lightGray }, bottom: { style: "thin", color: lightGray } };

synthesis.getRange("D6:E6").values = [["Reading priority", "Count"]];
synthesis.getRange("D7:D9").values = [["Essential"], ["High"], ["Medium"]];
synthesis.getRange("E7").formulas = [["=COUNTIFS('Literature Matrix'!M7:M18,D7)"]];
synthesis.getRange("E7:E9").fillDown();
synthesis.getRange("D6:E9").format.font = { name: font, size: 10 };
synthesis.getRange("D6:E6").format = { fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", borders: { insideVertical: { style: "thin", color: "#FFFFFF" } } };
synthesis.getRange("E7:E9").format.horizontalAlignment = "right";
synthesis.getRange("D7:E9").format.borders = { insideHorizontal: { style: "thin", color: lightGray }, bottom: { style: "thin", color: lightGray } };

const sections = [
  [12, "Key evidence", "Temporal structure helps correct local mistakes; current video LLMs still struggle with controlled temporal reasoning; audio and transcripts can improve results; duration increases difficulty."],
  [16, "Research gap", "Inference from this targeted review: no reviewed paper jointly tests blind clustering of independent clips, within-cluster ordering, generated hierarchy and fairness breakdown in one general-purpose multimodal model evaluation."],
  [20, "Immediate experiment", "Use the existing 21 blind clips. Run each accessible model with a fixed JSON schema, at least three prompt variants, and separate video-only and video-plus-transcript conditions when supported."],
  [24, "Recommended metrics", "Grouping: pairwise precision, recall and F1 plus Adjusted Rand Index. Ordering: pairwise precedence, exact three-clip sequence and Kendall's tau. Hierarchy: blinded human ratings. Report each component separately."],
  [28, "Fairness boundary", "The current COIN pilot cannot support a fairness claim because it lacks controlled demographic labels. Add matched demographic and recording-context groups only after the reconstruction protocol is stable."],
];
for (const [row, title, body] of sections) {
  synthesis.getRange(`A${row}:H${row}`).merge();
  synthesis.getRange(`A${row}`).values = [[title]];
  synthesis.getRange(`A${row}`).format = { fill: blue, font: { name: font, size: 11, bold: true, color: navy }, borders: { bottom: { style: "thin", color: "#AFC7D4" } } };
  synthesis.getRange(`A${row + 1}:H${row + 2}`).merge();
  synthesis.getRange(`A${row + 1}`).values = [[body]];
  synthesis.getRange(`A${row + 1}`).format = { font: { name: font, size: 10, color: "#1F2933" }, wrapText: true, verticalAlignment: "top" };
  synthesis.getRange(`A${row + 1}:H${row + 2}`).format.rowHeight = 28;
}
synthesis.getRange("A33:H33").merge();
synthesis.getRange("A33").values = [["Scope note"]];
synthesis.getRange("A33").format = { fill: paleBlue, font: { name: font, size: 10, bold: true, color: navy } };
synthesis.getRange("A34:H35").merge();
synthesis.getRange("A34").values = [["This is a targeted review for experiment design, not a systematic review. The full paper details and primary links are in the Literature Matrix sheet."]];
synthesis.getRange("A34").format = { font: { name: font, size: 10, italic: true, color: gray }, wrapText: true, verticalAlignment: "top" };

for (let col = 0; col < 8; col++) synthesis.getRangeByIndexes(0, col, 35, 1).format.columnWidth = col === 0 ? 24 : 16;
synthesis.getRange("A1:H35").format.font.name = font;
synthesis.getRange("A1:H35").format.verticalAlignment = "top";

workbook.recalculate();
await fs.mkdir(previewDir, { recursive: true });
const matrixPreview = await workbook.render({ sheetName: "Literature Matrix", range: "A1:N18", scale: 0.8, format: "png" });
await fs.writeFile(path.join(previewDir, "literature_matrix.png"), new Uint8Array(await matrixPreview.arrayBuffer()));
const synthesisPreview = await workbook.render({ sheetName: "Research Synthesis", range: "A1:H35", scale: 1, format: "png" });
await fs.writeFile(path.join(previewDir, "research_synthesis.png"), new Uint8Array(await synthesisPreview.arrayBuffer()));

const keyCheck = await workbook.inspect({ kind: "table", range: "Research Synthesis!A1:H35", include: "values,formulas", tableMaxRows: 35, tableMaxCols: 8, maxChars: 12000 });
console.log(keyCheck.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewDir, papers: papers.length }, null, 2));
