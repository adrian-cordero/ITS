"""
Project-wide settings: paths, coordinate systems, road-user categories
and which map layers exist.

By default all data is read from the repository's data/ folder. To read
from a folder on your own disk instead (e.g. the maps you edit in
QGIS), copy local_settings.example.py to local_settings.py (git-ignored)
and set the paths there, or set the matching environment variable:

    MAPS_DIR     / ITS_MAPS_DIR      folder with the .gpkg / .osm map files
    PARQUET_DIR  / ITS_PARQUET_DIR   folder with tumdot_muc_part_*.parquet
    BASEMAP      / ITS_BASEMAP       base-map file (e.g. osm_converted.kml)

Environment variables win over local_settings.py. Windows paths
(C:\\...) also work when running under WSL.
"""

import os
from pathlib import Path

# --------------------------------------------------
# PATHS
# --------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

try:
    from its import local_settings as _local
except ImportError:
    _local = None


def _as_local_path(value) -> Path:
    """Path(value), turning C:\\... into /mnt/c/... when running under WSL."""
    s = str(value)
    if os.name != "nt" and len(s) > 2 and s[1] == ":" and s[2] in "\\/":
        s = f"/mnt/{s[0].lower()}/{s[3:]}".replace("\\", "/")
    return Path(s)


def _setting(name, default) -> Path:
    value = os.environ.get(f"ITS_{name}") or getattr(_local, name, None) or default
    return _as_local_path(value)


DATA_DIR = _setting("DATA_DIR", REPO_ROOT / "data")
PARQUET_DIR = _setting("PARQUET_DIR", DATA_DIR / "parquet")
MAPS_DIR = _setting("MAPS_DIR", DATA_DIR / "maps")
RESULTS_DIR = REPO_ROOT / "results"
OCCUPANCY_RESULTS_DIR = RESULTS_DIR / "occupancy"         # detect_occupancy.py
QUEUE_EVENTS_RESULTS_DIR = RESULTS_DIR / "queue_events"   # detect_queue_events.py

N_PARTS = 22   # tumdot_muc_part_1 ... tumdot_muc_part_22

# All parts' bicycles in one file, sorted by time, with a `part` column
# (built by code/scripts/build_combined.py). load_part() reads cyclists
# from here when it exists; everything else still comes from the parts.
BICYCLE_FILE = PARQUET_DIR / "tumdot_muc_bicycles.parquet"

# Columns kept in BICYCLE_FILE. Add one here and rerun build_combined.py
# when the analysis needs it (e.g. dimension_x, acceleration_x).
BICYCLE_COLUMNS = ("timestamp", "category", "track_id",
                   "translation_x", "translation_y", "velocity_x", "velocity_y")

# --------------------------------------------------
# COORDINATES
# --------------------------------------------------

# Trajectories are stored as local offsets in UTM zone 32N.
TRAJECTORY_CRS = 32632
UTM_OFFSET_X = 692009.0
UTM_OFFSET_Y = 5338095.0

# Everything is drawn in Web Mercator. Its "metres" are ~1.5x too long
# here, so widths, distances and areas are computed in METRIC_CRS (UTM).
PLOT_CRS = 3857
METRIC_CRS = TRAJECTORY_CRS

# --------------------------------------------------
# ROAD-USER CATEGORIES
# --------------------------------------------------

CAR, PEDESTRIAN, BICYCLE, TRAILER, MOTORCYCLE, TRUCK, BUS, SCOOTER, STREETCAR = range(1, 10)

CATEGORY_NAMES = {
    CAR: "Car",
    PEDESTRIAN: "Pedestrian",
    BICYCLE: "Bicycle",
    TRAILER: "Trailer",
    MOTORCYCLE: "Motorcycle",
    TRUCK: "Truck",
    BUS: "Bus",
    SCOOTER: "Scooter",
    STREETCAR: "Streetcar",
}

# --------------------------------------------------
# BASE MAP
# --------------------------------------------------

BASEMAP_FILE = _setting("BASEMAP", MAPS_DIR / "Rheinstrasse_osm.osm")

# Layers read from the base-map file ("points" is never drawn).
BASEMAP_LAYERS = ("lines", "multilinestrings", "multipolygons", "other_relations")

# Only these `type`s are kept from other_relations; the rest (destination
# signs, turn restrictions, ...) showed up as pink dots.
BASEMAP_RELATION_TYPES = ("street",)

