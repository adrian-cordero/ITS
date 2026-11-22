"""
Interactive playback of precomputed frames: road users as dots, a time
slider, a play/pause button and hover tooltips.

    player = AnimationPlayer(fig, ax, frames)
    player.on_frame(CountGraph(ax_graph, counts, categories))   # optional extras
    player.show()

Anything that should change with the frame (a graph marker, legend
counts, highlighted areas) is a callback taking the current Frame.
"""

import matplotlib.pyplot as plt
import mplcursors
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider

from its.config import CATEGORY_NAMES
from its.viz.styles import OVERLAY_TEXT_ZORDER, ROAD_USER_ZORDER


class AnimationPlayer:

    def __init__(self, fig, ax, frames, interval=50, point_size=20):
        if not frames:
            raise ValueError("No frames to play: is the data empty after filtering?")

        self.fig = fig
        self.ax = ax
        self.frames = frames
        self.current = 0
        self.playing = False
        self._callbacks = []

        self.scatter = ax.scatter([], [], s=point_size, zorder=ROAD_USER_ZORDER)

        # ax.text is cheaper to update every frame than ax.set_title
        self.time_text = ax.text(
            0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=11,
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
            zorder=OVERLAY_TEXT_ZORDER,
        )

        self._setup_hover()
        self._setup_controls()

        # keep a reference, or the animation is garbage-collected
        self.animation = FuncAnimation(
            fig, self._step, interval=interval, blit=False, cache_frame_data=False
        )

    # ------------------------------------------------

    def on_frame(self, callback):
        """Call `callback(frame)` every time a frame is drawn."""
        self._callbacks.append(callback)
        return callback

    def draw_frame(self, idx):
        self.current = idx
        frame = self.frames[idx]

        self.scatter.set_offsets(frame.offsets)
        self.scatter.set_facecolors(frame.colors)
        self.time_text.set_text(f"Time = {frame.timestamp:.2f}")

        for callback in self._callbacks:
            callback(frame)

    def show(self, start=0):
        self.slider.set_val(start)   # draws the frame
        plt.show()

    def save(self, path, frame=0, **savefig_kwargs):
        """Save a still of one frame instead of opening a window."""
        self.slider.set_val(frame)
        self.fig.savefig(path, **savefig_kwargs)

    # ------------------------------------------------

    def _setup_hover(self):
        cursor = mplcursors.cursor(self.scatter, hover=True)

        @cursor.connect("add")
        def _on_add(sel):
            frame = self.frames[self.current]
            i = sel.index
            if i < len(frame.ids):
                cat = frame.categories[i]
                sel.annotation.set_text(
                    f"ID: {frame.ids[i]}\n"
                    f"Category: {CATEGORY_NAMES.get(cat, cat)}"
                )
            sel.annotation.get_bbox_patch().set(fc="white", alpha=0.9)

        self._cursor = cursor

    def _setup_controls(self):
        slider_ax = self.fig.add_axes([0.15, 0.08, 0.6, 0.03])
        self.slider = Slider(slider_ax, "Time", 0, max(len(self.frames) - 1, 1),
                             valinit=0, valstep=1)
        self.slider.on_changed(self._slider_changed)

        button_ax = self.fig.add_axes([0.8, 0.06, 0.1, 0.05])
        self.button = Button(button_ax, "Play")
        self.button.on_clicked(self._toggle_play)

    def _slider_changed(self, val):
        self.draw_frame(min(int(val), len(self.frames) - 1))
        self.fig.canvas.draw_idle()

    def _toggle_play(self, _event):
        self.playing = not self.playing
        self.button.label.set_text("Pause" if self.playing else "Play")

    def _step(self, _):
        if not self.playing:
            return
        nxt = (self.current + 1) % len(self.frames)
        self.draw_frame(nxt)
        # move the slider without triggering _slider_changed again
        self.slider.eventson = False
        self.slider.set_val(nxt)
        self.slider.eventson = True
