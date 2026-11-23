"""
Manage crossings: bands of constant width W from a start edge on one
polygon to an end edge on another polygon of the same layer
(CROSSING_LAYER in config.py, e.g. the waiting areas). The result is
saved as a new GeoPackage.

    python code/scripts/pick_edges.py                       # menu, W from config
    python code/scripts/pick_edges.py --width 4             # default W = 4 m
    python code/scripts/pick_edges.py --rebuild --width 4   # no window: rebuild from saved picks
    python code/scripts/pick_edges.py --reset               # delete all crossings, start over

A window shows the street map with the areas numbered (orange) and the
crossings numbered (#0, #1, ...). The terminal shows the crossings and
a menu:

    a        add a crossing
    e <#>    edit crossing # (current answers in brackets: Enter keeps them)
    d <#>    delete crossing #
    r <#>    reverse crossing #: swap start and end
    n <#> <N>  give crossing # its own number of lines N ("n 2 -" = back to default)
    w <#> <W>  give crossing # its own width W in metres ("w 2 -" = back to default)
    clear    delete all crossings and start over from #0
    q        save and quit

Before deleting everything (clear or --reset), the current picks are
copied to MAPS_DIR/edge_picks_backup_<date>-<time>.csv (a new file each
time). To undo, copy that file over edge_picks.csv and run with --rebuild.

Zoom with the mouse wheel or the toolbar (magnifier = zoom to a
rectangle, arrows = pan, house = back to the automatic view); the
window stays usable while the terminal waits for an answer.

Adding or editing asks for the start area, the start edge, the end area,
the end edge, the number of lines and the width (Enter = the default:
CROSSING_LINES, and --width or CROSSING_WIDTH); type c at any of these
to cancel. Any number of
crossings can start or end at the same area. Every change is saved
straight away.

Saves:
    MAPS_DIR/edge_picks.csv                  the picks (reused by --rebuild)
    MAPS_DIR/crossing_areas.gpkg             layers crossing_areas (bands) and crossing_edges
"""

import argparse
import shutil
from datetime import datetime

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt

from its.areas import (
    Crossing, build_crossings, crossing_geometry, crossing_length, crossing_lines,
    effective_lines, effective_width, load_picks, load_source, next_crossing_id, polygon_edges,
    reversed_crossing, save_crossings, save_picks,
)
from its.config import (
    CROSSING_LAYER, CROSSING_LINES, CROSSING_WIDTH, EDGE_PICKS_FILE, MAPS_DIR, METRIC_CRS,
)
from its.maps import load_basemap
from its.viz.basemap import draw_basemap
from its.viz.interaction import enable_scroll_zoom, responsive_input
from its.viz.styles import CROSSING_LINE_STYLES

START_COLOR = CROSSING_LINE_STYLES["start"]["color"]
END_COLOR = CROSSING_LINE_STYLES["end"]["color"]
BAND_COLOR = "tab:blue"

CONTEXT_MARGIN = 40.0   # metres of surroundings shown around the area(s) (at least)
CONTEXT_FACTOR = 1.5    # ...or this many times their size, if larger

MENU = ("a = add   e <#> = edit   d <#> = delete   r <#> = reverse   "
        "n <#> <N> = lines   w <#> <W> = width   clear = delete all   q = save and quit")
BACKUP_PREFIX = "edge_picks_backup"   # + _<date>-<time>.csv, one per reset


class Cancel(Exception):
    """The user typed c while adding or editing a crossing."""


def save_all(layer, source, picks, width, quiet=False):
    picks_path = save_picks(layer, source, picks)
    bands, edges = build_crossings(source, picks, width)
    gpkg_path = save_crossings(layer, bands, edges, source.attrs["file_crs"])
    if not quiet:
        print(f"Saved {len(picks)} crossing(s) (default W = {width} m):")
        print(f"  {picks_path}")
        print(f"  {gpkg_path}")