# --------------------------------------------------
# PROJECT LAYERS (drawn in QGIS, see data/maps/zone_delimitations.qgz)
# --------------------------------------------------

# name -> where to find the layer
#   file        file name inside MAPS_DIR
#   layer       layer name inside that file
#   assume_crs  (optional) the CRS the coordinates are really in, when
#               the file's own CRS label is wrong
#   where       (optional) pandas query string to keep only some rows
#   tag         (optional) substring that must appear in `other_tags`
#               (OSM layers), e.g. '"bicycle"=>"designated"'
PROJECT_LAYERS = {
    "waiting_areas":  {"file": "new_waiting_areas.gpkg", "layer": "waiting_areas"},
    "merge_areas":    {"file": "merge_areas.gpkg", "layer": "merge_areas"},
    # system.gpkg is labelled EPSG:3857 but its coordinates are lon/lat
    "system":         {"file": "system.gpkg", "layer": "system", "assume_crs": 4326},
    "system_objects": {"file": "system_streets.gpkg", "layer": "system_objects"},
    "cycleways":      {"file": "Rheinstrasse_osm.osm", "layer": "lines",
                       "where": "highway == 'cycleway'"},
}

# Layers drawn when a script is not told otherwise.
DEFAULT_PROJECT_LAYERS = ("waiting_areas",)

# --------------------------------------------------
# CROSSING AREAS (see its/crossings.py and code/scripts/define_crossings.py)
# --------------------------------------------------

# Layer whose polygons get a start and end edge.
CROSSING_LAYER = "waiting_areas"

# W: length of the start edge, the end edge and every line in between,
# in metres. Change it and run `define_crossings.py --rebuild`; no re-picking.
CROSSING_WIDTH = 8.0

# N: number of lines drawn between the start and end edge (default for
# animate.py --lines). They split the length L into N + 1 equal parts.
CROSSING_LINES = 4

# animate.py frames the map on the waiting areas used by a crossing (and
# the crossing bands), plus this many metres on every side. --margin
# changes it, --full shows all trajectories instead.
ANIMATE_MARGIN = 10.0

# Picked edges, stored in MAPS_DIR next to the layers.
EDGE_PICKS_FILE = "edge_picks.csv"

# The crossings built from the picks (define_crossings.py), in MAPS_DIR: a
# GeoPackage with layers CROSSING_AREAS_LAYER (the bands) and
# CROSSING_EDGES_LAYER (their start and end lines).
CROSSING_AREAS_FILE = "crossing_areas.gpkg"
CROSSING_AREAS_LAYER = "crossing_areas"
CROSSING_EDGES_LAYER = "crossing_edges"

# --------------------------------------------------
# EVENT DETECTION (see code/scripts/plot_occupancy.py, detect_queue_events.py)
# --------------------------------------------------
# Command-line options of the scripts override these for one run.

# Waiting areas ticked when the occupancy plot opens.
DEFAULT_OCCUPANCY_AREAS = (4, 5, 6, 7)

# Event types detect_queue_events.py detects: "start" (a start line crossed
# forward), "stop" (a cyclist stopping in the start waiting area) and/or
# "discharge" (a stopped queue released over the crossing's lines; needs
# start and stop, which are then detected too).
SNAPSHOT_EVENT_TYPES = ("start", "stop", "discharge")

# A cyclist has stopped when its speed stays below STOP_SPEED (m/s) for at
# least STOP_DURATION (s). With EVERY_STOP = False only its first stop per
# waiting area is an event.
STOP_SPEED = 0.5
STOP_DURATION = 0.5
EVERY_STOP = False

# "Near": not inside the waiting area, but within this many metres of its edge.
NEAR_DISTANCE = 5.0

# Discharge: a start event is matched to its reference stop, the latest stop
# event of the same crossing at or before it and at most DISCHARGE_MAX_LAG s
# earlier. The queue is the cyclists inside the area with speed below
# STOP_SPEED in that stop's snapshot. One discharge per reference stop.
DISCHARGE_MAX_LAG = 120.0

# view_discharges.py only shows discharges with at least this many cyclists
# in the queue (n_queue); 1 shows them all. --min-bikes and the viewer's
# "min bikes" box change it; the CSVs always keep every discharge.
DISCHARGE_MIN_BIKES = 1

# Metres around the waiting area shown on the intersection view of the photos.
SNAPSHOT_CONTEXT = 40.0
