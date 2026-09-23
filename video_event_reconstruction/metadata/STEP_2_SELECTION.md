# Step 2: COIN source-video selection

Selection completed on 2026-09-12.

## Result

- Seven public COIN source videos were selected.
- Each video has three consecutive annotated steps.
- The resulting experiment will contain 21 clips.
- Availability was checked with `yt-dlp --simulate`; no video media was downloaded.
- The activities span furniture assembly, instrument maintenance, cooking, paper craft, home repair, computer repair, and gardening.

## Selection rules

Candidates were required to have valid COIN temporal annotations, three ordered and visually meaningful steps, short clip durations, limited gaps between steps, and a publicly accessible source video.

## Files

- `selected_coin_sources.csv`: source video IDs, URLs, titles, classes, durations, and verification status.
- `selected_coin_clips.csv`: the 21 ground-truth clip boundaries and ordered step labels.

The COIN source annotation is stored at `../data/annotations/COIN.json`. The next step is to download only these seven source videos and verify that the annotated time ranges match the visible actions before extracting the 21 experiment clips.
