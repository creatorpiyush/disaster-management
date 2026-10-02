"""Live: Gangtok weather (Open-Meteo, -72 h .. +72 h) pushed through the layer models."""
import datetime as dt

import numpy as np

from .. import config as C, models as M, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour
from . import common

TITLE = "Live: Weather over Gangtok and its effect on every layer"
BAND_COL = {"C": C.COL[C.L_MO], "Ku": C.COL[C.L_SA], "Ka": C.COL[C.L_UAV]}
PERIODS = ["Live: now ± 3 days", "Replay: Oct 2023 GLOF week", "Replay: wettest monsoon days"]
SOURCE = {PERIODS[0]: "weather", PERIODS[1]: "wx_2023", PERIODS[2]: "wx_monsoon"}


def centre(period, w):
    if period == PERIODS[0]:
        return dt.datetime.strptime(w["current"]["time"][:13] + ":00", "%Y-%m-%dT%H:%M")
    if period == PERIODS[1]:
        return dt.datetime(2023, 10, 4, 0, 0)  # South Lhonak GLOF, night of 3-4 Oct 2023
    t = dt.datetime.strptime(w["hourly"]["time"][0], "%Y-%m-%dT%H:%M")
    return t + dt.timedelta(days=3)


def caine_index(rain):
    """Caine (1980): worst ratio of mean rain over the last D hours to 14.82 * D^-0.39, D = 1..72 h."""
    cs = np.r_[0, np.cumsum(rain)]
    out = np.zeros(len(rain))
    for k in range(len(rain)):
        D = np.arange(1, min(k + 1, 72) + 1)
        mean = (cs[k + 1] - cs[k + 1 - D]) / D
        out[k] = np.max(mean / (14.82 * D ** -0.39))
    return out


def series(w, factor=2.0, period=PERIODS[0]):
    h = w["hourly"]
    t = [dt.datetime.strptime(x, "%Y-%m-%dT%H:%M") for x in h["time"]]
    now = centre(period, w)
    rain = np.nan_to_num(np.array(h["precipitation"], dtype=float))
    gust = np.nan_to_num(np.array(h["wind_gusts_10m"], dtype=float))
    hrs = np.array([(x - now).total_seconds() / 3600 for x in t])
    E = caine_index(rain)
    peak = rain * factor  # convective rain peaks well above the hourly mean
    margin = {b: np.array([M.satellite_layer(**{**C.SAT, "band": b, "rain": r})["margin"] for r in peak])
              for b in BAND_COL}
    fly = np.array([M.uav_layer(**{**C.UAV, "wind": g, "rain": r})["fly"] for g, r in zip(gust, peak)])
    reach = {l: [] for l in C.ALL_LAYERS}
    core, ext = [], []
    for r, g, e in zip(peak, gust, E):
        i_ls = float(np.clip((e - 0.5) / 2.5, 0, 1))  # guess: index 1.5 ~ the default scenario (i = 0.4)
        s = dict(M.storm_from_intensity(i_ls), rain=r, wind=g)
        ev = M.evaluate_all(s)
        for l in C.ALL_LAYERS:
            reach[l].append(ev["reach"][l])
        core.append(ev["hybrid_core"])
        ext.append(ev["hybrid_ext"])
    return dict(t=t, hrs=hrs, rain=rain, peak=peak, gust=gust, E=E, margin=margin, fly=fly,
                reach={k: np.array(v) for k, v in reach.items()}, core=np.array(core), ext=np.array(ext),
                now=now, k_now=int(np.argmin(np.abs(hrs))))


def print_calculations(res=None, s=None):
    res = res or common.get("weather")
    s = s or series(res.data)
    _print_live(res, s)
    ui.sub("Replays of real past weather (Open-Meteo archive, ERA5 reanalysis)")
    for per in PERIODS[1:]:
        r = common.get(SOURCE[per])
        q = series(r.data, 2.0, per)
        ui.kv(f"{per.split(': ')[1]} ({q['t'][0]:%d %b %Y} → {q['t'][-1]:%d %b})",
              f"{q['rain'].sum():.0f} mm · peak {q['rain'].max():.1f} mm/h · landslide index max {q['E'].max():.2f}")
    ui.note("Reanalysis smooths out short bursts so the real peaks were higher than this. Interesting one: "
            "the Oct 2023 GLOF came with only moderate rain at Gangtok, so local weather alone wouldn't "
            "have warned anyone.")
    return s


