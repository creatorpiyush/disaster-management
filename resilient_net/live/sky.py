"""Live: which real satellites are over Gangtok right now, and which ones the ridges hide."""
import datetime as dt
import math
from types import SimpleNamespace

import numpy as np

from .. import config as C, ui
from ..views.satellite import SITES, site_info
from ..widgets import Controls, Player, new_figure, readout
from . import common, orbits

TITLE = "Live: Real satellites over Gangtok"
GROUPS = {  # label: (source, colour, downlink GHz used for FSPL, band text)
    "Starlink": ("sat_starlink", C.COL[C.L_MO], 11.7, "Ku"),
    "OneWeb": ("sat_oneweb", C.COL["violet"], 11.7, "Ku"),
    "Iridium": ("sat_iridium", C.COL[C.L_UAV], 1.62, "L"),
    "GEO": ("sat_geo", C.COL[C.L_SA], 11.7, "Ku"),
    "Stations": ("sat_stations", C.INK, 0.437, "UHF"),
}
INDIAN = ("GSAT", "INSAT", "CMS-", "GSAT-N")


def load():
    res = {g: common.get(src) for g, (src, *_r) in GROUPS.items()}
    cons = {g: orbits.Constellation(r.data, g) for g, r in res.items()}
    return res, cons


def snapshot(cons, t, site, min_el):
    info = site_info(site)
    lat, lon = common.GANGTOK
    out = {}
    for g, c in cons.items():
        az, el, rg = c.look(t, lat, lon, info["alt"] / 1000)
        hz = np.interp(az, np.r_[info["az"], 360], np.r_[info["sky"], info["sky"][0]])
        lim = 0.0 if g == "GEO" else min_el
        usable = (el >= lim) & (el > hz)
        out[g] = dict(az=az, el=el, rg=rg, hz=hz, usable=usable, up=el > 0)
    return out


def print_calculations(res=None, cons=None):
    if cons is None:
        res, cons = load()
    t = orbits.now()
    snap = snapshot(cons, t, "Gangtok ridge", 25.0)
    ui.head(TITLE.upper(), ui.cyan)
    ui.note(f"Elements from CelesTrak ({next(iter(res.values())).badge}), propagated with Kepler + J2. "
            "'Usable' = above the min elevation (25 deg for LEO) and not behind the ridge.")
    print(f"\n    {'Group':<10}{'tracked':>9}{'above horizon':>15}{'usable now':>12}")
    for g, s in snap.items():
        print(f"    {g:<10}{len(cons[g]):>9}{int(s['up'].sum()):>15}{int(s['usable'].sum()):>12}")
    for g in ("Starlink", "GEO"):
        s = snap[g]
        pick = s["usable"] & (np.array([n.startswith(INDIAN) for n in cons[g].names]) if g == "GEO" else True)
        if pick.any():
            k = int(np.argmax(np.where(pick, s["el"], -99)))
            f = GROUPS[g][2]
            d = s["rg"][k]
            ui.calc(f"Highest usable {'Indian GEO' if g == 'GEO' else g}: {cons[g].names[k]}", "FSPL = 92.45 + 20log d(km) + 20log f(GHz)",
                    f"El {s['el'][k]:.1f}°, d = {d:,.0f} km, f = {f} GHz",
                    f"{92.45 + 20 * math.log10(d) + 20 * math.log10(f):.1f} dB",
                    f"· one-way delay {d / 299.792458:.1f} ms")
    return snap


def _setup_sky(ax):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_facecolor("#111a24")
    ax.set_ylim(0, 90)
    ax.set_yticks([30, 60], ["60°", "30°"], fontsize=7, color=C.MUTED)
    ax.set_xticks(np.radians([0, 90, 180, 270]), ["N", "E", "S", "W"], color=C.INK2)
    ax.grid(color="#26313d", lw=0.6)
    sk = SimpleNamespace(fill=None)
    sk.ring, = ax.plot([], [], color=C.MUTED, lw=0.9, ls=":")
    sk.scat = {g: ax.scatter([], [], s=14 if g == "Starlink" else 26, color=GROUPS[g][1], zorder=5,
                             label=g, edgecolor="none") for g in GROUPS}
    sk.dim = ax.scatter([], [], s=8, color="#5d5d58", zorder=4)  # above the horizon but hidden / masked
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=7, ncol=5, markerscale=1.2,
              columnspacing=0.8, handletextpad=0.2)
    sk.txt = ax.text(0.5, -0.13, "", transform=ax.transAxes, ha="center", fontsize=8.5, color=C.INK)
    return sk


