"""Static plots."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection


def plot_trajectories(ax, df, linewidth=1, alpha=0.7):
    """One line per track (columns track_id, timestamp, x, y), colours
    cycling through the axes' colour cycle. All tracks are a single
    LineCollection, so the whole recording draws quickly."""
    d = df.sort_values(["track_id", "timestamp"], kind="stable")
    tid = d["track_id"].to_numpy()
    xy = np.column_stack([d["x"].to_numpy(), d["y"].to_numpy()])
    starts = np.flatnonzero(np.r_[True, tid[1:] != tid[:-1]])
    lines = np.split(xy, starts[1:])
    cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])
    colors = [cycle[i % len(cycle)] for i in range(len(lines))]
    ax.add_collection(LineCollection(lines, colors=colors, linewidths=linewidth, alpha=alpha))
