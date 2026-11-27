"""
Discharge events: a stopped queue released over a crossing's lines.

Naming
    crossing         the area / band only (crossing_id), never an event
    line             one of the crossing's N + 2 lines: line_index 0 is the
                     start line (line_role "start"), 1 ... N the lines in
                     between ("line"), N + 1 the end line ("end")
    line pass        one cyclist going forward over one line (a measurement)
    start event      a cyclist's first forward pass of the start line
                     (type "start" in its.analysis.start_stop)
    stop event       a cyclist stopping in the start waiting area (type "stop")
    reference stop   the stop event a start event is matched to: the latest
                     stop event of the same crossing at or before it, at most
                     `max_lag` s earlier
    queue            the cyclists inside the area with speed < stop_speed in
                     the reference stop's snapshot; queue_position 1 is the
                     one closest to the start line (smallest local x)
    discharge        one queue, one per reference stop. Of the start events
                     matched to that stop (n_start_events), the trigger is
                     the first one by a queue member: trigger_kind "queue".
                     Start events by non-members before it are rolling starts
                     (n_skipped_starts). If no queue member has a matched
                     start event, the trigger is the first matched start
                     event, a rolling start: trigger_kind "rolling",
                     n_skipped_starts 0. Both kinds are kept and numbered
                     together in time order.
    discharge pass   a queue member's first forward pass of a line after the
                     reference stop's snapshot

A cyclist can be in several queues (it was still waiting when a later
stop happened); its passes are then listed under each discharge.
"""

import numpy as np
import pandas as pd

from its.analysis.line_passes import forward_normal, line_passes

DISCHARGE_COLUMNS = ["discharge_id", "crossing_id", "area", "n_lines", "stop_event_id", "trigger_event_id",
                     "trigger_track", "trigger_kind", "trigger_in_queue", "n_skipped_starts", "stop_time", "release_time",
                     "n_start_events", "n_queue", "n_reached_start", "n_reached_end"]
QUEUE_COLUMNS = ["discharge_id", "track_id", "queue_position", "x", "y", "utm_x", "utm_y",
                 "speed"]
_NO_POSITIONS = pd.DataFrame(columns=["track_id", "status", "x", "y", "utm_x", "utm_y", "speed"])
PASS_COLUMNS = ["discharge_id", "crossing_id", "track_id", "queue_position", "line_index",
                "line_role", "time", "time_since_release", "x", "y"]


def match_reference_stops(events, max_lag):
    """
    Every start event with its reference stop. Returns the start events
    (event_id, crossing_id, trigger_track, event_time) with stop_event_id
    added; start events without a reference stop are dropped.
    """
    starts = events[events["type"] == "start"].sort_values("event_time")
    stops = events[events["type"] == "stop"].sort_values("event_time")
    if starts.empty or stops.empty:
        return starts.assign(stop_event_id=pd.Series(dtype=int)).iloc[0:0]
    matched = pd.merge_asof(
        starts[["event_id", "crossing_id", "trigger_track", "event_time"]],
        stops[["event_id", "crossing_id", "event_time"]].rename(
            columns={"event_id": "stop_event_id", "event_time": "stop_event_time"}),
        left_on="event_time", right_on="stop_event_time", by="crossing_id",
        direction="backward", tolerance=max_lag, allow_exact_matches=True)
    matched = matched.dropna(subset=["stop_event_id"])
    return matched.astype({"stop_event_id": int})


def queue_members(positions, stop_event_id, stop_speed):
    """
    The queue of one stop event: track_id, queue_position (1 = nearest the
    start line) and its snapshot position (local x, y, utm_x, utm_y) and speed.
    `positions` may also be {event_id: that event's positions}.
    """
    if isinstance(positions, dict):
        p = positions.get(stop_event_id, _NO_POSITIONS)
    else:
        p = positions[positions["event_id"] == stop_event_id]
    p = p[(p["status"] == "inside") & (p["speed"] < stop_speed)].sort_values("x")
    q = p[["track_id", "x", "y", "utm_x", "utm_y", "speed"]].reset_index(drop=True)
    q.insert(1, "queue_position", np.arange(1, len(q) + 1))
    return q


def first_passes(df, crossing_lines, crossing_id, tracks):
    """
    Every forward pass of `tracks` over each line of one crossing:
    track_id, time, x, y, line_index, line_role (all passes, not only the first).
    """
    lines = crossing_lines[crossing_lines["crossing_id"] == crossing_id].sort_values("index")
    by_role = dict(zip(lines["role"], lines.geometry))
    normal = forward_normal(by_role["start"], by_role["end"])
    d = df[df["track_id"].isin(tracks)]
    out = []
    for line in lines.itertuples():
        c = line_passes(d, line.geometry, normal)
        c = c[c["direction"] > 0].drop(columns="direction")
        out.append(c.assign(line_index=int(line.index), line_role=line.role))
    return pd.concat(out, ignore_index=True)


