"""Optional layer B - LoRa / D2D mesh. Not required, but it could complement the other layers."""
import math
from types import SimpleNamespace

import numpy as np

from .. import config as C, models as M, terrain, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

ME_C = C.COL[C.L_MESH]
TITLE = "Supplementary layer B: LoRa / D2D mesh"
MCROP = (-4.5, -6.0)  # SW corner of the 8x8 km map, Gangtok down to Ranipool


def terrain_loss():
    return terrain.zone_stats("Whole district")["mesh_loss"]


def defaults():
    m = C.MESH
    return dict(sf=m["sf"], ptx=m["ptx_dbm"], n=m["n_nodes"], alive=m["alive"], rate=m["msgs_per_hr"],
                noise=C.STORM["noise_rise"])


def evaluate(v):
    return M.mesh_layer(sf=int(v["sf"]), bw_khz=C.MESH["bw_khz"], ptx_dbm=v["ptx"], n_nodes=int(v["n"]),
                        alive=v["alive"], payload=C.MESH["payload"], msgs_per_hr=v["rate"], area_km=C.MESH["area_km"],
                        noise_rise=v["noise"], extra_loss=terrain_loss())


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    sf, bw = int(v["sf"]), C.MESH["bw_khz"]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_MESH])
    ui.note("Optional extension, not one of the three required layers, but it could complement them. "
            "LoRa radios or phones in D2D mode pass short SOS / status texts along to a gateway. "
            "No tower, no grid power.")
    ui.calc("LoRa bit rate", "Rb = SF · BW / 2^SF · 4/(4+CR)", f"{sf} × {bw:.0f} kHz / 2^{sf} × 4/5",
            f"{r['rb']:.0f}", "bit/s")
    ui.calc("Receiver sensitivity", "S = −174 + 10log BW + NF + SNRreq(SF)",
            f"−174 + 10log({bw * 1e3:.0f}) + 6 + ({M.LORA_SNR_REQ[sf]})", f"{r['sens']:.1f}", "dBm")
    zs = terrain.zone_stats("Whole district")
    ui.calc("Ridges between neighbours (real terrain)", "share of home pairs ≤ 2 km apart with no line of sight",
            f"{zs['n']} homes, SRTM profiles", f"{zs['blocked']:.0%} blocked",
            f"→ extra loss 6 + 20 × {zs['blocked']:.2f} = {zs['mesh_loss']:.1f} dB")
    ui.calc("Node-to-node range", "PL = 128.95 + 23.2 log10(d) + terrain loss + storm noise", "",
            f"{r['range_km']:.2f}", "km")
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


def _graph(pts, alive, rng_km, los=None):
    d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    adj = (d <= rng_km) & alive[:, None] & alive[None, :]
    if los is not None:
        adj &= los
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
    # label propagation - way faster than a python BFS per node with 400 nodes
    lab = np.arange(len(adj))
    big = len(adj) + 1
    while True:
        nb = np.where(adj, lab[None, :], big).min(axis=1)
        new = np.minimum(lab, nb)
        if np.array_equal(new, lab):
            return lab
        lab = new


def _radio_positions(rng):
    """Homes inside the map crop (up to 400) + the two gateways, and which radio pairs have line of sight."""
    A = C.MESH["area_km"]
    S = terrain.scenario(1500, 11)
    off = np.array(MCROP)
    c = S["cit"] - off
    pts = c[(c[:, 0] > 0.1) & (c[:, 0] < A - 0.1) & (c[:, 1] > 0.1) & (c[:, 1] < A - 0.1)][:400]
    order = rng.random(len(pts))  # radio i has battery if order[i] < alive %
    S0 = terrain.scenario()
    gws = np.array([g - off for g, nm in zip(S0["shelters"], S0["shelter_names"]) if nm in ("Gangtok", "Ranipool")])
    allp = np.vstack([pts, gws])
    # only check LoS for pairs within 4 km, nothing further can ever link up anyway
    ii, jj = np.nonzero(np.triu(np.hypot(allp[:, None, 0] - allp[None, :, 0],
                                         allp[:, None, 1] - allp[None, :, 1]) <= 4.0, 1))
    los = np.zeros((len(allp), len(allp)), bool)
    los[ii, jj] = S["T"].line_of_sight(allp[ii] + off, allp[jj] + off, 2.0, 2.0)
    los |= los.T
    return pts, order, gws, los


