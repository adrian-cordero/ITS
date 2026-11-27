"""Side graph: number of road users per category over time, with a marker at the current frame.

Long recordings are drawn as one-second means (the line only; the marker
shows the exact count of the current frame), so the graph stays quick to
redraw when zooming.
"""

import numpy as np
import pandas as pd

from its.config import CATEGORY_NAMES
from its.viz.styles import CATEGORY_COLORS


class CountGraph:
    """Use as an AnimationPlayer frame callback to move the markers."""

    def __init__(self, ax, counts: pd.DataFrame, categories, max_points=20_000, bin_s=1.0):
        self.counts = counts
        self.markers = {}
        shown = counts
        if len(counts) > max_points:
            shown = counts.groupby(np.floor(counts.index.to_numpy() / bin_s) * bin_s).mean()

        for cat in categories:
            color = CATEGORY_COLORS[cat]
            series = shown[cat] if cat in shown.columns else pd.Series(0, index=shown.index)
            ax.plot(shown.index, series, color=color,
                    label=CATEGORY_NAMES[cat], linewidth=2)
            self.markers[cat], = ax.plot([], [], "o", color=color, markersize=8)

        ax.set_title("Objects over time")
        ax.set_xlabel("Timestamp")
        ax.set_ylabel("Count")
        ax.legend()
        ax.grid(True)

    def __call__(self, frame):
        t = frame.timestamp
        for cat, marker in self.markers.items():
            n = self.counts.at[t, cat] if cat in self.counts.columns else 0
            marker.set_data([t], [n])
