"""Optional layer A - UAV aerial base station (Al-Hourani 2014 channel). Could complement the required layers."""
import math
from types import SimpleNamespace

import numpy as np
from matplotlib.patches import Circle, Polygon

from .. import config as C, models as M, terrain, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

UA_C = C.COL[C.L_UAV]
ENV_COL = {"Suburban": C.COL[C.L_MO], "Urban": C.COL[C.L_UAV], "Dense urban": C.COL[C.L_AN],
           "High-rise urban": C.COL[C.L_MESH]}
TITLE = "Supplementary layer A: UAV aerial base station"
CITY_KM = 10.0
CROP = (-5.0, -6.0)  # SW corner of the 10x10 km top view
PROFILE = ((-7.0, -4.1), (5.0, -4.1))  # west -> east across the Ranipool valley, below Gangtok


def defaults():
    u = C.UAV
    return dict(h=u["h_m"], ptx=u["ptx_dbm"], n=u["n_uav"], wind=8.0, limit=u["wind_limit"],
                noise=C.STORM["noise_rise"], env=u["env"], rain=5.0, alt=u["alt_msl"])


def evaluate(v):
    return M.uav_layer(h_m=v["h"], f_ghz=C.UAV["f_ghz"], ptx_dbm=v["ptx"], rx_sens_dbm=C.UAV["rx_sens_dbm"],
                       env=v["env"], n_uav=int(v["n"]), wind=v["wind"], wind_limit=v["limit"], noise_rise=v["noise"],
                       city_km2=CITY_KM ** 2, alt_msl=v["alt"], rain=v["rain"], endurance_min=C.UAV["endurance_min"])


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    a, b, el, en = M.UAV_ENV[v["env"]]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_UAV])
    ui.note("Optional extension, not one of the three required layers, but it could complement them. "
            "A drone (or tethered aerostat) with a small cell can bring back coverage over valleys whose "
            "sites lost fibre, once the cloudburst passes. Backhaul is via satellite. Gangtok is at ~1600 m "
            "so the air is thin.")
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
    ui.calc("Air density at flight altitude", "ρ/ρ0 = (1 − 2.2558·10⁻⁵·h)^4.2559   (ICAO standard atmosphere)",
            f"h = {v['alt']:.0f} + {v['h']:.0f} m", f"{r['rho']:.3f}")
    ui.calc("Endurance in thin air", "E = E0·√(ρ/ρ0)   (hover power ∝ 1/√ρ)",
            f"{C.UAV['endurance_min']:.0f} min × √{r['rho']:.3f}", f"{r['endurance']:.1f}", "min")
    ui.calc("Time on station", "E / (E + battery swap 12 min)", "", f"{r['on_station']:.0%}")
    ui.calc("Flight availability", "p_fly = 1/(1 + e^((wind − limit·√ρ)/2)) · 1/(1 + e^((rain − 25)/5))",
            f"wind {v['wind']:.0f} m/s, limit {v['limit']:.0f}→{r['limit_eff']:.1f} m/s, rain {v['rain']:.0f} mm/h",
            f"{r['fly']:.1%}")
    ui.bar("Citizens reached (two-way)", r["reach"], ui.LAYER_TINT[C.L_UAV])
    return r


HOMES = [(2.5, 2.5), (7.5, 7.5), (2.5, 7.5), (7.5, 2.5), (5, 5), (5, 1.5), (5, 8.5), (1.5, 5), (8.5, 5),
         (1.2, 1.2), (8.8, 8.8), (1.2, 8.8)]  # where each drone hovers on the top view, in launch order


def _setup_side(ax, TR):
    pd, pz, _, _ = TR.profile(*PROFILE, n=300)
    pz = pz / 1000
    k_floor = int(np.argmin(np.where((pd > 2) & (pd < 8), pz, 9)))  # lowest point = valley floor
    pd = pd - pd[k_floor]
    sv = SimpleNamespace(pd=pd, pz=pz, z_floor=pz[k_floor])
    ax.set_title("Side view: drone over the Ranipool valley (real terrain)")
    ax.fill_between(pd, 0, pz, color="#3a3226", ec="#6b5a43", lw=1, zorder=2)
    ax.set(xlim=(pd[0], pd[-1]), xlabel="distance across the valley (km)", ylabel="altitude above sea (km)")
    sv.cone = Polygon([[0, 0], [0, 0], [0, 0]], closed=True, fc=UA_C, alpha=0.10, ec="none", zorder=1)
    ax.add_patch(sv.cone)
    sv.rays = ax.vlines([], [], [], lw=1, zorder=3)
    sv.drone, = ax.plot([], [], marker=(4, 0, 45), ms=14, color=UA_C, mec=C.INK, ls="none", zorder=5)
    sv.rotor, = ax.plot([], [], "_", ms=22, color=C.INK2, mew=2, zorder=5)
    sv.txt = ax.text(0.02, 0.96, "", transform=ax.transAxes, va="top", fontsize=7.5, zorder=6)
    sv.gusts = ax.quiver(np.full(5, pd[0] + 0.4), np.linspace(sv.z_floor + 0.75, pz.max() + 0.2, 5), np.ones(5),
                         np.zeros(5), color=C.MUTED, scale=1, scale_units="xy", width=0.004, zorder=4)
    sv.ux = np.linspace(pd[0] + 0.5, pd[-1] - 0.5, 15)  # ground users along the profile
    sv.uz = np.interp(sv.ux, pd, pz) + 0.01
    return sv


