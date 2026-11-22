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

N_PARTS = 22   # tumdot_muc_part_1 ... tumdot_muc_part_22

# --------------------------------------------------
# COORDINATES
# --------------------------------------------------

# Trajectories are stored as local offsets in UTM zone 32N.
TRAJECTORY_CRS = 32632
UTM_OFFSET_X = 692009.0
UTM_OFFSET_Y = 5338095.0

# Everything is drawn and analysed in Web Mercator (metres).
PLOT_CRS = 3857

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
    "waiting_areas":  {"file": "waiting_areas.gpkg", "layer": "waiting_areas"},
    "merge_areas":    {"file": "merge_areas.gpkg", "layer": "merge_areas"},
    # system.gpkg is labelled EPSG:3857 but its coordinates are lon/lat
    "system":         {"file": "system.gpkg", "layer": "system", "assume_crs": 4326},
    "system_objects": {"file": "system_streets.gpkg", "layer": "system_objects"},
    "cycleways":      {"file": "Rheinstrasse_osm.osm", "layer": "lines",
                       "where": "highway == 'cycleway'"},
}

# Layers drawn when a script is not told otherwise.
DEFAULT_PROJECT_LAYERS = ("waiting_areas", "merge_areas")

# --------------------------------------------------
# QUEUE ANALYSIS
# --------------------------------------------------

# Stop line / exit line per approach, as shapely geometries in PLOT_CRS:
#   from shapely.geometry import LineString
#   STOP_EXIT_PAIRS = {
#       "rheinstr_east": {
#           "stop_line": LineString([(x1, y1), (x2, y2)]),
#           "exit_line": LineString([(x3, y3), (x4, y4)]),
#       },
#   }
STOP_EXIT_PAIRS = {}
