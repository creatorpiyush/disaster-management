"""LIVE DISASTER SIMULATION - a cyclone crosses the coastal smart city.

Towers fail as the wind rises, the satellite fades in heavy rain, drones launch once the wind drops,
repair crews restore towers, and every citizen is coloured by the layer that is serving them right now.
"""
import math

import numpy as np
from matplotlib.patches import Polygon, Circle

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

TITLE = "Live disaster simulation · cyclone over the coastal smart city"
KM = 20.0                     # city is 20 km × 20 km
HOURS = 96.0
PEAK_T = 30.0                 # eye closest to the city centre
LAND_T = PEAK_T + 18.0 * (KM / 2 + 1.0 - 15.5) / 14      # eye crosses the coast (x ≈ 15.5 km)
SERVE_ORDER = [C.L_MO, C.L_UAV, C.L_SA, C.L_MESH]
NONE_C = "#3d3d3a"


def coast_x(y):
    return 15.5 + 1.2 * np.sin(y / 3.0) + 0.6 * np.sin(y / 1.3)


def print_calculations(v=None):
    ui.head(TITLE.upper(), ui.cyan)
    ui.note("Time-stepped simulation (Δt = 15 min of storm time per frame at speed 1). The cyclone eye "
            f"moves from the sea across the city, making landfall at t ≈ {LAND_T:.0f} h. Local wind falls "
            "off with distance from the eye (Gaussian profile, radius 14 km). Each tower fails with hazard "
            "λ = 0.12·(wind − 30)/10 per hour; crews repair towers once the wind is below 15 m/s. "
            "Every citizen is served by the first layer that works for them, in the order "
            "mobile → UAV → satellite shelter → mesh → analog alert only.")