def _setup_top(ax, TR):
    ax.set_aspect("equal")
    ax.set(xlim=(0, CITY_KM), ylim=(0, CITY_KM), title="Top view: drones over Gangtok and Ranipool",
           xticks=[], yticks=[])
    x0, x1, y0, y1 = TR.extent
    ax.imshow(TR.hillshade(), extent=(x0 - CROP[0], x1 - CROP[0], y0 - CROP[1], y1 - CROP[1]), origin="lower",
              cmap="gray", vmin=-0.4, vmax=1.5, zorder=0)
    for rv in TR.rivers:
        ax.plot(rv["xy"][:, 0] - CROP[0], rv["xy"][:, 1] - CROP[1], color="#4f8fd0", lw=0.8)
    ax.plot([PROFILE[0][0] - CROP[0], PROFILE[1][0] - CROP[0]], [PROFILE[0][1] - CROP[1]] * 2, color=C.INK2,
            lw=0.8, ls="--")
    ax.text(0.2, PROFILE[0][1] - CROP[1] + 0.2, "side-view line", fontsize=6.5, color=C.INK2)
    cit = terrain.scenario()["cit"] - np.array(CROP)
    tv = SimpleNamespace(circles=[])
    tv.users = cit[(cit[:, 0] > 0) & (cit[:, 0] < CITY_KM) & (cit[:, 1] > 0) & (cit[:, 1] < CITY_KM)]
    tv.sc_users = ax.scatter(tv.users[:, 0], tv.users[:, 1], s=8, color=C.MUTED, zorder=3)
    tv.drones, = ax.plot([], [], marker=(4, 0, 45), ms=9, color=UA_C, mec=C.INK, ls="none")
    tv.txt = ax.text(0.02, 0.02, "", transform=ax.transAxes, fontsize=7.5, color=C.INK,
                     bbox=dict(fc=C.PANEL, ec="none", alpha=0.8))
    return tv


def _setup_pathloss(ax):
    pl = SimpleNamespace()
    pl.mean, = ax.plot([], [], color=UA_C, lw=2, label="mean path loss")
    pl.los, = ax.plot([], [], color=C.INK2, lw=1, ls="--", label="pure LoS / NLoS bounds")
    pl.nlos, = ax.plot([], [], color=C.INK2, lw=1, ls="--")
    pl.max = ax.axhline(0, color=C.COL["bad"], lw=1.2)
    pl.radius = ax.axvline(0, color=UA_C, lw=1, ls=":")
    pl.txt = ax.text(0.97, 0.05, "", transform=ax.transAxes, ha="right", fontsize=7.5)
    ax.set(title="Path loss vs ground distance", xlabel="ground distance (km)", ylabel="path loss (dB)",
           xlim=(0, 8), ylim=(70, 150))
    ax.legend(loc="upper left", fontsize=7)
    return pl


def _setup_altitude(ax):
    al = SimpleNamespace()
    al.curve, = ax.plot([], [], color=UA_C, lw=2)
    al.op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    al.best, = ax.plot([], [], "*", ms=15, color=UA_C, mec=C.INK)
    ax.axvspan(0, 120, color=C.COL["good"], alpha=0.08)
    ax.text(130, 0.2, "typical drone\nlimit 120 m", fontsize=7, color=C.COL["good"])
    al.txt = ax.text(0.97, 0.05, "", transform=ax.transAxes, ha="right", fontsize=7.5)
    ax.set(title="Coverage radius vs altitude (★ = optimum)", xlabel="altitude h (m)",
           ylabel="coverage radius (km)", xlim=(0, 3000))
    return al


def _setup_los(ax):
    th = np.linspace(0, 90, 200)
    lines = {env: ax.plot(th, M.p_los(th, env), color=col, lw=1.6, label=env)[0] for env, col in ENV_COL.items()}
    op, = ax.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)
    ax.set(title="Line-of-sight probability vs elevation angle", xlabel="elevation angle θ (°)",
           ylabel="P(LoS)", ylim=(0, 1.02), xlim=(0, 90))
    ax.legend(loc="lower right", fontsize=7)
    return lines, op


