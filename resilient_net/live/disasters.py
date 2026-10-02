"""Live: active disasters (GDACS, EONET) + earthquakes around Sikkim (USGS) with a G-R b-value fit."""
import datetime as dt
import math
from types import SimpleNamespace

import numpy as np

from .. import config as C, ui
from ..widgets import Controls, Player, new_figure, readout
from . import common

TITLE = "Live: Active disasters worldwide and earthquakes around Sikkim"
TYPES = {"EQ": ("Earthquake", "#e66767"), "TC": ("Tropical cyclone", "#3987e5"), "FL": ("Flood", "#199e70"),
         "VO": ("Volcano", "#d95926"), "WF": ("Wildfire", "#c98500"), "DR": ("Drought", "#9085e9")}
ALERT_SIZE = {"Green": 30, "Orange": 70, "Red": 130}
EONET_TYPE = {"severeStorms": "TC", "wildfires": "WF", "volcanoes": "VO", "floods": "FL", "earthquakes": "EQ",
              "drought": "DR"}
MC = 4.0  # magnitude of completeness of the USGS catalogue in this region
FILTERS = ["All types"] + [v[0] for v in TYPES.values()]


def load():
    g, e, q = common.get("gdacs"), common.get("eonet"), common.get("quakes")
    events = []
    for f in g.data.get("features", []):
        p, geo = f["properties"], f.get("geometry") or {}
        if geo.get("type") != "Point" or p.get("eventtype") not in TYPES:
            continue
        lon, lat = geo["coordinates"][:2]
        events.append(dict(src="GDACS", type=p["eventtype"], alert=p.get("alertlevel", "Green"),
                           name=p.get("name", p.get("eventname", "")), lat=lat, lon=lon,
                           date=str(p.get("fromdate", ""))[:10], country=p.get("country", "")))
    for ev in e.data.get("events", []):
        cat = ev["categories"][0]["id"] if ev.get("categories") else ""
        if cat not in EONET_TYPE or not ev.get("geometry"):
            continue
        last = ev["geometry"][-1]
        if last.get("type") != "Point":
            continue
        lon, lat = last["coordinates"][:2]
        events.append(dict(src="EONET", type=EONET_TYPE[cat], alert="Green", name=ev["title"], lat=lat, lon=lon,
                           date=str(last.get("date", ""))[:10], country=""))
    quakes = []
    for f in q.data.get("features", []):
        p = f["properties"]
        lon, lat, depth = f["geometry"]["coordinates"]
        if p.get("mag") is None:
            continue
        quakes.append(dict(mag=float(p["mag"]), lat=lat, lon=lon, depth=depth, place=p.get("place", ""),
                           t=dt.datetime.fromtimestamp(p["time"] / 1000, dt.timezone.utc)))
    for x in events + quakes:
        x["km"] = float(common.haversine_km(*common.GANGTOK, x["lat"], x["lon"]))
    return (g, e, q), events, quakes


def b_value(mags, mc):
    """Aki (1965) max-likelihood b-value, mags >= mc, 0.1 bins."""
    m = np.asarray(mags)
    m = m[m >= mc]
    if len(m) < 5:
        return float("nan"), len(m)
    return math.log10(math.e) / (m.mean() - (mc - 0.05)), len(m)


def print_calculations(res=None, events=None, quakes=None):
    if events is None:
        res, events, quakes = load()
    ui.head(TITLE.upper(), ui.cyan)
    ui.note(" · ".join(f"{r.provider}: {r.badge}" for r in res))
    red = [x for x in events if x["alert"] in ("Orange", "Red")]
    ui.kv("Active events listed (GDACS + EONET)", len(events))
    ui.kv("Orange / red GDACS alerts", len(red))
    for x in sorted(red, key=lambda x: x["alert"] == "Red", reverse=True)[:6]:
        print(f"      {x['alert']:<7}{TYPES[x['type']][0]:<17}{x['name'][:44]}")
    near = sorted(quakes, key=lambda x: x["km"])
    ui.sub("Earthquakes (M ≥ 3) within 500 km of Gangtok, last 90 days (USGS)")
    within = [x for x in quakes if x["km"] <= 500]
    for x in sorted(within, key=lambda x: -x["mag"])[:6]:
        print(f"      M{x['mag']:.1f}  {x['t']:%d %b %Y}  {x['km']:5.0f} km  {x['place'][:46]}")
    if near:
        ui.kv("Nearest event", f"M{near[0]['mag']:.1f}, {near[0]['km']:.0f} km away ({near[0]['place'][:40]})")
    b, n = b_value([x["mag"] for x in quakes], MC)
    ui.calc("Gutenberg–Richter b-value (Aki 1965)", "b = log10(e) / (M̄ − (Mc − ΔM/2))",
            f"{n} events with M ≥ {MC} in the 20–35° N, 78–98° E box", f"{b:.2f}",
            "(≈ 1 is typical; few events and an incomplete catalogue make this rough)")
    return events, quakes


