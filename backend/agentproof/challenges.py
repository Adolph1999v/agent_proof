"""Model-proposed, deterministically executed independent pytest challenges."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from agentproof.models import (
    ChallengeProposalEvidence,
    CommandEvidence,
    IndependentChallengeReport,
    IndependentChallengeRequest,
    ModelRunEvidence,
)
from agentproof.provider import ChallengeProvider, OpenAICompatibleProvider, ProviderError
from agentproof.verifier import DeterministicVerifier, VerificationInputError

MAX_TASK_CHARS = 2_000
MAX_CHANGED_APPLICATION_FILES = 4
MAX_PROMPT_PATCH_CHARS = 8_000
MAX_PATCH_FILE_CHARS = 3_000
MAX_SOURCE_CONTEXT_CHARS = 4_000
MAX_SOURCE_FILE_CHARS = 2_000
MAX_FILE_INDEX_CHARS = 1_500
MAX_USER_PROMPT_CHARS = 18_000
MAX_TEST_CHARS = 20_000
NO_THINK_DIRECTIVE = "\n/no_think"
CHALLENGE_TEST_NAME = "agentproof_challenge_test.py"
TEST_DIRECTORY_NAMES = {"test", "tests", "__tests__", "spec", "specs"}
TEST_FILE_NAMES = {"test.py", "tests.py", "conftest.py"}
BLOCKED_IMPORT_ROOTS = {
    "builtins",
    "ctypes",
    "http",
    "httpx",
    "importlib",
    "multiprocessing",
    "os",
    "pathlib",
    "random",
    "requests",
    "secrets",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "time",
    "urllib",
}
BLOCKED_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "exit",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "quit",
    "setattr",
    "vars",
}
BLOCKED_ATTRIBUTE_CALLS = {
    "connect",
    "popen",
    "remove",
    "read_bytes",
    "read_text",
    "rename",
    "replace",
    "request",
    "rmdir",
    "rmtree",
    "skip",
    "system",
    "unlink",
    "urlopen",
    "write_bytes",
    "write_text",
    "xfail",
}

SYSTEM_PROMPT = """You are AgentProof's independent challenge-test author. Return the required
JSON immediately without analysis, explanation, hidden planning, or Markdown.

You receive a user task and a candidate change. Create one focused pytest module that checks a
meaningful requirement the candidate's existing tests may have missed.

Rules:
- Return only one JSON object. Do not use Markdown fences.
- Never edit application files, existing tests, fixtures, configuration, or dependencies.
- Do not use network access, subprocesses, dynamic execution, environment variables, arbitrary
  filesystem access, monkeypatching, sleeps, randomness, skip, or xfail.
- The test must import real application code and contain a non-trivial assertion.
- Select one concrete behavior quickly. Do not exhaustively audit the repository or repeat analysis.
- Finish the complete JSON response within 300 generated tokens.
- Use behavior_mode "change" when the test should fail on the approved baseline and pass on the
  candidate. Use "preserve" when the same required behavior should pass on both.
- Return exactly this shape:
  {"behavior_mode":"change|preserve","summary":"short explanation",
   "invariants":["one to five concrete requirements"],"test_code":"complete pytest module"}
