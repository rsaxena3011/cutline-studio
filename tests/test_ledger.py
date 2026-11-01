import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ledger.ledger import diff_ledgers, validate_ledger


def make_ledger(take_id, lamp_present=True):
    return {
        "scene_id": "s1",
        "take_id": take_id,
        "source": {"kind": "still", "frame_time_seconds": None},
        "objects": [
            {"name": "brass lamp", "category": "prop", "present": lamp_present,
             "description": "on the desk"},
            {"name": "blue jacket", "category": "wardrobe", "present": True},
        ],
        "beats": [{"beat": "intro", "observed": True}],
    }


class TestLedger(unittest.TestCase):
    def test_valid_ledger_passes(self):
        self.assertEqual(validate_ledger(make_ledger("take_a")), [])

    def test_invalid_ledger_reports_errors(self):
        bad = {"scene_id": "s1"}
        errors = validate_ledger(bad)
        self.assertTrue(any("take_id" in e for e in errors))
        bad2 = make_ledger("take_a")
        bad2["objects"][0]["category"] = "unknown-thing"
        self.assertTrue(any("category" in e for e in validate_ledger(bad2)))

    def test_identical_ledgers_zero_diffs(self):
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        self.assertEqual(diff_ledgers(a, b), [])

    def test_duplicate_object_names_are_rejected(self):
        # Review round 1, R1-06: name-keyed consumers would silently
        # keep only the last of two same-named entries.
        led = make_ledger("take_a")
        led["objects"].append({"name": "brass lamp", "category": "prop",
                               "present": False})
        errors = validate_ledger(led)
        self.assertTrue(any("duplicates" in e for e in errors))

    def test_presence_diff_is_verdict_grade(self):
        a = make_ledger("take_a", lamp_present=True)
        b = make_ledger("take_b", lamp_present=False)
        diffs = diff_ledgers(a, b)
        presence = [d for d in diffs if d["kind"] == "presence"]
        self.assertEqual(len(presence), 1)
        self.assertEqual(presence[0]["object"], "brass lamp")
        self.assertEqual(presence[0]["take_a"], True)
        self.assertEqual(presence[0]["take_b"], False)


if __name__ == "__main__":
    unittest.main()