def clear_all(layer, source, picks, width, ask=input):
    """
    After a yes/no question, back up the picks file and delete all of this
    layer's crossings (in `picks` and on disk). Returns True if cleared.
    """
    if not picks:
        print("  There are no crossings to delete.")
        return False
    answer = ask(f"  Delete all {len(picks)} crossings of {layer}? [y/N]: ").strip().lower()
    if answer != "y":
        print("  Nothing deleted.")
        return False

    picks_path = MAPS_DIR / EDGE_PICKS_FILE
    if picks_path.exists():
        backup = MAPS_DIR / f"{BACKUP_PREFIX}_{datetime.now():%Y%m%d-%H%M%S}.csv"
        shutil.copyfile(picks_path, backup)
        print(f"  Backup: {backup}")
    picks.clear()
    save_all(layer, source, picks, width, quiet=True)
    print("  -> all crossings deleted; new ones start at #0")
    return True


def describe_lines(c):
    if c.lines is None:
        return f"N = {CROSSING_LINES} (default)"
    return f"N = {c.lines}"


def describe_width(c, default):
    w = effective_width(c, default)
    return f"W = {w:g} m" + (" (default)" if c.width is None else "")


def describe(source, c, width):
    _, s_line, e_line, angle = crossing_geometry(source, c, width)
    return (f"area {c.start_area} edge {c.start_edge} -> area {c.end_area} edge {c.end_edge}   "
            f"(L = {crossing_length(s_line, e_line):.1f} m, {describe_width(c, width)}, "
            f"{describe_lines(c)}, end edge turned {angle:.1f}°)")


def print_crossings(source, picks, width):
    print(f"\nCrossings ({len(picks)}):")
    if not picks:
        print("  none yet")
    for cid, pick in sorted(picks.items()):
        print(f"  #{cid:<3} {describe(source, pick, width)}")
    print(MENU)


# --------------------------------------------------
# WINDOW
# --------------------------------------------------


