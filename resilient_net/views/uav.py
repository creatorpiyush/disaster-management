"""SUPPLEMENTARY LAYER A - UAV aerial base station (drone / tethered cell on wings).

An optional extension that can be deployed alongside the three required layers. It uses the
air-to-ground channel model of Al-Hourani et al. (2014) to size coverage and the best altitude.
"""
import math

import numpy as np
from matplotlib.patches import Rectangle, Polygon, Circle

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

UA_C = C.COL[C.L_UAV]
ENV_COL = {"Suburban": C.COL[C.L_MO], "Urban": C.COL[C.L_UAV], "Dense urban": C.COL[C.L_AN],
           "High-rise urban": C.COL[C.L_MESH]}
TITLE = "Supplementary layer A · UAV aerial base station"
CITY_KM = 10.0


def defaults():
    u = C.UAV
    return dict(h=u["h_m"], ptx=u["ptx_dbm"], n=u["n_uav"], wind=10.0, limit=u["wind_limit"],
                noise=C.STORM["noise_rise"], env=u["env"])


def evaluate(v):
    return M.uav_layer(h_m=v["h"], f_ghz=C.UAV["f_ghz"], ptx_dbm=v["ptx"], rx_sens_dbm=C.UAV["rx_sens_dbm"],
                       env=v["env"], n_uav=int(v["n"]), wind=v["wind"], wind_limit=v["limit"], noise_rise=v["noise"],
                       city_km2=CITY_KM ** 2)


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    a, b, el, en = M.UAV_ENV[v["env"]]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_UAV])
    ui.note("Optional extension. This layer is not one of the three required layers. It is included as an "
            "additional option that could complement them: a drone or tethered aerostat carrying a small "
            "cell can restore coverage over areas where towers are down, once the wind drops. It is "
            "backhauled through the satellite layer.")
    ui.calc("Air-to-ground LoS probability", "P_LoS(θ) = 1 / (1 + a·exp(−b(θ − a)))",
            f"{v['env']}: a = {a}, b = {b}", "θ = elevation angle seen by the user")
    ui.calc("Mean path loss", "PL = FSPL(d) + P_LoS·η_LoS + (1 − P_LoS)·η_NLoS", f"η_LoS = {el} dB, η_NLoS = {en} dB",
            "(Al-Hourani et al., 2014)")
    ui.calc("Maximum allowed path loss", "PLmax = Pt − (sensitivity + storm noise)",
            f"{v['ptx']:.0f} − ({C.UAV['rx_sens_dbm']:.0f} + {v['noise']:.1f})", f"{r['pl_max']:.1f}", "dB")
    ui.calc("Coverage radius at h", "largest r with PL(h, r) ≤ PLmax", f"h = {v['h']:.0f} m",
            f"{r['radius_m'] / 1000:.2f}", "km")
    h_opt, r_opt, _, _ = M.uav_optimal_altitude(C.UAV["f_ghz"], v["env"], r["pl_max"])
    ui.calc("Optimal altitude", "h* = argmax R(h)", "", f"{h_opt:.0f} m → R = {r_opt / 1000:.2f} km",
            "(theory; drones are usually limited to ~120–400 m)")
    ui.calc("Area served", "A = N·π·R²", f"{int(v['n'])} × π × {r['radius_m'] / 1000:.2f}²", f"{r['area_km2']:.1f}",
            f"km² of {CITY_KM ** 2:.0f} km²")
    ui.calc("Flight availability", "p_fly = 1 / (1 + exp((wind − limit)/2))",
            f"wind {v['wind']:.0f} m/s, limit {v['limit']:.0f} m/s", f"{r['fly']:.1%}")
    ui.bar("Citizens reached (two-way)", r["reach"], ui.LAYER_TINT[C.L_UAV])
    return r


