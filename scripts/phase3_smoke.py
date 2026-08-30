"""Run one transparent synthetic smoke case against a loaded local model."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from agentproof.challenges import ChallengeError, IndependentChallengeRunner
from agentproof.models import IndependentChallengeRequest, VerificationRequest
from agentproof.verifier import DeterministicVerifier

TASK = (
    "Update greeting(name) so it trims surrounding whitespace and treats a blank name as "
    '"friend", while preserving the existing greeting format.'
)
PATCH = """diff --git a/greeting.py b/greeting.py
--- a/greeting.py
+++ b/greeting.py
@@ -1,2 +1,3 @@
 def greeting(name: str) -> str:
-    return f"Hello, {name}!"
+    clean_name = name.strip()
+    return f"Hello, {clean_name or 'friend'}!"
"""


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repository), *arguments], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument(
        "--model-name",
        default="auto",
        help="Loaded model ID, or 'auto' to use the only loaded text-generation model.",
    )
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="agentproof-phase3-") as temporary:
        repository = Path(temporary) / "greeting-service"
        (repository / "tests").mkdir(parents=True)
        (repository / "greeting.py").write_text(
            'def greeting(name: str) -> str:\n    return f"Hello, {name}!"\n',
            encoding="utf-8",
        )
        (repository / "tests" / "test_greeting.py").write_text(
            "from greeting import greeting\n\n\ndef test_regular_name() -> None:\n"
            '    assert greeting("Ada") == "Hello, Ada!"\n',
            encoding="utf-8",
        )
        _git(repository, "init", "--quiet")
        _git(repository, "add", ".")
        _git(
            repository,
            "-c",
            "user.name=AgentProof Smoke",
            "-c",
            "user.email=smoke@agentproof.local",
            "commit",
            "--quiet",
            "-m",
            "Smoke baseline",
        )

        verifier = DeterministicVerifier()
        verification = verifier.verify(
            VerificationRequest(repository_path=str(repository), task=TASK, patch=PATCH)
        )
        try:
            challenge = IndependentChallengeRunner(verifier).run(
                IndependentChallengeRequest(
                    run_id=verification.run_id,
                    task=TASK,
                    model_url=arguments.model_url,
                    model_name=arguments.model_name,
                )
            )
        except ChallengeError as error:
            print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
            return 1

    print(
        json.dumps(
            {
                "verification_run_id": verification.run_id,
                "baseline_verdict": verification.verdict,
                "challenge_id": challenge.challenge_id,
                "challenge_verdict": challenge.verdict,
                "summary": challenge.summary,
                "invariants": challenge.proposal.invariants,
                "baseline_challenge": challenge.baseline_execution.status,
                "candidate_challenge": challenge.candidate_execution.status,
                "prompt_tokens": challenge.model.prompt_tokens,
                "completion_tokens": challenge.model.completion_tokens,
                "model_duration_ms": challenge.model.duration_ms,
                "evidence_path": challenge.evidence_path,
            },
            indent=2,
        )
    )
    return 0 if challenge.verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
