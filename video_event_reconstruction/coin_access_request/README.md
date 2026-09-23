# COIN Official Access Request

This folder contains the official COIN licence agreement, the seven requested
video IDs, and a ready-to-send email.

## What must be completed manually

1. Open `COIN_License_Agreement.docx`.
2. Complete the user information fields: Name, Title, Affiliation, Address, and Date.
3. Ask the research advisor or an eligible professor at a university or research
   institution to review and sign the agreement. The COIN form specifically
   requires this type of signature.
4. Replace the bracketed placeholders in `email_to_coin_team.txt`.
5. Attach the signed licence and `requested_coin_videos.csv`.
6. Send the request to `tys15@tsinghua.org.cn`.

## Licence restriction

The official agreement permits scientific research use only and prohibits
commercial use and redistribution. Do not place downloaded COIN videos in Git,
public cloud folders, or a shared project archive. Store only derived experiment
metadata that the agreement permits.

## After access is granted

Place the seven authorised source videos in:

`video_event_reconstruction/data/source_videos/`

Then run the clip-extraction and scrambling stage. Keep the filenames or a
manifest that maps each downloaded file to its COIN video ID.
