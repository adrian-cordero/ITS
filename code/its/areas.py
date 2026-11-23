"""
Crossing areas: a band of constant width W from a start edge on one
polygon to an end edge on another polygon of the same layer, with N
lines drawn across it.

For each crossing (code/scripts/pick_edges.py does steps 1-3):
  1. you pick a start edge on polygon A and an end edge on polygon B
  2. crossing_edges(): both edges get length W, centred on their original
     midpoints, and the end edge is turned parallel to the start edge.
     make_crossing() is the four-sided band between them; every line
     across it has length W. L is the distance between the two edges.
     (If the midpoints are not straight across, the band leans: a
     parallelogram.)
  3. the bands are saved as layer crossing_areas of crossing_areas.gpkg,
     with an extra layer crossing_edges holding the start/end lines. The original polygons
     are not changed.
  4. crossing_lines() gives N lines between the edges, splitting L into
     N + 1 equal parts (no leftover). Each crossing can have its own N
     (`lines`) and its own W (`width`); crossings without them use the
     defaults.

Each crossing has its own `crossing_id`, so any number of crossings can
start or end at the same polygon. Polygons are identified by their row
number in the source layer; deleting or reordering features in QGIS
changes it, so re-pick after doing that. Picked edges
are stored by their midpoints, so moving vertices around doesn't break them.

All geometry here is in METRIC_CRS, so W and L are true metres.
"""

import warnings
from collections import namedtuple

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon

from its.config import (
    CROSSING_AREAS_FILE, CROSSING_AREAS_LAYER, CROSSING_EDGES_LAYER, EDGE_PICKS_FILE, MAPS_DIR,
    METRIC_CRS, PROJECT_LAYERS,
)

# --------------------------------------------------
# EDGES
# --------------------------------------------------


def polygon_edges(poly) -> list:
    """Edge k runs from vertex k to vertex k+1; each edge is a (2, 2) array."""
    c = np.asarray(poly.exterior.coords)[:-1, :2]
    return [np.array([c[k], c[(k + 1) % len(c)]]) for k in range(len(c))]


def _unit(v):
    return v / np.linalg.norm(v)


def edge_angle(e1, e2) -> float:
    """Angle between two edges' directions in degrees (0 = parallel, 90 = perpendicular)."""
    d1, d2 = e1[1] - e1[0], e2[1] - e2[0]
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    angle = np.degrees(np.arctan2(abs(cross), np.dot(d1, d2)))   # 0..180
    return float(min(angle, 180.0 - angle))


def nearest_edge(poly, xy) -> int:
    p = Point(xy)
    return int(np.argmin([LineString(e).distance(p) for e in polygon_edges(poly)]))


# --------------------------------------------------
# CONSTANT-WIDTH CROSSING
# --------------------------------------------------


def crossing_edges(start_poly, start: int, end_poly, end: int, width: float):
    """
    (start_line, end_line): edge `start` of start_poly and edge `end` of
    end_poly, both resized to length `width` around their midpoints and
    both in the start edge's direction.
    """
    if width <= 0:
        raise ValueError("width must be positive")

    s = polygon_edges(start_poly)[start]
    e = polygon_edges(end_poly)[end]
    half = _unit(s[1] - s[0]) * width / 2
    s_mid, e_mid = s.mean(axis=0), e.mean(axis=0)
    return (LineString([s_mid - half, s_mid + half]),
            LineString([e_mid - half, e_mid + half]))


def band_between(start_line, end_line) -> Polygon:
    """The four-sided band between two parallel lines of equal length."""
    (s0, s1), (e0, e1) = start_line.coords, end_line.coords
    return Polygon([s0, s1, e1, e0])


def make_crossing(start_poly, start, end_poly, end, width) -> Polygon:
    return band_between(*crossing_edges(start_poly, start, end_poly, end, width))


def crossing_length(start_line, end_line) -> float:
    """L: distance between the (parallel) start and end line."""
    s = np.asarray(start_line.coords)
    u = _unit(s[1] - s[0])
    normal = np.array([-u[1], u[0]])
    e_mid = np.asarray(end_line.coords).mean(axis=0)
    return float(abs(np.dot(e_mid - s[0], normal)))


def crossing_lines(start_line, end_line, n: int) -> list:
    """
    N lines between the start and end line, at fractions 1/(N+1) ...
    N/(N+1) of the way across. Each has the same length and direction
    as the start line.
    """
    s = np.asarray(start_line.coords)
    e = np.asarray(end_line.coords)
    return [LineString(s + (e - s) * i / (n + 1)) for i in range(1, n + 1)]


