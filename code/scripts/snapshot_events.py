"""
Snapshot events in each crossing's start waiting area: where every
cyclist in or near the area is at that moment, with a viewer showing the
waiting area and the whole intersection.

    python code/scripts/snapshot_events.py                    # part 16, all event types
    python code/scripts/snapshot_events.py --part all         # the whole recording, one timeline
    python code/scripts/snapshot_events.py --part 14-18       # parts 14 to 18
    python code/scripts/snapshot_events.py --view             # also open the viewer
    python code/scripts/snapshot_events.py --types stop --stop-speed 0.2 --stop-duration 1
    python code/scripts/snapshot_events.py --near 3 --context 60 --view

Event types:
    start     a cyclist crosses a start line forward (snapshot: its last
              timestep before the line)
    stop      a cyclist inside the start waiting area stays below
              --stop-speed m/s for at least --stop-duration s (snapshot:
              the start of the stop); only its first stop unless --every-stop.
              Recorded once for every crossing starting in that area, each
              in that crossing's local frame.
    discharge a stopped queue released over the crossing's lines. Each
              start event is matched to its reference stop: the latest stop
              of the same crossing at or before it, at most --max-lag s
              earlier. The queue is the cyclists inside with speed below
              --stop-speed in that stop's snapshot. One discharge per
              reference stop, triggered by the first matched start event
              of a queue member (trigger_kind "queue"; earlier rolling
              starts by others in n_skipped_starts), or by the first
              matched start event if no member has one ("rolling"); for every queue member, its first forward pass of each
              line (start, --lines in between, end) after the stop.
              Needs start and stop, which are then detected too.

--part takes one part, a range or "all". A range is detected as one
timeline: a queue that stops in one part and leaves in the next is one
discharge. Event and discharge IDs run over the whole selection, and the
`part` column says which part each event (snapshot time) or discharge
(release time) falls in.

The defaults of every option below are set in code/its/config.py
(EVENT DETECTION); the options override them for one run.

At each snapshot, cyclists are "inside" the waiting area, "near" (within
--near m of its edge, not inside) or farther away.

The viewer has two panels and a table:
    left   the waiting area in its own frame (start line on the left, x =
           metres behind the start line, y = along it)
    right  the intersection, --context m around the area: every cyclist,
           coloured inside / near / farther, the --near zone dashed
    table  the cyclists inside or near: x, y, distance, speed
Menus: the crossing being analysed (or up / down keys) and the event type
(start-line crossings or stops; discharges are not shown yet). Previous / Next buttons (or left / right
keys after clicking the window) step through that crossing's events.
"Show" switches the waiting areas (waiting_areas.gpkg), the crossing
areas (crossing_areas.gpkg) and the lines across them (as many as in
animate.py) on and off on both panels.

Writes to results/, as <S> = part16, part14-18 or all:
    <S>_events.csv                  one row per event
    <S>_event_positions.csv         cyclists inside or near (and the trigger) per event,
                                    with their local x, y
    <S>_discharges.csv              one row per discharge
    <S>_discharge_queues.csv        per discharge: its queue members and their snapshot position
    <S>_discharge_passes.csv        per discharge, queue member and line: the pass time
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.widgets import Button, CheckButtons, RadioButtons

from its.analysis.discharge import discharge_events
from its.analysis.snapshots import TimeIndex, snapshot_events
from its.areas import load_crossing_lines, load_source
from its.config import (
    BICYCLE, CROSSING_LAYER, CROSSING_LINES, DISCHARGE_MAX_LAG, EVERY_STOP,
    MAPS_DIR, METRIC_CRS, N_PARTS,
    NEAR_DISTANCE, RESULTS_DIR, SNAPSHOT_CONTEXT, SNAPSHOT_EVENT_TYPES, STOP_DURATION, STOP_SPEED,
)
from its.maps import load_basemap
from its.trajectories import add_metric_coordinates, load_parts, parse_parts, part_of, parts_label
from its.viz.basemap import draw_basemap
from its.viz.events import (
    END_COLOR, LAYER_STYLE, MID_STYLE, START_COLOR, draw_local_crossing, draw_shape, free_keys,
    load_bands, load_crossings, load_mid_lines,
)

STATUS_STYLE = {
    "inside": dict(color="tab:blue", s=60, label="inside"),
    "near":   dict(color="tab:orange", s=60, label="near, not inside"),
    "far":    dict(color="0.55", s=25, label="farther away"),
}
TYPE_LABEL = {"start": "start-line crossing", "stop": "stop in waiting area"}


# --------------------------------------------------
# DATA
# --------------------------------------------------


class Scene:
    """Everything the photos need besides the event tables."""

    def __init__(self, df, crossings, frames, near, context):
        self.by_time = TimeIndex(df)
        self.crossings = crossings
        self.frames = frames
        self.near = near
        self.context = context
        print("Loading the street map...")
        self.basemap = load_basemap(crs=METRIC_CRS)
        self.all_areas = load_source(CROSSING_LAYER)
        self.bands = load_bands(CROSSING_LAYER)
        self.mid_lines = load_mid_lines(CROSSING_LAYER, CROSSING_LINES)    # N per crossing, as animate.py
        # switched in the viewer
        self.layers = {name: True for name in (*LAYER_STYLE, "crossing lines")}


# --------------------------------------------------
# DRAWING
# --------------------------------------------------


def title_of(ev):
    what = TYPE_LABEL[ev["type"]]
    where = f"part {ev['part']}, area {ev['area']}, crossing #{int(ev['crossing_id'])}"
    return (f"Event {ev['event_id']} · {what} · {where}\n"
            f"t = {ev['snapshot_time']:.2f} s · {ev['n_inside']} inside · {ev['n_near']} near")


def draw_local(ax, ev, pos, info, band, mid_lines, layers):
    """Left panel: the waiting area (and its crossing band) in the crossing's local frame."""
    ax.clear()
    frame, polygon, crossing = info["frame"], info["polygon"], info["crossing"]
    sx, sy = draw_local_crossing(ax, frame, polygon, crossing["start_line"], band, mid_lines,
                                 layers=layers)

    for status in ("near", "inside"):
        p = pos[(pos["status"] == status) & ~pos["is_trigger"]]
        ax.scatter(p["x"], p["y"], edgecolor="white", zorder=5, **STATUS_STYLE[status])
    trig = pos[pos["is_trigger"]]
    ax.scatter(trig["x"], trig["y"], s=170, marker="*", color="tab:red", edgecolor="white", zorder=6)
    for r in pos.itertuples():
        ax.annotate(f"{r.track_id}\n({r.x:.1f}, {r.y:.1f})", (r.x, r.y), textcoords="offset points",
                    xytext=(6, 6), fontsize=7, zorder=7)

    xs = np.concatenate([sx, pos["x"].to_numpy()])
    ys = np.concatenate([sy, pos["y"].to_numpy()])
    ax.set_xlim(min(0, xs.min()) - 1, max(frame.width, xs.max()) + 1)
    ax.set_ylim(min(0, ys.min()) - 1, max(frame.depth, ys.max()) + 1)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m, from the start line into the area)")
    ax.set_ylabel("y (m, along the start line)")
    ax.set_title("Waiting area (local frame)", fontsize=10)


