"""Run one guarded OpenRouter event-reconstruction trial.

The script performs no paid request unless --execute is supplied. Every paid
run is isolated in a new directory and records the raw response, parsed model
answer, usage/cost data, and automatic evaluation.
"""

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
EXPERIMENT_ROOT = PROJECT_ROOT / "data" / "experiment_01"
PROTOCOL_ROOT = EXPERIMENT_ROOT / "experiment_protocol"
INPUT_ROOT = EXPERIMENT_ROOT / "model_inputs"
RUN_ROOT = EXPERIMENT_ROOT / "model_runs"
PROMPT_PATH = PROTOCOL_ROOT / "MODEL_PROMPT.txt"
SCHEMA_PATH = PROTOCOL_ROOT / "model_response.schema.json"
COMPOSITE_PATH = INPUT_ROOT / "all_21_clips_composite_visual_only.mp4"
OPENROUTER_COMPOSITE_PATH = (
    INPUT_ROOT / "all_21_clips_composite_openrouter_visual_only.mp4"
)
INDIVIDUAL_ROOT = INPUT_ROOT / "individual_visual_only"
EVALUATOR_PATH = PROJECT_ROOT / "scripts" / "evaluate_model_response.py"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
MODELS_URL = "https://openrouter.ai/api/v1/models"


MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "qwen-max": {
        "model_id": "qwen/qwen3.8-max-0902",
        "display_name": "Qwen3.8-Max (0902)",
        "input_form": "individual",
        "input_price_per_million": 2.0,
        "output_price_per_million": 6.0,
    },
    "gemini-pro": {
        "model_id": "google/gemini-3.1-pro-preview",
        "display_name": "Gemini 3.1 Pro Preview",
        "input_form": "composite",
        "input_price_per_million": 2.0,
        "output_price_per_million": 12.0,
    },
    "gemini-flash": {
        "model_id": "google/gemini-3.8-flash",
        "display_name": "Gemini 3.8 Flash",
        "input_form": "composite",
        "input_price_per_million": 0.75,
        "output_price_per_million": 3.75,
    },
    "seed-turbo": {
        "model_id": "bytedance-seed/seed-2-1-turbo",
        "display_name": "Seed 2.1 Turbo",
        "input_form": "composite",
        "input_price_per_million": 0.50,
        "output_price_per_million": 2.50,
        "protocol_note": "OpenRouter substitute for the selected Seed2.1 Pro",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_dotenv_if_present() -> Path | None:
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
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        # The closest project .env deliberately overrides an older inherited
        # process variable, which is important when keys are rotated.
        if name:
            os.environ[name] = value
    return path


def api_request(
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 900,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://smartlabs.local/event-reconstruction",
            "X-Title": "SmartLabs Event Reconstruction",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenRouter network error: {error.reason}") from error


def encoded_video(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:video/mp4;base64,{encoded}"


def input_paths(config: dict[str, Any]) -> list[Path]:
    if config["input_form"] == "individual":
        paths = [INDIVIDUAL_ROOT / f"V{index:03d}.mp4" for index in range(1, 22)]
    else:
        paths = [OPENROUTER_COMPOSITE_PATH]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing model inputs: {missing}")
    return paths


def clean_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))

    def sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if key not in {"$schema", "$id", "uniqueItems"}
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    # Alibaba's structured-output implementation rejects `uniqueItems` for
    # arrays. Cross-event and within-event uniqueness remain mandatory and are
    # enforced by evaluate_model_response.py after the response is received.
    return sanitize(schema)


def build_payload(
    config: dict[str, Any],
    paths: list[Path],
    max_output_tokens: int,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for path in paths:
        content.append(
            {
                "type": "video_url",
                "video_url": {"url": encoded_video(path)},
            }
        )
    content.append(
        {"type": "text", "text": PROMPT_PATH.read_text(encoding="utf-8-sig")}
    )
    payload: dict[str, Any] = {
        "model": config["model_id"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": max_output_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "event_reconstruction",
                "strict": True,
                "schema": clean_schema(),
            },
        },
        "provider": {"require_parameters": True},
    }
    if reasoning_effort is not None:
        payload["reasoning"] = {
            "effort": reasoning_effort,
            "exclude": True,
        }
    return payload


def estimate_cost(config: dict[str, Any], max_output_tokens: int) -> dict[str, float]:
    # Video tokenization differs by provider. A deliberately conservative 60K
    # input-token allowance is used only as a guardrail, not as measured usage.
    assumed_input_tokens = 60_000
    input_cost = (
        assumed_input_tokens * config["input_price_per_million"] / 1_000_000
    )
    output_cost = (
        max_output_tokens * config["output_price_per_million"] / 1_000_000
    )
    return {
        "assumed_input_tokens": assumed_input_tokens,
        "maximum_output_tokens": max_output_tokens,
        "estimated_input_cost_usd": round(input_cost, 6),
        "estimated_output_cost_usd": round(output_cost, 6),
        "estimated_total_cost_usd": round(input_cost + output_cost, 6),
    }


def extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Response does not contain choices[0].message.content") from error
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "".join(text_parts)
    raise RuntimeError(f"Unsupported message content type: {type(content).__name__}")


def run_evaluator(response_path: Path, output_path: Path) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            str(EVALUATOR_PATH),
            str(response_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return completed.returncode


def public_model_ids() -> set[str]:
    request = urllib.request.Request(MODELS_URL, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        raise RuntimeError(f"Could not retrieve OpenRouter model catalogue: {error}") from error
    return {str(item["id"]) for item in payload.get("data", []) if "id" in item}


def model_status_report() -> dict[str, Any]:
    available = public_model_ids()
    return {
        alias: {
            "model_id": config["model_id"],
            "available": config["model_id"] in available,
        }
        for alias, config in MODEL_CONFIGS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODEL_CONFIGS))
    parser.add_argument("--run-number", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--attempt", type=int, choices=range(1, 10), default=1)
    parser.add_argument("--max-output-tokens", type=int, default=3000)
    parser.add_argument("--max-estimated-cost", type=float, default=0.75)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high"),
        help="Optional OpenRouter-normalized reasoning effort.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Make the paid API request. Without this flag, only a dry run is performed.",
    )
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Validate the configured key without making a model request.",
    )
    parser.add_argument(
        "--check-models",
        action="store_true",
        help="Check selected model IDs against OpenRouter's public catalogue.",
    )
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    if args.check_models:
        print(json.dumps(model_status_report(), indent=2))
        return 0
    if args.check_key:
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        key_data = api_request(KEY_URL, api_key, timeout=60)
        safe = {
            "key_valid": True,
            "label": key_data.get("data", {}).get("label"),
            "limit": key_data.get("data", {}).get("limit"),
            "limit_remaining": key_data.get("data", {}).get("limit_remaining"),
            "usage": key_data.get("data", {}).get("usage"),
        }
        print(json.dumps(safe, indent=2))
        return 0
    if not args.model:
        parser.error("--model is required unless --check-key or --check-models is used")

    config = MODEL_CONFIGS[args.model]
    paths = input_paths(config)
    estimate = estimate_cost(config, args.max_output_tokens)
    input_bytes = sum(path.stat().st_size for path in paths)
    preflight = {
        "mode": "execute" if args.execute else "dry_run",
        "model_alias": args.model,
        "model_id": config["model_id"],
        "display_name": config["display_name"],
        "run_number": args.run_number,
        "attempt": args.attempt,
        "input_form": config["input_form"],
        "input_file_count": len(paths),
        "input_bytes": input_bytes,
        "estimated_base64_payload_bytes": int(input_bytes * 4 / 3),
        "prompt_sha256": sha256(PROMPT_PATH),
        "schema_sha256": sha256(SCHEMA_PATH),
        "input_sha256": {path.name: sha256(path) for path in paths},
        "cost_guardrail": estimate,
        "max_estimated_cost_usd": args.max_estimated_cost,
        "reasoning_effort": args.reasoning_effort or "provider_default",
    }
    print(json.dumps(preflight, indent=2))
    if estimate["estimated_total_cost_usd"] > args.max_estimated_cost:
        raise RuntimeError("Conservative estimated cost exceeds the configured guardrail")
    if not args.execute:
        print("DRY RUN ONLY: no API request was made and no credit was spent.")
        return 0
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    run_dir = (
        RUN_ROOT
        / args.model
        / f"run_{args.run_number:02d}_attempt_{args.attempt:02d}"
    )
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    request_manifest = {
        **preflight,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_url": API_URL,
        "temperature": 0,
        "max_output_tokens": args.max_output_tokens,
        "credentials_stored": False,
    }
    (run_dir / "request_manifest.json").write_text(
        json.dumps(request_manifest, indent=2), encoding="utf-8"
    )

    started = time.perf_counter()
    response: dict[str, Any] = {}
    try:
        payload = build_payload(
            config,
            paths,
            args.max_output_tokens,
            args.reasoning_effort,
        )
        response = api_request(API_URL, api_key, payload=payload)
        elapsed = time.perf_counter() - started
        (run_dir / "raw_api_response.json").write_text(
            json.dumps(response, indent=2), encoding="utf-8"
        )
        content = extract_message_content(response)
        parsed = json.loads(content)
        model_response_path = run_dir / "model_response.json"
        model_response_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        evaluator_code = run_evaluator(
            model_response_path, run_dir / "evaluation.json"
        )
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