class AreaView:
    """Street map and numbered areas drawn once; crossings and the current pick on top."""

    def __init__(self, layer, source, width):
        self.source = source
        self.width = width
        self.layer = layer

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(11, 11))
        ax = self.ax

        print("Loading map context...")
        draw_basemap(ax, load_basemap(crs=METRIC_CRS))

        source.plot(ax=ax, facecolor="orange", edgecolor="darkorange", alpha=0.3,
                    linewidth=1, zorder=5)
        for area_id, poly in enumerate(source.geometry):
            p = poly.representative_point()
            ax.annotate(str(area_id), (p.x, p.y), ha="center", va="center", fontsize=12,
                        fontweight="bold", color="darkorange", zorder=6,
                        bbox=dict(boxstyle="round", fc="white", ec="darkorange", alpha=0.8))

        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        enable_scroll_zoom(ax)
        self.artists = []

    def _clear(self):
        for a in self.artists:
            a.remove()
        self.artists = []

    def _draw_crossings(self, picks, highlight=None, faint=False):
        ax = self.ax
        for cid, pick in picks.items():
            if cid == highlight:
                continue
            band, s_line, e_line, _ = crossing_geometry(self.source, pick, self.width)
            alpha = 0.15 if faint else 0.35
            self.artists += ax.fill(*band.exterior.xy, color=BAND_COLOR, alpha=alpha, zorder=7)
            self.artists += ax.plot(*s_line.xy, color=START_COLOR, linewidth=2.5,
                                    alpha=0.5 if faint else 1, zorder=8)
            self.artists += ax.plot(*e_line.xy, color=END_COLOR, linewidth=2.5,
                                    alpha=0.5 if faint else 1, zorder=8)
            for line in crossing_lines(s_line, e_line, effective_lines(pick, CROSSING_LINES)):
                self.artists += ax.plot(*line.xy, color="black", linewidth=0.8,
                                        alpha=0.4 if faint else 1, zorder=8)
            c = band.centroid
            self.artists.append(ax.annotate(
                f"#{cid}", (c.x, c.y), ha="center", va="center", fontsize=10,
                fontweight="bold", color=BAND_COLOR, zorder=9, alpha=0.6 if faint else 1,
                bbox=dict(boxstyle="round", fc="white", ec=BAND_COLOR,
                          alpha=0.5 if faint else 0.9)))

    def _draw_polygon(self, poly, picked, color):
        """Highlight a polygon and number its edges (picked edge drawn thick)."""
        ax = self.ax
        self.artists += ax.fill(*poly.exterior.xy, color=color, alpha=0.15, zorder=10)
        for k, e in enumerate(polygon_edges(poly)):
            lw, c = (4, color) if k == picked else (2, "black")
            self.artists += ax.plot(e[:, 0], e[:, 1], color=c, linewidth=lw,
                                    solid_capstyle="round", zorder=11)
            self.artists.append(ax.annotate(
                str(k), e.mean(axis=0), ha="center", va="center", fontsize=12,
                fontweight="bold", zorder=13,
                bbox=dict(boxstyle="circle", fc="white", ec=color, lw=2)))

    def _zoom(self, polys, factor):
        minx = min(p.bounds[0] for p in polys)
        miny = min(p.bounds[1] for p in polys)
        maxx = max(p.bounds[2] for p in polys)
        maxy = max(p.bounds[3] for p in polys)
        pad = max(CONTEXT_MARGIN, factor * max(maxx - minx, maxy - miny))
        self.ax.set_xlim(minx - pad, maxx + pad)
        self.ax.set_ylim(miny - pad, maxy + pad)

    def _refresh(self, title, status=""):
        self.ax.set_title(title, fontsize=12)
        self.ax.set_xlabel(status, fontsize=11)
        self.fig.canvas.draw_idle()
        plt.pause(0.05)

    def overview(self, picks):
        """All areas and all crossings."""
        self._clear()
        self._draw_crossings(picks)
        self._zoom(list(self.source.geometry), 0.1)
        self._refresh(f"{self.layer}: {len(picks)} crossing(s)")

    def focus(self, picks, cid, start_area=None, start=None, end_area=None, end=None,
              lines=None, width=None):
        """One crossing being added/edited; the others drawn faint."""
        self._clear()
        self._draw_crossings(picks, highlight=cid, faint=True)
        shown = []

        if start_area is not None:
            shown.append(self.source.geometry.iloc[start_area])
            self._draw_polygon(shown[-1], start, START_COLOR)
        if end_area is not None:
            shown.append(self.source.geometry.iloc[end_area])
            self._draw_polygon(shown[-1], end, END_COLOR)

        status = ""
        if None not in (start_area, start, end_area, end):
            pick = Crossing(start_area, start, end_area, end, lines, width)
            band, s_line, e_line, _ = crossing_geometry(self.source, pick, self.width)
            self.artists += self.ax.fill(*band.exterior.xy, color=BAND_COLOR, alpha=0.3,
                                         zorder=12)
            self.artists += self.ax.plot(*band.exterior.xy, "--", color=BAND_COLOR,
                                         linewidth=2, zorder=12)
            for line in crossing_lines(s_line, e_line, effective_lines(pick, CROSSING_LINES)):
                self.artists += self.ax.plot(*line.xy, color="black", linewidth=1, zorder=12)
            status = describe(self.source, pick, self.width)

        if shown:
            self._zoom(shown, CONTEXT_FACTOR if len(shown) == 1 else 0.3)
        else:
            self._zoom(list(self.source.geometry), 0.1)
        self._refresh(f"{self.layer}: crossing #{cid}", status)


# --------------------------------------------------
# TERMINAL
# --------------------------------------------------


