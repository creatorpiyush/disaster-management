"""NOISE & SIGNAL-QUALITY LAB - Gaussian (and storm impulsive) noise, SNR, eye diagram and live BER.

Assignment section 3: model how background noise affects signal clarity, compute / simulate SNR and BER.
"""
import math

import numpy as np

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

TITLE = "Noise & signal-quality lab"
SIG_C, NOI_C = C.COL[C.L_MO], C.COL[C.L_AN]
SPS = 16


def defaults():
    return dict(ebn0=8.0, imp=0.0, kimp=15.0, alpha=0.35, mod="BPSK")


def rc_pulse(alpha, sps=SPS, span=6):
    t = np.arange(-span * sps, span * sps + 1) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.sinc(t) * np.cos(np.pi * alpha * t) / (1 - (2 * alpha * t) ** 2)
    sing = np.isclose(np.abs(2 * alpha * t), 1)
    h[sing] = np.pi / 4 * np.sinc(1 / (2 * alpha))
    return h


def ber_impulsive(mod, ebn0_db, p, k_db):
    return (1 - p) * M.ber_theory(mod, ebn0_db) + p * M.ber_theory(mod, ebn0_db - k_db)


def print_calculations(v=None):
    v = v or defaults()
    ui.head(TITLE.upper(), ui.cyan)
    ui.note("AWGN model: r = s + n with n ~ N(0, N0/2) per dimension. The storm adds impulsive noise "
            "(lightning, arcing power lines): with probability p a sample sees noise K dB stronger.")
    g = M.undb(v["ebn0"])
    for mod in M.MODS:
        k = M.MODS[mod]
        ui.calc(f"{mod}", "SNR = Es/N0 = k·Eb/N0  ·  BER from Q-function",
                f"Eb/N0 = {v['ebn0']:.1f} dB, k = {k}",
                f"SNR {v['ebn0'] + 10 * math.log10(k):.1f} dB · BER {float(M.ber_theory(mod, v['ebn0'])):.2e} · "
                f"Monte-Carlo {M.monte_carlo_ber(mod, v['ebn0'], 200000):.2e}")
    ui.calc("Shannon capacity", "C/B = log2(1 + SNR)", f"SNR = {v['ebn0']:.1f} dB",
            f"{math.log2(1 + g):.2f}", "bit/s/Hz")
    ui.sub("SNR of each layer at the default storm")
    e = M.evaluate_all(M.storm_from_intensity(0.4))
    L = e["layers"]
    ui.kv(C.L_AN + " (FM output SNR)", f"{L[C.L_AN]['snr_fm']:.1f} dB")
    ui.kv(C.L_MO + " (cell-edge SNR)", f"{L[C.L_MO]['snr_edge']:.1f} dB")
    ui.kv(C.L_SA + " (Eb/N0)", f"{L[C.L_SA]['ebn0']:.1f} dB")
    ui.kv(C.L_MESH + " (LoRa demod. threshold)", f"{M.LORA_SNR_REQ[C.MESH['sf']]:.1f} dB")


