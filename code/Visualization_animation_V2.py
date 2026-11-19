import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import fiona
import numpy as np
import mplcursors
import contextily as ctx
from fontTools.ufoLib.glifLib import layerInfoVersion3ValueData

from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from matplotlib.lines import Line2D
from pyproj import Transformer

#version without precalculating frames, working slider
# --------------------------------------------------
# LOAD KML MAP
# --------------------------------------------------

#kml_file = r"C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Map Data/2023-03-22_1477_TEMPUS_Rheinstrasse_ODR.kml" #reference lines map
kml_file = r"C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Map Data/osm_converted.kml"
fiona.drvsupport.supported_drivers['KML'] = 'rw'

CRS = 3857

# --------------------------------------------------
# LOAD PARQUET DATA
# --------------------------------------------------

file_number = 16
included_categories = [2, 3] #pedestrians and bicycles only

parquet_file = (
    r"C:/Users/daans/Documents/KUL_2026_2027/"
    r"Intelligent Transport Systems/Project/GitHub ITS/"
    r"ITS/Parquet/"
    + f"tumdot_muc_part_{file_number}.parquet"
)

df = pd.read_parquet(parquet_file)

df = df[df["category"].isin(included_categories)]

df = df.sort_values("timestamp")

timestamps = sorted(df["timestamp"].unique())

# --------------------------------------------------
# CATEGORY COLOURS
# --------------------------------------------------

category_colors = {
    1: "#1f77b4",  # car
    2: "#ff7f0e",  # pedestrian
    3: "#d62728",  # bicycle
    4: "#2ca02c",  # trailer
    5: "#9467bd",  # motorcycle
    6: "#8c564b",  # truck
    7: "#e377c2",  # bus
    8: "#7f7f7f",  # scooter
    9: "#bcbd22",  # streetcar
}

category_names = {
    1: "Car",
    2: "Pedestrian",
    3: "Bicycle",
    4: "Trailer",
    5: "Motorcycle",
    6: "Truck",
    7: "Bus",
    8: "Scooter",
    9: "Streetcar"
}

# --------------------------------------------------
# REFERENCE POINT
# --------------------------------------------------

e0 = 692009.0
n0 = 5338095.0

# --------------------------------------------------
# TRANSFORM ALL TRAJECTORIES ONCE
# --------------------------------------------------

transformer = Transformer.from_crs(
    "EPSG:32632",
    "EPSG:3857",
    always_xy=True
)

all_easting = e0 + df["translation_x"].values
all_northing = n0 + df["translation_y"].values

df["x_3857"], df["y_3857"] = transformer.transform(
    all_easting,
    all_northing
)
all_x = df["x_3857"]
all_y = df["y_3857"]

# --------------------------------------------------
# FIGURE
# --------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 12))

plt.subplots_adjust(bottom=0.2)

# --------------------------------------------------
# LEGEND
# --------------------------------------------------

legend_elements = [
    Line2D(
        [0], [0],
        marker='o',
        color='w',
        label=category_names[cat],
        markerfacecolor=category_colors[cat],
        markersize=8
    )
    for cat in included_categories
]

legend = ax.legend(
    handles=legend_elements,
    title="Categories",
    loc="upper right"
)

# --------------------------------------------------
# MAP EXTENT
# --------------------------------------------------

padding = 50

xmin = all_x.min() - padding
xmax = all_x.max() + padding

ymin = all_y.min() - padding
ymax = all_y.max() + padding

ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)

# --------------------------------------------------
# DRAW KML OVERLAY
# --------------------------------------------------

points, lines, multilinestrings, multipolygons, other_relations = (gpd.read_file(kml_file, driver="KML", layer = f"{name}") for name in ("points", "lines", "multilinestrings", "multipolygons", "other_relations"))
# Convert map to Web Mercator for satellite imagery
points = points.to_crs(epsg=CRS)
lines = lines.to_crs(epsg=CRS)
multilinestrings = multilinestrings.to_crs(epsg=CRS)
multipolygons = multipolygons.to_crs(epsg=CRS)
other_relations = other_relations.to_crs(epsg=CRS)

