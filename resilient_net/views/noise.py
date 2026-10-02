"""Noise lab (assignment section 3): AWGN + impulsive storm noise, SNR, eye diagram, live BER."""
import math
from types import SimpleNamespace

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


EDGES = np.linspace(-4, 4, 81)  # noise histogram bins (in units of sigma)


def _noise(rng, n, sigma, p, kdb):
    # gaussian, plus a fraction p of samples hit by an impulse kdb stronger
    w = rng.standard_normal(n) * sigma
    w[rng.random(n) < p] *= math.sqrt(M.undb(kdb))
    return w


def _setup_wave(ax):
    wv = SimpleNamespace()
    wv.tx, = ax.plot([], [], color=SIG_C, lw=2, label="transmitted")
    wv.rx, = ax.plot([], [], color=NOI_C, lw=0.9, alpha=0.9, label="received (signal + noise)")
    wv.dec = ax.scatter([], [], s=30, zorder=4)
    ax.set(title="Signal through the noisy channel (I branch)", xlabel="symbol index", ylabel="amplitude",
           xlim=(0, 16), ylim=(-3.5, 3.5))
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    wv.txt = ax.text(0.02, 0.04, "", transform=ax.transAxes, fontsize=7.5, color=C.INK2)
    return wv


def _setup_hist(ax):
    hs = SimpleNamespace()
    centres = (EDGES[:-1] + EDGES[1:]) / 2
    hs.bars = ax.bar(centres, np.full(80, 1e-9), width=0.1, color=NOI_C, alpha=0.75, label="measured noise")
    hs.pdf, = ax.plot([], [], color=C.INK, lw=1.6, label="Gaussian pdf (theory)")
    ax.set(title="Noise amplitude distribution", xlabel="noise sample value (normalised to σ)",
           ylabel="probability density (log)", yscale="log", ylim=(1e-5, 1), xlim=(-4, 4))
    ax.legend(loc="upper right", fontsize=7)
    hs.txt = ax.text(0.02, 0.95, "", transform=ax.transAxes, va="top", fontsize=7.5, color=C.INK2)
    return hs


def _setup_eye(ax):
    lines = ax.plot(np.zeros((2 * SPS + 1, 60)), np.zeros((2 * SPS + 1, 60)), color=SIG_C, lw=0.6, alpha=0.35)
    ax.axvline(0, color=C.INK2, ls=":", lw=1)
    ax.set(title="Eye diagram (accumulating)", xlabel="time (symbol periods)", ylabel="amplitude",
           xlim=(-1, 1), ylim=(-2.6, 2.6))
    txt = ax.text(0.02, 0.95, "", transform=ax.transAxes, va="top", fontsize=7.5, color=C.INK)
    return lines, txt


def _setup_ber(ax):
    bs = SimpleNamespace()
    bs.gauss, = ax.semilogy([], [], color=C.INK2, lw=1.5, ls="--", label="theory, Gaussian only")
    bs.imp, = ax.semilogy([], [], color=NOI_C, lw=2, label="theory, + impulsive storm noise")
    bs.live = ax.errorbar([0], [0.1], yerr=[[0.01], [0.01]], fmt="o", color=C.INK, ms=8, capsize=4,
                          label="live Monte-Carlo (95 % CI)")
    ax.axhline(1e-3, color=C.MUTED, ls=":", lw=1)
    ax.set(title="Bit error rate: live estimate vs theory", xlabel="Eb/N0 (dB)", ylabel="BER",
           ylim=(1e-6, 0.6), xlim=(-2, 20))
    ax.legend(loc="lower left", fontsize=7)
    bs.txt = ax.text(0.97, 0.95, "", transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=C.INK)
    return bs


def _setup_shannon(ax):
    sn = np.linspace(-20, 40, 300)
    ax.plot(sn, np.log2(1 + M.undb(sn)), color=C.INK, lw=2, label="Shannon limit log2(1+SNR)")
    for mod, col in zip(M.MODS, [C.COL[C.L_AN], C.COL[C.L_MO], C.COL[C.L_SA], C.COL[C.L_UAV]]):
        k = M.MODS[mod]
        req = M.required_ebn0(mod) + 10 * math.log10(k)
        ax.plot([req], [k], "o", color=col, ms=9, mec=C.BG)
        dx, dy, ha = {"ASK (OOK)": (1, -0.45, "left"), "BPSK": (-1, 0.25, "right")}.get(mod, (1, 0.1, "left"))
        ax.text(req + dx, k + dy, f"{mod} @BER 10⁻³", fontsize=7, color=C.INK2, ha=ha)
    # where each layer actually sits in the default storm
    L = M.evaluate_all(M.storm_from_intensity(0.4))["layers"]
    marks = [(C.L_MESH, M.LORA_SNR_REQ[C.MESH["sf"]]), (C.L_SA, L[C.L_SA]["ebn0"] + 3),
             (C.L_MO, L[C.L_MO]["snr_edge"]), (C.L_AN, L[C.L_AN]["link_fm"]["cnr"])]
    for i, (lay, x) in enumerate(marks):
        ax.axvline(x, color=C.COL[lay], lw=1.2, ls="--", alpha=0.9)
        ax.text(x + 0.5, 7.4 - 0.75 * i, C.SHORT[lay], fontsize=7, color=C.COL[lay])
    cur = ax.axvline(0, color=C.INK, lw=2)
    ax.set(title="Capacity limit and where each layer operates", xlabel="SNR (dB)",
           ylabel="spectral efficiency (bit/s/Hz)", xlim=(-20, 40), ylim=(0, 8))
    ax.legend(loc="lower right", fontsize=7)
    return cur