def ask_number(prompt, valid, current, error):
    """Ask for a number in `valid`; Enter keeps `current`; c cancels."""
    shown = f" [{current}]" if current is not None else ""
    while True:
        answer = responsive_input(f"  {prompt}{shown}: ").strip().lower()
        if answer == "" and current is not None:
            return current
        if answer == "c":
            raise Cancel
        if answer.isdigit() and int(answer) in valid:
            return int(answer)
        print(f"    {error} (c = cancel)")


def ask_lines(current):
    """
    Ask for the number of lines N. Enter keeps `current` (None = default),
    '-' goes back to the default, c cancels. Returns an int or None.
    """
    shown = f"[{current}]" if current is not None else f"[default {CROSSING_LINES}]"
    while True:
        answer = responsive_input(f"  Lines between the edges {shown} "
                                  "(- = default): ").strip().lower()
        if answer == "":
            return current
        if answer == "c":
            raise Cancel
        if answer == "-":
            return None
        if answer.isdigit():
            return int(answer)
        print("    Type a number (0 or more), - for the default, or c to cancel.")


def parse_width(text):
    """A positive width in metres from '3.5' or '3,5', else None."""
    try:
        w = float(text.replace(",", "."))
    except ValueError:
        return None
    return w if w > 0 else None


def ask_width(current, default):
    """
    Ask for the width W. Enter keeps `current` (None = default), '-' goes
    back to the default, c cancels. Returns a float or None.
    """
    shown = f"[{current:g}]" if current is not None else f"[default {default:g}]"
    while True:
        answer = responsive_input(f"  Width in metres {shown} (- = default): ").strip().lower()
        if answer == "":
            return current
        if answer == "c":
            raise Cancel
        if answer == "-":
            return None
        w = parse_width(answer)
        if w is not None:
            return w
        print("    Type a width in metres above 0 (e.g. 3.5), - for the default, or c to cancel.")


def ask_crossing(view, source, picks, cid, current=None):
    """Ask for start area, start edge, end area, end edge, lines, width. Raises Cancel."""
    cur = current or Crossing(None, None, None, None, None, None)
    areas = range(len(source))
    area_list = f"0-{len(source) - 1}"

    view.focus(picks, cid)
    start_area = ask_number(f"Start area ({area_list})", areas, cur[0],
                            f"Type an area number {area_list}.")

    n = len(polygon_edges(source.geometry.iloc[start_area]))
    view.focus(picks, cid, start_area)
    keep = cur[1] if start_area == cur[0] else None
    start = ask_number(f"Start edge on area {start_area} (0-{n - 1})", range(n), keep,
                       f"Type an edge number 0-{n - 1}.")

    view.focus(picks, cid, start_area, start)
    others = [a for a in areas if a != start_area]
    keep = cur[2] if cur[2] in others else None
    end_area = ask_number(f"End area ({', '.join(map(str, others))})", others, keep,
                          f"Type the number of another area (not {start_area}).")

    n = len(polygon_edges(source.geometry.iloc[end_area]))
    view.focus(picks, cid, start_area, start, end_area)
    keep = cur[3] if end_area == cur[2] else None
    end = ask_number(f"End edge on area {end_area} (0-{n - 1})", range(n), keep,
                     f"Type an edge number 0-{n - 1}.")

    view.focus(picks, cid, start_area, start, end_area, end, cur.lines, cur.width)
    lines = ask_lines(cur.lines)

    view.focus(picks, cid, start_area, start, end_area, end, lines, cur.width)
    width = ask_width(cur.width, view.width)

    view.focus(picks, cid, start_area, start, end_area, end, lines, width)
    return Crossing(start_area, start, end_area, end, lines, width)