def build():
    v = defaults()
    rng = np.random.default_rng(4)
    users = rng.uniform(0, CITY_KM, (260, 2))
    st = dict(r=evaluate(v))
    fig = new_figure(TITLE, "Optional extension that may complement the required layers: an aerial small cell "
                            "flown over damaged districts (air-to-ground channel, Al-Hourani 2014)",
                     "SUPPLEMENTARY · OPTIONAL")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_side, ax_top, ax_pl = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_alt, ax_los, ax_wind = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    # (a) side view --------------------------------------------------------------
    ax_side.set_title("Side view: drone, buildings and radio paths")
    ax_side.set(xlim=(-3, 3), ylim=(0, 1.2), xlabel="ground distance (km)", ylabel="height (km)")
    bx = np.linspace(-2.9, 2.8, 26)
    bh = rng.uniform(0.02, 0.09, len(bx))
    for x, hgt in zip(bx, bh):
        ax_side.add_patch(Rectangle((x, 0), 0.17, hgt, fc="#2b2e33", ec="#3b3f45", lw=0.6))
    cone = Polygon([[0, 0], [0, 0], [0, 0]], closed=True, fc=UA_C, alpha=0.12, ec="none")
    ax_side.add_patch(cone)
    rays = ax_side.vlines([], [], [], lw=1)
    drone, = ax_side.plot([], [], marker=(4, 0, 45), ms=14, color=UA_C, mec=C.INK, ls="none")
    rotor, = ax_side.plot([], [], "_", ms=22, color=C.INK2, mew=2)
    side_txt = ax_side.text(0.02, 0.96, "", transform=ax_side.transAxes, va="top", fontsize=7.5)
    gusts = ax_side.quiver(np.full(5, -2.6), np.linspace(0.35, 1.05, 5), np.ones(5), np.zeros(5), color=C.MUTED,
                           scale=1, scale_units="xy", width=0.004)
    ux = np.linspace(-2.7, 2.7, 13)

    # (b) top view ---------------------------------------------------------------
    ax_top.set_aspect("equal")
    ax_top.set(xlim=(0, CITY_KM), ylim=(0, CITY_KM), title="Top view: drones over the city", xlabel="km", ylabel="km")
    sc_users = ax_top.scatter(users[:, 0], users[:, 1], s=8, color=C.MUTED)
    circles = []
    home = [(2.5, 2.5), (7.5, 7.5), (2.5, 7.5), (7.5, 2.5), (5, 5), (5, 1.5), (5, 8.5), (1.5, 5), (8.5, 5),
            (1.2, 1.2), (8.8, 8.8), (1.2, 8.8)]
    drones_top, = ax_top.plot([], [], marker=(4, 0, 45), ms=9, color=UA_C, mec=C.INK, ls="none")
    top_txt = ax_top.text(0.02, 0.02, "", transform=ax_top.transAxes, fontsize=7.5, color=C.INK,
                          bbox=dict(fc=C.PANEL, ec="none", alpha=0.8))

    # (c) path loss vs distance -------------------------------------------------------
    rr = np.linspace(10, 8000, 300)
    l_pl, = ax_pl.plot([], [], color=UA_C, lw=2, label="mean path loss")
    l_los, = ax_pl.plot([], [], color=C.INK2, lw=1, ls="--", label="pure LoS / NLoS bounds")
    l_nlos, = ax_pl.plot([], [], color=C.INK2, lw=1, ls="--")
    l_max = ax_pl.axhline(0, color=C.COL["bad"], lw=1.2)
    r_line = ax_pl.axvline(0, color=UA_C, lw=1, ls=":")
    pl_txt = ax_pl.text(0.97, 0.05, "", transform=ax_pl.transAxes, ha="right", fontsize=7.5)
    ax_pl.set(title="Path loss vs ground distance", xlabel="ground distance (km)", ylabel="path loss (dB)",
              xlim=(0, 8), ylim=(70, 150))
    ax_pl.legend(loc="upper left", fontsize=7)

    # (d) radius vs altitude ----------------------------------------------------------
    l_alt, = ax_alt.plot([], [], color=UA_C, lw=2)
    op_alt, = ax_alt.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    best_alt, = ax_alt.plot([], [], "*", ms=15, color=UA_C, mec=C.INK)
    ax_alt.axvspan(0, 120, color=C.COL["good"], alpha=0.08)
    ax_alt.text(130, 0.2, "typical drone\nlimit 120 m", fontsize=7, color=C.COL["good"])
    alt_txt = ax_alt.text(0.97, 0.05, "", transform=ax_alt.transAxes, ha="right", fontsize=7.5)
    ax_alt.set(title="Coverage radius vs altitude (★ = optimum)", xlabel="altitude h (m)",
               ylabel="coverage radius (km)", xlim=(0, 3000))

    # (e) LoS probability ---------------------------------------------------------------
    th = np.linspace(0, 90, 200)
    los_lines = {}
    for env, col in ENV_COL.items():
        los_lines[env], = ax_los.plot(th, M.p_los(th, env), color=col, lw=1.6, label=env)
    op_los, = ax_los.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)
    ax_los.set(title="Line-of-sight probability vs elevation angle", xlabel="elevation angle θ (°)",
               ylabel="P(LoS)", ylim=(0, 1.02), xlim=(0, 90))
    ax_los.legend(loc="lower right", fontsize=7)

    # (f) wind ------------------------------------------------------------------------------
    w = np.linspace(0, 50, 200)
    l_fly, = ax_wind.plot([], [], color=UA_C, lw=2)
    op_wind, = ax_wind.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_wind.axvspan(33, 50, color=C.COL["bad"], alpha=0.08)
    ax_wind.text(34, 0.9, "cyclone-force\nwind", fontsize=7, color=C.COL["bad"])
    ax_wind.set(title="Can the drone fly? (availability vs wind)", xlabel="sustained wind (m/s)",
                ylabel="probability of flying", ylim=(-0.02, 1.05), xlim=(0, 50))
    wind_txt = ax_wind.text(0.03, 0.08, "", transform=ax_wind.transAxes, fontsize=7.5)

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        a, b, el, en = M.UAV_ENV[v["env"]]
        pl = M.uav_pathloss(v["h"], rr, C.UAV["f_ghz"], v["env"])
        fs = 20 * np.log10(4 * np.pi * C.UAV["f_ghz"] * 1e9 * np.hypot(v["h"], rr) / M.C_LIGHT)
        l_pl.set_data(rr / 1000, pl)
        l_los.set_data(rr / 1000, fs + el)
        l_nlos.set_data(rr / 1000, fs + en)
        l_max.set_ydata([r["pl_max"]] * 2)
        r_line.set_xdata([r["radius_m"] / 1000] * 2)
        pl_txt.set_text(f"PLmax = {r['pl_max']:.0f} dB → R = {r['radius_m'] / 1000:.2f} km")
        h_opt, r_opt, hs, rs = M.uav_optimal_altitude(C.UAV["f_ghz"], v["env"], r["pl_max"])
        l_alt.set_data(hs, rs / 1000)
        ax_alt.set_ylim(0, max(rs.max() / 1000 * 1.15, 0.5))
        ax_alt.set_xlim(0, max(3000, min(h_opt * 1.3, 5000)))
        op_alt.set_data([v["h"]], [r["radius_m"] / 1000])
        best_alt.set_data([h_opt], [r_opt / 1000])
        alt_txt.set_text(f"optimum h* = {h_opt:.0f} m, R = {r_opt / 1000:.2f} km\n"
                         f"edge angle θ* ≈ {math.degrees(math.atan2(h_opt, r_opt)):.1f}°")
        for env, ln in los_lines.items():
            ln.set_linewidth(3 if env == v["env"] else 1.2)
            ln.set_alpha(1 if env == v["env"] else 0.45)
        theta_edge = math.degrees(math.atan2(v["h"], max(r["radius_m"], 1)))
        op_los.set_data([theta_edge], [float(M.p_los(theta_edge, v["env"]))])
        l_fly.set_data(w, 1 / (1 + np.exp((w - v["limit"]) / 2)))
        op_wind.set_data([v["wind"]], [r["fly"]])
        wind_txt.set_text(f"limit {v['limit']:.0f} m/s → p_fly = {r['fly']:.0%}\n"
                          "tethered drones tolerate more wind")
        for c in circles:
            c.remove()
        circles.clear()
        R = r["radius_m"] / 1000
        span = max(3.0, R * 1.15)
        ax_side.set_xlim(-span, span)
        ax_side.set_ylim(0, max(0.6, v["h"] / 1000 * 1.35))
        st["ux"] = np.linspace(-span * 0.9, span * 0.9, 13)
        for (x, y) in home[:int(v["n"])]:
            c = Circle((x, y), R, fc=UA_C, alpha=0.13 if r["fly"] > 0.5 else 0.03, ec=UA_C, lw=1)
            ax_top.add_patch(c)
            circles.append(c)
        d = np.min([np.hypot(users[:, 0] - x, users[:, 1] - y) for (x, y) in home[:int(v["n"])]], axis=0)
        covered = (d <= R) & (r["fly"] > 0.5)
        sc_users.set_color(np.where(covered, UA_C, "#4a4a46"))
        top_txt.set_text(f"{covered.mean():.0%} of users inside a drone cell")
        ro.set_text(
            f"LIVE RESULTS ({v['env']})\n"
            f"altitude {v['h']:.0f} m · {int(v['n'])} drones\n"
            f"PLmax {r['pl_max']:.0f} dB · radius {R:.2f} km\n"
            f"area {r['area_km2']:.1f} km² of {CITY_KM ** 2:.0f} km²\n"
            f"p_fly {r['fly']:.0%} (wind {v['wind']:.0f} m/s)\n"
            f"Citizens reached (two-way): {r['reach']:.0%}")
        ro.set_color(status_colour(r["reach"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=3)
    ctl.slider("h", "Altitude h (m)", 20, 2000, v["h"], step=10, fmt="%.0f", color=UA_C)
    ctl.slider("ptx", "User Tx power (dBm)", 10, 33, v["ptx"], step=1, fmt="%.0f", color=UA_C)
    ctl.slider("n", "Number of drones", 1, 12, v["n"], step=1, fmt="%.0f", color=UA_C)
    ctl.slider("wind", "Wind after landfall (m/s)", 0, 50, v["wind"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("limit", "Drone wind limit (m/s)", 8, 30, v["limit"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 25, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.radio("env", "Environment", list(M.UAV_ENV), v["env"], [0.595, 0.075, 0.13, 0.13])
    ctl.reset_button([0.595, 0.038, 0.13, 0.03], "↺  Reset to red dots")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        r = st["r"]
        flying = r["fly"] > 0.5
        sway = 0.04 * v["wind"] / 20 * math.sin(frame * 0.35)
        hk = v["h"] / 1000 if flying else 0.03
        x0 = sway if flying else 0.0
        y0 = hk + (0.01 * math.sin(frame * 0.25) if flying else 0)
        drone.set_data([x0], [y0])
        rotor.set_data([x0], [y0 + 0.03])
        rotor.set_alpha(0.3 + 0.7 * abs(math.sin(frame * 1.7)) if flying else 0.3)
        R = r["radius_m"] / 1000
        cone.set_xy([[x0, y0], [x0 - R, 0], [x0 + R, 0]] if flying else [[0, 0], [0, 0], [0, 0]])
        if flying:
            seg, cols = [], []
            for u in st["ux"]:
                theta = math.degrees(math.atan2(y0, abs(u - x0) + 1e-6))
                ok = abs(u - x0) <= R and rng.random() < float(M.p_los(theta, v["env"])) + 0.2
                seg.append([(x0, y0), (u, 0.02)])
                cols.append(C.COL["good"] if ok else C.COL["bad"])
            rays.set_segments(seg)
            rays.set_color(cols)
            rays.set_alpha(0.55)
        else:
            rays.set_segments([])
        side_txt.set_text(f"FLYING at {v['h']:.0f} m — radius {R:.2f} km" if flying else
                          f"GROUNDED — wind {v['wind']:.0f} m/s > limit {v['limit']:.0f} m/s")
        side_txt.set_color(C.COL["good"] if flying else C.COL["bad"])
        gusts.set_UVC(np.full(5, 0.02 * v["wind"] * (1 + 0.2 * math.sin(frame * 0.5))), np.zeros(5))
        pos = [(x + 0.25 * math.cos(frame * 0.08 + i), y + 0.25 * math.sin(frame * 0.08 + i))
               for i, (x, y) in enumerate(home[:int(v["n"])])]
        p = np.array(pos)
        drones_top.set_data(p[:, 0], p[:, 1])
        drones_top.set_alpha(1 if flying else 0.35)

    return fig, step, ctl
