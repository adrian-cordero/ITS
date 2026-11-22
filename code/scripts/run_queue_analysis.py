"""
Detect cyclist discharge events and their queue size over time, and
write them to results/.

Needs the stop/exit lines in config.STOP_EXIT_PAIRS.

    python code/scripts/run_queue_analysis.py --parts 16
    python code/scripts/run_queue_analysis.py --parts 1 2 3
"""

import argparse

import _bootstrap  # noqa: F401
import pandas as pd

from its.analysis.crossings import detect_events, event_time_series
from its.config import BICYCLE, N_PARTS, RESULTS_DIR, STOP_EXIT_PAIRS
from its.trajectories import load_part, tracks


def analyse_part(part):
    df = load_part(part, columns=["timestamp", "category", "track_id"])
    timestamps = df["timestamp"].unique()
    bikes = df[df["category"] == BICYCLE]

    events = detect_events(tracks(bikes), STOP_EXIT_PAIRS)
    events.insert(0, "part", part)

    series = []
    for _, event in events.iterrows():
        s = event_time_series(event, bikes, timestamps).drop(columns="polygon")
        s.insert(0, "event_id", event["event_id"])
        s.insert(0, "part", part)
        series.append(s)

    return events, (pd.concat(series, ignore_index=True) if series else pd.DataFrame())


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--parts", type=int, nargs="+", default=[16],
                   choices=range(1, N_PARTS + 1), metavar="N")
    args = p.parse_args()

    if not STOP_EXIT_PAIRS:
        raise SystemExit("config.STOP_EXIT_PAIRS is empty: define the stop and exit "
                         "lines in code/its/config.py first.")

    RESULTS_DIR.mkdir(exist_ok=True)
    all_events, all_series = [], []
    for part in args.parts:
        events, series = analyse_part(part)
        print(f"Part {part}: {len(events)} events")
        all_events.append(events)
        all_series.append(series)

    pd.concat(all_events, ignore_index=True).to_csv(RESULTS_DIR / "events.csv", index=False)
    pd.concat(all_series, ignore_index=True).to_csv(RESULTS_DIR / "event_series.csv", index=False)
    print(f"Wrote {RESULTS_DIR / 'events.csv'} and {RESULTS_DIR / 'event_series.csv'}")


if __name__ == "__main__":
    main()
