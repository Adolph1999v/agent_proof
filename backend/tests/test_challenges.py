import json
import subprocess
from pathlib import Path

import httpx
import pytest
from agentproof.challenges import (
    MAX_CHANGED_APPLICATION_FILES,
    MAX_TASK_CHARS,
    MAX_USER_PROMPT_CHARS,
    SYSTEM_PROMPT,
    ChallengeError,
    IndependentChallengeRunner,
)
from agentproof.models import ChangedFile, IndependentChallengeRequest, VerificationRequest
from agentproof.provider import ModelCompletion, OpenAICompatibleProvider, ProviderError
from agentproof.verifier import DeterministicVerifier


class ScriptedProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompts: list[tuple[str, str]] = []

    @property
    def label(self) -> str:
        return "scripted:test-model"

    def complete(self, system_prompt: str, user_prompt: str) -> ModelCompletion:
        self.prompts.append((system_prompt, user_prompt))
        return ModelCompletion(
            content=json.dumps(self.response),
            duration_ms=12,
            prompt_tokens=100,
            completion_tokens=40,
        )


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def create_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "challenge-repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "service.py").write_text(
        "def value() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (repository / "tests" / "test_service.py").write_text(
        "from service import value\n\n\ndef test_value_is_an_integer() -> None:\n"
        "    assert isinstance(value(), int)\n",
        encoding="utf-8",
    )
    run_git(repository, "init", "--quiet")
    run_git(repository, "add", ".")
    run_git(
        repository,
        "-c",
        "user.name=AgentProof Tests",
        "-c",
        "user.email=tests@agentproof.local",
        "commit",
        "--quiet",
        "-m",
        "Initial fixture",
    )
    return repository


def verification_run(
    repository: Path,
    artifacts_root: Path,
    task: str,
) -> tuple[DeterministicVerifier, str]:
    patch = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,2 +1,2 @@
 def value() -> int:
