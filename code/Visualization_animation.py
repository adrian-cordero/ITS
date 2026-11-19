import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import fiona
import numpy as np
import mplcursors
from fontTools.ttx import process
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from matplotlib.lines import Line2D
from pyproj import Transformer

# --------------------------------------------------
# LOAD KML MAP
# --------------------------------------------------

kml_file = "C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Map Data/2023-03-22_1477_TEMPUS_Rheinstrasse_ODR.kml"

fiona.drvsupport.supported_drivers['KML'] = 'rw'

gdf = gpd.read_file(kml_file, driver="KML")
# ------------------------------------
# Load trajectory data
# ------------------------------------
file_number = 3
parquet_file = r"C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Trajectory Data/Parquet/tumdot_muc_part_"+str(file_number)+".parquet"

df = pd.read_parquet(parquet_file)

df = df.sort_values("timestamp")

timestamps = sorted(df["timestamp"].unique())

# ------------------------------------
# Figure
# ------------------------------------
category_colors = {
    1: "#1f77b4",  # blue - car
    2: "#ff7f0e",  # orange - pedestrian
    3: "#d62728",  # red - bicycle
    4: "#2ca02c",  # green - trailer
    5: "#9467bd",  # purple - motorcycle
    6: "#8c564b",  # brown - truck
    7: "#e377c2",  # pink - bus
    8: "#7f7f7f",  # gray - scooter
    9: "#bcbd22",  # olive - streetcar
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

fig, ax = plt.subplots(figsize=(12, 12))

plt.subplots_adjust(bottom=0.2)

legend_elements = [
    Line2D(
        [0], [0],
        marker='o',
        color='w',
        label=category_names[cat],
        markerfacecolor=color,
        markersize=8
    )
    for cat, color in category_colors.items()
]

ax.legend(
    handles=legend_elements,
    title="Categories",
    loc="upper right"
)


# Drawing KML map
gdf.plot(
    ax=ax,
    color="lightgrey",
    edgecolor="black"
)

scatter = ax.scatter([], [], s=10, c=[])
ax.set_aspect("equal")

cursor = mplcursors.cursor(scatter, hover=True)

@cursor.connect("add")
def on_add(sel):
    idx = sel.index

    if idx < len(current_categories):
        sel.annotation.set_text(
            f"ID: {current_ids[idx]}\n"
            f"Category: {current_categories[idx]}"
        )

    sel.annotation.get_bbox_patch().set(
        fc="white",
        alpha=0.9
    )

# ------------------------------------
# Slider
# ------------------------------------

slider_ax = plt.axes([0.15, 0.08, 0.6, 0.03])

time_slider = Slider(
    slider_ax,
    "Time",
    0,
    len(timestamps) - 1,
    valinit=0,
    valstep=1
)

# ------------------------------------
# Play button
# ------------------------------------

button_ax = plt.axes([0.8, 0.06, 0.1, 0.05])

play_button = Button(
    button_ax,
    "Play"
)

playing = False
current_frame = 0
current_categories = []

# ------------------------------------
# Update
# ------------------------------------

def draw_frame(frame_idx):

    global current_frame

    current_frame = frame_idx

    t = timestamps[frame_idx]

    current = df[df["timestamp"] == t]

    global current_categories
    current_categories = current["category"].tolist()
    global current_ids
    current_ids = current["track_id"].tolist()
    #print("Map CRS:", gdf.crs)
    #print("Map bounds:", gdf.total_bounds)

    #print("Trajectory X range:",
     #     df["translation_x"].min(),
      #    df["translation_x"].max())

    #print("Trajectory Y range:",
     #     df["translation_y"].min(),
      #    df["translation_y"].max())

    # reference point in UTM32N
    e0 = 692009.0
    n0 = 5338095.0

    data = current[["translation_x", "translation_y"]].values
    # convert offsets to absolute UTM coordinates
    easting = e0 + data[:,0]
    northing = n0 + data[:,1]

    # UTM32N -> WGS84
    transformer = Transformer.from_crs(
        "EPSG:32632",
        "EPSG:4326",
        always_xy=True
    )
    lon, lat = transformer.transform(easting, northing)
    #print("lon"+str(lon))
    #print("lat"+str(lat))
    offsets = np.column_stack((lon, lat))

    # Map category values to colours
    colors = current["category"].map(category_colors).fillna("black")

    scatter.set_offsets(offsets)
    scatter.set_color(colors)

    ax.set_title(f"Time = {t:.2f}")

    return scatter,


# ------------------------------------
# Animation callback
# ------------------------------------

def animate(_):

    global current_frame

    if not playing:
        return scatter,

    current_frame += 1

    if current_frame >= len(timestamps):
        current_frame = 0

    time_slider.set_val(current_frame)

    return draw_frame(current_frame)

# ------------------------------------
# Slider callback
# ------------------------------------

def slider_changed(val):

    draw_frame(int(val))

    fig.canvas.draw_idle()

time_slider.on_changed(slider_changed)

# ------------------------------------
# Play/Pause
# ------------------------------------

def play_pause(event):

    global playing

    playing = not playing

    if playing:
        play_button.label.set_text("Pause")
    else:
        play_button.label.set_text("Play")

play_button.on_clicked(play_pause)

# ------------------------------------
# Start animation
# ------------------------------------

ani = FuncAnimation(
    fig,
    animate,
    interval=50,
    blit=False
)

draw_frame(0)

plt.show()