def _print_live(res, s):
    k = s["k_now"]
    fut = slice(k, None)
    kf = k + int(np.argmax(s["E"][fut]))
    ui.head(TITLE.upper(), ui.cyan)
    ui.note(f"Source: Open-Meteo forecast API for Gangtok (27.33° N, 88.61° E, 1650 m) · {res.badge}.")
    cur = res.data.get("current", {})
    ui.kv("Now: rain / gusts / temperature", f"{cur.get('precipitation', 0)} mm · {cur.get('wind_gusts_10m', 0)} m/s · "
          f"{cur.get('temperature_2m', '?')} °C")
    ui.kv("Rain in the last 72 h", f"{s['rain'][:k + 1][-72:].sum():.0f} mm")
    ui.kv("Rain forecast for the next 72 h", f"{s['rain'][k + 1:].sum():.0f} mm")
    ui.calc("Landslide index now (Caine 1980)", "max over D of  (ΣR/D) / (14.82·D^−0.39)", "D = 1 … 72 h",
            f"{s['E'][k]:.2f}", "(> 1 means the rainfall threshold for shallow landslides is exceeded)")
    ui.calc("Highest index in the forecast", "", f"at {s['t'][kf]:%d %b %H:%M} IST", f"{s['E'][kf]:.2f}")
    kr = k + int(np.argmax(s["peak"][fut]))
    sat = M.satellite_layer(**{**C.SAT, "rain": s["peak"][kr]})
    ui.calc("Worst forecast hour for the Ku-band VSAT", "A = γ·Ls·r,  γ = k·R^α  (R = hourly rain × peak factor 2)",
            f"R = {s['peak'][kr]:.1f} mm/h at {s['t'][kr]:%d %b %H:%M}", f"fade {sat['a_d']:.1f} dB → margin "
            f"{sat['margin']:+.1f} dB")
    ui.kv("Drones able to fly now", f"{s['fly'][k]:.0%}")
    ui.kv("Hybrid two-way reach now (3 required → + optional)", f"{s['core'][k]:.0%} → {s['ext'][k]:.0%}")
    return s


def _clear(axes, keep):
    # wipe everything except the cursor + the dotted "now" line (the first two lines on each axes)
    for a in axes:
        for art in list(a.lines[2:]) + list(a.collections) + list(a.patches) + list(a.texts):
            if art not in keep:
                art.remove()


def _draw_rain(ax, s, v):
    x = s["hrs"]
    past = x <= 0
    ax.bar(x[past], s["rain"][past], width=0.9, color=C.COL[C.L_MO])
    ax.bar(x[~past], s["rain"][~past], width=0.9, color=C.COL[C.L_MO], alpha=0.45)
    ax.set(title="Rain over Gangtok (mm per hour)", ylabel="mm/h", ylim=(0, max(5, s["rain"].max() * 1.25)))
    live = v["period"] == PERIODS[0]
    ax.text(-71, ax.get_ylim()[1] * 0.9, "observed" if live else f"{s['now']:%d %b %Y %H:%M} IST = 0",
            fontsize=7, color=C.INK2)
    if live:
        ax.text(2, ax.get_ylim()[1] * 0.9, "forecast", fontsize=7, color=C.INK2)


def _draw_landslide(ax, s):
    x = s["hrs"]
    ax.plot(x, s["E"], color=C.COL["bad"], lw=2)
    ax.axhline(1, color=C.INK2, ls="--", lw=1)
    ax.text(-71, 1.05, "Caine threshold", fontsize=7, color=C.INK2)
    ax.fill_between(x, 1, s["E"], where=s["E"] > 1, color=C.COL["bad"], alpha=0.25)
    ax.set(title="Landslide index (mean rain ÷ Caine threshold)", ylabel="index",
           ylim=(0, max(1.6, s["E"].max() * 1.2)))


def _draw_margin(ax, s, v):
    for b, col in BAND_COL.items():
        ax.plot(s["hrs"], s["margin"][b], color=col, lw=1.8, label=f"{b}-band")
    ax.axhline(0, color=C.COL["bad"], ls="--", lw=1)
    ax.set(title=f"VSAT link margin (rain × {v['factor']:.1f} peak factor)", ylabel="dB")
    ax.legend(fontsize=7, loc="lower left")


def _draw_reach(ax, s):
    x = s["hrs"]
    for l in C.ALL_LAYERS:
        ax.plot(x, s["reach"][l], color=C.COL[l], lw=1.3, ls="-" if l in C.CORE_LAYERS else "--", label=C.SHORT[l])
    ax.plot(x, s["core"], color="#bdbcb3", lw=3, label="hybrid, 3 required")
    ax.plot(x, s["ext"], color=C.INK, lw=3, label="hybrid, + optional")
    ax.set(title="Citizens reached by each layer, hour by hour (Gangtok district)", ylabel="share",
           ylim=(0, 1.05))
    ax.legend(fontsize=7, ncol=7, loc="lower center")