"""


class ChallengeError(RuntimeError):
    """Raised when an independent challenge cannot be produced or executed safely."""


class _ChallengeProposal(BaseModel):
    behavior_mode: Literal["change", "preserve"]
    summary: str = Field(min_length=1, max_length=1000)
    invariants: list[str] = Field(min_length=1, max_length=5)
    test_code: str = Field(min_length=1, max_length=MAX_TEST_CHARS)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_test_path(path: Path) -> bool:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    return bool(
        parts & TEST_DIRECTORY_NAMES
        or name in TEST_FILE_NAMES
        or name.startswith("test_")
        or name.startswith("tests_")
        or name.endswith("_test.py")
        or name.endswith("_tests.py")
        or ".test." in name
        or ".spec." in name
    )


def _preview(value: str, limit: int = 12_000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n… output truncated by AgentProof …"


def _parse_proposal(raw: str) -> _ChallengeProposal:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        return _ChallengeProposal.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ChallengeError(
            "The local model response did not match AgentProof's challenge JSON contract."
        ) from error


def _validate_test(code: str) -> None:
    try:
        tree = ast.parse(code, filename=CHALLENGE_TEST_NAME)
    except SyntaxError as error:
        raise ChallengeError("The generated challenge test is not valid Python.") from error

    test_functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    if not test_functions or not assertions:
        raise ChallengeError(
            "The generated challenge must contain a pytest test function and an assertion."
        )
    if any(isinstance(node.test, ast.Constant) for node in assertions):
        raise ChallengeError("The generated challenge contains a trivial constant assertion.")

    for function in test_functions:
        argument_names = {argument.arg for argument in function.args.args}
        if "monkeypatch" in argument_names:
            raise ChallengeError("Generated challenges may not use monkeypatching.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ChallengeError("The generated challenge uses a blocked dynamic name.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ChallengeError("The generated challenge uses a blocked dynamic attribute.")
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".", maxsplit=1)[0] for alias in node.names}
            if roots & BLOCKED_IMPORT_ROOTS:
                raise ChallengeError("The generated challenge imports a blocked capability.")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", maxsplit=1)[0]
            if root in BLOCKED_IMPORT_ROOTS:
                raise ChallengeError("The generated challenge imports a blocked capability.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALL_NAMES:
                raise ChallengeError("The generated challenge calls a blocked capability.")
            if isinstance(node.func, ast.Attribute) and node.func.attr in BLOCKED_ATTRIBUTE_CALLS:
                raise ChallengeError("The generated challenge calls a blocked capability.")


class IndependentChallengeRunner:
    """Turn untrusted model suggestions into reproducible baseline/candidate evidence."""

    def __init__(
        self,
        verifier: DeterministicVerifier,
        provider: ChallengeProvider | None = None,
    ) -> None:
        self.verifier = verifier
        self.provider = provider

    def run(self, request: IndependentChallengeRequest) -> IndependentChallengeReport:
        try:
            source_report = self.verifier.get_report(request.run_id)
        except VerificationInputError as error:
            raise ChallengeError(str(error)) from error
        if (
            source_report.verdict != "INCONCLUSIVE"
            or source_report.test_execution.status != "passed"
        ):
            raise ChallengeError(
                "Independent challenges require an inconclusive run with passing baseline tests."
            )
        if _sha256(request.task) != source_report.input_digests.task_sha256:
            raise ChallengeError("The challenge task does not match the original verification run.")

        run_directory = self.verifier.artifacts_root / request.run_id
        source_workspace = run_directory / "workspace"
        patch_path = run_directory / "candidate.application.patch"
        if not patch_path.is_file():
            patch_path = run_directory / "candidate.patch"
        if not source_workspace.is_dir() or not patch_path.is_file():
            raise ChallengeError("The source verification workspace or candidate patch is missing.")

        application_changes = self._application_changes(
            source_report.changed_files,
            request.task,
        )
        if not application_changes:
            raise ChallengeError(
                "The current challenge adapter requires at least one changed Python "
                "application file."
            )
        patch = self._application_patch(source_workspace, application_changes)
        prompt = self._user_prompt(
            application_changes,
            source_workspace,
            request.task,
            patch,
        )
        provider = self.provider or OpenAICompatibleProvider(
            request.model_url,
            request.model_name,
            timeout_seconds=request.model_timeout_seconds,
        )

        challenge_id = f"challenge-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        challenge_directory = run_directory / "challenges" / challenge_id
        challenge_directory.mkdir(parents=True, exist_ok=False)
        relative_root = f"artifacts/runs/{request.run_id}/challenges/{challenge_id}"
        trajectory_path = challenge_directory / "trajectory.json"
        try:
            completion = provider.complete(SYSTEM_PROMPT, prompt)
        except ProviderError as error:
            self._write_trajectory(
                trajectory_path,
                prompt,
                error=str(error),
            )
            raise ChallengeError(
                f"{error} Failure evidence: {relative_root}/trajectory.json"
            ) from error

        if not completion.content.strip():
            if completion.finish_reason == "length":
                message = (
                    "The local model exhausted its context window before producing the challenge "
                    f"JSON ({completion.prompt_tokens} prompt + "
                    f"{completion.completion_tokens} completion tokens)."
                )
            else:
                message = "The local model returned an empty challenge response."
            self._write_trajectory(
                trajectory_path,
                prompt,
                completion=completion,
                error=message,
            )
            raise ChallengeError(
                f"{message} Failure evidence: {relative_root}/trajectory.json"
            )

        try:
            proposal = _parse_proposal(completion.content)
            _validate_test(proposal.test_code)
        except ChallengeError as error:
            self._write_trajectory(
                trajectory_path,
                prompt,
                completion=completion,
                error=str(error),
            )
            raise ChallengeError(
                f"{error} Failure evidence: {relative_root}/trajectory.json"
            ) from error

        self._write_trajectory(
            trajectory_path,
            prompt,
            completion=completion,
            proposal_accepted=True,
        )

        baseline_workspace = challenge_directory / "baseline"
        candidate_workspace = challenge_directory / "candidate"

        self._clone(source_workspace, baseline_workspace)
        self._clone(source_workspace, candidate_workspace)
        self._apply(candidate_workspace, patch_path)
        for workspace in (baseline_workspace, candidate_workspace):
            (workspace / CHALLENGE_TEST_NAME).write_text(proposal.test_code, encoding="utf-8")

        baseline_execution = self._run_test(
            baseline_workspace,
            request.test_timeout_seconds,
        )
        candidate_execution = self._run_test(
            candidate_workspace,
            request.test_timeout_seconds,
        )
        verdict, summary = self._verdict(
            proposal.behavior_mode,
            baseline_execution,
            candidate_execution,
        )

        report = IndependentChallengeReport(
            challenge_id=challenge_id,
            created_at=datetime.now(UTC),
            source_run_id=request.run_id,
            verdict=verdict,
            summary=summary,
            proposal=ChallengeProposalEvidence(
                behavior_mode=proposal.behavior_mode,
                summary=proposal.summary,
                invariants=proposal.invariants,
                test_sha256=_sha256(proposal.test_code),
                test_path=f"{relative_root}/{CHALLENGE_TEST_NAME}",
            ),
            model=ModelRunEvidence(
                provider=provider.label,
                model=getattr(provider, "model", request.model_name),
                prompt_sha256=_sha256(prompt),
                response_sha256=_sha256(completion.content),
                duration_ms=completion.duration_ms,
                prompt_tokens=completion.prompt_tokens,
                completion_tokens=completion.completion_tokens,
            ),
            baseline_execution=baseline_execution,
            candidate_execution=candidate_execution,
            evidence_path=f"{relative_root}/report.json",
            trajectory_path=f"{relative_root}/trajectory.json",
        )
        (challenge_directory / CHALLENGE_TEST_NAME).write_text(
            proposal.test_code,
            encoding="utf-8",
        )
        self._write_trajectory(
            trajectory_path,
            prompt,
            completion=completion,
            proposal_accepted=True,
            baseline_execution=baseline_execution.model_dump(mode="json"),
            candidate_execution=candidate_execution.model_dump(mode="json"),
        )
        (challenge_directory / "report.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return report

    @staticmethod
    def _user_prompt(changed_files, workspace: Path, task: str, patch: str) -> str:
        changed_files = list(changed_files)[:MAX_CHANGED_APPLICATION_FILES]
        sections: list[str] = []
        used = 0
        for changed in changed_files:
            path = Path(changed.path)
            source_path = workspace / path
            if not source_path.is_file():
                continue
            content = source_path.read_text(encoding="utf-8", errors="replace")
            remaining = MAX_SOURCE_CONTEXT_CHARS - used
            if remaining <= 0:
                break
            excerpt = content[: min(remaining, MAX_SOURCE_FILE_CHARS)]
            used += len(excerpt)
            sections.append(f"### {changed.path}\n{excerpt}")
        context = "\n\n".join(sections) or "(No changed Python source excerpt was available.)"
        file_index = "\n".join(
            f"- {changed.path} (+{changed.added_lines}/-{changed.deleted_lines})"
            for changed in changed_files
        )[:MAX_FILE_INDEX_CHARS]
        prompt = f"""## Original user task
{task[:MAX_TASK_CHARS]}