def _setup_map(ax, TR, gws):
    A, off = C.MESH["area_km"], np.array(MCROP)
    ax.set_aspect("equal")
    ax.set(xlim=(0, A), ylim=(0, A), title="Live SOS flooding over the real terrain", xticks=[], yticks=[])
    x0, x1, y0, y1 = TR.extent
    ax.imshow(TR.hillshade(), extent=(x0 - off[0], x1 - off[0], y0 - off[1], y1 - off[1]), origin="lower",
              cmap="gray", vmin=-0.3, vmax=1.6, zorder=0, interpolation="bilinear")
    for rv in TR.rivers:
        ax.plot(rv["xy"][:, 0] - off[0], rv["xy"][:, 1] - off[1], color="#4f8fd0", lw=0.8, zorder=1)
    for nm in ("Gangtok", "Ranipool"):
        place = next(q for q in TR.places if q["name"] == nm)
        ax.text(place["x"] - off[0] + 0.25, place["y"] - off[1] - 0.4, nm, fontsize=7, color=C.INK2, zorder=6)
    mp = SimpleNamespace()
    mp.edges = ax.vlines([], [], [], lw=0.6, color=ME_C, alpha=0.25)
    mp.hot = ax.vlines([], [], [], lw=1.8, color=C.INK)
    mp.dead = ax.scatter([], [], marker="x", s=14, color="#5a5a55", lw=1)
    mp.nodes = ax.scatter([], [], s=20, zorder=3)
    ax.scatter(gws[:, 0], gws[:, 1], marker="s", s=120, color=C.COL[C.L_SA], edgecolor=C.INK, zorder=5,
               label="gateway → satellite")
    mp.src, = ax.plot([], [], "*", ms=17, color=C.COL["warn"], mec=C.INK, zorder=6, label="SOS sender")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=7)
    mp.txt = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=8, color=C.INK,
                     bbox=dict(fc=C.PANEL, ec="none", alpha=0.85))
    return mp


def _setup_connectivity(ax):
    ax.set(title="Mesh connectivity vs number of radios", xlabel="radios deployed in 8×8 km",
           ylabel="fraction in connected mesh", ylim=(0, 1.05))
    cn = SimpleNamespace()
    cn.curve, = ax.plot([], [], color=ME_C, lw=2, label="approx. S = 1 − e^(−kS) (no city edge)")
    cn.sim = ax.scatter([], [], s=26, color=C.INK, zorder=4, label="random geometric graph (simulated)")
    cn.op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax.legend(loc="lower right", fontsize=7)
    return cn


def _setup_airtime(ax, sfs):
    pay = np.arange(5, 120)
    ax.set(title="Time on air and 1 % duty-cycle budget", xlabel="payload (bytes)", ylabel="time on air (ms)")
    ax.set_yscale("log")
    lines = {}
    for sf, alpha in zip(sfs, np.linspace(0.35, 1, 6)):
        lines[sf], = ax.plot(pay, [M.lora_airtime(sf, 125, p) * 1e3 for p in pay], color=ME_C, alpha=alpha, lw=1.3)
        ax.text(121, M.lora_airtime(sf, 125, 119) * 1e3, f"SF{sf}", fontsize=7, color=C.INK2, va="center")
    ax.set_xlim(0, 135)
    op, = ax.plot([], [], "o", ms=12, mfc="none", mec=C.INK, mew=2)
    txt = ax.text(0.03, 0.95, "", transform=ax.transAxes, va="top", fontsize=7.5)
    return lines, op, txt


def _setup_aloha(ax):
    G = np.linspace(0, 1.5, 200)
    ax.plot(G, np.exp(-2 * G), color=ME_C, lw=2, label="success  e^(−2G)")
    ax.plot(G, G * np.exp(-2 * G), color=C.INK2, lw=1.5, ls="--", label="throughput  G·e^(−2G)")
    op, = ax.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax.axvline(0.5, color=C.MUTED, ls=":", lw=1)
    ax.text(0.52, 0.85, "max throughput\n18.4 % at G = 0.5", fontsize=7, color=C.MUTED)
    ax.set(title="Collisions: pure ALOHA channel", xlabel="offered load G (Erlang)", ylabel="probability",
           ylim=(0, 1.05), xlim=(0, 1.5))
    ax.legend(loc="upper right", fontsize=7)
    txt = ax.text(0.97, 0.45, "", transform=ax.transAxes, ha="right", fontsize=7.5)
    return op, txt


