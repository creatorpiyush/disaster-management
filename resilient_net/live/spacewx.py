"""Live: space weather (NOAA SWPC Kp, X-ray flares, F10.7) and what it does to each layer."""
import datetime as dt

import numpy as np

from .. import config as C, ui
from ..widgets import Controls, Player, new_figure, readout
from . import common

TITLE = "Live: Space weather and what it means for each layer"
G_SCALE = [(9, "G5", "#a3132f"), (8, "G4", "#d22f2f"), (7, "G3", "#e66767"), (6, "G2", "#e09a00"),
           (5, "G1", "#e0c400"), (0, "quiet", "#2fb344")]
FLARE = [(1e-4, "X"), (1e-5, "M"), (1e-6, "C"), (1e-7, "B"), (1e-8, "A")]


def _t(s):
    s = s.replace("Z", "")[:19]
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S" if "T" in s else "%Y-%m-%d %H:%M:%S")


def parse(kp, xr, f107):
    rows = kp.data
    if rows and isinstance(rows[0], list):  # older SWPC format: header row + lists
        hdr = rows[0]
        rows = [dict(zip(hdr, r)) for r in rows[1:]]
    k_t = [_t(r["time_tag"]) for r in rows]
    k_v = np.array([float(r.get("Kp", r.get("kp_index", 0))) for r in rows])
    long_ = [r for r in xr.data if r.get("energy") == "0.1-0.8nm"]
    x_t = [_t(r["time_tag"]) for r in long_]
    x_v = np.array([float(r["flux"]) if r.get("flux") and r["flux"] > 0 else np.nan for r in long_])
    ok = np.isfinite(x_v)
    x_last = float(x_v[ok][-1]) if ok.any() else 1e-8
    fr = sorted((r for r in f107.data if r.get("flux")), key=lambda r: r["time_tag"])
    f_t = [_t(r["time_tag"]) for r in fr][-120:]
    f_v = np.array([float(r["flux"]) for r in fr])[-120:]
    return dict(k_t=k_t, k_v=k_v, x_t=x_t, x_v=x_v, f_t=f_t, f_v=f_v, x_last=x_last,
                x_max=float(np.nanmax(x_v)) if ok.any() else 1e-8)


def flare_class(flux):
    for lim, c in FLARE:
        if flux >= lim:
            return f"{c}{flux / lim:.1f}"
    return "A0"


def r_scale(flux):
    return "R5" if flux >= 2e-3 else "R4" if flux >= 1e-3 else "R3" if flux >= 1e-4 else "R2" if flux >= 5e-5 \
        else "R1" if flux >= 1e-5 else "none"


def g_scale(kp):
    return next((g, c) for lim, g, c in G_SCALE if kp >= lim)


def impacts(d):
    kp, xf, f = d["k_v"][-1], d["x_last"], d["f_v"][-1]
    g, _ = g_scale(kp)
    risk = "HIGH" if kp >= 6 or f >= 180 else "MODERATE" if kp >= 4 or f >= 130 else "LOW"
    hf = "blackout on the sunlit side" if xf >= 1e-5 else "normal"
    return [("Analog radio (VHF FM / MF AM)", "not affected (VHF/MF ground wave)" if xf < 1e-4 else
             "MF sky-wave absorbed; local FM unaffected", "good" if xf < 1e-4 else "warn"),
            ("HF links (if used for backhaul)", hf, "good" if xf < 1e-5 else "bad"),
            ("Satellite Ku-band (VSAT)", "minor scintillation only", "good" if risk != "HIGH" else "warn"),
            ("Satellite L-band (Iridium) / GNSS", f"scintillation risk {risk}",
             {"LOW": "good", "MODERATE": "warn", "HIGH": "bad"}[risk]),
            ("UAV navigation (GNSS)", "position errors grow" if risk != "LOW" else "normal",
             "good" if risk == "LOW" else "warn"),
            ("Geomagnetic storm level", f"Kp {kp:.1f} → {g}", "good" if kp < 5 else "bad")]


def load():
    res = (common.get("kp"), common.get("xray"), common.get("f107"))
    return res, parse(*res)


def print_calculations(res=None, d=None):
    if d is None:
        res, d = load()
    ui.head(TITLE.upper(), ui.cyan)
    ui.note(" · ".join(f"{r.provider}: {r.badge}" for r in res[:1]) + ". G/R are the NOAA scales (G from Kp, R from GOES 0.1-0.8 nm X-ray flux).")
    kp, xf = d["k_v"][-1], d["x_last"]
    ui.kv("Planetary Kp (latest 3-hour value)", f"{kp:.2f} → {g_scale(kp)[0]}")
    ui.kv("Max Kp in the record shown", f"{d['k_v'].max():.2f} → {g_scale(d['k_v'].max())[0]}")
    ui.kv("GOES X-ray flux now", f"{xf:.2e} W/m² (class {flare_class(xf)}, radio blackout {r_scale(xf)})")
    ui.kv("Largest flare in the record", f"{flare_class(d['x_max'])}")
    ui.kv("F10.7 solar radio flux (latest)", f"{d['f_v'][-1]:.0f} sfu")
    for name, txt, lvl in impacts(d):
        ui.kv(name, txt, lvl == "good" if lvl != "warn" else None)
    return d


