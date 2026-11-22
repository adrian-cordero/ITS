"""Category legend (optionally with live counts) and the project-layer legend."""

import numpy as np
from matplotlib.lines import Line2D

from its.config import CATEGORY_NAMES
from its.viz.styles import CATEGORY_COLORS


def category_legend(ax, categories, loc="upper right"):
    handles = [
        Line2D([0], [0], marker="o", color="w", label=CATEGORY_NAMES[cat],
               markerfacecolor=CATEGORY_COLORS[cat], markersize=8)
        for cat in categories
    ]
    return ax.legend(handles=handles, title="Categories", loc=loc)


class LiveCategoryCounts:
    """
    Frame callback for AnimationPlayer: shows how many road users of each
    category are on screen, e.g. "Bicycle (12)".
    """

    def __init__(self, legend, categories):
        self.texts = dict(zip(categories, legend.get_texts()))

    def __call__(self, frame):
        cats, counts = np.unique(frame.categories, return_counts=True)
        on_screen = dict(zip(cats, counts))
        for cat, text in self.texts.items():
            text.set_text(f"{CATEGORY_NAMES[cat]} ({on_screen.get(cat, 0)})")


def layer_legend(ax, handles, keep=None):
    """
    Legend for the project layers, placed below the map so it never
    covers the intersection. `keep` is an existing legend on `ax` that
    would otherwise be replaced.
    """
    if not handles:
        return None
    if keep is not None:
        ax.add_artist(keep)
    return ax.legend(handles=handles, title="Layers", loc="upper left",
                     bbox_to_anchor=(0, -0.08), ncol=len(handles))
