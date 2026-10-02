"""Layer 3 - satellite backup (GEO/LEO link budget with rain fade). Unit IV."""
import math
from functools import lru_cache
from types import SimpleNamespace

import numpy as np
from matplotlib.patches import Circle, Ellipse

from .. import config as C, models as M, terrain, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

SA_C = C.COL[C.L_SA]
BAND_COL = {"C": C.COL[C.L_MO], "Ku": C.COL[C.L_SA], "Ka": C.COL[C.L_UAV]}
TITLE = "Layer 3: Satellite backup"
SITES = {"Gangtok ridge": "Gangtok", "Singtam valley": "Singtam", "Dikchu gorge": "Dikchu"}
LEO_MIN_EL = 25.0
LEO_PASSES = [(200, 80, 0.004, 0.0), (120, 45, 0.005, 0.3), (250, 35, 0.006, 0.55), (300, 60, 0.0045, 0.8),
              (20, 30, 0.0055, 0.15), (160, 28, 0.005, 0.65)]  # (start azimuth, max elevation, speed, phase)


@lru_cache(maxsize=None)
def site_info(site):
    T = terrain.load()
    p = next(q for q in T.places if q["name"] == SITES[site])
    az, sky = T.skyline(p["x"], p["y"], 3.0, 2.0)
    az_geo, el_geo = terrain.geo_look_angles(*T.site_latlon(p["x"], p["y"]))
    return dict(alt=float(T.elev(p["x"], p["y"])), az=az, sky=sky, az_geo=az_geo, el_geo=el_geo)


def horizon_at(info, az_deg):
    return float(np.interp(az_deg % 360, np.r_[info["az"], 360], np.r_[info["sky"], info["sky"][0]]))


def blocked(v):
    info = site_info(v["site"])
    if v["orbit"] == "GEO":
        return 1.0 if horizon_at(info, info["az_geo"]) >= v["elev"] else 0.0
    open_ = np.mean(np.clip((60 - np.maximum(info["sky"], LEO_MIN_EL)) / (60 - LEO_MIN_EL), 0, 1))
    return float(1 - open_)


def defaults():
    s = C.SAT
    return dict(rain=C.STORM["rain"], elev=s["elev"], eirp=s["eirp_dbw"], dish=s["dish_m"], rate=s["rate_kbps"],
                hpa=s["hpa_w"], band=s["band"], orbit=s["orbit"], site="Gangtok ridge")


def evaluate(v):
    return M.satellite_layer(rain=v["rain"], band=v["band"], orbit=v["orbit"], elev=v["elev"], eirp_dbw=v["eirp"],
                             dish_m=v["dish"], rate_kbps=v["rate"], hpa_w=v["hpa"], wind=C.STORM["wind"],
                             req_ebn0=C.SAT["req_ebn0"], t_sys=C.SAT["t_sys"],
                             h_station=site_info(v["site"])["alt"] / 1000, block=blocked(v))


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    b = M.BANDS[v["band"]]
    alt = M.ORBITS[v["orbit"]]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_SA])
    ui.note("Why it's here: nothing on the ground except the terminal itself has to survive. Backhaul for "
            "shelters, hospitals and the EOC once fibre and towers are gone. Weak spot: rain fade at Ku/Ka.")
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
    info = site_info(v["site"])
    ui.sub(f"Terrain at the terminal: {v['site']} ({info['alt']:.0f} m above sea level, real SRTM skyline)")
    ui.calc("Look angles to a GEO satellite at 83° E", "El = atan((cos γ − Re/(Re+h)) / sin γ),  cos γ = cos φ·cos Δλ",
            f"φ = 27.3° N, Δλ = {83 - 88.6:.1f}°", f"El = {info['el_geo']:.1f}°, Az = {info['az_geo']:.0f}°")
    hz = horizon_at(info, info["az_geo"])
    ui.calc("Ridge height in that direction", "max over the path of atan((z − z0)/d − d/(2kRe))", "",
            f"{hz:.1f}°", "→ " + ("clear sky to the satellite" if hz < v["elev"] else "BLOCKED by the ridge"))
    ui.calc("Slant path through the rain", "Ls = (hR − hs) / sin El   (ITU-R P.839 rain height)",
            f"({M.RAIN_HEIGHT_KM} − {info['alt'] / 1000:.2f}) / sin {v['elev']:.0f}°",
            f"{(M.RAIN_HEIGHT_KM - info['alt'] / 1000) / math.sin(math.radians(v['elev'])):.2f}",
            f"km  (a sea-level station would have {M.RAIN_HEIGHT_KM / math.sin(math.radians(v['elev'])):.2f} km)")
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
    # where the satellite sits on the drawing, station at (0, 1)
    e = math.radians(elev)
    d = np.array([math.cos(e), math.sin(e)])
    p = np.array([0.0, 1.0])
    bq = 2 * p.dot(d)
    cq = p.dot(p) - radius ** 2
    t = (-bq + math.sqrt(bq ** 2 - 4 * cq)) / 2
    return p + t * d


