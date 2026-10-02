"""matplotlib theme + the slider/button panel shared by all views (red dot = default, R = reset)."""
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons, CheckButtons

from . import config as C

RED_DOT = "#ff3b30"


def apply_theme():
    mpl.rcParams.update({
        "figure.facecolor": C.BG, "axes.facecolor": C.PANEL, "savefig.facecolor": C.BG,
        "axes.edgecolor": C.GRID, "axes.labelcolor": C.INK2, "axes.titlecolor": C.INK,
        "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 8,
        "axes.labelsize": 8.5, "axes.grid": True, "grid.color": C.GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": C.MUTED, "ytick.color": C.MUTED, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "text.color": C.INK, "legend.fontsize": 7.5, "legend.frameon": False, "legend.labelcolor": C.INK2,
        "lines.linewidth": 2.0, "axes.axisbelow": True, "font.size": 9, "font.family": "DejaVu Sans",
        "toolbar": "toolbar2",
    })
    for key in ("keymap.home", "keymap.back"):  # we want R for reset
        try:
            mpl.rcParams[key] = [k for k in mpl.rcParams[key] if k not in ("r", "R")]
        except KeyError:
            pass


def fit_to_screen(fig):
    # on small screens (1366x768 laptops) just drop the dpi so the whole layout scales down together
    sw = sh = None
    try:
        win = fig.canvas.manager.window
        if hasattr(win, "winfo_screenwidth"):  # tk
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        elif hasattr(win, "screen"):  # qt
            g = win.screen().availableGeometry()
            sw, sh = g.width(), g.height()
    except Exception:
        return
    if not sw:
        return
    w, h = fig.get_size_inches()
    dpi = min(fig.dpi, 0.97 * sw / w, 0.88 * sh / h)  # 0.88 so the taskbar doesn't cover it
    if dpi < fig.dpi:
        fig.set_dpi(dpi)
        fig.set_size_inches(w, h, forward=True)


def new_figure(title, subtitle="", tag="", size=(16, 9.4)):
    fig = plt.figure(figsize=size)
    fit_to_screen(fig)
    try:
        fig.canvas.manager.set_window_title(title)
    except Exception:
        pass
    fig.text(0.015, 0.975, title, fontsize=15, fontweight="bold", color=C.INK, va="top")
    if subtitle:
        fig.text(0.015, 0.943, subtitle, fontsize=9.5, color=C.INK2, va="top")
    if tag:
        fig.text(0.985, 0.972, f"  {tag}  ", fontsize=9, color=C.BG, va="top", ha="right", fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.35", fc=C.INK2, ec="none"))
    fig.text(0.985, 0.006, ",  ".join(f"{n} ({r})" for n, r in C.MEMBERS), ha="right", va="bottom",
             fontsize=7, color=C.MUTED)
    fig.text(0.015, 0.006, "red dot = default (click to snap back)   R = reset   space = pause",
             ha="left", va="bottom", fontsize=7, color=C.MUTED)
    return fig


def readout(ax):
    # turns an axes into a little monospace text box, returns the Text so views can set_text() it
    ax.set_axis_off()
    ax.add_patch(mpl.patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.03",
                                            transform=ax.transAxes, fc="#202124", ec=C.GRID, lw=1))
    return ax.text(0.05, 0.95, "", transform=ax.transAxes, va="top", ha="left", family="monospace",
                   fontsize=8.3, color=C.INK, linespacing=1.45)


def status_colour(ok):
    return C.COL["good"] if ok >= 0.7 else C.COL["warn"] if ok >= 0.4 else C.COL["bad"]


