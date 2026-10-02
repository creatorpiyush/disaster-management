"""Layer 1 - analog emergency radio (AM/FM broadcast). Unit I."""
import math
from types import SimpleNamespace

import matplotlib
import numpy as np
from matplotlib.patches import Patch

from .. import config as C, models as M, terrain, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

AM_C, FM_C = C.COL[C.L_AN], C.COL["violet"]
TITLE = "Layer 1: Analog emergency radio (AM / FM)"


def defaults():
    a = C.ANALOG
    return dict(mu=a["mu"], df=a["df_khz"], fm=a["fm_khz"], p=a["p_kw"], dist=a["dist_km"],
                noise=C.STORM["noise_rise"], terr=a["terrain_db"])


def _homes():
    L = terrain.link_tables()
    return L["fm_d"], L["fm_loss"]


def evaluate(v):
    return M.analog_layer(p_kw=v["p"], dist_km=v["dist"], mu=v["mu"], df_khz=v["df"], fm_khz=v["fm"],
                          noise_rise=v["noise"], terrain_db=v["terr"], homes=_homes(),
                          **{k: C.ANALOG[k] for k in ("fc_mhz", "gt_db", "gr_db", "nf_db", "clutter_db")})


def coverage_radius(v, kind):
    # how far out the median output SNR stays above 20 dB (roughly where speech stays understandable)
    d = np.geomspace(0.5, 300, 160)
    fm = M.fm_metrics(v["df"], v["fm"])
    bw = fm["carson_khz"] if kind == "FM" else 2 * v["fm"]
    out = []
    for di in d:
        lk = M.analog_link(v["p"], di, C.ANALOG["fc_mhz"], C.ANALOG["gt_db"], C.ANALOG["gr_db"], C.ANALOG["nf_db"],
                           C.ANALOG["clutter_db"], v["noise"], bw, v["terr"])
        out.append(float(M.fm_output_snr(lk["cnr"], fm["beta"]) if kind == "FM" else M.am_output_snr(lk["cnr"],
                                                                                                    v["mu"])))
    ok = np.array(out) >= 20
    return float(d[ok].max()) if ok.any() else 0.0


def print_calculations(v=None):
    v = v or defaults()
    r = evaluate(v)
    am, fm, lk = r["am"], r["fm"], r["link_fm"]
    ui.head(TITLE.upper(), ui.LAYER_TINT[C.L_AN])
    ui.note("Why it's here: one-way, high power, no core network needed, cheap battery radios. "
            "Keeps telling people what to do after everything else has died.")
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
    hd, hl = _homes()
    ui.sub("Ridges between the mast and the homes (real terrain, ITU-R P.526)")
    ui.calc("Fresnel–Kirchhoff parameter", "v = h·√(2/λ · (1/d1 + 1/d2))",
            "h = height of the worst ridge above the direct path", "computed for every home from SRTM data")
    ui.calc("Knife-edge loss", "J(v) = 6.9 + 20log(√((v − 0.1)² + 1) + v − 0.1),  v > −0.78",
            f"median over {len(hl)} homes", f"{np.median(hl):.1f}",
            f"dB  ({np.mean(hl > 30):.0%} of homes lose more than 30 dB)")
    ui.sub(f"Link budget at the edge of the district ({v['dist']:.0f} km)")
    ui.calc("Path loss", "L = 32.44 + 20log d + 20log f + clutter + J(v)",
            f"32.44 + 20log{v['dist']:.0f} + 20log{C.ANALOG['fc_mhz']:.0f} + {C.ANALOG['clutter_db']:.0f} + "
            f"{v['terr']:.0f}", f"{lk['pl']:.1f}", "dB")
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
    ui.kv("Real homes with intelligible FM (SNRo ≥ 20 dB, σ = 6 dB)", f"{r['coverage']:.1%}")
    ui.bar("Citizens reached (alert)", r["reach"], ui.LAYER_TINT[C.L_AN])
    return r