def build():
    rng = np.random.default_rng(2026)
    # --- static city -------------------------------------------------------------
    cit = []
    while len(cit) < 420:
        p = rng.uniform(0.3, KM - 0.3, 2)
        if p[0] < coast_x(p[1]) - 0.3:
            cit.append(p)
    cit = np.array(cit)
    gx, gy = np.meshgrid(np.linspace(1.6, 14.4, 5), np.linspace(1.8, 18.2, 6))
    towers = np.c_[gx.ravel(), gy.ravel()] + rng.normal(0, 0.35, (30, 2))
    towers[:, 0] = np.minimum(towers[:, 0], coast_x(towers[:, 1]) - 0.6)
    shelters = np.array([[3.5, 4.0], [10.5, 15.5], [4.0, 14.0], [11.5, 6.0]])
    mast = np.array([2.0, 10.0])
    uav_base = np.array([1.0, 1.0])
    has_dev = rng.random(len(cit)) < 0.7
    u_block = rng.random(len(cit))
    exposure = 1 + 0.6 * (towers[:, 0] / KM)               # towers near the coast see stronger wind

    v = dict(peak=0.75, speed=1.0, crews=1.5, inc={"UAV": True, "Mesh": True})
    st = {}

    def reset():
        st.update(t=0.0, alive=np.ones(len(towers), bool), events=[], hist=[], uav_pos=np.tile(uav_base, (6, 1)),
                  uav_tgt=np.tile(uav_base, (6, 1)), mesh_ok=np.zeros(len(cit), bool), frame=0, launched=False,
                  repair_acc=0.0, last_down=0, fade_logged=False, done=False, lf=False, fade_end=None)

    reset()

    fig = new_figure(TITLE, "Watch the hybrid network react hour by hour: failures, failover, recovery",
                     "LIVE SIMULATION", size=(16, 9.6))
    gs = fig.add_gridspec(2, 2, left=0.035, right=0.985, top=0.905, bottom=0.25, width_ratios=[1.05, 1],
                          height_ratios=[1.25, 1], wspace=0.12, hspace=0.32)
    ax = fig.add_subplot(gs[:, 0])
    ax_ts = fig.add_subplot(gs[0, 1])
    ax_ev = fig.add_subplot(gs[1, 1])

    # --- map ----------------------------------------------------------------------
    ax.set_aspect("equal")
    ax.set(xlim=(0, KM), ylim=(0, KM), xticks=[], yticks=[])
    ax.set_facecolor("#1c1f1c")
    yy = np.linspace(0, KM, 200)
    ax.add_patch(Polygon(np.r_[np.c_[coast_x(yy), yy], [[KM, KM], [KM, 0]]], fc="#13283d", ec="#2e5a85", lw=1.2))
    ax.text(18.2, 1.0, "SEA", color="#4f7ca8", fontsize=10, fontweight="bold", ha="center")
    sc_cit = ax.scatter(cit[:, 0], cit[:, 1], s=11, color=NONE_C, zorder=3)
    sc_tw = ax.scatter(towers[:, 0], towers[:, 1], marker="^", s=55, color=C.COL[C.L_MO], edgecolor=C.INK, lw=0.6,
                       zorder=4)
    sc_dead = ax.scatter([], [], marker="x", s=60, color=C.COL["bad"], lw=2, zorder=4)
    ax.scatter(shelters[:, 0], shelters[:, 1], marker="s", s=90, color=C.COL[C.L_SA], edgecolor=C.INK, zorder=5)
    for s_ in shelters:
        ax.add_patch(Circle(s_, 1.6, fc="none", ec=C.COL[C.L_SA], lw=0.8, ls=":", zorder=2))
    ax.plot(*mast, marker="^", ms=15, color=C.COL[C.L_AN], mec=C.INK, zorder=5)
    ax.text(mast[0], mast[1] + 0.7, "FM mast", ha="center", fontsize=7, color=C.COL[C.L_AN])
    fm_ring = Circle(mast, 1, fc="none", ec=C.COL[C.L_AN], lw=1.2, alpha=0.6, zorder=2)
    ax.add_patch(fm_ring)
    mesh_lines = ax.vlines([], [], [], color=C.COL[C.L_MESH], lw=0.5, alpha=0.35, zorder=2)
    uav_cov = [Circle((0, 0), 1, fc=C.COL[C.L_UAV], alpha=0.12, ec=C.COL[C.L_UAV], lw=1, zorder=2) for _ in range(6)]
    for c in uav_cov:
        ax.add_patch(c)
    uav_dots, = ax.plot([], [], marker=(4, 0, 45), ms=10, color=C.COL[C.L_UAV], mec=C.INK, ls="none", zorder=6)
    arms = [ax.plot([], [], color="#d9dde3", lw=2.2, alpha=0.35, zorder=7)[0] for _ in range(4)]
    eye, = ax.plot([], [], "o", ms=14, mfc="none", mec="#ffffff", mew=2, zorder=8)
    clock = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=11, fontweight="bold", color=C.INK,
                    bbox=dict(fc="#000000", alpha=0.55, ec="none"), zorder=9)
    # legend
    handles = [ax.scatter([], [], s=30, color=C.COL[l], label=f"served by {C.SHORT[l].lower()}") for l in SERVE_ORDER]
    handles += [ax.scatter([], [], s=30, color=C.COL[C.L_AN], marker="h", label="analog alert only"),
                ax.scatter([], [], s=30, color=NONE_C, label="no contact")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.005), ncol=3, fontsize=7.2)

    # --- time series ------------------------------------------------------------------
    ax_ts.set_title("Share of citizens with two-way contact over time")
    ax_ev.set_axis_off()
    ev_txt = ax_ev.text(0.0, 1.0, "", transform=ax_ev.transAxes, va="top", family="monospace", fontsize=8,
                        color=C.INK, linespacing=1.5)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.165]))
    player = Player(fig)

    def log(msg):
        st["events"].append(f"t={st['t']:5.1f} h  {msg}")

    def env_at(t):
        """Eye position and city-wide hazard values at time t (hours)."""
        frac = (t - PEAK_T) / 18.0
        eye_p = np.array([KM / 2 + 1.0 - 14 * frac, KM / 2 - 0.8 + 11 * frac])
        d = float(np.hypot(*(eye_p - np.array([KM / 2, KM / 2]))))
        i = v["peak"] * math.exp(-(d / 14.0) ** 2)
        return eye_p, i

    def hazards(i):
        s = M.storm_from_intensity(i)
        s["rain"] = min(150.0, 60 * (i / 0.4) ** 2.2)   # rain bands are more peaked than wind
        return s

    def assign():
        t = st["t"]
        eye_p, i = env_at(t)
        storm = hazards(i)
        storm["towers_down"] = 100 * (1 - st["alive"].mean())
        e = M.evaluate_all(storm)
        inc = v["inc"]
        # mobile: nearest live tower within range, then Erlang-B blocking
        alive_t = towers[st["alive"]]
        r_mo = 2.6 * 10 ** (-storm["noise_rise"] / 35)
        if len(alive_t):
            d = np.hypot(cit[:, None, 0] - alive_t[None, :, 0], cit[:, None, 1] - alive_t[None, :, 1]).min(axis=1)
        else:
            d = np.full(len(cit), 99.0)
        block = e["layers"][C.L_MO]["block"]
        mob = (d <= r_mo) & (u_block >= block)
        # UAV
        fly = e["layers"][C.L_UAV]["fly"] > 0.5 and inc.get("UAV", True) and st["launched"]
        r_u = e["layers"][C.L_UAV]["radius_m"] / 1000
        if fly:
            du = np.hypot(cit[:, None, 0] - st["uav_pos"][None, :, 0], cit[:, None, 1] - st["uav_pos"][None, :, 1])
            uav = du.min(axis=1) <= r_u
        else:
            uav = np.zeros(len(cit), bool)
        # satellite shelters
        sat_ok = e["layers"][C.L_SA]["margin"] > 0
        ds = np.hypot(cit[:, None, 0] - shelters[None, :, 0], cit[:, None, 1] - shelters[None, :, 1]).min(axis=1)
        sat = (ds <= 1.6) & sat_ok
        # mesh (recomputed every few frames)
        mesh = st["mesh_ok"] & inc.get("Mesh", True)        # gateways at shelters reach local responders
        # analog
        an_r = 6 + 30 * e["layers"][C.L_AN]["coverage"] * e["layers"][C.L_AN]["mast_ok"]
        alert = np.hypot(*(cit - mast).T) <= an_r
        cls = np.full(len(cit), 5)
        for k, m in enumerate([mob, uav, sat, mesh]):
            cls = np.where((cls == 5) & m, k, cls)
        cls = np.where((cls == 5) & alert, 4, cls)
        st.update(cls=cls, eye=eye_p, i=i, storm=storm, e=e, fly=fly, r_u=r_u, an_r=an_r, sat_ok=sat_ok,
                  core=(mob | sat).mean())

    def update_mesh():
        storm = st.get("storm", M.storm_from_intensity(0))
        r = M.lora_range_km(C.MESH["sf"], 125, C.MESH["ptx_dbm"], storm["noise_rise"], 8.0)
        nodes = np.r_[cit[has_dev], shelters]
        dd = np.hypot(nodes[:, None, 0] - nodes[None, :, 0], nodes[:, None, 1] - nodes[None, :, 1])
        adj = dd <= r
        np.fill_diagonal(adj, False)
        lab = np.arange(len(nodes))
        big = len(nodes) + 1
        for _ in range(60):
            new = np.minimum(lab, np.where(adj, lab[None, :], big).min(axis=1))
            if np.array_equal(new, lab):
                break
            lab = new
        gw_labels = set(lab[-len(shelters):].tolist())
        ok_nodes = np.isin(lab[:-len(shelters)], list(gw_labels))
        mo = np.zeros(len(cit), bool)
        mo[np.nonzero(has_dev)[0]] = ok_nodes
        st["mesh_ok"] = mo
        ii, jj = np.nonzero(np.triu(adj))
        keep = rng.random(len(ii)) < min(1.0, 500 / max(len(ii), 1))
        mesh_lines.set_segments([[nodes[a], nodes[b]] for a, b in zip(ii[keep], jj[keep])])

    def advance(dt):
        st["t"] += dt
        eye_p, i = env_at(st["t"])
        storm = hazards(i)
        # tower failures: hazard grows with local wind above 30 m/s
        dloc = np.hypot(towers[:, 0] - eye_p[0], towers[:, 1] - eye_p[1])
        wind_loc = storm["wind"] * exposure * (0.6 + 0.4 * np.exp(-(dloc / 8) ** 2))
        lam = 0.12 * np.maximum(0, wind_loc - 30) / 10
        fail = (rng.random(len(towers)) < 1 - np.exp(-lam * dt)) & st["alive"]
        if fail.any():
            st["alive"] &= ~fail
        down = int((~st["alive"]).sum())
        if down >= st["last_down"] + 3:
            log(f"{down} of {len(towers)} cell towers are down")
            st["last_down"] = down
        # repairs once the wind drops
        if storm["wind"] < 15 and st["lf"] and down:
            st["repair_acc"] += v["crews"] * dt / 2
            while st["repair_acc"] >= 1 and (~st["alive"]).any():
                k = int(np.nonzero(~st["alive"])[0][0])
                st["alive"][k] = True
                st["repair_acc"] -= 1
                if (~st["alive"]).sum() % 4 == 0:
                    log(f"repair crews: {int((~st['alive']).sum())} towers still down")
            st["last_down"] = int((~st["alive"]).sum())
        # UAV launch when wind allows
        if v["inc"].get("UAV", True) and not st["launched"] and storm["wind"] < C.UAV["wind_limit"] \
                and st["lf"] and down:
            st["launched"] = True
            log("wind below drone limit → UAV cells launched")
        if st["launched"]:
            dead = towers[~st["alive"]]
            tg = dead[:6] if len(dead) else np.tile(uav_base, (1, 1))
            st["uav_tgt"][:len(tg)] = tg
            st["uav_tgt"][len(tg):] = uav_base
            st["uav_pos"] += (st["uav_tgt"] - st["uav_pos"]) * min(1, 0.25 * dt * 4)
        if storm["rain"] > 75 and not st["fade_logged"]:
            log("heavy rain → satellite Ku-band link in deep fade")
            st["fade_logged"] = True
        if st["fade_logged"] and storm["rain"] < 50 and st["fade_end"] is None:
            st["fade_end"] = True
            log("rain easing → satellite link restored")
        if not st["lf"] and eye_p[0] < coast_x(eye_p[1]):
            st["lf"] = True
            log("LANDFALL — eye wall crosses the coast")

    def recompute(vals):
        v.update(peak=vals["peak"], speed=vals["speed"], crews=vals["crews"], inc=vals["inc"])
        assign()
        draw(0)
        fig.canvas.draw_idle()

    def restart():
        reset()
        update_mesh()
        assign()
        log("simulation started — cyclone approaching from the sea")

    def draw(frame):
        cls = st["cls"]
        palette = [C.COL[l] for l in SERVE_ORDER] + [C.COL[C.L_AN], NONE_C]
        sc_cit.set_color([palette[c] for c in cls])
        sc_cit.set_sizes(np.where(cls == 4, 9, 13))
        sc_tw.set_offsets(towers[st["alive"]] if st["alive"].any() else np.zeros((0, 2)))
        sc_dead.set_offsets(towers[~st["alive"]] if (~st["alive"]).any() else np.zeros((0, 2)))
        mesh_lines.set_visible(v["inc"].get("Mesh", True))
        for k, c in enumerate(uav_cov):
            c.center = tuple(st["uav_pos"][k])
            c.set_radius(st["r_u"])
            c.set_visible(st["fly"])
        uav_dots.set_data(st["uav_pos"][:, 0], st["uav_pos"][:, 1])
        uav_dots.set_visible(v["inc"].get("UAV", True) and st["launched"])
        ex, ey = st["eye"]
        rot = frame * 0.15
        for k, a in enumerate(arms):
            r = np.linspace(0.6, 13, 80)
            th = rot + k * np.pi / 2 + r / 3.2
            a.set_data(ex + r * np.cos(th), ey + r * np.sin(th))
            a.set_alpha(0.15 + 0.5 * st["i"])
        eye.set_data([ex], [ey])
        fm_ring.set_radius((frame * 0.4) % max(st["an_r"], 1))
        s = st["storm"]
        clock.set_text(f"t = {st['t']:5.1f} h   wind {s['wind']:4.0f} m/s   rain {s['rain']:4.0f} mm/h")
        counts = np.bincount(cls, minlength=6) / len(cls)
        two_way = counts[:4].sum()
        ro.set_text(
            f"NOW (t = {st['t']:.1f} h)\n"
            f"towers alive {st['alive'].sum()}/{len(towers)} · drones {'up' if st['fly'] else 'grounded'}\n"
            f"satellite {'OK' if st['sat_ok'] else 'IN FADE'} · storm i = {st['i']:.2f}\n"
            f"two-way contact (hybrid) {two_way:.0%}\n"
            f"two-way, 3 required only {st['core']:.0%}\n"
            f"alert-only {counts[4]:.0%} · no contact {counts[5]:.0%}")
        ro.set_color(status_colour(two_way))
        ev_txt.set_text("EVENT LOG\n" + "\n".join(st["events"][-11:]))
        return counts

    def draw_ts():
        h = np.array(st["hist"])
        ax_ts.cla()
        ax_ts.set_title("Share of citizens with two-way contact over time")
        if len(h) > 1:
            t = h[:, 0]
            ax_ts.stackplot(t, h[:, 1:5].T, colors=[C.COL[l] for l in SERVE_ORDER], alpha=0.9, edgecolor=C.PANEL,
                            lw=0.5, labels=[C.SHORT[l] for l in SERVE_ORDER])
            ax_ts.plot(t, h[:, 5], color=C.INK, lw=2, ls="--", label="3 required layers only")
            ax_ts.plot(t, h[:, 6], color=C.COL["warn"], lw=1.2, label="storm intensity")
        ax_ts.axvline(LAND_T, color=C.MUTED, ls=":", lw=1)
        ax_ts.text(LAND_T + 0.8, 1.02, "landfall", fontsize=7, color=C.MUTED)
        ax_ts.set(xlim=(0, HOURS), ylim=(0, 1.22), xlabel="hours", ylabel="share of citizens")
        ax_ts.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        if len(h) > 1:
            ax_ts.legend(loc="upper center", fontsize=6.5, ncol=6, handlelength=1.2, columnspacing=0.8)

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.58, 0.165), cols=1, rows=3)
    ctl.slider("peak", "Cyclone peak intensity", 0.2, 1.0, v["peak"], step=0.05, fmt="%.2f", color=C.COL["bad"])
    ctl.slider("speed", "Simulation speed", 0.25, 4, v["speed"], step=0.25, fmt="%.2f×")
    ctl.slider("crews", "Repair crews (towers / 2 h)", 0, 3, v["crews"], step=0.1, fmt="%.1f", color=C.COL["good"])
    ctl.check("inc", "Optional layers", ["UAV", "Mesh"], [True, True], [0.605, 0.075, 0.12, 0.125])
    ctl.button([0.605, 0.038, 0.058, 0.03], "▶ Play/Pause", player.toggle)
    ctl.button([0.667, 0.038, 0.058, 0.03], "↻ Restart", lambda: (restart(), draw_ts()))
    ctl.reset_button([0.44, 0.042, 0.14, 0.03], "↺  Reset sliders")
    restart()
    draw(0)
    draw_ts()

    def step(frame):
        if not player.running:
            return
        st["frame"] += 1
        if st["t"] < HOURS:
            advance(0.25 * v["speed"])
            if st["frame"] % 4 == 0:
                update_mesh()
            assign()
            counts = draw(st["frame"])
            st["hist"].append([st["t"], *counts[:4], st["core"], st["i"]])
            if st["frame"] % 3 == 0:
                draw_ts()
        else:
            if not st["done"]:
                log("simulation complete — press Restart to run again")
                st["done"] = True
                draw_ts()
            draw(st["frame"])

    return fig, step, ctl
