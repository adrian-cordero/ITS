"""
Static plot of every trajectory in one part, on the site map.

    python code/scripts/plot_trajectories.py --part 1
    python code/scripts/plot_trajectories.py --part 1 --categories 3 --save bikes.png
"""

import argparse

import _bootstrap  # noqa: F401
import matplotlib.pyplot as plt

from its.config import CATEGORY_NAMES, N_PARTS
from its.maps import load_basemap, load_project_layers
from its.trajectories import load_part
from its.viz.basemap import draw_basemap, draw_project_layers, set_extent
from its.viz.legends import layer_legend
from its.viz.static import plot_trajectories


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", type=int, default=1, choices=range(1, N_PARTS + 1), metavar="N")
    p.add_argument("--categories", type=int, nargs="+", default=None,
                   help="category codes to show (default: all)")
    p.add_argument("--layers", nargs="*", default=[], metavar="LAYER",
                   help="project layers to draw on top (default: none)")
    p.add_argument("--save", metavar="FILE", help="save to a file instead of showing")
    args = p.parse_args()

    df = load_part(args.part, categories=args.categories)

    fig, ax = plt.subplots(figsize=(12, 12))
    set_extent(ax, df)
    draw_basemap(ax, load_basemap())
    plot_trajectories(ax, df)
    layer_legend(ax, draw_project_layers(ax, load_project_layers(args.layers)))

    which = ", ".join(CATEGORY_NAMES[c] for c in args.categories) if args.categories else "all road users"
    ax.set_title(f"Trajectories, part {args.part} ({which})")

    if args.save:
        fig.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"Saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