GW = np.array([math.cos(math.radians(55)), math.sin(math.radians(55))])  # gateway position on the drawing


def _setup_orbit(ax):
    ax.set_aspect("equal")
    ax.set(xlim=(-2.6, 7.0), ylim=(-1.9, 7.2), xticks=[], yticks=[])
    ax.set_title("Live link geometry (LEO radius exaggerated)")
    ax.add_patch(Circle((0, 0), 1, fc="#1e3a5f", ec=C.COL[C.L_MO], lw=1.2))
    ax.add_patch(Circle((0, 0), 6.61, fc="none", ec=C.MUTED, lw=0.8, ls=":"))
    ax.add_patch(Circle((0, 0), 1.45, fc="none", ec=C.MUTED, lw=0.8, ls=":"))
    ax.text(-2.4, 6.0, "GEO 35 786 km", fontsize=7, color=C.MUTED)
    ax.text(-1.6, -1.95, "LEO 550 km", fontsize=7, color=C.MUTED)
    ax.plot([0], [1], "s", color=C.INK, ms=7)
    ax.text(-0.15, 1.15, "terminal", fontsize=7, color=C.INK, ha="right")
    ax.plot(*GW, "s", color=C.INK2, ms=6)
    ax.text(GW[0] + 0.15, GW[1] - 0.15, "gateway / EOC", fontsize=7, color=C.INK2)
    o = SimpleNamespace()
    o.geo, = ax.plot([], [], "D", color=SA_C, ms=9)
    o.leo, = ax.plot([], [], "o", color=SA_C, ms=5)
    o.up, = ax.plot([], [], color=SA_C, lw=1.2, alpha=0.6)
    o.down, = ax.plot([], [], color=SA_C, lw=1.2, alpha=0.6)
    o.pulses, = ax.plot([], [], "o", color=C.INK, ms=4)
    o.cloud = Ellipse((0.35, 1.9), 1.6, 0.5, fc="#5c6670", ec="none", alpha=0.0)
    ax.add_patch(o.cloud)
    o.rain = ax.vlines([], [], [], color="#8fb4d9", lw=0.8, alpha=0.7)
    o.txt = ax.text(0.98, 0.03, "", transform=ax.transAxes, va="bottom", ha="right", fontsize=7.5, color=C.INK)
    return o


def _setup_rain(ax, rr, elev):
    curves = []
    for bn, col in BAND_COL.items():
        b = M.BANDS[bn]
        fade = [M.rain_attenuation(x, b["fd"], b["k"], b["a"], elev, h_station=1.6)[0] for x in rr]
        curves.append(ax.plot(rr, fade, color=col, lw=1.8, label=f"{bn} ({b['fd']:.0f} GHz)")[0])
    op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax.set(title="Rain fade vs rain rate (downlink)", xlabel="rain rate (mm/h)", ylabel="attenuation (dB)",
           xlim=(0, 150), ylim=(0, 40))
    ax.legend(loc="upper left", fontsize=7)
    return curves, op


