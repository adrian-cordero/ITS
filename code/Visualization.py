import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import fiona

# --------------------------------------------------
# LOAD KML MAP
# --------------------------------------------------

kml_file = "C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Map Data/2023-03-22_1477_TEMPUS_Rheinstrasse_ODR.kml"
fiona.drvsupport.supported_drivers['KML'] = 'rw'

gdf = gpd.read_file(kml_file, driver="KML")

# --------------------------------------------------
# LOAD TRAJECTORIES
# --------------------------------------------------

csv_file = r"C:/Users/daans/Documents/KUL_2026_2027/Intelligent Transport Systems/Project/GitHub ITS/TUMDOT - MUC - Download/Trajectory Data/tumdot_muc_part_1.csv"

df = pd.read_csv(csv_file)

# --------------------------------------------------
# PLOT MAP
# --------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 12))

gdf.plot(
    ax=ax,
    color="lightgrey",
    edgecolor="black"
)

# --------------------------------------------------
# PLOT TRAJECTORIES
# --------------------------------------------------

for track_id, track in df.groupby("track_id"):

    track = track.sort_values("timestamp")

    ax.plot(
        track["translation_x"],
        track["translation_y"],
        linewidth=1,
        alpha=0.7
    )

# --------------------------------------------------
# FORMATTING
# --------------------------------------------------

ax.set_title("Map + Vehicle Trajectories")
ax.set_aspect("equal")

plt.show()
