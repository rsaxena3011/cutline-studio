import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.judge.judge import FixtureJudge, settle, validate_judgment
from src.ledger.ledger import validate_ledger

BUNDLE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "studio_desk")


def read_json(name):
    with open(os.path.join(BUNDLE, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestFixtureBundle(unittest.TestCase):
    def test_bundle_ledgers_are_schema_valid(self):
        self.assertEqual(validate_ledger(read_json("ledger_a.json")), [])
        self.assertEqual(validate_ledger(read_json("ledger_b.json")), [])

    def test_judgment_citations_point_at_real_frames(self):
        judge = FixtureJudge(BUNDLE)
        judgment = judge.answer("jacket_identity")
        self.assertIsNotNone(judgment)
        self.assertTrue(validate_judgment(judgment))
        for frame in judgment["citations"]["frames"]:
            self.assertTrue(os.path.isfile(os.path.join(BUNDLE, frame)),
                            f"cited frame missing: {frame}")

    def test_uncited_judgment_falls_back_to_review(self):
        record = settle("q", {"decision": "same_item", "citations": {}})
        self.assertEqual(record["verdict"], "REVIEW")
        record = settle("q", None)
        self.assertEqual(record["verdict"], "REVIEW")

    def test_cited_judgment_settles(self):
        judge = FixtureJudge(BUNDLE)
        record = settle("jacket_identity", judge.answer("jacket_identity"))
        self.assertEqual(record["verdict"], "ALLOW")
        self.assertEqual(record["decision"], "same_item")


if __name__ == "__main__":
    unittest.main()