def _setup_wind(ax):
    wd = SimpleNamespace()
    wd.curve, = ax.plot([], [], color=UA_C, lw=2)
    wd.op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax.axvspan(20, 50, color=C.COL["bad"], alpha=0.08)
    ax.text(21, 0.9, "storm gusts in\nthe valleys", fontsize=7, color=C.COL["bad"])
    ax.set(title="Can the drone fly? (availability vs wind)", xlabel="sustained wind (m/s)",
           ylabel="probability of flying", ylim=(-0.02, 1.05), xlim=(0, 50))
    wd.txt = ax.text(0.03, 0.08, "", transform=ax.transAxes, fontsize=7.5)
    return wd


def _draw_pathloss(pl, v, r, rr):
    _, _, el, en = M.UAV_ENV[v["env"]]
    fs = 20 * np.log10(4 * np.pi * C.UAV["f_ghz"] * 1e9 * np.hypot(v["h"], rr) / M.C_LIGHT)
    pl.mean.set_data(rr / 1000, M.uav_pathloss(v["h"], rr, C.UAV["f_ghz"], v["env"]))
    pl.los.set_data(rr / 1000, fs + el)
    pl.nlos.set_data(rr / 1000, fs + en)
    pl.max.set_ydata([r["pl_max"]] * 2)
    pl.radius.set_xdata([r["radius_m"] / 1000] * 2)
    pl.txt.set_text(f"PLmax = {r['pl_max']:.0f} dB → R = {r['radius_m'] / 1000:.2f} km")


def _draw_altitude(ax, al, v, r):
    h_opt, r_opt, hs, rs = M.uav_optimal_altitude(C.UAV["f_ghz"], v["env"], r["pl_max"])
    al.curve.set_data(hs, rs / 1000)
    ax.set_ylim(0, max(rs.max() / 1000 * 1.15, 0.5))
    ax.set_xlim(0, max(3000, min(h_opt * 1.3, 5000)))
    al.op.set_data([v["h"]], [r["radius_m"] / 1000])
    al.best.set_data([h_opt], [r_opt / 1000])
    al.txt.set_text(f"optimum h* = {h_opt:.0f} m, R = {r_opt / 1000:.2f} km\n"
                    f"edge angle θ* ≈ {math.degrees(math.atan2(h_opt, r_opt)):.1f}°")


def _draw_top(ax, tv, v, r):
    for c in tv.circles:
        c.remove()
    tv.circles.clear()
    R = r["radius_m"] / 1000
    spots = HOMES[:int(v["n"])]
    for x, y in spots:
        c = Circle((x, y), R, fc=UA_C, alpha=0.13 if r["fly"] > 0.5 else 0.03, ec=UA_C, lw=1)
        ax.add_patch(c)
        tv.circles.append(c)
    d = np.min([np.hypot(tv.users[:, 0] - x, tv.users[:, 1] - y) for x, y in spots], axis=0)
    covered = (d <= R) & (r["fly"] > 0.5)
    tv.sc_users.set_color(np.where(covered, UA_C, "#4a4a46"))
    tv.txt.set_text(f"{covered.mean():.0%} of users inside a drone cell")


def _readout_text(v, r):
    return (f"LIVE RESULTS ({v['env']})\n"
            f"altitude {v['h']:.0f} m · {int(v['n'])} drones\n"
            f"PLmax {r['pl_max']:.0f} dB · radius {r['radius_m'] / 1000:.2f} km\n"
            f"area {r['area_km2']:.1f} km² of {CITY_KM ** 2:.0f} km²\n"
            f"p_fly {r['fly']:.0%} · ρ {r['rho']:.2f} · {r['endurance']:.0f} min\n"
            f"Citizens reached (two-way): {r['reach']:.0%}")


