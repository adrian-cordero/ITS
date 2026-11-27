"""
Animated playback of the trajectories on the site map.

    python code/scripts/animate.py                              # all parts, cyclists only
    python code/scripts/animate.py --part 16                     # one part (or 14-18)
    python code/scripts/animate.py --categories 2 3              # pedestrians + cyclists
    python code/scripts/animate.py --part 3 --categories 1 2 3
    python code/scripts/animate.py --layers waiting_areas system
    python code/scripts/animate.py --no-graph --satellite
    python code/scripts/animate.py --save frame.png --frame 500  # still image, no window
    python code/scripts/animate.py --lines 9                     # 9 lines where a crossing has no own N
    python code/scripts/animate.py --margin 25                   # 25 m around the crossings
    python code/scripts/animate.py --full                        # all trajectories
    python code/scripts/animate.py --speed 4                     # 4x real time

While playing, the - / + buttons (or keys) halve and double the speed;
left / right step one frame, page up / page down jump one minute.

The parts follow each other in time, so --part all (the default) or a
range is one timeline. Cyclists come from the combined bicycle file (about
1 s for the whole recording); other categories are read from the 22 part
files, which takes longer and needs a few GB for all parts.

The map opens on the waiting areas used by a crossing (and the crossing
bands) plus ANIMATE_MARGIN metres on every side (config.py); with no
crossings picked yet, on all waiting areas.

Zoom with the mouse wheel or the toolbar (magnifier, pan arrows, house = reset).

Crossing areas (start/end edge + N lines in between) are drawn when
define_crossings.py has made crossing_areas.gpkg.

Category codes: 1 car, 2 pedestrian, 3 bicycle, 4 trailer, 5 motorcycle,
6 truck, 7 bus, 8 scooter, 9 streetcar.
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt

from its.crossings import crossing_areas_path, crossing_extent, load_crossing_lines
from its.config import (
    ANIMATE_MARGIN, BICYCLE, CROSSING_LAYER, CROSSING_LINES, CROSSING_WIDTH,
    DEFAULT_PROJECT_LAYERS, MAPS_DIR, N_PARTS, PLOT_CRS, PROJECT_LAYERS,
)
from its.maps import load_basemap, load_project_layers
from its.trajectories import counts_per_time, load_parts, parse_parts, parts_label
from its.viz.crossings import draw_crossing_lines
from its.viz.basemap import (
    add_satellite, draw_basemap, draw_project_layers, set_extent, set_extent_to_areas,
)
from its.viz.count_graph import CountGraph
from its.viz.frames import precompute_frames
from its.viz.interaction import enable_scroll_zoom
from its.viz.legends import LiveCategoryCounts, category_legend, layer_legend
from its.viz.player import AnimationPlayer


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", type=parse_parts, default="all", metavar="PARTS",
                   help=f"a part (16), a range (14-18) or all (default; parts 1-{N_PARTS})")
    p.add_argument("--categories", type=int, nargs="+", default=[BICYCLE],
                   help="category codes to show (default 3: cyclists only)")
    p.add_argument("--layers", nargs="*", default=list(DEFAULT_PROJECT_LAYERS),
                   choices=sorted(PROJECT_LAYERS), metavar="LAYER",
                   help=f"project layers to draw (default: {' '.join(DEFAULT_PROJECT_LAYERS)}; "
                        f"available: {', '.join(sorted(PROJECT_LAYERS))}). "
                        "Pass --layers with nothing after it for none.")
    p.add_argument("--lines", type=int, default=CROSSING_LINES, metavar="N",
                   help=f"lines between the start and end edge, for crossings without "
                        f"their own number (set in define_crossings.py) "
                        f"(default {CROSSING_LINES}; 0 = only the edges)")
    p.add_argument("--no-crossings", action="store_true",
                   help="don't draw crossing-area edges and lines")
    p.add_argument("--margin", type=float, default=ANIMATE_MARGIN, metavar="M",
                   help=f"metres shown around the crossings' waiting areas "
                        f"(default {ANIMATE_MARGIN:g})")
    p.add_argument("--full", action="store_true",
                   help="frame all trajectories instead of the crossings' waiting areas")
    p.add_argument("--no-graph", action="store_true", help="hide the count-over-time graph")
    p.add_argument("--satellite", action="store_true", help="satellite background (needs internet)")
    p.add_argument("--speed", type=float, default=1.0, metavar="X",
                   help="playback speed as a multiple of real time (default 1; "
                        "e.g. 0.5 = half speed, 10 = ten times faster)")
    p.add_argument("--interval", type=int, default=50,
                   help="ms between screen updates (default 50); speed doesn't depend on it")
    p.add_argument("--save", metavar="FILE", help="save one frame as an image instead of playing")
    p.add_argument("--frame", type=int, default=0, help="frame to start at / save (default 0)")
    return p.parse_args()


def main():
    args = parse_args()

    # ---------------- data
    # only the columns playback needs: cyclists then come from the combined file
    df = load_parts(args.part, categories=args.categories,
                    columns=["timestamp", "category", "track_id"])
    frames = precompute_frames(df)
    counts = None if args.no_graph else counts_per_time(df)
    print(f"{parts_label(args.part)}: {len(df):,} rows, {len(frames):,} frames")
    print(f"Map layers from: {MAPS_DIR}")

    # ---------------- figure
    if args.no_graph:
        fig, ax = plt.subplots(figsize=(12, 12))
        ax_graph = None
    else:
        fig, (ax, ax_graph) = plt.subplots(1, 2, figsize=(18, 10),
                                           gridspec_kw={"width_ratios": [2, 1]})
    plt.subplots_adjust(bottom=0.2)

    # ---------------- map
    if args.full:
        set_extent(ax, df)
    else:
        try:
            set_extent_to_areas(ax, crossing_extent(CROSSING_LAYER, CROSSING_WIDTH),
                                args.margin)
        except Exception as e:  # missing or unreadable layer: fall back to the old view
            print(f"Can't frame on {CROSSING_LAYER} ({e}); showing all trajectories")
            set_extent(ax, df)
    del df   # frames and counts hold what playback needs
    draw_basemap(ax, load_basemap())
    layer_handles = draw_project_layers(ax, load_project_layers(args.layers))
    if not args.no_crossings:
        if crossing_areas_path(CROSSING_LAYER).exists():
            lines = load_crossing_lines(CROSSING_LAYER, max(args.lines, 0)).to_crs(PLOT_CRS)
            layer_handles += draw_crossing_lines(ax, lines)
        else:
            print(f"No crossing areas yet ({crossing_areas_path(CROSSING_LAYER).name} missing): "
                  "run code/scripts/define_crossings.py")
    if args.satellite:
        add_satellite(ax)

    enable_scroll_zoom(ax)
    legend = category_legend(ax, args.categories)
    layer_legend(ax, layer_handles, keep=legend)

    # ---------------- playback
    player = AnimationPlayer(fig, ax, frames, interval=args.interval, speed=args.speed)
    player.on_frame(LiveCategoryCounts(legend, args.categories))
    if ax_graph is not None:
        player.on_frame(CountGraph(ax_graph, counts, args.categories))

    if args.save:
        player.save(args.save, frame=args.frame, dpi=120)
        print(f"Saved {args.save}")
    else:
        player.show(start=args.frame)


if __name__ == "__main__":
    main()
