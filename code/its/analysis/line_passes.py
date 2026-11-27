"""
Line passes: road users going over a line segment, and in which direction.

A line pass is a step between two consecutive positions of the same
track that intersects the segment. Its direction is +1 when the step
moves along `normal` (for a crossing: from the start line towards the
end line) and -1 against it. The pass time is interpolated between the
two timestamps. ("Crossing" is kept for the band between two waiting
areas, its.crossings; it is never an event.)

Positions (utm_x, utm_y) and lines are in METRIC_CRS.
"""

import numpy as np
import pandas as pd

_COLUMNS = ["track_id", "time", "direction", "x", "y"]


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def line_passes(df: pd.DataFrame, line, normal) -> pd.DataFrame:
    """
    Every time a track crosses the segment `line`.

    df      rows with columns track_id, timestamp, utm_x, utm_y
    line    shapely LineString with two points
    normal  (dx, dy): the "forward" direction

    Returns columns track_id, time, direction (+1 forward / -1 backward),
    x, y (the crossing point), sorted by time.
    """
    d = df.sort_values(["track_id", "timestamp"], kind="stable")
    tid = d["track_id"].to_numpy()
    t = d["timestamp"].to_numpy()
    px, py = d["utm_x"].to_numpy(), d["utm_y"].to_numpy()

    same = tid[1:] == tid[:-1]                       # step stays within one track
    p0x, p0y, p1x, p1y = px[:-1], py[:-1], px[1:], py[1:]
    sx, sy = p1x - p0x, p1y - p0y                    # step vector

    (ax, ay), (bx, by) = np.asarray(line.coords)[:2, :2]
    ex, ey = bx - ax, by - ay                        # line vector

    denom = _cross(sx, sy, ex, ey)
    with np.errstate(divide="ignore", invalid="ignore"):
        qx, qy = ax - p0x, ay - p0y
        s_frac = _cross(qx, qy, ex, ey) / denom      # where along the step
        l_frac = _cross(qx, qy, sx, sy) / denom      # where along the line

    # 0 < s_frac <= 1: a point exactly on the line counts once, not twice
    hit = same & (denom != 0) & (s_frac > 0) & (s_frac <= 1) & (l_frac >= 0) & (l_frac <= 1)
    if not hit.any():
        return pd.DataFrame(columns=_COLUMNS)

    i = np.flatnonzero(hit)
    f = s_frac[i]
    direction = np.sign(sx[i] * normal[0] + sy[i] * normal[1]).astype(int)

    out = pd.DataFrame({
        "track_id": tid[i],
        "time": t[i] + f * (t[i + 1] - t[i]),
        "direction": direction,
        "x": p0x[i] + f * sx[i],
        "y": p0y[i] + f * sy[i],
    })
    return out.sort_values("time", kind="stable").reset_index(drop=True)


def forward_normal(start_line, end_line):
    """Unit normal of `start_line` pointing towards `end_line` (start -> end)."""
    s = np.asarray(start_line.coords)[:2, :2]
    u = (s[1] - s[0]) / np.linalg.norm(s[1] - s[0])
    n = np.array([-u[1], u[0]])
    e_mid = np.asarray(end_line.coords)[:2, :2].mean(axis=0)
    return n if np.dot(e_mid - s.mean(axis=0), n) >= 0 else -n


def first_forward_per_track(crossings: pd.DataFrame) -> pd.DataFrame:
    """
    One row per track: its first forward (+1) crossing. A bike that
    wobbles back and forth over the line counts once.
    """
    fwd = crossings[crossings["direction"] > 0]
    return fwd.sort_values("time").drop_duplicates("track_id").reset_index(drop=True)
