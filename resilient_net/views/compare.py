"""COMPARISON - all layers side by side, the hybrid result, and the effect of terrain and storm phase."""
import math

import numpy as np

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

TITLE = "Comparison of all layers · hybrid network"
PHASES = ["During landfall", "Recovery (first 72 h)"]
LAT_MS = {C.L_AN: 1, C.L_MO: 30, C.L_SA: 257, C.L_UAV: 35, C.L_MESH: 780}
AXES = ["Reach now", "Data rate", "Low latency", "Storm\nrobustness", "Infrastructure\nindependence",
        "Deploy speed", "Cost\nefficiency"]
FAILOVER = [C.L_MO, C.L_UAV, C.L_SA, C.L_MESH]


def storm_for(intensity, phase):
    s = M.storm_from_intensity(intensity)
    if phase == PHASES[1]:            # eye has passed: wind and rain drop, damage and demand remain
        s = dict(s, wind=min(s["wind"], 9.0), rain=s["rain"] * 0.15, noise_rise=s["noise_rise"] * 0.5,
                 surge=s["surge"] * 1.2)
    return s


def evaluate(v):
    e = M.evaluate_all(storm_for(v["i"], v["phase"]), v["terrain"])
    inc = v.get("inc", {})
    layers = [C.L_MO, C.L_SA] + [l for l in (C.L_UAV, C.L_MESH) if inc.get(C.SHORT[l], True)]
    e["hybrid_sel"] = 1 - float(np.prod([1 - e["reach"][l] for l in layers]))
    e["sel_layers"] = layers
    return e


def scores(e, calm):
    out = {}
    for l in C.ALL_LAYERS:
        st = M.LAYER_STATIC[l]
        rate = (math.log10(M.DATA_RATE[l]) - 3) / 4
        lat = 1 - math.log10(LAT_MS[l]) / 3
        robust = min(1.0, e["reach"][l] / max(calm["reach"][l], 1e-3))
        out[l] = [e["reach"][l], rate, lat, robust, st[3], st[0], st[1]]
    return out


def failover_shares(reach, layers):
    left, shares = 1.0, []
    for l in layers:
        s = left * reach[l]
        shares.append((l, s))
        left -= s
    alert = left * reach[C.L_AN]
    return shares + [("Analog alert only", alert), ("No contact", left - alert)]


def print_calculations(v=None):
    v = v or dict(i=0.4, phase=PHASES[0], terrain=C.TERRAINS[0])
    e = evaluate(v)
    ui.head("COMPARISON OF ALL LAYERS", ui.cyan)
    ui.note(f"Storm intensity {v['i']:.2f} · {v['phase']} · terrain: {v['terrain']}. "
            "Each layer is evaluated with its own physical model; the hybrid assumes the layers fail "
            "independently, so availability = 1 − Π(1 − p_i).")
    print()
    print(f"    {'Layer':<30}{'Reach':>8}{'Data rate':>12}{'Latency':>10}  Type")
    ui.hr("·")
    for l in C.ALL_LAYERS:
        tag = "required" if l in C.CORE_LAYERS else "optional extension"
        rate = M.DATA_RATE[l]
        rs = f"{rate / 1e6:.1f} Mb/s" if rate >= 1e6 else f"{rate / 1e3:.1f} kb/s"
        print(f"    {ui.LAYER_TINT[l](f'{l:<30}')}{e['reach'][l]:>7.0%}{rs:>12}{LAT_MS[l]:>8} ms  {tag}")
    ui.hr("·")
    ui.calc("Hybrid (3 required layers, two-way)", "A = 1 − (1 − p_mobile)(1 − p_satellite)",
            f"1 − (1 − {e['reach'][C.L_MO]:.2f})(1 − {e['reach'][C.L_SA]:.2f})", f"{e['hybrid_core']:.1%}")
    ui.calc("Hybrid + supplementary layers (two-way)", "A = 1 − Π(1 − p_i), i ∈ {mobile, sat, UAV, mesh}", "",
            f"{e['hybrid_ext']:.1%}")
    ui.calc("Alert reach (any layer incl. analog radio)", "1 − Π over all five layers", "", f"{e['alert']:.1%}")
    ui.bar("Hybrid, required layers", e["hybrid_core"], ui.green)
    ui.bar("Hybrid, with optional layers", e["hybrid_ext"], ui.green)
    best = max([l for l in C.ALL_LAYERS if l != C.L_AN], key=lambda l: e["reach"][l])
    ui.note(f"Best single two-way layer here: {best} ({e['reach'][best]:.0%}). The required three-layer hybrid "
            f"reaches {e['hybrid_core']:.0%} two-way; adding the optional layers could raise this to "
            f"{e['hybrid_ext']:.0%}.")
    return e