def _draw_sf_bars(ax, v, sfs):
    ax.cla()
    ax.set_title("Spreading factor trade-off: range vs speed")
    ranges = [M.lora_range_km(sf, 125, v["ptx"], v["noise"], terrain_loss()) for sf in sfs]
    ax.bar(sfs, ranges, color=[ME_C if sf == int(v["sf"]) else "#4a3340" for sf in sfs], width=0.65)
    for sf, rk in zip(sfs, ranges):
        ax.text(sf, rk + 0.05, f"{M.lora_bitrate(sf, 125):.0f} b/s", ha="center", fontsize=7, color=C.INK2)
    ax.set(xlabel="spreading factor SF (label = bit rate)", ylabel="node-to-node range (km)",
           ylim=(0, max(ranges) * 1.25))
    ax.set_xticks(sfs)


def _simulated_connectivity(ns, alive_pct, range_km, A, tries=3):
    # drop radios at random, build the graph, size of the biggest cluster. averaged over a few tries
    mrng = np.random.default_rng(1)
    out = []
    for nn in ns:
        acc = []
        for _ in range(tries):
            p = mrng.uniform(0, A, (int(nn * alive_pct / 100) + 1, 2))
            lab = _components(_graph(p, np.ones(len(p), bool), range_km))
            acc.append(max(np.bincount(lab)) / len(p))
        out.append(np.mean(acc))
    return out


def _readout_text(v, r):
    return (f"LIVE RESULTS (SF{int(v['sf'])}, {v['ptx']:.0f} dBm)\n"
            f"bit rate {r['rb']:.0f} b/s · sens {r['sens']:.1f} dBm\n"
            f"range {r['range_km']:.2f} km · degree k {r['mean_degree']:.1f}\n"
            f"connected {r['conn']:.0%} · hops ≈ {r['hops']:.1f}\n"
            f"ALOHA success {r['p_aloha']:.0%} · ToA {r['toa'] * 1e3:.0f} ms\n"
            f"Citizens reached (text): {r['reach']:.0%}")


def _flood_status(lvl, wave, n_gws):
    gw_hit = [g for g in lvl[-n_gws:] if 0 <= g <= wave]
    if gw_hit:
        return f"SOS reached a gateway in {int(min(gw_hit))} hops", C.COL["good"]
    if wave > max(lvl.max(), 0) + 1:
        return "SOS stuck on an island, no gateway in reach", C.COL["bad"]
    return f"flooding… hop {int(wave)}", C.INK