def _readout_text(s, k, period):
    x = s["hrs"][k]
    tag = ("observed" if x <= 0 else "forecast") if period == PERIODS[0] else "archive"
    return (f"{s['t'][k]:%a %d %b  %H:%M} IST ({tag})\n"
            f"rain {s['rain'][k]:.1f} mm/h · gusts {s['gust'][k]:.0f} m/s\n"
            f"landslide index {s['E'][k]:.2f} {'⚠ above threshold' if s['E'][k] > 1 else ''}\n"
            f"Ku margin {s['margin']['Ku'][k]:+.1f} dB · drones {s['fly'][k]:.0%}\n"
            f"hybrid 3 required {s['core'][k]:.0%}\n"
            f"hybrid + optional {s['ext'][k]:.0%}")


def build():
    res = common.get("weather")
    v = dict(hour=0.0, factor=2.0, period=PERIODS[0])
    st = dict(s=series(res.data, v["factor"]), cur=0.0, res=res)
    fig = new_figure(TITLE, "Hourly rain + wind from Open-Meteo pushed through the same models as everything else "
                            "(landslides, rain fade, drone limits, hybrid reach)",
                     "LIVE DATA")
    common.badge(fig, [res, common.get(SOURCE[PERIODS[1]])])
    gs = fig.add_gridspec(2, 3, left=0.045, right=0.985, top=0.9, bottom=0.27, wspace=0.26, hspace=0.42)
    ax_r, ax_e, ax_m = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ax_u, ax_h = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1:])
    axes = (ax_r, ax_e, ax_m, ax_u, ax_h)
    cursors = [a.axvline(0, color=C.COL["warn"], lw=1.4, zorder=6) for a in axes]
    for a in axes:
        a.axvline(0, color=C.INK2, lw=0.8, ls=":")
        a.axvspan(0, 80, color="#ffffff", alpha=0.025)  # faint shading = forecast side
        a.set_xlim(-73, 73)
        a.set_xlabel("hours from the selected moment")
    dots = {}

    def recompute(vals):
        if vals["factor"] != v["factor"] or vals["period"] != v["period"]:
            st["res"] = common.get(SOURCE[vals["period"]])
            st["s"] = series(st["res"].data, vals["factor"], vals["period"])
        v.update(vals)
        st["cur"] = v["hour"]
        s = st["s"]
        _clear(axes, cursors)
        _draw_rain(ax_r, s, v)
        _draw_landslide(ax_e, s)
        _draw_margin(ax_m, s, v)
        ax_u.plot(s["hrs"], s["fly"], color=C.COL[C.L_UAV], lw=2)
        ax_u.set(title="Can a drone fly? (gusts and rain)", ylabel="probability", ylim=(-0.03, 1.05))
        _draw_reach(ax_h, s)
        for key, a in (("E", ax_e), ("fly", ax_u), ("ext", ax_h), ("Ku", ax_m)):
            dots[key], = a.plot([], [], "o", ms=11, mfc="none", mec=C.INK, mew=2, zorder=7)
        draw()
        fig.canvas.draw_idle()

    def draw():
        s = st["s"]
        k = int(np.argmin(np.abs(s["hrs"] - st["cur"])))
        x = s["hrs"][k]
        for c in cursors:
            c.set_xdata([x, x])
        dots["E"].set_data([x], [s["E"][k]])
        dots["fly"].set_data([x], [s["fly"][k]])
        dots["ext"].set_data([x], [s["ext"][k]])
        dots["Ku"].set_data([x], [s["margin"]["Ku"][k]])
        ro.set_text(_readout_text(s, k, v["period"]))
        ro.set_color(status_colour(s["ext"][k]))

    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)
    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.55, 0.17), cols=1, rows=2)
    ctl.slider("hour", "Hour (0 = now)", -72, 72, 0.0, step=1, fmt="%+.0f h", color=C.COL["warn"])
    ctl.slider("factor", "Peak / hourly rain factor", 1, 4, 2.0, step=0.1, fmt="%.1f", color=C.COL["bad"])
    ctl.radio("period", "Period", PERIODS, PERIODS[0], [0.575, 0.075, 0.15, 0.13])
    ctl.reset_button([0.36, 0.05, 0.1, 0.035], "Back to now")
    ctl.button([0.465, 0.05, 0.1, 0.035], "▶  Sweep", player.toggle)
    player.running = False  # starts paused, the Sweep button plays through the 144 h
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        st["cur"] = (st["cur"] + 72 + 0.5) % 144 - 72
        draw()

    return fig, step, ctl
