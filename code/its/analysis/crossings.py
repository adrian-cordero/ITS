"""
Detect when tracks cross a line, and build discharge events from a
stop line / exit line pair.

Tracks are DataFrames sorted by timestamp with columns timestamp, x, y
(see its.trajectories.tracks). Lines are shapely geometries in PLOT_CRS.
"""

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, MultiPoint


def crossed_line(prev_xy, curr_xy, line) -> bool:
    """Does the step from prev_xy to curr_xy cross `line`?"""
    return LineString([prev_xy, curr_xy]).intersects(line)


def track_segments(track: pd.DataFrame) -> np.ndarray:
    """Array of LineStrings, one per step between consecutive points."""
    xy = track[["x", "y"]].to_numpy()
    if len(xy) < 2:
        return np.empty(0, dtype=object)
    return shapely.linestrings(np.stack([xy[:-1], xy[1:]], axis=1))


def crossing_times(track: pd.DataFrame, line) -> np.ndarray:
    """Timestamps at which the track crosses `line` (time of the point just after)."""
    segments = track_segments(track)
    if not len(segments):
        return np.empty(0)
    hits = shapely.intersects(segments, line)
    return track["timestamp"].to_numpy()[1:][hits]


def detect_events(tracks: dict, stop_exit_pairs: dict) -> pd.DataFrame:
    """
    One event per (pair, track) where the track crosses the stop line and
    later the exit line.

    tracks           {track_id: track DataFrame}
    stop_exit_pairs  {pair_name: {"stop_line": geom, "exit_line": geom}}

    Returns columns: event_id, pair_name, anchor_id, start_time, end_time
    (start = first stop-line crossing, end = first exit-line crossing after it).
    """
    rows = []
    for pair_name, pair in stop_exit_pairs.items():
        for track_id, track in tracks.items():
            stops = crossing_times(track, pair["stop_line"])
            if not len(stops):
                continue
            t_stop = stops[0]

            exits = crossing_times(track, pair["exit_line"])
            exits = exits[exits > t_stop]
            if not len(exits):
                continue

            rows.append({
                "pair_name": pair_name,
                "anchor_id": track_id,
                "start_time": t_stop,
                "end_time": exits[0],
            })

    events = pd.DataFrame(rows, columns=["pair_name", "anchor_id", "start_time", "end_time"])
    events.insert(0, "event_id", range(len(events)))
    return events


def convex_hull_from_points(points):
    """Convex hull polygon of the points, or None if they don't span an area."""
    if len(points) < 3:
        return None
    hull = MultiPoint(points).convex_hull
    return hull if hull.geom_type == "Polygon" else None


def event_time_series(event, bikes: pd.DataFrame, timestamps, zone=None) -> pd.DataFrame:
    """
    Per timestamp during the event: how many cyclists there are and the
    area of their convex hull.

    event       a row of detect_events (needs start_time, end_time)
    bikes       cyclist rows (columns timestamp, x, y)
    timestamps  all timestamps to report, including ones without cyclists
    zone        optional polygon: only count cyclists inside it. Without
                it every cyclist in the scene is counted.

    Returns columns: timestamp, count, area, polygon. `area` is in
    Web Mercator units, about 2.2x true m² here (see queues.jam_density).
    """
    t0, t1 = event["start_time"], event["end_time"]
    window = bikes[(bikes["timestamp"] >= t0) & (bikes["timestamp"] <= t1)]

    if zone is not None:
        window = window[shapely.contains_xy(zone, window["x"], window["y"])]

    by_time = {t: grp[["x", "y"]].to_numpy() for t, grp in window.groupby("timestamp")}

    rows = []
    for t in timestamps:
        if not (t0 <= t <= t1):
            continue
        points = by_time.get(t, np.empty((0, 2)))
        hull = convex_hull_from_points(points)
        rows.append({
            "timestamp": t,
            "count": len(points),
            "area": hull.area if hull is not None else 0.0,
            "polygon": hull,
        })

    return pd.DataFrame(rows, columns=["timestamp", "count", "area", "polygon"])


def polygons_by_timestamp(series_by_event: dict) -> dict:
    """{timestamp: [hull polygons]} across events, for drawing during playback."""
    lookup = {}
    for series in series_by_event.values():
        for t, poly in zip(series["timestamp"], series["polygon"]):
            if poly is not None:
                lookup.setdefault(t, []).append(poly)
    return lookup
