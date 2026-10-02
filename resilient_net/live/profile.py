"""Live: SRTM terrain profile between two points, Fresnel zone and knife-edge loss (ITU-R P.526)."""
import math
from types import SimpleNamespace

import numpy as np

from .. import config as C, models as M, terrain, ui
from ..terrain import K_FACTOR, R_EARTH, knife_edge_db
from ..widgets import Controls, Player, new_figure, readout, status_colour
from . import common

TITLE = "Live: Terrain path profile, Fresnel zone and diffraction loss"
N_PTS = 100


def paths():
    S = terrain.scenario()
    T = S["T"]
    pl = {p["name"]: np.array([p["x"], p["y"]]) for p in T.places}
    m = S["mast"]
    return {"FM mast → Gangtok": (m, pl["Gangtok"]), "FM mast → Ranipool": (m, pl["Ranipool"]),
            "FM mast → Singtam": (m, pl["Singtam"]), "FM mast → Dikchu": (m, pl["Dikchu"]),
            "FM mast → Pakyong": (m, pl["Pakyong"]), "Gangtok → Singtam": (pl["Gangtok"], pl["Singtam"])}


def fetch(name, a, b):
    T = terrain.load()
    t = np.linspace(0, 1, N_PTS)
    xs, ys = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    lat, lon = T.site_latlon(xs, ys)
    url = "https://api.opentopodata.org/v1/srtm30m?locations=" + "|".join(f"{la:.5f},{lo:.5f}"
                                                                          for la, lo in zip(lat, lon))
    key = "profile_" + "".join(ch for ch in name if ch.isalnum())
    fallback = lambda: {"results": [{"elevation": float(z)} for z in T.elev(xs, ys)]}
    r = common.get_url(key, url, 24 * 365, "OpenTopoData (SRTM 30 m)", fallback)
    z = np.array([q["elevation"] if q["elevation"] is not None else np.nan for q in r.data["results"]], float)
    z = np.where(np.isnan(z), T.elev(xs, ys), z)
    return r, t * math.hypot(*(b - a)), z, xs, ys


def analyse(d, z, f_mhz, ht, hr, k):
    D = d[-1]
    lam = 299.792458 / f_mhz
    d1, d2 = d, D - d
    bulge = d1 * d2 * 1000 / (2 * k * R_EARTH)  # m
    line = (z[0] + ht) + (z[-1] + hr - z[0] - ht) * d / D
    zb = z + bulge
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.sqrt(lam * d1 * d2 * 1000 / np.maximum(D, 1e-9))  # metres (d is in km)
        v = (zb - line) * np.sqrt(2 / lam * (1 / (d1 * 1000) + 1 / (d2 * 1000)))
    inner = slice(1, -1)
    k_max = 1 + int(np.nanargmax(v[inner]))
    vmax = float(v[k_max])
    J = float(knife_edge_db(vmax))
    fspl = float(M.fspl_db(D, f_mhz))
    clear = float(np.nanmin(((line - zb) / np.where(f1 > 0, f1, np.nan))[inner]))
    return dict(D=D, lam=lam, bulge=bulge, line=line, zb=zb, f1=f1, v=v, k=k_max, vmax=vmax, J=J, fspl=fspl,
                total=fspl + J, clear=clear)


def print_calculations():
    ui.head(TITLE.upper(), ui.cyan)
    ui.note("Single worst knife edge (ITU-R P.526) on the SRTM profile, k = 4/3. "
            "'Clear' = at least 60% of the first Fresnel zone is free.")
    print(f"\n    {'Path (100 MHz FM, 50 m mast, 1.5 m radio)':<44}{'km':>6}{'v':>7}{'J(v) dB':>9}{'FSPL dB':>9}")
    for name, (a, b) in paths().items():
        r, d, z, _, _ = fetch(name, a, b)
        q = analyse(d, z, 100.0, 50.0 if name.startswith("FM") else 10.0, 1.5, K_FACTOR)
        print(f"    {name:<44}{q['D']:>6.1f}{q['vmax']:>7.2f}{q['J']:>9.1f}{q['fspl']:>9.1f}")
    ui.note(f"Elevation source: {r.provider} · {r.badge}")


