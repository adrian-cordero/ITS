"""
Snapshot events in each crossing's start waiting area, with a photo of
the waiting area and of the whole intersection at the same moment.

    python code/scripts/snapshot_events.py                    # part 16, both event types
    python code/scripts/snapshot_events.py --view             # also open the viewer
    python code/scripts/snapshot_events.py --types stop --stop-speed 0.2 --stop-duration 1
    python code/scripts/snapshot_events.py --near 3 --context 60 --no-images

Event types:
    crossing  a cyclist crosses a start line forward (snapshot: its last
              timestep before the line)
    stop      a cyclist inside the start waiting area stays below
              --stop-speed m/s for at least --stop-duration s (snapshot:
              the start of the stop); only its first stop unless --every-stop

The defaults of every option below are set in code/its/config.py
(EVENT DETECTION); the options override them for one run.

At each snapshot, cyclists are "inside" the waiting area, "near" (within
--near m of its edge, not inside) or farther away.

Photos have two panels:
    left   the waiting area in its own frame (start line on the left, x =
           metres behind the start line, y = along it)
    right  the intersection, --context m around the area: every cyclist,
           coloured inside / near / farther, the --near zone dashed

Viewer: Previous / Next buttons (or left / right keys after clicking the
window), and a choice of all events, crossings only or stops only.

Writes to results/:
    part<P>_events.csv              one row per event
    part<P>_event_positions.csv     cyclists inside or near (and the trigger) per event
    snapshots/part<P>/<type>_NNN.png
"""

import argparse

import _bootstrap  # noqa: F401
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.widgets import Button, RadioButtons

from its.analysis.snapshots import snapshot_events
from its.areas import load_crossing_lines, load_source, parallel_path
from its.config import (
    BICYCLE, CROSSING_LAYER, EVERY_STOP, MAPS_DIR, METRIC_CRS, N_PARTS, NEAR_DISTANCE,
    RESULTS_DIR, SNAPSHOT_CONTEXT, SNAPSHOT_EVENT_TYPES, STOP_DURATION, STOP_SPEED,
)
from its.maps import load_basemap
from its.trajectories import add_metric_coordinates, load_part
from its.viz.basemap import draw_basemap
from its.viz.styles import CROSSING_LINE_STYLES

START_COLOR = CROSSING_LINE_STYLES["start"]["color"]
END_COLOR = CROSSING_LINE_STYLES["end"]["color"]
STATUS_STYLE = {
    "inside": dict(color="tab:blue", s=60, label="inside"),
    "near":   dict(color="tab:orange", s=60, label="near, not inside"),
    "far":    dict(color="0.55", s=25, label="farther away"),
}
TYPE_LABEL = {"crossing": "start-line crossing", "stop": "stop in waiting area"}


# --------------------------------------------------
# DATA
# --------------------------------------------------


def load_crossings(layer, only=None):
    """[{crossing_id, start_area, area_polygon, start_line, end_line}] in METRIC_CRS."""
    path = parallel_path(layer)
    if not path.exists():
        raise SystemExit(f"{path.name} not found: make crossings with pick_edges.py first")
    areas = load_source(layer)
    bands = gpd.read_file(path, layer=f"{layer}_parallel")
    start_area = dict(zip(bands["crossing_id"], bands["start_area"]))
    lines = load_crossing_lines(layer, 0)
    out = []
    for cid, grp in lines.groupby("crossing_id"):
        if only and cid not in only:
            continue
        by_role = dict(zip(grp["role"], grp.geometry))
        a = int(start_area[cid])
        out.append({"crossing_id": int(cid), "start_area": a,
                    "area_polygon": areas.geometry.iloc[a],
                    "start_line": by_role["start"], "end_line": by_role["end"]})
    return out


class Scene:
    """Everything the photos need besides the event tables."""

    def __init__(self, df, crossings, areas, near, context):
        self.by_time = {t: g for t, g in df.groupby("timestamp")}
        self.crossings = crossings
        self.areas = areas
        self.near = near
        self.context = context
        print("Loading the street map...")
        self.basemap = load_basemap(crs=METRIC_CRS)
        self.all_areas = load_source(CROSSING_LAYER)


# --------------------------------------------------
# DRAWING
# --------------------------------------------------


def title_of(ev):
    what = TYPE_LABEL[ev["type"]]
    where = f"area {ev['area']}"
    if ev["type"] == "crossing":
        where += f", crossing #{int(ev['crossing_id'])}"
    return (f"Event {ev['event_id']} · {what} · {where}\n"
            f"t = {ev['snapshot_time']:.2f} s · {ev['n_inside']} inside · {ev['n_near']} near")