def build():
    res, d = load()
    fig = new_figure(TITLE, "The one noise source nobody can switch off. Flares black out HF, geomagnetic storms "
                            "cause scintillation (L-band and GNSS get hit hardest).",
                     "LIVE DATA")
    common.badge(fig, list(res))
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.14, wspace=0.28, hspace=0.42)
    ax_k, ax_x = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1:])
    ax_f, ax_i = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1:])
    ax_i.set_axis_off()

    cols = [g_scale(k)[1] for k in d["k_v"]]
    ax_k.bar(d["k_t"], d["k_v"], width=0.11, color=cols)
    ax_k.axhline(5, color=C.COL["warn"], ls="--", lw=1)
    ax_k.text(d["k_t"][0], 5.15, "storm (G1) at Kp 5", fontsize=7, color=C.COL["warn"])
    ax_k.set(title="Planetary Kp index (3-hourly)", ylabel="Kp", ylim=(0, 9))
    k_dot, = ax_k.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)

    ax_x.semilogy(d["x_t"], d["x_v"], color=C.COL[C.L_AN], lw=1.2)
    for lim, c in FLARE:
        ax_x.axhline(lim, color=C.GRID, lw=0.8)
        ax_x.text(d["x_t"][-1], lim * 1.3, f" {c}", fontsize=8, color=C.INK2)
    ax_x.set(title="GOES X-ray flux 0.1–0.8 nm (solar flares)", ylabel="W/m²", ylim=(1e-9, 1e-3))
    x_dot, = ax_x.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)

    ax_f.plot(d["f_t"], d["f_v"], color=C.COL[C.L_UAV], lw=1.6)
    ax_f.set(title="F10.7 solar radio flux (sfu)", ylabel="sfu")
    for a in (ax_k, ax_x, ax_f):
        a.tick_params(axis="x", labelsize=6.5)
        for lab in a.get_xticklabels():
            lab.set_rotation(20)

    rows = impacts(d)
    ax_i.text(0, 1.0, "WHAT IT MEANS FOR EACH LAYER (now)", fontsize=10, fontweight="bold", color=C.INK,
              transform=ax_i.transAxes, va="top")
    lamps = []
    for k, (name, txt, lvl) in enumerate(rows):
        y = 0.84 - k * 0.14
        lamps.append(ax_i.plot([0.02], [y], "o", ms=13, color=C.COL[lvl], transform=ax_i.transAxes)[0])
        ax_i.text(0.06, y, name, fontsize=9, color=C.INK, transform=ax_i.transAxes, va="center")
        ax_i.text(0.5, y, txt, fontsize=9, color=C.INK2, transform=ax_i.transAxes, va="center")
    ax_i.text(0, 0.0, "Gangtok (~18° N magnetic) lies under the northern crest of the equatorial ionisation "
                        "anomaly:\nL-band scintillation is most likely after sunset in high-flux years.",
              fontsize=7.5, color=C.MUTED, transform=ax_i.transAxes)
    ro = readout(fig.add_axes([0.735, 0.015, 0.25, 0.1]))
    kp, xf = d["k_v"][-1], d["x_last"]
    ro.set_text(f"Kp {kp:.1f} ({g_scale(kp)[0]}) · flare class {flare_class(xf)}\n"
                f"radio blackout {r_scale(xf)} · F10.7 {d['f_v'][-1]:.0f} sfu")
    ro.set_fontsize(8)
    player = Player(fig)
    ctl = Controls(fig, lambda vals: None, rect=(0.015, 0.02, 0.2, 0.0), cols=1, rows=1)
    ctl.button([0.015, 0.03, 0.12, 0.04], "▶  Play / pause", player.toggle)

    def step(frame):
        if not player.running:
            return
        u = abs(np.sin(frame * 0.15))
        k_dot.set_data([d["k_t"][-1]], [d["k_v"][-1]])
        x_dot.set_data([d["x_t"][-1]], [d["x_last"]])
        for m in (k_dot, x_dot):
            m.set_markersize(9 + 6 * u)
        for lp in lamps:
            lp.set_alpha(0.55 + 0.45 * u)

    return fig, step, ctl