def _setup_waves(ax):
    ax.set_title("Live transmitter output")
    w = SimpleNamespace()
    w.msg, = ax.plot([], [], color=C.INK2, lw=1.4, label="voice / tone m(t)")
    w.am, = ax.plot([], [], color=AM_C, lw=0.9, label="AM wave")
    w.env, = ax.plot([], [], color=AM_C, lw=1.6, ls="--", alpha=0.8)
    w.fm, = ax.plot([], [], color=FM_C, lw=0.9, label="FM wave")
    ax.set(xlim=(0, 3), ylim=(-6.2, 4.6), yticks=[3, 0, -4.2], xlabel="time (message periods)")
    ax.set_yticklabels(["m(t)", "AM", "FM"])
    ax.legend(loc="upper right", ncol=3, fontsize=6.8)
    return w


def _setup_bessel(ax):
    b = np.linspace(0, 10, 300)
    for n, a in zip(range(5), [1, 0.85, 0.7, 0.55, 0.4]):
        ax.plot(b, M.bessel_j(n, b), lw=1.5, color=FM_C, alpha=a)
        k = 40 + 50 * n
        ax.text(b[k], M.bessel_j(n, b[k]) + 0.05, f"J{n}", color=C.INK2, fontsize=7.5)
    ax.axhline(0, color=C.MUTED, lw=0.8)
    line = ax.axvline(0, color=AM_C, lw=1.5)
    txt = ax.text(0, 0.92, "", color=AM_C, fontsize=8, fontweight="bold")
    ax.plot([2.405], [0], "o", color=C.INK2, ms=5)
    ax.annotate("carrier null β = 2.405", (2.405, 0), (3.4, -0.47), fontsize=7, color=C.INK2,
                arrowprops=dict(arrowstyle="-", color=C.MUTED))
    ax.set(title="FM sideband amplitudes Jn(β)", xlabel="modulation index β", ylim=(-0.6, 1.05))
    return line, txt


def _setup_demod(ax):
    ax.set_title("What the listener hears (simulated through noise)")
    d = SimpleNamespace()
    d.orig, = ax.plot([], [], color=C.INK2, lw=2.2, label="original")
    d.am, = ax.plot([], [], color=AM_C, lw=1.0, label="AM receiver")
    d.fm, = ax.plot([], [], color=FM_C, lw=1.0, label="FM receiver")
    ax.set(xlim=(0.5, 5.5), ylim=(-3, 3), xlabel="time (message periods)", ylabel="amplitude")
    ax.legend(loc="upper right", ncol=3, fontsize=6.8)
    d.txt = ax.text(0.02, 0.05, "", transform=ax.transAxes, fontsize=7.5, color=C.INK2)
    return d


def _setup_threshold(ax):
    th = SimpleNamespace()
    th.fm_curve, = ax.plot([], [], color=FM_C, lw=2, label="FM theory")
    th.am_curve, = ax.plot([], [], color=AM_C, lw=2, label="AM theory")
    th.fm_sim = ax.scatter([], [], s=28, color=FM_C, edgecolor=C.PANEL, lw=1.5, zorder=4, label="FM simulated")
    th.am_sim = ax.scatter([], [], s=28, marker="s", color=AM_C, edgecolor=C.PANEL, lw=1.5, zorder=4,
                           label="AM simulated")
    th.fm_op, = ax.plot([], [], "o", ms=13, mfc="none", mec=FM_C, mew=2)
    th.am_op, = ax.plot([], [], "o", ms=13, mfc="none", mec=AM_C, mew=2)
    ax.axhline(20, color=C.MUTED, ls=":", lw=1)
    ax.text(-4, 21, "intelligible speech (20 dB)", fontsize=7, color=C.MUTED)
    ax.axvspan(-5, 10, color=C.COL["bad"], alpha=0.07)
    ax.text(-4, 60, "FM threshold\nregion", fontsize=7, color=C.COL["bad"])
    ax.set(title="Output SNR vs carrier-to-noise (threshold effect)", xlabel="CNR at receiver (dB)",
           ylabel="output SNR (dB)", xlim=(-5, 45), ylim=(-10, 75))
    ax.legend(loc="lower right", fontsize=6.8, ncol=2)
    return th


