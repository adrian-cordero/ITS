"""Split trajectories into per-timestamp frames once, so playback stays fast."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from its.viz.styles import CATEGORY_COLORS, DEFAULT_CATEGORY_COLOR


@dataclass
class Frame:
    timestamp: float
    offsets: np.ndarray      # (n, 2) positions in PLOT_CRS
    colors: np.ndarray       # (n,) colour per road user
    categories: np.ndarray   # (n,)
    ids: np.ndarray          # (n,) track_id


def precompute_frames(df: pd.DataFrame, colors=CATEGORY_COLORS,
                      default_color=DEFAULT_CATEGORY_COLOR) -> list:
    """One Frame per timestamp in `df` (needs columns timestamp, x, y, category, track_id)."""
    df = df.sort_values("timestamp", kind="stable")

    timestamps = df["timestamp"].to_numpy()
    xy = df[["x", "y"]].to_numpy()
    cats = df["category"].to_numpy()
    ids = df["track_id"].to_numpy()
    cols = df["category"].map(colors).fillna(default_color).to_numpy()

    unique_t, starts = np.unique(timestamps, return_index=True)
    ends = np.append(starts[1:], len(df))

    return [
        Frame(t, xy[a:b], cols[a:b], cats[a:b], ids[a:b])
        for t, a, b in zip(unique_t, starts, ends)
    ]
