import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compare.compare import compare_target
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


if __name__ == "__main__":
    unittest.main()
