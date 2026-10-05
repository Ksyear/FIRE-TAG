#!/usr/bin/env python3
"""Estimate where the three anchors are from Tag ranges alone (self-calibration).

While the Tag moves around, each cycle gives three ranges (to A0, A1, A2).
The anchor triangle and all Tag positions are solved together:
  1. Triangle-inequality bounds give a first guess of the anchor distances
     (|r0 - r1| <= d01 <= r0 + r1 for every cycle).
  2. Alternating least squares: solve Tag positions with the current anchors,
     then each anchor from the Tag positions, repeat.
  3. Fix the frame: A0 at (0, 0), A1 on the +x axis, A2 above the x axis.

Assumes anchors and Tag are at about the same height. Works only if the Tag
moves over an area: along a single line an anchor and its mirror image fit the
ranges equally well. calibrate() therefore solves from many starting guesses
and reports ok=False when equally good solutions disagree.

  python3 anchor_calibration.py --raw data/raw.jsonl            # print result
  python3 anchor_calibration.py --raw data/raw.jsonl --write    # also update config.json
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

from fire_tag_receiver import solve_position

MIN_SAMPLES = 100
MAX_RMS_M = 0.15
MIN_SPREAD_RATIO = 0.25   # Tag path must not be close to a straight line
MAX_SAMPLES = 400         # keeps one calibration run around a second
AMBIGUOUS_M = 0.10        # equally good solutions further apart than this = not unique


def _pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, max(0, int(q * (len(v) - 1))))]


def _triangle(d01, d02, d12):
    x = (d01 * d01 + d02 * d02 - d12 * d12) / (2 * d01)
    y = math.sqrt(max(d02 * d02 - x * x, 1e-6))
    return {0: (0.0, 0.0), 1: (d01, 0.0), 2: (x, y)}


def _regauge(anchors):
    """A0 at origin, A1 on +x, A2 with y > 0."""
    ox, oy = anchors[0]
    moved = {k: (x - ox, y - oy) for k, (x, y) in anchors.items()}
    ang = math.atan2(moved[1][1], moved[1][0])
    c, s = math.cos(-ang), math.sin(-ang)
    rot = {k: (x * c - y * s, x * s + y * c) for k, (x, y) in moved.items()}
    if rot[2][1] < 0:
        rot = {k: (x, -y) for k, (x, y) in rot.items()}
    return rot


def _rms(anchors, samples, tags):
    err = 0.0
    for (r0, r1, r2), (tx, ty) in zip(samples, tags):
        for k, r in ((0, r0), (1, r1), (2, r2)):
            ax, ay = anchors[k]
            err += (math.hypot(tx - ax, ty - ay) - r) ** 2
    return math.sqrt(err / (3 * len(samples)))


def _solve_tags(anchors, samples):
    a = {k: {"x": x, "y": y} for k, (x, y) in anchors.items()}
    tags = []
    for r0, r1, r2 in samples:
        res = solve_position(a, {0: r0, 1: r1, 2: r2})
        tags.append((res[0], res[1]) if res else (0.0, 0.0))
    return tags


def _refine(anchors, samples, iters=40):
    tags = _solve_tags(anchors, samples)
    for _ in range(iters):
        pts = {i: {"x": x, "y": y} for i, (x, y) in enumerate(tags)}
        new = {}
        for k in range(3):
            res = solve_position(pts, {i: s[k] for i, s in enumerate(samples)})
            new[k] = (res[0], res[1]) if res else anchors[k]
        anchors = _regauge(new)
        tags = _solve_tags(anchors, samples)
    return anchors, tags


def calibrate(samples):
    """samples: list of (r0, r1, r2) in metres. Returns a result dict or None."""
    samples = [s for s in samples if all(0.02 < r < 50 for r in s)]
    if len(samples) < 3:
        return None
    if len(samples) > MAX_SAMPLES:
        step = len(samples) / MAX_SAMPLES
        samples = [samples[int(i * step)] for i in range(MAX_SAMPLES)]
    # Robust bounds (percentiles instead of max/min to ignore single bad cycles).
    guesses = []
    for (i, j) in ((0, 1), (0, 2), (1, 2)):
        lo = _pct([abs(s[i] - s[j]) for s in samples], 0.98)
        hi = _pct([s[i] + s[j] for s in samples], 0.02)
        guesses.append((lo, hi))
    rng = random.Random(0)
    starts = [(w, w, w) for w in (0.5, 0.25, 0.75, 0.0, 1.0)]
    starts += [(rng.random(), rng.random(), rng.random()) for _ in range(8)]
    runs = []
    for ws in starts:   # many starting points; keep all to check uniqueness
        d = [lo + w * (hi - lo) if hi > lo else lo for w, (lo, hi) in zip(ws, guesses)]
        if d[0] < 0.05:
            continue
        anchors, tags = _refine(_regauge(_triangle(*d)), samples, iters=25)
        runs.append({"anchors": anchors, "tags": tags, "rms": _rms(anchors, samples, tags)})
    if not runs:
        return None
    best = min(runs, key=lambda r: r["rms"])

    def tri(anc):
        return [math.hypot(anc[p][0] - anc[q][0], anc[p][1] - anc[q][1]) for p, q in ((0, 1), (0, 2), (1, 2))]
    best_d = tri(best["anchors"])
    ambiguous = any(r["rms"] <= best["rms"] * 1.25 + 0.005
                    and max(abs(x - y) for x, y in zip(tri(r["anchors"]), best_d)) > AMBIGUOUS_M
                    for r in runs)
    a = best["anchors"]
    xs = [t[0] for t in best["tags"]]
    ys = [t[1] for t in best["tags"]]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs) / len(xs)
    syy = sum((y - my) ** 2 for y in ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    disc = math.sqrt(max(tr * tr / 4 - det, 0))
    big, small = tr / 2 + disc, max(tr / 2 - disc, 0)
    spread = math.sqrt(small / big) if big > 0 else 0.0
    dist = lambda p, q: math.hypot(a[p][0] - a[q][0], a[p][1] - a[q][1])
    result = {
        "anchors": {k: {"x": round(x, 3), "y": round(y, 3)} for k, (x, y) in a.items()},
        "distances": {"01": round(dist(0, 1), 3), "02": round(dist(0, 2), 3), "12": round(dist(1, 2), 3)},
        "rms_m": round(best["rms"], 3),
        "samples": len(samples),
        "spread": round(spread, 2),
        "unique": not ambiguous,
    }
    result["ok"] = (len(samples) >= MIN_SAMPLES and best["rms"] <= MAX_RMS_M
                    and spread >= MIN_SPREAD_RATIO and not ambiguous)
    return result


def samples_from_raw(path, bias=None):
    """Complete cycles (all three anchors) from a receiver --record file."""
    bias = bias or {}
    cycles = {}
    for line in open(path, encoding="utf-8"):
        if not line.startswith('{"type":"range"'):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        a = int(m["anchor"])
        cycles.setdefault((m["tag"], m["seq"], m.get("anchor_ms", 0) // 60000), {})[a] = \
            m["range_mm"] / 1000.0 - bias.get(a, 0.0)
    return [(c[0], c[1], c[2]) for c in cycles.values() if all(k in c for k in (0, 1, 2))]


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=str(here / "data" / "raw.jsonl"))
    ap.add_argument("--config", default=str(here / "config.json"))
    ap.add_argument("--write", action="store_true", help="write the anchor x, y into config.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    bias = {int(k): v.get("bias_m", 0.0) for k, v in cfg["anchors"].items()}
    res = calibrate(samples_from_raw(args.raw, bias))
    if res is None:
        sys.exit("not enough complete cycles in the recording")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.write:
        if not res["ok"]:
            sys.exit("result not reliable (see ok/rms_m/spread); config.json not changed")
        for k, p in res["anchors"].items():
            cfg["anchors"][str(k)].update(p)
        Path(args.config).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {args.config}")


if __name__ == "__main__":
    main()
