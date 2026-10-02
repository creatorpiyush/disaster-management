"""LAYER 3 - Satellite backup (GEO / LEO link budget with rain fade).  Unit IV."""
import math

import numpy as np
from matplotlib.patches import Circle, Ellipse

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

SA_C = C.COL[C.L_SA]
BAND_COL = {"C": C.COL[C.L_MO], "Ku": C.COL[C.L_SA], "Ka": C.COL[C.L_UAV]}
TITLE = "Layer 3 · Satellite backup"


def defaults():
    s = C.SAT
    return dict(rain=C.STORM["rain"], elev=s["elev"], eirp=s["eirp_dbw"], dish=s["dish_m"], rate=s["rate_kbps"],
                hpa=s["hpa_w"], band=s["band"], orbit=s["orbit"])


def evaluate(v):
    return M.satellite_layer(rain=v["rain"], band=v["band"], orbit=v["orbit"], elev=v["elev"], eirp_dbw=v["eirp"],
                             dish_m=v["dish"], rate_kbps=v["rate"], hpa_w=v["hpa"], wind=C.STORM["wind"],
                             req_ebn0=C.SAT["req_ebn0"], t_sys=C.SAT["t_sys"])


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    b = M.BANDS[v["band"]]
    alt = M.ORBITS[v["orbit"]]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_SA])
    ui.note("Role in the hybrid design: a link that does not depend on anything on the ground except the "
            "terminal itself. It backhauls shelters, hospitals and the emergency operations centre when "
            "fibre and towers are gone. Its weak point is rain fade at high frequency.")
    ui.sub(f"Geometry ({v['orbit']}, altitude {alt:,.0f} km, elevation {v['elev']:.0f}°)")
    ui.calc("Slant range", "d = √((Re+h)² − (Re·cos El)²) − Re·sin El",
            f"Re = 6378 km, h = {alt:,.0f} km, El = {v['elev']:.0f}°", f"{r['d']:,.0f}", "km")
    ui.calc("Propagation delay", "τ = 2d / c   (user → satellite → gateway)", f"2 × {r['d']:,.0f} / 3×10⁵",
            f"{r['delay_ms']:.1f}", "ms")
    ui.sub(f"Free-space path loss ({v['band']}-band: up {b['fu']:.0f} GHz / down {b['fd']:.0f} GHz)")
    ui.calc("Uplink FSPL", "L = 92.45 + 20log d(km) + 20log f(GHz)",
            f"92.45 + 20log{r['d']:.0f} + 20log{b['fu']:.0f}", f"{r['lu']:.2f}", "dB")
    ui.calc("Downlink FSPL", "L = 92.45 + 20log d(km) + 20log f(GHz)",
            f"92.45 + 20log{r['d']:.0f} + 20log{b['fd']:.0f}", f"{r['ld']:.2f}", "dB")
    ui.sub(f"Rain fade at {v['rain']:.0f} mm/h (ITU-R P.838 / P.618)")
    ui.calc("Specific attenuation", "γ = k·R^α", f"{b['k']} × {v['rain']:.0f}^{b['a']}", f"{r['gam']:.3f}", "dB/km")
    ui.calc("Downlink rain attenuation", "A = γ · Ls · r(reduction)", "", f"{r['a_d']:.2f}", "dB")
    ui.calc("Uplink rain attenuation", "A_up ≈ A_down (fu/fd)^1.72", "", f"{r['a_u']:.2f}", "dB")
    ui.calc("Rain noise temperature", "ΔT = 275(1 − 10^(−A/10))", "", f"{r['t_rain']:.0f}", "K")
    ui.sub("Link budget")
    ui.calc("Terminal dish gain (rx)", "G = 10log(η(πD/λ)²)", f"η = 0.6, D = {v['dish']} m", f"{r['g_rx']:.1f}", "dBi")
    ui.calc("Figure of merit", "G/T = G − 10log(Tsys + ΔT)", f"{r['g_rx']:.1f} − 10log({C.SAT['t_sys']:.0f} + "
            f"{r['t_rain']:.0f})", f"{r['gt']:.1f}", "dB/K")
    ui.calc("Downlink C/N0", "EIRP − L − A − Latm + G/T + 228.6",
            f"{v['eirp']:.0f} − {r['ld']:.1f} − {r['a_d']:.1f} − {r['atm'] + r['point']:.1f} + {r['gt']:.1f} + 228.6",
            f"{r['cn0_d']:.1f}", "dB-Hz")
    ui.calc("Uplink C/N0", "EIRP_t − L − A − Latm + (G/T)sat + 228.6",
            f"{r['eirp_up']:.1f} − {r['lu']:.1f} − {r['a_u']:.1f} − {r['atm'] + r['point']:.1f} + {b['sat_gt']:.0f} + 228.6",
            f"{r['cn0_u']:.1f}", "dB-Hz")
    ui.calc("Total C/N0", "(C/N0)⁻¹ = (C/N0)up⁻¹ + (C/N0)down⁻¹", "", f"{r['cn0']:.1f}", "dB-Hz")
    ui.calc("Eb/N0", "Eb/N0 = C/N0 − 10log Rb", f"{r['cn0']:.1f} − 10log({v['rate'] * 1e3:.0f})", f"{r['ebn0']:.1f}",
            "dB")
    ui.kv("Link margin over required 6 dB (QPSK + FEC)", f"{r['margin']:+.1f} dB", r["margin"] > 0)
    ui.bar("Citizens reached (via shelters)", r["reach"], ui.LAYER_TINT[C.L_SA])
    return r