def _setup_map(ax, S, grid_shape, n_rings):
    TR = S["T"]
    ax.set_title("Coverage on the real terrain")
    ax.imshow(TR.hillshade(), extent=TR.extent, origin="lower", cmap="gray", vmin=-0.4, vmax=1.4)
    m = SimpleNamespace()
    m.img = ax.imshow(np.zeros(grid_shape + (4,)), extent=TR.extent, origin="lower", interpolation="bilinear")
    for rv in TR.rivers:
        ax.plot(*rv["xy"].T, color="#4f8fd0", lw=0.7)
    m.homes = ax.scatter(*S["cit"].T, s=5, color=C.MUTED, zorder=3, lw=0)
    ax.plot(*S["mast"], "^", ms=11, color=C.INK, mec=C.BG, zorder=5)
    ax.text(S["mast"][0], S["mast"][1] + 0.9, "FM mast\n(ridge)", ha="center", fontsize=6.5, color=C.INK)
    for nm in ("Gangtok", "Singtam", "Ranipool", "Pakyong", "Dikchu"):
        place = next((q for q in TR.places if q["name"] == nm), None)
        if place:
            ax.text(place["x"], place["y"] - 0.9, nm, ha="center", fontsize=6.5, color=C.INK2)
    m.rings = [ax.plot([], [], color=FM_C, lw=1.0)[0] for _ in range(n_rings)]
    ax.set(xlim=TR.extent[:2], ylim=TR.extent[2:], xticks=[], yticks=[])
    ax.set_aspect("equal")
    ax.legend(handles=[Patch(color=FM_C, alpha=0.6, label="FM ≥ 20 dB"), Patch(color=AM_C, alpha=0.6,
              label="AM only"), Patch(color="#5a1f22", alpha=0.6, label="ridge shadow")],
              loc="upper left", fontsize=6.3, bbox_to_anchor=(0, -0.01), ncol=3)
    m.txt = ax.text(0.98, 0.03, "", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5,
                    color=C.INK, bbox=dict(fc=C.PANEL, ec="none", alpha=0.8))
    return m


def _draw_spectrum(ax, v, fm):
    beta = fm["beta"]
    ax.cla()
    ax.set_title("Spectrum around the carrier")
    n = np.arange(-int(beta) - 6, int(beta) + 7)
    jn = np.abs([M.bessel_j(int(k), beta) for k in n])
    ax.axvspan(-fm["carson_khz"] / 2, fm["carson_khz"] / 2, color=FM_C, alpha=0.12)
    ax.vlines(n * v["fm"], 0, jn, color=FM_C, lw=2.4, label=f"FM lines |Jn(β)|, β = {beta:.2f}")
    ax.vlines(np.array([-1, 0, 1]) * v["fm"] + 0.25, 0, [v["mu"] / 2, 1, v["mu"] / 2], color=AM_C, lw=2.4,
              label=f"AM: carrier + sidebands (μ = {v['mu']:.2f})")
    ax.annotate("", (-fm["carson_khz"] / 2, 1.08), (fm["carson_khz"] / 2, 1.08),
                arrowprops=dict(arrowstyle="<->", color=FM_C))
    ax.text(0, 1.11, f"Carson BW = {fm['carson_khz']:.1f} kHz", ha="center", fontsize=7.5, color=FM_C)
    ax.annotate("", (-v["fm"], -0.1), (v["fm"], -0.1), arrowprops=dict(arrowstyle="<->", color=AM_C))
    ax.text(v["fm"] + 0.5, -0.12, f"AM BW = {2 * v['fm']:.1f} kHz", fontsize=7.5, color=AM_C, va="center")
    span = max(fm["carson_khz"] * 0.75, 4 * v["fm"])
    ax.set(xlim=(-span, span), ylim=(-0.2, 1.6), xlabel="offset from carrier fc (kHz)",
           ylabel="line amplitude (normalised)")
    ax.legend(loc="upper left", fontsize=6.5)