#points.plot(ax=ax, facecolor="none", edgecolor="yellow", linewidth=1)
multipolygons.plot(ax=ax, color="grey", markersize=45, edgecolor="white", linewidth=0.8, zorder=3)
lines.plot(ax=ax, color="#ADD8E6", linewidth=0.6, zorder=2)
multilinestrings.plot(ax=ax, color="#00008B", markersize=45, edgecolor="white", linewidth=0.8, zorder=3)
other_relations.plot(ax=ax, color="#DAB1DA", markersize=45, edgecolor="white", linewidth=0.8, zorder=3)

# --------------------------------------------------
# SATELLITE BACKGROUND
# --------------------------------------------------

#ctx.add_basemap(ax,source=ctx.providers.Esri.WorldImagery)

# --------------------------------------------------
# SCATTER
# --------------------------------------------------

scatter = ax.scatter(
    [],
    [],
    s=20,
    c=[],
    zorder=10
)

ax.set_aspect("equal")

# --------------------------------------------------
# HOVER
# --------------------------------------------------

current_categories = []
current_ids = []

cursor = mplcursors.cursor(scatter, hover=True)

@cursor.connect("add")
def on_add(sel):

    idx = sel.index

    if idx < len(current_categories):

        category = current_categories[idx]

        sel.annotation.set_text(
            f"ID: {current_ids[idx]}\n"
            f"Category: {category_names.get(category, category)}"
        )

    sel.annotation.get_bbox_patch().set(
        fc="white",
        alpha=0.9
    )

# --------------------------------------------------
# SLIDER
# --------------------------------------------------

slider_ax = plt.axes([0.15, 0.08, 0.6, 0.03])

time_slider = Slider(
    slider_ax,
    "Time",
    0,
    len(timestamps) - 1,
    valinit=0,
    valstep=1
)

# --------------------------------------------------
# BUTTON
# --------------------------------------------------

button_ax = plt.axes([0.8, 0.06, 0.1, 0.05])

play_button = Button(
    button_ax,
    "Play"
)

playing = False
current_frame = 0

# --------------------------------------------------
# UPDATE FRAME
# --------------------------------------------------

def draw_frame(frame_idx):

    global current_frame
    global current_categories
    global current_ids
    global counts

    current_frame = frame_idx

    t = timestamps[frame_idx]

    current = df[df["timestamp"] == t]
    counts = current["category"].value_counts()

    current_categories = current["category"].tolist()
    current_ids = current["track_id"].tolist()

    #data = current[
    #    ["translation_x", "translation_y"]
    #].values

    #easting = e0 + data[:, 0]
    #northing = n0 + data[:, 1]

    #x, y = transformer.transform(
    #    easting,
    #    northing
    #)
    x, y = current["x_3857"], current["y_3857"]
    offsets = np.column_stack((x, y))

    colors = (
        current["category"]
        .map(category_colors)
        .fillna("black")
    )

    ax.set_title(f"Time = {t:.2f}")

    legend_texts = legend.get_texts()
    for i, cat in enumerate(included_categories):
        legend_texts[i].set_text(
            f"{category_names[cat]} ({counts.get(cat, 0)})"
        )

    scatter.set_offsets(offsets)
    scatter.set_color(colors)

    return scatter,

# --------------------------------------------------
# ANIMATION
# --------------------------------------------------

def animate(_):

    global current_frame

    if not playing:
        return scatter,

    current_frame += 1

    if current_frame >= len(timestamps):
        current_frame = 0

    time_slider.set_val(current_frame)

    return draw_frame(current_frame)

# --------------------------------------------------
# SLIDER CALLBACK
# --------------------------------------------------

def slider_changed(val):

    draw_frame(int(val))

    fig.canvas.draw_idle()

time_slider.on_changed(slider_changed)

# --------------------------------------------------
# PLAY / PAUSE
# --------------------------------------------------

def play_pause(event):

    global playing

    playing = not playing

    if playing:
        play_button.label.set_text("Pause")
    else:
        play_button.label.set_text("Play")

play_button.on_clicked(play_pause)

# --------------------------------------------------
# START
# --------------------------------------------------

ani = FuncAnimation(
    fig,
    animate,
    interval=50,
    blit=False,
    cache_frame_data=False
)

draw_frame(0)

plt.show()