def _setup_counts(ax):
    ax.set(title="Usable satellites over the next 2 hours", xlabel="minutes from now", ylabel="count")
    lines = {g: ax.plot([], [], color=GROUPS[g][1], lw=1.6, label=g)[0] for g in GROUPS}
    cur = ax.axvline(0, color=C.COL["warn"], lw=1.2)
    ax.set_yscale("symlog", linthresh=5)
    ax.legend(fontsize=6.5, ncol=3, loc="upper right")
    return lines, cur


def _setup_geo(ax):
    ax.set(title="Geostationary belt seen from the site", xlabel="azimuth (°)", ylabel="elevation (°)",
           xlim=(60, 300), ylim=(0, 70))
    gb = SimpleNamespace(fill=None, labels=[])
    gb.sky, = ax.plot([], [], color="#a07850", lw=1.5)
    gb.all = ax.scatter([], [], s=14, color=C.COL[C.L_SA], zorder=4)
    gb.indian = ax.scatter([], [], s=50, marker="D", color=C.COL["warn"], edgecolor=C.INK, zorder=5,
                           label="Indian GSAT / INSAT")
    ax.legend(fontsize=6.8, loc="upper right")
    return gb


def _draw_skyline(ax, sk, v, info):
    th = np.radians(np.r_[info["az"], 360])
    sky = np.r_[info["sky"], info["sky"][0]]
    if sk.fill is not None:
        sk.fill.remove()
    sk.fill = ax.fill_between(th, 90 - sky, 90, color="#6b4f35", alpha=0.95, lw=0, zorder=3)
    sk.ring.set_data(np.linspace(0, 2 * np.pi, 180), np.full(180, 90 - v["minel"]))
    ax.set_title(f"Sky over {v['site']} ({info['alt']:.0f} m) · ridges in brown", pad=14)


def _draw_geo_belt(ax, gb, cons, t, v, info):
    gb.sky.set_data(info["az"], info["sky"])
    if gb.fill is not None:
        gb.fill.remove()
    gb.fill = ax.fill_between(info["az"], 0, info["sky"], color="#6b4f35", alpha=0.9, lw=0)
    s = snapshot({"GEO": cons["GEO"]}, t, v["site"], v["minel"])["GEO"]
    up = s["up"]
    gb.all.set_offsets(np.c_[s["az"][up], s["el"][up]])
    names = np.array(cons["GEO"].names)
    ind = up & np.array([n.startswith(INDIAN) for n in names])
    gb.indian.set_offsets(np.c_[s["az"][ind], s["el"][ind]] if ind.any() else np.zeros((0, 2)))
    for lbl in gb.labels:
        lbl.remove()
    gb.labels = [ax.text(s["az"][k] + 2, s["el"][k] + 1.5, names[k], fontsize=6, color=C.INK2)
                 for k in np.nonzero(ind)[0][:7]]


def _table_text(rows):
    lines = [f"{'USABLE NOW (LEO, + Indian GEO)':<26}{'group':<10}{'El°':>6}{'Az°':>6}{'range km':>10}"
             f"{'FSPL dB':>9}{'delay ms':>10}", "─" * 77]
    for el, nm, g, az, rg, f in rows:
        fspl = 92.45 + 20 * math.log10(rg) + 20 * math.log10(f)
        lines.append(f"{nm[:25]:<26}{g:<10}{el:>6.1f}{az:>6.0f}{rg:>10,.0f}{fspl:>9.1f}{rg / 299.792458:>10.2f}")
    return "\n".join(lines)


