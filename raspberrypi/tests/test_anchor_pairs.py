import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anchor_pair_calibration import AnchorPairs


class AnchorPairTests(unittest.TestCase):
    def make_pairs(self, sides=(3, 4, 5), heights=(1, 1, 1), count=20):
        anchors = {i: {"z": z} for i, z in enumerate(heights)}
        pairs = AnchorPairs(anchors)
        for (a, b), distance in zip(((0, 1), (0, 2), (1, 2)), sides):
            slant = math.hypot(distance, heights[a] - heights[b])
            for seq in range(count):
                pairs.add(a, b, slant * 1000, seq)
        return pairs

    def test_direct_measurements_recover_three_four_five_triangle(self):
        result = self.make_pairs().result()
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "anchor_ranges")
        self.assertEqual(result["anchors"][0], {"x": 0.0, "y": 0.0})
        self.assertEqual(result["anchors"][1], {"x": 3.0, "y": 0.0})
        self.assertEqual(result["anchors"][2], {"x": 0.0, "y": 4.0})

    def test_known_height_difference_is_removed(self):
        result = self.make_pairs(heights=(1, 4, 1)).result()
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["distances"]["12"], 5.0)
        self.assertEqual(result["anchors"][2], {"x": 0.0, "y": 4.0})

    def test_incomplete_or_unstable_pairs_do_not_set_coordinates(self):
        self.assertFalse(self.make_pairs(count=19).result()["ok"])
        pairs = self.make_pairs()
        for seq in range(20, 60):
            pairs.add(0, 1, 2500 if seq % 2 else 3500, seq)
        self.assertFalse(pairs.result()["ok"])

    def test_collinear_and_impossible_triangles_are_rejected(self):
        self.assertFalse(self.make_pairs((1, 2, 3)).result()["ok"])
        self.assertFalse(self.make_pairs((1, 2, 4)).result()["ok"])

    def test_outlier_does_not_replace_stable_median(self):
        pairs = self.make_pairs()
        pairs.add(0, 1, 30000, 20)
        self.assertTrue(pairs.result()["ok"])
        self.assertEqual(pairs.result()["distances"]["01"], 3.0)

    def test_duplicate_measurement_and_unknown_pair_are_ignored(self):
        pairs = self.make_pairs(count=19)
        pairs.add(1, 0, 3000, 0)
        pairs.add(0, 0, 3000, 20)
        pairs.add(0, 3, 3000, 20)
        pairs.add(0, 1, float("nan"), 20)
        self.assertEqual(pairs.counts(), {"01": 19, "02": 19, "12": 19})
        self.assertFalse(pairs.result()["ok"])


if __name__ == "__main__":
    unittest.main()
