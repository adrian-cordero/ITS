"""
Queue measures per waiting area.

Method (from the original pseudocode in Main.py), for each time step
and waiting area:

    a = queue area
    b = number of cyclists in the area
    jam density = b / a

    c = time the last cyclist exits the waiting area
    d = time the first cyclist exits the waiting area
    N = cyclists passing the exit line between d and c
    discharge rate = N / (c - d)

The crossing and event detection behind these lives in
its.analysis.crossings.
"""


def jam_density(count, area):
    """Cyclists per unit area.

    Careful: areas measured in Web Mercator (PLOT_CRS, the `x`/`y`
    columns) are about 2.2x too large at Munich's latitude (scale factor
    1/cos(48.17°)²). For true m², measure areas on translation_x/y (UTM).
    """
    return count / area if area > 0 else float("nan")


def discharge_rate(n_discharged, t_first_exit, t_last_exit):
    """Cyclists per second leaving the waiting area."""
    duration = t_last_exit - t_first_exit
    return n_discharged / duration if duration > 0 else float("nan")