def _setup_map(ax, T):
    ax.imshow(T.hillshade(), extent=T.extent, origin="lower", cmap="gray", vmin=-0.4, vmax=1.5,
              interpolation="bilinear")
    for rv in T.rivers:
        ax.plot(*rv["xy"].T, color="#4f8fd0", lw=0.7)
    for nm in ("Gangtok", "Singtam", "Ranipool", "Pakyong", "Dikchu"):
        place = next(q for q in T.places if q["name"] == nm)
        ax.text(place["x"] + 0.3, place["y"] + 0.3, nm, fontsize=7, color=C.INK)
    mp = SimpleNamespace()
    mp.path, = ax.plot([], [], color=C.COL["warn"], lw=2.2)
    mp.ends, = ax.plot([], [], "o", color=C.COL["warn"], mec=C.INK, ms=7)
    mp.edge, = ax.plot([], [], "x", color=C.COL["bad"], ms=10, mew=2.5)
    ax.set(xlim=T.extent[:2], ylim=T.extent[2:], xticks=[], yticks=[], title="Path on the map")
    ax.set_aspect("equal")
    return mp


def _setup_knife_edge(ax):
    vv = np.linspace(-3, 5, 300)
    ax.plot(vv, knife_edge_db(vv), color=C.COL["bad"], lw=2)
    ax.axvline(-0.78, color=C.MUTED, ls=":", lw=1)
    ax.text(-0.7, 2, "v > −0.78:\nloss starts", fontsize=7, color=C.MUTED)
    dot, = ax.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)
    ax.set(title="Knife-edge loss J(v) (ITU-R P.526)", xlabel="Fresnel–Kirchhoff parameter v",
           ylabel="loss (dB)", xlim=(-3, 5), ylim=(0, 30))
    return dot


def _draw_profile(ax, d, z, q, v, provider, pulse):
    ax.cla()
    ax.fill_between(d, 0, q["zb"], color="#3a3226", ec="#6b5a43", lw=1, zorder=2,
                    label=f"terrain + Earth bulge (k = {v['k']:.2f})")
    ax.plot(d, q["line"], color=C.COL["warn"], lw=1.6, zorder=4, label="direct ray")
    ax.fill_between(d, q["line"] - q["f1"], q["line"] + q["f1"], color=C.COL["warn"], alpha=0.15, lw=0,
                    zorder=3, label=f"1st Fresnel zone ({v['f']:.0f} MHz)")
    ax.plot([d[0], d[0]], [z[0], z[0] + v["ht"]], color=C.INK, lw=3, zorder=5)  # masts
    ax.plot([d[-1], d[-1]], [z[-1], z[-1] + v["hr"]], color=C.INK, lw=3, zorder=5)
    k = q["k"]
    ax.plot([d[k], d[k]], [q["zb"][k], q["line"][k]], color=C.COL["bad"], lw=2, zorder=6)
    ax.annotate(f"dominant edge: v = {q['vmax']:.2f} → J = {q['J']:.1f} dB", (d[k], q["zb"][k]),
                (0.35, 0.92), textcoords="axes fraction", fontsize=8, color=C.COL["bad"],
                arrowprops=dict(arrowstyle="->", color=C.COL["bad"]), zorder=7)
    ax.set(xlim=(0, d[-1]), ylim=(np.nanmin(z) - 100, max(np.nanmax(q["zb"]), np.nanmax(q["line"])) + 250),
           title=f"Profile: {v['path']}  ({q['D']:.1f} km, {provider})", xlabel="distance (km)",
           ylabel="height above sea (m)")
    ax.legend(fontsize=7, loc="lower left", ncol=3)
    ax.add_line(pulse)  # cla() removed it


def _draw_budget(ax, q):
    ax.cla()
    a = C.ANALOG
    pr = 10 * math.log10(a["p_kw"] * 1e6) + a["gt_db"] + a["gr_db"] - q["total"] - a["clutter_db"]
    left = 0
    for lab, val, col in [("FSPL", q["fspl"], C.COL[C.L_MO]), ("ridge J(v)", q["J"], C.COL["bad"]),
                          ("clutter", a["clutter_db"], C.MUTED)]:
        ax.barh(0, val, left=left, color=col, height=0.5, edgecolor=C.PANEL, lw=2)
        ax.text(left + val / 2, 0, f"{lab}\n{val:.1f}", ha="center", va="center", fontsize=7.5, color=C.BG,
                fontweight="bold")
        left += val
    ax.set(title="Path loss budget (dB)", xlim=(0, max(left * 1.08, 150)), yticks=[], xlabel="dB")
    ax.text(0.02, 0.88, f"total {left:.1f} dB → FM Pr = {pr:.1f} dBm (100 W, +6 dBi)",
            transform=ax.transAxes, fontsize=8, color=C.INK)