def draw_local(ax, ev, pos, area):
    """Left panel: the waiting area in its local frame."""
    ax.clear()
    frame, polygon, crossing = area["frame"], area["polygon"], area["crossing"]
    px, py = frame.coords_local(polygon)
    ax.fill(px, py, color="orange", alpha=0.2, zorder=1)
    ax.plot(px, py, color="darkorange", linewidth=1.5, zorder=2)
    lx, ly = frame.coords_local(crossing["start_line"])
    ax.plot(lx, ly, color=START_COLOR, linewidth=3, zorder=3)

    for status in ("near", "inside"):
        p = pos[(pos["status"] == status) & ~pos["is_trigger"]]
        ax.scatter(p["x"], p["y"], edgecolor="white", zorder=5, **STATUS_STYLE[status])
    trig = pos[pos["is_trigger"]]
    ax.scatter(trig["x"], trig["y"], s=170, marker="*", color="tab:red", edgecolor="white", zorder=6)
    for r in pos.itertuples():
        ax.annotate(f"{r.track_id}\n({r.x:.1f}, {r.y:.1f})", (r.x, r.y), textcoords="offset points",
                    xytext=(6, 6), fontsize=7, zorder=7)

    xs = np.r_[px, lx, pos["x"].to_numpy()]
    ys = np.r_[py, ly, pos["y"].to_numpy()]
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
    area = scene.areas[ev["area"]]
    polygon = area["polygon"]
    draw_basemap(ax, scene.basemap)
    scene.all_areas.plot(ax=ax, facecolor="orange", edgecolor="darkorange", alpha=0.25, zorder=4)
    gpd.GeoSeries([polygon], crs=METRIC_CRS).plot(ax=ax, facecolor="none", edgecolor="darkorange",
                                                  linewidth=2.5, zorder=5)
    zone = polygon.buffer(scene.near)
    ax.plot(*zone.exterior.xy, "--", color="tab:orange", linewidth=1.2, zorder=5)
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
    ax.legend(handles=handles, loc="lower right", fontsize=8)


def draw_event(fig, ax_local, ax_map, ev, positions, scene):
    pos = positions[positions["event_id"] == ev["event_id"]]
    draw_local(ax_local, ev, pos, scene.areas[ev["area"]])
    draw_intersection(ax_map, ev, pos, scene)
    fig.suptitle(title_of(ev), fontsize=11)
    return pos


def save_images(events, positions, scene, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):                 # no photos left over from an earlier run
        old.unlink()
    fig, (ax_local, ax_map) = plt.subplots(1, 2, figsize=(15, 7.5))
    for ev in events.to_dict("records"):
        draw_event(fig, ax_local, ax_map, ev, positions, scene)
        fig.savefig(folder / f"{ev['type']}_{ev['event_id']:03d}.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------
# VIEWER
# --------------------------------------------------


class EventViewer:

    def __init__(self, events, positions, scene):
        self.all_events = events.to_dict("records")
        self.positions = positions
        self.scene = scene
        self.kind = "all"
        self.events = self.all_events
        self.i = 0
        for key in ("left", "right", "n", "b"):         # free them from matplotlib's toolbar keys
            for name, keys in plt.rcParams.items():
                if name.startswith("keymap.") and key in keys:
                    keys.remove(key)

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
        self.kind_radio = RadioButtons(self.fig.add_axes([0.30, 0.01, 0.16, 0.12]),
                                       ("all", "crossing", "stop"))
        self.kind_radio.on_clicked(self.set_kind)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.show()

    def set_kind(self, kind):
        self.kind = kind
        self.events = [e for e in self.all_events if kind == "all" or e["type"] == kind]
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

    def show(self):
        self.table_ax.clear()
        self.table_ax.axis("off")
        if not self.events:
            self.ax_local.clear()
            self.ax_map.clear()
            self.fig.suptitle(f"No {self.kind} events")
            self.fig.canvas.draw_idle()
            return
        ev = self.events[self.i]
        pos = draw_event(self.fig, self.ax_local, self.ax_map, ev, self.positions, self.scene)
        rows = [f"{self.kind} event {self.i + 1} of {len(self.events)}", "",
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
    p.add_argument("--part", type=int, default=16, choices=range(1, N_PARTS + 1), metavar="N",
                   help="trajectory part (default 16)")
    p.add_argument("--types", nargs="+", default=list(SNAPSHOT_EVENT_TYPES),
                   choices=["crossing", "stop"],
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
    p.add_argument("--context", type=float, default=SNAPSHOT_CONTEXT,
                   help=f"metres around the area shown on the intersection view "
                        f"(default {SNAPSHOT_CONTEXT:g})")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes (default 3: cyclists)")
    p.add_argument("--no-images", action="store_true", help="don't save the photos")
    p.add_argument("--view", action="store_true", help="open the viewer")
    args = p.parse_args()

    crossings = load_crossings(CROSSING_LAYER, args.crossings)
    df = load_part(args.part, categories=args.categories,
                   columns=["timestamp", "category", "track_id", "velocity_x", "velocity_y"])
    df = add_metric_coordinates(df)
    df["speed"] = np.hypot(df["velocity_x"], df["velocity_y"])

    events, positions, areas = snapshot_events(
        df, crossings, types=args.types, near=args.near, stop_speed=args.stop_speed,
        stop_duration=args.stop_duration, every_stop=args.every_stop)

    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / f"part{args.part}"
    events.to_csv(f"{stem}_events.csv", index=False)
    positions.to_csv(f"{stem}_event_positions.csv", index=False)

    print(f"Part {args.part}: {len(events)} events in start area(s) {sorted(areas)} "
          f"(maps from {MAPS_DIR})")
    print(f"  stop = below {args.stop_speed} m/s for {args.stop_duration} s; near = within {args.near} m")
    if len(events):
        print(events.groupby("type").size().to_string())
        print(events[["event_id", "type", "trigger_track", "snapshot_time", "n_inside",
                      "n_near"]].to_string(index=False))
    print(f"Wrote {stem}_events.csv and _event_positions.csv")

    if not len(events) or (args.no_images and not args.view):
        return
    scene = Scene(df, crossings, areas, args.near, args.context)
    if not args.no_images:
        folder = RESULTS_DIR / "snapshots" / f"part{args.part}"
        save_images(events, positions, scene, folder)
        print(f"Saved {len(events)} photos in {folder}")
    if args.view:
        viewer = EventViewer(events, positions, scene)    # keep it alive while the window is open
        plt.show()
        del viewer


if __name__ == "__main__":
    main()