def build():
    v = dict(i=0.4, phase=PHASES[0], terrain=C.TERRAINS[0], inc={"UAV": True, "Mesh": True})
    st = dict(e=None, shown={l: 0.0 for l in C.ALL_LAYERS + ["core", "sel"]}, radar=None, target=None)
    fig = new_figure(TITLE, "Each layer has strengths and weak points. The layers are combined so that one "
                            "layer's weak point is covered by another.", "COMPARISON")
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.87, bottom=0.27, wspace=0.32, hspace=0.45)
    ax_rad = fig.add_subplot(gs[0, 0], projection="polar")
    ax_bar, ax_sw = fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_rl, ax_fo, ax_tab = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]), fig.add_subplot(gs[1, 2])

    ang = np.linspace(0, 2 * np.pi, len(AXES), endpoint=False)
    ax_rad.set_facecolor(C.PANEL)
    ax_rad.set_xticks(ang, AXES, fontsize=7, color=C.INK2)
    ax_rad.set_yticks([0.25, 0.5, 0.75, 1.0], ["", "", "", ""])
    ax_rad.set_ylim(0, 1.05)
    ax_rad.spines["polar"].set_color(C.GRID)
    ax_rad.set_title("Layer profiles (normalised 0–1)", pad=14)
    rad_lines, rad_fills = {}, {}
    for l in C.ALL_LAYERS:
        ls = "-" if l in C.CORE_LAYERS else "--"
        rad_lines[l], = ax_rad.plot([], [], color=C.COL[l], lw=1.8, ls=ls, label=C.SHORT[l])
    ax_rad.legend(loc="upper left", bbox_to_anchor=(-0.42, 1.12), fontsize=6.8)

    ax_bar.set_title("Citizens reached by each layer")
    names = [C.SHORT[l] for l in C.ALL_LAYERS] + ["Hybrid\n(3 req.)", "Hybrid\n(+ opt.)"]
    cols = [C.COL[l] for l in C.ALL_LAYERS] + ["#bdbcb3", C.INK]
    bars = ax_bar.bar(range(7), np.zeros(7), color=cols, width=0.66)
    for b, l in zip(bars, C.ALL_LAYERS):
        if l in C.EXTRA_LAYERS:
            b.set_hatch("///")
            b.set_edgecolor(C.PANEL)
    bar_txt = [ax_bar.text(i, 0, "", ha="center", fontsize=7.5, color=C.INK) for i in range(7)]
    ax_bar.set_xticks(range(7), names, fontsize=7)
    ax_bar.set(ylim=(0, 1.12), ylabel="share of citizens")
    ax_bar.axvline(4.5, color=C.MUTED, lw=0.8, ls=":")

    ax_sw.set_title("Reach vs storm intensity")
    sw_lines = {l: ax_sw.plot([], [], color=C.COL[l], lw=1.4, ls="-" if l in C.CORE_LAYERS else "--")[0]
                for l in C.ALL_LAYERS}
    sw_core, = ax_sw.plot([], [], color="#bdbcb3", lw=3, label="hybrid, 3 required")
    sw_sel, = ax_sw.plot([], [], color=C.INK, lw=3, label="hybrid, + optional")
    sw_cur = ax_sw.axvline(0.4, color=C.COL["warn"], lw=1.5)
    ax_sw.set(xlabel="storm intensity (0 = calm, 1 = extreme)", ylabel="share of citizens", xlim=(0, 1),
              ylim=(0, 1.05))
    ax_sw.legend(loc="lower left", fontsize=7)

    ax_rl.set_title("Data rate vs latency (bubble = reach)")
    rl_sc = ax_rl.scatter([M.DATA_RATE[l] for l in C.ALL_LAYERS], [LAT_MS[l] for l in C.ALL_LAYERS], s=100,
                          c=[C.COL[l] for l in C.ALL_LAYERS], alpha=0.85, edgecolor=C.INK, lw=0.8)
    for l in C.ALL_LAYERS:
        ax_rl.text(M.DATA_RATE[l] * 1.5, LAT_MS[l] * 1.25, C.SHORT[l], fontsize=7.5, color=C.INK2)
    ax_rl.set(xscale="log", yscale="log", xlim=(500, 1e8), ylim=(0.4, 4000), xlabel="data rate (bit/s, log)",
              ylabel="one-way latency (ms, log)")

    ax_fo.set_title("Who serves a citizen? (failover order)")
    ax_tab.set_axis_off()
    tab_txt = ax_tab.text(0, 1, "", family="monospace", fontsize=7.6, va="top", color=C.INK, transform=ax_tab.transAxes)

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)
    xs = np.linspace(0, 1, 21)

    def recompute(vals):
        v["i"], v["phase"], v["terrain"] = vals["i"], vals["phase"], vals["terrain"]
        v["inc"] = vals["inc"]
        e = st["e"] = evaluate(v)
        calm = M.evaluate_all(storm_for(0.0, PHASES[0]), v["terrain"])
        st["target"] = scores(e, calm)
        if st["radar"] is None:
            st["radar"] = {l: list(s) for l, s in st["target"].items()}
        # sweep
        ev = [evaluate(dict(v, i=x)) for x in xs]
        for l, ln in sw_lines.items():
            ln.set_data(xs, [q["reach"][l] for q in ev])
        sw_core.set_data(xs, [q["hybrid_core"] for q in ev])
        sw_sel.set_data(xs, [q["hybrid_sel"] for q in ev])
        sw_cur.set_xdata([v["i"]] * 2)
        rl_sc.set_sizes([40 + 600 * e["reach"][l] for l in C.ALL_LAYERS])
        # failover stacks
        ax_fo.cla()
        ax_fo.set_title("Who serves a citizen? (failover order)")
        rows = [("3 required layers", failover_shares(e["reach"], [C.L_MO, C.L_SA])),
                ("+ optional layers", failover_shares(e["reach"], [l for l in FAILOVER if l in e["sel_layers"]]))]
        segcol = {**C.COL, "Analog alert only": C.COL[C.L_AN], "No contact": "#3a3a37"}
        for y, (lab, shares) in enumerate(rows):
            left = 0
            for name, s in shares:
                if s <= 0.001:
                    continue
                ax_fo.barh(y, s, left=left, color=segcol.get(name, C.MUTED), height=0.55, edgecolor=C.PANEL, lw=2,
                           hatch="///" if name == "Analog alert only" else None, alpha=0.95)
                if s > 0.07:
                    short = C.SHORT.get(name, "alert" if "alert" in name else "none")
                    ax_fo.text(left + s / 2, y, f"{short}\n{s:.0%}", ha="center", va="center", fontsize=6.8,
                               color=C.BG if name != "No contact" else C.INK2, fontweight="bold")
                left += s
        ax_fo.set_yticks([0, 1], [r[0] for r in rows], fontsize=7.5)
        ax_fo.set(xlim=(0, 1), xlabel="share of citizens")
        ax_fo.invert_yaxis()
        ax_fo.grid(axis="y", visible=False)
        # table
        L = e["layers"]
        lines = [f"{'KEY NUMBERS':<24}{'value':>12}", "─" * 36,
                 f"{'FM output SNR':<24}{L[C.L_AN]['snr_fm']:>9.1f} dB",
                 f"{'Mobile edge Eb/N0':<24}{L[C.L_MO]['ebn0_edge']:>9.1f} dB",
                 f"{'Mobile call blocking':<24}{L[C.L_MO]['block']:>10.0%}",
                 f"{'Satellite rain fade':<24}{L[C.L_SA]['a_d']:>9.1f} dB",
                 f"{'Satellite margin':<24}{L[C.L_SA]['margin']:>+9.1f} dB",
                 f"{'UAV flying prob.':<24}{L[C.L_UAV]['fly']:>10.0%}",
                 f"{'UAV cell radius':<24}{L[C.L_UAV]['radius_m'] / 1e3:>9.2f} km",
                 f"{'Mesh connected':<24}{L[C.L_MESH]['conn']:>10.0%}",
                 f"{'Mesh ALOHA success':<24}{L[C.L_MESH]['p_aloha']:>10.0%}",
                 "─" * 36,
                 f"{'Hybrid (3 required)':<24}{e['hybrid_core']:>10.0%}",
                 f"{'Hybrid (+ optional)':<24}{e['hybrid_sel']:>10.0%}",
                 f"{'Alert reach (any)':<24}{e['alert']:>10.0%}"]
        tab_txt.set_text("\n".join(lines))
        s = storm_for(v["i"], v["phase"])
        ro.set_text(
            f"STORM  intensity {v['i']:.2f}  ({v['phase'].split(' (')[0]})\n"
            f"noise +{s['noise_rise']:.1f} dB · rain {s['rain']:.0f} mm/h\n"
            f"towers down {s['towers_down']:.0f} % · surge ×{s['surge']:.1f}\n"
            f"wind {s['wind']:.0f} m/s · {v['terrain'].split(' (')[0]}\n"
            f"HYBRID 3 required   {e['hybrid_core']:.0%}\n"
            f"HYBRID + optional   {e['hybrid_sel']:.0%}")
        ro.set_color(status_colour(e["hybrid_sel"]))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.40, 0.17), cols=1, rows=2)
    ctl.slider("i", "Storm intensity", 0, 1, 0.4, step=0.01, fmt="%.2f", color=C.COL["bad"])
    ctl.reset_button([0.12, 0.055, 0.2, 0.035])
    ctl.radio("phase", "Storm phase", PHASES, PHASES[0], [0.425, 0.035, 0.1, 0.15])
    ctl.radio("terrain", "Terrain", C.TERRAINS, C.TERRAINS[0], [0.53, 0.035, 0.105, 0.15])
    ctl.check("inc", "Optional layers in hybrid", ["UAV", "Mesh"], [True, True], [0.64, 0.035, 0.085, 0.15])
    recompute(ctl.values)

    def step(frame):
        if not player.running or st["e"] is None:
            return
        e = st["e"]
        tgt = [e["reach"][l] for l in C.ALL_LAYERS] + [e["hybrid_core"], e["hybrid_sel"]]
        keys = C.ALL_LAYERS + ["core", "sel"]
        for i, (k, t) in enumerate(zip(keys, tgt)):
            st["shown"][k] += (t - st["shown"][k]) * 0.18
            h = st["shown"][k]
            bars[i].set_height(h)
            bar_txt[i].set_position((i, h + 0.025))
            bar_txt[i].set_text(f"{h:.0%}")
        pulse = 0.75 + 0.25 * math.sin(frame * 0.2)
        bars[6].set_alpha(pulse)
        for l in C.ALL_LAYERS:
            cur, tg = st["radar"][l], st["target"][l]
            for j in range(len(cur)):
                cur[j] += (tg[j] - cur[j]) * 0.2
            rad_lines[l].set_data(np.r_[ang, ang[0]], np.r_[cur, cur[0]])

    return fig, step, ctl
