"""Run BRAB prompt packs through an external command adapter."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from brab.io import load_jsonl, write_jsonl


def run_command_on_prompts(
    prompts_path: Path,
    out_path: Path,
    *,
    model_name: str,
    command: list[str],
    timeout_seconds: int,
) -> int:
    if not command:
        raise ValueError("command cannot be empty")
    prompts = load_jsonl(prompts_path)
    outputs = [
        run_single_prompt(prompt, model_name=model_name, command=command, timeout_seconds=timeout_seconds)
        for prompt in prompts
    ]
    write_jsonl(out_path, outputs)
    return len(outputs)


def run_single_prompt(
    prompt: Mapping[str, Any],
    *,
    model_name: str,
    command: list[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    task_id = str(prompt.get("task_id", ""))
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(prompt),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "task_id": task_id,
            "model_name": model_name,
            "label": "",
            "answer": "",
            "rationale": "",
            "raw_output": exc.stdout or "",
            "error": f"timeout after {timeout_seconds}s",
        }

    parsed = _parse_stdout(completed.stdout)
    output = {
        "task_id": parsed.get("task_id", task_id),
        "model_name": model_name,
        "label": parsed.get("label", ""),
        "answer": parsed.get("answer", ""),
        "rationale": parsed.get("rationale", ""),
        "evidence_used": parsed.get("evidence_used", []),
        "uncertainty_notes": parsed.get("uncertainty_notes", ""),
        "raw_output": completed.stdout,
    }
    if completed.returncode != 0:
        output["error"] = f"command exited with {completed.returncode}: {completed.stderr.strip()}"
    return output


def _parse_stdout(stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return {"answer": stripped, "raw_output": stdout}
    if not isinstance(value, dict):
        return {"answer": stripped, "raw_output": stdout}
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a prompt JSONL through an external command. The command receives one prompt "
            "record as JSON on stdin and should print a JSON object with label/answer/rationale."
        )
    )
    parser.add_argument("--prompts", type=Path, required=True, help="Prompt pack JSONL from brab_export_prompts.py")
    parser.add_argument("--out", type=Path, required=True, help="Model output JSONL path")
    parser.add_argument("--model-name", required=True, help="Model name to record in outputs")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per task in seconds")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    total = run_command_on_prompts(
        args.prompts,
        args.out,
        model_name=args.model_name,
        command=command,
        timeout_seconds=args.timeout,
    )
    print(f"Wrote {total} model outputs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