def _setup_world(ax):
    ax.set(xlim=(-180, 180), ylim=(-60, 80), xticks=[], yticks=[],
           title="Active disasters worldwide (GDACS + NASA EONET)")
    ax.set_facecolor("#101820")
    common.draw_geojson(ax, "world_land.json")
    ax.set_aspect("equal")
    ax.plot(common.GANGTOK[1], common.GANGTOK[0], "*", ms=13, color=C.INK, mec=C.BG, zorder=8)
    by_type = {t: ax.scatter([], [], color=c, edgecolor=C.INK, lw=0.4, alpha=0.85, zorder=5, label=n)
               for t, (n, c) in TYPES.items()}
    ax.legend(loc="lower left", fontsize=6.8, ncol=6, markerscale=0.7, bbox_to_anchor=(0, -0.1))
    pulse = ax.scatter([], [], s=0, facecolor="none", edgecolor=C.COL["bad"], lw=1.5, zorder=4)
    return by_type, pulse


def _setup_region(ax):
    ax.set(xlim=(78, 98), ylim=(20, 35), title="Earthquakes around Sikkim (USGS, M ≥ 3)", xlabel="longitude °E",
           ylabel="latitude °N")
    ax.set_facecolor("#101820")
    common.draw_geojson(ax, "borders_south_asia.json", fc="#26292c", ec="#5a5d60", lw=0.7)
    ax.set_aspect("equal")
    ax.plot(common.GANGTOK[1], common.GANGTOK[0], "*", ms=15, color=C.INK, mec=C.BG, zorder=8)
    ax.text(common.GANGTOK[1] + 0.3, common.GANGTOK[0] + 0.3, "Gangtok", fontsize=7.5, color=C.INK, zorder=8)
    rg = SimpleNamespace()
    rg.ring, = ax.plot([], [], color=C.COL["warn"], lw=1.2, ls="--", zorder=6)
    rg.quakes = ax.scatter([], [], zorder=5, edgecolor=C.INK, lw=0.4)
    rg.pulse = ax.scatter([], [], s=0, facecolor="none", edgecolor=C.COL["warn"], lw=1.5, zorder=4)
    return rg


def _xy(items):
    return np.array([[x["lon"], x["lat"]] for x in items]) if items else np.zeros((0, 2))


def _draw_gutenberg_richter(ax, quakes):
    ax.cla()
    m = np.array([x["mag"] for x in quakes])
    grid = np.arange(3.0, max(m.max(), 3.1) + 0.1, 0.1)
    n = np.array([(m >= g).sum() for g in grid])
    ax.semilogy(grid, np.maximum(n, 0.8), "o", ms=4, color=C.INK)
    b, nb = b_value(m, MC)
    if np.isfinite(b):
        a = math.log10(max((m >= MC).sum(), 1)) + b * MC
        gf = grid[grid >= MC - 1e-9]
        ax.semilogy(gf, 10 ** (a - b * gf), color=C.COL["bad"], lw=2, label=f"log N = {a:.2f} − {b:.2f}·M  (b, Aki 1965)")
        ax.legend(fontsize=7, loc="upper right")
    ax.axvline(MC, color=C.MUTED, ls=":", lw=1)
    ax.text(MC + 0.02, 1.0, "Mc: smaller quakes are under-reported", fontsize=7, color=C.MUTED)
    ax.set(title="Gutenberg–Richter: how often each magnitude occurs", xlabel="magnitude M",
           ylabel="number of quakes ≥ M (log)")
    return b, nb


def _draw_timeline(ax, near, radius):
    ax.cla()
    if near:
        ax.vlines([x["t"] for x in near], 0, [x["mag"] for x in near], color=C.COL["warn"], lw=1.2)
        ax.scatter([x["t"] for x in near], [x["mag"] for x in near], s=[8 * 2 ** (x["mag"] - 2.5) for x in near],
                   color=C.COL["warn"], edgecolor=C.INK, lw=0.4, zorder=3)
    ax.set(title=f"Quakes within {radius:.0f} km of Gangtok", ylabel="magnitude",
           ylim=(2.5, max([x["mag"] for x in near], default=5) + 0.6))
    ax.tick_params(axis="x", labelsize=6.5)
    for lab in ax.get_xticklabels():
        lab.set_rotation(20)


