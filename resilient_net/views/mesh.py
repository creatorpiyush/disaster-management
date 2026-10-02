"""SUPPLEMENTARY LAYER B - LoRa / device-to-device mesh.

An optional extension that can be deployed alongside the three required layers: battery-powered
LoRa radios (or phones in D2D mode) relay short text messages hop-by-hop to a gateway at a shelter,
which forwards them over the satellite layer.
"""
import math

import numpy as np

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

ME_C = C.COL[C.L_MESH]
TITLE = "Supplementary layer B · LoRa / D2D mesh"


def defaults():
    m = C.MESH
    return dict(sf=m["sf"], ptx=m["ptx_dbm"], n=m["n_nodes"], alive=m["alive"], rate=m["msgs_per_hr"],
                noise=C.STORM["noise_rise"])


def evaluate(v):
    return M.mesh_layer(sf=int(v["sf"]), bw_khz=C.MESH["bw_khz"], ptx_dbm=v["ptx"], n_nodes=int(v["n"]),
                        alive=v["alive"], payload=C.MESH["payload"], msgs_per_hr=v["rate"], area_km=C.MESH["area_km"],
                        noise_rise=v["noise"])


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    sf, bw = int(v["sf"]), C.MESH["bw_khz"]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_MESH])
    ui.note("Optional extension. This layer is not one of the three required layers. It is included as an "
            "additional option: low-power LoRa radios or phones in device-to-device mode relay short SOS and "
            "status messages to a gateway, with no tower and no grid power needed.")
    ui.calc("LoRa bit rate", "Rb = SF · BW / 2^SF · 4/(4+CR)", f"{sf} × {bw:.0f} kHz / 2^{sf} × 4/5",
            f"{r['rb']:.0f}", "bit/s")
    ui.calc("Receiver sensitivity", "S = −174 + 10log BW + NF + SNRreq(SF)",
            f"−174 + 10log({bw * 1e3:.0f}) + 6 + ({M.LORA_SNR_REQ[sf]})", f"{r['sens']:.1f}", "dBm")
    ui.calc("Node-to-node range", "PL = 128.95 + 23.2 log10(d) (+ clutter, storm noise)", "", f"{r['range_km']:.2f}",
            "km")
    ui.calc("Time on air", "T = (Npre + 4.25)Tsym + Npayload·Tsym  (Semtech AN1200.13)",
            f"{C.MESH['payload']}-byte message", f"{r['toa'] * 1e3:.0f}", "ms")
    ui.calc("Duty-cycle check", "T · msgs/h ≤ 1 % of 3600 s", f"{r['toa']:.3f} × {v['rate']:.0f}",
            "OK" if r["duty_ok"] else "VIOLATES 1 % limit")
    ui.calc("Mean node degree", "k = λ·π·r²", f"λ = {r['n_alive']:.0f} / {C.MESH['area_km']:.0f}² km⁻²",
            f"{r['mean_degree']:.2f}")
    ui.calc("Connected fraction", "S = 1 − exp(−k·S)   (giant component)", "", f"{r['conn']:.1%}")
    ui.calc("Collision-free delivery", "P = exp(−2G)   (pure ALOHA)", f"G = {r['g']:.3f} Erlang", f"{r['p_aloha']:.1%}")
    ui.bar("Citizens reached (two-way text)", r["reach"], ui.LAYER_TINT[C.L_MESH])
    return r


def _graph(pts, alive, rng_km):
    d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    adj = (d <= rng_km) & alive[:, None] & alive[None, :]
    np.fill_diagonal(adj, False)
    return adj


def _bfs(adj, src):
    level = np.full(len(adj), -1)
    level[src] = 0
    frontier = [src]
    while frontier:
        nxt = []
        for u in frontier:
            for w in np.nonzero(adj[u])[0]:
                if level[w] < 0:
                    level[w] = level[u] + 1
                    nxt.append(w)
        frontier = nxt
    return level


def _components(adj):
    """Connected-component labels by vectorised min-label propagation."""
    lab = np.arange(len(adj))
    big = len(adj) + 1
    while True:
        nb = np.where(adj, lab[None, :], big).min(axis=1)
        new = np.minimum(lab, nb)
        if np.array_equal(new, lab):
            return lab
        lab = new


