import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.segment.measurements import (edge_contact, mask_area, mask_bbox,
                                      mask_centroid, measure_mask)


class TestMeasurements(unittest.TestCase):
    def test_area_and_centroid(self):
        mask = np.zeros((10, 20), dtype=bool)
        mask[2:5, 4:8] = True
        self.assertEqual(mask_area(mask), 12)
        cx, cy = mask_centroid(mask)
        self.assertAlmostEqual(cx, 5.5)
        self.assertAlmostEqual(cy, 3.0)
        self.assertEqual(mask_bbox(mask), (4, 2, 7, 4))

    def test_empty_mask(self):
        mask = np.zeros((10, 20), dtype=bool)
        self.assertEqual(mask_area(mask), 0)
        self.assertIsNone(mask_centroid(mask))
        self.assertIsNone(mask_bbox(mask))
        self.assertFalse(any(edge_contact(mask).values()))

    def test_edge_contact(self):
        mask = np.zeros((10, 20), dtype=bool)
        mask[0:3, 18:20] = True
        contact = edge_contact(mask)
        self.assertTrue(contact["top"])
        self.assertTrue(contact["right"])
        self.assertFalse(contact["left"])
        self.assertFalse(contact["bottom"])
        record = measure_mask(mask)
        self.assertTrue(record["touches_edge"])
        self.assertEqual(record["frame"], {"width": 20, "height": 10})


if __name__ == "__main__":
    unittest.main()
