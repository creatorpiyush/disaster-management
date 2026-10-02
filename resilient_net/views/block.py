"""BLOCK DIAGRAM - complete transmitter → channel → receiver chain for every layer, animated.

Packets flow through each chain. Tick a failure box and that channel breaks: its packets stop, and the
hybrid controller fails over to the next working layer. Dashed arrows show how the layers support each
other (satellite backhaul for cells and drones, mesh gateways uplinking via satellite).
"""
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from .. import config as C, ui
from ..widgets import Controls, Player, new_figure

TITLE = "Block diagram · transmitter → channel → receiver for every layer"

ROWS = [
    (C.L_AN, ["Voice / siren\nsource +\npre-emphasis", "AM / FM\nmodulator\n(μ, β = Δf/fm)", "RF power amp\n+ VHF mast",
              "CHANNEL\npath loss + storm\nstatic (AWGN)", "RF front end\n+ limiter", "Discriminator /\nenvelope det.\n→ speaker"]),
    (C.L_MO, ["ADC + PCM\nfs ≥ 2W, n bits\nRb = n·fs", "Channel coding\n+ BPSK / QPSK\nmodulator", "Cell tower\n(eNB / gNB)\nErlang-B",
              "CHANNEL\nHata loss + fading\n+ AWGN", "Phone RF +\ndemodulator", "Decoder + DAC\n→ voice / data"]),
    (C.L_SA, ["VSAT encoder\n+ QPSK mod.", "Up-converter\n+ HPA + dish\n(uplink fu)", "Satellite\ntransponder\nLNA → shift → HPA",
              "CHANNEL\nFSPL + rain fade\n(up & down)", "Dish + LNB\n(downlink fd)", "Demodulator\n+ decoder\n→ shelter / EOC"]),
    (C.L_UAV, ["Core link via\nsatellite\nbackhaul", "Small-cell\nbaseband\n(LTE)", "Drone-borne\nantenna\n(altitude h)",
               "CHANNEL\nair-to-ground\nLoS / NLoS", "Phone RF +\ndemodulator", "Decoder\n→ voice / data"]),
    (C.L_MESH, ["Phone / LoRa\nnode: SOS text", "CSS LoRa\nmodulator\n(SF, BW)", "Neighbour\nrelays\n(multi-hop)",
                "CHANNEL\nground loss +\nALOHA collisions", "Gateway at\nshelter", "Satellite uplink\n→ EOC"]),
]
FAIL_LABELS = ["FM mast down", "Cell towers down", "Satellite rain fade", "Drones grounded (wind)",
               "Mesh batteries flat"]


def print_calculations(v=None):
    ui.head("BLOCK DIAGRAM — SIGNAL CHAINS", ui.cyan)
    for (layer, blocks), lab in zip(ROWS, ["required", "required", "required", "optional", "optional"]):
        chain = "  →  ".join(b.replace("\n", " ") for b in blocks)
        print(f"  {ui.LAYER_TINT[layer](ui.bold(layer))} ({lab})")
        for line in ui._wrap(chain, ui.W - 6):
            print("      " + line)
    ui.note("Failover order for two-way traffic: Digital mobile network → UAV cell (optional) → Satellite "
            "backup → LoRa / D2D mesh (optional). The analog emergency radio broadcasts alerts throughout.")


