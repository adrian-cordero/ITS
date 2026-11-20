"""
Load a selection of GIS layers from the project's `maps` folder.

Edit SELECTED_LAYERS to choose what gets imported. Every layer is
returned as a GeoDataFrame reprojected to TARGET_CRS, so it lines up with
the trajectories drawn by Visualization_animation_V3.py (EPSG:3857).

    from gis_import import load_layers
    layers = load_layers()
    layers["waiting_areas"].plot()
"""

import os
import warnings
from pathlib import Path

import fiona
import geopandas as gpd

# fiona can't read these formats unless they are enabled explicitly
fiona.drvsupport.supported_drivers["OSM"] = "r"
fiona.drvsupport.supported_drivers["KML"] = "rw"

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

MAPS_DIR = Path(
    r"C:\Users\adria\OneDrive\Documents\0. Masters\2. Semester III"
    r"\Intelligent Transport Systems\project\maps"
)

TARGET_CRS = 3857

# key -> where to find the layer.
#   file        file name inside MAPS_DIR
#   layer       layer name inside that file
#   assume_crs  (optional) the CRS the coordinates are really in, when
#               the file's own CRS label is wrong
#   where       (optional) pandas query string to keep only some rows
#   tag         (optional) substring that must appear in `other_tags`
#               (OSM layers), e.g. '"bicycle"=>"designated"'
#
# Comment a line out to skip that layer.
SELECTED_LAYERS = {
    "waiting_areas":  {"file": "waiting_areas.gpkg", "layer": "waiting_areas"},
    # system.gpkg is labelled EPSG:3857 but its coordinates are lon/lat
    #"system":         {"file": "system.gpkg", "layer": "system", "assume_crs": 4326},
    #"system_objects": {"file": "system_streets.gpkg", "layer": "system_objects"},
    "merge_areas":  {"file": "merge_areas.gpkg", "layer": "merge_areas"},   # currently empty
    # "osm_lines":    {"file": "Rheinstrasse_osm.osm", "layer": "lines"},
    # "cycleways":    {"file": "Rheinstrasse_osm.osm", "layer": "lines",
    #                  "where": "highway == 'cycleway'"},
}


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _resolve(path: Path) -> Path:
    """Use the /mnt/c/... form of a Windows path when running under WSL."""
    if path.exists() or os.name == "nt":
        return path
    s = str(path).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        return Path(f"/mnt/{s[0].lower()}{s[2:]}")
    return path


def list_available(maps_dir: Path = MAPS_DIR) -> dict:
    """Return {file name: [layer names]} for every GIS file in maps_dir."""
    maps_dir = _resolve(maps_dir)
    out = {}
    for f in sorted(maps_dir.iterdir()):
        if f.suffix.lower() in (".gpkg", ".osm", ".kml", ".shp", ".geojson"):
            out[f.name] = fiona.listlayers(f)
    return out


def load_layer(spec: dict, maps_dir: Path = MAPS_DIR,
               target_crs=TARGET_CRS) -> gpd.GeoDataFrame:
    """Load a single layer described by one SELECTED_LAYERS entry."""
    path = _resolve(maps_dir) / spec["file"]
    gdf = gpd.read_file(path, layer=spec["layer"])

    if "assume_crs" in spec:
        gdf = gdf.set_crs(spec["assume_crs"], allow_override=True)

    if "tag" in spec and "other_tags" in gdf:
        gdf = gdf[gdf["other_tags"].str.contains(spec["tag"], regex=False, na=False)]

    if "where" in spec:
        gdf = gdf.query(spec["where"])

    if target_crs is not None and gdf.crs is not None and len(gdf):
        gdf = gdf.to_crs(target_crs)

    return gdf.reset_index(drop=True)


def load_layers(selection: dict = None, maps_dir: Path = MAPS_DIR,
                target_crs=TARGET_CRS) -> dict:
    """Load every layer in `selection` (default: SELECTED_LAYERS)."""
    selection = SELECTED_LAYERS if selection is None else selection
    layers = {}
    for key, spec in selection.items():
        gdf = load_layer(spec, maps_dir, target_crs)
        if gdf.empty:
            warnings.warn(f"Layer '{key}' ({spec['file']}:{spec['layer']}) is empty")
        layers[key] = gdf
    return layers


# --------------------------------------------------
# QUICK CHECK
# --------------------------------------------------

if __name__ == "__main__":
    print("Available layers:")
    for f, names in list_available().items():
        print(f"  {f}: {names}")

    print("\nSelected layers:")
    for key, gdf in load_layers().items():
        print(f"  {key:15} {len(gdf):4} features  {sorted(gdf.geom_type.unique())}  "
              f"bounds={[round(b) for b in gdf.total_bounds] if len(gdf) else '-'}")