def _setup_margin(ax):
    lines = {bn: ax.plot([], [], color=col, lw=1.8, label=f"{bn}-band")[0] for bn, col in BAND_COL.items()}
    ax.axhline(0, color=C.COL["bad"], lw=1.2, ls="--")
    ax.text(2, 0.8, "link lost below 0 dB", fontsize=7, color=C.COL["bad"])
    op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax.set(title="Link margin vs rain rate (each band)", xlabel="rain rate (mm/h)", ylabel="Eb/N0 margin (dB)",
           xlim=(0, 150), ylim=(-30, 45))
    ax.legend(loc="upper right", fontsize=7)
    return lines, op


def _setup_sky(ax):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_facecolor("#16202b")
    ax.set_ylim(0, 90)
    ax.set_yticks([30, 60, 65], ["60°", "30°", ""], fontsize=6.5, color=C.MUTED)
    ax.set_xticks(np.radians([0, 90, 180, 270]), ["N", "E", "S", "W"], fontsize=7.5, color=C.INK2)
    ax.grid(color="#2c3a48", lw=0.6)
    ax.plot(np.linspace(0, 2 * np.pi, 120), np.full(120, 90 - LEO_MIN_EL), color=C.MUTED, lw=0.8, ls=":")
    geo, = ax.plot([], [], "D", ms=9, color=SA_C, mec=C.INK, zorder=6)
    leo = ax.scatter([], [], s=26, zorder=6)
    return geo, leo


def _draw_waterfall(ax, v, r):
    ax.cla()
    ax.set_title(f"Downlink budget ({v['band']}-band, {v['orbit']}): where the decibels go")
    steps = [("Sat EIRP", v["eirp"]), ("FSPL", -r["ld"]), ("Rain", -r["a_d"]),
             ("Atm + point", -(r["atm"] + r["point"])), ("G/T", r["gt"]), ("−k (228.6)", 228.6)]
    level = 0.0
    for i, (_, val) in enumerate(steps):
        ax.bar(i, val, bottom=level, color=C.COL["good"] if val >= 0 else C.COL["bad"], width=0.62, alpha=0.85)
        ax.text(i, level + val + (4 if val >= 0 else -4), f"{val:+.1f}", ha="center",
                va="bottom" if val >= 0 else "top", fontsize=7.5, color=C.INK)
        if i:
            ax.plot([i - 1.31, i - 0.31], [level, level], color=C.MUTED, lw=0.8)
        level += val
    n = len(steps)
    ax.bar(n, r["cn0_d"], color=SA_C, width=0.62)
    ax.text(n, r["cn0_d"] + 4, f"{r['cn0_d']:.1f}\ndB-Hz", ha="center", fontsize=7.5)
    ax.bar(n + 1, r["cn0"], color=SA_C, width=0.62, alpha=0.6)
    ax.text(n + 1, r["cn0"] + 4, f"{r['cn0']:.1f}\n(+uplink)", ha="center", fontsize=7.5)
    need = C.SAT["req_ebn0"] + 10 * math.log10(v["rate"] * 1e3)
    ax.axhline(need, color=C.COL["warn"], ls="--", lw=1.2)
    ax.text(-0.4, need + 12, f"C/N0 needed for {v['rate']:.0f} kbps = {need:.1f} dB-Hz",
            fontsize=7.5, color=C.COL["warn"], ha="left")
    ax.set_xticks(range(n + 2), [lab for lab, _ in steps] + ["C/N0 down", "C/N0 total"], fontsize=7.5)
    ax.set(ylabel="dB", ylim=(-220, 290))


def _margin_curve(v, band, rain):
    h = site_info(v["site"])["alt"] / 1000
    return [M.satellite_layer(rain=x, band=band, orbit=v["orbit"], elev=v["elev"], eirp_dbw=v["eirp"],
                              dish_m=v["dish"], rate_kbps=v["rate"], hpa_w=v["hpa"], h_station=h)["margin"]
            for x in rain]


def _readout_text(v, r, info):
    return (f"LIVE RESULTS ({v['band']}-band {v['orbit']})\n"
            f"slant range {r['d']:,.0f} km · delay {r['delay_ms']:.0f} ms\n"
            f"FSPL up {r['lu']:.1f} / down {r['ld']:.1f} dB\n"
            f"rain fade {r['a_d']:.1f} dB · G/T {r['gt']:.1f} dB/K\n"
            f"C/N0 {r['cn0']:.1f} dB-Hz · Eb/N0 {r['ebn0']:.1f} dB\n"
            f"margin {r['margin']:+.1f} dB · reach {r['reach']:.0%}\n"
            f"site {info['alt']:.0f} m · sky blocked {blocked(v):.0%}")


