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
default demo path), and is the only judge implemented today. A live
Muse Spark client does not exist yet; when it is built it must follow
the same citation contract, and its citations must resolve the same
way FixtureJudge now requires: cited frames must be files in the
bundle and cited ledger lines must name real takes and objects.
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
    """Cached judgments from a fixture bundle's judgments.json.

    A cached judgment is served only if its citations resolve inside
    the bundle: every cited frame must be a file in the bundle, and
    every cited ledger line must name a take and an object that take's
    ledger actually records (checked when the bundle carries ledgers).
    A judgment whose citations do not resolve is treated as no
    judgment at all, so settle() raises the question to the human.
    """

    def __init__(self, bundle_dir: str):
        self.bundle_dir = bundle_dir
        path = os.path.join(bundle_dir, "judgments.json")
        self.judgments: dict = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                self.judgments = json.load(fh)
        self.ledger_lines: set = set()
        for name in ("ledger_a.json", "ledger_b.json"):
            ledger_path = os.path.join(bundle_dir, name)
            if os.path.isfile(ledger_path):
                with open(ledger_path, encoding="utf-8") as fh:
                    ledger = json.load(fh)
                for obj in ledger.get("objects", []):
                    self.ledger_lines.add(
                        f"{ledger['take_id']}.objects[{obj['name']}]")

    def _citations_resolve(self, judgment: dict) -> bool:
        citations = judgment.get("citations") or {}
        bundle_root = os.path.realpath(self.bundle_dir)
        for frame in citations.get("frames") or []:
            frame_path = os.path.realpath(os.path.join(bundle_root, frame))
            if not frame_path.startswith(bundle_root + os.sep):
                return False
            if not os.path.isfile(frame_path):
                return False
        if self.ledger_lines:
            for line in citations.get("ledger_lines") or []:
                if line not in self.ledger_lines:
                    return False
        return True

    def answer(self, question_key: str) -> dict | None:
        judgment = self.judgments.get(question_key)
        if judgment is None:
            return None
        if validate_judgment(judgment) and not self._citations_resolve(judgment):
            return None
        return judgment
