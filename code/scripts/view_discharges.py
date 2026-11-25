"""
Discharge viewer: how each stopped queue left its waiting area over the
crossing's lines. It only reads results; detect them first with

    python code/scripts/snapshot_events.py --part 16        # writes the discharge CSVs
    python code/scripts/view_discharges.py                  # part 16, queue discharges
    python code/scripts/view_discharges.py --kind all       # also rolling-start discharges

    python code/scripts/snapshot_events.py --part all       # the whole recording
    python code/scripts/view_discharges.py --part all --min-bikes 4   # queues of 4 or more

--part must match the snapshot_events.py run (16, 14-18 or all).
--min-bikes N only shows discharges with at least N cyclists in the queue
(n_queue >= N; the "min bikes" box changes it in the window).

Reads from results/, as <S> = part16, part14-18 or all:
    <S>_discharges.csv, _discharge_queues.csv, _discharge_passes.csv
    <S>_event_positions.csv   (the other cyclists at the reference stop)
and the parts' trajectories, for the paths.

Panels, in the order the discharge happens:
    queue & paths   (top left) the waiting area and crossing in the local
                    frame (start line at x = 0, the crossing at negative x):
                    queue members numbered by queue position at the
                    reference stop, their paths up to the end line, a dot
                    at every line pass. Other cyclists at the stop in grey.
    time-distance   (top right) distance from the start line (m) against
                    time since the release (s), one curve per member; the
                    lines are horizontal gridlines, the release is t = 0.
                    The spacing at the start line is the headway, the slope
                    the speed. ★ = trigger.
    headways        (bottom left) at the start line, in the order the
                    members crossed it: the gap to the one before (the first
                    bar: from the release).
    table           (right) per member: start / end pass time and headway.
Each member has the same colour in every panel.

Menus: the crossing (or up / down keys), the kind (queue / rolling /
all) and the smallest queue shown ("min bikes", Enter to apply). Previous / Next (or left / right keys) step through the discharges.
"Show" switches the paths, the lines between start and end and the other
cyclists on and off.
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox

from its.analysis.crossings import forward_normal
from its.analysis.snapshots import local_frame
from its.areas import crossing_length
from its.config import BICYCLE, CROSSING_LAYER, DISCHARGE_MIN_BIKES, N_PARTS, RESULTS_DIR
from its.trajectories import add_metric_coordinates, load_parts, parse_parts, parts_label
from its.viz.events import (
    END_COLOR, MID_STYLE, START_COLOR, draw_local_crossing, free_keys, load_bands,
    load_crossings, mid_lines_of,
)

KINDS = ("queue", "rolling", "all")
# a member that never reaches the end line: its path is drawn this long after the release
PATH_AFTER = 20.0
# the time-distance plot starts at most this long before the release
TD_BEFORE = 10.0
MARGIN = 2.0        # metres around the area and crossing in the queue panel


def member_colors(n):
    """One colour per queue position (1 ... n)."""
    cmap = plt.get_cmap("tab10")
    return {k: cmap((k - 1) % 10) for k in range(1, n + 1)}


# --------------------------------------------------
# DATA
# --------------------------------------------------


def read_results(label, part_arg):
    """The discharge CSVs of one snapshot_events.py run (label: part16, part14-18, all)."""
    names = ("discharges", "discharge_queues", "discharge_passes", "event_positions")
    missing = [n for n in names if not (RESULTS_DIR / f"{label}_{n}.csv").exists()]
    if missing:
        raise SystemExit(f"{', '.join(f'{label}_{n}.csv' for n in missing)} not found in "
                         f"{RESULTS_DIR}: run snapshot_events.py --part {part_arg} first")
    out = [pd.read_csv(RESULTS_DIR / f"{label}_{n}.csv") for n in names]
    if "part" not in out[0]:
        raise SystemExit(f"{label}_discharges.csv is from an older version: "
                         f"rerun snapshot_events.py --part {part_arg}")
    return out


class Scene:
    """Everything the panels need: crossings in their local frames and the tracks."""

    def __init__(self, parts, categories, discharges, queues, passes, positions):
        self.discharges = discharges
        self.queues = {k: g for k, g in queues.groupby("discharge_id")}
        self.passes = {k: g for k, g in passes.groupby("discharge_id")}
        self.no_queue, self.no_passes = queues.iloc[0:0], passes.iloc[0:0]
        self.positions = {k: g for k, g in positions.groupby("event_id")}

        used = set(discharges["crossing_id"].astype(int))
        bands = load_bands(CROSSING_LAYER)
        self.crossings = {}
        for c in load_crossings(CROSSING_LAYER, used):
            north = forward_normal(c["start_line"], c["end_line"])
            self.crossings[c["crossing_id"]] = {
                **c, "band": bands.get(c["crossing_id"]),
                "frame": local_frame(c["area_polygon"], north),
                "length": crossing_length(c["start_line"], c["end_line"]),
            }

        print("Loading the trajectories...")
        tracks = set(queues["track_id"])
        df = load_parts(parts, categories=categories,
                        columns=["timestamp", "category", "track_id"])
        df = add_metric_coordinates(df[df["track_id"].isin(tracks)].copy())
        self.tracks = {t: g.sort_values("timestamp") for t, g in df.groupby("track_id")}
        self.layers = {"paths": True, "crossing lines": True, "other cyclists": True}

    def line_distance(self, crossing_id, n_lines, line_index):
        """Distance (m) of line `line_index` from the start line."""
        return line_index * self.crossings[crossing_id]["length"] / (n_lines + 1)


def member_data(scene, d):
    """
    Per queue member of discharge row `d`: queue position, track, colour,
    snapshot position, path (local x, y, distance, time since release) and passes.
    """
    q = scene.queues.get(d["discharge_id"], scene.no_queue)
    p = scene.passes.get(d["discharge_id"], scene.no_passes)
    c = scene.crossings[d["crossing_id"]]
    end_index = d["n_lines"] + 1
    colors = member_colors(len(q))
    out = []
    for m in q.sort_values("queue_position").itertuples():
        mp = p[p["track_id"] == m.track_id].sort_values("line_index")
        end_pass = mp.loc[mp["line_index"] == end_index, "time"]
        t_to = end_pass.iloc[0] if len(end_pass) else d["release_time"] + PATH_AFTER
        tr = scene.tracks.get(m.track_id)
        if tr is not None:
            tr = tr[(tr["timestamp"] >= d["stop_time"]) & (tr["timestamp"] <= t_to)]
            px, py = c["frame"].to_local(tr["utm_x"], tr["utm_y"])
            pt = tr["timestamp"].to_numpy() - d["release_time"]
        else:
            px = py = pt = np.array([])
        out.append({"pos": m.queue_position, "track": m.track_id, "color": colors[m.queue_position],
                    "x": m.x, "y": m.y, "px": px, "py": py, "pd": -px, "pt": pt, "passes": mp})
    return out


def start_headways(members):
    """[(member, headway)] in the order the members passed the start line."""
    starts = [(m, m["passes"].loc[m["passes"]["line_index"] == 0, "time_since_release"])
              for m in members]
    starts = sorted(((m, s.iloc[0]) for m, s in starts if len(s)), key=lambda ms: ms[1])
    return [(m, t - (starts[i - 1][1] if i else 0.0)) for i, (m, t) in enumerate(starts)]


# --------------------------------------------------
# DRAWING
# --------------------------------------------------


def draw_queue(ax, scene, d, members):
    """Top left: queue at the reference stop and the members' paths in the local frame."""
    ax.clear()
    c = scene.crossings[d["crossing_id"]]
    frame = c["frame"]
    mids = mid_lines_of(c, d["n_lines"])
    xs, ys = draw_local_crossing(ax, frame, c["area_polygon"], c["start_line"], c["band"], mids,
                                 c["end_line"], layers=scene.layers)

    queued = {m["track"] for m in members}
    if scene.layers["other cyclists"]:
        snap = scene.positions.get(d["stop_event_id"])
        if snap is not None:
            other = snap[~snap["track_id"].isin(queued)]
            ax.scatter(other["x"], other["y"], s=25, color="0.6", edgecolor="white", zorder=4,
                       label="other cyclists at the stop")
    for m in members:
        if scene.layers["paths"] and len(m["px"]):
            ax.plot(m["px"], m["py"], color=m["color"], linewidth=1.4, alpha=0.8, zorder=5)
            if len(m["passes"]):
                lx, ly = frame.to_local(m["passes"]["x"], m["passes"]["y"])
                ax.scatter(lx, ly, s=18, color=m["color"], edgecolor="black", linewidth=0.4,
                           zorder=6)
        trig = m["track"] == d["trigger_track"]
        ax.scatter(m["x"], m["y"], s=260 if trig else 130, marker="*" if trig else "o",
                   color=m["color"], edgecolor="black", zorder=7)
        ax.annotate(str(m["pos"]), (m["x"], m["y"]), ha="center", va="center", fontsize=7,
                    color="white", fontweight="bold", zorder=8)

    ax.set_xlim(xs.min() - MARGIN, xs.max() + MARGIN)
    ax.set_ylim(ys.min() - MARGIN, ys.max() + MARGIN)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m): < 0 crossing · > 0 waiting area")
    ax.set_ylabel("y (m, along the start line)")
    ax.set_title(f"Queue at the reference stop (event {d['stop_event_id']}) and paths",
                 fontsize=10)


