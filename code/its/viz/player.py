"""
Interactive playback of precomputed frames: road users as dots, a time
slider, a play/pause button and hover tooltips.

    player = AnimationPlayer(fig, ax, frames)
    player.on_frame(CountGraph(ax_graph, counts, categories))   # optional extras
    player.show()

Speed is a multiple of real time (1 = real time). Above that, frames are
skipped rather than drawn faster, so high speeds don't depend on how fast
the window redraws. The - / + buttons (or the - and + keys) halve and
double it while playing. Left / right step one frame, page up / page down
jump one minute.

`frames` is anything with len() and [i] giving a Frame (see
its.viz.frames.Frames); a `timestamps` array on it is used when present.

Anything that should change with the frame (a graph marker, legend
counts, highlighted areas) is a callback taking the current Frame.
"""

import matplotlib.pyplot as plt
import mplcursors
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider

from its.config import CATEGORY_NAMES
from its.viz.styles import OVERLAY_TEXT_ZORDER, ROAD_USER_ZORDER


MIN_SPEED = 1 / 16
MAX_SPEED = 256
JUMP_SECONDS = 60   # page up / page down

# matplotlib uses left/right for view history; here they step frames
for _key in ("left", "right"):
    for _name in ("keymap.back", "keymap.forward"):
        if _key in plt.rcParams[_name]:
            plt.rcParams[_name] = [k for k in plt.rcParams[_name] if k != _key]


class AnimationPlayer:

    def __init__(self, fig, ax, frames, interval=50, point_size=20, speed=1.0):
        if len(frames) == 0:
            raise ValueError("No frames to play: is the data empty after filtering?")

        self.fig = fig
        self.ax = ax
        self.frames = frames
        self.current = 0
        self.playing = False
        self._callbacks = []

        # seconds of data between frames, and of wall time between ticks
        times = getattr(frames, "timestamps", None)
        if times is None:
            times = np.array([f.timestamp for f in frames])
        self.frame_dt = float(np.median(np.diff(times))) if len(times) > 1 else 1.0
        self.interval_s = interval / 1000
        self.speed = min(max(speed, MIN_SPEED), MAX_SPEED)
        self._carry = 0.0   # fraction of a frame left over from the last tick

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
        part = "" if frame.part is None else f"part {frame.part} · "
        self.time_text.set_text(f"{part}Time = {frame.timestamp:.2f} · speed ×{self.speed:g}")

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

        slower_ax = self.fig.add_axes([0.8, 0.005, 0.045, 0.045])
        faster_ax = self.fig.add_axes([0.855, 0.005, 0.045, 0.045])
        self.slower_button = Button(slower_ax, "−")
        self.faster_button = Button(faster_ax, "+")
        self.slower_button.on_clicked(lambda _e: self.set_speed(self.speed / 2))
        self.faster_button.on_clicked(lambda _e: self.set_speed(self.speed * 2))
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    def set_speed(self, speed):
        """Playback speed as a multiple of real time."""
        self.speed = min(max(speed, MIN_SPEED), MAX_SPEED)
        self._carry = 0.0
        self.draw_frame(self.current)   # refresh the speed shown
        self.fig.canvas.draw_idle()

    def _on_key(self, event):
        if event.key in ("+", "="):
            self.set_speed(self.speed * 2)
        elif event.key in ("-", "_"):
            self.set_speed(self.speed / 2)
        elif event.key in ("left", "right", "pageup", "pagedown"):
            jump = max(1, round(JUMP_SECONDS / self.frame_dt))
            step = {"left": -1, "right": 1, "pageup": jump, "pagedown": -jump}[event.key]
            self.slider.set_val(min(max(self.current + step, 0), len(self.frames) - 1))

    def _slider_changed(self, val):
        self.draw_frame(min(int(val), len(self.frames) - 1))
        self.fig.canvas.draw_idle()

    def _toggle_play(self, _event):
        self.playing = not self.playing
        self.button.label.set_text("Pause" if self.playing else "Play")

    def _step(self, _):
        if not self.playing:
            return
        # frames of data that fit in one tick at this speed (may be < 1)
        self._carry += self.speed * self.interval_s / self.frame_dt
        n = int(self._carry)
        if n == 0:
            return
        self._carry -= n
        nxt = (self.current + n) % len(self.frames)
        self.draw_frame(nxt)
        # move the slider without triggering _slider_changed again
        self.slider.eventson = False
        self.slider.set_val(nxt)
        self.slider.eventson = True