def build():
    v = defaults()
    A = C.MESH["area_km"]
    rng = np.random.default_rng(8)
    pts_all, order, gws, los_all = _radio_positions(rng)
    st = dict(r=evaluate(v), src=0, t=0, level=None, adj=None, n=0, alive=None)
    fig = new_figure(TITLE, "Optional extension that could complement the required layers: battery radios hop "
                            "SOS texts to a gateway, which sends them up via satellite", "SUPPLEMENTARY (OPTIONAL)")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_map = fig.add_subplot(gs[:, 0])
    ax_sf, ax_conn = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_toa, ax_alo = fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    sfs = np.arange(7, 13)
    mp = _setup_map(ax_map, terrain.load(), gws)
    ax_sf.set_title("Spreading factor trade-off: range vs speed")
    conn = _setup_connectivity(ax_conn)
    toa_lines, op_toa, toa_txt = _setup_airtime(ax_toa, sfs)
    op_alo, alo_txt = _setup_aloha(ax_alo)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def new_flood():
        idx = np.nonzero(st["alive"])[0]
        if len(idx) == 0:
            st["level"] = None
            return
        st["src"] = int(rng.choice(idx))
        st["level"] = _bfs(st["adj"], st["src"])
        st["t"] = 0

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        n = min(int(v["n"]), len(pts_all))
        pts = np.vstack([pts_all[:n], gws])
        alive = np.r_[order[:n] < v["alive"] / 100, [True] * len(gws)]
        idx = np.r_[np.arange(n), len(pts_all) + np.arange(len(gws))]
        r_clear = M.lora_range_km(int(v["sf"]), C.MESH["bw_khz"], v["ptx"], v["noise"], 6.0)  # ridge-free links
        st.update(pts=pts, alive=alive, adj=_graph(pts, alive, r_clear, los_all[np.ix_(idx, idx)]), n=n)
        ii, jj = np.nonzero(np.triu(st["adj"]))
        mp.edges.set_segments([[pts[i], pts[j]] for i, j in zip(ii, jj)])
        mp.dead.set_offsets(pts[~alive] if (~alive).any() else np.zeros((0, 2)))
        new_flood()

        _draw_sf_bars(ax_sf, v, sfs)
        ns = np.arange(10, 401, 10)
        k = [nn * v["alive"] / 100 / A ** 2 * math.pi * min(r["range_km"], A) ** 2 for nn in ns]
        conn.curve.set_data(ns, [M.giant_component(kk) for kk in k])
        ax_conn.set_xlim(0, 400)
        conn.sim.set_offsets(np.c_[ns[::4], _simulated_connectivity(ns[::4], v["alive"], r["range_km"], A)])
        conn.op.set_data([n], [r["conn"]])

        for sf, ln in toa_lines.items():
            ln.set_linewidth(3 if sf == int(v["sf"]) else 1.2)
        op_toa.set_data([C.MESH["payload"]], [r["toa"] * 1e3])
        toa_txt.set_text(f"SF{int(v['sf'])}, {C.MESH['payload']} B → {r['toa'] * 1e3:.0f} ms on air\n"
                         f"1 % duty cycle → max {36.0 / r['toa']:.0f} msgs/h per radio")
        toa_txt.set_color(C.COL["good"] if r["duty_ok"] else C.COL["bad"])
        op_alo.set_data([min(r["g"], 1.5)], [r["p_aloha"]])
        alo_txt.set_text(f"G = {r['g']:.3f} → {r['p_aloha']:.0%} delivered")
        ro.set_text(_readout_text(v, r))
        ro.set_color(status_colour(r["reach"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.70, 0.17), cols=2, rows=3)
    ctl.slider("sf", "Spreading factor SF", 7, 12, v["sf"], step=1, fmt="%.0f", color=ME_C)
    ctl.slider("ptx", "Tx power (dBm)", 2, 30, v["ptx"], step=1, fmt="%.0f", color=ME_C)
    ctl.slider("n", "Radios deployed", 20, 400, v["n"], step=10, fmt="%.0f", color=ME_C)
    ctl.slider("alive", "Radios with battery (%)", 10, 100, v["alive"], step=5, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("rate", "Messages per radio per hour", 1, 120, v["rate"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 25, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.reset_button([0.6, 0.045, 0.1, 0.03])
    ctl.button([0.49, 0.045, 0.1, 0.03], "✉  New SOS", new_flood)
    recompute(ctl.values)

    def step(frame):
        if not player.running or st["level"] is None:
            return
        pts, alive, lvl = st["pts"], st["alive"], st["level"]
        st["t"] += 1
        wave = st["t"] / 6.0  # hops travelled so far
        reached = (lvl >= 0) & (lvl <= wave)
        cols = np.where(~alive, "#00000000", np.where(reached, ME_C, "#6b6b66")).astype(object)
        cols[-len(gws):] = C.COL[C.L_SA]
        mp.nodes.set_offsets(pts)
        mp.nodes.set_color(list(cols))
        mp.nodes.set_sizes(np.where(reached & (lvl >= wave - 1), 60, 20))
        # the edges currently being "travelled", drawn partway along
        ii, jj = np.nonzero(st["adj"])
        front = (lvl[ii] == math.floor(wave)) & (lvl[jj] == math.floor(wave) + 1)
        frac = wave - math.floor(wave)
        mp.hot.set_segments([[pts[i], pts[i] + (pts[j] - pts[i]) * frac] for i, j in zip(ii[front], jj[front])])
        mp.src.set_data([pts[st["src"]][0]], [pts[st["src"]][1]])
        msg, col = _flood_status(lvl, wave, len(gws))
        mp.txt.set_text(f"{msg}\nnodes reached {reached.sum()} / {alive.sum()}")
        mp.txt.set_color(col)
        if wave > max(lvl.max(), 0) + 3:
            new_flood()

    return fig, step, ctl
