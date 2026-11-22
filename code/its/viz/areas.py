"""Draw crossing-area lines (start edge, end edge, N lines in between)."""

from matplotlib.lines import Line2D

from its.viz.styles import CROSSING_LINE_STYLES, CROSSING_LINE_ZORDER


def draw_crossing_lines(ax, lines, styles=CROSSING_LINE_STYLES):
    """
    Draw the output of its.areas.load_crossing_lines (already in the
    plot CRS). Returns legend handles.
    """
    handles = []
    for role in ("line", "start", "end"):
        subset = lines[lines["role"] == role]
        if subset.empty:
            continue
        style = dict(styles[role])
        label = style.pop("label")
        subset.plot(ax=ax, zorder=CROSSING_LINE_ZORDER, **style)
        handles.append(Line2D([0], [0], label=label, **style))
    return handles
