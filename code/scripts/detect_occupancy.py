"""
Occupancy and line passes, by default over the whole recording (all parts as one
timeline, so tracks crossing a part boundary stay one track):

  1. occupancy: how many cyclists are inside each waiting area at every
     timestep (centre point inside the polygon)
  2. line passes: for every crossing (define_crossings.py), each time a
     cyclist crosses its start line or end line, with direction
     (+1 = start -> end, -1 = the other way). Each bike is counted at
     most once per line and direction.

    python code/scripts/detect_occupancy.py              # all parts, cyclists
    python code/scripts/detect_occupancy.py --part 16    # one part (or a range: 14-18)
    python code/scripts/detect_occupancy.py --part 3 --categories 3 8

Writes to results/occupancy/ (<P> = all, part16 or part14-18):
    <P>_occupancy.csv          timestamp, area_0 ... area_7, total
    <P>_line_passes.csv        every line pass: crossing_id, line, track_id, time, direction, x, y
    <P>_crossing_summary.csv   per crossing: bikes crossing start / end line forward and backward
"""

import argparse

import _bootstrap  # noqa: F401
import pandas as pd

from its.analysis.line_passes import first_forward_per_track, forward_normal, line_passes
from its.analysis.occupancy import count_in_areas
from its.crossings import crossing_areas_path, load_crossing_lines, load_source
from its.config import BICYCLE, CROSSING_LAYER, MAPS_DIR, N_PARTS, OCCUPANCY_RESULTS_DIR
from its.trajectories import (
    add_metric_coordinates, frame_timestamps, load_parts, parse_parts, parts_label,
)


def detect(parts, categories, layer=CROSSING_LAYER):
    timestamps = frame_timestamps(parts)           # every frame, also those without cyclists
    df = add_metric_coordinates(load_parts(parts, categories=categories,
                                           columns=["timestamp", "category", "track_id"]))

    areas = load_source(layer)
    occupancy = count_in_areas(df, areas.geometry, timestamps)

    rows = []
    crossing_ids = []
    if crossing_areas_path(layer).exists():
        lines = load_crossing_lines(layer, 0)       # start and end line of every crossing
        crossing_ids = sorted(lines["crossing_id"].unique())
        for cid, grp in lines.groupby("crossing_id"):
            by_role = dict(zip(grp["role"], grp.geometry))
            normal = forward_normal(by_role["start"], by_role["end"])
            for role in ("start", "end"):
                c = line_passes(df, by_role[role], normal)
                c.insert(0, "line", role)
                c.insert(0, "crossing_id", cid)
                rows.append(c)
    crossings = (pd.concat(rows, ignore_index=True) if rows
                 else pd.DataFrame(columns=["crossing_id", "line", "track_id", "time",
                                            "direction", "x", "y"]))
    return df, occupancy, crossings, crossing_ids


def summarise(crossings, crossing_ids):
    """Per crossing: distinct bikes crossing each line forward / backward
    (crossings nobody crossed get zeros)."""
    rows = []
    for cid in crossing_ids:
        grp = crossings[crossings["crossing_id"] == cid]
        row = {"crossing_id": cid}
        for role in ("start", "end"):
            g = grp[grp["line"] == role]
            row[f"{role}_forward"] = g.loc[g["direction"] > 0, "track_id"].nunique()
            row[f"{role}_backward"] = g.loc[g["direction"] < 0, "track_id"].nunique()
        both = (set(first_forward_per_track(grp[grp["line"] == "start"])["track_id"])
                & set(first_forward_per_track(grp[grp["line"] == "end"])["track_id"]))
        row["start_and_end_forward"] = len(both)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", type=parse_parts, default="all", metavar="P",
                   help=f"a part (16), a range (14-18) or all (1-{N_PARTS}; default)")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes to count (default 3: cyclists)")
    args = p.parse_args()

    df, occupancy, crossings, crossing_ids = detect(args.part, args.categories)
    summary = summarise(crossings, crossing_ids)

    OCCUPANCY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    label = parts_label(args.part)
    stem = OCCUPANCY_RESULTS_DIR / label
    occupancy.to_csv(f"{stem}_occupancy.csv", index=False)
    crossings.to_csv(f"{stem}_line_passes.csv", index=False)
    summary.to_csv(f"{stem}_crossing_summary.csv", index=False)

    area_cols = [c for c in occupancy.columns if c.startswith("area_")]
    print(f"{label}: {df['track_id'].nunique()} tracks, {len(occupancy)} timesteps "
          f"(maps from {MAPS_DIR})")
    print("Occupancy, max / mean per area:")
    for c in area_cols:
        print(f"  {c}: max {occupancy[c].max()}, mean {occupancy[c].mean():.2f}")
    print("Bikes crossing each line (each bike once):")
    print(summary.to_string(index=False) if len(summary) else "  no crossings defined")
    print(f"Wrote {stem}_occupancy.csv, _line_passes.csv, _crossing_summary.csv")


if __name__ == "__main__":
    main()