def draw_intersection(ax, ev, pos, scene):
    """Right panel: the intersection around the area, every cyclist at that moment."""
    ax.clear()
    polygon = scene.frames[ev["crossing_id"]]["polygon"]
    draw_basemap(ax, scene.basemap)
    if scene.layers["waiting areas"]:
        for i, poly in enumerate(scene.all_areas.geometry):
            draw_shape(ax, *poly.exterior.xy, "waiting areas", strong=i == ev["area"], zorder=4)
    if scene.layers["crossing areas"]:
        for cid, band in scene.bands.items():
            draw_shape(ax, *band.exterior.xy, "crossing areas", strong=cid == ev["crossing_id"],
                       zorder=4)
    zone = polygon.buffer(scene.near)
    ax.plot(*zone.exterior.xy, "--", color="tab:orange", linewidth=1.2, zorder=5)
    if scene.layers["crossing lines"]:
        for line in (g for gs in scene.mid_lines.values() for g in gs):
            ax.plot(*line.xy, zorder=6, **MID_STYLE)
    for c in scene.crossings:
        ax.plot(*c["start_line"].xy, color=START_COLOR, linewidth=2.5, zorder=6)
        ax.plot(*c["end_line"].xy, color=END_COLOR, linewidth=2.5, zorder=6)

    here = scene.by_time[ev["snapshot_time"]]
    status = dict(zip(pos["track_id"], pos["status"]))
    s = here["track_id"].map(status).fillna("far")
    for st in ("far", "near", "inside"):
        p = here[s.to_numpy() == st]
        ax.scatter(p["utm_x"], p["utm_y"], edgecolor="white", zorder=8, **STATUS_STYLE[st])
    trig = here[here["track_id"] == ev["trigger_track"]]
    ax.scatter(trig["utm_x"], trig["utm_y"], s=200, marker="*", color="tab:red",
               edgecolor="white", zorder=9)

    minx, miny, maxx, maxy = polygon.bounds
    ax.set_xlim(minx - scene.context, maxx + scene.context)
    ax.set_ylim(miny - scene.context, maxy + scene.context)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Intersection, {scene.context:g} m around area {ev['area']} "
                 f"(dashed: {scene.near:g} m zone)", fontsize=10)

    handles = [Line2D([], [], marker="o", linestyle="", color=STATUS_STYLE[k]["color"],
                      label=STATUS_STYLE[k]["label"]) for k in ("inside", "near", "far")]
    handles.append(Line2D([], [], marker="*", linestyle="", color="tab:red", markersize=12,
                          label="trigger"))
    handles += [Line2D([], [], color=st["edgecolor"], linestyle=st["linestyle"], label=name)
                for name, st in LAYER_STYLE.items() if scene.layers[name]]
    if scene.layers["crossing lines"]:
        handles.append(Line2D([], [], label="crossing lines", **MID_STYLE))
    ax.legend(handles=handles, loc="lower right", fontsize=8)


