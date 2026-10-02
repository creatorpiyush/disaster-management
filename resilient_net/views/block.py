"""Block diagram: Tx -> channel -> Rx for every layer. Break a channel and watch the failover."""
import textwrap
from types import SimpleNamespace

import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from .. import config as C, ui
from ..widgets import Controls, Player, new_figure

TITLE = "Block diagram · transmitter → channel → receiver for every layer"

ROWS = [
    (C.L_AN, ["Voice / siren\nsource +\npre-emphasis", "AM / FM\nmodulator\n(μ, β = Δf/fm)", "RF power amp\n+ ridge-top\nVHF mast",
              "CHANNEL\nridge diffraction\n+ static (AWGN)", "RF front end\n+ limiter", "Discriminator /\nenvelope det.\n→ speaker"]),
    (C.L_MO, ["ADC + PCM\nfs ≥ 2W, n bits\nRb = n·fs", "Channel coding\n+ BPSK / QPSK\nmodulator", "Hill-top site\n(eNB / gNB)\nfibre on roads",
              "CHANNEL\nHata + terrain\n+ AWGN", "Phone RF +\ndemodulator", "Decoder + DAC\n→ voice / data"]),
    (C.L_SA, ["VSAT encoder\n+ QPSK mod.", "Up-converter\n+ HPA + dish\n(uplink fu)", "Satellite\ntransponder\nLNA → shift → HPA",
              "CHANNEL\nFSPL + rain fade\n+ skyline", "Dish + LNB\n(downlink fd)", "Demodulator\n+ decoder\n→ shelter / EOC"]),
    (C.L_UAV, ["Core link via\nsatellite\nbackhaul", "Small-cell\nbaseband\n(LTE)", "Drone-borne\nantenna\n(altitude h)",
               "CHANNEL\nair-to-ground\nover valleys", "Phone RF +\ndemodulator", "Decoder\n→ voice / data"]),
    (C.L_MESH, ["Phone / LoRa\nnode: SOS text", "CSS LoRa\nmodulator\n(SF, BW)", "Neighbour\nrelays\n(multi-hop)",
                "CHANNEL\nridge-blocked\nlinks + ALOHA", "Gateway at\nshelter", "Satellite uplink\n→ EOC"]),
]
FAIL_LABELS = ["FM mast off-air", "Fibre cut by landslides", "Satellite rain fade", "Drones grounded (rain)",
               "Mesh batteries flat"]


def print_calculations(v=None):
    ui.head("BLOCK DIAGRAM: SIGNAL CHAINS", ui.cyan)
    for (layer, blocks), lab in zip(ROWS, ["required", "required", "required", "optional", "optional"]):
        chain = "  →  ".join(b.replace("\n", " ") for b in blocks)
        print(f"  {ui.LAYER_TINT[layer](ui.bold(layer))} ({lab})")
        for line in textwrap.wrap(chain, ui.W - 6):
            print("      " + line)
    ui.note("Failover order for two-way traffic: Digital mobile network → UAV cell (optional) → Satellite "
            "backup → LoRa / D2D mesh (optional). The analog emergency radio broadcasts alerts throughout.")


YS = [54, 42, 30, 18, 6]  # row heights, same order as ROWS
BW, GAP, X0 = 10.4, 1.4, 19.0  # block width, gap between blocks, x of the first block
XS = [X0 + i * (BW + GAP) for i in range(6)]
FAILOVER = [1, 3, 2, 4]  # row indexes: mobile, UAV, satellite, mesh
SHORT_NAMES = {1: "Mobile", 3: "UAV", 2: "Satellite", 4: "Mesh"}


def _box(ax, x, y, w, h, text, fc, ec, ls="-", fs=7.0, tc=None, lw=1.3):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9", fc=fc, ec=ec, lw=lw, ls=ls)
    ax.add_patch(p)
    t = ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc or C.INK, linespacing=1.15)
    return p, t


def _arrow(ax, p1, p2, col=C.INK2, ls="-", lw=1.2, rad=0.0):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=10, color=col, lw=lw, ls=ls, alpha=1.0,
                        connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(a)
    return a


def _draw_ends(ax):
    """EOC on the left, citizens on the right, controller strip in between. Returns the controller marks."""
    _box(ax, 0.6, 3, 8.4, 56, "EMERGENCY\nOPERATIONS\nCENTRE\n(EOC)\n\nalerts\nvoice\ndata\nsensor feeds", "#24272b",
         C.INK2, fs=7.6)
    _box(ax, 10.6, 3, 6.2, 56, "", "#2b2124", C.COL["bad"], fs=7)
    marks = [ax.text(15.0, y + 1.6, "", ha="center", va="center", fontsize=11, color=C.COL["good"]) for y in YS]
    ax.text(12.4, 31, "HYBRID CONTROLLER  ·  priority routing & failover", ha="center", va="center", fontsize=7.5,
            color=C.COL["bad"], fontweight="bold", rotation=90)
    _box(ax, 90.2, 3, 9.2, 56, "CITIZENS\n&\nSHELTERS\n\nphones\nradios\nsirens\nVSATs", "#24272b", C.INK2, fs=7.6)
    _arrow(ax, (9.2, 31), (10.4, 31))
    return marks