def build():
    fig = new_figure(TITLE, "Tick a failure on the right to break a channel and watch the hybrid controller "
                            "re-route traffic. Dashed outlines = optional extension layers.", "BLOCK DIAGRAM",
                     size=(16.5, 9.6))
    ax = fig.add_axes([0.01, 0.06, 0.83, 0.85])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 63.5)
    ax.set_axis_off()
    st = dict(failed=[False] * 5, show_opt=True, t=0.0)
    ys = [54, 42, 30, 18, 6]
    bw, gap, x0 = 10.4, 1.4, 19.0
    xs = [x0 + i * (bw + gap) for i in range(6)]

    def box(x, y, w, h, text, fc, ec, ls="-", fs=7.0, tc=None, lw=1.3):
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9", fc=fc, ec=ec, lw=lw, ls=ls)
        ax.add_patch(p)
        t = ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc or C.INK,
                    linespacing=1.15)
        return p, t

    def arrow(p1, p2, col=C.INK2, ls="-", lw=1.2, rad=0.0, alpha=1.0):
        a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=10, color=col, lw=lw, ls=ls, alpha=alpha,
                            connectionstyle=f"arc3,rad={rad}")
        ax.add_patch(a)
        return a

    box(0.6, 3, 8.4, 56, "EMERGENCY\nOPERATIONS\nCENTRE\n(EOC)\n\nalerts\nvoice\ndata\nsensor feeds", "#24272b",
        C.INK2, fs=7.6)
    ctrl, _ = box(10.6, 3, 6.2, 56, "", "#2b2124", C.COL["bad"], fs=7)
    ctrl_marks = [ax.text(15.0, y + 1.6, "", ha="center", va="center", fontsize=11, color=C.COL["good"])
                  for y in [54, 42, 30, 18, 6]]
    ax.text(12.4, 31, "HYBRID CONTROLLER  ·  priority routing & failover", ha="center", va="center", fontsize=7.5,
            color=C.COL["bad"], fontweight="bold", rotation=90)
    box(90.2, 3, 9.2, 56, "CITIZENS\n&\nSHELTERS\n\nphones\nradios\nsirens\nVSATs", "#24272b", C.INK2, fs=7.6)
    arrow((9.2, 31), (10.4, 31))

    row_art = []
    for (layer, blocks), y in zip(ROWS, ys):
        opt = layer in C.EXTRA_LAYERS
        col = C.COL[layer]
        ls = (0, (4, 2)) if opt else "-"
        art = dict(boxes=[], arrows=[], lamp=None, label=None, chan=None, x=None)
        lab = f"{layer}" + ("   · optional extension" if opt else "   · required")
        art["label"] = ax.text(xs[0], y + 5.7, lab, fontsize=8.2, color=col, fontweight="bold")
        art["lamp"], = ax.plot([17.6], [y + 1.6], "o", ms=9, color=C.COL["good"], mec=C.BG)
        for i, (bx, txt) in enumerate(zip(xs, blocks)):
            chan = txt.startswith("CHANNEL")
            fc = "#2e2f31" if chan else col
            p, t = box(bx, y - 2.2, bw, 7.4, txt, fc + ("" if chan else ""), C.MUTED if chan else C.INK,
                       ls=ls, fs=7.0, tc=C.INK if chan else "#101114", lw=1.0)
            if not chan:
                p.set_alpha(0.92)
            else:
                art["chan"] = (p, t)
            art["boxes"].append((p, t))
            if i < 5:
                art["arrows"].append(arrow((bx + bw + 0.25, y + 1.6), (bx + bw + gap - 0.25, y + 1.6)))
        art["arrows"].append(arrow((16.9, 31), (xs[0] - 0.3, y + 1.6), col=C.MUTED, lw=0.9))
        art["arrows"].append(arrow((xs[-1] + bw + 0.3, y + 1.6), (90.0, 31), col=C.MUTED, lw=0.9))
        art["x"] = ax.text(xs[3] + bw - 0.4, y + 4.6, "", ha="right", va="top", fontsize=15,
                           color=C.COL["bad"], fontweight="bold", zorder=9)
        # noise squiggle on the channel block
        sq = np.linspace(0, 1, 60)
        ax.plot(xs[3] + 0.8 + sq * (bw - 1.6), y - 1.3 + 0.35 * np.random.default_rng(int(y)).standard_normal(60),
                color=C.MUTED, lw=0.6)
        art["track"], = ax.plot([xs[0], xs[-1] + bw], [y - 3.0, y - 3.0], color=col, lw=0.8, alpha=0.35)
        row_art.append(art)

    # interconnections between layers ------------------------------------------------------------
    sat_y, mo_y, ua_y, me_y = ys[2], ys[1], ys[3], ys[4]
    links = [
        arrow((xs[2] + bw * 0.25, sat_y + 5.4), (xs[2] + bw * 0.25, mo_y - 2.4), col=C.COL[C.L_SA], ls="--", lw=1.3),
        arrow((xs[2] + bw * 0.75, sat_y - 2.4), (xs[0] + bw * 0.6, ua_y + 5.4), col=C.COL[C.L_SA], ls="--", lw=1.3,
              rad=-0.15),
        arrow((xs[5] + bw * 0.5, me_y + 5.4), (xs[4] + bw * 0.6, sat_y - 2.4), col=C.COL[C.L_MESH], ls="--", lw=1.3,
              rad=0.2),
    ]
    lbl = dict(fontsize=6.6, va="center", bbox=dict(fc=C.BG, ec="none", pad=1.2), zorder=7)
    ax.text(xs[2] + bw * 0.25 + 0.5, (sat_y + mo_y) / 2 + 1.2, "satellite backhaul for portable cells",
            color=C.COL[C.L_SA], **lbl)
    lk2 = ax.text(xs[1] + bw * 0.5, (sat_y + ua_y) / 2 + 1.6, "satellite backhaul for drones",
                  color=C.COL[C.L_SA], ha="center", **lbl)
    lk3 = ax.text(xs[5] + bw * 0.5, me_y + 7.3, "mesh gateway uplink via satellite",
                  color=C.COL[C.L_MESH], ha="center", **lbl)

    status = ax.text(50, 62.3, "", ha="center", fontsize=10, fontweight="bold", color=C.COL["good"])
    rng = np.random.default_rng(0)
    packets = [ax.plot([], [], "o", ms=5.5, color=C.INK, mec=C.BG, zorder=8)[0] for _ in ROWS]
    phase = [rng.random(4) for _ in ROWS]
    highlight = FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.3,rounding_size=1.2", fc="none",
                               ec=C.COL["good"], lw=2.5, zorder=1)
    ax.add_patch(highlight)

    # right-hand control panel --------------------------------------------------------------------
    player = Player(fig)

    def on_change(vals):
        st["failed"] = [vals["fail"][k] for k in FAIL_LABELS]
        st["show_opt"] = vals["view"] == "Required + optional layers"
        refresh()

    ctl = Controls(fig, on_change, rect=(0.845, 0.06, 0.145, 0.0), cols=1, rows=1)
    ctl.check("fail", "Break a channel", FAIL_LABELS, [False] * 5, [0.848, 0.52, 0.142, 0.3])
    ctl.radio("view", "Show", ["Required + optional layers", "Required layers only"],
              "Required + optional layers", [0.848, 0.33, 0.142, 0.12])
    ctl.reset_button([0.848, 0.26, 0.142, 0.04], "↺  Repair everything")
    order_txt = fig.text(0.848, 0.235, "", va="top", fontsize=7.6, color=C.INK2, family="monospace",
                         linespacing=1.5)

    def active_rows():
        rows = [1, 3, 2, 4] if st["show_opt"] else [1, 2]
        return [r for r in rows if not st["failed"][r]]

    def refresh():
        for r, art in enumerate(row_art):
            vis = st["show_opt"] or r < 3
            for p, t in art["boxes"]:
                p.set_visible(vis)
                t.set_visible(vis)
            for a in art["arrows"]:
                a.set_visible(vis)
            art["lamp"].set_visible(vis)
            art["label"].set_visible(vis)
            art["track"].set_visible(vis)
            packets[r].set_visible(vis)
            bad = st["failed"][r]
            art["lamp"].set_color(C.COL["bad"] if bad else C.COL["good"])
            p, t = art["chan"]
            p.set_facecolor("#4a2326" if bad else "#2e2f31")
            p.set_edgecolor(C.COL["bad"] if bad else C.MUTED)
            art["x"].set_text("✕" if bad and vis else "")
        for a in links[1:]:
            a.set_visible(st["show_opt"])
        lk2.set_visible(st["show_opt"])
        lk3.set_visible(st["show_opt"])
        act = active_rows()
        alert_ok = not st["failed"][0]
        if act:
            r = act[0]
            highlight.set_bounds(xs[0] - 1.2, ys[r] - 2.4, xs[-1] + bw - xs[0] + 2.4, 8.6)
            highlight.set_visible(True)
            status.set_text(f"Two-way traffic is carried by: {ROWS[r][0]}" +
                            ("" if alert_ok else "   ·   alerts: FM mast down!"))
            status.set_color(C.COL["good"] if r == 1 else C.COL["warn"])
        else:
            highlight.set_visible(False)
            status.set_text("No two-way path left — " + ("analog radio still broadcasts alerts" if alert_ok
                                                         else "COMPLETE BLACKOUT"))
            status.set_color(C.COL["warn"] if alert_ok else C.COL["bad"])
        names = {1: "Mobile", 3: "UAV", 2: "Satellite", 4: "Mesh"}
        seq = [1, 3, 2, 4] if st["show_opt"] else [1, 2]
        lines = ["FAILOVER ORDER"] + [f"{i + 1}. {names[r]:<10}{'DOWN' if st['failed'][r] else 'ok'}"
                                      for i, r in enumerate(seq)]
        lines += ["", f"Alerts: analog radio {'DOWN' if st['failed'][0] else 'ok'}"]
        order_txt.set_text("\n".join(lines))
        for r, m in enumerate(ctrl_marks):
            vis = st["show_opt"] or r < 3
            on = bool(act) and act[0] == r
            m.set_text(("▶" if on else "◆" if r == 0 and not st["failed"][0] else "·") if vis else "")
            m.set_color(C.COL["good"] if on else C.COL[C.L_AN] if r == 0 else C.MUTED)
        fig.canvas.draw_idle()

    refresh()

    def step(frame):
        if not player.running:
            return
        st["t"] += 0.012
        act = active_rows()
        for r, (art, pk) in enumerate(zip(row_art, packets)):
            y = ys[r] - 3.0
            pos = (phase[r] + st["t"] * (1.6 if r == 0 else 1.0)) % 1
            xx = xs[0] + pos * (xs[-1] + bw - xs[0])
            if r == 4:
                xx = xs[-1] + bw - (xx - xs[0])          # mesh carries citizen → EOC traffic (reverse)
            if st["failed"][r]:
                stop = xs[3] + bw / 2
                xx = np.where(xx < stop, xx, np.nan) if r != 4 else np.where(xx > stop, xx, np.nan)
            carrying = r == 0 or (act and act[0] == r)
            pk.set_data(xx, np.full(len(xx), y))
            pk.set_markersize(6.5 if carrying else 4.0)
            pk.set_alpha(1.0 if carrying else 0.45)
            pk.set_color(C.INK if carrying else C.MUTED)
        lw = 2 + 1.2 * abs(np.sin(frame * 0.15))
        highlight.set_linewidth(lw)

    return fig, step, ctl
