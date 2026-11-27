"""
Split trajectories into per-timestamp frames once, so playback stays fast.

The rows are sorted by time once and kept as flat arrays; a frame is
just a start and end index into them. frames[i] builds that frame's
Frame on demand, from views of those arrays (nothing is copied), so the
whole recording (~165k frames, ~3M cyclist rows) costs little more than
the data itself.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba

from its.viz.styles import CATEGORY_COLORS, DEFAULT_CATEGORY_COLOR


@dataclass
class Frame:
    timestamp: float
    offsets: np.ndarray      # (n, 2) positions in PLOT_CRS
    colors: np.ndarray       # (n, 4) RGBA per road user
    categories: np.ndarray   # (n,)
    ids: np.ndarray          # (n,) track_id
    part: int | None = None  # trajectory part, when the data has a `part` column


class Frames:
    """A list-like of Frames: len(frames), frames[i], frames.timestamps."""

    def __init__(self, timestamps, starts, xy, categories, ids, color_lut, parts=None):
        self.timestamps = timestamps          # (n_frames,)
        self._starts = starts                 # (n_frames + 1,) row ranges
        self._xy = xy
        self._cats = categories
        self._ids = ids
        self._lut = color_lut                 # category code -> RGBA
        self.parts = parts                    # (n_frames,) or None

    def __len__(self):
        return len(self.timestamps)

    def __getitem__(self, i):
        if i < 0:
            i += len(self)
        a, b = self._starts[i], self._starts[i + 1]
        cats = self._cats[a:b]
        return Frame(float(self.timestamps[i]), self._xy[a:b], self._lut[cats], cats,
                     self._ids[a:b], None if self.parts is None else int(self.parts[i]))


def precompute_frames(df: pd.DataFrame, colors=CATEGORY_COLORS,
                      default_color=DEFAULT_CATEGORY_COLOR) -> Frames:
    """Frames for `df` (needs columns timestamp, x, y, category, track_id;
    `part` is used when present)."""
    t = df["timestamp"].to_numpy()
    order = None if np.all(t[1:] >= t[:-1]) else np.argsort(t, kind="stable")

    def col(name, dtype=None):
        a = df[name].to_numpy(dtype=dtype)
        return a if order is None else a[order]

    t = col("timestamp")
    xy = np.column_stack([col("x"), col("y")])
    cats = col("category", np.int64)
    ids = col("track_id")

    unique_t, starts = np.unique(t, return_index=True)
    starts = np.append(starts, len(t))

    lut = np.tile(np.array(to_rgba(default_color)), (max(int(cats.max(initial=0)), *colors) + 1, 1))
    for cat, c in colors.items():
        lut[cat] = to_rgba(c)

    parts = col("part")[starts[:-1]] if "part" in df.columns and len(t) else None
    return Frames(unique_t, starts, xy, cats, ids, lut, parts)
