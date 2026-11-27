"""
Drawing shared by the event viewers (detect_queue_events.py, view_discharges.py):
the crossings and their waiting areas, drawn in a crossing's local frame
(its.analysis.start_stop.LocalFrame) or in METRIC_CRS.
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np

from its.crossings import crossing_areas_path, crossing_lines, load_crossing_lines, load_source
from its.config import CROSSING_AREAS_LAYER, METRIC_CRS
from its.viz.styles import CROSSING_LINE_STYLES

START_COLOR = CROSSING_LINE_STYLES["start"]["color"]
END_COLOR = CROSSING_LINE_STYLES["end"]["color"]
MID_STYLE = dict(color=CROSSING_LINE_STYLES["line"]["color"], linewidth=0.8)

# map layers the viewers can switch on and off: waiting_areas.gpkg and the
# crossing bands of crossing_areas.gpkg
LAYER_STYLE = {
    "waiting areas":  dict(facecolor="orange", edgecolor="darkorange", linestyle="-"),
    "crossing areas": dict(facecolor="teal", edgecolor="teal", linestyle="--"),
}


# --------------------------------------------------
# DATA
# --------------------------------------------------


def load_crossings(layer, only=None):
    """[{crossing_id, start_area, area_polygon, start_line, end_line}] in METRIC_CRS."""
    path = crossing_areas_path(layer)
    if not path.exists():
        raise SystemExit(f"{path.name} not found: make crossings with define_crossings.py first")
    areas = load_source(layer)
    bands = gpd.read_file(path, layer=CROSSING_AREAS_LAYER)
    start_area = dict(zip(bands["crossing_id"], bands["start_area"]))
    lines = load_crossing_lines(layer, 0)
    out = []
    for cid, grp in lines.groupby("crossing_id"):
        if only is not None and cid not in only:
            continue
        by_role = dict(zip(grp["role"], grp.geometry))
        a = int(start_area[cid])
        out.append({"crossing_id": int(cid), "start_area": a,
                    "area_polygon": areas.geometry.iloc[a],
                    "start_line": by_role["start"], "end_line": by_role["end"]})
    return out


def load_bands(layer):
    """{crossing_id: band polygon} in METRIC_CRS."""
    bands = gpd.read_file(crossing_areas_path(layer), layer=CROSSING_AREAS_LAYER).to_crs(METRIC_CRS)
    return dict(zip(bands["crossing_id"].astype(int), bands.geometry))


def load_mid_lines(layer, n):
    """{crossing_id: [lines between start and end]}, N per crossing as in animate.py."""
    lines = load_crossing_lines(layer, n)
    mid = lines[lines["role"] == "line"]
    return {int(cid): list(g.geometry) for cid, g in mid.groupby("crossing_id")}


def mid_lines_of(crossing, n):
    """The N lines between a crossing's start and end line."""
    return crossing_lines(crossing["start_line"], crossing["end_line"], n)


# --------------------------------------------------
# DRAWING
# --------------------------------------------------


def draw_shape(ax, xs, ys, layer, strong=False, zorder=1):
    """One polygon outline (xs, ys) in a LAYER_STYLE style; `strong` = the event's own."""
    st = LAYER_STYLE[layer]
    ax.fill(xs, ys, color=st["facecolor"], alpha=0.25 if strong else 0.15, zorder=zorder, lw=0)
    ax.plot(xs, ys, color=st["edgecolor"], linestyle=st["linestyle"],
            linewidth=2.2 if strong else 1.2, zorder=zorder + 1)


def draw_local_crossing(ax, frame, polygon, start_line, band=None, mid_lines=(), end_line=None,
                        layers=None):
    """
    A crossing's waiting area, band and lines in its local frame. `layers`
    switches "waiting areas", "crossing areas" and "crossing lines" (all on
    when None). Returns (xs, ys): the drawn points, for the axis limits.
    """
    on = (lambda name: True) if layers is None else (lambda name: layers.get(name, True))
    lx, ly = frame.coords_local(start_line)
    xs, ys = [lx], [ly]
    if on("waiting areas"):
        px, py = frame.coords_local(polygon)
        draw_shape(ax, px, py, "waiting areas", strong=True)
        xs.append(px)
        ys.append(py)
    if on("crossing areas") and band is not None:
        bx, by = frame.coords_local(band)
        draw_shape(ax, bx, by, "crossing areas", strong=True)
        xs.append(bx)
        ys.append(by)
    ax.plot(lx, ly, color=START_COLOR, linewidth=3, zorder=3)
    if end_line is not None:
        ex, ey = frame.coords_local(end_line)
        ax.plot(ex, ey, color=END_COLOR, linewidth=3, zorder=3)
        xs.append(ex)
        ys.append(ey)
    if on("crossing lines"):
        for line in mid_lines:
            ax.plot(*frame.coords_local(line), zorder=3, **MID_STYLE)
    return np.concatenate(xs), np.concatenate(ys)


# --------------------------------------------------
# WINDOW
# --------------------------------------------------


def free_keys(*keys):
    """Take `keys` away from matplotlib's own shortcuts, so a viewer can use them."""
    for key in keys:
        for name, bound in plt.rcParams.items():
            if name.startswith("keymap.") and key in bound:
                bound.remove(key)
