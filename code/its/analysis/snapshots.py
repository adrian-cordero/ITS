"""
Snapshot events in a crossing's start waiting area.

Event types
    start     a cyclist crosses the crossing's start line forward
              (start -> end); each cyclist once per line. Snapshot: its
              last timestep before the line. (A "crossing" is only ever
              the area / band, never an event.)
    stop      a cyclist inside the start waiting area slows below
              `stop_speed` (m/s) and stays below it for at least
              `stop_duration` (s). Snapshot: the first timestep of the
              stop. Unless `every_stop`, only each cyclist's first stop
              per area. Defaults: STOP_SPEED, STOP_DURATION, EVERY_STOP
              in config.py. A stop is recorded once for every crossing
              that starts in the area, each with positions in that
              crossing's local frame.

At the snapshot time every cyclist is classed as
    inside    in the waiting area (stay rule of its.analysis.occupancy:
              inside from its first to its last timestep in the area)
    near      not inside, but within `near` metres of the area's edge
              (default NEAR_DISTANCE in config.py)
    (others are farther away and only appear on the intersection view)

Local frame of a crossing (its start waiting area seen from its start
line; crossings sharing a start area each have their own), in metres:
    y  "north": along the start line
    x  north rotated -90 degrees (clockwise): perpendicular to the start
       line, pointing from it back into the waiting area
    (0, 0) is the bottom-left corner of the smallest rectangle in these
    axes that contains the area, so the start line is on the left and x
    is roughly the distance behind the start line. Near cyclists can lie
    outside the rectangle (negative or beyond the area's size).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely

from its.analysis.crossings import first_forward_per_track, forward_normal, line_crossings
from its.analysis.occupancy import area_stays
from its.config import (
    EVERY_STOP, NEAR_DISTANCE, SNAPSHOT_EVENT_TYPES, STOP_DURATION, STOP_SPEED,
)

EVENT_COLUMNS = ["event_id", "type", "area", "crossing_id", "trigger_track", "event_time",
                 "snapshot_time", "n_inside", "n_near", "trigger_inside"]
POSITION_COLUMNS = ["event_id", "track_id", "status", "x", "y", "distance_to_area",
                    "utm_x", "utm_y", "speed", "is_trigger"]


# --------------------------------------------------
# LOCAL FRAME
# --------------------------------------------------


@dataclass
class LocalFrame:
    origin: np.ndarray      # UTM point that becomes (0, 0)
    x_axis: np.ndarray      # unit vector, from the start line into the area
    y_axis: np.ndarray      # unit vector ("north", along the start line)
    width: float            # extent of the area along x (m)
    depth: float            # extent of the area along y (m)

    def to_local(self, ux, uy):
        """UTM coordinates -> local (x, y) in metres."""
        d = np.column_stack([np.asarray(ux, float), np.asarray(uy, float)]) - self.origin
        return d @ self.x_axis, d @ self.y_axis

    def coords_local(self, geom):
        """A LineString's or Polygon exterior's points in local coordinates."""
        c = np.asarray(geom.exterior.coords if hasattr(geom, "exterior") else geom.coords)[:, :2]
        return self.to_local(c[:, 0], c[:, 1])


def local_frame(area, forward) -> LocalFrame:
    """
    Frame of `area` for a start line whose direction of travel is
    `forward`: x points against `forward` (from the start line into the
    area), y is x rotated +90 degrees, so x = y rotated -90 degrees.
    """
    f = np.asarray(forward, float) / np.linalg.norm(forward)
    x_axis = -f
    y_axis = np.array([-x_axis[1], x_axis[0]])            # x rotated +90 degrees
    c = np.asarray(area.exterior.coords)[:, :2]
    px, py = c @ x_axis, c @ y_axis
    origin = px.min() * x_axis + py.min() * y_axis        # back to UTM
    return LocalFrame(origin, x_axis, y_axis, float(px.max() - px.min()),
                      float(py.max() - py.min()))


# --------------------------------------------------
# DETECTORS  (each returns rows with type, area, crossing_id,
#             trigger_track, event_time, snapshot_time)
# --------------------------------------------------


def detect_start_events(d, crossing):
    north = forward_normal(crossing["start_line"], crossing["end_line"])
    triggers = first_forward_per_track(line_crossings(d, crossing["start_line"], north))
    rows = []
    for trig in triggers.itertuples():
        times = d.loc[d["track_id"] == trig.track_id, "timestamp"]
        before = times[times < trig.time]
        if before.empty:
            continue
        rows.append({"type": "start", "area": crossing["start_area"],
                     "crossing_id": crossing["crossing_id"], "trigger_track": trig.track_id,
                     "event_time": trig.time, "snapshot_time": before.max()})
    return rows


def detect_stop_events(d, area_id, polygon, stays, stop_speed, stop_duration, every_stop=False):
    """Cyclists inside the area whose speed stays below stop_speed for stop_duration."""
    t = d["timestamp"].to_numpy()
    tid = d["track_id"].to_numpy()
    first = d["track_id"].map(stays["first_in"]).to_numpy(dtype=float)
    last = d["track_id"].map(stays["last_in"]).to_numpy(dtype=float)
    inside = (t >= first) & (t <= last)
    stopped = inside & (d["speed"].to_numpy() < stop_speed)

    # runs of consecutive stopped rows within one track
    new_run = np.r_[True, (tid[1:] != tid[:-1]) | ~stopped[:-1]]
    run_id = np.cumsum(new_run)
    runs = (pd.DataFrame({"run": run_id[stopped], "track_id": tid[stopped], "t": t[stopped]})
            .groupby("run").agg(track_id=("track_id", "first"), start=("t", "min"), end=("t", "max")))
    runs = runs[(runs["end"] - runs["start"]) >= stop_duration - 1e-9].sort_values("start")
    if not every_stop:
        runs = runs.drop_duplicates("track_id")
    return [{"type": "stop", "area": area_id, "crossing_id": None,
             "trigger_track": r.track_id, "event_time": r.start, "snapshot_time": r.start}
            for r in runs.itertuples()]


# --------------------------------------------------
# SNAPSHOTS
# --------------------------------------------------


def take_snapshot(here, trigger_track, polygon, stays, frame, near):
    """Classify every cyclist in `here` (rows of one timestep); keep inside, near and the trigger."""
    first = here["track_id"].map(stays["first_in"])
    last = here["track_id"].map(stays["last_in"])
    inside = ((here["timestamp"] >= first) & (here["timestamp"] <= last)).to_numpy()
    dist = shapely.distance(polygon, shapely.points(here["utm_x"], here["utm_y"]))
    dist = np.where(inside, 0.0, dist)
    is_near = ~inside & (dist <= near)
    is_trigger = (here["track_id"] == trigger_track).to_numpy()
    keep = inside | is_near | is_trigger

    snap = here.loc[keep]
    x, y = frame.to_local(snap["utm_x"], snap["utm_y"])
    status = np.where(inside[keep], "inside", np.where(is_near[keep], "near", "far"))
    positions = pd.DataFrame({
        "track_id": snap["track_id"].to_numpy(), "status": status, "x": x, "y": y,
        "distance_to_area": dist[keep], "utm_x": snap["utm_x"].to_numpy(),
        "utm_y": snap["utm_y"].to_numpy(), "speed": snap["speed"].to_numpy(),
        "is_trigger": is_trigger[keep],
    })
    counts = {"n_inside": int(inside.sum()), "n_near": int(is_near.sum()),
              "trigger_inside": bool(inside[is_trigger].any())}
    return positions, counts


def snapshot_events(df, crossings, types=SNAPSHOT_EVENT_TYPES, near=NEAR_DISTANCE,
                    stop_speed=STOP_SPEED, stop_duration=STOP_DURATION, every_stop=EVERY_STOP):
    """
    df         cyclist rows: track_id, timestamp, utm_x, utm_y, speed
    crossings  [{"crossing_id", "start_area", "area_polygon", "start_line", "end_line"}]
               in METRIC_CRS. Stops are looked for in each crossing's start area.

    Every event belongs to one crossing (`crossing_id`); a stop in a start
    area shared by several crossings appears once per crossing.

    Returns (events, positions, frames) where frames = {crossing_id:
    {"area", "polygon", "frame", "crossing"}} describes every crossing used.
    """
    d = df.sort_values(["track_id", "timestamp"], kind="stable").reset_index(drop=True)
    by_time = {t: g for t, g in d.groupby("timestamp")}

    stays, frames = {}, {}
    for c in crossings:
        area = c["start_area"]
        if area not in stays:                 # who is inside when: per area, shared
            stays[area] = area_stays(d, c["area_polygon"])
        north = forward_normal(c["start_line"], c["end_line"])
        frames[c["crossing_id"]] = {"area": area, "polygon": c["area_polygon"], "crossing": c,
                                    "frame": local_frame(c["area_polygon"], north)}

    found = []
    if "start" in types:
        for c in crossings:
            found += detect_start_events(d, c)
    if "stop" in types:
        for area, area_stay in stays.items():
            on_area = [c for c in crossings if c["start_area"] == area]
            stops = detect_stop_events(d, area, on_area[0]["area_polygon"], area_stay,
                                       stop_speed, stop_duration, every_stop)
            found += [{**e, "crossing_id": c["crossing_id"]} for e in stops for c in on_area]

    found.sort(key=lambda e: (e["snapshot_time"], e["type"], e["crossing_id"]))
    events, positions = [], []
    for event_id, e in enumerate(found):
        f = frames[e["crossing_id"]]
        pos, counts = take_snapshot(by_time[e["snapshot_time"]], e["trigger_track"],
                                    f["polygon"], stays[e["area"]], f["frame"], near)
        pos.insert(0, "event_id", event_id)
        positions.append(pos)
        events.append({"event_id": event_id, **e, **counts})

    events = pd.DataFrame(events, columns=EVENT_COLUMNS)
    positions = (pd.concat(positions, ignore_index=True) if positions
                 else pd.DataFrame(columns=POSITION_COLUMNS))
    return events, positions[POSITION_COLUMNS], frames