def build():
    res, cons = load()
    st = dict(t0=orbits.now(), sim=0.0)  # sim = simulated seconds since t0
    v = dict(speed=60.0, minel=25.0, site="Gangtok ridge", grp={g: True for g in GROUPS})
    fig = new_figure(TITLE, "Which satellites can a VSAT on the Gangtok ridge (or down in the valley) actually "
                            "see right now?", "LIVE DATA")
    common.badge(fig, list(res.values()))
    gs = fig.add_gridspec(2, 3, left=0.03, right=0.985, top=0.9, bottom=0.27, wspace=0.3, hspace=0.45,
                          width_ratios=[1.25, 1, 1])
    ax_sky = fig.add_subplot(gs[:, 0], projection="polar")
    ax_cnt, ax_geo = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_tab = fig.add_subplot(gs[1, 1:])
    ax_tab.set_axis_off()

    sky = _setup_sky(ax_sky)
    cnt_lines, cnt_cur = _setup_counts(ax_cnt)
    belt = _setup_geo(ax_geo)
    tab = ax_tab.text(0, 1, "", family="monospace", fontsize=7.8, va="top", color=C.INK, transform=ax_tab.transAxes)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def now_t():
        return st["t0"] + dt.timedelta(seconds=st["sim"])

    def recompute(vals):
        v.update(speed=vals["speed"], minel=vals["minel"], site=vals["site"], grp=vals["grp"])
        info = site_info(v["site"])
        _draw_skyline(ax_sky, sky, v, info)
        mins = np.arange(0, 121, 3)
        t = now_t()
        for g in GROUPS:
            c = [int(snapshot({g: cons[g]}, t + dt.timedelta(minutes=float(m)), v["site"], v["minel"])[g]["usable"]
                     .sum()) for m in mins]
            cnt_lines[g].set_data(mins, c)
            cnt_lines[g].set_visible(v["grp"].get(g, True))
        ax_cnt.relim()
        ax_cnt.autoscale_view()
        st["cnt_t0"] = st["sim"]
        _draw_geo_belt(ax_geo, belt, cons, t, v, info)
        draw()
        fig.canvas.draw_idle()

    def draw():
        t = now_t()
        snap = snapshot(cons, t, v["site"], v["minel"])
        dims, rows, tot = [], [], 0
        for g, s in snap.items():
            on = v["grp"].get(g, True)
            u = s["usable"] & on
            sky.scat[g].set_offsets(np.c_[np.radians(s["az"][u]), 90 - s["el"][u]] if u.any() else np.zeros((0, 2)))
            hid = s["up"] & ~s["usable"] & on
            dims.append(np.c_[np.radians(s["az"][hid]), 90 - s["el"][hid]])
            tot += int(u.sum())
            for k in np.nonzero(u)[0]:
                nm = cons[g].names[k]
                if g != "GEO" or nm.startswith(INDIAN):
                    rows.append((s["el"][k], nm, g, s["az"][k], s["rg"][k], GROUPS[g][2]))
        dd = np.vstack(dims) if dims else np.zeros((0, 2))
        sky.dim.set_offsets(dd if len(dd) else np.zeros((0, 2)))
        # table: highest 8 LEO + highest 4 Indian GEO
        rows = (sorted([r for r in rows if r[2] != "GEO"], reverse=True)[:8] +
                sorted([r for r in rows if r[2] == "GEO"], reverse=True)[:4])
        tab.set_text(_table_text(rows))
        blocked = sum(int((s["up"] & ~s["usable"] & (s["el"] >= (0 if g == "GEO" else v["minel"]))).sum())
                      for g, s in snap.items() if v["grp"].get(g, True))
        sky.txt.set_text(f"{tot} usable · {blocked} hidden behind ridges · grey = below the {v['minel']:.0f}° mask")
        cnt_cur.set_xdata([(st["sim"] - st.get("cnt_t0", 0)) / 60] * 2)
        ist = t.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        ro.set_text(
            f"SIMULATED CLOCK (IST)\n{ist:%d %b %Y  %H:%M:%S}  ×{v['speed']:.0f}\n"
            f"site {v['site']} · mask {v['minel']:.0f}°\n"
            + "\n".join(f"{g:<9}{int(snap[g]['usable'].sum()):>4} usable / {len(cons[g])}"
                        for g in ("Starlink", "OneWeb", "Iridium")))

    def back_to_now():
        st.update(sim=0.0, t0=orbits.now())
        recompute(dict(ctl.values))

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.40, 0.17), cols=1, rows=3)
    ctl.slider("speed", "Clock speed (× real time)", 1, 600, v["speed"], step=1, fmt="%.0f",
               color=C.COL[C.L_SA])
    ctl.slider("minel", "Minimum elevation (°)", 0, 60, v["minel"], step=1, fmt="%.0f")
    ctl.radio("site", "Terminal site", list(SITES), v["site"], [0.425, 0.035, 0.12, 0.15])
    ctl.check("grp", "Constellations", list(GROUPS), [True] * len(GROUPS), [0.555, 0.035, 0.09, 0.15])
    ctl.button([0.655, 0.12, 0.07, 0.035], "↻ Now", back_to_now)
    ctl.reset_button([0.655, 0.06, 0.07, 0.035], "Reset")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        st["sim"] += 0.045 * v["speed"]
        draw()

    return fig, step, ctl
