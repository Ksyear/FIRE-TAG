from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fire_tag_web import trail_segments
from fire_tag_receiver import solve_position


class TrailTests(unittest.TestCase):
    def points(self, values):
        return [{"t": t, "x": x, "y": y} for t, x, y in values]

    def test_stationary_jitter_does_not_make_a_spaghetti_path(self):
        points = self.points([(0, 1, 1), (.1, 1.1, .95), (.2, .9, 1.1),
                              (.5, 1.05, 1.02), (1, 1, 1)])
        self.assertEqual(trail_segments(points), [[[1, 1]]])

    def test_a_large_instantaneous_jump_is_not_connected_by_a_line(self):
        points = self.points([(0, 0, 0), (.1, 4, 5), (.2, .1, 0), (.7, .5, 0), (1.2, .9, 0)])
        self.assertEqual(trail_segments(points), [[[0, 0]], [[4, 5]], [[.1, 0], [.5, 0], [.9, 0]]])

    def test_ordinary_walking_and_time_gaps_remain_visible(self):
        points = self.points([(0, 0, 0), (.5, .4, 0), (1, .8, 0), (3, 1.2, 0), (3.5, 1.6, 0)])
        self.assertEqual(trail_segments(points), [[[0, 0], [.4, 0], [.8, 0]], [[1.2, 0], [1.6, 0]]])

    def test_mirrored_anchor_coordinates_produce_a_mirrored_solution(self):
        ranges = {0: 5**.5, 1: 8**.5, 2: 5**.5}
        anchors = {0: {"x": 0, "y": 0}, 1: {"x": 3, "y": 0}, 2: {"x": 0, "y": 4}}
        x, y, _ = solve_position(anchors, ranges)
        mirrored = {k: {"x": -a["x"], "y": a["y"]} for k, a in anchors.items()}
        mx, my, _ = solve_position(mirrored, ranges)
        self.assertAlmostEqual(x, 1)
        self.assertAlmostEqual(y, 2)
        self.assertAlmostEqual(mx, -1)
        self.assertAlmostEqual(my, 2)


if __name__ == "__main__": unittest.main()