def discharge_events(df, events, positions, crossing_lines, stop_speed, max_lag):
    """
    df              cyclist rows: track_id, timestamp, utm_x, utm_y (METRIC_CRS)
    events          snapshot events with types "start" and "stop"
                    (its.analysis.start_stop.start_stop_events)
    positions       their snapshot positions
    crossing_lines  its.crossings.load_crossing_lines(): crossing_id, role, index, geometry

    Returns (discharges, queues, passes) with DISCHARGE_COLUMNS, QUEUE_COLUMNS
    and PASS_COLUMNS. n_lines is N, the number of lines between start and end.
    """
    matched = match_reference_stops(events, max_lag)
    stop_info = events.set_index("event_id")
    n_lines = crossing_lines.groupby("crossing_id")["index"].max()   # index of the end line

    discharges, passes, queue_rows = [], [], []
    queues = {}
    found = []
    by_event = {k: g for k, g in positions.groupby("event_id")}
    for stop_id, grp in matched.groupby("stop_event_id"):
        grp = grp.sort_values("event_time")
        q = queue_members(by_event, stop_id, stop_speed)
        in_queue = grp["trigger_track"].isin(q["track_id"]).to_numpy()
        first = int(np.argmax(in_queue)) if in_queue.any() else 0
        found.append((grp.iloc[first], stop_id, grp, q, bool(in_queue.any()), first))
    found.sort(key=lambda f: f[0]["event_time"])        # number by release time

    for discharge_id, (trig, stop_id, grp, q, by_queue, n_skipped) in enumerate(found):
        stop = stop_info.loc[stop_id]
        queue_rows.append(q.assign(discharge_id=discharge_id))
        queues[discharge_id] = (int(trig["crossing_id"]), float(stop["snapshot_time"]),
                                float(trig["event_time"]), q)
        discharges.append({
            "discharge_id": discharge_id, "crossing_id": int(trig["crossing_id"]),
            "area": int(stop["area"]), "n_lines": int(n_lines[int(trig["crossing_id"])]) - 1,
            "stop_event_id": int(stop_id),
            "trigger_event_id": int(trig["event_id"]), "trigger_track": int(trig["trigger_track"]),
            "trigger_kind": "queue" if by_queue else "rolling",
            "trigger_in_queue": by_queue,
            "n_skipped_starts": n_skipped if by_queue else 0,
            "stop_time": float(stop["snapshot_time"]), "release_time": float(trig["event_time"]),
            "n_start_events": len(grp), "n_queue": len(q),
        })

    # line passes per crossing, once for every track that is in any of its queues
    all_passes = {}
    for cid in {c for c, *_ in queues.values()}:
        tracks = set().union(*(set(q["track_id"]) for c, _, _, q in queues.values() if c == cid))
        all_passes[cid] = first_passes(df, crossing_lines, cid, tracks) if tracks else None

    for row in discharges:
        cid, stop_time, release, q = queues[row["discharge_id"]]
        ap = all_passes[cid]
        if ap is None or q.empty:
            row["n_reached_start"] = row["n_reached_end"] = 0
            continue
        p = ap[ap["track_id"].isin(q["track_id"]) & (ap["time"] > stop_time)]
        p = p.sort_values("time").drop_duplicates(["track_id", "line_index"])
        p = p.merge(q[["track_id", "queue_position"]], on="track_id")
        p = p.assign(discharge_id=row["discharge_id"], crossing_id=cid,
                     time_since_release=p["time"] - release)
        passes.append(p)
        row["n_reached_start"] = int((p["line_index"] == 0).sum())
        row["n_reached_end"] = int((p["line_index"] == n_lines[cid]).sum())

    discharges = pd.DataFrame(discharges, columns=DISCHARGE_COLUMNS)
    queues = (pd.concat(queue_rows, ignore_index=True)[QUEUE_COLUMNS] if queue_rows
              else pd.DataFrame(columns=QUEUE_COLUMNS))
    passes = (pd.concat(passes, ignore_index=True)[PASS_COLUMNS]
              .sort_values(["discharge_id", "queue_position", "line_index"]).reset_index(drop=True)
              if passes else pd.DataFrame(columns=PASS_COLUMNS))
    return discharges, queues, passes