-    return 1
+    return 2
diff --git a/test_candidate_added.py b/test_candidate_added.py
new file mode 100644
--- /dev/null
+++ b/test_candidate_added.py
@@ -0,0 +1,5 @@
+from service import value
+
+
+def test_candidate_secret_marker() -> None:
+    assert isinstance(value(), int)
diff --git a/helper.py b/helper.py
new file mode 100644
--- /dev/null
+++ b/helper.py
@@ -0,0 +1,2 @@
+def candidate_application_marker() -> str:
+    return "application"
diff --git a/test.py b/test.py
new file mode 100644
--- /dev/null
+++ b/test.py
@@ -0,0 +1,2 @@
+def candidate_root_test_marker() -> bool:
+    return True
"""
    verifier = DeterministicVerifier(artifacts_root)
    report = verifier.verify(
        VerificationRequest(repository_path=str(repository), task=task, patch=patch)
    )
    assert report.verdict == "INCONCLUSIVE"
    assert "test_candidate_added.py" in {changed.path for changed in report.changed_files}
    assert "test_candidate_added.py" in report.protected_inputs_changed
    assert report.test_execution.status == "passed"
    return verifier, report.run_id


def challenge_request(run_id: str, task: str) -> IndependentChallengeRequest:
    return IndependentChallengeRequest(
        run_id=run_id,
        task=task,
        model_url="http://127.0.0.1:1234/v1",
        model_name="scripted-model",
    )


def test_change_challenge_is_verified_only_when_baseline_fails_and_candidate_passes(
    tmp_path: Path,
) -> None:
    task = "Change the service value from 1 to 2."
    repository = create_repository(tmp_path)
    verifier, run_id = verification_run(repository, tmp_path / "artifacts" / "runs", task)
    provider = ScriptedProvider(
        {
            "behavior_mode": "change",
            "summary": "The requested value must now be two.",
            "invariants": ["value() returns 2"],
            "test_code": "from service import value\n\n\ndef test_new_value() -> None:\n"
            "    assert value() == 2\n",
        }
    )

    report = IndependentChallengeRunner(verifier, provider).run(
        challenge_request(run_id, task)
    )

    assert report.verdict == "VERIFIED"
    assert report.baseline_execution.status == "failed"
    assert report.candidate_execution.status == "passed"
    assert report.model.prompt_tokens == 100
    assert (tmp_path / report.evidence_path).is_file()
    assert "test_service.py" not in provider.prompts[0][1]
    assert "test_candidate_secret_marker" not in provider.prompts[0][1]
    assert "candidate_root_test_marker" not in provider.prompts[0][1]
    assert "candidate_application_marker" in provider.prompts[0][1]


def test_prompt_context_is_bounded_and_prioritizes_python_application_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "large.py").write_text("x = 1\n" * 10_000, encoding="utf-8")
    changes = [
        ChangedFile(path="large.py", added_lines=10_000, deleted_lines=0, protected=False),
        ChangedFile(path="test.py", added_lines=1, deleted_lines=0, protected=False),
        ChangedFile(path="README.md", added_lines=1, deleted_lines=0, protected=False),
    ]

    application_changes = IndependentChallengeRunner._application_changes(changes)
    prompt = IndependentChallengeRunner._user_prompt(
        application_changes,
        workspace,
        "Implement one concrete behavior.",
        "p" * 100_000,
    )

    assert [change.path for change in application_changes] == ["large.py"]
    assert len(prompt) <= MAX_USER_PROMPT_CHARS
    assert "test.py" not in prompt
    assert "README.md" not in prompt


def test_prompt_truncates_task_and_includes_at_most_four_relevant_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    changes = []
    for index in range(6):
        name = "payment.py" if index == 0 else f"module_{index}.py"
        (workspace / name).write_text(f"VALUE = {index}\n", encoding="utf-8")
        changes.append(
            ChangedFile(path=name, added_lines=index + 1, deleted_lines=0, protected=False)
        )

    application_changes = IndependentChallengeRunner._application_changes(
        changes,
        "Update payment behavior.",
    )
    prompt = IndependentChallengeRunner._user_prompt(
        application_changes,
        workspace,
        "x" * (MAX_TASK_CHARS + 500),
        "patch",
    )

    assert len(application_changes) == MAX_CHANGED_APPLICATION_FILES
    assert application_changes[0].path == "payment.py"
    assert prompt.count("### ") == MAX_CHANGED_APPLICATION_FILES
    assert "x" * MAX_TASK_CHARS in prompt
    assert "x" * (MAX_TASK_CHARS + 1) not in prompt
    assert len(prompt) <= MAX_USER_PROMPT_CHARS


def test_application_file_selection_is_deterministic_and_excludes_untrusted_inputs() -> None:
    changes = [
        ChangedFile(path="generic.py", added_lines=100, deleted_lines=0, protected=False),
        ChangedFile(path="payment_service.py", added_lines=1, deleted_lines=0, protected=False),
        ChangedFile(path="tests/test_payment.py", added_lines=50, deleted_lines=0, protected=False),
        ChangedFile(path="protected.py", added_lines=50, deleted_lines=0, protected=True),
        ChangedFile(path="payment.md", added_lines=50, deleted_lines=0, protected=False),
    ]

    first = IndependentChallengeRunner._application_changes(changes, "Fix payment behavior")
    second = IndependentChallengeRunner._application_changes(
        list(reversed(changes)),
        "Fix payment behavior",
    )

    assert [change.path for change in first] == ["payment_service.py", "generic.py"]
    assert [change.path for change in second] == ["payment_service.py", "generic.py"]


def test_preservation_challenge_marks_a_regression_unsafe(tmp_path: Path) -> None:
    task = "Refactor the service without changing its returned value."
    repository = create_repository(tmp_path)
    verifier, run_id = verification_run(repository, tmp_path / "artifacts" / "runs", task)
    provider = ScriptedProvider(
        {
            "behavior_mode": "preserve",
            "summary": "The original value must remain stable.",
            "invariants": ["value() still returns 1"],
            "test_code": "from service import value\n\n\ndef test_value_is_preserved() -> None:\n"
            "    assert value() == 1\n",
        }
    )

    report = IndependentChallengeRunner(verifier, provider).run(
        challenge_request(run_id, task)
    )

    assert report.verdict == "UNSAFE"
    assert report.baseline_execution.status == "passed"
    assert report.candidate_execution.status == "failed"


def test_generated_challenge_with_blocked_capability_is_rejected(tmp_path: Path) -> None:
    task = "Change the service value from 1 to 2."
    repository = create_repository(tmp_path)
    verifier, run_id = verification_run(repository, tmp_path / "artifacts" / "runs", task)
    provider = ScriptedProvider(
        {
            "behavior_mode": "change",
            "summary": "Unsafe generated test.",
            "invariants": ["value() returns 2"],
            "test_code": "import subprocess\n\n\ndef test_bad() -> None:\n"
            "    assert subprocess.run(['true']).returncode == 0\n",
        }
    )

    with pytest.raises(ChallengeError, match="blocked capability"):
        IndependentChallengeRunner(verifier, provider).run(challenge_request(run_id, task))


def test_challenge_rejects_a_different_task_from_the_source_run(tmp_path: Path) -> None:
    task = "Change the service value from 1 to 2."
    repository = create_repository(tmp_path)
    verifier, run_id = verification_run(repository, tmp_path / "artifacts" / "runs", task)
    provider = ScriptedProvider({})

    with pytest.raises(ChallengeError, match="does not match"):
        IndependentChallengeRunner(verifier, provider).run(
            challenge_request(run_id, "A different task")
        )
    assert provider.prompts == []


def test_model_provider_accepts_only_loopback_http_endpoints() -> None:
    with pytest.raises(ProviderError, match="only plain HTTP"):
        OpenAICompatibleProvider("https://models.example.com/v1", "remote-model")

    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "local-model")
    assert provider.label == "openai-compatible:local-model"


def test_model_provider_requests_strict_json_schema_and_records_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"behavior_mode":"change"}',
                            "reasoning_content": "brief reasoning",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
            }

    class FakeClient:
        def __init__(self, **options: object) -> None:
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, *arguments: object) -> None:
            return None

        def post(self, endpoint: str, **options: object) -> FakeResponse:
            captured["endpoint"] = endpoint
            captured["request"] = options
            return FakeResponse()

    monkeypatch.setattr("agentproof.provider.httpx.Client", FakeClient)
    provider = OpenAICompatibleProvider("http://127.0.0.1:1234/v1", "local-model")

    completion = provider.complete("system", "user")

    assert completion.prompt_tokens == 12
    assert completion.completion_tokens == 7
    assert completion.finish_reason == "stop"
    assert completion.reasoning_content == "brief reasoning"
    request_json = captured["request"]["json"]
    assert SYSTEM_PROMPT.startswith("/no_think")
    assert request_json["response_format"]["type"] == "json_schema"
    assert request_json["temperature"] == 0
    assert request_json["seed"] == 42
    assert request_json["max_tokens"] == 1536
    assert captured["options"]["trust_env"] is False


def test_model_provider_reports_timeout_and_releases_single_request_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {"content": '{"behavior_mode":"change"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            }

    class FakeClient:
        def __init__(self, **options: object) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, *arguments: object) -> None:
            return None

        def post(self, endpoint: str, **options: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout(
                    "model timed out",
                    request=httpx.Request("POST", endpoint),
                )
            return FakeResponse()

    monkeypatch.setattr("agentproof.provider.httpx.Client", FakeClient)
    provider = OpenAICompatibleProvider(
        "http://127.0.0.1:1234/v1",
        "local-model",
        timeout_seconds=37,
    )

    with pytest.raises(ProviderError, match="within 37 seconds"):
        provider.complete("system", "user")

    completion = provider.complete("system", "user")
    assert completion.finish_reason == "stop"


def test_challenge_request_defaults_to_two_minute_model_timeout() -> None:
    request = IndependentChallengeRequest(
        run_id="run-20260830T100000Z-1234abcd",
        task="Verify one behavior.",
        model_url="http://127.0.0.1:1234/v1",
        model_name="local-model",
    )

    assert request.model_timeout_seconds == 120


def test_empty_length_limited_response_is_preserved_as_failure_evidence(
    tmp_path: Path,
) -> None:
    class EmptyProvider:
        @property
        def label(self) -> str:
            return "scripted:empty"

        def complete(self, system_prompt: str, user_prompt: str) -> ModelCompletion:
            return ModelCompletion(
                content="",
                duration_ms=10,
                prompt_tokens=14_734,
                completion_tokens=1_650,
                finish_reason="length",
                reasoning_content="The model used the remaining context for reasoning.",
            )

    task = "Change the service value from 1 to 2."
    repository = create_repository(tmp_path)
    artifacts_root = tmp_path / "artifacts" / "runs"
    verifier, run_id = verification_run(repository, artifacts_root, task)

    with pytest.raises(ChallengeError, match="exhausted its context window"):
        IndependentChallengeRunner(verifier, EmptyProvider()).run(
            challenge_request(run_id, task)
        )

    trajectories = list((artifacts_root / run_id / "challenges").glob("*/trajectory.json"))
    assert len(trajectories) == 1
    trajectory = json.loads(trajectories[0].read_text(encoding="utf-8"))
    assert trajectory["proposal_accepted"] is False
    assert trajectory["model_finish_reason"] == "length"
    assert trajectory["model_usage"]["prompt_tokens"] == 14_734