def _readout_text(v, q):
    ok = q["clear"] >= 0.6
    return (f"{v['path']}\n"
            f"distance {q['D']:.1f} km · λ = {q['lam']:.2f} m\n"
            f"Earth bulge at mid-path {q['bulge'].max():.0f} m\n"
            f"worst clearance {q['clear']:+.2f} × F1 ({'clear' if ok else 'obstructed'})\n"
            f"v = {q['vmax']:.2f} → J(v) = {q['J']:.1f} dB\n"
            f"FSPL {q['fspl']:.1f} + J {q['J']:.1f} = {q['total']:.1f} dB")


def build():
    P = paths()
    names = list(P)
    T = terrain.load()
    v = dict(path=names[2], f=100.0, k=round(K_FACTOR, 2), ht=50.0, hr=1.5)
    st = dict(res=None)
    fig = new_figure(TITLE, "Link budget on the actual ground: earth curvature, direct ray, 1st Fresnel zone "
                            "and whichever ridge gets in the way (ITU-R P.526)", "LIVE DATA")
    badge_txt = fig.text(0.985, 0.943, "", fontsize=8, color=C.BG, va="top", ha="right", fontweight="bold",
                         bbox=dict(boxstyle="round,pad=0.3", fc=C.COL["good"], ec="none"))
    gs = fig.add_gridspec(2, 3, left=0.05, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42,
                          width_ratios=[1.2, 1.2, 1])
    ax_p = fig.add_subplot(gs[0, :2])
    ax_m = fig.add_subplot(gs[:, 2])
    ax_j, ax_b = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
    mp = _setup_map(ax_m, T)
    j_dot = _setup_knife_edge(ax_j)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)
    pulse, = ax_p.plot([], [], "o", ms=8, color=C.COL["warn"], mec=C.INK, zorder=8)

    def recompute(vals):
        new_path = vals["path"] != v["path"] or st["res"] is None
        v.update(vals)
        if new_path:  # only hit the API when the path actually changes
            a, b = P[v["path"]]
            st["res"], st["d"], st["z"], st["xs"], st["ys"] = fetch(v["path"], a, b)
            mp.path.set_data(st["xs"], st["ys"])
            mp.ends.set_data([st["xs"][0], st["xs"][-1]], [st["ys"][0], st["ys"][-1]])
            badge_txt.set_text(f"  {st['res'].badge}  ")
            badge_txt.get_bbox_patch().set_facecolor(st["res"].colour)
        d, z = st["d"], st["z"]
        q = st["q"] = analyse(d, z, v["f"], v["ht"], v["hr"], v["k"])
        _draw_profile(ax_p, d, z, q, v, st["res"].provider, pulse)
        mp.edge.set_data([st["xs"][q["k"]]], [st["ys"][q["k"]]])
        j_dot.set_data([np.clip(q["vmax"], -3, 5)], [min(q["J"], 29.5)])
        _draw_budget(ax_b, q)
        ro.set_text(_readout_text(v, q))
        ro.set_color(status_colour(1.0 if q["clear"] >= 0.6 else 0.5 if q["J"] < 15 else 0.0))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.52, 0.17), cols=2, rows=2)
    ctl.slider("f", "Frequency (MHz)", 30, 3000, v["f"], step=10, fmt="%.0f", color=C.COL[C.L_AN])
    ctl.slider("k", "k-factor (refraction)", 0.5, 4.0, v["k"], step=0.01, fmt="%.2f")
    ctl.slider("ht", "Tx mast height (m)", 5, 120, v["ht"], step=1, fmt="%.0f")
    ctl.slider("hr", "Rx antenna height (m)", 1.5, 30, v["hr"], step=0.5, fmt="%.1f")
    ctl.radio("path", "Path", names, v["path"], [0.545, 0.035, 0.13, 0.17])
    ctl.reset_button([0.36, 0.05, 0.16, 0.035])
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        # a dot travelling along the ray, shrinks + turns red once it's past a ridge that blocks it
        u = (frame % 60) / 60
        d, q = st["d"], st["q"]
        x = u * d[-1]
        pulse.set_data([x], [np.interp(x, d, q["line"])])
        blocked = x > d[q["k"]] and q["J"] > 6
        pulse.set_color(C.COL["bad"] if blocked else C.COL["warn"])
        pulse.set_markersize(8 * (0.4 if blocked else 1.0) + 2)

    return fig, step, ctl