## Changed Python application files
{file_index}

## Candidate application patch (test files excluded)
{patch[:MAX_PROMPT_PATCH_CHARS]}

## Changed candidate Python source excerpts
{context}

Write one independent pytest challenge for the most important unproven behavior. Return only the
required JSON object.
"""
        bounded = prompt[: MAX_USER_PROMPT_CHARS - len(NO_THINK_DIRECTIVE)]
        return f"{bounded}{NO_THINK_DIRECTIVE}"

    @staticmethod
    def _application_changes(changed_files, task: str = ""):
        task_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", task[:MAX_TASK_CHARS].casefold())
            if len(term) >= 3
        }

        def relevance(changed) -> int:
            normalized_path = changed.path.casefold()
            return sum(term in normalized_path for term in task_terms)

        eligible = (
            changed
            for changed in changed_files
            if not changed.protected
            and not _is_test_path(Path(changed.path))
            and Path(changed.path).suffix.lower() == ".py"
        )
        return sorted(
            eligible,
            key=lambda changed: (
                -relevance(changed),
                -(changed.added_lines + changed.deleted_lines),
                changed.path.casefold(),
                changed.path,
            ),
        )[:MAX_CHANGED_APPLICATION_FILES]

    @staticmethod
    def _application_patch(workspace: Path, changed_files) -> str:
        sections: list[str] = []
        used = 0
        for changed in list(changed_files)[:MAX_CHANGED_APPLICATION_FILES]:
            path = Path(changed.path)
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "diff",
                    "--no-ext-diff",
                    "--no-renames",
                    "--binary",
                    "--full-index",
                    "HEAD",
                    "--",
                    changed.path,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if completed.returncode != 0:
                raise ChallengeError("AgentProof could not prepare model-safe change context.")
            section = completed.stdout
            source = workspace / path
            if not section and source.is_file():
                intent = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(workspace),
                        "add",
                        "--intent-to-add",
                        "--",
                        changed.path,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
                if intent.returncode != 0:
                    raise ChallengeError("AgentProof could not prepare newly added model context.")
                added = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(workspace),
                        "diff",
                        "--no-ext-diff",
                        "--no-renames",
                        "--binary",
                        "--full-index",
                        "HEAD",
                        "--",
                        changed.path,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
                if added.returncode != 0:
                    raise ChallengeError("AgentProof could not prepare newly added model context.")
                section = added.stdout
            remaining = MAX_PROMPT_PATCH_CHARS - used
            if remaining <= 0:
                break
            bounded_section = section[: min(remaining, MAX_PATCH_FILE_CHARS)]
            sections.append(bounded_section)
            used += len(bounded_section)
        return "\n".join(sections) or "(No non-test patch content was available.)"

    @staticmethod
    def _write_trajectory(
        path: Path,
        prompt: str,
        *,
        completion=None,
        error: str | None = None,
        proposal_accepted: bool = False,
        baseline_execution=None,
        candidate_execution=None,
    ) -> None:
        payload = {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": prompt,
            "model_response": completion.content if completion else None,
            "model_reasoning": completion.reasoning_content if completion else None,
            "model_finish_reason": completion.finish_reason if completion else None,
            "model_usage": (
                {
                    "prompt_tokens": completion.prompt_tokens,
                    "completion_tokens": completion.completion_tokens,
                    **completion.extra_usage,
                }
                if completion
                else None
            ),
            "proposal_accepted": proposal_accepted,
            "error": error,
            "baseline_execution": baseline_execution,
            "candidate_execution": candidate_execution,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _clone(source: Path, destination: Path) -> None:
        completed = subprocess.run(
            ["git", "clone", "--quiet", "--no-local", str(source), str(destination)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if completed.returncode != 0:
            raise ChallengeError("AgentProof could not create a challenge workspace.")

    @staticmethod
    def _apply(workspace: Path, patch_path: Path) -> None:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "apply",
                "--recount",
                "--whitespace=nowarn",
                str(patch_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if completed.returncode != 0:
            raise ChallengeError("The candidate patch could not be replayed for its challenge.")

    @staticmethod
    def _run_test(workspace: Path, timeout_seconds: int) -> CommandEvidence:
        command = [sys.executable, "-m", "pytest", "-q", CHALLENGE_TEST_NAME]
        started = time.monotonic()
        temporary_directory = workspace / ".agentproof-temp"
        temporary_directory.mkdir(exist_ok=False)
        environment = {
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(temporary_directory),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TMPDIR": str(temporary_directory),
        }
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return CommandEvidence(
                command=command,
                status="timed_out",
                duration_ms=round((time.monotonic() - started) * 1000),
                output_preview=_preview(str(output)),
            )
        return CommandEvidence(
            command=command,
            status="passed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            duration_ms=round((time.monotonic() - started) * 1000),
            output_preview=_preview(completed.stdout + completed.stderr),
        )

    @staticmethod
    def _verdict(
        mode: Literal["change", "preserve"],
        baseline: CommandEvidence,
        candidate: CommandEvidence,
    ) -> tuple[Literal["VERIFIED", "UNSAFE", "INCONCLUSIVE"], str]:
        if baseline.status == "timed_out" or candidate.status == "timed_out":
            return "INCONCLUSIVE", "The independent challenge timed out."
        if baseline.status == "failed" and candidate.status == "failed":
            return (
                "INCONCLUSIVE",
                "The generated challenge failed on both the baseline and candidate.",
            )
        if baseline.status == "passed" and candidate.status == "failed":
            return (
                "UNSAFE",
                "The candidate failed an independent behavior that the approved "
                "baseline preserved.",
            )
        if baseline.status == "failed" and candidate.status == "passed":
            if mode == "change":
                return (
                    "VERIFIED",
                    "The independent challenge failed on the baseline and passed on the candidate.",
                )
            return (
                "INCONCLUSIVE",
                "The challenge behavior improved, but the model classified it as preservation.",
            )
        if baseline.status == "passed" and candidate.status == "passed":
            if mode == "preserve":
                return (
                    "VERIFIED",
                    "The independent preservation challenge passed on both baseline and candidate.",
                )
            return (
                "INCONCLUSIVE",
                "The challenge passed, but it did not distinguish the candidate from the baseline.",
            )
        return "INCONCLUSIVE", "The independent challenge did not produce usable evidence."