def draw_event(fig, ax_local, ax_map, ev, positions, scene):
    pos = positions[positions["event_id"] == ev["event_id"]]
    draw_local(ax_local, ev, pos, scene.frames[ev["crossing_id"]],
               scene.bands.get(int(ev["crossing_id"])),
               scene.mid_lines.get(int(ev["crossing_id"]), []), scene.layers)
    draw_intersection(ax_map, ev, pos, scene)
    fig.suptitle(title_of(ev), fontsize=11)
    return pos


# --------------------------------------------------
# VIEWER
# --------------------------------------------------


class EventViewer:

    def __init__(self, events, positions, scene):
        self.all_events = events.to_dict("records")
        self.positions = positions
        self.scene = scene
        self.kind = "start"
        # every crossing, also those without events: menu label -> crossing_id
        self.crossing_labels = {f"#{cid} (area {f['area']})": cid
                                for cid, f in sorted(scene.frames.items())}
        self.crossing = next(iter(self.crossing_labels.values()))
        self.events = []
        self.i = 0
        free_keys("left", "right", "up", "down", "n", "b")

        self.fig = plt.figure(figsize=(17, 8.5))
        self.ax_local = self.fig.add_axes([0.04, 0.17, 0.30, 0.70])
        self.ax_map = self.fig.add_axes([0.36, 0.17, 0.40, 0.70])
        self.table_ax = self.fig.add_axes([0.78, 0.17, 0.21, 0.70])
        self.table_ax.axis("off")

        # keep references to the widgets, or they stop responding
        self.prev_button = Button(self.fig.add_axes([0.04, 0.04, 0.1, 0.06]), "◀ Previous")
        self.next_button = Button(self.fig.add_axes([0.15, 0.04, 0.1, 0.06]), "Next ▶")
        self.prev_button.on_clicked(lambda _e: self.step(-1))
        self.next_button.on_clicked(lambda _e: self.step(+1))
        kind_ax = self.fig.add_axes([0.29, 0.01, 0.14, 0.12])
        kind_ax.set_title("Event type", fontsize=9, loc="left")
        self.kind_radio = RadioButtons(kind_ax, ("start", "stop"))
        self.kind_radio.on_clicked(self.set_kind)

        n = len(self.crossing_labels)
        crossing_ax = self.fig.add_axes([0.46, 0.01, 0.18, min(0.12, 0.03 * n + 0.02)])
        crossing_ax.set_title("Crossing", fontsize=9, loc="left")
        self.crossing_radio = RadioButtons(crossing_ax, tuple(self.crossing_labels))
        self.crossing_radio.on_clicked(self.set_crossing)

        layers_ax = self.fig.add_axes([0.67, 0.01, 0.14, 0.12])
        layers_ax.set_title("Show", fontsize=9, loc="left")
        self.layer_checks = CheckButtons(layers_ax, tuple(scene.layers),
                                         tuple(scene.layers.values()))
        self.layer_checks.on_clicked(self.toggle_layer)

        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.refilter()

    def set_kind(self, kind):
        self.kind = kind
        self.refilter()

    def set_crossing(self, label):
        self.crossing = self.crossing_labels[label]
        self.refilter()

    def toggle_layer(self, name):
        self.scene.layers[name] = not self.scene.layers[name]
        self.show()                                    # same event, redrawn

    def refilter(self):
        """Events of the chosen crossing and type, back to the first one."""
        self.events = [e for e in self.all_events
                       if e["crossing_id"] == self.crossing and e["type"] == self.kind]
        self.i = 0
        self.show()

    def step(self, delta):
        if self.events:
            self.i = (self.i + delta) % len(self.events)
        self.show()

    def on_key(self, event):
        if event.key in ("right", "n"):
            self.step(+1)
        elif event.key in ("left", "b"):
            self.step(-1)
        elif event.key in ("up", "down"):                # previous / next crossing in the menu
            labels = list(self.crossing_labels)
            j = labels.index(self.crossing_radio.value_selected)
            self.crossing_radio.set_active((j + (1 if event.key == "down" else -1)) % len(labels))

    def show(self):
        self.table_ax.clear()
        self.table_ax.axis("off")
        if not self.events:
            self.ax_local.clear()
            self.ax_map.clear()
            self.fig.suptitle(f"No {self.kind} events for crossing #{self.crossing}")
            self.fig.canvas.draw_idle()
            return
        ev = self.events[self.i]
        pos = draw_event(self.fig, self.ax_local, self.ax_map, ev, self.positions, self.scene)
        rows = [f"crossing #{self.crossing}: {self.kind} event {self.i + 1} of {len(self.events)}", "",
                f"{'track':>6} {'x':>6} {'y':>6} {'dist':>5} {'v':>5}  status"]
        for r in pos.sort_values(["status", "x"]).itertuples():
            note = r.status + (" *" if r.is_trigger else "")
            rows.append(f"{r.track_id:>6} {r.x:>6.1f} {r.y:>6.1f} {r.distance_to_area:>5.1f} "
                        f"{r.speed:>5.2f}  {note}")
        rows += ["", "x, y: local frame (m)", "dist: to the area edge (m)",
                 "v: speed (m/s)   * trigger"]
        self.table_ax.text(0, 1, "\n".join(rows), va="top", family="monospace", fontsize=8)
        self.fig.canvas.draw_idle()