def build():
    v = defaults()
    A = C.MESH["area_km"]
    rng = np.random.default_rng(8)
    pts_all = rng.uniform(0, A, (400, 2))
    order = rng.random(400)
    gws = np.array([[A * 0.2, A * 0.8], [A * 0.8, A * 0.25]])
    st = dict(r=evaluate(v), src=0, t=0, level=None, adj=None, n=0, alive=None)
    fig = new_figure(TITLE, "Optional extension that may complement the required layers: battery radios relay "
                            "SOS texts hop-by-hop to a gateway that uplinks via satellite", "SUPPLEMENTARY · OPTIONAL")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_map = fig.add_subplot(gs[:, 0])
    ax_sf, ax_conn = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_toa, ax_alo = fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    ax_map.set_aspect("equal")
    ax_map.set(xlim=(0, A), ylim=(0, A), title="Live message flooding through the mesh", xlabel="km", ylabel="km")
    edges = ax_map.vlines([], [], [], lw=0.6, color=ME_C, alpha=0.25)
    hot = ax_map.vlines([], [], [], lw=1.8, color=C.INK)
    sc_dead = ax_map.scatter([], [], marker="x", s=14, color="#5a5a55", lw=1)
    sc_nodes = ax_map.scatter([], [], s=20, zorder=3)
    ax_map.scatter(gws[:, 0], gws[:, 1], marker="s", s=120, color=C.COL[C.L_SA], edgecolor=C.INK, zorder=5,
                   label="gateway → satellite")
    src_pt, = ax_map.plot([], [], "*", ms=17, color=C.COL["warn"], mec=C.INK, zorder=6, label="SOS sender")
    ax_map.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=7)
    map_txt = ax_map.text(0.02, 0.98, "", transform=ax_map.transAxes, va="top", fontsize=8, color=C.INK,
                          bbox=dict(fc=C.PANEL, ec="none", alpha=0.85))

    sfs = np.arange(7, 13)
    ax_sf.set_title("Spreading factor trade-off: range vs speed")
    ax_conn.set(title="Mesh connectivity vs number of radios", xlabel="radios deployed in 8×8 km",
                ylabel="fraction in connected mesh", ylim=(0, 1.05))
    l_conn, = ax_conn.plot([], [], color=ME_C, lw=2, label="approx. S = 1 − e^(−kS) (no city edge)")
    mc_conn = ax_conn.scatter([], [], s=26, color=C.INK, zorder=4, label="random geometric graph (simulated)")
    op_conn, = ax_conn.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_conn.legend(loc="lower right", fontsize=7)

    pay = np.arange(5, 120)
    ax_toa.set(title="Time on air and 1 % duty-cycle budget", xlabel="payload (bytes)", ylabel="time on air (ms)")
    ax_toa.set_yscale("log")
    toa_lines = {}
    for s_, a_ in zip(sfs, np.linspace(0.35, 1, 6)):
        toa_lines[s_], = ax_toa.plot(pay, [M.lora_airtime(s_, 125, p) * 1e3 for p in pay], color=ME_C, alpha=a_,
                                     lw=1.3)
        ax_toa.text(121, M.lora_airtime(s_, 125, 119) * 1e3, f"SF{s_}", fontsize=7, color=C.INK2, va="center")
    ax_toa.set_xlim(0, 135)
    op_toa, = ax_toa.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)
    toa_txt = ax_toa.text(0.03, 0.95, "", transform=ax_toa.transAxes, va="top", fontsize=7.5)

    G = np.linspace(0, 1.5, 200)
    ax_alo.plot(G, np.exp(-2 * G), color=ME_C, lw=2, label="success  e^(−2G)")
    ax_alo.plot(G, G * np.exp(-2 * G), color=C.INK2, lw=1.5, ls="--", label="throughput  G·e^(−2G)")
    op_alo, = ax_alo.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_alo.axvline(0.5, color=C.MUTED, ls=":", lw=1)
    ax_alo.text(0.52, 0.85, "max throughput\n18.4 % at G = 0.5", fontsize=7, color=C.MUTED)
    ax_alo.set(title="Collisions: pure ALOHA channel", xlabel="offered load G (Erlang)", ylabel="probability",
               ylim=(0, 1.05), xlim=(0, 1.5))
    ax_alo.legend(loc="upper right", fontsize=7)
    alo_txt = ax_alo.text(0.97, 0.45, "", transform=ax_alo.transAxes, ha="right", fontsize=7.5)

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def new_flood():
        alive = st["alive"]
        idx = np.nonzero(alive)[0]
        if len(idx) == 0:
            st["level"] = None
            return
        st["src"] = int(rng.choice(idx))
        st["level"] = _bfs(st["adj"], st["src"])
        st["t"] = 0

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        n = int(v["n"])
        pts = np.vstack([pts_all[:n], gws])
        alive = np.r_[order[:n] < v["alive"] / 100, [True, True]]
        st.update(pts=pts, alive=alive, adj=_graph(pts, alive, r["range_km"]), n=n)
        ii, jj = np.nonzero(np.triu(st["adj"]))
        edges.set_segments([[pts[i], pts[j]] for i, j in zip(ii, jj)])
        sc_dead.set_offsets(pts[~alive] if (~alive).any() else np.zeros((0, 2)))
        new_flood()
        # SF bars
        ax_sf.cla()
        ax_sf.set_title("Spreading factor trade-off: range vs speed")
        rng_ = [M.lora_range_km(s_, 125, v["ptx"], v["noise"]) for s_ in sfs]
        cols = [ME_C if s_ == int(v["sf"]) else "#4a3340" for s_ in sfs]
        ax_sf.bar(sfs, rng_, color=cols, width=0.65)
        for s_, rk in zip(sfs, rng_):
            ax_sf.text(s_, rk + 0.05, f"{M.lora_bitrate(s_, 125):.0f} b/s", ha="center", fontsize=7, color=C.INK2)
        ax_sf.set(xlabel="spreading factor SF (label = bit rate)", ylabel="node-to-node range (km)",
                  ylim=(0, max(rng_) * 1.25))
        ax_sf.set_xticks(sfs)
        # connectivity
        ns = np.arange(10, 401, 10)
        th = [M.giant_component(nn * v["alive"] / 100 / A ** 2 * math.pi * min(r["range_km"], A) ** 2) for nn in ns]
        l_conn.set_data(ns, th)
        ax_conn.set_xlim(0, 400)
        mrng = np.random.default_rng(1)
        sim = []
        for nn in ns[::4]:
            acc = []
            for _ in range(3):
                p = mrng.uniform(0, A, (int(nn * v["alive"] / 100) + 1, 2))
                adj = _graph(p, np.ones(len(p), bool), r["range_km"])
                lab = _components(adj)
                comp = np.bincount(lab)
                acc.append(max(comp) / len(p))
            sim.append(np.mean(acc))
        mc_conn.set_offsets(np.c_[ns[::4], sim])
        op_conn.set_data([n], [r["conn"]])
        for s_, ln in toa_lines.items():
            ln.set_linewidth(3 if s_ == int(v["sf"]) else 1.2)
        op_toa.set_data([C.MESH["payload"]], [r["toa"] * 1e3])
        max_msgs = 36.0 / r["toa"]
        toa_txt.set_text(f"SF{int(v['sf'])}, {C.MESH['payload']} B → {r['toa'] * 1e3:.0f} ms on air\n"
                         f"1 % duty cycle → max {max_msgs:.0f} msgs/h per radio")
        toa_txt.set_color(C.COL["good"] if r["duty_ok"] else C.COL["bad"])
        op_alo.set_data([min(r["g"], 1.5)], [r["p_aloha"]])
        alo_txt.set_text(f"G = {r['g']:.3f} → {r['p_aloha']:.0%} delivered")
        ro.set_text(
            f"LIVE RESULTS (SF{int(v['sf'])}, {v['ptx']:.0f} dBm)\n"
            f"bit rate {r['rb']:.0f} b/s · sens {r['sens']:.1f} dBm\n"
            f"range {r['range_km']:.2f} km · degree k {r['mean_degree']:.1f}\n"
            f"connected {r['conn']:.0%} · hops ≈ {r['hops']:.1f}\n"
            f"ALOHA success {r['p_aloha']:.0%} · ToA {r['toa'] * 1e3:.0f} ms\n"
            f"Citizens reached (text): {r['reach']:.0%}")
        ro.set_color(status_colour(r["reach"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.70, 0.17), cols=2, rows=3)
    ctl.slider("sf", "Spreading factor SF", 7, 12, v["sf"], step=1, fmt="%.0f", color=ME_C)
    ctl.slider("ptx", "Tx power (dBm)", 2, 20, v["ptx"], step=1, fmt="%.0f", color=ME_C)
    ctl.slider("n", "Radios deployed", 20, 400, v["n"], step=10, fmt="%.0f", color=ME_C)
    ctl.slider("alive", "Radios with battery (%)", 10, 100, v["alive"], step=5, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("rate", "Messages per radio per hour", 1, 120, v["rate"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 25, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.reset_button([0.6, 0.045, 0.1, 0.03])
    ctl.button([0.49, 0.045, 0.1, 0.03], "✉  New SOS", lambda: new_flood())
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        pts, alive = st["pts"], st["alive"]
        lvl = st["level"]
        if lvl is None:
            return
        st["t"] += 1
        wave = st["t"] / 6.0                           # hops travelled so far
        reached = (lvl >= 0) & (lvl <= wave)
        cols = np.where(~alive, "#00000000", np.where(reached, ME_C, "#6b6b66"))
        cols = cols.astype(object)
        cols[-2:] = C.COL[C.L_SA]
        sc_nodes.set_offsets(pts)
        sc_nodes.set_color(list(cols))
        sc_nodes.set_sizes(np.where(reached & (lvl >= wave - 1), 60, 20))
        ii, jj = np.nonzero(st["adj"])
        front = (lvl[ii] == math.floor(wave)) & (lvl[jj] == math.floor(wave) + 1)
        frac = wave - math.floor(wave)
        hot.set_segments([[pts[i], pts[i] + (pts[j] - pts[i]) * frac] for i, j in zip(ii[front], jj[front])])
        src_pt.set_data([pts[st["src"]][0]], [pts[st["src"]][1]])
        gw_l = lvl[-2:]
        gw_hit = [g for g in gw_l if 0 <= g <= wave]
        tot = (lvl >= 0).sum()
        if gw_hit:
            msg = f"SOS reached a gateway in {int(min(gw_hit))} hops ✓"
            col = C.COL["good"]
        elif wave > max(lvl.max(), 0) + 1:
            msg = "SOS stuck in an island — no gateway reachable ✗"
            col = C.COL["bad"]
        else:
            msg = f"flooding… hop {int(wave)}"
            col = C.INK
        map_txt.set_text(f"{msg}\nnodes reached {reached.sum()} / {alive.sum()}")
        map_txt.set_color(col)
        if wave > max(lvl.max(), 0) + 3:
            new_flood()

    return fig, step, ctl
