"""
Load the base map and the project layers (waiting areas etc.).

Every layer comes back as a GeoDataFrame in PLOT_CRS, so it lines up
with the trajectories from its.trajectories.

    from its.maps import load_basemap, load_project_layers
    basemap = load_basemap()
    layers = load_project_layers(["waiting_areas"])
"""

import warnings

import fiona
import geopandas as gpd

from its.config import (
    BASEMAP_FILE,
    BASEMAP_LAYERS,
    BASEMAP_RELATION_TYPES,
    DEFAULT_PROJECT_LAYERS,
    MAPS_DIR,
    PLOT_CRS,
    PROJECT_LAYERS,
)

# fiona can't read these formats unless they are enabled explicitly
fiona.drvsupport.supported_drivers["OSM"] = "r"
fiona.drvsupport.supported_drivers["KML"] = "rw"

_GIS_SUFFIXES = (".gpkg", ".osm", ".kml", ".shp", ".geojson")


def list_available(maps_dir=MAPS_DIR) -> dict:
    """{file name: [layer names]} for every GIS file in maps_dir."""
    return {
        f.name: fiona.listlayers(f)
        for f in sorted(maps_dir.iterdir())
        if f.suffix.lower() in _GIS_SUFFIXES
    }


def single_parts(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Turn one-part MultiPolygons (QGIS saves layers as MultiPolygon by
    default) into plain Polygons, so .exterior works. Rows and their order
    are kept; MultiPolygons with several parts are left as they are."""
    def one(g):
        if g is not None and g.geom_type == "MultiPolygon" and len(g.geoms) == 1:
            return g.geoms[0]
        return g
    gdf = gdf.copy()
    gdf[gdf.geometry.name] = gdf.geometry.apply(one)
    return gdf


def load_layer(spec: dict, maps_dir=MAPS_DIR, crs=PLOT_CRS) -> gpd.GeoDataFrame:
    """Load one layer described by a config.PROJECT_LAYERS entry."""
    gdf = single_parts(gpd.read_file(maps_dir / spec["file"], layer=spec["layer"]))

    if "assume_crs" in spec:
        gdf = gdf.set_crs(spec["assume_crs"], allow_override=True)

    if "tag" in spec and "other_tags" in gdf:
        gdf = gdf[gdf["other_tags"].str.contains(spec["tag"], regex=False, na=False)]

    if "where" in spec:
        gdf = gdf.query(spec["where"])

    if crs is not None and gdf.crs is not None and len(gdf):
        gdf = gdf.to_crs(crs)

    return gdf.reset_index(drop=True)


def load_project_layers(names=DEFAULT_PROJECT_LAYERS, maps_dir=MAPS_DIR,
                        crs=PLOT_CRS) -> dict:
    """{name: GeoDataFrame} for the given config.PROJECT_LAYERS names."""
    unknown = set(names) - set(PROJECT_LAYERS)
    if unknown:
        raise KeyError(f"Unknown layer(s) {sorted(unknown)}; "
                       f"available: {sorted(PROJECT_LAYERS)}")

    layers = {}
    for name in names:
        spec = PROJECT_LAYERS[name]
        if not (maps_dir / spec["file"]).exists():
            warnings.warn(f"Layer '{name}' skipped: {maps_dir / spec['file']} not found")
            continue
        gdf = load_layer(spec, maps_dir, crs)
        if gdf.empty:
            warnings.warn(f"Layer '{name}' ({spec['file']}:{spec['layer']}) is empty")
        layers[name] = gdf
    return layers


def load_basemap(path=BASEMAP_FILE, layers=BASEMAP_LAYERS,
                 relation_types=BASEMAP_RELATION_TYPES, crs=PLOT_CRS) -> dict:
    """
    {layer name: GeoDataFrame} from an OSM (or OSM-derived KML) file.

    other_relations is reduced to `relation_types`; pass None to keep all.
    """
    out = {}
    for name in layers:
        gdf = gpd.read_file(path, layer=name).to_crs(crs)
        if name == "other_relations" and relation_types is not None and "type" in gdf:
            gdf = gdf[gdf["type"].isin(relation_types)]
        out[name] = gdf
    return out
