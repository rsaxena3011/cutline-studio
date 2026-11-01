"""Judgment layer.

Reviews only what deterministic comparison cannot settle: identity
under a lighting change, restyle versus replacement. The discipline is
structural, not a prompt suggestion:

- Every judgment must cite the ledger lines and the frame identifiers
  it rests on. A judgment without citations is discarded by
  validate_judgment, and the question falls back to a REVIEW flag for
  the human.
- Uncertainty is returned as a flag for the human, never as a pass.

FixtureJudge serves cached judgments from a fixture bundle (the
default demo path). SparkJudge is the live Muse Spark client slot;
it follows the same citation contract.
"""

from __future__ import annotations

import json
import os


def validate_judgment(judgment: dict) -> bool:
    """A judgment stands only if it cites ledger lines and frames."""
    if not isinstance(judgment, dict):
        return False
    citations = judgment.get("citations") or {}
    ledger_lines = citations.get("ledger_lines") or []
    frames = citations.get("frames") or []
    return bool(judgment.get("decision")) and bool(ledger_lines) and bool(frames)


def settle(question_key: str, judgment: dict | None) -> dict:
    """Turn a judgment (or its absence) into a review record.

    No judgment, or a judgment that fails validation, becomes REVIEW:
    the human decides. A valid judgment carries its citations through
    as evidence.
    """
    if judgment is None or not validate_judgment(judgment):
        return {
            "question": question_key,
            "verdict": "REVIEW",
            "decision": None,
            "reason": "No cited judgment available. Raised to the human.",
            "citations": None,
        }
    effect = (judgment.get("verdict_effect") or "").lower()
    verdict = {"allow": "ALLOW", "block": "BLOCK", "review": "REVIEW"}.get(
        effect, "REVIEW")
    return {
        "question": question_key,
        "verdict": verdict,
        "decision": judgment.get("decision"),
        "reason": judgment.get("rationale"),
        "citations": judgment.get("citations"),
    }


class FixtureJudge:
    """Cached judgments from a fixture bundle's judgments.json."""

    def __init__(self, bundle_dir: str):
        path = os.path.join(bundle_dir, "judgments.json")
        self.judgments: dict = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                self.judgments = json.load(fh)

    def answer(self, question_key: str) -> dict | None:
        return self.judgments.get(question_key)