class Controls:
    """Sliders / radios / checkboxes at the bottom of a figure. Calls on_change(values) on any change."""

    def __init__(self, fig, on_change, rect=(0.015, 0.035, 0.70, 0.17), cols=2, rows=None, row_h=0.026):
        self.fig, self.on_change, self.rect, self.cols, self.row_h = fig, on_change, rect, cols, row_h
        self.rows = rows
        self.sliders, self.radios, self.checks, self.defaults, self.values = {}, {}, {}, {}, {}
        self._n = 0
        self._mute = False
        self._buttons = []  # matplotlib only keeps weak refs to callbacks, so hold on to the buttons
        x, y, w, h = rect
        bg = fig.add_axes([x, y, w, max(h, 1e-3)], zorder=-1)
        bg.set_axis_off()
        if h > 0.01:
            bg.add_patch(mpl.patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.04",
                                                    transform=bg.transAxes, fc="#1d1f22", ec=C.GRID, lw=1))
        fig.canvas.mpl_connect("key_press_event", self._key)

    def slider(self, key, label, vmin, vmax, init, step=None, fmt="%.1f", color=None):
        x, y, w, h = self.rect
        rows = self.rows or max(1, int((h - 0.02) // self.row_h))
        col, row = divmod(self._n, rows)
        self._n += 1
        cw = w / self.cols
        sx = x + col * cw + 0.105
        sy = y + h - 0.016 - (row + 1) * self.row_h
        ax = self.fig.add_axes([sx, sy, cw - 0.165, self.row_h * 0.55], facecolor=C.PANEL)
        kw = dict(valinit=init, valfmt=fmt, color=color or "#5a8fd8", track_color="#34363a")
        if step is not None:
            kw["valstep"] = step
        try:
            s = Slider(ax, label, vmin, vmax, initcolor="none",
                       handle_style=dict(facecolor=C.INK, edgecolor="#5a5a5a", size=11), **kw)
        except TypeError:  # matplotlib < 3.5
            s = Slider(ax, label, vmin, vmax, **kw)
        s.label.set_color(C.INK2)
        s.label.set_fontsize(8)
        s.label.set_x(-0.035)
        s.valtext.set_color(C.INK)
        s.valtext.set_fontsize(8)
        s.valtext.set_family("monospace")
        ax.plot([init], [0.5], "o", color=RED_DOT, ms=7.5, mec="white", mew=1.0, zorder=20, clip_on=False)
        tol = 0.025 * (vmax - vmin)

        def snap(ev, s=s, ax=ax, init=init, tol=tol):
            if ev.inaxes is ax and ev.xdata is not None and abs(ev.xdata - init) <= tol and s.val != init:
                s.set_val(init)

        self.fig.canvas.mpl_connect("button_press_event", snap)
        self.fig.canvas.mpl_connect("button_release_event", snap)
        s.on_changed(lambda v, k=key: self._changed(k, v))
        self.sliders[key], self.defaults[key], self.values[key] = s, init, init
        return s

    def radio(self, key, title, options, init, rect):
        ax = self.fig.add_axes(rect, facecolor="#1d1f22")
        ax.set_title(title, fontsize=8.5, color=C.INK2, loc="left", pad=3)
        for sp in ax.spines.values():
            sp.set_color(C.GRID)
        idx = options.index(init)
        try:
            r = RadioButtons(ax, options, active=idx, activecolor=RED_DOT,
                             label_props={"color": [C.INK] * len(options), "fontsize": [8] * len(options)},
                             radio_props={"edgecolor": [C.INK2] * len(options)})
        except TypeError:
            r = RadioButtons(ax, options, active=idx, activecolor=RED_DOT)
            for t in r.labels:
                t.set_color(C.INK)
                t.set_fontsize(8)
        r.on_clicked(lambda lab, k=key: self._changed(k, lab))
        self.radios[key], self.defaults[key], self.values[key] = r, init, init
        return r

    def check(self, key, title, options, actives, rect):
        ax = self.fig.add_axes(rect, facecolor="#1d1f22")
        ax.set_title(title, fontsize=8.5, color=C.INK2, loc="left", pad=3)
        for sp in ax.spines.values():
            sp.set_color(C.GRID)
        try:
            c = CheckButtons(ax, options, actives,
                             label_props={"color": [C.INK] * len(options), "fontsize": [8] * len(options)},
                             frame_props={"edgecolor": [C.INK2] * len(options)},
                             check_props={"facecolor": [RED_DOT] * len(options)})
        except TypeError:
            c = CheckButtons(ax, options, actives)
            for t in c.labels:
                t.set_color(C.INK)
                t.set_fontsize(8)
        c.on_clicked(lambda lab, k=key: self._changed(k, dict(zip(options, c.get_status()))))
        self.checks[key] = (c, list(actives))
        self.defaults[key] = dict(zip(options, actives))
        self.values[key] = dict(zip(options, actives))
        return c

    def reset_button(self, rect, label="Reset all"):
        return self.button(rect, label, self.reset)

    def button(self, rect, label, callback):
        b = Button(self.fig.add_axes(rect), label, color="#2a2c30", hovercolor="#3a3d42")
        b.label.set_color(C.INK)
        b.label.set_fontsize(8.5)
        b.on_clicked(lambda _e: callback())
        self._buttons.append(b)
        return b

    def _changed(self, key, val):
        self.values[key] = val
        if not self._mute:
            self.on_change(dict(self.values))

    def reset(self):
        self._mute = True
        for k, s in self.sliders.items():
            s.set_val(self.defaults[k])
        for k, r in self.radios.items():
            r.set_active(list(t.get_text() for t in r.labels).index(self.defaults[k]))
        for k, (c, actives) in self.checks.items():
            for i, (now, want) in enumerate(zip(c.get_status(), actives)):
                if now != want:
                    c.set_active(i)
        self._mute = False
        self.on_change(dict(self.values))

    def _key(self, ev):
        if ev.key in ("r", "R"):
            self.reset()

    def set(self, key, val):
        # only the self-test uses this
        if key in self.sliders:
            self.sliders[key].set_val(val)
        elif key in self.radios:
            r = self.radios[key]
            r.set_active([t.get_text() for t in r.labels].index(val))


class Player:
    # space bar = pause/play. views check .running each frame

    def __init__(self, fig):
        self.running = True
        fig.canvas.mpl_connect("key_press_event", self._key)

    def _key(self, ev):
        if ev.key == " ":
            self.running = not self.running

    def toggle(self):
        self.running = not self.running
