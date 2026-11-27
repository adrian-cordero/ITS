"""
Cyclists inside the waiting areas over time, as an interactive
matplotlib window.

    python code/scripts/plot_occupancy.py                    # all parts, areas 4 5 6 7 ticked
    python code/scripts/plot_occupancy.py --part 16           # one part (or a range: 14-18)
    python code/scripts/plot_occupancy.py --areas 0 1 4       # tick other areas at the start
    python code/scripts/plot_occupancy.py --part 3 --categories 3 8
    python code/scripts/plot_occupancy.py --save occupancy.png

In the window:
    checkboxes (left)    show / hide each waiting area
    mouse over the plot  counts of the shown areas at that moment
    mouse wheel/toolbar  zoom and pan (house = back to the full view)

Each cyclist (object id) enters an area at most once and leaves it at
most once: its stay runs from its first to its last timestep inside,
and it counts as inside for that whole stay, even if its centre point
wobbles over the edge.

The panel under the checkboxes lists, for each shown area: the most
cyclists at once, the average, the share of time with at least one
cyclist, and the number of entries and exits. The terminal prints the
same counts, plus how many were already inside when the recording
started or were still inside when it ended.
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import CheckButtons

from its.analysis.occupancy import area_events, count_in_areas, event_counts
from its.crossings import load_source
from its.config import BICYCLE, CATEGORY_NAMES, DEFAULT_OCCUPANCY_AREAS, MAPS_DIR, N_PARTS
from its.trajectories import (
    add_metric_coordinates, frame_timestamps, load_parts, parse_parts, parts_label,
)
from its.viz.interaction import enable_scroll_zoom

AREA_LAYER = "waiting_areas"


def compute(parts, categories):
    timestamps = frame_timestamps(parts)           # every frame, also those without cyclists
    df = add_metric_coordinates(load_parts(parts, categories=categories,
                                           columns=["timestamp", "category", "track_id"]))
    areas = load_source(AREA_LAYER).geometry
    occupancy = count_in_areas(df, areas, timestamps)
    counts = event_counts(area_events(df, areas), len(areas)).set_index("area")
    return occupancy, counts, len(areas)


class OccupancyPlot:

    def __init__(self, occupancy, counts, n_areas, shown, title):
        self.occ = occupancy
        self.counts = counts
        self.t = occupancy["timestamp"].to_numpy()
        self.colors = {i: plt.cm.tab10(i % 10) for i in range(n_areas)}

        self.fig = plt.figure(figsize=(14, 7))
        self.ax = self.fig.add_axes([0.25, 0.1, 0.72, 0.8])
        check_ax = self.fig.add_axes([0.02, 0.45, 0.17, 0.45])
        self.stats_ax = self.fig.add_axes([0.02, 0.05, 0.2, 0.36])
        self.stats_ax.axis("off")

        self.lines = {}
        for i in range(n_areas):
            (line,) = self.ax.step(self.t, occupancy[f"area_{i}"], where="post",
                                   color=self.colors[i], linewidth=1.2, label=f"Area {i}")
            line.set_visible(i in shown)
            self.lines[i] = line

        self.ax.set_title(title)
        self.ax.set_xlabel("Recording time (s)")
        self.ax.set_ylabel("Cyclists inside (centre point)")
        self.ax.set_xlim(self.t[0], self.t[-1])
        self.ax.grid(True, alpha=0.3)
        self.ax.yaxis.get_major_locator().set_params(integer=True)

        labels = [f"Area {i}" for i in range(n_areas)]
        self.check = CheckButtons(check_ax, labels, [i in shown for i in range(n_areas)],
                                  label_props={"color": [self.colors[i] for i in range(n_areas)]})
        check_ax.set_title("Waiting areas", fontsize=10, loc="left")
        self.check.on_clicked(self.on_toggle)

        self.cursor = self.ax.axvline(self.t[0], color="grey", linewidth=0.8, visible=False)
        self.readout = self.ax.text(0.01, 0.98, "", transform=self.ax.transAxes, va="top",
                                    fontsize=9, family="monospace",
                                    bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"))
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_move)
        enable_scroll_zoom(self.ax)
        self.refresh()

    def shown(self):
        return [i for i, line in self.lines.items() if line.get_visible()]

    def on_toggle(self, label):
        i = int(label.split()[-1])
        self.lines[i].set_visible(not self.lines[i].get_visible())
        self.refresh()

    def refresh(self):
        shown = self.shown()
        top = max([self.occ[f"area_{i}"].max() for i in shown] + [1])
        self.ax.set_ylim(0, top + 0.5)
        handles = [self.lines[i] for i in shown]
        if handles:
            self.ax.legend(handles=handles, loc="upper right")
        elif self.ax.get_legend():
            self.ax.get_legend().remove()

        rows = [f"{'area':<5}{'max':>4}{'avg':>6}{'occ%':>6}{'in':>5}{'out':>5}"]
        for i in shown:
            v = self.occ[f"area_{i}"].to_numpy()
            c = self.counts.loc[i]
            rows.append(f"{i:<5}{v.max():>4}{v.mean():>6.2f}{100 * (v > 0).mean():>6.1f}"
                        f"{c['entries']:>5}{c['exits']:>5}")
        if not shown:
            rows.append("(no area selected)")
        self.stats_ax.clear()
        self.stats_ax.axis("off")
        self.stats_ax.text(0, 1, "\n".join(rows), va="top", family="monospace", fontsize=9)
        self.readout.set_text("")
        self.cursor.set_visible(False)
        self.fig.canvas.draw_idle()

    def on_move(self, event):
        if event.inaxes is not self.ax or event.xdata is None:
            return
        k = int(np.clip(np.searchsorted(self.t, event.xdata, side="right") - 1, 0, len(self.t) - 1))
        shown = self.shown()
        parts = [f"t = {self.t[k]:.2f} s"] + [f"area {i}: {self.occ[f'area_{i}'].iloc[k]}"
                                              for i in shown]
        self.readout.set_text("\n".join(parts))
        self.cursor.set_xdata([self.t[k], self.t[k]])
        self.cursor.set_visible(True)
        self.fig.canvas.draw_idle()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", type=parse_parts, default="all", metavar="P",
                   help=f"a part (16), a range (14-18) or all (1-{N_PARTS}; default)")
    p.add_argument("--areas", type=int, nargs="+", default=None,
                   help=f"waiting areas ticked at the start "
                        f"(default {' '.join(map(str, DEFAULT_OCCUPANCY_AREAS))}, "
                        f"or all areas if the layer has none of those)")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes to count (default 3: cyclists)")
    p.add_argument("--save", metavar="FILE", help="save the figure instead of opening a window")
    args = p.parse_args()

    occupancy, counts, n_areas = compute(args.part, args.categories)
    if args.areas is None:
        args.areas = ([a for a in DEFAULT_OCCUPANCY_AREAS if 0 <= a < n_areas]
                      or list(range(n_areas)))
    bad = [a for a in args.areas if not 0 <= a < n_areas]
    if bad:
        raise SystemExit(f"No waiting area(s) {bad}: they are numbered 0-{n_areas - 1}")

    who = ", ".join(CATEGORY_NAMES[c] for c in args.categories)
    label = parts_label(args.part)
    print(f"{label}: {len(occupancy)} timesteps, {n_areas} waiting areas (from {MAPS_DIR})")
    print("Events per area (each cyclist enters and leaves at most once):")
    print(counts.to_string())
    plot = OccupancyPlot(occupancy, counts, n_areas, set(args.areas),
                         f"Inside the waiting areas, {label} ({who})")
    if args.save:
        plot.fig.savefig(args.save, dpi=130)
        print(f"Saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
