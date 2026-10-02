#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
 DISASTER-RESILIENT HYBRID COMMUNICATION NETWORK FOR A SMART CITY
 Single study area: COASTAL CITY HIT BY A CYCLONE
==============================================================================
 The three required layers (names exactly as in the assignment):
   1. Old-school analog emergency radio   (AM / FM)
   2. Digital mobile network              (PCM + BPSK / QPSK / 16-QAM, cells)
   3. Satellite backup                    (link budget + rain attenuation)

 The formulas in analog() / mobile() / satellite() are the SAME as in the
 interactive chat lab, so numbers match. Run:
       pip install numpy matplotlib
       python coastal_cyclone_hybrid_network.py
 Figures are shown and saved in ./figures/ (PNG).

 Model notes (state these in the article)
   * Parameters are illustrative design assumptions - replace them with
     values from your cited papers.
   * The analog radio is a one-way alert broadcast, so "hybrid two-way
     availability" uses the digital mobile network + satellite backup only.
   * Rain fade: simplified ITU-R P.618 effective-path model, ITU-R P.838
     coefficients (approximate, horizontal polarisation).
 References
   [1] Haykin, Communication Systems.   [2] Proakis & Salehi, Digital Comms.
   [3] Rappaport, Wireless Communications.  [4] ITU-R P.838-3, P.618.