def _snr(v, d, loss, kind):
    a = C.ANALOG
    fm = M.fm_metrics(v["df"], v["fm"])
    bw = fm["carson_khz"] if kind == "FM" else 2 * v["fm"]
    lk = M.analog_link(v["p"], np.maximum(d, 0.2), a["fc_mhz"], a["gt_db"], a["gr_db"], a["nf_db"],
                       a["clutter_db"], v["noise"], bw, loss)
    return M.fm_output_snr(lk["cnr"], fm["beta"]) if kind == "FM" else M.am_output_snr(lk["cnr"], v["mu"])


_RGBA = {k: np.array(matplotlib.colors.to_rgba(c, 0.55)) for k, c in
         (("fm", FM_C), ("am", AM_C), ("none", "#5a1f22"))}


def _draw_coverage(m, v, grid, homes):
    fm_ok, am_ok = _snr(v, grid[1], grid[0], "FM") >= 20, _snr(v, grid[1], grid[0], "AM") >= 20
    m.img.set_data(np.where(fm_ok[..., None], _RGBA["fm"], np.where(am_ok[..., None], _RGBA["am"], _RGBA["none"])))
    h_fm, h_am = _snr(v, *homes, "FM") >= 20, _snr(v, *homes, "AM") >= 20
    m.homes.set_color(np.where(h_fm, C.INK, np.where(h_am, AM_C, C.COL["bad"])))
    m.txt.set_text(f"homes with clear FM {h_fm.mean():.0%} · AM {h_am.mean():.0%}")


def _draw_threshold(th, v, r, cn):
    beta = r["fm"]["beta"]
    th.fm_curve.set_data(cn, M.fm_output_snr(cn, beta))
    th.am_curve.set_data(cn, M.am_output_snr(cn, v["mu"]))
    pts = np.array([0, 5, 10, 15, 20, 30])
    sims = [M.simulate_am_fm(v["mu"], beta, c, n=3000, seed=7) for c in pts]
    th.fm_sim.set_offsets(np.c_[pts, [s["snr_fm"] for s in sims]])
    th.am_sim.set_offsets(np.c_[pts, [s["snr_am"] for s in sims]])


def _readout_text(v, r):
    fm = r["fm"]
    return (f"LIVE RESULTS  (district edge {v['dist']:.0f} km, ridge {v['terr']:.0f} dB)\n"
            f"AM  μ={v['mu']:.2f}  BW={2 * v['fm']:.1f} kHz  η={r['am']['eff']:.0%}\n"
            f"FM  β={fm['beta']:.2f}  Carson BW={fm['carson_khz']:.1f} kHz\n"
            f"Pr = {r['link_fm']['pr']:.1f} dBm   CNR = {r['link_fm']['cnr']:.1f} dB\n"
            f"SNRo  FM {r['snr_fm']:5.1f} dB | AM {r['snr_am']:5.1f} dB\n"
            f"Real homes reached (alert): {r['reach']:.0%}")


