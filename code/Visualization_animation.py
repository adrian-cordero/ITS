import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import fiona
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
# --------------------------------------------------
# LOAD KML MAP
# --------------------------------------------------

kml_file = "C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Map Data/2023-03-22_1477_TEMPUS_Rheinstrasse_ODR.kml"

fiona.drvsupport.supported_drivers['KML'] = 'rw'

gdf = gpd.read_file(kml_file, driver="KML")
# ------------------------------------
# Load trajectory data
# ------------------------------------
csv_file = r"C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Trajectory Data/tumdot_muc_part_1.csv"

df = pd.read_csv(csv_file)

df = df.sort_values("timestamp")

timestamps = sorted(df["timestamp"].unique())

# ------------------------------------
# Figure
# ------------------------------------
offsetX = 690000
offsetY = 5350000
offsetZ = 0


fig, ax = plt.subplots(figsize=(12, 12))

plt.subplots_adjust(bottom=0.2)

# Drawing KML map
gdf.plot(
    ax=ax,
    color="lightgrey",
    edgecolor="black"
)

scatter = ax.scatter([], [], s=10)

ax.set_aspect("equal")

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

# ------------------------------------
# Update
# ------------------------------------

def draw_frame(frame_idx):

    global current_frame

    current_frame = frame_idx

    t = timestamps[frame_idx]

    current = df[df["timestamp"] == t]

    print("Map CRS:", gdf.crs)
    print("Map bounds:", gdf.total_bounds)

    print("Trajectory X range:",
          df["translation_x"].min(),
          df["translation_x"].max())

    print("Trajectory Y range:",
          df["translation_y"].min(),
          df["translation_y"].max())
    scatter.set_offsets(
        current[
            ["translation_x", "translation_y"]
        ].values + [365 ,78]
    )
    print("hello"+str(current[["translation_x", "translation_y"]].values))

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