def parse_command(line, picks):
    """
    (cmd, crossing_id or None, value or None), or None after printing why not.
    cmd is 'a', 'e', 'd', 'r', 'n', 'w', 'clear' or 'q'; value is N for 'n'
    or W for 'w' (None = back to the default).
    """
    parts = line.strip().lower().split()
    if not parts:
        return None
    cmd, args = parts[0], parts[1:]
    if cmd in ("a", "q", "clear") and not args:
        return cmd, None, None
    if (cmd in ("e", "d", "r") and len(args) == 1) or (cmd in ("n", "w") and len(args) == 2):
        cid = args[0].lstrip("#")
        if not (cid.isdigit() and int(cid) in picks):
            print(f"    No crossing #{cid}.")
            return None
        value = None
        if cmd == "n":
            if args[1] == "-":
                value = None
            elif args[1].isdigit():
                value = int(args[1])
            else:
                print("    Usage: n <#> <N>, e.g. n 2 6 (or n 2 - for the default).")
                return None
        if cmd == "w" and args[1] != "-":
            value = parse_width(args[1])
            if value is None:
                print("    Usage: w <#> <W>, e.g. w 2 3.5 (or w 2 - for the default).")
                return None
        return cmd, int(cid), value
    print(f"    Not understood. {MENU}")
    return None


def menu(layer, source, picks, width):
    view = AreaView(layer, source, width)

    while True:
        view.overview(picks)
        print_crossings(source, picks, width)
        try:
            line = responsive_input("> ")
        except EOFError:
            line = "q"
        command = parse_command(line, picks)
        if command is None:
            continue
        cmd, cid, value = command

        if cmd == "q":
            break
        if cmd == "clear":
            clear_all(layer, source, picks, width, ask=responsive_input)
            continue

        try:
            if cmd == "a":
                cid = next_crossing_id(picks)
                print(f"New crossing #{cid}:")
                picks[cid] = ask_crossing(view, source, picks, cid)
                print(f"  -> #{cid} added")
            elif cmd == "e":
                print(f"Edit crossing #{cid} (Enter keeps the value in brackets):")
                picks[cid] = ask_crossing(view, source, picks, cid, current=picks[cid])
                print(f"  -> #{cid} changed")
            elif cmd == "d":
                print(f"  #{cid}: {describe(source, picks[cid], width)}")
                if responsive_input("  Delete it? [y/N]: ").strip().lower() == "y":
                    del picks[cid]
                    print(f"  -> #{cid} deleted")
                else:
                    continue
            elif cmd == "r":
                picks[cid] = reversed_crossing(picks[cid])
                print(f"  -> #{cid} reversed: {describe(source, picks[cid], width)}")
            elif cmd == "n":
                picks[cid] = picks[cid]._replace(lines=value)
                print(f"  -> #{cid}: {describe_lines(picks[cid])}")
            elif cmd == "w":
                picks[cid] = picks[cid]._replace(width=value)
                print(f"  -> #{cid}: {describe_width(picks[cid], width)}")
        except Cancel:
            print("  cancelled")
            continue

        save_all(layer, source, picks, width, quiet=True)

    save_all(layer, source, picks, width)
    plt.close(view.fig)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--layer", default=CROSSING_LAYER, help=f"default {CROSSING_LAYER}")
    p.add_argument("--width", type=float, default=CROSSING_WIDTH,
                   help=f"W in metres for crossings without their own width "
                        f"(default {CROSSING_WIDTH})")
    p.add_argument("--rebuild", action="store_true",
                   help="don't open a window: rebuild the GeoPackage from saved picks")
    p.add_argument("--reset", action="store_true",
                   help=f"delete all crossings first (asks; backup in {BACKUP_PREFIX}_<time>.csv)")
    args = p.parse_args()
    if args.reset and args.rebuild:
        p.error("--reset and --rebuild can't be combined")

    source = load_source(args.layer)
    picks = load_picks(args.layer, source)
    print(f"{args.layer}: {len(source)} areas, {len(picks)} crossing(s) "
          f"(from {MAPS_DIR})")

    if args.rebuild:
        if not picks:
            raise SystemExit("No saved picks: run without --rebuild first.")
        save_all(args.layer, source, picks, args.width)
        return

    if args.reset:
        clear_all(args.layer, source, picks, args.width)

    menu(args.layer, source, picks, args.width)


if __name__ == "__main__":
    main()
