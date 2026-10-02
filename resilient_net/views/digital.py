"""LAYER 2 - Digital mobile network (PCM + digital modulation + cellular capacity).  Units III and IV."""
import math

import numpy as np
from matplotlib.patches import RegularPolygon, Circle

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

MO_C = C.COL[C.L_MO]
MOD_COL = {"ASK (OOK)": C.COL[C.L_AN], "BPSK": C.COL[C.L_MO], "QPSK": C.COL[C.L_SA], "16-QAM": C.COL[C.L_UAV]}
TITLE = "Layer 2 · Digital mobile network"


def defaults():
    d = C.DIGITAL
    return dict(fs=d["fs_khz"], bits=d["bits"], down=C.STORM["towers_down"], surge=C.STORM["surge"],
                noise=C.STORM["noise_rise"], split=d["split"], mod="QPSK")


def evaluate(v):
    p = {k: C.DIGITAL[k] for k in ("f_mhz", "ptx_dbm", "h_bs", "h_ms", "r_cell_km", "nf_db", "bw_mhz", "channels",
                                    "erl_per_cell")}
    return M.mobile_layer(towers_down=v["down"], surge=v["surge"], noise_rise=v["noise"], mod=v["mod"],
                          bits=int(v["bits"]), fs_khz=v["fs"], split=int(v["split"]), **p)


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    p = r["pcm"]
    d = C.DIGITAL
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_MO])
    ui.note("Role in the hybrid design: the everyday two-way voice/data network. It carries most traffic while "
            "towers stand, but it depends on ground power and backhaul, and it saturates when everyone calls.")
    ui.sub("Sampling and quantisation (PCM)")
    ui.calc("Nyquist rate", "fs ≥ 2W", f"2 × {d['w_khz']} kHz", f"{p['nyquist_khz']:.1f} kHz",
            f"→ chosen fs = {v['fs']:.1f} kHz {'(OK)' if p['ok'] else '(ALIASING!)'}")
    ui.calc("Sampling interval", "Ts = 1/fs", f"1 / {v['fs']:.1f} kHz", f"{p['ts_us']:.1f}", "µs")
    ui.calc("Quantisation levels", "L = 2ⁿ", f"2^{int(v['bits'])}", f"{p['levels']}")
    ui.calc("Step size", "Δ = 2Vmax / L", f"2 × 1 V / {p['levels']}", f"{p['step'] * 1e3:.3f}", "mV")
    ui.calc("Max quantisation error", "|e| ≤ Δ/2", f"{p['step'] * 1e3:.3f} / 2", f"{p['qerr_max'] * 1e3:.3f}", "mV")
    ui.calc("Quantisation noise power", "Nq = Δ²/12", f"({p['step']:.5f})² / 12", f"{p['qnoise']:.3e}", "V²")
    ui.calc("SQNR (full-scale sine)", "SQNR = 6.02n + 1.76", f"6.02 × {int(v['bits'])} + 1.76", f"{p['sqnr']:.2f}",
            "dB")
    ui.calc("Bit rate", "Rb = n · fs", f"{int(v['bits'])} × {v['fs']:.1f} kHz", f"{p['rb'] / 1e3:.1f}", "kbps")
    ui.sub("Transmission bandwidth for the PCM stream")
    for mod, k in M.MODS.items():
        q = M.pcm(fs_khz=v["fs"], bits=int(v["bits"]), mod=mod)
        ui.calc(mod, "B = Rb(1 + α) / log2M   (raised cosine, α = 0.35)",
                f"{p['rb'] / 1e3:.1f}k × 1.35 / {k}", f"{q['bw_rc'] / 1e3:.1f} kHz",
                f"(null-to-null {q['bw_null'] / 1e3:.1f} kHz)")
    ui.sub(f"Radio link at the edge of a surviving cell ({v['mod']})")
    ui.calc("Effective cell radius", "R' = R / √(1 − F)", f"{d['r_cell_km']} / √(1 − {v['down'] / 100:.2f})",
            f"{r['r_eff']:.2f}", "km")
    ui.calc("Okumura–Hata urban loss", "L = 69.55 + 26.16log f − 13.82log hb − a(hm) + (44.9 − 6.55log hb)log d",
            f"f = {d['f_mhz']:.0f} MHz, hb = {d['h_bs']:.0f} m, d = {r['r_eff']:.2f} km",
            f"{float(M.hata_urban(r['r_eff'], d['f_mhz'], d['h_bs'], d['h_ms'])):.1f}", "dB")
    ui.calc("Edge SNR", "SNR = Pt + G − L − penetration − N", "", f"{r['snr_edge']:.1f}", "dB")
    ui.calc("Eb/N0", "Eb/N0 = SNR + 10log(B/Rb)", f"{r['snr_edge']:.1f} + 10log({d['bw_mhz'] * 1e6:.0f}/{p['rb']:.0f})",
            f"{r['ebn0_edge']:.1f}", "dB")
    ui.calc("Bit error rate", {"ASK (OOK)": "Pb = Q(√(Eb/N0))", "BPSK": "Pb = Q(√(2Eb/N0))",
                               "QPSK": "Pb = Q(√(2Eb/N0))", "16-QAM": "Pb ≈ ¾ Q(√(0.8 Eb/N0))"}[v["mod"]],
            f"Eb/N0 = {r['ebn0_edge']:.1f} dB", f"{r['ber_edge']:.2e}")
    ui.sub("Capacity, cell splitting and blocking (Unit IV)")
    ui.calc("Co-channel C/I, cluster N = 7", "C/I = (√(3N))ⁿ / 6, n = 4", "(√21)⁴ / 6",
            f"{M.cochannel_ci(7):.1f}", "dB")
    ui.calc("Cell splitting", "cells × 4 per split, capacity × 4", f"split level {int(v['split'])}",
            f"{4 ** int(v['split'])}× capacity per km²")
    ui.calc("Offered load per surviving cell", "A = A0 · surge / (1 − F) / 4^split",
            f"{d['erl_per_cell']:.0f} × {v['surge']:.1f} / {r['surv']:.2f} / {4 ** int(v['split'])}",
            f"{r['load']:.1f}", "Erlang")
    ui.calc("Erlang-B blocking", "B(A, N) = (Aᴺ/N!) / Σ(Aᵏ/k!)", f"A = {r['load']:.1f}, N = {r['channels']}",
            f"{r['block']:.1%}")
    ui.kv("Area coverage of surviving cells", f"{r['coverage']:.1%}", r["coverage"] > 0.9)
    ui.bar("Citizens reached (two-way)", r["reach"], ui.LAYER_TINT[C.L_MO])
    return r