def _draw_row(ax, layer, blocks, y):
    opt = layer in C.EXTRA_LAYERS
    col = C.COL[layer]
    ls = (0, (4, 2)) if opt else "-"
    art = SimpleNamespace(boxes=[], arrows=[], chan=None)
    art.label = ax.text(XS[0], y + 5.7, layer + ("   · optional extension" if opt else "   · required"),
                        fontsize=8.2, color=col, fontweight="bold")
    art.lamp, = ax.plot([17.6], [y + 1.6], "o", ms=9, color=C.COL["good"], mec=C.BG)
    for i, (bx, txt) in enumerate(zip(XS, blocks)):
        chan = txt.startswith("CHANNEL")
        p, t = _box(ax, bx, y - 2.2, BW, 7.4, txt, "#2e2f31" if chan else col, C.MUTED if chan else C.INK,
                    ls=ls, fs=7.0, tc=C.INK if chan else "#101114", lw=1.0)
        if chan:
            art.chan = (p, t)
        else:
            p.set_alpha(0.92)
        art.boxes.append((p, t))
        if i < 5:
            art.arrows.append(_arrow(ax, (bx + BW + 0.25, y + 1.6), (bx + BW + GAP - 0.25, y + 1.6)))
    art.arrows.append(_arrow(ax, (16.9, 31), (XS[0] - 0.3, y + 1.6), col=C.MUTED, lw=0.9))
    art.arrows.append(_arrow(ax, (XS[-1] + BW + 0.3, y + 1.6), (90.0, 31), col=C.MUTED, lw=0.9))
    art.x = ax.text(XS[3] + BW - 0.4, y + 4.6, "", ha="right", va="top", fontsize=15,
                    color=C.COL["bad"], fontweight="bold", zorder=9)
    sq = np.linspace(0, 1, 60)  # noise squiggle on the channel block
    ax.plot(XS[3] + 0.8 + sq * (BW - 1.6), y - 1.3 + 0.35 * np.random.default_rng(int(y)).standard_normal(60),
            color=C.MUTED, lw=0.6)
    art.track, = ax.plot([XS[0], XS[-1] + BW], [y - 3.0, y - 3.0], color=col, lw=0.8, alpha=0.35)
    return art


def _draw_links(ax):
    """Dashed arrows where one layer leans on another. Returns (optional-only arrows, optional-only labels)."""
    sat_y, mo_y, ua_y, me_y = YS[2], YS[1], YS[3], YS[4]
    sa_col, me_col = C.COL[C.L_SA], C.COL[C.L_MESH]
    _arrow(ax, (XS[2] + BW * 0.25, sat_y + 5.4), (XS[2] + BW * 0.25, mo_y - 2.4), col=sa_col, ls="--", lw=1.3)
    opt_arrows = [
        _arrow(ax, (XS[2] + BW * 0.75, sat_y - 2.4), (XS[0] + BW * 0.6, ua_y + 5.4), col=sa_col, ls="--", lw=1.3,
               rad=-0.15),
        _arrow(ax, (XS[5] + BW * 0.5, me_y + 5.4), (XS[4] + BW * 0.6, sat_y - 2.4), col=me_col, ls="--", lw=1.3,
               rad=0.2),
    ]
    lbl = dict(fontsize=6.6, va="center", bbox=dict(fc=C.BG, ec="none", pad=1.2), zorder=7)
    ax.text(XS[2] + BW * 0.25 + 0.5, (sat_y + mo_y) / 2 + 1.2, "satellite backhaul for portable cells",
            color=sa_col, **lbl)
    opt_labels = [
        ax.text(XS[1] + BW * 0.5, (sat_y + ua_y) / 2 + 1.6, "satellite backhaul for drones",
                color=sa_col, ha="center", **lbl),
        ax.text(XS[5] + BW * 0.5, me_y + 7.3, "mesh gateway uplink via satellite", color=me_col, ha="center", **lbl),
    ]
    return opt_arrows, opt_labels


def _refresh_row(art, packet, visible, failed):
    for p, t in art.boxes:
        p.set_visible(visible)
        t.set_visible(visible)
    for a in art.arrows:
        a.set_visible(visible)
    for a in (art.lamp, art.label, art.track, packet):
        a.set_visible(visible)
    art.lamp.set_color(C.COL["bad"] if failed else C.COL["good"])
    p, _ = art.chan
    p.set_facecolor("#4a2326" if failed else "#2e2f31")
    p.set_edgecolor(C.COL["bad"] if failed else C.MUTED)
    art.x.set_text("✕" if failed and visible else "")


def _order_text(failed, show_opt):
    seq = FAILOVER if show_opt else [1, 2]
    lines = ["FAILOVER ORDER"] + [f"{i + 1}. {SHORT_NAMES[r]:<10}{'DOWN' if failed[r] else 'ok'}"
                                  for i, r in enumerate(seq)]
    lines += ["", f"Alerts: analog radio {'DOWN' if failed[0] else 'ok'}"]
    return "\n".join(lines)


