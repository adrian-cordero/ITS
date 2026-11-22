"""Side graph: number of road users per category over time, with a marker at the current frame."""

import pandas as pd

from its.config import CATEGORY_NAMES
from its.viz.styles import CATEGORY_COLORS


class CountGraph:
    """Use as an AnimationPlayer frame callback to move the markers."""

    def __init__(self, ax, counts: pd.DataFrame, categories):
        self.counts = counts
        self.markers = {}

        for cat in categories:
            color = CATEGORY_COLORS[cat]
            series = counts[cat] if cat in counts.columns else pd.Series(0, index=counts.index)
            ax.plot(counts.index, series, color=color,
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