def build():
    v = defaults()
    rng = np.random.default_rng(11)
    st = dict(r=evaluate(v), calls=np.zeros((0, 4)), mc=None, const=None)
    fig = new_figure(TITLE, "PCM sampling & quantisation → digital modulation → noisy radio link → cells, "
                            "splitting and call blocking", "LAYER 2 · REQUIRED")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_pcm, ax_q, ax_con = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_ber, ax_cell, ax_erl = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    # (a) PCM sampling ----------------------------------------------------------
    W = C.DIGITAL["w_khz"]
    tt = np.linspace(0, 2.0, 1200)                         # ms
    l_sig, = ax_pcm.plot([], [], color=C.INK2, lw=1.6, label=f"voice tone {W} kHz")
    l_qnt, = ax_pcm.step([], [], where="mid", color=MO_C, lw=1.4, label="quantised")
    l_rec, = ax_pcm.plot([], [], color=C.COL["bad"], lw=1.3, ls="--", label="rebuilt from samples")
    stems = ax_pcm.vlines([], [], [], color=MO_C, lw=1)
    dots = ax_pcm.scatter([], [], s=14, color=MO_C, zorder=3)
    bits_txt = ax_pcm.text(0.01, 0.03, "", transform=ax_pcm.transAxes, family="monospace", fontsize=7.5,
                           color=MO_C)
    alias_txt = ax_pcm.text(0.99, 0.03, "", transform=ax_pcm.transAxes, ha="right", fontsize=7.5)
    ax_pcm.set(title="Sampling + quantisation (live)", xlabel="time (ms)", ylabel="V", xlim=(0, 2), ylim=(-1.5, 1.5))
    ax_pcm.legend(loc="upper right", fontsize=6.5, ncol=3)

    # (b) quantisation error / SQNR --------------------------------------------
    ax_q.set(title="SQNR vs bits: theory and simulation", xlabel="bits per sample n", ylabel="SQNR (dB)")
    ns = np.arange(2, 13)
    ax_q.plot(ns, 6.02 * ns + 1.76, color=C.INK2, ls="--", lw=1.5, label="6.02n + 1.76")
    x = np.sin(2 * np.pi * rng.random(40000))
    sim = [M.db(0.5 / np.mean((np.clip((np.floor(x / (2 / 2 ** n)) + 0.5) * (2 / 2 ** n), -1, 1) - x) ** 2))
           for n in ns]
    bars = ax_q.bar(ns, sim, color="#34363a", width=0.7, label="simulated")
    ax_q.legend(loc="upper left", fontsize=7)
    q_txt = ax_q.text(0.03, 0.72, "", transform=ax_q.transAxes, ha="left", va="top", fontsize=8, color=MO_C)

    # (c) constellation ----------------------------------------------------------
    ax_con.set_aspect("equal")
    ax_con.set(title="Received constellation at cell edge", xlabel="in-phase I", ylabel="quadrature Q",
               xlim=(-1.9, 1.9), ylim=(-1.9, 1.9))
    sc_ok = ax_con.scatter([], [], s=4, color=MO_C, alpha=0.5)
    sc_err = ax_con.scatter([], [], s=9, color=C.COL["bad"], alpha=0.9)
    sc_ref = ax_con.scatter([], [], s=60, marker="+", color=C.INK, zorder=4)
    bound_lines = []
    con_txt = ax_con.text(0.02, 0.97, "", transform=ax_con.transAxes, va="top", fontsize=7.5, color=C.INK)

    # (d) BER -------------------------------------------------------------------
    eb = np.linspace(-2, 22, 200)
    for mod, col in MOD_COL.items():
        ls = (0, (4, 3)) if mod == "BPSK" else "-"
        ax_ber.semilogy(eb, np.maximum(M.ber_theory(mod, eb), 1e-9), color=col, lw=1.6 if mod != "BPSK" else 2.4,
                        ls=ls, label=mod if mod != "BPSK" else "BPSK (= QPSK per bit)", alpha=0.9, zorder=3)
    mc_pts = ax_ber.scatter([], [], s=30, color=C.INK, zorder=4, label="Monte-Carlo")
    op_ber, = ax_ber.plot([], [], "o", ms=14, mfc="none", mec=C.INK, mew=2)
    ax_ber.axhline(1e-3, color=C.MUTED, ls=":", lw=1)
    ax_ber.text(-1.5, 1.4e-3, "voice target 10⁻³", fontsize=7, color=C.MUTED)
    ax_ber.set(title="Bit error rate vs Eb/N0", xlabel="Eb/N0 (dB)", ylabel="BER", ylim=(1e-7, 0.6), xlim=(-2, 22))
    ax_ber.legend(loc="lower left", fontsize=6.5, ncol=2)

    # (e) cell map ----------------------------------------------------------------
    centres = M.hex_cells(2, 1.0)
    order = rng.permutation(len(centres))
    ax_cell.set_aspect("equal")
    ax_cell.set(title="Cell layout under the storm", xlim=(-5, 5), ylim=(-4.4, 4.4), xticks=[], yticks=[])
    hexes = []
    for (cx, cy) in centres:
        h = RegularPolygon((cx, cy), 6, radius=1.0, orientation=0, fc=MO_C, ec=C.BG, lw=1.2, alpha=0.25)
        ax_cell.add_patch(h)
        hexes.append(h)
    towers = ax_cell.scatter(centres[:, 0], centres[:, 1], marker="^", s=40, color=C.INK, zorder=4)
    dead = ax_cell.scatter([], [], marker="x", s=55, color=C.COL["bad"], lw=2, zorder=5)
    split_patches = []
    for (cx, cy) in M.hex_cells(2, 0.5):
        if math.hypot(cx, cy) < 1.6:
            p = RegularPolygon((cx, cy), 6, radius=0.5, orientation=0, fc="none", ec=C.INK2, lw=0.8, ls="--")
            ax_cell.add_patch(p)
            split_patches.append(p)
    sc_calls = ax_cell.scatter([], [], s=16, zorder=6)
    cell_txt = ax_cell.text(0.02, 0.02, "", transform=ax_cell.transAxes, fontsize=7.5, color=C.INK)

    # (f) Erlang B ------------------------------------------------------------------
    ax_erl.set(title="Call blocking (Erlang-B)", xlabel="offered traffic per cell (Erlang)",
               ylabel="blocking probability", xlim=(0, 260), ylim=(0, 1))
    l_erl, = ax_erl.plot([], [], color=MO_C, lw=2)
    op_erl, = ax_erl.plot([], [], "o", ms=13, mfc="none", mec=C.INK, mew=2)
    ax_erl.axhline(0.02, color=C.MUTED, ls=":", lw=1)
    ax_erl.text(5, 0.04, "design GoS 2 %", fontsize=7, color=C.MUTED)
    erl_txt = ax_erl.text(0.97, 0.05, "", transform=ax_erl.transAxes, ha="right", fontsize=7.5, color=C.INK)
    vl_normal = ax_erl.axvline(C.DIGITAL["erl_per_cell"], color=C.COL["good"], lw=1, ls="--")
    ax_erl.text(C.DIGITAL["erl_per_cell"] + 3, 0.92, "normal day", fontsize=7, color=C.COL["good"])

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        p = r["pcm"]
        n = int(v["bits"])
        for b, k in zip(bars, ns):
            b.set_color(MO_C if k == n else "#34363a")
        q_txt.set_text(f"n = {n}: L = {p['levels']}, Δ = {p['step'] * 1e3:.2f} mV\nSQNR = {p['sqnr']:.1f} dB")
        # constellation reference + decision boundaries
        for ln in bound_lines:
            ln.remove()
        bound_lines.clear()
        mod = v["mod"]
        ref = {"ASK (OOK)": [0, math.sqrt(2)], "BPSK": [-1, 1]}.get(mod)
        if ref is not None:
            sc_ref.set_offsets(np.c_[ref, [0, 0]])
            bound_lines.append(ax_con.axvline(math.sqrt(2) / 2 if mod == "ASK (OOK)" else 0, color=C.INK2, lw=0.8,
                                              ls="--"))
        elif mod == "QPSK":
            s = 1 / math.sqrt(2)
            sc_ref.set_offsets([[a, b] for a in (-s, s) for b in (-s, s)])
            bound_lines.extend([ax_con.axvline(0, color=C.INK2, lw=0.8, ls="--"),
                            ax_con.axhline(0, color=C.INK2, lw=0.8, ls="--")])
        else:
            lv = np.array([-3, -1, 1, 3]) / math.sqrt(10)
            sc_ref.set_offsets([[a, b] for a in lv for b in lv])
            for b in (-2 / math.sqrt(10), 0, 2 / math.sqrt(10)):
                bound_lines.extend([ax_con.axvline(b, color=C.INK2, lw=0.8, ls="--"),
                                ax_con.axhline(b, color=C.INK2, lw=0.8, ls="--")])
        st["const"] = None
        # BER Monte-Carlo
        pts = np.arange(0, 14, 2)
        mrng = np.random.default_rng(5)
        mc = [M.monte_carlo_ber(mod, e, 60000, mrng) for e in pts]
        okp = np.array(mc) > 0
        mc_pts.set_offsets(np.c_[pts[okp], np.array(mc)[okp]])
        mc_pts.set_color(MOD_COL[mod])
        op_ber.set_data([np.clip(r["ebn0_edge"], -2, 22)], [max(r["ber_edge"], 1.2e-7)])
        # cells
        k_dead = int(round(v["down"] / 100 * len(centres)))
        dead_idx = set(order[:k_dead].tolist())
        for i, h in enumerate(hexes):
            h.set_facecolor("#3a2224" if i in dead_idx else MO_C)
            h.set_alpha(0.55 if i in dead_idx else 0.18 + 0.25 * r["coverage"])
        alive = [i for i in range(len(centres)) if i not in dead_idx]
        towers.set_offsets(centres[alive] if alive else np.zeros((0, 2)))
        dead.set_offsets(centres[list(dead_idx)] if dead_idx else np.zeros((0, 2)))
        for sp in split_patches:
            sp.set_visible(int(v["split"]) >= 1)
        st["dead"] = dead_idx
        cell_txt.set_text(f"{len(alive)}/{len(centres)} towers alive · R' = {r['r_eff']:.2f} km · "
                          f"split ×{4 ** int(v['split'])}")
        A = np.linspace(0.1, 260, 160)
        l_erl.set_data(A, [M.erlang_b(a, r["channels"]) for a in A])
        op_erl.set_data([min(r["load"], 259)], [r["block"]])
        erl_txt.set_text(f"{r['channels']} channels/cell ({mod})\nload {r['load']:.0f} E → blocking {r['block']:.0%}")
        bw = M.pcm(fs_khz=v["fs"], bits=n, mod=mod)["bw_rc"]
        ro.set_text(
            f"LIVE RESULTS ({mod})\n"
            f"Rb = {p['rb'] / 1e3:.0f} kbps   B = {bw / 1e3:.1f} kHz\n"
            f"Edge SNR {r['snr_edge']:.1f} dB  Eb/N0 {r['ebn0_edge']:.1f} dB\n"
            f"BER {r['ber_edge']:.1e}   coverage {r['coverage']:.0%}\n"
            f"Blocking {r['block']:.0%}  ({r['load']:.0f} E / {r['channels']} ch)\n"
            f"Citizens reached (two-way): {r['reach']:.0%}")
        ro.set_color(status_colour(r["reach"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=3)
    ctl.slider("fs", "Sampling fs (kHz)", 2, 16, v["fs"], step=0.5, fmt="%.1f")
    ctl.slider("bits", "Bits per sample n", 2, 12, v["bits"], step=1, fmt="%.0f")
    ctl.slider("split", "Cell-split level", 0, 2, v["split"], step=1, fmt="%.0f")
    ctl.slider("down", "Towers destroyed (%)", 0, 90, v["down"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("surge", "Call surge (× normal)", 1, 10, v["surge"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.slider("noise", "Storm noise rise (dB)", 0, 25, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.radio("mod", "Modulation", list(M.MODS), v["mod"], [0.595, 0.075, 0.13, 0.13])
    ctl.reset_button([0.595, 0.038, 0.13, 0.03], "↺  Reset to red dots")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        r = st["r"]
        ph = frame * 0.02
        sig = np.sin(2 * np.pi * W * (tt + ph))
        fs = v["fs"]
        ts = np.arange(0, 2.0, 1 / fs)
        smp = np.sin(2 * np.pi * W * (ts + ph))
        L = 2 ** int(v["bits"])
        dlt = 2 / L
        qs = np.clip((np.floor(smp / dlt) + 0.5) * dlt, -1 + dlt / 2, 1 - dlt / 2)
        l_sig.set_data(tt, sig)
        idx = np.minimum((tt * fs).astype(int), len(qs) - 1)
        l_qnt.set_data(tt, qs[idx])
        rec = np.sum(qs[None, :] * np.sinc(fs * (tt[:, None] - ts[None, :])), axis=1)
        l_rec.set_data(tt, rec)
        stems.set_segments([[(a, 0), (a, b)] for a, b in zip(ts, qs)])
        dots.set_offsets(np.c_[ts, qs])
        code = int((qs[-1] + 1) / dlt - 0.5)
        bits_txt.set_text("last sample → " + format(max(0, min(L - 1, code)), f"0{int(v['bits'])}b"))
        if fs >= 2 * W:
            alias_txt.set_text("fs ≥ 2W ✓ no aliasing")
            alias_txt.set_color(C.COL["good"])
        else:
            fa = abs(W - fs * round(W / fs))
            alias_txt.set_text(f"fs < 2W ✗ aliasing → heard as {fa:.1f} kHz")
            alias_txt.set_color(C.COL["bad"])
        # constellation: accumulate received symbols at the edge Eb/N0
        crng = np.random.default_rng(frame)
        sym, bits = M.modulate(v["mod"], 240, crng)
        rx = M.add_awgn(sym, v["mod"], r["ebn0_edge"], crng)
        dec = M.demodulate(v["mod"], rx)
        k = M.MODS[v["mod"]]
        wrong = np.any((dec != bits).reshape(-1, k), axis=1)
        old = st["const"] if st["const"] is not None else np.zeros((0, 3))
        new = np.c_[rx.real, rx.imag, wrong]
        allp = np.vstack([old, new])[-2500:]
        st["const"] = allp
        sc_ok.set_offsets(allp[allp[:, 2] == 0, :2])
        sc_err.set_offsets(allp[allp[:, 2] == 1, :2] if (allp[:, 2] == 1).any() else np.zeros((0, 2)))
        ser = allp[:, 2].mean()
        con_txt.set_text(f"{v['mod']} @ Eb/N0 {r['ebn0_edge']:.1f} dB\nsymbol errors {ser:.2%}")
        # call attempts on the cell map
        nc = 4
        pos = np.c_[crng.uniform(-4.2, 4.2, nc), crng.uniform(-3.8, 3.8, nc)]
        ok = crng.random(nc) < r["coverage"] * (1 - r["block"])
        d = np.hypot(pos[:, None, 0] - centres[None, :, 0], pos[:, None, 1] - centres[None, :, 1]).min(axis=1)
        ok &= d < 1.6
        calls = np.vstack([st["calls"], np.c_[pos, ok, np.zeros(nc)]])
        calls[:, 3] += 1
        calls = calls[calls[:, 3] < 25]
        st["calls"] = calls
        sc_calls.set_offsets(calls[:, :2])
        cols = np.array([C.COL["good"] if c else C.COL["bad"] for c in calls[:, 2]])
        sc_calls.set_color(cols)
        sc_calls.set_alpha(None)
        sc_calls.set_sizes(10 + 30 * (1 - calls[:, 3] / 25))
        op_ber.set_markersize(11 + 4 * abs(math.sin(frame * 0.2)))

    return fig, step, ctl
