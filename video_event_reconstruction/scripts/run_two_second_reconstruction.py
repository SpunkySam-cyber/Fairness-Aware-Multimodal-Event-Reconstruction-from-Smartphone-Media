"""Run a guarded OpenRouter trial for the 509-clip reconstruction experiment."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = PROJECT_ROOT / "data" / "experiment_02_two_second"
INPUT = EXPERIMENT / "model_input" / "scrambled_509_clips_labelled.mp4"
SHARD_DIR = EXPERIMENT / "model_input" / "shards_10"
PROMPT = EXPERIMENT / "experiment_protocol" / "MODEL_PROMPT.txt"
SCHEMA = EXPERIMENT / "experiment_protocol" / "model_response.schema.json"
RUN_ROOT = EXPERIMENT / "model_runs"
EVALUATOR = PROJECT_ROOT / "scripts" / "evaluate_two_second_response.py"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"

MODELS: dict[str, dict[str, Any]] = {
    "qwen-max": {
        "model_id": "qwen/qwen3.8-max-0902",
        "display_name": "Qwen3.8-Max (0902)",
        "input_price_per_million": 2.0,
        "output_price_per_million": 6.0,
    },
    "gemini-flash": {
        "model_id": "google/gemini-3.8-flash",
        "display_name": "Gemini 3.8 Flash",
        "input_price_per_million": 0.75,
        "output_price_per_million": 3.75,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_dotenv() -> Path | None:
    candidates = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / ".env",
        PROJECT_ROOT.parent.parent / ".env",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ[name.strip()] = value.strip().strip('"').strip("'")
    return path


def request(
    url: str,
    key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://smartlabs.local/event-reconstruction",
            "X-Title": "SmartLabs 509-Clip Reconstruction",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenRouter network error: {error.reason}") from error


def clean_schema() -> dict[str, Any]:
    raw = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key not in {"$schema", "$id", "uniqueItems"}
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(raw)


def encoded_video(path: Path) -> str:
    return "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode(
        "ascii"
    )


def payload(
    config: dict[str, Any],
    input_paths: list[Path],
    max_tokens: int,
    reasoning_effort: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": PROMPT.read_text(encoding="utf-8-sig"),
        }
    ]
    content.extend(
        {
            "type": "video_url",
            "video_url": {"url": encoded_video(path)},
        }
        for path in input_paths
    )
    return {
        "model": config["model_id"],
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning": {"effort": reasoning_effort, "exclude": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "two_second_event_reconstruction",
                "strict": True,
                "schema": clean_schema(),
            },
        },
        "provider": {"require_parameters": True},
    }


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Response contains no choices")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        combined = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
        if combined:
            return combined
    raise RuntimeError("Model returned no usable final content")


def run_evaluator(response_path: Path, run_dir: Path) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            str(EVALUATOR),
            str(response_path),
            "--output",
            str(run_dir / "evaluation.json"),
            "--reconstruct-dir",
            str(run_dir / "reconstructed_videos"),
        ],
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODELS), default="qwen-max")
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=12000)
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--max-estimated-cost", type=float, default=1.25)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--check-key", action="store_true")
    parser.add_argument(
        "--sharded-input",
        action="store_true",
        help="Send the ten transport shards instead of one long inline video.",
    )
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if args.check_key:
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        data = request(KEY_URL, key, timeout=60).get("data", {})
        print(
            json.dumps(
                {
                    "key_valid": True,
                    "label": data.get("label"),
                    "limit": data.get("limit"),
                    "limit_remaining": data.get("limit_remaining"),
                    "usage": data.get("usage"),
                },
                indent=2,
            )
        )
        return 0

    input_paths = (
        sorted(SHARD_DIR.glob("scrambled_part_*_labelled.mp4"))
        if args.sharded_input
        else [INPUT]
    )
    if args.sharded_input and len(input_paths) != 10:
        raise RuntimeError(f"Expected 10 input shards, found {len(input_paths)}")
    for required in (*input_paths, PROMPT, SCHEMA):
        if not required.exists():
            raise FileNotFoundError(required)
    config = MODELS[args.model]
    assumed_input_tokens = 350_000
    estimate = (
        assumed_input_tokens * config["input_price_per_million"] / 1_000_000
        + args.max_output_tokens
        * config["output_price_per_million"]
        / 1_000_000
    )
    preflight = {
        "mode": "execute" if args.execute else "dry_run",
        "model_alias": args.model,
        "model_id": config["model_id"],
        "display_name": config["display_name"],
        "run_number": args.run_number,
        "attempt": args.attempt,
        "input_files": [str(path.relative_to(PROJECT_ROOT)) for path in input_paths],
        "input_file_count": len(input_paths),
        "input_bytes": sum(path.stat().st_size for path in input_paths),
        "estimated_base64_payload_bytes": int(
            sum(path.stat().st_size for path in input_paths) * 4 / 3
        ),
        "input_sha256": [sha256(path) for path in input_paths],
        "prompt_sha256": sha256(PROMPT),
        "schema_sha256": sha256(SCHEMA),
        "assumed_input_tokens": assumed_input_tokens,
        "max_output_tokens": args.max_output_tokens,
        "reasoning_effort": args.reasoning_effort,
        "estimated_maximum_cost_usd": round(estimate, 6),
        "cost_guardrail_usd": args.max_estimated_cost,
    }
    print(json.dumps(preflight, indent=2), flush=True)
    if estimate > args.max_estimated_cost:
        raise RuntimeError("Estimated maximum cost exceeds the configured guardrail")
    if not args.execute:
        print("DRY RUN ONLY: no API request was made and no credit was spent.")
        return 0
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    run_dir = (
        RUN_ROOT
        / args.model
        / f"run_{args.run_number:02d}_attempt_{args.attempt:02d}"
    )
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "request_manifest.json").write_text(
        json.dumps(
            {
                **preflight,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "credentials_stored": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    response: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        response = request(
            API_URL,
            key,
            payload(
                config,
                input_paths,
                args.max_output_tokens,
                args.reasoning_effort,
            ),
        )
        elapsed = time.perf_counter() - started
        (run_dir / "raw_api_response.json").write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )
        parsed = json.loads(extract_content(response))
        response_path = run_dir / "model_response.json"
        response_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        evaluator_code = run_evaluator(response_path, run_dir)
        summary = {
            "model_alias": args.model,
            "requested_model": config["model_id"],
            "served_model": response.get("model"),
            "provider": response.get("provider"),
            "generation_id": response.get("id"),
            "elapsed_seconds": round(elapsed, 3),
            "usage": response.get("usage", {}),
            "evaluator_exit_code": evaluator_code,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        return evaluator_code
    except Exception as error:
        elapsed = time.perf_counter() - started
        if response:
            (run_dir / "raw_api_response.json").write_text(
                json.dumps(response, indent=2), encoding="utf-8"
            )
        failure = {
            "error_type": type(error).__name__,
            "error": str(error),
            "elapsed_seconds": round(elapsed, 3),
            "generation_id": response.get("id"),
            "served_model": response.get("model"),
            "provider": response.get("provider"),
            "usage": response.get("usage", {}),
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "error.json").write_text(
            json.dumps(failure, indent=2), encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