==============================================================================
"""
import os
import sys
import math
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.widgets import Slider, Button

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT = "DISASTER-RESILIENT HYBRID COMMUNICATION NETWORK FOR A SMART CITY"
STUDY = "Study area: Coastal city + cyclone"
MEMBERS = [("Manasvi Choudhary", "2430112"), ("Kumari Sweta", "2430211"), ("Srishti Anand", "2430221")]
L_AN, L_MO, L_SA = "Old-school analog emergency radio", "Digital mobile network", "Satellite backup"
COL = dict(an="#E67E22", mo="#2980B9", sa="#8E44AD", hy="#1D9E75", bad="#C0392B", grey="#7F8C8D", dark="#2C3E50")
FIG_DIR, SHOW, W, SEED = "figures", True, 78, 2026

ORIG = dict(N=5.0, R=60.0, F=35.0, S=3.0, df=5, mi=1, ad=100, bi=1)
MOD = [("BPSK", 1), ("QPSK", 2), ("16-QAM", 4)]
BAND = [("C-band", 7.056e-4, 1.59, 12.0), ("Ku-band", 0.0386, 1.14, 14.0), ("Ka-band", 0.2403, 0.9485, 15.0)]
SATP = {"C": dict(fu=6, fd=4, se=38, ugt=12, ue=52, sgt=2), "Ku": dict(fu=14, fd=12, se=50, ugt=17, ue=55, sgt=8),
        "Ka": dict(fu=30, fd=20, se=56, ugt=20, ue=58, sgt=12)}
RATE, REQ, OTHER, ELEV = 512e3, 11.1, 2.0, 60.0


# ----------------------------------------------------------------------------
#  CORE MODEL  (identical to the chat lab)
# ----------------------------------------------------------------------------
def clamp(x, a, b):
    return min(b, max(a, x))


def erlang_b(E, C):
    B = 1.0
    for k in range(1, int(C) + 1):
        B = E * B / (k + E * B)
    return B


def analog(N, df):
    bw = 2 * (df + 3)
    c = 30 - N - 10 * math.log10(bw / 16)
    beta = df / 3
    g = 10 * math.log10(1.5 * beta ** 2)
    out = 10 + g - 3 * (10 - c) if c < 10 else c + g
    return dict(snr=out, cnr=c, bw=bw, beta=beta, p=0.97 * clamp((out - 8) / 17, 0, 1))


def ber_of(mi, g):
    k = MOD[mi][1]
    return 0.375 * math.erfc(math.sqrt(0.4 * g)) if k == 4 else 0.5 * math.erfc(math.sqrt(g))


def mobile(N, F, S, mi, ad):
    k = MOD[mi][1]
    sn = 17 - N - 0.1 * F
    ebn0 = sn - 10 * math.log10(k)
    ber = ber_of(mi, 10 ** (ebn0 / 10))
    link = clamp(1 - math.log10(max(ber, 1e-12) / 1e-3) / 2, 0, 1)
    s = 1 - F / 100
    cov = 1 - (1 - s) ** 3
    load = 70 * S * (ad / 100) / max(s, 0.05)
    bl = erlang_b(load, 68 * k)
    return dict(snr=sn, ebn0=ebn0, ber=ber, link=link, cov=cov, load=load, block=bl,
                p=cov * (1 - bl) * link * (0.3 + 0.7 * ad / 100))


def satellite(R, bi):
    _, k, a, m0 = BAND[bi]
    gam = k * max(R, 0.01) ** a
    Ls = 5 / math.sin(math.radians(ELEV))
    Lg = Ls * math.cos(math.radians(ELEV))
    L0 = 35 * math.exp(-0.015 * min(R, 100))
    A = gam * Ls / (1 + Lg / L0)
    m = m0 - A
    return dict(A=A, m=m, snr=REQ + m, gam=gam, p=0.98 / (1 + math.exp(-m / 1.5)))


def ideal(v):
    bd, bs = 2, -1
    for d in range(2, 31):
        s = analog(v["N"], d)["p"] * math.sqrt(16 / (2 * (d + 3)))
        if s > bs + 1e-9:
            bs, bd = s, d
    bm, ba, bb = 0, 100, -1
    for m in range(3):
        for a in range(5, 101, 5):
            p = mobile(v["N"], v["F"], v["S"], m, a)["p"]
            if p > bb + 1e-9:
                bb, bm, ba = p, m, a
    ps = [satellite(v["R"], i)["p"] for i in range(3)]
    bi = next(i for i, p in enumerate(ps) if p >= max(ps) - 0.005)
    return dict(df=bd, mi=bm, ad=ba, bi=bi)


def evaluate(v):
    A, M, S = analog(v["N"], v["df"]), mobile(v["N"], v["F"], v["S"], v["mi"], v["ad"]), satellite(v["R"], v["bi"])
    two = 1 - (1 - M["p"]) * (1 - S["p"])
    share = {L_MO: M["p"], L_SA: (1 - M["p"]) * S["p"], "Analog alert only": (1 - two) * A["p"],
             "No contact": (1 - two) * (1 - A["p"])}
    return dict(A=A, M=M, S=S, two=two, share=share)


def storm(i):
    return dict(N=3 + 17 * i, R=140 * i, F=85 * i, S=1 + 8 * i)


def intensity(t):
    return math.sin(math.pi * t) ** 1.2


# ----------------------------------------------------------------------------
#  CONSOLE UI
# ----------------------------------------------------------------------------
def hr(ch="═"):
    print(ch * W)


def banner():
    print()
    hr()
    print(PROJECT.center(W))
    print(STUDY.center(W))
    hr()
    print("  PROJECT TEAM")
    for n, r in MEMBERS:
        print(f"    {n} - {r}")
    hr("─")
    print("  Navigation: only the numbers displayed on screen are accepted.")
    hr()


def head(t):
    print()
    hr("━")
    print("  " + t)
    hr("━")


def ask(prompt, valid):
    valid = [str(x) for x in valid]
    while True:
        try:
            s = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Session ended. Thank you.")
            sys.exit(0)
        if s in valid:
            return s
        print(f"  ✖  '{s}' is not a valid option. Please press only one of: {', '.join(valid)}.")


def menu(title, items):
    print()
    hr("─")
    print("  " + title)
    hr("─")
    for k, lbl in items:
        print(f"    Press {k:>2}  →  {lbl}")
    return ask(f"\n  Please enter your choice ({', '.join(k for k, _ in items)}): ", [k for k, _ in items])


def pause():
    ask("\n  Press 1 to continue ▶ ", ["1"])


def style():
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")
    plt.rcParams.update({"axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8, "font.size": 9,
                         "axes.titleweight": "bold"})


def new_fig(r, c, title, size=(15.5, 8.8)):
    fig, ax = plt.subplots(r, c, figsize=size)
    fig.suptitle(f"{title}\nCoastal city + cyclone", fontsize=13, fontweight="bold")
    return fig, ax


def finish(fig, name):
    fig.tight_layout(rect=[0, 0.02, 1, 0.93])
    fig.text(0.995, 0.004, " · ".join(m[0] for m in MEMBERS), ha="right", fontsize=7, color="gray")
    os.makedirs(FIG_DIR, exist_ok=True)
    p = os.path.join(FIG_DIR, name + ".png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    print(f"   ✔ Figure saved → {p}")
    if SHOW:
        plt.show()
    plt.close(fig)


def wrap(text, width):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + [line]


def print_assumptions():
    head("STUDY AREA: COASTAL CITY + CYCLONE - ASSUMPTIONS")
    for k, val in [("Hazard", "Cyclone: storm surge, high winds, extreme rain, power failure"),
                   ("Original storm conditions", f"noise +{ORIG['N']:.0f} dB, rain {ORIG['R']:.0f} mm/h, "
                                                 f"{ORIG['F']:.0f} % towers destroyed, traffic surge ×{ORIG['S']:.0f}"),
                   ("Original design", f"FM deviation {ORIG['df']} kHz, {MOD[ORIG['mi']][0]}, admission "
                                       f"{ORIG['ad']} %, {BAND[ORIG['bi']][0]}"),
                   ("Cell capacity", "136 channels (QPSK), 2 % GoS; normal load 70 Erlang/cell"),
                   ("Satellite", f"GEO, elevation {ELEV:.0f}°, {RATE / 1e3:.0f} kbps, required Eb/N0 {REQ} dB")]:
        print(f"   {k:<28}: {val}")


def print_result(v, title="RESULT"):
    r = evaluate(v)
    print(f"\n   {title}")
    print(f"   {L_MO:<46}{r['M']['p']:>7.1%}   (BER {r['M']['ber']:.1e}, blocking {r['M']['block']:.0%})")
    print(f"   {L_SA:<46}{r['S']['p']:>7.1%}   (rain fade {r['S']['A']:.1f} dB, margin {r['S']['m']:+.1f} dB)")
    print(f"   {L_AN + ' (alert only)':<46}{r['A']['p']:>7.1%}   (output SNR {r['A']['snr']:.1f} dB)")
    print(f"   {'HYBRID two-way availability':<46}{r['two']:>7.1%}")
    return r


# ----------------------------------------------------------------------------
#  1. BLOCK DIAGRAM
# ----------------------------------------------------------------------------
def _box(ax, x, y, w, h, text, color, fs=7.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8", fc=color,
                                ec=COL["dark"], lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="white", fontweight="bold")


def _arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11, color=COL["dark"], lw=1.3))


def run_block():
    head("BLOCK DIAGRAM - TRANSMITTER TO RECEIVER, ALL THREE LAYERS")
    v = ORIG
    S = satellite(v["R"], v["bi"])
    rows = [("an", 44, L_AN, ["Audio filter\n(3 kHz)", "AM / FM\nmodulator", "RF power amp\n+ VHF antenna",
                              f"CHANNEL\nstorm noise\n+{v['N']:.0f} dB", "FM / AM\ndemodulator"]),
            ("mo", 28, L_MO, ["ADC + PCM\n(8 bit, 8 kHz)", "Channel\ncoding", f"{MOD[v['mi']][0]}\nmodulator",
                              "Cell tower\n(Erlang-B)", f"CHANNEL\nAWGN + fading", "Demodulator\n+ PCM decoder"]),
            ("sa", 12, L_SA, ["VSAT\nterminal", "Uplink", "Satellite\ntransponder",
                              f"Downlink\n{BAND[v['bi']][0]}, rain fade\n{S['A']:.1f} dB", "Earth\nstation"])]
    fig, ax = plt.subplots(figsize=(15.5, 8.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.axis("off")
    fig.suptitle("Hybrid Network Block Diagram - coastal city + cyclone", fontsize=13, fontweight="bold")
    _box(ax, 1, 12, 10, 42, "EMERGENCY\nSOURCES\n\nVoice\nAlerts\nSensors", COL["dark"], 8)
    _box(ax, 13, 6, 5.5, 54, "H\nY\nB\nR\nI\nD\n\nC\nO\nN\nT\nR\nO\nL\nL\nE\nR", COL["bad"], 8)
    _box(ax, 88, 12, 11, 42, "EMERGENCY\nOPERATIONS\nCENTRE\n\nPriority routing\n& failover", COL["dark"], 8)
    for key, y, name, labels in rows:
        n, gap = len(labels), 2.2
        w = (85.5 - 21 - gap * (n - 1)) / n
        _arrow(ax, 18.5, 33, 20.2, y + 5)
        for i, lab in enumerate(labels):
            x = 21 + i * (w + gap)
            _box(ax, x, y, w, 10, lab, COL["grey"] if "CHANNEL" in lab else COL[key], 6.8)
            if i < n - 1:
                _arrow(ax, x + w + 0.1, y + 5, x + w + gap - 0.1, y + 5)
        _arrow(ax, 85.8, y + 5, 87.6, 33)
        ax.text(21, y + 11.2, name, fontsize=9, fontweight="bold", color=COL[key])
    ax.text(50, 59, "Failover order:  Digital mobile network  →  Satellite backup  →  Old-school analog emergency radio (alert)",
            ha="center", fontsize=10, color=COL["bad"], fontweight="bold")
    ax.text(50, 2, "Grey boxes = noisy channels analysed in the noise, BER and rain-fade modules.", ha="center",
            fontsize=8.5, color=COL["grey"])
    finish(fig, "01_block_diagram")


# ----------------------------------------------------------------------------
#  2. OLD-SCHOOL ANALOG EMERGENCY RADIO
# ----------------------------------------------------------------------------
def spec(x, fs):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    X /= X.max()
    return np.fft.rfftfreq(len(x), 1 / fs), 20 * np.log10(X + 1e-6)


def run_analog(v=None):
    v = v or ORIG
    head(f"{L_AN.upper()}  (AM / FM)")
    fmax, mu = 3.0, 0.8
    I = ideal(v)
    A = analog(v["N"], v["df"])
    print(f"   AM : modulation index μ = {mu};  bandwidth = 2·fm = {2 * fmax:.0f} kHz;  "
          f"efficiency η = μ²/(2+μ²) = {mu ** 2 / (2 + mu ** 2):.1%}")
    print(f"   FM : deviation Δf = {v['df']} kHz;  β = Δf/fm = {A['beta']:.2f};  Carson BW = 2(Δf+fm) = {A['bw']:.0f} kHz")
    print(f"   CNR at the receiver with storm noise +{v['N']:.0f} dB = {A['cnr']:.1f} dB;  output SNR = {A['snr']:.1f} dB "
          f"(FM threshold at 10 dB)")
    print(f"   Ideal FM deviation for this storm = {I['df']} kHz  (smallest bandwidth that still gives full reach)")
    fs, fc = 600e3, 60e3
    t = np.arange(0, 0.02, 1 / fs)
    am = (1 + mu * np.cos(2 * np.pi * 3e3 * t)) * np.cos(2 * np.pi * fc * t)
    fm = np.cos(2 * np.pi * fc * t + A["beta"] * np.sin(2 * np.pi * 3e3 * t))
    fig, ax = new_fig(2, 3, f"{L_AN} - AM / FM")
    m = t < 1e-3
    ax[0, 0].plot(t[m] * 1e3, am[m], color=COL["an"], lw=0.7)
    env = 1 + mu * np.cos(2 * np.pi * 3e3 * t[m])
    ax[0, 0].plot(t[m] * 1e3, env, "k--", lw=1)
    ax[0, 0].plot(t[m] * 1e3, -env, "k--", lw=1)
    ax[0, 0].set(title=f"AM waveform and envelope (μ = {mu})", xlabel="time (ms)", ylabel="amplitude")
    f, s = spec(am, fs)
    ax[0, 1].plot((f - fc) / 1e3, s, color=COL["an"])
    ax[0, 1].set(xlim=(-15, 15), ylim=(-70, 5), title=f"AM spectrum - BW = {2 * fmax:.0f} kHz", xlabel="offset from carrier (kHz)",
                 ylabel="dB")
    f, s = spec(fm, fs)
    ax[0, 2].plot((f - fc) / 1e3, s, color=COL["bad"])
    ax[0, 2].axvline(A["bw"] / 2, color="k", ls="--")
    ax[0, 2].axvline(-A["bw"] / 2, color="k", ls="--")
    ax[0, 2].set(xlim=(-40, 40), ylim=(-70, 5), title=f"FM spectrum, Δf={v['df']} kHz - Carson BW {A['bw']:.0f} kHz",
                 xlabel="offset from carrier (kHz)", ylabel="dB")
    dfs = np.arange(2, 31)
    outs = [analog(v["N"], d)["snr"] for d in dfs]
    sc = [analog(v["N"], d)["p"] * math.sqrt(16 / (2 * (d + 3))) for d in dfs]
    ax[1, 0].plot(dfs, outs, color=COL["an"], lw=2)
    ax[1, 0].axhline(25, color="grey", ls=":")
    ax[1, 0].plot([v["df"]], [A["snr"]], "o", color=COL["mo"], ms=9, label="current")
    ax[1, 0].plot([I["df"]], [analog(v["N"], I["df"])["snr"]], "o", color=COL["hy"], ms=11, label="ideal")
    ax[1, 0].set(title="Output SNR vs FM deviation", xlabel="Δf (kHz)", ylabel="output SNR (dB)")
    ax[1, 0].legend()
    ax[1, 1].plot(dfs, sc, color=COL["an"], lw=2)
    ax[1, 1].plot([I["df"]], [analog(v["N"], I["df"])["p"] * math.sqrt(16 / (2 * (I["df"] + 3)))], "o", color=COL["hy"], ms=11)
    ax[1, 1].set(title="Design score = reach × spectrum efficiency (peak = ideal)", xlabel="Δf (kHz)", ylabel="score")
    Ns = np.arange(0, 26)
    mu_ = 0.8
    am_out = [30 - n - 10 * math.log10(6 / 16) + 10 * math.log10(mu_ ** 2 / (2 + mu_ ** 2)) for n in Ns]
    ax[1, 2].plot(Ns, am_out, color=COL["an"], lw=2, label="AM (μ=0.8)")
    ax[1, 2].plot(Ns, [analog(n, v["df"])["snr"] for n in Ns], color=COL["bad"], lw=2, label=f"FM (Δf={v['df']} kHz)")
    ax[1, 2].axvline(v["N"], color="k", ls="--")
    ax[1, 2].set(title="Output SNR vs storm noise (AM vs FM)", xlabel="storm noise rise (dB)", ylabel="output SNR (dB)")
    ax[1, 2].legend()
    finish(fig, "02_analog_emergency_radio")


# ----------------------------------------------------------------------------
#  3. DIGITAL MOBILE NETWORK
# ----------------------------------------------------------------------------
def mc_ber(mi, e_db, nb, rng):
    g = 10 ** (e_db / 10)
    if mi < 2:
        b = rng.integers(0, 2, nb)
        r = (2 * b - 1) + rng.standard_normal(nb) / math.sqrt(2 * g)
        return float(np.mean((r > 0) != (b == 1)))
    b1, b0 = rng.integers(0, 2, nb), rng.integers(0, 2, nb)
    lev = np.where(b1 == 1, 1, -1) * np.where(b0 == 1, 1, 3)
    r = lev + rng.standard_normal(nb) * math.sqrt(1.25 / g)
    return float((np.mean((r > 0) != (b1 == 1)) + np.mean((np.abs(r) < 2) != (b0 == 1))) / 2)


def run_digital(v=None):
    v = v or ORIG
    rng = np.random.default_rng(SEED)
    head(f"{L_MO.upper()}  (PCM + modulation + cellular capacity)")
    nb, fs_s = 8, 8000
    delta = 2 / 2 ** nb
    M = mobile(v["N"], v["F"], v["S"], v["mi"], v["ad"])
    I = ideal(v)
    print(f"   PCM: fs = 2·4 kHz = {fs_s} Hz;  {nb}-bit → L = {2 ** nb} levels;  Δ = {delta:.5f} V;  max error Δ/2 = {delta / 2:.5f} V")
    print(f"        SQNR = 6.02n+1.76 = {6.02 * nb + 1.76:.1f} dB;  Rb = n·fs = {nb * fs_s / 1e3:.0f} kbps;  "
          f"BW(BPSK, α=0.35) = {nb * fs_s * 1.35 / 1e3:.1f} kHz")
    print(f"   Weak-site SNR = 17 − noise − 0.1·(%towers destroyed) = {M['snr']:.1f} dB;  {MOD[v['mi']][0]}  Eb/N0 = {M['ebn0']:.1f} dB;  "
          f"BER = {M['ber']:.2e}")
    print(f"   Cell load = {M['load']:.0f} Erlang vs {68 * MOD[v['mi']][1]} channels → blocking {M['block']:.0%};  "
          f"overall reach = {M['p']:.1%}")
    print(f"   Ideal setting for this storm: {MOD[I['mi']][0]}, admission {I['ad']} %")
    fig, ax = new_fig(2, 3, f"{L_MO} - PCM, BER and capacity")
    d3 = 2 / 2 ** 3
    qf = lambda x, d: np.clip(d * (np.floor(x / d) + 0.5), -1 + d / 2, 1 - d / 2)
    t = np.linspace(0, 2e-3, 2000)
    x = np.sin(2 * np.pi * 1000 * t)
    ts = np.arange(0, 2e-3, 1 / fs_s)
    ax[0, 0].plot(t * 1e3, x, color=COL["grey"], label="analog message")
    ax[0, 0].step(t * 1e3, qf(x, d3), where="mid", color=COL["mo"], label="quantised (3-bit)")
    ax[0, 0].stem(ts * 1e3, np.sin(2 * np.pi * 1000 * ts), linefmt="r-", markerfmt="ro", basefmt=" ")
    ax[0, 0].set(title="PCM: sampling + quantisation", xlabel="time (ms)", ylabel="V")
    ax[0, 0].legend(loc="lower left")
    ns = np.arange(1, 13)
    sim = [10 * np.log10(0.5 / np.mean((qf(xx, 2 / 2 ** n) - xx) ** 2))
           for n in ns for xx in [np.sin(2 * np.pi * rng.random(30000))]]
    ax[0, 1].plot(ns, 6.02 * ns + 1.76, "k--", label="theory 6.02n+1.76")
    ax[0, 1].plot(ns, sim, "o-", color=COL["mo"], label="simulated")
    ax[0, 1].set(title="SQNR vs bits", xlabel="bits n", ylabel="SQNR (dB)")
    ax[0, 1].legend()
    eg = np.arange(0, 16.1, 0.5)
    for mi, c in enumerate([COL["hy"], COL["mo"], COL["sa"]]):
        ax[0, 2].semilogy(eg, [max(ber_of(mi, 10 ** (e / 10)), 1e-9) for e in eg], color=c, lw=2, label=MOD[mi][0])
        pts = np.arange(0, 10, 1.5)
        ax[0, 2].semilogy(pts, [max(mc_ber(mi, p, 300000, rng), 1e-7) for p in pts], "o", color=c, ms=4)
    ax[0, 2].axvline(M["ebn0"], color="k", ls=":")
    ax[0, 2].set(ylim=(1e-7, 1), title="BER vs Eb/N0 (lines = theory, dots = Monte-Carlo)", xlabel="Eb/N0 (dB)",
                 ylabel="BER")
    ax[0, 2].legend()
    Es = np.linspace(0, 400, 300)
    for c_, col in [(68, COL["grey"]), (136, COL["mo"]), (272, COL["hy"])]:
        ax[1, 0].plot(Es, [erlang_b(e, c_) * 100 for e in Es], color=col, lw=2, label=f"{c_} channels")
    ax[1, 0].axvline(M["load"], color="k", ls="--")
    ax[1, 0].axhline(2, color="r", ls=":")
    ax[1, 0].set(ylim=(0, 100), title="Erlang-B blocking vs load per surviving cell", xlabel="Erlang", ylabel="blocking (%)")
    ax[1, 0].legend()
    ads = np.arange(5, 101, 5)
    for mi, c in enumerate([COL["hy"], COL["mo"], COL["sa"]]):
        ax[1, 1].plot(ads, [mobile(v["N"], v["F"], v["S"], mi, a)["p"] * 100 for a in ads], color=c, lw=2, label=MOD[mi][0])
    ax[1, 1].plot([v["ad"]], [M["p"] * 100], "o", color="k", ms=9, label="current")
    ax[1, 1].plot([I["ad"]], [mobile(v["N"], v["F"], v["S"], I["mi"], I["ad"])["p"] * 100], "*", color=COL["hy"], ms=18,
                  label="ideal")
    ax[1, 1].set(title="Reach vs priority-call admission", xlabel="admission (%)", ylabel="citizens reached (%)")
    ax[1, 1].legend(fontsize=7)
    k = MOD[v["mi"]][1]
    N_ = 1500
    if k == 1:
        sym = rng.choice([-1, 1], N_) + 0j
    elif k == 2:
        sym = (rng.choice([-1, 1], N_) + 1j * rng.choice([-1, 1], N_)) / math.sqrt(2)
    else:
        sym = (rng.choice([-3, -1, 1, 3], N_) + 1j * rng.choice([-3, -1, 1, 3], N_)) / math.sqrt(10)
    esn0 = 10 ** (clamp(M["snr"], -5, 30) / 10)
    r = sym + (rng.standard_normal(N_) + 1j * rng.standard_normal(N_)) * math.sqrt(1 / (2 * esn0))
    ax[1, 2].scatter(r.real, r.imag, s=5, alpha=0.5, color=COL["mo"])
    ax[1, 2].axhline(0, color="k", lw=0.5)
    ax[1, 2].axvline(0, color="k", lw=0.5)
    ax[1, 2].set(title=f"{MOD[v['mi']][0]} constellation at weak site (SNR {M['snr']:.1f} dB)", xlabel="I", ylabel="Q",
                 aspect="equal")
    finish(fig, "03_digital_mobile_network")


# ----------------------------------------------------------------------------
#  4. SATELLITE BACKUP
# ----------------------------------------------------------------------------
def slant_km(h, el):
    e = math.radians(el)
    return math.sqrt((6371 + h) ** 2 - (6371 * math.cos(e)) ** 2) - 6371 * math.sin(e)


def clear_budget(key):
    b, d = SATP[key], slant_km(35786, ELEV)
    rate = 10 * math.log10(RATE)
    out = {}
    for leg, f, eirp, gt in (("up", b["fu"], b["ue"], b["sgt"]), ("down", b["fd"], b["se"], b["ugt"])):
        fs_ = 20 * math.log10(d) + 20 * math.log10(f * 1000) + 32.44
        cn0 = eirp + gt - fs_ - OTHER + 228.6
        out[leg] = dict(f=f, fspl=fs_, cn0=cn0, eb=cn0 - rate, margin=cn0 - rate - REQ)
    return out


def run_sat(v=None):
    v = v or ORIG
    head(f"{L_SA.upper()}  (link budget + rain attenuation)")
    d = slant_km(35786, ELEV)
    print(f"   GEO satellite, elevation {ELEV:.0f}°, slant range {d:,.0f} km, rate {RATE / 1e3:.0f} kbps, required Eb/N0 {REQ} dB")
    print(f"   {'Band':<7}{'Up FSPL':>9}{'Up margin':>11}{'Down FSPL':>11}{'Down margin':>13}{'Clear-sky':>11}")
    for key in ("C", "Ku", "Ka"):
        b = clear_budget(key)
        m = min(b["up"]["margin"], b["down"]["margin"])
        print(f"   {key:<7}{b['up']['fspl']:>8.1f} {b['up']['margin']:>10.1f} {b['down']['fspl']:>10.1f} "
              f"{b['down']['margin']:>12.1f} {m:>10.1f}")
    print("   (the model uses these clear-sky margins rounded down: 12 / 14 / 15 dB)")
    S = satellite(v["R"], v["bi"])
    I = ideal(v)
    print(f"   Rain {v['R']:.0f} mm/h on {BAND[v['bi']][0]}: fade {S['A']:.1f} dB → margin {S['m']:+.1f} dB "
          f"({'LINK HOLDS' if S['m'] >= 0 else 'RAIN OUTAGE'});   ideal band = {BAND[I['bi']][0]}")
    fig, ax = new_fig(2, 3, f"{L_SA} - FSPL, link budget and rain fade")
    f = np.logspace(0, 1.5, 200)
    for nm, h, c in [("GEO 35,786 km", 35786, COL["sa"]), ("LEO 550 km", 550, COL["hy"])]:
        ax[0, 0].semilogx(f, 20 * np.log10(slant_km(h, ELEV)) + 20 * np.log10(f * 1000) + 32.44, color=c, lw=2, label=nm)
    ax[0, 0].set(title="Free-space path loss vs frequency", xlabel="GHz", ylabel="FSPL (dB)")
    ax[0, 0].legend()
    R = np.linspace(1, 150, 150)
    cols = [COL["hy"], COL["mo"], COL["bad"]]
    for i, (n, k, a, m0) in enumerate(BAND):
        ax[0, 1].loglog(R, k * R ** a, color=cols[i], lw=2, label=n)
        ax[0, 2].plot(R, [satellite(r, i)["A"] for r in R], color=cols[i], lw=2, label=n)
        ax[1, 0].plot(R, [satellite(r, i)["m"] for r in R], color=cols[i], lw=2, label=n)
        ax[1, 2].plot(R, [satellite(r, i)["p"] * 100 for r in R], color=cols[i], lw=2, label=n)
    ax[0, 1].set(title="Specific rain attenuation γ = k·R^α", xlabel="rain rate (mm/h)", ylabel="dB/km")
    ax[0, 2].set(title="Total rain fade on the slant path", xlabel="rain rate (mm/h)", ylabel="dB")
    ax[1, 0].axhline(0, color="k")
    ax[1, 0].set(ylim=(-40, 20), title="Link margin vs rain (below 0 = outage)", xlabel="rain rate (mm/h)", ylabel="dB")
    ax[1, 2].set(title="Citizens reachable via satellite vs rain", xlabel="rain rate (mm/h)", ylabel="%")
    for a in (ax[0, 2], ax[1, 0], ax[1, 2]):
        a.axvline(v["R"], color="k", ls="--")
        a.legend()
    ax[0, 1].legend()
    b = clear_budget(["C", "Ku", "Ka"][v["bi"]])["down"]
    items = [("Satellite EIRP", SATP[["C", "Ku", "Ka"][v["bi"]]]["se"]), ("Terminal G/T", SATP[["C", "Ku", "Ka"][v["bi"]]]["ugt"]),
             ("FSPL", -b["fspl"]), ("Rain fade", -S["A"]), ("Other", -OTHER), ("Boltzmann +228.6", 228.6),
             ("Rate", -10 * math.log10(RATE)), ("= Eb/N0 (rain)", S["snr"]), ("Required", REQ)]
    ax[1, 1].barh([i[0] for i in items][::-1], [i[1] for i in items][::-1],
                  color=[COL["hy"] if x >= 0 else COL["bad"] for _, x in items][::-1])
    ax[1, 1].set(title=f"Downlink budget, {BAND[v['bi']][0]}, rain {v['R']:.0f} mm/h", xlabel="dB")
    finish(fig, "04_satellite_backup")


# ----------------------------------------------------------------------------
#  5. NOISE AND SIGNAL QUALITY
# ----------------------------------------------------------------------------
def verdict(s):
    return ("Clean" if s >= 30 else "Good" if s >= 20 else "Noisy" if s >= 12 else "Very noisy" if s >= 6 else "Lost in noise")


def run_noise(v=None):
    v = v or ORIG
    rng = np.random.default_rng(SEED + 1)
    head("NOISE AND SIGNAL QUALITY CHECK (Gaussian noise, SNR, BER)")
    r = evaluate(v)
    snrs = [(L_AN, r["A"]["snr"], COL["an"]), (L_MO, r["M"]["snr"], COL["mo"]), (L_SA, r["S"]["snr"], COL["sa"])]
    for n, s, _ in snrs:
        print(f"   {n:<36} SNR {s:>6.1f} dB   → {verdict(s)}")
    print(f"   BER (digital mobile network, {MOD[v['mi']][0]}) = {r['M']['ber']:.2e}   |   Monte-Carlo check: "
          f"{mc_ber(v['mi'], r['M']['ebn0'], 400000, rng):.2e}")
    fig, ax = new_fig(2, 3, "Noise and signal quality - what survives the storm?")
    t = np.linspace(0, 3, 500)
    z = rng.standard_normal(500)
    for a, (n, s, c) in zip(ax[0], snrs):
        sg = math.sqrt(0.5 / 10 ** (clamp(s, -5, 40) / 10))
        a.plot(t, np.sin(2 * np.pi * t) + sg * z, color=COL["grey"], lw=0.7)
        a.plot(t, np.sin(2 * np.pi * t), color=c, lw=3)
        a.set(title=f"{n}\n{s:.0f} dB SNR - {verdict(s)}", yticks=[], xticks=[])
    Ns = np.arange(0, 26)
    ax[1, 0].plot(Ns, [analog(n, v["df"])["snr"] for n in Ns], color=COL["an"], lw=2, label=L_AN)
    ax[1, 0].plot(Ns, [mobile(n, v["F"], v["S"], v["mi"], v["ad"])["snr"] for n in Ns], color=COL["mo"], lw=2, label=L_MO)
    ax[1, 0].plot(Ns, [satellite(v["R"], v["bi"])["snr"] for _ in Ns], color=COL["sa"], lw=2, label=L_SA)
    ax[1, 0].axvline(v["N"], color="k", ls="--")
    ax[1, 0].set(title="SNR of each layer vs storm noise", xlabel="storm noise rise (dB)", ylabel="SNR (dB)")
    ax[1, 0].legend(fontsize=7)
    for mi, c in enumerate([COL["hy"], COL["mo"], COL["sa"]]):
        ax[1, 1].semilogy(Ns, [max(mobile(n, v["F"], v["S"], mi, 100)["ber"], 1e-9) for n in Ns], color=c, lw=2, label=MOD[mi][0])
    ax[1, 1].axvline(v["N"], color="k", ls="--")
    ax[1, 1].set(ylim=(1e-9, 1), title="BER vs storm noise (mobile modulation choice)", xlabel="storm noise rise (dB)", ylabel="BER")
    ax[1, 1].legend()
    sn = np.linspace(-10, 30, 200)
    ax[1, 2].plot(sn, np.log2(1 + 10 ** (sn / 10)), "k--", label="Shannon limit")
    for nm, th, se, c in [("BPSK", 6.8, 1, COL["hy"]), ("QPSK", 9.8, 2, COL["mo"]), ("16-QAM", 16, 4, COL["sa"])]:
        ax[1, 2].plot([th, 30], [se, se], color=c, lw=2, label=nm)
    ax[1, 2].set(title="Spectral efficiency vs SNR (BER ≈ 1e-3)", xlabel="SNR (dB)", ylabel="bits/s/Hz")
    ax[1, 2].legend()
    finish(fig, "05_noise_and_signal_quality")


# ----------------------------------------------------------------------------
#  6. STORM STRESS TEST
# ----------------------------------------------------------------------------
def run_stress():
    head("STORM STRESS TEST - SWEEP EACH DANGER, ORIGINAL DESIGN vs IDEAL DESIGN")
    fig, ax = new_fig(2, 2, "Storm stress test: how far can each condition go?")
    sw = [("N", "Storm noise rise (dB)", np.linspace(0, 25, 26)), ("R", "Rain rate (mm/h)", np.linspace(0, 150, 31)),
          ("F", "Towers destroyed (%)", np.linspace(0, 95, 20)), ("S", "Call traffic surge (×)", np.linspace(1, 10, 19))]
    for a, (key, lab, xs) in zip(ax.ravel(), sw):
        pa, pm, ps, hy, hi = [], [], [], [], []
        for x in xs:
            v = dict(ORIG)
            v[key] = x
            e = evaluate(v)
            pa.append(e["A"]["p"] * 100)
            pm.append(e["M"]["p"] * 100)
            ps.append(e["S"]["p"] * 100)
            hy.append(e["two"] * 100)
            v2 = dict(v)
            v2.update(ideal(v))
            hi.append(evaluate(v2)["two"] * 100)
        a.plot(xs, pm, color=COL["mo"], lw=1.6, label=L_MO)
        a.plot(xs, ps, color=COL["sa"], lw=1.6, label=L_SA)
        a.plot(xs, pa, color=COL["an"], lw=1.6, label=L_AN + " (alert)")
        a.plot(xs, hy, color=COL["bad"], lw=2.5, ls="--", label="Hybrid, original design")
        a.plot(xs, hi, color=COL["hy"], lw=3, label="Hybrid, ideal design")
        a.axvline(ORIG[key], color="k", ls=":")
        a.set(xlabel=lab, ylabel="citizens reached (%)", ylim=(0, 105), title=f"Sweep: {lab}")
    ax[0, 0].legend(fontsize=7)
    finish(fig, "06_storm_stress_test")


# ----------------------------------------------------------------------------
#  7. HYBRID RESULT + CITIZEN MAP + CYCLONE TIMELINE
# ----------------------------------------------------------------------------
def citizen_classes(r, rng):
    u = rng.random((200, 3))
    return np.where(u[:, 0] < r["M"]["p"], 0, np.where(u[:, 1] < r["S"]["p"], 1, np.where(u[:, 2] < r["A"]["p"], 2, 3)))


def run_hybrid():
    head("HYBRID NETWORK RESULT AND FINAL RECOMMENDATION")
    I = ideal(ORIG)
    v2 = dict(ORIG)
    v2.update(I)
    r1 = print_result(ORIG, "ORIGINAL DESIGN")
    r2 = print_result(v2, f"IDEAL DESIGN  (Δf {I['df']} kHz, {MOD[I['mi']][0]}, admission {I['ad']} %, {BAND[I['bi']][0]})")
    best = max([(L_MO, r1["M"]["p"]), (L_SA, r1["S"]["p"])], key=lambda x: x[1])
    print("\n   CRITICAL REVIEW")
    for ln in [f"1. The best single two-way layer under the original design is the {best[0]} at {best[1]:.1%}; the hybrid reaches "
               f"{r1['two']:.1%} and the ideal design raises it to {r2['two']:.1%}.",
               f"2. Heavy rain ({ORIG['R']:.0f} mm/h) makes {BAND[ORIG['bi']][0]} satellite unreliable; "
               f"{BAND[I['bi']][0]} keeps the {L_SA.lower()} usable.",
               f"3. Tower loss ({ORIG['F']:.0f} %) plus a ×{ORIG['S']:.0f} traffic surge blocks calls on the {L_MO.lower()}; "
               f"priority admission ({I['ad']} %) restores service for emergency users.",
               f"4. The {L_AN.lower()} stays reliable (one-way alert) because FM trades bandwidth for noise immunity, "
               f"so it covers the citizens the other two layers miss.",
               "5. No single network is enough: each layer fails under a different danger (tower loss, rain, noise), "
               "which is why the hybrid is more resilient on this coastal terrain."]:
        for i, w_ in enumerate(wrap(ln, 70)):
            print(("   " if i == 0 else "      ") + w_)
    rng = np.random.default_rng(7)
    fig, ax = new_fig(2, 3, "Hybrid network - original design vs ideal design")
    names = [L_MO, L_SA, "Old-school analog\nemergency radio (alert)", "Hybrid two-way"]
    x = np.arange(4)
    for off, (r, lab, c) in zip((-0.2, 0.2), [(r1, "Original design", COL["grey"]), (r2, "Ideal design", COL["hy"])]):
        ax[0, 0].bar(x + off, [r["M"]["p"] * 100, r["S"]["p"] * 100, r["A"]["p"] * 100, r["two"] * 100], 0.38, color=c, label=lab)
    ax[0, 0].set_xticks(x)
    ax[0, 0].set_xticklabels(names, fontsize=7)
    ax[0, 0].set(ylim=(0, 112), ylabel="citizens reached (%)", title="Availability by layer")
    ax[0, 0].legend()
    for a, r, tt in [(ax[0, 1], r1, "Who serves citizens: original"), (ax[0, 2], r2, "Who serves citizens: ideal")]:
        a.pie(r["share"].values(), labels=None, autopct=lambda p: f"{p:.0f}%" if p > 4 else "", startangle=90,
              colors=[COL["mo"], COL["sa"], COL["an"], "#34495E"], textprops={"color": "white", "fontsize": 8})
        a.legend([f"{k} ({val:.0%})" for k, val in r["share"].items()], loc="upper center", bbox_to_anchor=(0.5, 0.0),
                 fontsize=7, ncol=2, frameon=False)
        a.set_title(tt)
    for a, r, tt in [(ax[1, 0], r1, "Citizen map: original"), (ax[1, 1], r2, "Citizen map: ideal")]:
        cl = citizen_classes(r, np.random.default_rng(7))
        xs, ys = np.meshgrid(np.arange(20), np.arange(10))
        a.scatter(xs.ravel(), -ys.ravel(), c=[[COL["mo"], COL["sa"], COL["an"], "#BDC3C7"][i] for i in cl], s=90)
        a.set(title=f"{tt} ({int(np.sum(cl < 2))}/200 with two-way link)", xticks=[], yticks=[])
        a.grid(False)
    ts = np.linspace(0, 1, 41)
    h1, h2, ia = [], [], []
    for t in ts:
        s = storm(intensity(t))
        va = dict(ORIG)
        va.update(s)
        vb = dict(va)
        vb.update(ideal(va))
        h1.append(evaluate(va)["two"] * 100)
        h2.append(evaluate(vb)["two"] * 100)
        ia.append(intensity(t) * 100)
    ax[1, 2].plot(ts * 72, ia, color=COL["grey"], ls=":", label="cyclone intensity (%)")
    ax[1, 2].plot(ts * 72, h1, color=COL["bad"], lw=2, label="hybrid, original design")
    ax[1, 2].plot(ts * 72, h2, color=COL["hy"], lw=3, label="hybrid, ideal design")
    ax[1, 2].set(title="Cyclone timeline (72 h)", xlabel="hours", ylabel="%", ylim=(0, 105))
    ax[1, 2].legend(fontsize=7)
    finish(fig, "07_hybrid_result")


# ----------------------------------------------------------------------------
#  8. INTERACTIVE SLIDER LAB (ideal dots)
# ----------------------------------------------------------------------------
SPECS = [("N", "Storm noise (dB)", 0, 25, 1), ("R", "Rain (mm/h)", 0, 150, 5), ("F", "Towers destroyed (%)", 0, 95, 5),
         ("S", "Traffic surge (×)", 1, 10, 0.5), ("df", "FM deviation (kHz)", 2, 30, 1),
         ("mi", "Mobile modulation", 0, 2, 1), ("ad", "Priority admission (%)", 5, 100, 5), ("bi", "Satellite band", 0, 2, 1)]


def run_lab():
    head("INTERACTIVE LAB - drag the sliders, follow the green ideal dots")
    print("   Conditions (top four) are the storm; design choices (bottom four) show a green ideal dot.")
    fig = plt.figure(figsize=(15, 8.5))
    fig.suptitle("Interactive lab - coastal city + cyclone", fontsize=13, fontweight="bold")
    sl, dots, lock = {}, {}, [False]
    axb = fig.add_axes([0.58, 0.55, 0.39, 0.33])
    axm = fig.add_axes([0.58, 0.08, 0.39, 0.38])
    for i, (k, lab, lo, hi, st) in enumerate(SPECS):
        a = fig.add_axes([0.17, 0.88 - i * 0.085 - (0.03 if i > 3 else 0), 0.24, 0.03])
        s = Slider(a, lab, lo, hi, valinit=ORIG[k], valstep=st, color=COL["mo"])
        sl[k] = s
        if i > 3:
            dots[k], = a.plot([lo], [0.5], "o", color=COL["hy"], ms=10, mec="white", zorder=5)

    def refresh(_=None):
        if lock[0]:
            return
        v = {k: s.val for k, s in sl.items()}
        for k in ("df", "mi", "ad", "bi"):
            v[k] = int(v[k])
        r, I = evaluate(v), ideal(v)
        for k in dots:
            dots[k].set_data([I[k]], [0.5])
        sl["mi"].valtext.set_text(f"{MOD[v['mi']][0]} (ideal {MOD[I['mi']][0]})")
        sl["bi"].valtext.set_text(f"{BAND[v['bi']][0]} (ideal {BAND[I['bi']][0]})")
        sl["df"].valtext.set_text(f"{v['df']} (ideal {I['df']})")
        sl["ad"].valtext.set_text(f"{v['ad']} (ideal {I['ad']})")
        axb.clear()
        vals = [r["M"]["p"] * 100, r["S"]["p"] * 100, r["A"]["p"] * 100, r["two"] * 100]
        axb.bar(["Digital\nmobile network", "Satellite\nbackup", "Old-school analog\nemergency radio", "HYBRID\ntwo-way"], vals,
                color=[COL["mo"], COL["sa"], COL["an"], COL["hy"]])
        for i, x in enumerate(vals):
            axb.text(i, x + 2, f"{x:.0f}%", ha="center")
        axb.set(ylim=(0, 115), ylabel="citizens reached (%)", title=f"Fade {r['S']['A']:.1f} dB | BER {r['M']['ber']:.1e} | "
                                                                   f"blocking {r['M']['block']:.0%}")
        axm.clear()
        cl = citizen_classes(r, np.random.default_rng(7))
        xs, ys = np.meshgrid(np.arange(20), np.arange(10))
        axm.scatter(xs.ravel(), -ys.ravel(), c=[[COL["mo"], COL["sa"], COL["an"], "#BDC3C7"][i] for i in cl], s=110)
        axm.set(xticks=[], yticks=[], title="Citizen map: blue mobile, purple satellite, orange alert only, grey no contact")
        axm.grid(False)
        fig.canvas.draw_idle()

    def setv(d):
        lock[0] = True
        for k, x in d.items():
            sl[k].set_val(x)
        lock[0] = False
        refresh()

    def b_reset(_):
        setv(ORIG)

    def b_ideal(_):
        setv(ideal({k: s.val for k, s in sl.items()}))

    def b_worst(_):
        setv(dict(N=20, R=120, F=80, S=8))
    btns = []
    for i, (lab, fn) in enumerate([("Reset to original", b_reset), ("Jump to ideal", b_ideal), ("Worst-case storm", b_worst)]):
        a = fig.add_axes([0.06 + i * 0.12, 0.10, 0.11, 0.05])
        b = Button(a, lab)
        b.on_clicked(fn)
        btns.append(b)
    for s in sl.values():
        s.on_changed(refresh)
    refresh()
    fig._keep = (sl, btns, dots, setv)
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, "08_interactive_lab_snapshot.png"), dpi=150)
    if SHOW:
        plt.show()
    return fig


# ----------------------------------------------------------------------------
#  MENU
# ----------------------------------------------------------------------------
MODS = [("1", "Block diagram (all three layers)", run_block),
        ("2", f"{L_AN} - AM / FM", run_analog),
        ("3", f"{L_MO} - PCM, BER, capacity", run_digital),
        ("4", f"{L_SA} - link budget, rain fade", run_sat),
        ("5", "Noise and signal quality check", run_noise),
        ("6", "Storm stress test (original vs ideal design)", run_stress),
        ("7", "Hybrid result, citizen map, recommendation", run_hybrid),
        ("8", "Interactive lab with sliders and ideal dots", run_lab)]


def main():
    global SHOW
    style()
    banner()
    print_assumptions()
    items = [(k, t) for k, t, _ in MODS] + [("9", "Run everything and save all figures"), ("0", "Exit")]
    while True:
        ch = menu("MAIN MENU", items)
        if ch == "0":
            print(f"\n  Thank you. Figures are stored in ./{FIG_DIR}/\n")
            return
        if ch == "9":
            SHOW = False
            for _, _, fn in MODS:
                fn()
            SHOW = True
            print(f"\n   ✔ All figures saved in ./{FIG_DIR}/")
        else:
            dict((k, fn) for k, _, fn in MODS)[ch]()
        pause()


if __name__ == "__main__":
    main()