def build():
    v = defaults()
    rng = np.random.default_rng(21)
    st = dict(err=0, bits=0, hist=np.zeros(80), traces=[], const=np.zeros((0, 3)), tbuf=None, h=rc_pulse(0.35),
              conv=[])
    fig = new_figure(TITLE, "Live Monte-Carlo: Gaussian + storm impulsive noise → waveform, noise statistics, eye "
                            "diagram, constellation and a BER estimate that converges in front of you",
                     "NOISE · SNR · BER")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_t, ax_h, ax_eye = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_c, ax_b, ax_s = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    l_tx, = ax_t.plot([], [], color=SIG_C, lw=2, label="transmitted")
    l_rx, = ax_t.plot([], [], color=NOI_C, lw=0.9, alpha=0.9, label="received (signal + noise)")
    sc_dec = ax_t.scatter([], [], s=30, zorder=4)
    ax_t.set(title="Signal through the noisy channel (I branch)", xlabel="symbol index", ylabel="amplitude",
             xlim=(0, 16), ylim=(-3.5, 3.5))
    ax_t.legend(loc="upper right", fontsize=7, ncol=2)
    t_txt = ax_t.text(0.02, 0.04, "", transform=ax_t.transAxes, fontsize=7.5, color=C.INK2)

    edges = np.linspace(-4, 4, 81)
    centres = (edges[:-1] + edges[1:]) / 2
    bars = ax_h.bar(centres, np.full(80, 1e-9), width=0.1, color=NOI_C, alpha=0.75, label="measured noise")
    l_pdf, = ax_h.plot([], [], color=C.INK, lw=1.6, label="Gaussian pdf (theory)")
    ax_h.set(title="Noise amplitude distribution", xlabel="noise sample value (normalised to σ)",
             ylabel="probability density (log)", yscale="log", ylim=(1e-5, 1), xlim=(-4, 4))
    ax_h.legend(loc="upper right", fontsize=7)
    h_txt = ax_h.text(0.02, 0.95, "", transform=ax_h.transAxes, va="top", fontsize=7.5, color=C.INK2)

    eye_lines = ax_eye.plot(np.zeros((2 * SPS + 1, 60)), np.zeros((2 * SPS + 1, 60)), color=SIG_C, lw=0.6,
                            alpha=0.35)
    ax_eye.axvline(0, color=C.INK2, ls=":", lw=1)
    ax_eye.set(title="Eye diagram (accumulating)", xlabel="time (symbol periods)", ylabel="amplitude",
               xlim=(-1, 1), ylim=(-2.6, 2.6))
    eye_txt = ax_eye.text(0.02, 0.95, "", transform=ax_eye.transAxes, va="top", fontsize=7.5, color=C.INK)

    ax_c.set_aspect("equal")
    sc_ok = ax_c.scatter([], [], s=4, color=SIG_C, alpha=0.5)
    sc_bad = ax_c.scatter([], [], s=9, color=C.COL["bad"])
    ax_c.set(title="Constellation (red = wrong decision)", xlabel="I", ylabel="Q", xlim=(-2, 2), ylim=(-2, 2))

    eb = np.linspace(-2, 20, 200)
    l_gauss, = ax_b.semilogy([], [], color=C.INK2, lw=1.5, ls="--", label="theory, Gaussian only")
    l_imp, = ax_b.semilogy([], [], color=NOI_C, lw=2, label="theory, + impulsive storm noise")
    live = ax_b.errorbar([0], [0.1], yerr=[[0.01], [0.01]], fmt="o", color=C.INK, ms=8, capsize=4,
                         label="live Monte-Carlo (95 % CI)")
    ax_b.axhline(1e-3, color=C.MUTED, ls=":", lw=1)
    ax_b.set(title="Bit error rate: live estimate vs theory", xlabel="Eb/N0 (dB)", ylabel="BER",
             ylim=(1e-6, 0.6), xlim=(-2, 20))
    ax_b.legend(loc="lower left", fontsize=7)
    b_txt = ax_b.text(0.97, 0.95, "", transform=ax_b.transAxes, ha="right", va="top", fontsize=7.5, color=C.INK)

    sn = np.linspace(-20, 40, 300)
    ax_s.plot(sn, np.log2(1 + M.undb(sn)), color=C.INK, lw=2, label="Shannon limit log2(1+SNR)")
    for mod, col in zip(M.MODS, [C.COL[C.L_AN], C.COL[C.L_MO], C.COL[C.L_SA], C.COL[C.L_UAV]]):
        k = M.MODS[mod]
        req = M.required_ebn0(mod) + 10 * math.log10(k)
        ax_s.plot([req], [k], "o", color=col, ms=9, mec=C.BG)
        dx, dy, ha = {"ASK (OOK)": (1, -0.45, "left"), "BPSK": (-1, 0.25, "right")}.get(mod, (1, 0.1, "left"))
        ax_s.text(req + dx, k + dy, f"{mod} @BER 10⁻³", fontsize=7, color=C.INK2, ha=ha)
    e = M.evaluate_all(M.storm_from_intensity(0.4))
    L = e["layers"]
    marks = [(C.L_MESH, M.LORA_SNR_REQ[C.MESH["sf"]]), (C.L_SA, L[C.L_SA]["ebn0"] + 3),
             (C.L_MO, L[C.L_MO]["snr_edge"]), (C.L_AN, L[C.L_AN]["link_fm"]["cnr"])]
    for i, (lay, s) in enumerate(marks):
        ax_s.axvline(s, color=C.COL[lay], lw=1.2, ls="--", alpha=0.9)
        ax_s.text(s + 0.5, 7.4 - 0.75 * i, C.SHORT[lay], fontsize=7, color=C.COL[lay])
    cur = ax_s.axvline(0, color=C.INK, lw=2)
    ax_s.set(title="Capacity limit and where each layer operates", xlabel="SNR (dB)",
             ylabel="spectral efficiency (bit/s/Hz)", xlim=(-20, 40), ylim=(0, 8))
    ax_s.legend(loc="lower right", fontsize=7)

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        st.update(err=0, bits=0, hist=np.zeros(80), traces=[], const=np.zeros((0, 3)), h=rc_pulse(v["alpha"]),
                  conv=[])
        p = v["imp"] / 100
        l_gauss.set_data(eb, np.maximum(M.ber_theory(v["mod"], eb), 1e-9))
        l_imp.set_data(eb, np.maximum(ber_impulsive(v["mod"], eb, p, v["kimp"]), 1e-9))
        x = np.linspace(-4, 4, 200)
        l_pdf.set_data(x, np.exp(-x ** 2 / 2) / math.sqrt(2 * math.pi))
        cur.set_xdata([v["ebn0"] + 10 * math.log10(M.MODS[v["mod"]])] * 2)
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=2)
    ctl.slider("ebn0", "Eb/N0 (dB)", -2, 20, v["ebn0"], step=0.5, fmt="%.1f", color=SIG_C)
    ctl.slider("alpha", "Roll-off α", 0.05, 1.0, v["alpha"], step=0.05, fmt="%.2f", color=SIG_C)
    ctl.slider("imp", "Impulsive noise (% of samples)", 0, 20, v["imp"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.slider("kimp", "Impulse strength (dB)", 0, 25, v["kimp"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.radio("mod", "Modulation", list(M.MODS), v["mod"], [0.595, 0.075, 0.13, 0.13])
    ctl.reset_button([0.595, 0.038, 0.13, 0.03], "↺  Reset to red dots")
    recompute(ctl.values)

    def noise(n, sigma, p, kdb):
        w = rng.standard_normal(n) * sigma
        hit = rng.random(n) < p
        w[hit] *= math.sqrt(M.undb(kdb))
        return w

    def step(frame):
        if not player.running:
            return
        mod = v["mod"]
        k = M.MODS[mod]
        p = v["imp"] / 100
        # ---- symbol-level Monte-Carlo for BER ---------------------------------
        nb = 6000 - 6000 % k
        sym, bits = M.modulate(mod, nb, rng)
        n0 = 1.0 / (k * M.undb(v["ebn0"]))
        sig = math.sqrt(n0 / 2)
        wi, wq = noise(len(sym), sig, p, v["kimp"]), noise(len(sym), sig, p, v["kimp"])
        rx = sym + wi + 1j * wq
        dec = M.demodulate(mod, rx)
        st["err"] += int(np.sum(dec != bits))
        st["bits"] += len(bits)
        ber = st["err"] / st["bits"]
        st["conv"].append(ber)
        # histogram of normalised noise
        hcount, _ = np.histogram(wi / sig, bins=edges)
        st["hist"] += hcount
        dens = st["hist"] / max(st["hist"].sum(), 1) / 0.1
        for b, d in zip(bars, dens):
            b.set_height(max(d, 1e-9))
        kurt = float(np.mean((wi / sig) ** 4))
        h_txt.set_text(f"σ = {sig:.3f}   kurtosis = {kurt:.1f}  (Gaussian = 3)")
        # constellation
        wrong = np.any((dec != bits).reshape(-1, k), axis=1)
        new = np.c_[rx.real[:300], rx.imag[:300], wrong[:300]]
        cp = np.vstack([st["const"], new])[-3000:]
        st["const"] = cp
        sc_ok.set_offsets(cp[cp[:, 2] == 0, :2])
        sc_bad.set_offsets(cp[cp[:, 2] == 1, :2] if (cp[:, 2] == 1).any() else np.zeros((0, 2)))
        # ---- waveform-level view (pulse shaped) ---------------------------------
        h = st["h"]
        ns = 40
        a = sym[:ns].real * (1 if mod != "ASK (OOK)" else 1)
        up = np.zeros(ns * SPS)
        up[::SPS] = a
        tx = np.convolve(up, h, mode="same")
        wn = noise(len(tx), 1.0, p, v["kimp"])
        hn = h / math.sqrt(np.sum(h ** 2))
        rxw = tx + np.convolve(wn, hn, mode="same") * sig
        s0 = 8 * SPS
        seg = slice(s0, s0 + 16 * SPS)
        tt = np.arange(16 * SPS) / SPS
        l_tx.set_data(tt, tx[seg])
        l_rx.set_data(tt, rxw[seg])
        samp = rxw[s0:s0 + 16 * SPS:SPS]
        truth = a[8:24]
        thr = math.sqrt(2) / 2 if mod == "ASK (OOK)" else 0
        if mod == "16-QAM":
            lv = np.array([-3, -1, 1, 3]) / math.sqrt(10)
            dec_w = lv[np.argmin(np.abs(samp[:, None] - lv[None, :]), axis=1)]
            ok = np.isclose(dec_w, truth)
        else:
            ok = (samp > thr) == (truth > thr)
        sc_dec.set_offsets(np.c_[np.arange(16), samp])
        sc_dec.set_color([C.COL["good"] if o else C.COL["bad"] for o in ok])
        t_txt.set_text(f"{(~ok).sum()} wrong decisions in this window")
        # eye: overlay 2-symbol slices
        for i in range(10, 30):
            st["traces"].append(rxw[i * SPS - SPS:i * SPS + SPS + 1])
        st["traces"] = st["traces"][-60:]
        x = np.linspace(-1, 1, 2 * SPS + 1)
        for ln, tr in zip(eye_lines, st["traces"]):
            ln.set_data(x, tr)
        mid = np.array([tr[SPS] for tr in st["traces"]])
        if mod in ("BPSK", "QPSK"):
            pos, neg = mid[mid > 0], mid[mid <= 0]
            opening = (pos.min() - neg.max()) if len(pos) and len(neg) else 0
            eye_txt.set_text(f"eye opening {max(opening, 0):.2f}" + ("" if opening > 0 else "  (eye CLOSED)"))
            eye_txt.set_color(C.COL["good"] if opening > 0 else C.COL["bad"])
        else:
            eye_txt.set_text("multi-level eye")
            eye_txt.set_color(C.INK)
        # live BER point
        ci = 1.96 * math.sqrt(max(ber * (1 - ber), 1e-12) / st["bits"])
        y = max(ber, 1.1e-6)
        lo = max(min(ci, y - 1e-6), 0)
        live.lines[0].set_data([v["ebn0"]], [y])
        try:
            seg_ = [[(v["ebn0"], max(y - lo, 1e-6)), (v["ebn0"], y + ci)]]
            live.lines[2][0].set_segments(seg_)
            live.lines[1][0].set_data([v["ebn0"]], [max(y - lo, 1e-6)])
            live.lines[1][1].set_data([v["ebn0"]], [y + ci])
        except (IndexError, TypeError):
            pass
        th = float(ber_impulsive(mod, v["ebn0"], p, v["kimp"]))
        b_txt.set_text(f"{st['bits']:,} bits simulated\nmeasured {ber:.2e}\ntheory   {th:.2e}")
        snr = v["ebn0"] + 10 * math.log10(k)
        ro.set_text(
            f"LIVE RESULTS ({mod})\n"
            f"Eb/N0 {v['ebn0']:.1f} dB → SNR {snr:.1f} dB\n"
            f"impulsive {v['imp']:.1f} % at +{v['kimp']:.0f} dB\n"
            f"BER measured {ber:.2e}\n"
            f"BER theory   {th:.2e}\n"
            f"Shannon C/B {math.log2(1 + M.undb(snr)):.2f} bit/s/Hz")
        ro.set_color(status_colour(1 - min(1, ber * 300)))

    return fig, step, ctl