def _packet_x(r, phase, t, failed):
    pos = (phase + t * (1.6 if r == 0 else 1.0)) % 1
    xx = XS[0] + pos * (XS[-1] + BW - XS[0])
    if r == 4:
        xx = XS[-1] + BW - (xx - XS[0])  # mesh goes the other way, citizen -> EOC
    if failed:  # packets die at the broken channel
        stop = XS[3] + BW / 2
        xx = np.where(xx < stop, xx, np.nan) if r != 4 else np.where(xx > stop, xx, np.nan)
    return xx


def build():
    fig = new_figure(TITLE, "Tick a failure on the right to break a channel and see where the traffic goes. "
                            "Dashed = optional layers.", "BLOCK DIAGRAM",
                     size=(16.5, 9.6))
    ax = fig.add_axes([0.01, 0.06, 0.83, 0.85])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 63.5)
    ax.set_axis_off()
    st = dict(failed=[False] * 5, show_opt=True, t=0.0)

    ctrl_marks = _draw_ends(ax)
    row_art = [_draw_row(ax, layer, blocks, y) for (layer, blocks), y in zip(ROWS, YS)]
    opt_arrows, opt_labels = _draw_links(ax)
    status = ax.text(50, 62.3, "", ha="center", fontsize=10, fontweight="bold", color=C.COL["good"])
    rng = np.random.default_rng(0)
    packets = [ax.plot([], [], "o", ms=5.5, color=C.INK, mec=C.BG, zorder=8)[0] for _ in ROWS]
    phase = [rng.random(4) for _ in ROWS]
    highlight = FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.3,rounding_size=1.2", fc="none",
                               ec=C.COL["good"], lw=2.5, zorder=1)
    ax.add_patch(highlight)
    player = Player(fig)

    def on_change(vals):
        st["failed"] = [vals["fail"][k] for k in FAIL_LABELS]
        st["show_opt"] = vals["view"] == "Required + optional layers"
        refresh()

    ctl = Controls(fig, on_change, rect=(0.845, 0.06, 0.145, 0.0), cols=1, rows=1)
    ctl.check("fail", "Break a channel", FAIL_LABELS, [False] * 5, [0.848, 0.52, 0.142, 0.3])
    ctl.radio("view", "Show", ["Required + optional layers", "Required layers only"],
              "Required + optional layers", [0.848, 0.33, 0.142, 0.12])
    ctl.reset_button([0.848, 0.26, 0.142, 0.04], "Repair everything")
    order_txt = fig.text(0.848, 0.235, "", va="top", fontsize=7.6, color=C.INK2, family="monospace",
                         linespacing=1.5)

    def active_rows():
        return [r for r in (FAILOVER if st["show_opt"] else [1, 2]) if not st["failed"][r]]

    def refresh():
        failed, show_opt = st["failed"], st["show_opt"]
        for r, art in enumerate(row_art):
            _refresh_row(art, packets[r], show_opt or r < 3, failed[r])
        for a in opt_arrows + opt_labels:
            a.set_visible(show_opt)

        act = active_rows()
        alert_ok = not failed[0]
        if act:
            r = act[0]
            highlight.set_bounds(XS[0] - 1.2, YS[r] - 2.4, XS[-1] + BW - XS[0] + 2.4, 8.6)
            highlight.set_visible(True)
            status.set_text(f"Two-way traffic is carried by: {ROWS[r][0]}" +
                            ("" if alert_ok else "   ·   alerts: FM mast down!"))
            status.set_color(C.COL["good"] if r == 1 else C.COL["warn"])
        else:
            highlight.set_visible(False)
            status.set_text("No two-way path left. " + ("analog radio still broadcasts alerts" if alert_ok
                                                         else "COMPLETE BLACKOUT"))
            status.set_color(C.COL["warn"] if alert_ok else C.COL["bad"])
        order_txt.set_text(_order_text(failed, show_opt))

        for r, m in enumerate(ctrl_marks):
            on = bool(act) and act[0] == r
            if show_opt or r < 3:
                m.set_text("▶" if on else "◆" if r == 0 and alert_ok else "·")
            else:
                m.set_text("")
            m.set_color(C.COL["good"] if on else C.COL[C.L_AN] if r == 0 else C.MUTED)
        fig.canvas.draw_idle()

    refresh()

    def step(frame):
        if not player.running:
            return
        st["t"] += 0.012
        act = active_rows()
        for r, pk in enumerate(packets):
            xx = _packet_x(r, phase[r], st["t"], st["failed"][r])
            carrying = r == 0 or (act and act[0] == r)
            pk.set_data(xx, np.full(len(xx), YS[r] - 3.0))
            pk.set_markersize(6.5 if carrying else 4.0)
            pk.set_alpha(1.0 if carrying else 0.45)
            pk.set_color(C.INK if carrying else C.MUTED)
        highlight.set_linewidth(2 + 1.2 * abs(np.sin(frame * 0.15)))

    return fig, step, ctl
