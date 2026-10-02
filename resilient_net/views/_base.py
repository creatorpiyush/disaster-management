"""Launch helper shared by all views: wires the animation timer and shows / saves the figure."""
import os

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from ..widgets import apply_theme

FIG_DIR = "figures"


def launch(build, name, test_frames=0, interval=45, exercise=True, dpi=150):
    """build() -> (fig, step, controls). step(frame) advances the live simulation.

    test_frames > 0 runs headless: steps the animation, exercises every control,
    and saves a PNG snapshot (used by `python main.py --export` and the self-test)."""
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
    anim = FuncAnimation(fig, step, interval=interval, cache_frame_data=False, blit=False)
    fig._keep_alive = anim
    plt.show()
    plt.close(fig)
    return None


def _exercise(ctl, step):
    """Move every slider to both ends, flip every radio, then reset (catches runtime errors)."""
    for k, s in ctl.sliders.items():
        for v in (s.valmin, s.valmax):
            s.set_val(v)
            step(0)
    for k, r in ctl.radios.items():
        for t in r.labels:
            ctl.set(k, t.get_text())
            step(0)
    for k, (c, _) in ctl.checks.items():
        for i in range(len(c.labels)):
            c.set_active(i)
            step(0)
            c.set_active(i)
    ctl.reset()
    for i in range(3):
        step(i)