def draw_time_distance(ax, scene, d, members):
    """Top right: distance from the start line against time since the release."""
    ax.clear()
    cid, n = d["crossing_id"], d["n_lines"]
    for i in range(n + 2):
        dist = scene.line_distance(cid, n, i)
        style = (dict(color=START_COLOR, linewidth=1.6) if i == 0 else
                 dict(color=END_COLOR, linewidth=1.6) if i == n + 1 else
                 dict(MID_STYLE, linestyle=":"))
        ax.axhline(dist, zorder=1, **style)
        ax.annotate("start" if i == 0 else "end" if i == n + 1 else f"line {i}",
                    (1.0, dist), xycoords=("axes fraction", "data"), xytext=(3, 0),
                    textcoords="offset points", va="center", fontsize=7)
    ax.axvline(0, color="tab:red", linewidth=1, linestyle="--", zorder=1)

    t_max = 1.0
    for m in members:
        if len(m["pt"]):
            ax.plot(m["pt"], m["pd"], color=m["color"], linewidth=1.6, zorder=3,
                    label=f"{m['pos']}: {m['track']}")
        p = m["passes"]
        if len(p):
            dist = [scene.line_distance(cid, n, i) for i in p["line_index"]]
            ax.scatter(p["time_since_release"], dist, s=22, color=m["color"], edgecolor="black",
                       linewidth=0.4, zorder=4)
            t_max = max(t_max, p["time_since_release"].max())
            if m["track"] == d["trigger_track"]:
                s0 = p[p["line_index"] == 0]
                if len(s0):
                    ax.scatter(s0["time_since_release"], [0.0], s=220, marker="*",
                               color=m["color"], edgecolor="black", zorder=5)

    t_min = max(d["stop_time"] - d["release_time"], -TD_BEFORE)
    ax.set_xlim(t_min - 0.5, t_max + 1.0)
    lows = [m["pd"].min() for m in members if len(m["pd"])]
    ax.set_ylim(min(lows + [0.0]) - 1.0, scene.line_distance(cid, n, n + 1) + 1.0)
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_xlabel("time since release (s)")
    ax.set_ylabel("distance from the start line (m)")
    ax.set_title(f"Time–distance (reference stop at {d['stop_time'] - d['release_time']:.1f} s)",
                 fontsize=10)
    if members:
        ax.legend(fontsize=7, loc="upper left", title="pos: track", title_fontsize=7)


