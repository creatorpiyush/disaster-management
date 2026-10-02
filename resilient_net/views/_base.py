"""launch(): runs a view's animation in a window, or headless for export / selftest."""
import os
import time

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from ..widgets import apply_theme

FIG_DIR = "figures"


def launch(build, name, test_frames=0, interval=45, exercise=True, dpi=150):
    # build() -> (fig, step, controls). With test_frames set: no window, just run, poke controls, save png
    apply_theme()
    fig, step, ctl = build()
    if test_frames:
        for i in range(test_frames):
            step(i)
        if ctl is not None and exercise:
            _exercise(ctl, step)
        os.makedirs(FIG_DIR, exist_ok=True)
        path = os.path.join(FIG_DIR, f"{name}.png")
        fig.savefig(path, dpi=dpi)
        plt.close(fig)
        return path
    if os.environ.get("RN_LITE") == "1":  # --lite
        interval = max(interval, 110)
    pace = _Pacer(interval)
    anim = FuncAnimation(fig, pace.wrap(step), interval=interval, cache_frame_data=False, blit=False)
    pace.anim = anim
    fig.canvas.mpl_connect("draw_event", pace.drawn)
    fig._keep_alive = anim  # otherwise the animation gets garbage collected and just stops

    def stop(_event=None):
        try:
            anim.event_source.stop()
        except Exception:
            pass

    fig.canvas.mpl_connect("close_event", stop)
    try:
        # pumping the event loop by hand instead of plt.show(block=True) because on macOS
        # that sometimes never returns after closing the window and the menu hangs
        plt.show(block=False)
        while plt.fignum_exists(fig.number):
            fig.canvas.start_event_loop(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        plt.close("all")
        _finish_closing(fig)
    return None


class _Pacer:
    """Frame timer = ~1.6x the measured frame cost, so slow laptops still have time left for the sliders."""

    def __init__(self, base):
        self.base, self.anim, self.t0, self.cost = base, None, None, base / 1000

    def wrap(self, step):
        def run(frame):
            self.t0 = time.perf_counter()
            return step(frame)
        return run

    def drawn(self, _event):
        if self.t0 is None or self.anim is None:
            return
        self.cost = 0.8 * self.cost + 0.2 * (time.perf_counter() - self.t0)
        self.t0 = None
        want = int(min(600, max(self.base, 1600 * self.cost)))
        src = self.anim.event_source
        if src is not None and abs(want - src.interval) > 0.2 * src.interval:
            src.interval = want


def _finish_closing(fig, rounds=10):
    # give the OS a moment to actually close the window before we block on input(),
    # otherwise macOS leaves a frozen ghost window with the spinning beachball
    for _ in range(rounds):
        try:
            fig.canvas.flush_events()
        except Exception:
            break
        time.sleep(0.02)


def _exercise(ctl, step):
    # push every slider to both ends, click every radio/checkbox, then reset
    for s in ctl.sliders.values():
        for v in (s.valmin, s.valmax):
            s.set_val(v)
            step(0)
    for k, r in ctl.radios.items():
        for t in r.labels:
            ctl.set(k, t.get_text())
            step(0)
    for c, _ in ctl.checks.values():
        for i in range(len(c.labels)):
            c.set_active(i)
            step(0)
            c.set_active(i)
    ctl.reset()
    for i in range(3):
        step(i)