def _shaped_waveform(rng, sym, h, sig, p, kimp, ns=40):
    # first ns symbols, raised-cosine shaped, + noise filtered by the same (normalised) pulse
    a = sym[:ns].real
    up = np.zeros(ns * SPS)
    up[::SPS] = a
    tx = np.convolve(up, h, mode="same")
    wn = _noise(rng, len(tx), 1.0, p, kimp)
    rxw = tx + np.convolve(wn, h / math.sqrt(np.sum(h ** 2)), mode="same") * sig
    return a, tx, rxw


def _decisions(mod, samp, truth):
    if mod == "16-QAM":
        lv = np.array([-3, -1, 1, 3]) / math.sqrt(10)
        return np.isclose(lv[np.argmin(np.abs(samp[:, None] - lv[None, :]), axis=1)], truth)
    thr = math.sqrt(2) / 2 if mod == "ASK (OOK)" else 0
    return (samp > thr) == (truth > thr)


def _draw_eye(lines, txt, traces, mod):
    x = np.linspace(-1, 1, 2 * SPS + 1)
    for ln, tr in zip(lines, traces):
        ln.set_data(x, tr)
    if mod not in ("BPSK", "QPSK"):
        txt.set_text("multi-level eye")
        txt.set_color(C.INK)
        return
    mid = np.array([tr[SPS] for tr in traces])
    pos, neg = mid[mid > 0], mid[mid <= 0]
    opening = (pos.min() - neg.max()) if len(pos) and len(neg) else 0
    txt.set_text(f"eye opening {max(opening, 0):.2f}" + ("" if opening > 0 else "  (eye CLOSED)"))
    txt.set_color(C.COL["good"] if opening > 0 else C.COL["bad"])


def _draw_live_ber(live, ebn0, ber, nbits):
    # point + 95% confidence bar. errorbar artists are awkward to update, hence the poking around
    ci = 1.96 * math.sqrt(max(ber * (1 - ber), 1e-12) / nbits)
    y = max(ber, 1.1e-6)
    lo = max(min(ci, y - 1e-6), 0)
    live.lines[0].set_data([ebn0], [y])
    try:
        live.lines[2][0].set_segments([[(ebn0, max(y - lo, 1e-6)), (ebn0, y + ci)]])
        live.lines[1][0].set_data([ebn0], [max(y - lo, 1e-6)])
        live.lines[1][1].set_data([ebn0], [y + ci])
    except (IndexError, TypeError):
        pass


def _readout_text(v, ber, theory):
    snr = v["ebn0"] + 10 * math.log10(M.MODS[v["mod"]])
    return (f"LIVE RESULTS ({v['mod']})\n"
            f"Eb/N0 {v['ebn0']:.1f} dB → SNR {snr:.1f} dB\n"
            f"impulsive {v['imp']:.1f} % at +{v['kimp']:.0f} dB\n"
            f"BER measured {ber:.2e}\n"
            f"BER theory   {theory:.2e}\n"
            f"Shannon C/B {math.log2(1 + M.undb(snr)):.2f} bit/s/Hz")