def build():
    v = defaults()
    st = dict(r=evaluate(v), sim=None, rings=[0.0, 0.33, 0.66])
    fig = new_figure(TITLE, "AM/FM from a ridge-top mast: modulation, spectrum, FM threshold, and coverage "
                            "over the real hills", "LAYER 1 (REQUIRED)")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.28, hspace=0.42)
    ax_wave, ax_spec, ax_bes = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_demod, ax_snr, ax_map = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    t = np.linspace(0, 3, 1500)
    cn = np.linspace(-5, 45, 200)
    th_c = np.linspace(0, 2 * np.pi, 200)
    waves = _setup_waves(ax_wave)
    ax_spec.set_title("Spectrum around the carrier")
    ax_spec.set(xlabel="offset from carrier fc (kHz)", ylabel="line amplitude (normalised)")
    beta_line, beta_txt = _setup_bessel(ax_bes)
    demod = _setup_demod(ax_demod)
    thr = _setup_threshold(ax_snr)
    S = terrain.scenario()
    grid = terrain.fm_loss_grid()  # (loss, dist)
    homes = _homes()
    cmap = _setup_map(ax_map, S, grid[0].shape, len(st["rings"]))
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)

    def recompute(vals):
        v.update({k: vals[k] for k in v})
        r = st["r"] = evaluate(v)
        beta = r["fm"]["beta"]
        _draw_spectrum(ax_spec, v, r["fm"])
        beta_line.set_xdata([min(beta, 10)] * 2)
        beta_txt.set_position((min(beta, 10) + 0.15, 0.92))
        beta_txt.set_text(f"β = {beta:.2f}")
        _draw_threshold(thr, v, r, cn)
        _draw_coverage(cmap, v, grid, homes)
        thr.fm_op.set_data([np.clip(r["link_fm"]["cnr"], -5, 45)], [np.clip(r["snr_fm"], -10, 75)])
        thr.am_op.set_data([np.clip(r["link_am"]["cnr"], -5, 45)], [np.clip(r["snr_am"], -10, 75)])
        ro.set_text(_readout_text(v, r))
        ro.set_color(status_colour(r["reach"]))
        st["sim"] = None
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.46, 0.17), cols=2, rows=4)
    ctl.slider("mu", "AM index μ", 0.1, 1.0, v["mu"], fmt="%.2f", color=AM_C)
    ctl.slider("df", "FM deviation Δf (kHz)", 1, 25, v["df"], step=0.5, fmt="%.1f", color=FM_C)
    ctl.slider("fm", "Message freq fm (kHz)", 0.5, 5, v["fm"], step=0.1, fmt="%.1f")
    ctl.slider("p", "Tx power (kW)", 0.01, 1.0, v["p"], step=0.01, fmt="%.2f")
    ctl.slider("dist", "District edge (km)", 2, 60, v["dist"], step=1, fmt="%.0f")
    ctl.slider("noise", "Storm noise rise (dB)", 0, 30, v["noise"], step=0.5, fmt="%.1f", color=C.COL["bad"])
    ctl.slider("terr", "Ridge loss at edge (dB)", 0, 50, v["terr"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.reset_button([0.49, 0.06, 0.11, 0.035])
    ctl.button([0.61, 0.06, 0.11, 0.035], "▶  Play / pause", player.toggle)
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        ph = frame * 0.03
        r = st["r"]
        m = np.cos(2 * np.pi * (t + ph))
        fc = 14
        waves.msg.set_data(t, 3 + m)
        waves.am.set_data(t, (1 + v["mu"] * m) * np.cos(2 * np.pi * fc * t))
        waves.env.set_data(t, 1 + v["mu"] * m)
        waves.fm.set_data(t, -4.2 + np.cos(2 * np.pi * fc * t + r["fm"]["beta"] * np.sin(2 * np.pi * (t + ph))))

        if st["sim"] is None or frame % 8 == 0:  # the demod sim is slow, don't redo it every frame
            st["sim"] = M.simulate_am_fm(v["mu"], r["fm"]["beta"], r["link_fm"]["cnr"], n=3000, seed=frame)
        s = st["sim"]
        shift = int(len(s["t"]) * ((ph * 0.5) % 1) / 6)
        demod.orig.set_data(s["t"], np.roll(s["m"], -shift))
        demod.am.set_data(s["t"], np.clip(np.roll(s["am_out"], -shift), -3, 3))
        demod.fm.set_data(s["t"], np.clip(np.roll(s["fm_out"], -shift), -3, 3))
        demod.txt.set_text(f"measured SNR → AM {s['snr_am']:.1f} dB · FM {s['snr_fm']:.1f} dB "
                           f"(CNR {r['link_fm']['cnr']:.1f} dB)")

        for i, ln in enumerate(cmap.rings):  # radio waves spreading out from the mast
            st["rings"][i] = (st["rings"][i] + 0.012) % 1
            rr = st["rings"][i] * 14.0
            ln.set_data(S["mast"][0] + rr * np.cos(th_c), S["mast"][1] + rr * np.sin(th_c))
            ln.set_alpha(1 - st["rings"][i])
        pulse = 11 + 4 * abs(math.sin(frame * 0.2))
        thr.fm_op.set_markersize(pulse)
        thr.am_op.set_markersize(pulse)

    return fig, step, ctl
