"""Colours, line styles and drawing order shared by all plots."""

from its.config import (
    BICYCLE, BUS, CAR, MOTORCYCLE, PEDESTRIAN, SCOOTER, STREETCAR, TRAILER, TRUCK,
)

# --------------------------------------------------
# ROAD USERS
# --------------------------------------------------

CATEGORY_COLORS = {
    CAR: "#1f77b4",
    PEDESTRIAN: "#ff7f0e",
    BICYCLE: "#d62728",
    TRAILER: "#2ca02c",
    MOTORCYCLE: "#9467bd",
    TRUCK: "#8c564b",
    BUS: "#e377c2",
    SCOOTER: "#7f7f7f",
    STREETCAR: "#bcbd22",
}
DEFAULT_CATEGORY_COLOR = "black"

# --------------------------------------------------
# DRAWING ORDER (higher is on top)
# --------------------------------------------------

PROJECT_LAYER_ZORDER = 4    # above the base map (2-3)
ROAD_USER_ZORDER = 10
OVERLAY_TEXT_ZORDER = 11

# --------------------------------------------------
# BASE MAP (keys are layers from its.maps.load_basemap)
# --------------------------------------------------

BASEMAP_STYLES = {
    "multipolygons":    dict(color="grey", edgecolor="white", linewidth=0.8, zorder=3),
    "lines":            dict(color="#ADD8E6", linewidth=0.6, zorder=2),
    "multilinestrings": dict(color="#00008B", edgecolor="white", linewidth=0.8, zorder=3),
    "other_relations":  dict(color="#DAB1DA", edgecolor="white", linewidth=0.8, zorder=3),
}

# --------------------------------------------------
# PROJECT LAYERS (keys are config.PROJECT_LAYERS names)
# --------------------------------------------------

PROJECT_LAYER_STYLES = {
    "waiting_areas": dict(facecolor="orange", edgecolor="darkorange",
                          alpha=0.35, linewidth=1.5),
    "merge_areas":   dict(facecolor="none", edgecolor="red",
                          linestyle="--", linewidth=1.5),
    "system":        dict(facecolor="none", edgecolor="black",
                          linestyle=":", linewidth=1.0),
    "cycleways":     dict(facecolor="none", edgecolor="#d62728", linewidth=1.2),
}
DEFAULT_PROJECT_LAYER_STYLE = dict(facecolor="none", edgecolor="black", linewidth=1.0)

# --------------------------------------------------
# CROSSING LINES (keys are the `role` from its.crossings.load_crossing_lines)
# --------------------------------------------------

CROSSING_LINE_STYLES = {
    "start": dict(color="#2ca02c", linewidth=2.5, label="start edge"),
    "end":   dict(color="#9400d3", linewidth=2.5, label="end edge"),
    "line":  dict(color="black", linewidth=0.8, label="crossing lines"),
}
CROSSING_LINE_ZORDER = 5    # above the project layers, below road users