def draw_headways(ax, hw):
    """Bottom left: start-line headways in passing order."""
    ax.clear()
    if hw:
        k = np.arange(1, len(hw) + 1)
        ax.bar(k, [h for _, h in hw], color=[m["color"] for m, _ in hw], edgecolor="black",
               linewidth=0.5)
        ax.set_xticks(k, [f"{i}\n(pos {m['pos']})" for i, (m, _) in zip(k, hw)], fontsize=7)
    else:
        ax.text(0.5, 0.5, "nobody in the queue passed the start line", ha="center",
                va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([])
    ax.axhline(0, color="black", linewidth=0.6)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylabel("headway (s)")
    ax.set_title("Start-line headways, in passing order (1st: from the release)", fontsize=10)


def table_text(d, members, hw, i, n):
    end_index = d["n_lines"] + 1
    headway = {m["track"]: h for m, h in hw}
    rows = [f"discharge {i + 1} of {n}", "",
            f"part      {d['part']}",
            f"kind      {d['trigger_kind']}",
            f"trigger   {d['trigger_track']} (event {d['trigger_event_id']})"
            + ("" if d["trigger_in_queue"] else "\n          rolling start, not queued"),
            f"skipped   {d['n_skipped_starts']} rolling start(s)",
            f"starts    {d['n_start_events']} matched",
            f"queue     {d['n_queue']}",
            f"reached   start {d['n_reached_start']} · end {d['n_reached_end']}",
            f"lines     N = {d['n_lines']}", "",
            f"{'pos':>3} {'track':>6} {'t_s':>6} {'t_e':>6} {'hw':>5}"]
    for m in members:
        p = m["passes"]
        ts = p.loc[p["line_index"] == 0, "time_since_release"]
        te = p.loc[p["line_index"] == end_index, "time_since_release"]
        fmt = lambda s: f"{s.iloc[0]:>6.2f}" if len(s) else f"{'–':>6}"
        h = headway.get(m["track"])
        rows.append(f"{m['pos']:>3} {m['track']:>6} {fmt(ts)} {fmt(te)} "
                    + (f"{h:>5.2f}" if h is not None else f"{'–':>5}")
                    + (" ★" if m["track"] == d["trigger_track"] else ""))
    rows += ["", "t_s, t_e: start / end line pass,", "  s since release",
             "hw: start-line headway (s)", "★ trigger"]
    return "\n".join(rows)


# --------------------------------------------------
# VIEWER
# --------------------------------------------------


class DischargeViewer:

    def __init__(self, scene, kind="queue", min_bikes=DISCHARGE_MIN_BIKES):
        self.scene = scene
        self.all = scene.discharges.sort_values("release_time").to_dict("records")
        self.kind = kind
        self.min_bikes = min_bikes
        self.crossing_labels = {f"#{cid} (area {c['start_area']})": cid
                                for cid, c in sorted(scene.crossings.items())}
        self.crossing = next(iter(self.crossing_labels.values()))
        self.items, self.i = [], 0
        free_keys("left", "right", "up", "down", "n", "b")

        self.fig = plt.figure(figsize=(17, 9))
        self.ax_queue = self.fig.add_axes([0.04, 0.45, 0.34, 0.46])
        self.ax_td = self.fig.add_axes([0.43, 0.45, 0.31, 0.46])
        self.ax_hw = self.fig.add_axes([0.05, 0.19, 0.33, 0.19])
        self.table_ax = self.fig.add_axes([0.80, 0.17, 0.19, 0.74])
        self.table_ax.axis("off")

        self.prev_button = Button(self.fig.add_axes([0.04, 0.04, 0.1, 0.06]), "◀ Previous")
        self.next_button = Button(self.fig.add_axes([0.15, 0.04, 0.1, 0.06]), "Next ▶")
        self.prev_button.on_clicked(lambda _e: self.step(-1))
        self.next_button.on_clicked(lambda _e: self.step(+1))

        n = len(self.crossing_labels)
        crossing_ax = self.fig.add_axes([0.29, 0.01, 0.16, min(0.12, 0.03 * n + 0.02)])
        crossing_ax.set_title("Crossing", fontsize=9, loc="left")
        self.crossing_radio = RadioButtons(crossing_ax, tuple(self.crossing_labels))
        self.crossing_radio.on_clicked(self.set_crossing)

        kind_ax = self.fig.add_axes([0.48, 0.01, 0.10, 0.12])
        kind_ax.set_title("Kind", fontsize=9, loc="left")
        self.kind_radio = RadioButtons(kind_ax, KINDS, active=KINDS.index(kind))
        self.kind_radio.on_clicked(self.set_kind)

        layers_ax = self.fig.add_axes([0.61, 0.01, 0.14, 0.12])
        layers_ax.set_title("Show", fontsize=9, loc="left")
        self.layer_checks = CheckButtons(layers_ax, tuple(scene.layers),
                                         tuple(scene.layers.values()))
        self.layer_checks.on_clicked(self.toggle_layer)

        self.min_box = TextBox(self.fig.add_axes([0.87, 0.04, 0.05, 0.05]), "min bikes ",
                               initial=str(min_bikes))
        self.min_box.on_submit(self.set_min_bikes)

        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.refilter()

    def set_min_bikes(self, text):
        try:
            self.min_bikes = max(0, int(text))
        except ValueError:                      # not a number: put the last value back
            self.min_box.set_val(str(self.min_bikes))
            return
        self.refilter()

    def set_kind(self, kind):
        self.kind = kind
        self.refilter()

    def set_crossing(self, label):
        self.crossing = self.crossing_labels[label]
        self.refilter()

    def toggle_layer(self, name):
        self.scene.layers[name] = not self.scene.layers[name]
        self.show()

    def refilter(self):
        self.items = [d for d in self.all if d["crossing_id"] == self.crossing
                      and (self.kind == "all" or d["trigger_kind"] == self.kind)
                      and d["n_queue"] >= self.min_bikes]
        self.i = 0
        self.show()

    def step(self, delta):
        if self.items:
            self.i = (self.i + delta) % len(self.items)
        self.show()

    def on_key(self, event):
        if self.min_box.capturekeystrokes:          # typing in the "min bikes" box
            return
        if event.key in ("right", "n"):
            self.step(+1)
        elif event.key in ("left", "b"):
            self.step(-1)
        elif event.key in ("up", "down"):
            labels = list(self.crossing_labels)
            j = labels.index(self.crossing_radio.value_selected)
            self.crossing_radio.set_active((j + (1 if event.key == "down" else -1)) % len(labels))

    def show(self):
        self.table_ax.clear()
        self.table_ax.axis("off")
        if not self.items:
            for ax in (self.ax_queue, self.ax_td, self.ax_hw):
                ax.clear()
            what = "" if self.kind == "all" else f"{self.kind} "
            self.fig.suptitle(f"No {what}discharges with at least {self.min_bikes} bike(s) "
                              f"for crossing #{self.crossing}")
            self.fig.canvas.draw_idle()
            return
        d = self.items[self.i]
        members = member_data(self.scene, d)
        hw = start_headways(members)
        draw_queue(self.ax_queue, self.scene, d, members)
        draw_time_distance(self.ax_td, self.scene, d, members)
        draw_headways(self.ax_hw, hw)
        self.table_ax.text(0, 1, table_text(d, members, hw, self.i, len(self.items)), va="top",
                           family="monospace", fontsize=8)
        self.fig.suptitle(f"Discharge {d['discharge_id']} · part {d['part']} · "
                          f"{d['trigger_kind']} · crossing "
                          f"#{d['crossing_id']} (area {d['area']}) · release t = "
                          f"{d['release_time']:.2f} s · {d['n_queue']} in queue", fontsize=11)
        self.fig.canvas.draw_idle()


# --------------------------------------------------
# MAIN
# --------------------------------------------------


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", default="16", metavar="P",
                   help=f"the snapshot_events.py run to show: a part (16), a range (14-18) "
                        f"or 'all' (1-{N_PARTS}); default 16")
    p.add_argument("--min-bikes", type=int, default=DISCHARGE_MIN_BIKES, metavar="N",
                   help=f"only discharges with at least N cyclists in the queue "
                        f"(default {DISCHARGE_MIN_BIKES}: all)")
    p.add_argument("--kind", choices=KINDS, default="queue",
                   help="discharges shown first (default queue; the menu switches)")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes the discharges were detected for (default 3: cyclists)")
    args = p.parse_args()
    try:
        parts = parse_parts(args.part)
    except ValueError as e:
        p.error(f"--part {e}")
    label = parts_label(parts)

    discharges, queues, passes, positions = read_results(label, args.part)
    if discharges.empty:
        raise SystemExit(f"{label}_discharges.csv has no discharges")
    shown = discharges[discharges["n_queue"] >= args.min_bikes]
    print(f"{label}: {len(discharges)} discharges "
          f"({(discharges['trigger_kind'] == 'queue').sum()} queue, "
          f"{(discharges['trigger_kind'] == 'rolling').sum()} rolling); "
          f"{len(shown)} with at least {args.min_bikes} bike(s) in the queue")
    scene = Scene(parts, args.categories, discharges, queues, passes, positions)
    viewer = DischargeViewer(scene, args.kind, args.min_bikes)    # keep it alive while the window is open
    plt.show()
    del viewer


if __name__ == "__main__":
    main()
