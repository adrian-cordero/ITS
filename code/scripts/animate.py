"""
Animated playback of one trajectory part on the site map.

    python code/scripts/animate.py                              # part 16, pedestrians + cyclists
    python code/scripts/animate.py --part 3 --categories 1 2 3
    python code/scripts/animate.py --layers waiting_areas system
    python code/scripts/animate.py --no-graph --satellite
    python code/scripts/animate.py --save frame.png --frame 500  # still image, no window

Category codes: 1 car, 2 pedestrian, 3 bicycle, 4 trailer, 5 motorcycle,
6 truck, 7 bus, 8 scooter, 9 streetcar.
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt

from its.config import (
    BICYCLE, DEFAULT_PROJECT_LAYERS, MAPS_DIR, N_PARTS, PEDESTRIAN, PROJECT_LAYERS,
)
from its.maps import load_basemap, load_project_layers
from its.trajectories import counts_per_time, load_part
from its.viz.basemap import add_satellite, draw_basemap, draw_project_layers, set_extent
from its.viz.count_graph import CountGraph
from its.viz.frames import precompute_frames
from its.viz.legends import LiveCategoryCounts, category_legend, layer_legend
from its.viz.player import AnimationPlayer


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", type=int, default=16, choices=range(1, N_PARTS + 1),
                   metavar="N", help=f"trajectory part 1-{N_PARTS} (default 16)")
    p.add_argument("--categories", type=int, nargs="+", default=[PEDESTRIAN, BICYCLE],
                   help="category codes to show (default 2 3)")
    p.add_argument("--layers", nargs="*", default=list(DEFAULT_PROJECT_LAYERS),
                   choices=sorted(PROJECT_LAYERS), metavar="LAYER",
                   help=f"project layers to draw (default: {' '.join(DEFAULT_PROJECT_LAYERS)}; "
                        f"available: {', '.join(sorted(PROJECT_LAYERS))}). "
                        "Pass --layers with nothing after it for none.")
    p.add_argument("--no-graph", action="store_true", help="hide the count-over-time graph")
    p.add_argument("--satellite", action="store_true", help="satellite background (needs internet)")
    p.add_argument("--interval", type=int, default=50, help="ms between frames (default 50)")
    p.add_argument("--save", metavar="FILE", help="save one frame as an image instead of playing")
    p.add_argument("--frame", type=int, default=0, help="frame to start at / save (default 0)")
    return p.parse_args()


def main():
    args = parse_args()

    # ---------------- data
    df = load_part(args.part, categories=args.categories)
    frames = precompute_frames(df)
    print(f"Part {args.part}: {len(df):,} rows, {len(frames):,} frames")
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
    set_extent(ax, df)
    draw_basemap(ax, load_basemap())
    layer_handles = draw_project_layers(ax, load_project_layers(args.layers))
    if args.satellite:
        add_satellite(ax)

    legend = category_legend(ax, args.categories)
    layer_legend(ax, layer_handles, keep=legend)

    # ---------------- playback
    player = AnimationPlayer(fig, ax, frames, interval=args.interval)
    player.on_frame(LiveCategoryCounts(legend, args.categories))
    if ax_graph is not None:
        player.on_frame(CountGraph(ax_graph, counts_per_time(df), args.categories))

    if args.save:
        player.save(args.save, frame=args.frame, dpi=120)
        print(f"Saved {args.save}")
    else:
        player.show(start=args.frame)


if __name__ == "__main__":
    main()