def build():
    v = defaults()
    rng = np.random.default_rng(21)
    st = dict(err=0, bits=0, hist=np.zeros(80), traces=[], const=np.zeros((0, 3)), h=rc_pulse(0.35))
    fig = new_figure(TITLE, "Monte-Carlo with Gaussian + impulsive storm noise: waveform, noise histogram, eye "
                            "diagram, constellation, BER converging as it runs",
                     "NOISE / SNR / BER")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_t, ax_h, ax_eye = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_c, ax_b, ax_s = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    wave = _setup_wave(ax_t)
    hist = _setup_hist(ax_h)
    eye_lines, eye_txt = _setup_eye(ax_eye)
    ax_c.set_aspect("equal")
    sc_ok = ax_c.scatter([], [], s=4, color=SIG_C, alpha=0.5)
    sc_bad = ax_c.scatter([], [], s=9, color=C.COL["bad"])
    ax_c.set(title="Constellation (red = wrong decision)", xlabel="I", ylabel="Q", xlim=(-2, 2), ylim=(-2, 2))
    eb = np.linspace(-2, 20, 200)
    berp = _setup_ber(ax_b)
    cur = _setup_shannon(ax_s)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        # any change restarts the Monte-Carlo from scratch
        st.update(err=0, bits=0, hist=np.zeros(80), traces=[], const=np.zeros((0, 3)), h=rc_pulse(v["alpha"]))
        berp.gauss.set_data(eb, np.maximum(M.ber_theory(v["mod"], eb), 1e-9))
        berp.imp.set_data(eb, np.maximum(ber_impulsive(v["mod"], eb, v["imp"] / 100, v["kimp"]), 1e-9))
        x = np.linspace(-4, 4, 200)
        hist.pdf.set_data(x, np.exp(-x ** 2 / 2) / math.sqrt(2 * math.pi))
        cur.set_xdata([v["ebn0"] + 10 * math.log10(M.MODS[v["mod"]])] * 2)
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.57, 0.17), cols=2, rows=2)
    ctl.slider("ebn0", "Eb/N0 (dB)", -2, 20, v["ebn0"], step=0.5, fmt="%.1f", color=SIG_C)
    ctl.slider("alpha", "Roll-off α", 0.05, 1.0, v["alpha"], step=0.05, fmt="%.2f", color=SIG_C)
    ctl.slider("imp", "Impulsive noise (% of samples)", 0, 20, v["imp"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.slider("kimp", "Impulse strength (dB)", 0, 25, v["kimp"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.radio("mod", "Modulation", list(M.MODS), v["mod"], [0.595, 0.075, 0.13, 0.13])
    ctl.reset_button([0.595, 0.038, 0.13, 0.03], "Reset to red dots")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        mod, p = v["mod"], v["imp"] / 100
        k = M.MODS[mod]

        # symbol level: 6000 bits per frame, keep a running BER
        sym, bits = M.modulate(mod, 6000 - 6000 % k, rng)
        sig = math.sqrt(1.0 / (k * M.undb(v["ebn0"])) / 2)
        wi, wq = _noise(rng, len(sym), sig, p, v["kimp"]), _noise(rng, len(sym), sig, p, v["kimp"])
        rx = sym + wi + 1j * wq
        dec = M.demodulate(mod, rx)
        st["err"] += int(np.sum(dec != bits))
        st["bits"] += len(bits)
        ber = st["err"] / st["bits"]

        st["hist"] += np.histogram(wi / sig, bins=EDGES)[0]
        dens = st["hist"] / max(st["hist"].sum(), 1) / 0.1
        for b, d in zip(hist.bars, dens):
            b.set_height(max(d, 1e-9))
        hist.txt.set_text(f"σ = {sig:.3f}   kurtosis = {float(np.mean((wi / sig) ** 4)):.1f}  (Gaussian = 3)")

        wrong = np.any((dec != bits).reshape(-1, k), axis=1)
        cp = st["const"] = np.vstack([st["const"], np.c_[rx.real[:300], rx.imag[:300], wrong[:300]]])[-3000:]
        sc_ok.set_offsets(cp[cp[:, 2] == 0, :2])
        sc_bad.set_offsets(cp[cp[:, 2] == 1, :2] if (cp[:, 2] == 1).any() else np.zeros((0, 2)))

        # waveform level (pulse shaped), shows a 16 symbol window
        a, tx, rxw = _shaped_waveform(rng, sym, st["h"], sig, p, v["kimp"])
        s0 = 8 * SPS
        tt = np.arange(16 * SPS) / SPS
        wave.tx.set_data(tt, tx[s0:s0 + 16 * SPS])
        wave.rx.set_data(tt, rxw[s0:s0 + 16 * SPS])
        samp = rxw[s0:s0 + 16 * SPS:SPS]
        ok = _decisions(mod, samp, a[8:24])
        wave.dec.set_offsets(np.c_[np.arange(16), samp])
        wave.dec.set_color([C.COL["good"] if o else C.COL["bad"] for o in ok])
        wave.txt.set_text(f"{(~ok).sum()} wrong decisions in this window")

        st["traces"] = (st["traces"] + [rxw[i * SPS - SPS:i * SPS + SPS + 1] for i in range(10, 30)])[-60:]
        _draw_eye(eye_lines, eye_txt, st["traces"], mod)

        _draw_live_ber(berp.live, v["ebn0"], ber, st["bits"])
        theory = float(ber_impulsive(mod, v["ebn0"], p, v["kimp"]))
        berp.txt.set_text(f"{st['bits']:,} bits simulated\nmeasured {ber:.2e}\ntheory   {theory:.2e}")
        ro.set_text(_readout_text(v, ber, theory))
        ro.set_color(status_colour(1 - min(1, ber * 300)))

    return fig, step, ctl