# --------------------------------------------------
# MAIN
# --------------------------------------------------


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", default="16", metavar="P",
                   help=f"a part (16), a range (14-18) or 'all' (1-{N_PARTS}); default 16")
    p.add_argument("--types", nargs="+", default=list(SNAPSHOT_EVENT_TYPES),
                   choices=["start", "stop", "discharge"],
                   help=f"event types to detect (default {' '.join(SNAPSHOT_EVENT_TYPES)})")
    p.add_argument("--crossings", type=int, nargs="+", metavar="ID",
                   help="only these crossings and their start areas (default: all)")
    p.add_argument("--near", type=float, default=NEAR_DISTANCE,
                   help=f"metres from the area's edge that count as near (default {NEAR_DISTANCE:g})")
    p.add_argument("--stop-speed", type=float, default=STOP_SPEED,
                   help=f"speed below which a cyclist counts as stopped, m/s (default {STOP_SPEED:g})")
    p.add_argument("--stop-duration", type=float, default=STOP_DURATION,
                   help=f"how long the speed must stay below it, s (default {STOP_DURATION:g})")
    p.add_argument("--every-stop", action=argparse.BooleanOptionalAction, default=EVERY_STOP,
                   help="record every stop, not only each cyclist's first per area")
    p.add_argument("--max-lag", type=float, default=DISCHARGE_MAX_LAG,
                   help=f"longest time from a reference stop to its start event, s "
                        f"(default {DISCHARGE_MAX_LAG:g})")
    p.add_argument("--lines", type=int, default=CROSSING_LINES,
                   help=f"lines between start and end line for discharges, unless a crossing "
                        f"has its own (default {CROSSING_LINES})")
    p.add_argument("--context", type=float, default=SNAPSHOT_CONTEXT,
                   help=f"metres around the area shown on the intersection view "
                        f"(default {SNAPSHOT_CONTEXT:g})")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes (default 3: cyclists)")
    p.add_argument("--view", action="store_true", help="open the viewer")
    args = p.parse_args()
    try:
        parts = parse_parts(args.part)
    except ValueError as e:
        p.error(f"--part {e}")

    crossings = load_crossings(CROSSING_LAYER, args.crossings)
    df = load_parts(parts, categories=args.categories,
                    columns=["timestamp", "category", "track_id", "velocity_x", "velocity_y"])
    df = add_metric_coordinates(df)
    df["speed"] = np.hypot(df["velocity_x"], df["velocity_y"])

    types = set(args.types) | ({"start", "stop"} if "discharge" in args.types else set())
    events, positions, frames = snapshot_events(
        df, crossings, types=types, near=args.near, stop_speed=args.stop_speed,
        stop_duration=args.stop_duration, every_stop=args.every_stop)
    events.insert(1, "part", part_of(df, events["snapshot_time"]))

    RESULTS_DIR.mkdir(exist_ok=True)
    label = parts_label(parts)
    stem = RESULTS_DIR / label
    many = len(parts) > 1
    events.to_csv(f"{stem}_events.csv", index=False)
    positions.to_csv(f"{stem}_event_positions.csv", index=False)

    used = ", ".join(f"#{cid} (area {f['area']})" for cid, f in sorted(frames.items()))
    print(f"{label}: {len(events)} events for crossing(s) {used} (maps from {MAPS_DIR})")
    print(f"  stop = below {args.stop_speed} m/s for {args.stop_duration} s; near = within {args.near} m")
    if len(events):
        print(events.groupby(["crossing_id", "type"]).size().to_string())
        if not many:                      # the full list is too long for a range
            print(events[["event_id", "type", "crossing_id", "trigger_track", "snapshot_time",
                          "n_inside", "n_near"]].to_string(index=False))
    print(f"Wrote {stem}_events.csv and _event_positions.csv")

    if "discharge" in args.types:
        lines = load_crossing_lines(CROSSING_LAYER, args.lines)
        lines = lines[lines["crossing_id"].isin(frames)]
        discharges, queues, passes = discharge_events(df, events, positions, lines, args.stop_speed,
                                              args.max_lag)
        discharges.insert(1, "part", part_of(df, discharges["release_time"]))
        discharges.to_csv(f"{stem}_discharges.csv", index=False)
        queues.to_csv(f"{stem}_discharge_queues.csv", index=False)
        passes.to_csv(f"{stem}_discharge_passes.csv", index=False)
        print(f"{len(discharges)} discharges (reference stop at most {args.max_lag:g} s "
              f"before the start event):")
        if len(discharges) and many:
            print(discharges.groupby(["crossing_id", "trigger_kind"]).size().to_string())
            print("Queue size (n_queue): number of discharges")
            print(discharges["n_queue"].value_counts().sort_index().to_string())
        elif len(discharges):
            print(discharges.drop(columns=["area", "stop_time"]).to_string(index=False))
        print(f"Wrote {stem}_discharges.csv, _discharge_queues.csv and _discharge_passes.csv "
              f"(view them with view_discharges.py --part {args.part})")

    if not len(events) or not args.view:
        return
    scene = Scene(df, crossings, frames, args.near, args.context)
    viewer = EventViewer(events, positions, scene)    # keep it alive while the window is open
    plt.show()
    del viewer


if __name__ == "__main__":
    main()
