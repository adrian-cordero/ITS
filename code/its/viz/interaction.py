"""Mouse/keyboard helpers for interactive windows."""

import threading

import matplotlib.pyplot as plt


def enable_scroll_zoom(ax, factor=1.25):
    """
    Zoom `ax` with the mouse wheel, around the mouse pointer. Works next
    to the toolbar's zoom/pan buttons (the house button resets the view).
    """
    def on_scroll(event):
        if event.inaxes is not ax or event.xdata is None:
            return
        scale = 1 / factor if event.button == "up" else factor
        x, y = event.xdata, event.ydata
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(x - (x - x0) * scale, x + (x1 - x) * scale)
        ax.set_ylim(y - (y - y0) * scale, y + (y1 - y) * scale)
        ax.figure.canvas.draw_idle()

    return ax.figure.canvas.mpl_connect("scroll_event", on_scroll)


def responsive_input(prompt=""):
    """
    input() that keeps matplotlib windows responsive (zoom, pan, scroll)
    while waiting for the answer in the terminal.
    """
    result = {}

    def read():
        try:
            result["value"] = input(prompt)
        except BaseException as exc:      # EOFError, KeyboardInterrupt
            result["error"] = exc

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    while reader.is_alive():
        if plt.get_fignums():
            plt.pause(0.05)               # lets the window handle mouse/keys
        else:
            reader.join(0.05)

    if "error" in result:
        raise result["error"]
    return result["value"]
