"""Static plots."""


def plot_trajectories(ax, df, linewidth=1, alpha=0.7):
    """One line per track (columns track_id, timestamp, x, y)."""
    for _, track in df.groupby("track_id"):
        track = track.sort_values("timestamp")
        ax.plot(track["x"], track["y"], linewidth=linewidth, alpha=alpha)
