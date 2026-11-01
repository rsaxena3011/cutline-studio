import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compare.compare import beat_flags, compare_target
from src.segment.measurements import measure_mask
from src.segment.segment import Segmentation
from tests.test_ledger import make_ledger


def seg(found, mask=None):
    measurement = measure_mask(mask) if found and mask is not None else None
    return Segmentation(object_name="brass lamp", found=found,
                        mask=mask if found else None, measurement=measurement)


def block_mask(x0, x1, y0=10, y1=30, shape=(100, 200)):
    mask = np.zeros(shape, dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask


class TestCompareRules(unittest.TestCase):
    def test_missing_object_blocks(self):
        a = make_ledger("take_a", lamp_present=True)
        b = make_ledger("take_b", lamp_present=False)
        record = compare_target(a, b, seg(True, block_mask(50, 70)),
                                seg(False), "brass lamp")
        self.assertEqual(record["verdict"], "BLOCK")
        self.assertEqual(record["flags"][0]["rule"], "object_missing")

    def test_edge_contact_is_review_never_block(self):
        # Same-size mask in both takes; in take B it sits against the
        # right edge. The only flag must be the cropping warning, at
        # REVIEW severity: edge contact is a warning, never proof, so
        # it never BLOCKs on its own.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        record = compare_target(
            a, b,
            seg(True, block_mask(320, 360, shape=(100, 400))),
            seg(True, block_mask(360, 400, shape=(100, 400))),
            "brass lamp")
        self.assertEqual(len(record["flags"]), 1)
        self.assertEqual(record["flags"][0]["rule"], "cropping_warning")
        self.assertEqual(record["flags"][0]["severity"], "REVIEW")
        self.assertEqual(record["verdict"], "REVIEW")

    def test_no_mask_but_ledger_present_is_review(self):
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        record = compare_target(a, b, seg(True, block_mask(50, 70)),
                                seg(False), "brass lamp")
        self.assertEqual(record["verdict"], "REVIEW")
        self.assertEqual(record["flags"][0]["rule"], "cannot_verify")

    def test_clean_pair_allows(self):
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        record = compare_target(a, b, seg(True, block_mask(50, 70)),
                                seg(True, block_mask(51, 71)), "brass lamp")
        self.assertEqual(record["verdict"], "ALLOW")
        self.assertEqual(record["flags"], [])

    def test_big_area_change_blocks(self):
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        record = compare_target(a, b, seg(True, block_mask(50, 90)),
                                seg(True, block_mask(50, 60)), "brass lamp")
        self.assertEqual(record["verdict"], "BLOCK")
        self.assertIn("mask_area_change", {f["rule"] for f in record["flags"]})

    def test_unrecorded_object_is_review_never_allow(self):
        # Review round 1, R1-01: the target is missing from ledger_b's
        # object list entirely. The old code returned a silent ALLOW.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        b["objects"] = [o for o in b["objects"]
                        if o["name"] != "brass lamp"]
        record = compare_target(a, b, seg(True, block_mask(50, 70)),
                                seg(False), "brass lamp")
        self.assertEqual(record["verdict"], "REVIEW")
        self.assertEqual(record["flags"][0]["rule"], "cannot_verify")

    def test_vertical_move_blocks(self):
        # Review round 1, R1-02: movement is checked on both axes.
        # Same-size mask moved down by 40 percent of frame height.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        record = compare_target(
            a, b,
            seg(True, block_mask(50, 70, y0=10, y1=30)),
            seg(True, block_mask(50, 70, y0=50, y1=70)),
            "brass lamp")
        self.assertEqual(record["verdict"], "BLOCK")
        self.assertIn("mask_moved", {f["rule"] for f in record["flags"]})

    def test_area_rule_uses_frame_share_not_pixels(self):
        # Review round 2, R2-02: the same relative object in a
        # half-resolution take has a quarter of the pixels but the
        # same share of the frame. That is not a size change.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        big = np.zeros((100, 200), dtype=bool)
        big[10:30, 50:70] = True
        small = np.zeros((50, 100), dtype=bool)
        small[5:15, 25:35] = True
        record = compare_target(a, b, seg(True, big), seg(True, small),
                                "brass lamp")
        self.assertEqual(record["verdict"], "ALLOW")
        self.assertEqual(record["flags"], [])

    def test_beat_mismatch_flags_review(self):
        # Review round 2, R2-01: a beat observed in one take and not
        # the other used to vanish entirely. It now flags at scene
        # level, at REVIEW severity.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        b["beats"] = [{"beat": "intro", "observed": False}]
        flags = beat_flags(a, b)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["rule"], "beat_mismatch")
        self.assertEqual(flags[0]["severity"], "REVIEW")
        self.assertEqual(beat_flags(a, a), [])

    def test_scene_mismatch_is_an_error(self):
        # Review round 1, R1-03: two takes of different scenes must
        # not compare at all.
        a = make_ledger("take_a")
        b = make_ledger("take_b")
        b["scene_id"] = "a-different-scene"
        with self.assertRaises(ValueError):
            compare_target(a, b, seg(True, block_mask(50, 70)),
                           seg(True, block_mask(50, 70)), "brass lamp")


if __name__ == "__main__":
    unittest.main()
