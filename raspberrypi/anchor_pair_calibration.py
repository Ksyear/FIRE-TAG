"""Validate an anchor triangle from direct, repeated UWB measurements."""

from collections import deque
import math
from statistics import median


class AnchorPairs:
    PAIRS = ((0, 1), (0, 2), (1, 2))
    MIN_SAMPLES = 20
    MAX_SPREAD_M = 0.15
    MIN_ALTITUDE_M = 0.20

    def __init__(self, anchors):
        self.anchors = anchors
        self.samples = {pair: deque(maxlen=40) for pair in self.PAIRS}
        self.seen = {pair: deque(maxlen=80) for pair in self.PAIRS}

    def counts(self):
        return {f"{a}{b}": len(self.samples[a, b]) for a, b in self.PAIRS}

    def add(self, anchor, peer, range_mm, seq):
        pair = tuple(sorted((anchor, peer)))
        if pair not in self.samples or seq in self.seen[pair]:
            return False
        slant = float(range_mm) / 1000
        dz = self.anchors[anchor].get("z", 0) - self.anchors[peer].get("z", 0)
        if not math.isfinite(slant) or not max(0.02, abs(dz)) < slant < 50:
            return False
        self.samples[pair].append(math.sqrt(slant * slant - dz * dz))
        self.seen[pair].append(seq)
        return True

    def result(self):
        counts = self.counts()
        result = {"ok": False, "source": "anchor_ranges", "counts": counts,
                  "samples": sum(counts.values()), "message": "앵커 간 거리를 수집하고 있습니다."}
        if any(n < self.MIN_SAMPLES for n in counts.values()):
            return result
        distances = {pair: median(self.samples[pair]) for pair in self.PAIRS}
        spread = max(1.4826 * median(abs(x - distances[pair]) for x in self.samples[pair])
                     for pair in self.PAIRS)
        result["spread_m"] = round(spread, 3)
        if spread > self.MAX_SPREAD_M:
            result["message"] = "앵커 간 거리의 산포가 큽니다. 앵커를 고정하고 통신 경로를 확인하세요."
            return result
        d01, d02, d12 = (distances[p] for p in self.PAIRS)
        if max(d01, d02, d12) >= (d01 + d02 + d12) / 2:
            result["message"] = "측정 거리가 삼각 부등식을 만족하지 않습니다. 계속 측정합니다."
            return result
        x = (d01 * d01 + d02 * d02 - d12 * d12) / (2 * d01)
        y = math.sqrt(max(0, d02 * d02 - x * x))
        # Twice the area divided by the longest side is the minimum altitude.
        if d01 * y / max(d01, d02, d12) < self.MIN_ALTITUDE_M:
            result["message"] = "앵커 배치가 거의 일직선입니다. 앵커 세 대를 삼각형으로 배치하세요."
            return result
        result.update(ok=True, anchors={0: {"x": 0.0, "y": 0.0},
                                        1: {"x": round(d01, 3), "y": 0.0},
                                        2: {"x": round(x, 3), "y": round(y, 3)}},
                      distances={f"{a}{b}": round(d, 3) for (a, b), d in distances.items()})
        return result