def _animate_side(sv, v, r, frame):
    flying = r["fly"] > 0.5
    x0 = 0.05 * v["wind"] / 20 * math.sin(frame * 0.35) if flying else 0.0  # sways in the wind
    y0 = sv.z_floor + (v["h"] / 1000 + 0.01 * math.sin(frame * 0.25) if flying else 0.03)
    sv.drone.set_data([x0], [y0])
    sv.rotor.set_data([x0], [y0 + 0.04])
    sv.rotor.set_alpha(0.3 + 0.7 * abs(math.sin(frame * 1.7)) if flying else 0.3)
    R = r["radius_m"] / 1000
    sv.cone.set_xy([[x0, y0], [x0 - R, sv.z_floor], [x0 + R, sv.z_floor]] if flying else [[0, 0], [0, 0], [0, 0]])
    if flying:
        # ray from the drone to each ground user: green if the terrain doesn't get in the way and it's in range
        seg, cols = [], []
        t = np.linspace(0, 1, 40)[1:-1]
        for u, zu in zip(sv.ux, sv.uz):
            xs = x0 + (u - x0) * t
            clear = np.all(np.interp(xs, sv.pd, sv.pz) <= y0 + (zu - y0) * t + 0.005)
            seg.append([(x0, y0), (u, zu)])
            cols.append(C.COL["good"] if clear and abs(u - x0) <= R else C.COL["bad"])
        sv.rays.set_segments(seg)
        sv.rays.set_color(cols)
        sv.rays.set_alpha(0.6)
    else:
        sv.rays.set_segments([])
    why = "wind" if v["wind"] > r["limit_eff"] else "heavy rain"
    sv.txt.set_text(f"FLYING {v['h']:.0f} m above the valley · green = clear path, red = ridge or range"
                    if flying else f"GROUNDED by {why} (wind {v['wind']:.0f} m/s, rain {v['rain']:.0f} mm/h)")
    sv.txt.set_color(C.COL["good"] if flying else C.COL["bad"])
    sv.gusts.set_UVC(np.full(5, 0.02 * v["wind"] * (1 + 0.2 * math.sin(frame * 0.5))), np.zeros(5))


def build():
    v = defaults()
    st = dict(r=evaluate(v))
    fig = new_figure(TITLE, "Optional extension that could complement the required layers: a small cell flown "
                            "over cut-off valleys (Al-Hourani 2014 channel, thin mountain air)",
                     "SUPPLEMENTARY (OPTIONAL)")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_side, ax_top, ax_pl = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_alt, ax_los, ax_wind = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    TR = terrain.load()
    rr = np.linspace(10, 8000, 300)
    w = np.linspace(0, 50, 200)
    side = _setup_side(ax_side, TR)
    top = _setup_top(ax_top, TR)
    pl = _setup_pathloss(ax_pl)
    alt = _setup_altitude(ax_alt)
    los_lines, op_los = _setup_los(ax_los)
    wind = _setup_wind(ax_wind)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        _draw_pathloss(pl, v, r, rr)
        _draw_altitude(ax_alt, alt, v, r)
        for env, ln in los_lines.items():
            ln.set_linewidth(3 if env == v["env"] else 1.2)
            ln.set_alpha(1 if env == v["env"] else 0.45)
        theta_edge = math.degrees(math.atan2(v["h"], max(r["radius_m"], 1)))
        op_los.set_data([theta_edge], [float(M.p_los(theta_edge, v["env"]))])

        rain_f = 1 / (1 + math.exp((v["rain"] - 25) / 5))
        wind.curve.set_data(w, rain_f / (1 + np.exp((w - r["limit_eff"]) / 2)))
        wind.op.set_data([v["wind"]], [r["fly"]])
        wind.txt.set_text(f"limit {v['limit']:.0f} m/s → {r['limit_eff']:.1f} m/s in thin air (ρ = {r['rho']:.2f})\n"
                          f"rain {v['rain']:.0f} mm/h → ×{rain_f:.2f} · p_fly = {r['fly']:.0%}")

        ax_side.set_ylim(0.5, max(side.pz.max(), side.z_floor + v["h"] / 1000) + 0.35)
        _draw_top(ax_top, top, v, r)
        ro.set_text(_readout_text(v, r))
        ro.set_color(status_colour(r["reach"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=4)
    ctl.slider("h", "Altitude h (m)", 20, 2000, v["h"], step=10, fmt="%.0f", color=UA_C)
    ctl.slider("ptx", "User Tx power (dBm)", 10, 33, v["ptx"], step=1, fmt="%.0f", color=UA_C)
    ctl.slider("n", "Number of drones", 1, 12, v["n"], step=1, fmt="%.0f", color=UA_C)
    ctl.slider("wind", "Valley wind gusts (m/s)", 0, 40, v["wind"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("rain", "Rain rate (mm/h)", 0, 120, v["rain"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("limit", "Drone wind limit (m/s)", 8, 30, v["limit"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 25, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.slider("alt", "Launch site altitude (m)", 0, 4000, v["alt"], step=50, fmt="%.0f")
    ctl.radio("env", "Environment", list(M.UAV_ENV), v["env"], [0.595, 0.075, 0.13, 0.13])
    ctl.reset_button([0.595, 0.038, 0.13, 0.03], "Reset to red dots")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        r = st["r"]
        _animate_side(side, v, r, frame)
        p = np.array([(x + 0.25 * math.cos(frame * 0.08 + i), y + 0.25 * math.sin(frame * 0.08 + i))
                      for i, (x, y) in enumerate(HOMES[:int(v["n"])])])  # little hover circles
        top.drones.set_data(p[:, 0], p[:, 1])
        top.drones.set_alpha(1 if r["fly"] > 0.5 else 0.35)

    return fig, step, ctl