def _sat_pos(elev, radius):
    """Point on an orbit of given radius seen from the ground station (0, 1) at the given elevation."""
    e = math.radians(elev)
    d = np.array([math.cos(e), math.sin(e)])
    p = np.array([0.0, 1.0])
    bq = 2 * p.dot(d)
    cq = p.dot(p) - radius ** 2
    t = (-bq + math.sqrt(bq ** 2 - 4 * cq)) / 2
    return p + t * d


def build():
    v = defaults()
    st = dict(r=evaluate(v), pulse=0.0, drops=np.random.default_rng(2).random((40, 2)))
    fig = new_figure(TITLE, "GEO and LEO satellite links: geometry, free-space loss, rain fade, link budget and "
                            "latency — recomputed live", "LAYER 3 · REQUIRED")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_orb, ax_wf, ax_fspl = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1:]), None
    ax_rain, ax_mar, ax_lat = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    # (a) orbit animation ---------------------------------------------------------
    ax_orb.set_aspect("equal")
    ax_orb.set(xlim=(-2.6, 7.0), ylim=(-1.9, 7.2), xticks=[], yticks=[])
    ax_orb.set_title("Live link geometry (LEO radius exaggerated)")
    ax_orb.add_patch(Circle((0, 0), 1, fc="#1e3a5f", ec=C.COL[C.L_MO], lw=1.2))
    ax_orb.add_patch(Circle((0, 0), 6.61, fc="none", ec=C.MUTED, lw=0.8, ls=":"))
    ax_orb.add_patch(Circle((0, 0), 1.45, fc="none", ec=C.MUTED, lw=0.8, ls=":"))
    ax_orb.text(-2.4, 6.0, "GEO 35 786 km", fontsize=7, color=C.MUTED)
    ax_orb.text(-1.6, -1.95, "LEO 550 km", fontsize=7, color=C.MUTED)
    gw = np.array([math.cos(math.radians(55)), math.sin(math.radians(55))])
    ax_orb.plot([0], [1], "s", color=C.INK, ms=7)
    ax_orb.text(-0.15, 1.15, "terminal", fontsize=7, color=C.INK, ha="right")
    ax_orb.plot(*gw, "s", color=C.INK2, ms=6)
    ax_orb.text(gw[0] + 0.15, gw[1] - 0.15, "gateway / EOC", fontsize=7, color=C.INK2)
    geo_dot, = ax_orb.plot([], [], "D", color=SA_C, ms=9)
    leo_dots, = ax_orb.plot([], [], "o", color=SA_C, ms=5)
    link_up, = ax_orb.plot([], [], color=SA_C, lw=1.2, alpha=0.6)
    link_dn, = ax_orb.plot([], [], color=SA_C, lw=1.2, alpha=0.6)
    pulses, = ax_orb.plot([], [], "o", color=C.INK, ms=4)
    cloud = Ellipse((0.35, 1.9), 1.6, 0.5, fc="#5c6670", ec="none", alpha=0.0)
    ax_orb.add_patch(cloud)
    rain_lines = ax_orb.vlines([], [], [], color="#8fb4d9", lw=0.8, alpha=0.7)
    orb_txt = ax_orb.text(0.02, 0.97, "", transform=ax_orb.transAxes, va="top", fontsize=7.5, color=C.INK)

    # (b) waterfall -----------------------------------------------------------------
    ax_wf.set_title("Downlink + total budget: where the decibels go")

    # (c) rain attenuation ---------------------------------------------------------
    rr = np.linspace(0, 150, 120)
    for bn, col in BAND_COL.items():
        b = M.BANDS[bn]
        ax_rain.plot(rr, [M.rain_attenuation(x, b["fd"], b["k"], b["a"], v["elev"])[0] for x in rr], color=col,
                     lw=1.8, label=f"{bn} ({b['fd']:.0f} GHz)")
    op_rain, = ax_rain.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_rain.set(title="Rain fade vs rain rate (downlink)", xlabel="rain rate (mm/h)", ylabel="attenuation (dB)",
                xlim=(0, 150), ylim=(0, 40))
    ax_rain.legend(loc="upper left", fontsize=7)
    rain_curves = ax_rain.get_lines()[:3]

    # (d) margin vs rain --------------------------------------------------------------
    mar_lines = {bn: ax_mar.plot([], [], color=col, lw=1.8, label=f"{bn}-band")[0] for bn, col in BAND_COL.items()}
    ax_mar.axhline(0, color=C.COL["bad"], lw=1.2, ls="--")
    ax_mar.text(2, 0.8, "link lost below 0 dB", fontsize=7, color=C.COL["bad"])
    op_mar, = ax_mar.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_mar.set(title="Link margin vs rain rate (each band)", xlabel="rain rate (mm/h)", ylabel="Eb/N0 margin (dB)",
               xlim=(0, 150), ylim=(-30, 45))
    ax_mar.legend(loc="upper right", fontsize=7)

    # (e) latency ---------------------------------------------------------------------
    ax_lat.set_title("One-way latency of each path")

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        # waterfall
        ax_wf.cla()
        ax_wf.set_title(f"Downlink budget ({v['band']}-band, {v['orbit']}): where the decibels go")
        steps = [("Sat EIRP", v["eirp"]), ("FSPL", -r["ld"]), ("Rain", -r["a_d"]), ("Atm + point", -(r["atm"] +
                 r["point"])), ("G/T", r["gt"]), ("−k (228.6)", 228.6)]
        level, xs = 0.0, []
        for i, (lab, val) in enumerate(steps):
            col = C.COL["good"] if val >= 0 else C.COL["bad"]
            ax_wf.bar(i, val, bottom=level, color=col, width=0.62, alpha=0.85)
            ax_wf.text(i, level + val + (4 if val >= 0 else -4), f"{val:+.1f}", ha="center",
                       va="bottom" if val >= 0 else "top", fontsize=7.5, color=C.INK)
            if i:
                ax_wf.plot([i - 1.31, i - 0.31], [level, level], color=C.MUTED, lw=0.8)
            level += val
            xs.append(lab)
        ax_wf.bar(len(steps), r["cn0_d"], color=SA_C, width=0.62)
        ax_wf.text(len(steps), r["cn0_d"] + 4, f"{r['cn0_d']:.1f}\ndB-Hz", ha="center", fontsize=7.5)
        ax_wf.bar(len(steps) + 1, r["cn0"], color=SA_C, width=0.62, alpha=0.6)
        ax_wf.text(len(steps) + 1, r["cn0"] + 4, f"{r['cn0']:.1f}\n(+uplink)", ha="center", fontsize=7.5)
        need = C.SAT["req_ebn0"] + 10 * math.log10(v["rate"] * 1e3)
        ax_wf.axhline(need, color=C.COL["warn"], ls="--", lw=1.2)
        ax_wf.text(-0.4, need + 12, f"C/N0 needed for {v['rate']:.0f} kbps = {need:.1f} dB-Hz",
                   fontsize=7.5, color=C.COL["warn"], ha="left")
        ax_wf.set_xticks(range(len(steps) + 2), xs + ["C/N0 down", "C/N0 total"], fontsize=7.5)
        ax_wf.set(ylabel="dB", ylim=(-220, 290))
        # rain + margin curves
        for line, (bn, b) in zip(rain_curves, M.BANDS.items()):
            line.set_ydata([M.rain_attenuation(x, b["fd"], b["k"], b["a"], v["elev"])[0] for x in rr])
        op_rain.set_data([v["rain"]], [min(r["a_d"], 39.5)])
        lo = 0
        for bn, line in mar_lines.items():
            m = [M.satellite_layer(rain=x, band=bn, orbit=v["orbit"], elev=v["elev"], eirp_dbw=v["eirp"],
                                   dish_m=v["dish"], rate_kbps=v["rate"], hpa_w=v["hpa"])["margin"] for x in rr[::4]]
            line.set_data(rr[::4], m)
            lo = min(lo, min(m))
        ax_mar.set_ylim(max(lo - 3, -40), 45)
        op_mar.set_data([v["rain"]], [r["margin"]])
        # latency bars
        ax_lat.cla()
        ax_lat.set_title("One-way latency of each path")
        geo = M.satellite_layer(orbit="GEO", elev=v["elev"])["delay_ms"]
        leo = M.satellite_layer(orbit="LEO", elev=v["elev"])["delay_ms"]
        items = [("Satellite GEO", geo + 10, SA_C), ("Satellite LEO", leo + 15, SA_C), ("Mobile (4G)", 30, C.COL[C.L_MO]),
                 ("UAV cell", 35, C.COL[C.L_UAV]), ("LoRa mesh (3 hops)", 3 * 260, C.COL[C.L_MESH]),
                 ("Analog radio", 1, C.COL[C.L_AN])]
        for i, (lab, ms, col) in enumerate(items):
            hl = (lab.endswith(v["orbit"]))
            ax_lat.barh(i, ms, color=col, alpha=1 if hl else 0.45, height=0.62)
            ax_lat.text(ms * 1.08 + 0.5, i, f"{ms:.0f} ms", va="center", fontsize=7.5, color=C.INK)
        ax_lat.set_xscale("log")
        ax_lat.set_yticks(range(len(items)), [i[0] for i in items], fontsize=7.5)
        ax_lat.set(xlim=(0.5, 5000), xlabel="ms (log scale)")
        ax_lat.invert_yaxis()
        ax_lat.grid(axis="y", visible=False)
        ro.set_text(
            f"LIVE RESULTS ({v['band']}-band {v['orbit']})\n"
            f"slant range {r['d']:,.0f} km · delay {r['delay_ms']:.0f} ms\n"
            f"FSPL up {r['lu']:.1f} / down {r['ld']:.1f} dB\n"
            f"rain fade {r['a_d']:.1f} dB · G/T {r['gt']:.1f} dB/K\n"
            f"C/N0 {r['cn0']:.1f} dB-Hz · Eb/N0 {r['ebn0']:.1f} dB\n"
            f"margin {r['margin']:+.1f} dB · reach {r['reach']:.0%}")
        ro.set_color(status_colour(r["p_link"]))
        cloud.set_alpha(min(0.9, v["rain"] / 120))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=3)
    ctl.slider("rain", "Rain rate (mm/h)", 0, 150, v["rain"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("elev", "Elevation angle (°)", 10, 90, v["elev"], step=1, fmt="%.0f")
    ctl.slider("eirp", "Satellite EIRP (dBW)", 30, 60, v["eirp"], step=0.5, fmt="%.1f", color=SA_C)
    ctl.slider("dish", "Dish diameter (m)", 0.45, 3.0, v["dish"], step=0.05, fmt="%.2f", color=SA_C)
    ctl.slider("rate", "Data rate (kbps)", 32, 2048, v["rate"], step=32, fmt="%.0f", color=SA_C)
    ctl.slider("hpa", "Terminal HPA (W)", 1, 100, v["hpa"], step=1, fmt="%.0f", color=SA_C)
    ctl.radio("band", "Band", ["C", "Ku", "Ka"], v["band"], [0.595, 0.125, 0.06, 0.08])
    ctl.radio("orbit", "Orbit", ["GEO", "LEO"], v["orbit"], [0.665, 0.125, 0.06, 0.08])
    ctl.reset_button([0.595, 0.045, 0.13, 0.03], "↺  Reset to red dots")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        r = st["r"]
        geo = _sat_pos(v["elev"], 6.61)
        geo_dot.set_data([geo[0]], [geo[1]])
        ang = np.radians(frame * 2.2 + np.arange(6) * 60)
        leo = np.c_[1.45 * np.cos(ang), 1.45 * np.sin(ang)]
        leo_dots.set_data(leo[:, 0], leo[:, 1])
        if v["orbit"] == "GEO":
            sat = geo
            speed = 0.012
        else:
            vis = leo[leo[:, 1] > 0.9]
            sat = vis[np.argmax(vis[:, 1])] if len(vis) else _sat_pos(v["elev"], 1.45)
            speed = 0.05
        alive = r["margin"] > 0
        col = SA_C if alive else C.COL["bad"]
        link_up.set_data([0, sat[0]], [1, sat[1]])
        link_dn.set_data([sat[0], gw[0]], [sat[1], gw[1]])
        link_up.set_color(col)
        link_dn.set_color(col)
        link_up.set_linestyle("-" if alive else ":")
        st["pulse"] = (st["pulse"] + speed) % 1
        pts = []
        for k in range(3):
            u = (st["pulse"] + k / 3) % 1
            if u < 0.5:
                pts.append(np.array([0, 1]) + (sat - np.array([0, 1])) * (u / 0.5))
            elif alive:
                pts.append(sat + (gw - sat) * ((u - 0.5) / 0.5))
        pts = np.array(pts) if pts else np.zeros((0, 2))
        pulses.set_data(pts[:, 0], pts[:, 1])
        pulses.set_color(C.INK if alive else C.COL["bad"])
        n = int(min(40, v["rain"] / 3))
        dr = st["drops"]
        dr[:, 1] = (dr[:, 1] + 0.08) % 1
        x = -0.4 + 1.5 * dr[:n, 0]
        y = 1.8 - 0.8 * dr[:n, 1]
        rain_lines.set_segments([[(a, b), (a - 0.03, b - 0.15)] for a, b in zip(x, y)])
        orb_txt.set_text(f"{v['orbit']}: {r['d']:,.0f} km, {r['delay_ms']:.0f} ms\n"
                         f"{'LINK UP' if alive else 'LINK LOST (rain fade)'}")
        orb_txt.set_color(C.COL["good"] if alive else C.COL["bad"])

    return fig, step, ctl
