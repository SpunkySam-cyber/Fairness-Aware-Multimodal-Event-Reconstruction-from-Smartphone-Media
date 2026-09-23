# Fairness-Aware Multimodal Event Reconstruction

This repository starts with the Android photo collection proof of concept. The
collector finds images in accessible Android shared storage, copies them into a
single laptop folder, preserves the originals, and writes an auditable manifest.

## Current milestone

The current implementation provides:

- Android device detection through ADB
- Recursive image discovery under `/sdcard`
- Copy-only transfer; no delete or move operation exists
- One flat destination folder for all images
- Collision-safe filenames
- SHA-256 hashes and duplicate flags
- CSV, JSONL, and JSON run reports
- Partial scan results and inaccessible-folder warnings
- A local-folder mode for testing without a phone

## Requirements

- Windows with Python 3.11 or later
- An Android phone and data-capable USB cable for the real-device demo
- Android Platform Tools (`adb`) for the real-device demo

## Test without a phone

From this folder, run:

```powershell
python collect_photos.py --local-source "C:\path\to\sample_phone_storage" --output collected_photos
```

The program recursively scans the local sample folder as if it were Android
storage. Images are copied into `collected_photos`, and reports are written to
`run_reports`.

Use `--dry-run` to inventory files without copying them:

```powershell
python collect_photos.py --local-source "C:\path\to\sample_phone_storage" --dry-run
```

## Test with an Android phone

1. Install Android Platform Tools. The program checks `PATH`, `ADB_PATH`, and
   the standard Windows Package Manager installation location.
2. Enable Developer options and USB debugging on the phone.
3. Connect the phone and accept its authorization prompt.
4. Confirm the connection:

   ```powershell
   adb devices -l
   ```

5. Run the collector:

   ```powershell
   python collect_photos.py --output collected_photos
   ```

If multiple Android devices are connected, select one with `--serial`:

```powershell
python collect_photos.py --serial DEVICE_SERIAL --output collected_photos
```

## Output

Images from every discovered phone folder are stored directly in one directory:

```text
collected_photos/
```

Reports are stored separately:

```text
run_reports/<run-id>/manifest.csv
run_reports/<run-id>/manifest.jsonl
run_reports/<run-id>/summary.json
```

The manifest preserves each image's original phone path even though the copied
images are flattened into one directory.

## Important limitation

The collector can only read storage exposed to the ADB shell. Modern Android
versions may restrict private application directories. Such access errors are
recorded; the program does not claim that inaccessible private files were
collected.

## Run automated tests

```powershell
python -m unittest discover -s tests -v
```
