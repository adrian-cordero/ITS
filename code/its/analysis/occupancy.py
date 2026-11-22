"""
Road users inside each area, and when they enter and leave.

Each object (track_id) enters an area at most once and leaves it at most
once: its stay runs from the first timestep its centre point is inside
the polygon to the last one. Moving out and back in during the stay
(a centre point wobbling over the edge) doesn't count as leaving, and
the object counts as inside for the whole stay.

Positions (utm_x, utm_y) and polygons are compared in METRIC_CRS (UTM),
see its.trajectories.add_metric_coordinates.
"""

import numpy as np
import pandas as pd
import shapely

_EVENT_COLUMNS = ["area", "track_id", "enter_time", "exit_time", "started_inside", "ended_inside"]


def _sorted(df):
    return df.sort_values(["track_id", "timestamp"], kind="stable")


def area_stays(df, poly):
    """Per track with any position inside `poly`: first and last timestamp
    inside (index track_id, columns first_in, last_in)."""
    return _stays(df, poly)


def _stays(d, poly):
    """Per track with any position inside `poly`: first and last timestamp inside."""
    inside = shapely.contains_xy(poly, d["utm_x"].to_numpy(), d["utm_y"].to_numpy())
    g = d.loc[inside].groupby("track_id")["timestamp"]
    return pd.DataFrame({"first_in": g.min(), "last_in": g.max()})


def area_events(df: pd.DataFrame, areas) -> pd.DataFrame:
    """
    One row per (area, object) that is ever inside the area:

    enter_time      first timestep inside
    exit_time       first timestep after the last one inside (NaN if the
                    track ends inside)
    started_inside  the track's first position is already inside (it
                    entered before the recording started)
    ended_inside    the track ends inside, so it never leaves

    df     rows with columns track_id, timestamp, utm_x, utm_y
    areas  sequence of polygons in METRIC_CRS
    """
    d = _sorted(df)
    t = d["timestamp"].to_numpy()
    tid = d["track_id"]
    track_first = d.groupby("track_id")["timestamp"].min()
    track_last = d.groupby("track_id")["timestamp"].max()

    rows = []
    for i, poly in enumerate(areas):
        stays = _stays(d, poly)
        if stays.empty:
            continue
        # exit = the track's first timestep after its last one inside
        after = t > tid.map(stays["last_in"]).to_numpy(dtype=float)
        exit_time = d.loc[after].groupby("track_id")["timestamp"].min()

        ev = stays.copy()
        ev["exit_time"] = exit_time.reindex(ev.index)
        ev["started_inside"] = ev["first_in"] == track_first.reindex(ev.index)
        ev["ended_inside"] = ev["last_in"] == track_last.reindex(ev.index)
        ev = ev.reset_index().rename(columns={"first_in": "enter_time"})
        ev.insert(0, "area", i)
        rows.append(ev[_EVENT_COLUMNS])

    if not rows:
        return pd.DataFrame(columns=_EVENT_COLUMNS)
    return pd.concat(rows, ignore_index=True)


def count_in_areas(df: pd.DataFrame, areas, timestamps) -> pd.DataFrame:
    """
    One row per timestamp in `timestamps` (including ones with nobody
    inside), one column per area: `area_0`, `area_1`, ... plus `total`
    (objects inside any area, each counted once). An object counts as
    inside for its whole stay (first to last timestep inside).
    """
    d = _sorted(df)
    t = d["timestamp"].to_numpy()
    tid = d["track_id"]
    index = pd.Index(np.sort(np.unique(timestamps)), name="timestamp")

    out = pd.DataFrame(index=index)
    in_any = np.zeros(len(d), dtype=bool)
    for i, poly in enumerate(areas):
        stays = _stays(d, poly)
        first = tid.map(stays["first_in"]).to_numpy(dtype=float)
        last = tid.map(stays["last_in"]).to_numpy(dtype=float)
        in_stay = (t >= first) & (t <= last)                    # NaN compares False
        in_any |= in_stay
        out[f"area_{i}"] = pd.Series(t[in_stay]).value_counts().reindex(index, fill_value=0).to_numpy()
    out["total"] = pd.Series(t[in_any]).value_counts().reindex(index, fill_value=0).to_numpy()
    return out.astype(int).reset_index()


def event_counts(events: pd.DataFrame, n_areas: int) -> pd.DataFrame:
    """Per area: entries (objects that entered, once each) and exits (objects that left)."""
    g = events.groupby("area")
    out = pd.DataFrame({
        "entries": g["track_id"].nunique(),
        "exits": g["exit_time"].count(),
        "started_inside": g["started_inside"].sum(),
        "ended_inside": g["ended_inside"].sum(),
    }).reindex(range(n_areas), fill_value=0)
    out.index.name = "area"
    return out.astype(int).reset_index()