def _readout_text(v, events, near, b, nb):
    red = sum(x["alert"] == "Red" for x in events)
    org = sum(x["alert"] == "Orange" for x in events)
    big = max(near, key=lambda x: x["mag"]) if near else None
    return (f"WORLD: {len(events)} active events\n"
            f"GDACS alerts: {red} red · {org} orange\n"
            f"quakes ≤ {v['radius']:.0f} km, {v['days']:.0f} d: {len(near)}\n"
            + (f"largest M{big['mag']:.1f} · {big['km']:.0f} km\n{big['place'][:30]}\n" if big else "none\n\n")
            + f"b-value {b:.2f} ({nb} events ≥ M{MC})")


def build():
    res, events, quakes = load()
    v = dict(radius=500.0, days=90.0, filt=FILTERS[0])
    fig = new_figure(TITLE, "What the emergency ops centre would be watching: disasters going on right now, "
                            "and how shaky the ground under Sikkim has been.", "LIVE DATA")
    common.badge(fig, list(res))
    gs = fig.add_gridspec(2, 3, left=0.035, right=0.985, top=0.9, bottom=0.27, wspace=0.25, hspace=0.38,
                          width_ratios=[1.25, 1.25, 1])
    ax_w = fig.add_subplot(gs[0, :2])
    ax_s = fig.add_subplot(gs[:, 2])
    ax_gr, ax_mt = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])

    ev_sc, pulse = _setup_world(ax_w)
    region = _setup_region(ax_s)
    th = np.linspace(0, 2 * np.pi, 200)
    ax_gr.set(title="Gutenberg–Richter: how often each magnitude occurs", xlabel="magnitude M",
              ylabel="number of quakes ≥ M (log)", yscale="log")
    ax_mt.set(title="Quakes within the radius over time", xlabel="date", ylabel="magnitude")
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.17]))
    player = Player(fig)
    st = {}

    def recompute(vals):
        v.update(vals)
        want = None if v["filt"] == FILTERS[0] else next(t for t, (n, _) in TYPES.items() if n == v["filt"])
        for t, sc in ev_sc.items():
            pts = [x for x in events if x["type"] == t and (want is None or t == want)]
            sc.set_offsets(_xy(pts))
            sc.set_sizes([ALERT_SIZE.get(x["alert"], 30) for x in pts])
        st["hot"] = _xy([x for x in events if x["alert"] in ("Orange", "Red") and (want is None or x["type"] == want)])

        now = dt.datetime.now(dt.timezone.utc)
        qs = [x for x in quakes if x["t"] >= now - dt.timedelta(days=v["days"])] or quakes
        region.quakes.set_offsets(_xy(qs))
        region.quakes.set_sizes([8 * 2 ** (x["mag"] - 2.5) for x in qs])
        region.quakes.set_array(np.array([(now - x["t"]).days for x in qs]))  # colour = age
        region.quakes.set_cmap("magma_r")
        region.quakes.set_clim(0, 90)
        dlat = v["radius"] / 111.0
        region.ring.set_data(common.GANGTOK[1] + dlat / math.cos(math.radians(27.33)) * np.cos(th),
                             common.GANGTOK[0] + dlat * np.sin(th))
        near = [x for x in qs if x["km"] <= v["radius"]]
        st["near"] = _xy(near)

        b, nb = _draw_gutenberg_richter(ax_gr, quakes)
        _draw_timeline(ax_mt, near, v["radius"])
        ro.set_text(_readout_text(v, events, near, b, nb))
        fig.canvas.draw_idle()

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.45, 0.17), cols=1, rows=2)
    ctl.slider("radius", "Radius around Gangtok (km)", 100, 1500, v["radius"], step=50, fmt="%.0f",
               color=C.COL["warn"])
    ctl.slider("days", "Days back", 7, 90, v["days"], step=1, fmt="%.0f")
    ctl.radio("filt", "World map shows", FILTERS, FILTERS[0], [0.475, 0.035, 0.13, 0.17])
    ctl.reset_button([0.615, 0.06, 0.11, 0.035], "Reset")
    recompute(ctl.values)

    def step(frame):
        if not player.running:
            return
        u = (frame % 30) / 30  # expanding rings around the serious ones
        pulse.set_offsets(st["hot"])
        pulse.set_sizes(np.full(len(st["hot"]), 60 + 700 * u))
        pulse.set_alpha(1 - u)
        region.pulse.set_offsets(st["near"])
        region.pulse.set_sizes(np.full(len(st["near"]), 30 + 500 * u))
        region.pulse.set_alpha(1 - u)

    return fig, step, ctl