def _pulse_points(phase, sat, alive):
    # 3 dots travelling terminal -> satellite -> gateway (they stop at the sat if the link is down)
    pts = []
    for k in range(3):
        u = (phase + k / 3) % 1
        if u < 0.5:
            pts.append(np.array([0, 1]) + (sat - np.array([0, 1])) * (u / 0.5))
        elif alive:
            pts.append(sat + (GW - sat) * ((u - 0.5) / 0.5))
    return np.array(pts) if pts else np.zeros((0, 2))


def _leo_sky_points(info, frame):
    pts, cols = [], []
    for a0, emax, sp, ph in LEO_PASSES:
        u = (ph + frame * sp) % 1
        az, el = a0 + 180 * u, emax * math.sin(math.pi * u)
        pts.append([math.radians(az), 90 - el])
        cols.append(SA_C if el >= max(LEO_MIN_EL, horizon_at(info, az)) else "#7d7d76")
    return pts, cols


def build():
    v = defaults()
    st = dict(r=evaluate(v), pulse=0.0, drops=np.random.default_rng(2).random((40, 2)), sky_art=None)
    fig = new_figure(TITLE, "GEO / LEO from a hill town: geometry, FSPL, rain fade, link budget, and the real "
                            "skyline in brown", "LAYER 3 (REQUIRED)")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_orb, ax_wf = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1:])
    ax_rain, ax_mar = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])
    ax_sky = fig.add_subplot(gs[1, 2], projection="polar")

    rr = np.linspace(0, 150, 120)
    orb = _setup_orbit(ax_orb)
    ax_wf.set_title("Downlink + total budget: where the decibels go")
    rain_curves, op_rain = _setup_rain(ax_rain, rr, v["elev"])
    mar_lines, op_mar = _setup_margin(ax_mar)
    geo_mk, leo_mk = _setup_sky(ax_sky)
    sky_txt = fig.text(0.0, 0.0, "", fontsize=7.5, color=C.INK)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        info = site_info(v["site"])
        _draw_waterfall(ax_wf, v, r)

        for line, b in zip(rain_curves, M.BANDS.values()):
            line.set_ydata([M.rain_attenuation(x, b["fd"], b["k"], b["a"], v["elev"],
                                               h_station=info["alt"] / 1000)[0] for x in rr])
        op_rain.set_data([v["rain"]], [min(r["a_d"], 39.5)])
        lo = 0
        for bn, line in mar_lines.items():
            m = _margin_curve(v, bn, rr[::4])
            line.set_data(rr[::4], m)
            lo = min(lo, min(m))
        ax_mar.set_ylim(max(lo - 3, -40), 45)
        op_mar.set_data([v["rain"]], [r["margin"]])

        # skyline for the chosen site
        if st["sky_art"] is not None:
            st["sky_art"].remove()
        th = np.radians(np.r_[info["az"], 360])
        sk = np.r_[info["sky"], info["sky"][0]]
        st["sky_art"] = ax_sky.fill_between(th, 90 - sk, 90, color="#6b4f35", alpha=0.95, lw=0, zorder=3)
        ax_sky.set_title(f"Sky from {v['site']} ({info['alt']:.0f} m)", fontsize=9)
        geo_mk.set_data([math.radians(info["az_geo"])], [90 - v["elev"]])
        hz = horizon_at(info, info["az_geo"])
        geo_ok = hz < v["elev"]
        geo_mk.set_color(SA_C if geo_ok else C.COL["bad"])
        pos = ax_sky.get_position()
        sky_txt.set_position((pos.x0 - 0.02, pos.y0 - 0.035))
        sky_txt.set_text(f"GEO ◆ at {v['elev']:.0f}°: ridge {hz:.0f}° → {'clear' if geo_ok else 'BLOCKED'}   ·   "
                         f"LEO ● needs ≥ {LEO_MIN_EL:.0f}° + clear sky")
        sky_txt.set_color(C.COL["good"] if geo_ok else C.COL["bad"])

        ro.set_text(_readout_text(v, r, info))
        ro.set_color(status_colour(r["p_link"]))
        orb.cloud.set_alpha(min(0.9, v["rain"] / 120))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.50, 0.17), cols=2, rows=3)
    ctl.slider("rain", "Rain rate (mm/h)", 0, 150, v["rain"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("elev", "Elevation angle (°)", 10, 90, v["elev"], step=1, fmt="%.0f")
    ctl.slider("eirp", "Satellite EIRP (dBW)", 30, 60, v["eirp"], step=0.5, fmt="%.1f", color=SA_C)
    ctl.slider("dish", "Dish diameter (m)", 0.45, 3.0, v["dish"], step=0.05, fmt="%.2f", color=SA_C)
    ctl.slider("rate", "Data rate (kbps)", 32, 2048, v["rate"], step=32, fmt="%.0f", color=SA_C)
    ctl.slider("hpa", "Terminal HPA (W)", 1, 100, v["hpa"], step=1, fmt="%.0f", color=SA_C)
    ctl.radio("band", "Band", ["C", "Ku", "Ka"], v["band"], [0.525, 0.125, 0.06, 0.08])
    ctl.radio("orbit", "Orbit", ["GEO", "LEO"], v["orbit"], [0.592, 0.125, 0.06, 0.08])
    ctl.radio("site", "Terminal site", list(SITES), v["site"], [0.525, 0.035, 0.127, 0.065])
    ctl.reset_button([0.66, 0.125, 0.068, 0.08], "Reset")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        r = st["r"]
        geo = _sat_pos(v["elev"], 6.61)
        orb.geo.set_data([geo[0]], [geo[1]])
        ang = np.radians(frame * 2.2 + np.arange(6) * 60)
        leo = np.c_[1.45 * np.cos(ang), 1.45 * np.sin(ang)]
        orb.leo.set_data(leo[:, 0], leo[:, 1])
        if v["orbit"] == "GEO":
            sat, speed = geo, 0.012
        else:  # use whichever LEO is highest above the terminal
            vis = leo[leo[:, 1] > 0.9]
            sat = vis[np.argmax(vis[:, 1])] if len(vis) else _sat_pos(v["elev"], 1.45)
            speed = 0.05

        alive = r["margin"] > 0 and blocked(v) < 1
        col = SA_C if alive else C.COL["bad"]
        orb.up.set_data([0, sat[0]], [1, sat[1]])
        orb.down.set_data([sat[0], GW[0]], [sat[1], GW[1]])
        orb.up.set_color(col)
        orb.down.set_color(col)
        orb.up.set_linestyle("-" if alive else ":")
        st["pulse"] = (st["pulse"] + speed) % 1
        pts = _pulse_points(st["pulse"], sat, alive)
        orb.pulses.set_data(pts[:, 0], pts[:, 1])
        orb.pulses.set_color(C.INK if alive else C.COL["bad"])

        n = int(min(40, v["rain"] / 3))
        dr = st["drops"]
        dr[:, 1] = (dr[:, 1] + 0.08) % 1
        x, y = -0.4 + 1.5 * dr[:n, 0], 1.8 - 0.8 * dr[:n, 1]
        orb.rain.set_segments([[(a, b), (a - 0.03, b - 0.15)] for a, b in zip(x, y)])
        why = "ridge blocks the sky" if blocked(v) >= 1 else "rain fade"
        orb.txt.set_text(f"{v['orbit']}: {r['d']:,.0f} km, one-way delay {r['delay_ms']:.0f} ms\n"
                         f"{'LINK UP' if alive else 'LINK LOST (' + why + ')'}")
        pts, cols = _leo_sky_points(site_info(v["site"]), frame)
        leo_mk.set_offsets(pts)
        leo_mk.set_color(cols)
        orb.txt.set_color(C.COL["good"] if alive else C.COL["bad"])

    return fig, step, ctl