# --------------------------------------------------
# PICKS FILE  (edge midpoints in METRIC_CRS)
# --------------------------------------------------

# One crossing. `lines` is its own number of lines N and `width` its own
# width W in metres; None means "use the default".
Crossing = namedtuple("Crossing", "start_area start_edge end_area end_edge lines width",
                      defaults=(None, None))

# picks = {crossing_id: Crossing}


def effective_lines(crossing, default: int) -> int:
    """The crossing's own N, or `default` if it has none."""
    return default if crossing.lines is None else crossing.lines


def effective_width(crossing, default: float) -> float:
    """The crossing's own W, or `default` if it has none."""
    return default if crossing.width is None else crossing.width


def reversed_crossing(c: Crossing) -> Crossing:
    return Crossing(c.end_area, c.end_edge, c.start_area, c.start_edge, c.lines, c.width)

_PICK_COLUMNS = ["layer", "crossing_id", "start_area", "start_x", "start_y",
                 "end_area", "end_x", "end_y", "lines", "width"]


def load_picks(layer: str, source: gpd.GeoDataFrame, maps_dir=MAPS_DIR) -> dict:
    """{crossing_id: Crossing} for `layer`."""
    path = maps_dir / EDGE_PICKS_FILE
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    if "end_area" not in df.columns:
        warnings.warn(f"{path.name} is in an old format (end edge on the same polygon); "
                      "ignoring it. Pick again.")
        return {}
    if "crossing_id" not in df.columns:          # one-crossing-per-area format
        df = df.rename(columns={"area_id": "start_area"})
        df.insert(1, "crossing_id", range(len(df)))

    picks = {}
    for row in df[df["layer"] == layer].itertuples():
        if max(row.start_area, row.end_area) >= len(source):
            warnings.warn(f"Crossing #{row.crossing_id} ({row.start_area} -> {row.end_area}): "
                          "that polygon no longer exists")
            continue
        start_poly = source.geometry.iloc[row.start_area]
        end_poly = source.geometry.iloc[row.end_area]
        lines = getattr(row, "lines", None)
        width = getattr(row, "width", None)
        picks[int(row.crossing_id)] = Crossing(
            int(row.start_area), nearest_edge(start_poly, (row.start_x, row.start_y)),
            int(row.end_area), nearest_edge(end_poly, (row.end_x, row.end_y)),
            None if lines is None or pd.isna(lines) else int(lines),
            None if width is None or pd.isna(width) else float(width),
        )
    return picks


def save_picks(layer: str, source: gpd.GeoDataFrame, picks: dict, maps_dir=MAPS_DIR):
    path = maps_dir / EDGE_PICKS_FILE
    rows = []
    for cid, c in sorted(picks.items()):
        s = polygon_edges(source.geometry.iloc[c.start_area])[c.start_edge].mean(axis=0)
        e = polygon_edges(source.geometry.iloc[c.end_area])[c.end_edge].mean(axis=0)
        rows.append([layer, cid, c.start_area, s[0], s[1], c.end_area, e[0], e[1],
                     c.lines, c.width])
    new = pd.DataFrame(rows, columns=_PICK_COLUMNS)

    if path.exists():                 # keep other layers' picks
        old = pd.read_csv(path)
        if "crossing_id" in old.columns:
            others = old[old["layer"] != layer]
            parts = [df for df in (others, new) if not df.empty]
            new = pd.concat(parts, ignore_index=True) if parts else new
    new["lines"] = pd.to_numeric(new["lines"], errors="coerce").astype("Int64")  # 2, not 2.0
    new.to_csv(path, index=False)
    return path


def next_crossing_id(picks: dict) -> int:
    return max(picks, default=-1) + 1


# --------------------------------------------------
# LOAD / BUILD / SAVE LAYERS
# --------------------------------------------------


def load_source(layer: str, maps_dir=MAPS_DIR) -> gpd.GeoDataFrame:
    """The original layer in METRIC_CRS; its file CRS is kept in .attrs['file_crs']."""
    spec = PROJECT_LAYERS[layer]
    gdf = gpd.read_file(maps_dir / spec["file"], layer=spec["layer"])
    file_crs = gdf.crs
    gdf = gdf.to_crs(METRIC_CRS).reset_index(drop=True)
    gdf.attrs["file_crs"] = file_crs
    return gdf


