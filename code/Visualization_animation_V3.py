import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import fiona
import numpy as np
import mplcursors

from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from matplotlib.lines import Line2D
from pyproj import Transformer

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

CRS = 3857
file_number = 3

# --------------------------------------------------
# LOAD MAP
# --------------------------------------------------

kml_file = (
    r"C:/Users/daans/Documents/KUL_2026_2027/"
    r"Intelligent Transport Systems/Project/GitHub ITS/"
    r"TUMDOT - MUC - Download/Map Data/osm_converted.kml"
)

fiona.drvsupport.supported_drivers["KML"] = "rw"

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

parquet_file = (
    r"C:/Users/daans/Documents/KUL_2026_2027/"
    r"Intelligent Transport Systems/Project/GitHub ITS/"
    r"TUMDOT - MUC - Download/Trajectory Data/Parquet/"
    + f"tumdot_muc_part_{file_number}.parquet"
)

df = pd.read_parquet(parquet_file)

# --------------------------------------------------
# CATEGORY INFO
# --------------------------------------------------

category_colors = {
    1: "#1f77b4",
    2: "#ff7f0e",
    3: "#d62728",
    4: "#2ca02c",
    5: "#9467bd",
    6: "#8c564b",
    7: "#e377c2",
    8: "#7f7f7f",
    9: "#bcbd22",
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
    9: "Streetcar",
}

# --------------------------------------------------
# COORDINATE TRANSFORM ONLY ONCE
# --------------------------------------------------

e0 = 692009.0
n0 = 5338095.0

transformer = Transformer.from_crs(
    "EPSG:32632",
    "EPSG:3857",
    always_xy=True
)

all_easting = e0 + df["translation_x"].values
all_northing = n0 + df["translation_y"].values

x3857, y3857 = transformer.transform(
    all_easting,
    all_northing
)

df["x_3857"] = x3857
df["y_3857"] = y3857

# --------------------------------------------------
# PRECOMPUTE COLORS ONLY ONCE
# --------------------------------------------------

df["color"] = (
    df["category"]
    .map(category_colors)
    .fillna("black")
)

# --------------------------------------------------
# SORT DATA
# --------------------------------------------------

df = df.sort_values("timestamp")

timestamps = df["timestamp"].unique()

# --------------------------------------------------
# PRECOMPUTE FRAME DATA (BIG SPEEDUP)
# --------------------------------------------------

frames = []

for timestamp, group in df.groupby("timestamp", sort=True):

    frames.append(
        {
            "timestamp": timestamp,
            "offsets": group[
                ["x_3857", "y_3857"]
            ].to_numpy(),

            "colors": group["color"].to_numpy(),

            "categories": group[
                "category"
            ].to_numpy(),

            "ids": group[
                "track_id"
            ].to_numpy(),
        }
    )

print(f"Frames precomputed: {len(frames)}")

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
        [0],
        [0],
        marker="o",
        color="w",
        label=category_names[cat],
        markerfacecolor=color,
        markersize=8,
    )
    for cat, color in category_colors.items()
]

ax.legend(
    handles=legend_elements,
    title="Categories",
    loc="upper right",
)

# --------------------------------------------------
# MAP EXTENTS
# --------------------------------------------------

padding = 50

xmin = df["x_3857"].min() - padding
xmax = df["x_3857"].max() + padding

ymin = df["y_3857"].min() - padding
ymax = df["y_3857"].max() + padding

ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)

# --------------------------------------------------
# DRAW MAP
# --------------------------------------------------

layers = {}

for name in (
    "points",
    "lines",
    "multilinestrings",
    "multipolygons",
    "other_relations",
):
    layers[name] = gpd.read_file(
        kml_file,
        driver="KML",
        layer=name,
    ).to_crs(epsg=CRS)

layers["multipolygons"].plot(
    ax=ax,
    color="grey",
    edgecolor="white",
    linewidth=0.8,
    zorder=3,
)

layers["lines"].plot(
    ax=ax,
    color="#ADD8E6",
    linewidth=0.6,
    zorder=2,
)

layers["multilinestrings"].plot(
    ax=ax,
    color="#00008B",
    edgecolor="white",
    linewidth=0.8,
    zorder=3,
)

layers["other_relations"].plot(
    ax=ax,
    color="#DAB1DA",
    edgecolor="white",
    linewidth=0.8,
    zorder=3,
)

# --------------------------------------------------
# SCATTER
# --------------------------------------------------

scatter = ax.scatter(
    [],
    [],
    s=20,
    animated=False,
    zorder=10,
)

# Faster title than set_title()

title_text = ax.text(
    0.02,
    0.98,
    "",
    transform=ax.transAxes,
    va="top",
    fontsize=11,
    bbox=dict(
        facecolor="white",
        alpha=0.7,
        edgecolor="none",
    ),
)

ax.set_aspect("equal")

# --------------------------------------------------
# HOVER
# --------------------------------------------------

current_categories = np.array([])
current_ids = np.array([])

cursor = mplcursors.cursor(
    scatter,
    hover=True
)

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
        alpha=0.9,
    )

# --------------------------------------------------
# SLIDER
# --------------------------------------------------

slider_ax = plt.axes(
    [0.15, 0.08, 0.6, 0.03]
)

time_slider = Slider(
    slider_ax,
    "Time",
    0,
    len(frames) - 1,
    valinit=0,
    valstep=1,
)

# --------------------------------------------------
# BUTTON
# --------------------------------------------------

button_ax = plt.axes(
    [0.8, 0.06, 0.1, 0.05]
)

play_button = Button(
    button_ax,
    "Play",
)

playing = False
current_frame = 0

# --------------------------------------------------
# DRAW FRAME
# --------------------------------------------------

def draw_frame(frame_idx):

    global current_categories
    global current_ids

    frame = frames[frame_idx]

    current_categories = frame["categories"]
    current_ids = frame["ids"]

    scatter.set_offsets(
        frame["offsets"]
    )

    scatter.set_facecolors(
        frame["colors"]
    )

    title_text.set_text(
        f"Time = {frame['timestamp']:.2f}"
    )

    return scatter, title_text

# --------------------------------------------------
# ANIMATION
# --------------------------------------------------

def animate(_):

    global current_frame

    if not playing:
        return

    current_frame += 1

    if current_frame >= len(frames):
        current_frame = 0

    draw_frame(current_frame)

    time_slider.eventson = False
    time_slider.set_val(current_frame)
    time_slider.eventson = True

def slider_changed(val):

    global current_frame

    current_frame = int(val)

    draw_frame(current_frame)

# --------------------------------------------------
# SLIDER CALLBACK
# --------------------------------------------------

def slider_changed(val):

    draw_frame(int(val))

    fig.canvas.draw_idle()

time_slider.on_changed(
    slider_changed
)

# --------------------------------------------------
# PLAY / PAUSE
# --------------------------------------------------

def play_pause(event):

    global playing

    playing = not playing

    if playing:
        play_button.label.set_text(
            "Pause"
        )
    else:
        play_button.label.set_text(
            "Play"
        )

play_button.on_clicked(
    play_pause
)

# --------------------------------------------------
# START
# --------------------------------------------------

draw_frame(0)

ani = FuncAnimation(
    fig,
    animate,
    interval=50,
    blit=False,
    cache_frame_data=False,
)

plt.show()