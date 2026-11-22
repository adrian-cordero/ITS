"""Draw the map underneath the trajectories."""

from matplotlib.patches import Patch

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
