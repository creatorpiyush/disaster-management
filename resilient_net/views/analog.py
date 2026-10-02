"""LAYER 1 - Analog emergency radio (AM / FM broadcast).  Assignment Unit I."""
import math

import numpy as np

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

AM_C, FM_C = C.COL[C.L_AN], C.COL["violet"]
TITLE = "Layer 1 · Analog emergency radio (AM / FM)"


def defaults():
    a = C.ANALOG
    return dict(mu=a["mu"], df=a["df_khz"], fm=a["fm_khz"], p=a["p_kw"], dist=a["dist_km"],
                noise=C.STORM["noise_rise"])


def evaluate(v):
    return M.analog_layer(p_kw=v["p"], dist_km=v["dist"], mu=v["mu"], df_khz=v["df"], fm_khz=v["fm"],
                          noise_rise=v["noise"], **{k: C.ANALOG[k] for k in ("fc_mhz", "gt_db", "gr_db", "nf_db",
                                                                              "clutter_db")})


def coverage_radius(v, kind):
    """Largest distance at which the median output SNR still gives intelligible speech (20 dB)."""
    d = np.geomspace(0.5, 300, 160)
    fm = M.fm_metrics(v["df"], v["fm"])
    bw = fm["carson_khz"] if kind == "FM" else 2 * v["fm"]
    out = []
    for di in d:
        lk = M.analog_link(v["p"], di, C.ANALOG["fc_mhz"], C.ANALOG["gt_db"], C.ANALOG["gr_db"], C.ANALOG["nf_db"],
                           C.ANALOG["clutter_db"], v["noise"], bw)
        out.append(float(M.fm_output_snr(lk["cnr"], fm["beta"]) if kind == "FM" else M.am_output_snr(lk["cnr"],
                                                                                                    v["mu"])))
    ok = np.array(out) >= 20
    return float(d[ok].max()) if ok.any() else 0.0


# ---------------------------------------------------------------------------
def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    am, fm, lk = r["am"], r["fm"], r["link_fm"]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_AN])
    ui.note("Role in the hybrid design: a one-way, high-power broadcast that needs no network core, works "
            "with cheap battery receivers and keeps telling citizens what to do when everything else is down.")
    ui.sub("AM emergency broadcast")
    ui.calc("Modulation index", "μ = Am / Ac", f"μ = {v['mu']:.2f}", f"{v['mu']:.2f}",
            "(μ ≤ 1 avoids over-modulation)")
    ui.calc("Bandwidth", "B_AM = 2·fm", f"2 × {v['fm']:.1f} kHz", f"{am['bw_khz']:.1f}", "kHz")
    ui.calc("Total power", "Pt = Pc(1 + μ²/2)", f"Pc(1 + {v['mu']:.2f}²/2)", f"{am['pt_over_pc']:.3f} · Pc")
    ui.calc("Power efficiency", "η = μ² / (2 + μ²)", f"{v['mu']:.2f}² / (2 + {v['mu']:.2f}²)", f"{am['eff']:.1%}")
    ui.calc("Spectrum", "carrier at fc, sidebands at fc ± fm with amplitude μ/2 each",
            f"fc ± {v['fm']:.1f} kHz", f"sidebands {am['sideband_db']:.1f} dB below carrier")
    ui.sub("FM emergency broadcast")
    ui.calc("Modulation index", "β = Δf / fm", f"{v['df']:.1f} / {v['fm']:.1f}", f"{fm['beta']:.3f}")
    ui.calc("Carson bandwidth", "B_T = 2(Δf + fm)", f"2({v['df']:.1f} + {v['fm']:.1f})", f"{fm['carson_khz']:.1f}",
            "kHz")
    js = ", ".join(f"J{n}={M.bessel_j(n, fm['beta']):+.3f}" for n in range(4))
    ui.calc("Spectral lines", "amplitude of line n = Jn(β)", js, f"{fm['n_sig']} significant sideband pairs")
    ui.calc("FM noise advantage", "SNRo/γ = 3β²/2", f"1.5 × {fm['beta']:.2f}²", f"{fm['gain_db']:+.1f}", "dB")
    ui.sub(f"Link budget at the edge of the city ({v['dist']:.0f} km)")
    ui.calc("Path loss", "L = 32.44 + 20log d + 20log f + clutter",
            f"32.44 + 20log{v['dist']:.0f} + 20log{C.ANALOG['fc_mhz']:.0f} + {C.ANALOG['clutter_db']:.0f}",
            f"{lk['pl']:.1f}", "dB")
    ui.calc("Received power", "Pr = Pt + Gt + Gr − L",
            f"{lk['pt_dbm']:.1f} + {C.ANALOG['gt_db']:.0f} + ({C.ANALOG['gr_db']:.0f}) − {lk['pl']:.1f}",
            f"{lk['pr']:.1f}", "dBm")
    ui.calc("Noise floor", "N = −174 + 10log B + F(man-made, ITU-R P.372) + storm rise",
            f"−174 + 10log({fm['carson_khz'] * 1e3:.0f}) + {lk['f_total']:.1f} + {v['noise']:.1f}",
            f"{lk['noise']:.1f}", "dBm")
    ui.calc("Carrier-to-noise", "CNR = Pr − N", f"{lk['pr']:.1f} − ({lk['noise']:.1f})", f"{lk['cnr']:.1f}", "dB")
    ui.kv("Output SNR, FM (with threshold model)", f"{r['snr_fm']:.1f} dB", r["snr_fm"] >= 20)
    ui.kv("Output SNR, AM (envelope detector)", f"{r['snr_am']:.1f} dB", r["snr_am"] >= 20)
    ui.kv("FM coverage radius (SNRo ≥ 20 dB)", f"{coverage_radius(v, 'FM'):.0f} km")
    ui.kv("AM coverage radius (SNRo ≥ 20 dB)", f"{coverage_radius(v, 'AM'):.0f} km")
    ui.bar("Citizens reached (alert)", r["reach"], ui.LAYER_TINT[C.L_AN])
    return r


