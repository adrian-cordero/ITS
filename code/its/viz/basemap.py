"""Draw the map underneath the trajectories."""

import geopandas as gpd
from matplotlib.patches import Patch
from shapely.geometry import box

from its.config import PLOT_CRS
from its.viz.styles import (
    BASEMAP_STYLES,
    DEFAULT_PROJECT_LAYER_STYLE,
    PROJECT_LAYER_STYLES,
    PROJECT_LAYER_ZORDER,
)


def set_extent(ax, df, padding=50):
    """Zoom to the trajectories in `df` (columns x, y) plus `padding` metres.

    Call this before drawing map layers so they don't change the zoom.
    """
    ax.set_xlim(df["x"].min() - padding, df["x"].max() + padding)
    ax.set_ylim(df["y"].min() - padding, df["y"].max() + padding)
    ax.set_aspect("equal")


def set_extent_to_areas(ax, geoms, margin_m=10.0, crs=PLOT_CRS):
    """Zoom to the box around `geoms` (a GeoSeries in a metric CRS) plus
    `margin_m` true metres on every side, centred on that box.

    The margin is added before converting to `crs`, since a unit of
    Web Mercator is not a metre. Call before drawing map layers.
    """
    x0, y0, x1, y1 = geoms.total_bounds
    frame = box(x0 - margin_m, y0 - margin_m, x1 + margin_m, y1 + margin_m)
    px0, py0, px1, py1 = gpd.GeoSeries([frame], crs=geoms.crs).to_crs(crs).total_bounds
    ax.set_xlim(px0, px1)
    ax.set_ylim(py0, py1)
    ax.set_aspect("equal")


def draw_basemap(ax, layers, styles=BASEMAP_STYLES):
    """Draw the layers from its.maps.load_basemap that have a style."""
    for name, style in styles.items():
        gdf = layers.get(name)
        if gdf is not None and not gdf.empty:
            gdf.plot(ax=ax, **style)


def draw_project_layers(ax, layers, styles=PROJECT_LAYER_STYLES,
                        default=DEFAULT_PROJECT_LAYER_STYLE):
    """Draw project layers; returns legend handles for the ones drawn."""
    handles = []
    for name, gdf in layers.items():
        if gdf.empty:
            continue
        style = styles.get(name, default)
        gdf.plot(ax=ax, zorder=PROJECT_LAYER_ZORDER, **style)
        handles.append(Patch(label=name.replace("_", " "), **style))
    return handles


def add_satellite(ax):
    """Esri satellite imagery behind everything (needs internet + contextily)."""
    import contextily as ctx

    ctx.add_basemap(ax, crs=f"EPSG:{PLOT_CRS}", source=ctx.providers.Esri.WorldImagery)
