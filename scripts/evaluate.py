"""Run the pinned baseline-versus-AgentProof evaluation cases."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentproof.challenges import ChallengeError, IndependentChallengeRunner
from agentproof.models import IndependentChallengeRequest, VerificationRequest
from agentproof.verifier import DeterministicVerifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "evaluation" / "benchmark_cases.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "evaluation" / "results" / "recorded-evaluation.json"


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 60) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "output_preview": (completed.stdout + completed.stderr)[-2000:],
        }
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            "status": "timed_out",
            "exit_code": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "output_preview": output[-2000:],
        }


def _git(repository: Path, *arguments: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Git command failed.")


def _safe_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if root.resolve() not in target.parents:
        raise ValueError(f"Evaluation path escapes its case root: {relative}")
    return target


def _write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        target = _safe_path(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _prepare_case(case: dict[str, Any], root: Path) -> tuple[Path, str]:
    baseline = root / "baseline"
    baseline.mkdir(parents=True)
    _write_files(baseline, case["baseline_files"])
    _git(baseline, "init", "--quiet")
    _git(baseline, "add", ".")
    _git(
        baseline,
        "-c",
        "user.name=AgentProof Evaluation",
        "-c",
        "user.email=evaluation@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Pinned baseline",
    )

    if "patch_override" in case:
        return baseline, case["patch_override"]

    candidate = root / "candidate"
    _git(root, "clone", "--quiet", "--no-local", str(baseline), str(candidate))
    _write_files(candidate, case.get("candidate_files", {}))
    for relative in case.get("delete_files", []):
        target = _safe_path(candidate, relative)
        if target.is_file():
            target.unlink()
    completed = subprocess.run(
        ["git", "-C", str(candidate), "diff", "--binary", "--full-index", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if not completed.stdout.strip():
        raise ValueError(f"Evaluation case {case['id']} produced an empty patch.")
    return baseline, completed.stdout


def _baseline_run(repository: Path, patch: str, root: Path) -> dict[str, Any]:
    candidate = root / "naive-baseline"
    _git(root, "clone", "--quiet", "--no-local", str(repository), str(candidate))
    patch_path = root / "candidate.patch"
    patch_path.write_text(patch, encoding="utf-8")
    apply_result = _run(
        ["git", "-C", str(candidate), "apply", "--recount", str(patch_path)],
        timeout=30,
    )
    if apply_result["status"] != "passed":
        return {"decision": "REJECTED", "patch_apply": apply_result, "tests": None}
    tests = _run([sys.executable, "-m", "pytest", "-q"], cwd=candidate, timeout=45)
    return {
        "decision": "ACCEPTED" if tests["status"] == "passed" else "REJECTED",
        "patch_apply": apply_result,
        "tests": tests,
    }


def _agentproof_run(
    repository: Path,
    patch: str,
    case: dict[str, Any],
    model_url: str,
    model_name: str,
) -> dict[str, Any]:
    verifier = DeterministicVerifier()
    verification = verifier.verify(
        VerificationRequest(
            repository_path=str(repository),
            task=case["task"],
            patch=patch,
        )
    )
    result: dict[str, Any] = {
        "verdict": verification.verdict,
        "summary": verification.summary,
        "run_id": verification.run_id,
        "baseline_tests": verification.test_execution.status,
        "protected_inputs_changed": verification.protected_inputs_changed,
        "challenge": None,
    }
    if verification.verdict == "UNSAFE" or verification.test_execution.status != "passed":
        return result

    try:
        challenge = IndependentChallengeRunner(verifier).run(
            IndependentChallengeRequest(
                run_id=verification.run_id,
                task=case["task"],
                model_url=model_url,
                model_name=model_name,
            )
        )
    except ChallengeError as error:
        result["verdict"] = "INCONCLUSIVE"
        result["summary"] = str(error)
        return result

    result["verdict"] = challenge.verdict
    result["summary"] = challenge.summary
    result["challenge"] = {
        "challenge_id": challenge.challenge_id,
        "behavior_mode": challenge.proposal.behavior_mode,
        "invariants": challenge.proposal.invariants,
        "baseline_status": challenge.baseline_execution.status,
        "candidate_status": challenge.candidate_execution.status,
        "model": challenge.model.model,
        "duration_ms": challenge.model.duration_ms,
        "prompt_tokens": challenge.model.prompt_tokens,
        "completion_tokens": challenge.model.completion_tokens,
        "evidence_path": challenge.evidence_path,
    }
    return result


def _percent(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--model-name", default="auto")
    parser.add_argument("--case", action="append", dest="selected_cases")
    arguments = parser.parse_args()

    manifest = json.loads(arguments.cases.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if arguments.selected_cases:
        selected = set(arguments.selected_cases)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown evaluation case(s): {', '.join(sorted(missing))}")

    results: list[dict[str, Any]] = []
    started = time.monotonic()
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        with tempfile.TemporaryDirectory(prefix=f"agentproof-eval-{index:02d}-") as temporary:
            case_root = Path(temporary)
            repository, patch = _prepare_case(case, case_root)
            baseline = _baseline_run(repository, patch, case_root)
            agentproof = _agentproof_run(
                repository,
                patch,
                case,
                arguments.model_url,
                arguments.model_name,
            )
        baseline_prediction = "VERIFIED" if baseline["decision"] == "ACCEPTED" else "UNSAFE"
        results.append(
            {
                "case_id": case["id"],
                "difficulty": case["difficulty"],
                "expected": case["expected"],
                "task": case["task"],
                "baseline": baseline,
                "baseline_prediction": baseline_prediction,
                "baseline_correct": baseline_prediction == case["expected"],
                "agentproof": agentproof,
                "agentproof_correct": agentproof["verdict"] == case["expected"],
            }
        )
        print(
            f"  baseline={baseline_prediction} agentproof={agentproof['verdict']} "
            f"expected={case['expected']}",
            flush=True,
        )

    unsafe = [result for result in results if result["expected"] == "UNSAFE"]
    safe = [result for result in results if result["expected"] == "VERIFIED"]
    challenged = [result for result in results if result["agentproof"]["challenge"]]
    summary = {
        "case_count": len(results),
        "unsafe_case_count": len(unsafe),
        "correct_case_count": len(safe),
        "baseline_accuracy_percent": _percent(
            sum(result["baseline_correct"] for result in results), len(results)
        ),
        "agentproof_accuracy_percent": _percent(
            sum(result["agentproof_correct"] for result in results), len(results)
        ),
        "baseline_unsafe_detection_percent": _percent(
            sum(result["baseline_correct"] for result in unsafe), len(unsafe)
        ),
        "agentproof_unsafe_detection_percent": _percent(
            sum(result["agentproof_correct"] for result in unsafe), len(unsafe)
        ),
        "agentproof_correct_patch_verification_percent": _percent(
            sum(result["agentproof_correct"] for result in safe), len(safe)
        ),
        "challenge_execution_percent": _percent(len(challenged), len(results)),
        "model_prompt_tokens": sum(
            result["agentproof"]["challenge"]["prompt_tokens"] for result in challenged
        ),
        "model_completion_tokens": sum(
            result["agentproof"]["challenge"]["completion_tokens"] for result in challenged
        ),
        "model_duration_ms": sum(
            result["agentproof"]["challenge"]["duration_ms"] for result in challenged
        ),
        "evaluation_duration_ms": round((time.monotonic() - started) * 1000),
    }
    report = {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "purpose": "Controlled baseline-versus-AgentProof evaluation",
        "model_url": arguments.model_url,
        "model_name_requested": arguments.model_name,
        "summary": summary,
        "cases": results,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["agentproof_accuracy_percent"] == 100.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