def crossing_geometry(source, c: Crossing, default_width):
    """(band, start_line, end_line, angle_fixed) for one crossing; W is the
    crossing's own width, or `default_width` if it has none."""
    start_poly = source.geometry.iloc[c.start_area]
    end_poly = source.geometry.iloc[c.end_area]
    s_line, e_line = crossing_edges(start_poly, c.start_edge, end_poly, c.end_edge,
                                    effective_width(c, default_width))
    angle = edge_angle(polygon_edges(start_poly)[c.start_edge],
                       polygon_edges(end_poly)[c.end_edge])
    return band_between(s_line, e_line), s_line, e_line, angle


def build_crossings(source: gpd.GeoDataFrame, picks: dict, width: float):
    """(bands, edges) GeoDataFrames in METRIC_CRS, one band per crossing.
    `width` is the default W for crossings without their own."""
    bands, edges = [], []
    for cid, c in sorted(picks.items()):
        band, s_line, e_line, angle = crossing_geometry(source, c, width)
        bands.append({"crossing_id": cid, "start_area": c.start_area,
                      "start_edge": c.start_edge, "end_area": c.end_area,
                      "end_edge": c.end_edge, "width": effective_width(c, width),
                      "own_width": c.width is not None,
                      "length": round(crossing_length(s_line, e_line), 3),
                      "angle_fixed": round(angle, 2),
                      "lines": -1 if c.lines is None else c.lines,   # -1 = default
                      "geometry": band})
        edges.append({"crossing_id": cid, "role": "start", "geometry": s_line})
        edges.append({"crossing_id": cid, "role": "end", "geometry": e_line})

    columns = ["crossing_id", "start_area", "start_edge", "end_area", "end_edge", "width",
               "own_width", "length", "angle_fixed", "lines", "geometry"]
    bands = gpd.GeoDataFrame(bands, columns=columns, geometry="geometry", crs=source.crs)
    edges = gpd.GeoDataFrame(edges, columns=["crossing_id", "role", "geometry"],
                             geometry="geometry", crs=source.crs)
    return bands, edges


def crossing_areas_path(layer: str, maps_dir=MAPS_DIR):
    """CROSSING_AREAS_FILE: the crossings of `layer` (one layer at a time)."""
    return maps_dir / CROSSING_AREAS_FILE


def save_crossings(layer: str, bands, edges, crs, maps_dir=MAPS_DIR):
    """Write CROSSING_AREAS_FILE (replacing it) with both layers, in `crs`."""
    path = crossing_areas_path(layer, maps_dir)
    if path.exists():
        path.unlink()
    if bands.empty:
        return path
    bands.to_crs(crs).to_file(path, layer=CROSSING_AREAS_LAYER, driver="GPKG")
    edges.to_crs(crs).to_file(path, layer=CROSSING_EDGES_LAYER, driver="GPKG")
    return path


def load_crossing_lines(layer: str, n: int, maps_dir=MAPS_DIR) -> gpd.GeoDataFrame:
    """
    Start, end and N in-between lines for every crossing in
    CROSSING_AREAS_FILE, in METRIC_CRS. N is the crossing's own number
    of lines if it has one, otherwise `n`. Columns: crossing_id, role
    ("start", "line", "end"), index (0 = start ... N + 1 = end), geometry.
    """
    path = crossing_areas_path(layer, maps_dir)
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not found: run code/scripts/pick_edges.py first")

    edges = gpd.read_file(path, layer=CROSSING_EDGES_LAYER).to_crs(METRIC_CRS)
    key = "crossing_id" if "crossing_id" in edges.columns else "area_id"

    own_n = {}
    bands = gpd.read_file(path, layer=CROSSING_AREAS_LAYER)
    if "lines" in bands.columns and key in bands.columns:
        own_n = {k: int(v) for k, v in zip(bands[key], bands["lines"])
                 if pd.notna(v) and int(v) >= 0}

    rows = []
    for cid, grp in edges.groupby(key):
        lines = dict(zip(grp["role"], grp.geometry))
        n_here = own_n.get(cid, n)
        rows.append({"crossing_id": cid, "role": "start", "index": 0, "geometry": lines["start"]})
        for i, line in enumerate(crossing_lines(lines["start"], lines["end"], n_here), start=1):
            rows.append({"crossing_id": cid, "role": "line", "index": i, "geometry": line})
        rows.append({"crossing_id": cid, "role": "end", "index": n_here + 1,
                     "geometry": lines["end"]})

    return gpd.GeoDataFrame(rows, columns=["crossing_id", "role", "index", "geometry"],
                            geometry="geometry", crs=METRIC_CRS)