# ---------------------------------------------------------------------------
def build():
    v = defaults()
    st = dict(v=v, r=evaluate(v), sim=None, mc=None, rings=[0.0, 0.33, 0.66], rad=(0, 0))
    fig = new_figure(TITLE, "AM and FM broadcast through a storm-noisy channel: modulation, spectrum, "
                            "threshold effect and coverage — all recomputed live", "LAYER 1 · REQUIRED")
    g = dict(left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    gs = fig.add_gridspec(2, 3, **g)
    ax_wave, ax_spec, ax_bes = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_demod, ax_snr, ax_map = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    # (a) live waveforms -----------------------------------------------------
    t = np.linspace(0, 3, 1500)
    ax_wave.set_title("Live transmitter output")
    l_msg, = ax_wave.plot([], [], color=C.INK2, lw=1.4, label="voice / tone m(t)")
    l_am, = ax_wave.plot([], [], color=AM_C, lw=0.9, label="AM wave")
    l_env, = ax_wave.plot([], [], color=AM_C, lw=1.6, ls="--", alpha=0.8)
    l_fm, = ax_wave.plot([], [], color=FM_C, lw=0.9, label="FM wave")
    ax_wave.set(xlim=(0, 3), ylim=(-6.2, 4.6), yticks=[3, 0, -4.2], xlabel="time (message periods)")
    ax_wave.set_yticklabels(["m(t)", "AM", "FM"])
    ax_wave.legend(loc="upper right", ncol=3, fontsize=6.8)

    # (b) spectrum -----------------------------------------------------------
    ax_spec.set_title("Spectrum around the carrier")
    ax_spec.set(xlabel="offset from carrier fc (kHz)", ylabel="line amplitude (normalised)")
    # (c) Bessel ---------------------------------------------------------------
    b = np.linspace(0, 10, 300)
    for n, a in zip(range(5), [1, 0.85, 0.7, 0.55, 0.4]):
        ax_bes.plot(b, M.bessel_j(n, b), lw=1.5, color=FM_C, alpha=a)
        k = 40 + 50 * n
        ax_bes.text(b[k], M.bessel_j(n, b[k]) + 0.05, f"J{n}", color=C.INK2, fontsize=7.5)
    ax_bes.axhline(0, color=C.MUTED, lw=0.8)
    beta_line = ax_bes.axvline(0, color=AM_C, lw=1.5)
    beta_txt = ax_bes.text(0, 0.92, "", color=AM_C, fontsize=8, fontweight="bold")
    ax_bes.plot([2.405], [0], "o", color=C.INK2, ms=5)
    ax_bes.annotate("carrier null β = 2.405", (2.405, 0), (3.4, -0.47), fontsize=7, color=C.INK2,
                    arrowprops=dict(arrowstyle="-", color=C.MUTED))
    ax_bes.set(title="FM sideband amplitudes Jn(β)", xlabel="modulation index β", ylim=(-0.6, 1.05))

    # (d) demodulated audio --------------------------------------------------
    ax_demod.set_title("What the listener hears (simulated through noise)")
    l_dm, = ax_demod.plot([], [], color=C.INK2, lw=2.2, label="original")
    l_dam, = ax_demod.plot([], [], color=AM_C, lw=1.0, label="AM receiver")
    l_dfm, = ax_demod.plot([], [], color=FM_C, lw=1.0, label="FM receiver")
    ax_demod.set(xlim=(0.5, 5.5), ylim=(-3, 3), xlabel="time (message periods)", ylabel="amplitude")
    ax_demod.legend(loc="upper right", ncol=3, fontsize=6.8)
    dm_txt = ax_demod.text(0.02, 0.05, "", transform=ax_demod.transAxes, fontsize=7.5, color=C.INK2)

    # (e) threshold ------------------------------------------------------------
    cn = np.linspace(-5, 45, 200)
    l_fmc, = ax_snr.plot([], [], color=FM_C, lw=2, label="FM theory")
    l_amc, = ax_snr.plot([], [], color=AM_C, lw=2, label="AM theory")
    mc_fm = ax_snr.scatter([], [], s=28, color=FM_C, edgecolor=C.PANEL, lw=1.5, zorder=4, label="FM simulated")
    mc_am = ax_snr.scatter([], [], s=28, marker="s", color=AM_C, edgecolor=C.PANEL, lw=1.5, zorder=4,
                           label="AM simulated")
    op_fm, = ax_snr.plot([], [], "o", ms=13, mfc="none", mec=FM_C, mew=2)
    op_am, = ax_snr.plot([], [], "o", ms=13, mfc="none", mec=AM_C, mew=2)
    ax_snr.axhline(20, color=C.MUTED, ls=":", lw=1)
    ax_snr.text(-4, 21, "intelligible speech (20 dB)", fontsize=7, color=C.MUTED)
    ax_snr.axvspan(-5, 10, color=C.COL["bad"], alpha=0.07)
    ax_snr.text(-4, 60, "FM threshold\nregion", fontsize=7, color=C.COL["bad"])
    ax_snr.set(title="Output SNR vs carrier-to-noise (threshold effect)", xlabel="CNR at receiver (dB)",
               ylabel="output SNR (dB)", xlim=(-5, 45), ylim=(-10, 75))
    ax_snr.legend(loc="lower right", fontsize=6.8, ncol=2)

    # (f) coverage map ---------------------------------------------------------
    ax_map.set_title("Coverage around the broadcast mast")
    ax_map.set_aspect("equal")
    ax_map.set(xlim=(-130, 130), ylim=(-130, 130), ylabel="km")
    rng = np.random.default_rng(3)
    rr = 125 * np.sqrt(rng.random(500))
    th = 2 * np.pi * rng.random(500)
    homes = np.c_[rr * np.cos(th), rr * np.sin(th)]
    sc_homes = ax_map.scatter(homes[:, 0], homes[:, 1], s=4, color=C.MUTED, alpha=0.8)
    th_c = np.linspace(0, 2 * np.pi, 200)
    c_fm, = ax_map.plot([], [], color=FM_C, lw=2, label="FM, SNRo ≥ 20 dB")
    c_am, = ax_map.plot([], [], color=AM_C, lw=2, ls="--", label="AM, SNRo ≥ 20 dB")
    c_city, = ax_map.plot([], [], color=C.INK2, lw=1, ls=":", label="city edge (distance slider)")
    ring_lines = [ax_map.plot([], [], color=FM_C, lw=1.2)[0] for _ in st["rings"]]
    ax_map.plot([0], [0], "^", color=C.INK, ms=11, mec=C.BG)
    ax_map.legend(loc="upper left", fontsize=6.3, bbox_to_anchor=(0, -0.13), ncol=2)
    map_txt = ax_map.text(0.98, 0.97, "", transform=ax_map.transAxes, ha="right", va="top", fontsize=7.5,
                          color=C.INK)

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        st["r"] = evaluate(v)
        fm = st["r"]["fm"]
        beta = fm["beta"]
        # spectrum
        ax_spec.cla()
        ax_spec.set_title("Spectrum around the carrier")
        n = np.arange(-int(beta) - 6, int(beta) + 7)
        jn = np.abs([M.bessel_j(int(k), beta) for k in n])
        ax_spec.axvspan(-fm["carson_khz"] / 2, fm["carson_khz"] / 2, color=FM_C, alpha=0.12)
        ax_spec.vlines(n * v["fm"], 0, jn, color=FM_C, lw=2.4, label=f"FM lines |Jn(β)|, β = {beta:.2f}")
        ax_spec.vlines(np.array([-1, 0, 1]) * v["fm"] + 0.25, 0, [v["mu"] / 2, 1, v["mu"] / 2], color=AM_C, lw=2.4,
                       label=f"AM: carrier + sidebands (μ = {v['mu']:.2f})")
        ax_spec.annotate("", (-fm["carson_khz"] / 2, 1.08), (fm["carson_khz"] / 2, 1.08),
                         arrowprops=dict(arrowstyle="<->", color=FM_C))
        ax_spec.text(0, 1.11, f"Carson BW = {fm['carson_khz']:.1f} kHz", ha="center", fontsize=7.5, color=FM_C)
        ax_spec.annotate("", (-v["fm"], -0.1), (v["fm"], -0.1), arrowprops=dict(arrowstyle="<->", color=AM_C))
        ax_spec.text(v["fm"] + 0.5, -0.12, f"AM BW = {2 * v['fm']:.1f} kHz", fontsize=7.5, color=AM_C, va="center")
        span = max(fm["carson_khz"] * 0.75, 4 * v["fm"])
        ax_spec.set(xlim=(-span, span), ylim=(-0.2, 1.6), xlabel="offset from carrier fc (kHz)",
                    ylabel="line amplitude (normalised)")
        ax_spec.legend(loc="upper left", fontsize=6.5)
        beta_line.set_xdata([min(beta, 10)] * 2)
        beta_txt.set_position((min(beta, 10) + 0.15, 0.92))
        beta_txt.set_text(f"β = {beta:.2f}")
        # threshold curves + Monte-Carlo points
        l_fmc.set_data(cn, M.fm_output_snr(cn, beta))
        l_amc.set_data(cn, M.am_output_snr(cn, v["mu"]))
        pts = np.array([0, 5, 10, 15, 20, 30])
        sims = [M.simulate_am_fm(v["mu"], beta, c, n=3000, seed=7) for c in pts]
        mc_fm.set_offsets(np.c_[pts, [s["snr_fm"] for s in sims]])
        mc_am.set_offsets(np.c_[pts, [s["snr_am"] for s in sims]])
        st["rad"] = (coverage_radius(v, "FM"), coverage_radius(v, "AM"))
        c_fm.set_data(st["rad"][0] * np.cos(th_c), st["rad"][0] * np.sin(th_c))
        c_am.set_data(st["rad"][1] * np.cos(th_c), st["rad"][1] * np.sin(th_c))
        c_city.set_data(v["dist"] * np.cos(th_c), v["dist"] * np.sin(th_c))
        d = np.hypot(homes[:, 0], homes[:, 1])
        sc_homes.set_color(np.where(d <= st["rad"][0], FM_C, np.where(d <= st["rad"][1], AM_C, "#4a4a46")))
        r = st["r"]
        cnr = r["link_fm"]["cnr"]
        op_fm.set_data([np.clip(cnr, -5, 45)], [np.clip(r["snr_fm"], -10, 75)])
        cnr_am = r["link_am"]["cnr"]
        op_am.set_data([np.clip(cnr_am, -5, 45)], [np.clip(r["snr_am"], -10, 75)])
        map_txt.set_text(f"FM radius {st['rad'][0]:.0f} km\nAM radius {st['rad'][1]:.0f} km")
        ok = r["reach"]
        ro.set_text(
            f"LIVE RESULTS  (edge of city, {v['dist']:.0f} km)\n"
            f"AM  μ={v['mu']:.2f}  BW={2 * v['fm']:.1f} kHz  η={r['am']['eff']:.0%}\n"
            f"FM  β={beta:.2f}  Carson BW={fm['carson_khz']:.1f} kHz\n"
            f"Pr = {r['link_fm']['pr']:.1f} dBm   CNR = {cnr:.1f} dB\n"
            f"SNRo  FM {r['snr_fm']:5.1f} dB | AM {r['snr_am']:5.1f} dB\n"
            f"Citizens reached (alert): {ok:.0%}")
        ro.set_color(status_colour(ok))
        st["sim"] = None
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, cols=2, rows=3)
    ctl.slider("mu", "AM index μ", 0.1, 1.0, v["mu"], fmt="%.2f", color=AM_C)
    ctl.slider("df", "FM deviation Δf (kHz)", 1, 25, v["df"], step=0.5, fmt="%.1f", color=FM_C)
    ctl.slider("fm", "Message freq fm (kHz)", 0.5, 5, v["fm"], step=0.1, fmt="%.1f")
    ctl.slider("p", "Tx power (kW)", 0.05, 10, v["p"], fmt="%.2f")
    ctl.slider("dist", "City edge distance (km)", 5, 120, v["dist"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 30, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.reset_button([0.6, 0.045, 0.1, 0.03])
    ctl.button([0.49, 0.045, 0.1, 0.03], "▶  Play / pause", player.toggle)
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        ph = frame * 0.03
        r = st["r"]
        beta = r["fm"]["beta"]
        m = np.cos(2 * np.pi * (t + ph))
        fc = 14
        l_msg.set_data(t, 3 + m)
        am = (1 + v["mu"] * m) * np.cos(2 * np.pi * fc * t)
        l_am.set_data(t, am)
        l_env.set_data(t, 1 + v["mu"] * m)
        l_fm.set_data(t, -4.2 + np.cos(2 * np.pi * fc * t + beta * np.sin(2 * np.pi * (t + ph))))
        if st["sim"] is None or frame % 8 == 0:
            st["sim"] = M.simulate_am_fm(v["mu"], beta, r["link_fm"]["cnr"], n=3000, seed=frame)
        s = st["sim"]
        shift = int(len(s["t"]) * ((ph * 0.5) % 1) / 6)
        l_dm.set_data(s["t"], np.roll(s["m"], -shift))
        l_dam.set_data(s["t"], np.clip(np.roll(s["am_out"], -shift), -3, 3))
        l_dfm.set_data(s["t"], np.clip(np.roll(s["fm_out"], -shift), -3, 3))
        dm_txt.set_text(f"measured SNR → AM {s['snr_am']:.1f} dB · FM {s['snr_fm']:.1f} dB "
                        f"(CNR {r['link_fm']['cnr']:.1f} dB)")
        R = max(st["rad"][0], 5)
        for i, ln in enumerate(ring_lines):
            st["rings"][i] = (st["rings"][i] + 0.012) % 1
            rr_ = st["rings"][i] * R
            ln.set_data(rr_ * np.cos(th_c), rr_ * np.sin(th_c))
            ln.set_alpha(1 - st["rings"][i])
        pulse = 11 + 4 * abs(math.sin(frame * 0.2))
        op_fm.set_markersize(pulse)
        op_am.set_markersize(pulse)

    return fig, step, ctl
