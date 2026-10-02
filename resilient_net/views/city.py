"""Live disaster sim over Gangtok: cloudburst -> landslides -> GLOF, and which layer still reaches each citizen."""
import math
from types import SimpleNamespace

import matplotlib
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle

from .. import config as C, models as M, terrain, ui
from ..widgets import Controls, Player, new_figure, readout, status_colour

TITLE = "Live disaster simulation: cloudburst, landslides and a glacial-lake flood over Gangtok"
HOURS = 96.0
CELL_T, CELL_W = 22.0, 6.0  # cloudburst peak time and duration scale (h)
CELL_FROM, CELL_TO = np.array([-15.0, -13.0]), np.array([7.0, 9.0])
CELL_R = 5.0  # km, radius of the convective cell
GLOF_T, GLOF_SPEED, GLOF_HOURS = 44.0, 15.0, 16.0  # outburst time (h), wave speed (km/h), duration (h)
SLIDE_SLOPE = 30.0  # degrees: steeper ground can fail
SERVE_ORDER = [C.L_MO, C.L_UAV, C.L_SA, C.L_MESH]
NONE_C = "#3d3d3a"
SLIDE_C = "#b07a3c"


def _fibre_routes(nodes, edges, core, site_nodes):
    # fibre runs along the roads, so: shortest road route exchange -> each site (None = cut off)
    import heapq
    adj = [[] for _ in nodes]
    for k, (a, b) in enumerate(edges):
        w = float(np.hypot(*(nodes[a] - nodes[b])))
        adj[a].append((b, w, k))
        adj[b].append((a, w, k))
    dist = np.full(len(nodes), np.inf)
    parent = np.full(len(nodes), -1)
    dist[core] = 0
    pq = [(0.0, core)]
    while pq:
        du, u = heapq.heappop(pq)
        if du > dist[u]:
            continue
        for w_, l, k in adj[u]:
            if du + l < dist[w_]:
                dist[w_], parent[w_] = du + l, k
                heapq.heappush(pq, (du + l, w_))
    routes = []
    for n in site_nodes:
        if not np.isfinite(dist[n]):
            routes.append(None)
            continue
        path, u = [], n
        while u != core:
            k = parent[u]
            path.append(k)
            a, b = edges[k]
            u = a if b == u else b
        routes.append(np.array(path, dtype=int))
    return routes


def print_calculations(v=None):
    ui.head(TITLE.upper(), ui.cyan)
    ui.note("How it works: each frame is 15 min (at speed 1). The rain cell moves SW to NE and peaks around "
            "t = 22 h. On slopes over 30 deg we compare the mean rain so far against the Caine (1980) "
            "threshold I = 14.82 D^-0.39 mm/h, and once it's exceeded slides start (more often the further "
            "over and the steeper). A slide cuts roads within 250 m.")
    ui.note("Fibre and grid power run along the roads, so if a site's only fibre route back to the Gangtok "
            "exchange gets cut it loses both (unless it has a microwave hop to the ridge) and runs on "
            "battery till it's flat.")
    ui.note("At t = 44 h the GLOF enters the Teesta from the north at 15 km/h and floods anything less than "
            "30 m (slider) above the riverbed. Each citizen uses the first layer that works for them: "
            "mobile, then UAV, satellite shelter, mesh, and finally analog alert only.")
    ui.calc("Caine threshold after 24 h of rain", "I = 14.82 · D^−0.39", "D = 24 h",
            f"{14.82 * 24 ** -0.39:.2f}", "mm/h mean intensity")


def cell_centre(t):
    # the rain cell drifts SW -> NE across the map over ~28 h
    u = np.clip((t - (CELL_T - 14)) / 28, 0, 1)
    return CELL_FROM + (CELL_TO - CELL_FROM) * u


def cell_env(t):
    return math.exp(-((t - CELL_T) / CELL_W) ** 2)


def noise_rise(t):
    return 2 + 8 * cell_env(t)  # lightning static


def surge(t):
    return 1 + 2.5 * math.exp(-((t - 34) / 26) ** 2)


class CitySim:
    """All the simulation state + rules. Knows nothing about matplotlib except returning mesh segments."""

    def __init__(self, v, rng):
        self.v, self.rng = v, rng  # v = live slider values, shared with the figure
        S = self.S = terrain.scenario()
        T = self.T = S["T"]
        self.cit, self.sites, self.shelters = S["cit"], S["sites"], S["shelters"]
        cit, sites, shelters = self.cit, self.sites, self.shelters
        self.n_c, self.n_s = len(cit), len(sites)
        self.L = terrain.link_tables()
        hata = np.array([[float(M.hata_urban(max(d, 0.05))) for d in row] for row in self.L["site_d"]])
        self.site_pl = hata + self.L["site_loss"] + 12.0  # + building penetration
        self.nodes, self.edges, self.mid = T.road_graph()
        mid = self.mid
        self.is_nh10 = np.array([r == "NH10" for r in T.edge_ref])
        self.shelter_alt = T.elev(shelters[:, 0], shelters[:, 1])
        self.shelter_hand = T.hand_at(shelters[:, 0], shelters[:, 1])
        self.site_hand = T.hand_at(sites[:, 0], sites[:, 1])
        self.edge_hand = T.hand_at(mid[:, 0], mid[:, 1])
        self.mast_node = T.nearest_node(*S["mast"])
        # each site's fibre + power follow ONE road route back to the Gangtok exchange
        self.route = _fibre_routes(self.nodes, self.edges, S["core"], S["site_node"])
        # sites not joined to the Gangtok road network get microwave + local power instead
        self.isolated = np.array([r is None for r in self.route])
        self.microwave = S["microwave"] | self.isolated

        self.X, self.Y = T.mesh()
        slope = T.slope_deg()
        cand = slope > SLIDE_SLOPE
        self.cx, self.cy, self.cs = self.X[cand], self.Y[cand], slope[cand]
        # road cuts destabilise the hillside, so slopes next to a road fail a lot more often
        near_road = np.array([np.hypot(mid[::6, 0] - a, mid[::6, 1] - b).min() < 0.4 for a, b in zip(self.cx, self.cy)])
        self.road_factor = np.where(near_road, 6.0, 1.0)
        self._setup_flood_geometry()
        self._setup_mesh(rng)
        self.u_block = rng.random(self.n_c)  # each citizen's "dice roll" against call blocking
        self.uav_base = shelters[0].copy()  # drones fly from the Gangtok shelter
        self.n_uav = C.UAV["n_uav"]
        self.zone_valley = S["zone"] == terrain.ZONES[3]
        self.st = {}

    def _setup_flood_geometry(self):
        # the wave travels N -> S, so for everything we need "y of the nearest bit of Teesta"
        T, X, Y, mid = self.T, self.X, self.Y, self.mid
        self.hand_g, tpts, _ = T.teesta()
        near = np.argmin(np.hypot(X.ravel()[:, None] - tpts[None, :, 0], Y.ravel()[:, None] - tpts[None, :, 1]),
                         axis=1).reshape(X.shape)
        self.y_river = tpts[near, 1]
        self.y_top = tpts[:, 1].max()

        def river_y_at(x, y):
            return tpts[np.argmin(np.hypot(tpts[:, 0] - x, tpts[:, 1] - y)), 1]

        self.shelter_ry = np.array([river_y_at(*p) for p in self.shelters])
        self.site_ry = np.array([river_y_at(*p) for p in self.sites])
        self.edge_ry = tpts[np.argmin(np.hypot(mid[:, None, 0] - tpts[None, ::4, 0],
                                               mid[:, None, 1] - tpts[None, ::4, 1]), axis=1) * 4, 1]
        self.cit_ry = np.array([river_y_at(*p) for p in self.cit])

    def _setup_mesh(self, rng):
        T, cit, shelters, n_c = self.T, self.cit, self.shelters, self.n_c
        self.has_dev = rng.random(n_c) < 0.7
        self.batt_dies = rng.uniform(30, 160, n_c)  # hours until each phone is flat
        ii, jj = np.nonzero(np.triu(np.hypot(cit[:, None, 0] - cit[None, :, 0],
                                             cit[:, None, 1] - cit[None, :, 1]) <= 3, 1))
        clear = T.line_of_sight(cit[ii], cit[jj], 1.5, 1.5)
        self.los = np.zeros((n_c, n_c), bool)
        self.los[ii[clear], jj[clear]] = True
        self.los |= self.los.T
        self.sh_los = np.zeros((n_c, len(shelters)), bool)
        for k, sp in enumerate(shelters):
            m = np.hypot(*(cit - sp).T) <= 4
            self.sh_los[m, k] = T.line_of_sight(cit[m], np.repeat(sp[None, :], m.sum(), 0), 1.5, 6.0)
        self.d_cc = np.hypot(cit[:, None, 0] - cit[None, :, 0], cit[:, None, 1] - cit[None, :, 1])
        self.d_cs = np.hypot(cit[:, None, 0] - shelters[None, :, 0], cit[:, None, 1] - shelters[None, :, 1])

    # hazards
    def rain_at(self, x, y, t):
        c = cell_centre(t)
        bg = 6.0 * math.exp(-((t - 24) / 22) ** 2)  # normal monsoon rain in the background
        d = np.hypot(np.asarray(x) - c[0], np.asarray(y) - c[1])
        return bg + self.v["peak"] * cell_env(t) * np.exp(-(d / CELL_R) ** 2)

    def glof_front(self, t):
        if not self.v["inc"].get("GLOF", True) or t < GLOF_T:
            return None
        return self.y_top - GLOF_SPEED * (t - GLOF_T)

    # bookkeeping
    def reset(self):
        n_e, n_s, shape = len(self.edges), self.n_s, self.X.shape
        # note: update, not replace - a few keys (sat_ok, mast_ok, ...) are meant to carry over
        self.st.update(t=0.0, cum=np.zeros(self.cx.size), slides=[], cut=np.zeros(n_e, bool),
                       washed=np.zeros(n_e, bool), site_dead=np.zeros(n_s, bool), batt=np.full(n_s, self.v["batt"]),
                       shelter_dead=np.zeros(len(self.shelters), bool), flooded=np.zeros(shape, bool),
                       flood_now=np.zeros(shape, bool), events=[], hist=[],
                       uav_pos=np.tile(self.uav_base, (self.n_uav, 1)), launched=False,
                       mesh_ok=np.zeros(self.n_c, bool), frame=0, done=False, reach=None, flags=set(),
                       repair_acc=0.0, mast_fuel=72.0, dev_lost=np.zeros(self.n_c, bool))
        self.recompute_roads()

    def recompute_roads(self):
        st = self.st
        blocked = st["cut"] | st["washed"]
        st["reach"] = self.T.reachable(self.S["core"], blocked)
        st["fibre"] = np.array([r is None or not blocked[r].any() for r in self.route])

    def log(self, msg):
        self.st["events"].append(f"t={self.st['t']:5.1f} h  {msg}")

    def once(self, key, msg):
        if key not in self.st["flags"]:
            self.st["flags"].add(key)
            self.log(msg)

    # one time step
    def landslides(self, dt):
        st, mid = self.st, self.mid
        t = st["t"]
        st["cum"] += self.rain_at(self.cx, self.cy, t) * dt
        D = max(t, 1.0)
        exceed = (st["cum"] / D) / (14.82 * D ** -0.39)  # how far over the Caine threshold
        lam = 0.0009 * self.road_factor * (self.cs - SLIDE_SLOPE) / 15 * np.maximum(0, exceed - 1) ** 1.5
        hit = np.nonzero(self.rng.random(self.cx.size) < 1 - np.exp(-lam * dt))[0]
        changed = False
        for k in hit[:6]:
            p = np.array([self.cx[k], self.cy[k]])
            st["slides"].append(p)
            self.once("slide", "first landslides on the steep slopes (Caine threshold exceeded)")
            near_e = np.hypot(mid[:, 0] - p[0], mid[:, 1] - p[1]) < 0.3
            if near_e.any():
                st["cut"] |= near_e
                changed = True
                if self.is_nh10[near_e].any():
                    self.once("nh10", "landslide blocks NH10 (Gangtok's road + fibre link to the plains)")
            dead = (np.hypot(*(self.sites - p).T) < 0.2) & ~st["site_dead"]
            if dead.any():
                st["site_dead"] |= dead
                self.log("a landslide buries a cell site")
        return changed

    def flood(self, dt):
        st = self.st
        yf = self.glof_front(st["t"])
        if yf is None:
            st["flood_now"][:] = False
            return False
        self.once("glof", "GLACIAL LAKE OUTBURST! flood wave coming down the Teesta")
        depth = self.v["depth"]
        reach_now = (self.hand_g < depth) & (self.y_river >= yf)
        st["flooded"] |= reach_now
        st["flood_now"] = reach_now & (st["t"] < GLOF_T + GLOF_HOURS + (self.y_top - self.y_river) / GLOF_SPEED)
        changed = False
        w = (self.edge_hand < depth) & (self.edge_ry >= yf) & ~st["washed"]
        if w.any():
            st["washed"] |= w
            changed = True
            if self.is_nh10[w].any():
                self.once("nh10w", "flood washes away stretches of NH10 along the Teesta")
        sd = (self.site_hand < depth) & (self.site_ry >= yf) & ~st["site_dead"]
        if sd.any():
            st["site_dead"] |= sd
            self.log(f"flood destroys {int(sd.sum())} valley cell site(s)")
        sh = (self.shelter_hand < depth) & (self.shelter_ry >= yf) & ~st["shelter_dead"]
        for k in np.nonzero(sh)[0]:
            st["shelter_dead"][k] = True
            self.log(f"flood reaches {self.S['shelter_names'][k]}, lost its VSAT shelter")
        st["dev_lost"] |= (self.S["hand"] < depth) & (self.cit_ry >= yf) & self.has_dev
        return changed

    def repairs(self, dt):
        st, mid = self.st, self.mid
        if self.rain_at(0, 0, st["t"]) > 10 or not st["cut"].any():
            return False
        st["repair_acc"] += self.v["crews"] * dt
        changed = False
        while st["repair_acc"] >= 1 and st["cut"].any():
            idx = np.nonzero(st["cut"])[0]
            k = idx[np.argmin(np.hypot(mid[idx, 0], mid[idx, 1]))]  # crews work outward from Gangtok
            st["cut"][np.hypot(mid[:, 0] - mid[k, 0], mid[:, 1] - mid[k, 1]) < 0.3] = False
            st["repair_acc"] -= 1
            changed = True
        if changed:
            self.once("crews", "rain easing, road crews start clearing slides out from Gangtok")
        return changed

    def _update_power(self, dt):
        st, n_s = self.st, self.n_s
        powered = st["fibre"] | self.isolated  # grid power comes along the same road as the fibre
        st["batt"] = np.where(powered, self.v["batt"], st["batt"] - dt)
        st["site_ok"] = ~st["site_dead"] & (st["fibre"] | self.microwave) & (powered | (st["batt"] > 0))
        off = n_s - int(st["site_ok"].sum())
        if off >= st.get("last_off", 0) + 4:
            self.log(f"{off} of {n_s} cell sites off-air (fibre cut, batteries flat or destroyed)")
            st["last_off"] = off
        elif off < st.get("last_off", 0) - 4:
            self.log(f"sites coming back: {off} still off-air")
            st["last_off"] = off
        # the FM mast generator can only be refuelled if its road is open
        if not st["reach"][self.mast_node]:
            st["mast_fuel"] -= dt
        st["mast_ok"] = st["mast_fuel"] > 0
        if not st["mast_ok"]:
            self.once("mast", "FM mast generator out of diesel (road to the ridge still blocked)")
        return off

    def _update_drones(self, dt, t, off):
        st = self.st
        base_rain = float(self.rain_at(*self.uav_base, t))
        u = M.uav_layer(**{**C.UAV, "env": "Suburban", "wind": 4 + 0.15 * base_rain, "rain": base_rain,
                           "alt_msl": 1600})
        st["fly"] = u["fly"] > 0.5 and self.v["inc"].get("UAV", True) and not st["shelter_dead"][0]
        st["r_u"] = u["radius_m"] / 1000
        if st["fly"] and not st["launched"] and off >= 2:
            st["launched"] = True
            self.log("rain below 25 mm/h → UAV cells launched from Gangtok")
        if st["launched"]:
            # each drone heads for the nearest dead site
            dead = self.sites[~st["site_ok"]]
            base = self.uav_base
            tg = dead[np.argsort(np.hypot(*(dead - base).T))][:self.n_uav] if len(dead) else base[None, :]
            tgt = np.tile(base, (self.n_uav, 1))
            tgt[:len(tg)] = tg
            st["uav_pos"] += (tgt - st["uav_pos"]) * min(1.0, 0.6 * dt)

    def advance(self, dt):
        st = self.st
        st["t"] += dt
        t = st["t"]
        if self.landslides(dt) | self.flood(dt) | self.repairs(dt):
            self.recompute_roads()
        off = self._update_power(dt)
        if float(self.rain_at(*self.shelters[0], t)) > 60:
            self.once("fade", "cloudburst over Gangtok → Ku-band satellite link fading")
        self._update_drones(dt, t, off)

    def update_mesh(self):
        """Who can get a text out through the mesh. Returns a (thinned) list of links to draw."""
        st, n_c = self.st, self.n_c
        t = st["t"]
        r = M.lora_range_km(C.MESH["sf"], C.MESH["bw_khz"], C.MESH["ptx_dbm"], noise_rise(t), 6.0)
        alive = self.has_dev & (self.batt_dies > t) & ~st["dev_lost"]
        adj = (self.d_cc <= r) & self.los & alive[:, None] & alive[None, :]
        lab = np.arange(n_c)  # connected components by label propagation
        for _ in range(80):
            new = np.minimum(lab, np.where(adj, lab[None, :], n_c + 1).min(axis=1))
            if np.array_equal(new, lab):
                break
            lab = new
        sh_ok = ~st["shelter_dead"] & st.get("sat_ok", np.ones(len(self.shelters), bool))
        gate = (self.d_cs <= r * 1.5) & self.sh_los & sh_ok[None, :] & alive[:, None]
        good = set(lab[gate.any(axis=1)].tolist())  # clusters that touch a working gateway
        st["mesh_ok"] = alive & np.isin(lab, list(good))
        a, b = np.nonzero(np.triu(adj))
        keep = self.rng.random(len(a)) < min(1.0, 700 / max(len(a), 1))  # don't draw thousands of lines
        return [[self.cit[i], self.cit[j]] for i, j in zip(a[keep], b[keep])]

    def _fm_alert(self, nr):
        a, L = C.ANALOG, self.L
        fm = M.fm_metrics(a["df_khz"], a["fm_khz"])
        lk = M.analog_link(a["p_kw"], np.maximum(L["fm_d"], 0.2), a["fc_mhz"], a["gt_db"], a["gr_db"], a["nf_db"],
                           a["clutter_db"], nr, fm["carson_khz"], L["fm_loss"])
        return (M.fm_output_snr(lk["cnr"], fm["beta"]) >= 20) & self.st.get("mast_ok", True)

    def assign(self):
        """Work out which layer serves each citizen: 0-3 = SERVE_ORDER, 4 = alert only, 5 = nothing."""
        st, cit, n_c, n_s = self.st, self.cit, self.n_c, self.n_s
        t = st["t"]
        nr = noise_rise(t)
        inc = self.v["inc"]
        # mobile: a working site within the path loss budget, then Erlang-B blocking
        pl_max = 43 + 15 - (-174 + 10 * math.log10(0.2e6) + 7 + nr) - 4.9
        cover = (self.site_pl <= pl_max) & st["site_ok"][None, :]
        load = C.DIGITAL["erl_per_cell"] * surge(t) * n_s / max(int(st["site_ok"].sum()), 1)
        block = M.erlang_b(load, C.DIGITAL["channels"])
        mob = cover.any(axis=1) & (self.u_block >= block)
        if st["launched"] and st["fly"] and inc.get("UAV", True):
            uav = (np.hypot(cit[:, None, 0] - st["uav_pos"][None, :, 0],
                            cit[:, None, 1] - st["uav_pos"][None, :, 1]) <= st["r_u"]).any(axis=1)
        else:
            uav = np.zeros(n_c, bool)
        # satellite shelters (people walk up to 1.5 km): rain fade at each one + flood losses
        sat_ok = np.array([not st["shelter_dead"][k] and M.satellite_layer(
            **{**C.SAT, "rain": float(self.rain_at(*self.shelters[k], t)),
               "h_station": self.shelter_alt[k] / 1000})["margin"] > 0
            for k in range(len(self.shelters))])
        st["sat_ok"] = sat_ok
        sat = ((self.d_cs <= 1.5) & sat_ok[None, :]).any(axis=1)
        mesh = st["mesh_ok"] & inc.get("Mesh", True)
        alert = self._fm_alert(nr)
        cls = np.full(n_c, 5)
        for k, m in enumerate([mob, uav, sat, mesh]):
            cls = np.where((cls == 5) & m, k, cls)
        cls = np.where((cls == 5) & alert, 4, cls)
        st.update(cls=cls, block=block, core=(mob | sat).mean(), rain0=float(self.rain_at(0, 0, t)), nr=nr)

    def restart(self):
        self.reset()
        self.advance(0.0)
        segs = self.update_mesh()
        self.assign()
        self.log("monsoon rain over Sikkim, big cell building to the SW")
        return segs


def _setup_map(ax, sim):
    T, S = sim.T, sim.S
    m = SimpleNamespace()
    ax.set_aspect("equal")
    ax.set(xlim=T.extent[:2], ylim=T.extent[2:], xticks=[], yticks=[])
    ax.imshow(T.hillshade(), extent=T.extent, origin="lower", cmap="gray", vmin=-0.5, vmax=1.7,
              interpolation="bilinear", zorder=0)
    m.flood = ax.imshow(np.zeros(sim.X.shape + (4,)), extent=T.extent, origin="lower", interpolation="bilinear",
                        zorder=1)
    for rv in T.rivers:
        ax.plot(*rv["xy"].T, color="#3f7fbf", lw=1.0 if rv["name"] == "Teesta" else 0.6, zorder=1)
    ax.add_collection(LineCollection(sim.nodes[sim.edges], colors="#8c877c", lw=0.6, alpha=0.55, zorder=2))
    m.cuts = LineCollection([], colors="#ff4d4d", lw=3.4, zorder=4)
    ax.add_collection(m.cuts)
    for p in T.places:
        if p["kind"] in ("city", "town", "suburb") or p["name"] in ("Dikchu", "Rumtek"):
            ax.text(p["x"] + 0.3, p["y"] + 0.3, p["name"], fontsize=7.5, color=C.INK, zorder=8,
                    fontweight="bold" if p["kind"] == "city" else "normal")
    m.mesh = LineCollection([], colors=C.COL[C.L_MESH], lw=0.5, alpha=0.35, zorder=2)
    ax.add_collection(m.mesh)
    m.cit = ax.scatter(*sim.cit.T, s=11, color=NONE_C, zorder=5, lw=0)
    m.slides = ax.scatter([], [], marker="x", s=22, color=SLIDE_C, lw=1.6, zorder=4)
    m.sites = ax.scatter(*sim.sites.T, marker="^", s=55, color=C.COL[C.L_MO], edgecolor=C.INK, lw=0.6, zorder=6)
    m.shelters = ax.scatter(*sim.shelters.T, marker="s", s=80, color=C.COL[C.L_SA], edgecolor=C.INK, zorder=6)
    ax.plot(*S["mast"], marker="*", ms=16, color=C.COL[C.L_AN], mec=C.INK, zorder=7)
    ax.text(S["mast"][0], S["mast"][1] - 1.0, "FM mast", ha="center", fontsize=7, color=C.COL[C.L_AN], zorder=8)
    m.fm_ring = Circle(S["mast"], 1, fc="none", ec=C.COL[C.L_AN], lw=1.2, alpha=0.6, zorder=3)
    ax.add_patch(m.fm_ring)
    m.uav_cov = [Circle((0, 0), 1, fc=C.COL[C.L_UAV], alpha=0.14, ec=C.COL[C.L_UAV], lw=1, zorder=3)
                 for _ in range(sim.n_uav)]
    for c in m.uav_cov:
        ax.add_patch(c)
    m.uav, = ax.plot([], [], marker=(4, 0, 45), ms=10, color=C.COL[C.L_UAV], mec=C.INK, ls="none", zorder=9)
    m.cell = Circle((0, 0), CELL_R, fc="#9fb4c8", ec="none", alpha=0.0, zorder=3)
    ax.add_patch(m.cell)
    m.rain = LineCollection([], colors="#cfe0f0", lw=0.7, alpha=0.6, zorder=3)
    ax.add_collection(m.rain)
    m.streak_seed = sim.rng.random((60, 2))
    m.clock = ax.text(0.015, 0.985, "", transform=ax.transAxes, va="top", fontsize=10, fontweight="bold",
                      color=C.INK, bbox=dict(fc="#000000", alpha=0.6, ec="none"), zorder=10)
    ax.text(0.985, 0.015, f"terrain: NASA SRTM · map: {T.attribution}", transform=ax.transAxes, ha="right",
            fontsize=6, color=C.INK2, zorder=10, bbox=dict(fc="#000000", alpha=0.5, ec="none"))
    _map_legend(ax)
    return m


def _map_legend(ax):
    handles = [ax.scatter([], [], s=30, color=C.COL[l], label=f"served by {C.SHORT[l].lower()}") for l in SERVE_ORDER]
    handles += [ax.scatter([], [], s=30, color=C.COL[C.L_AN], label="analog alert only"),
                ax.scatter([], [], s=30, color=NONE_C, label="no contact"),
                ax.scatter([], [], marker="x", s=30, color=SLIDE_C, label="landslide"),
                ax.plot([], [], color=C.COL["bad"], lw=2, label="road / fibre cut")[0],
                ax.scatter([], [], marker="s", s=30, color="#2f6fb0", label="GLOF flood")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.003), ncol=5, fontsize=6.8,
              columnspacing=1.0, handletextpad=0.3)


FLOOD_RGBA = np.array(matplotlib.colors.to_rgba("#2f6fb0", 0.75))
SCAR_RGBA = np.array(matplotlib.colors.to_rgba("#5a4a3a", 0.55))  # where the flood has been


def _draw_network(m, sim, v):
    st = sim.st
    cls = st["cls"]
    palette = [C.COL[l] for l in SERVE_ORDER] + [C.COL[C.L_AN], NONE_C]
    m.cit.set_color([palette[c] for c in cls])
    m.cit.set_sizes(np.where(cls == 4, 9, 14))
    ok = st["site_ok"]
    on_batt = ok & ~(st["fibre"] | sim.isolated)
    m.sites.set_color(np.where(ok, np.where(on_batt, C.COL["warn"], C.COL[C.L_MO]), C.COL["bad"]))
    m.shelters.set_color(np.where(st["shelter_dead"], C.COL["bad"],
                                  np.where(st.get("sat_ok", True), C.COL[C.L_SA], C.COL["warn"])))
    if st["slides"]:
        m.slides.set_offsets(np.array(st["slides"]))
    e = st["cut"] | st["washed"]
    m.cuts.set_segments(sim.nodes[sim.edges[e]] if e.any() else [])
    img = np.zeros(sim.X.shape + (4,))
    img[st["flooded"] & ~st["flood_now"]] = SCAR_RGBA
    img[st["flood_now"]] = FLOOD_RGBA
    m.flood.set_data(img)
    m.mesh.set_visible(v["inc"].get("Mesh", True))
    for k, c in enumerate(m.uav_cov):
        c.center = tuple(st["uav_pos"][k])
        c.set_radius(st["r_u"])
        c.set_visible(st["launched"] and st["fly"])
    m.uav.set_data(st["uav_pos"][:, 0], st["uav_pos"][:, 1])
    m.uav.set_visible(st["launched"] and v["inc"].get("UAV", True))
    m.uav.set_alpha(1.0 if st["fly"] else 0.35)
    return on_batt


def _draw_weather(m, sim, v, frame):
    st = sim.st
    cc, env = cell_centre(st["t"]), cell_env(st["t"])
    m.cell.center = tuple(cc)
    m.cell.set_alpha(0.35 * env * v["peak"] / 130)
    sd = m.streak_seed[:int(60 * env)].copy()
    sd[:, 1] = (sd[:, 1] - frame * 0.07) % 1
    px = cc[0] + (sd[:, 0] - 0.5) * 2 * CELL_R
    py = cc[1] + (sd[:, 1] - 0.5) * 2 * CELL_R
    m.rain.set_segments([[(a, b), (a - 0.15, b - 0.6)] for a, b in zip(px, py)])
    m.fm_ring.set_radius((frame * 0.35) % 14 + 0.1)
    m.fm_ring.set_visible(bool(st.get("mast_ok", True)))
    m.clock.set_text(f"t = {st['t']:5.1f} h   rain over Gangtok {st['rain0']:4.0f} mm/h   "
                     f"slides {len(st['slides'])}")


def _readout_text(sim, counts, on_batt):
    st = sim.st
    cls = st["cls"]
    two_way = counts[:4].sum()
    valley = (cls[sim.zone_valley] < 4).mean() if sim.zone_valley.any() else 0
    return (f"NOW (t = {st['t']:.1f} h)\n"
            f"cell sites on air {int(st['site_ok'].sum())}/{sim.n_s} · on battery {int(on_batt.sum())}\n"
            f"road cuts {int(st['cut'].sum())} · washed {int(st['washed'].sum())} · call block {st['block']:.0%}\n"
            f"two-way (hybrid) {two_way:.0%} · 3 required only {st['core']:.0%}\n"
            f"two-way on the valley floor {valley:.0%}\n"
            f"alert-only {counts[4]:.0%} · no contact {counts[5]:.0%}")


def _draw_timeseries(ax, hist, show_glof):
    h = np.array(hist)
    ax.cla()
    ax.set_title("Share of citizens with two-way contact over time")
    if len(h) > 1:
        t = h[:, 0]
        ax.stackplot(t, h[:, 1:5].T, colors=[C.COL[l] for l in SERVE_ORDER], alpha=0.9, edgecolor=C.PANEL,
                     lw=0.5, labels=[C.SHORT[l] for l in SERVE_ORDER])
        ax.plot(t, h[:, 5], color=C.INK, lw=2, ls="--", label="3 required layers only")
        ax.plot(t, h[:, 6], color=C.COL["warn"], lw=1.2, label="rain at Gangtok (÷150)")
    ax.axvline(CELL_T, color=C.MUTED, ls=":", lw=1)
    ax.text(CELL_T + 0.8, 0.03, "cloudburst peak", fontsize=7, color=C.INK2)
    if show_glof:
        ax.axvline(GLOF_T, color="#2f6fb0", ls=":", lw=1)
        ax.text(GLOF_T + 0.8, 0.09, "lake outburst", fontsize=7, color="#7fb4ef")
    ax.set(xlim=(0, HOURS), ylim=(0, 1.22), xlabel="hours", ylabel="share of citizens")
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    if len(h) > 1:
        ax.legend(loc="upper center", fontsize=6.5, ncol=6, handlelength=1.2, columnspacing=0.8,
                  bbox_to_anchor=(0.5, 0.99))


def build():
    v = dict(peak=130.0, speed=1.0, crews=0.6, batt=6.0, depth=30.0, inc={"UAV": True, "Mesh": True, "GLOF": True})
    sim = CitySim(v, np.random.default_rng(2023))
    st = sim.st

    fig = new_figure(TITLE, "SRTM terrain + OSM roads/rivers/towns. Landslides cut the roads (and the fibre along "
                            "them), the flood comes down the Teesta, network fails over.",
                     "LIVE SIMULATION", size=(16, 9.6))
    gs = fig.add_gridspec(2, 2, left=0.02, right=0.985, top=0.905, bottom=0.25, width_ratios=[1.05, 1],
                          height_ratios=[1.25, 1], wspace=0.1, hspace=0.32)
    ax = fig.add_subplot(gs[:, 0])
    ax_ts = fig.add_subplot(gs[0, 1])
    ax_ev = fig.add_subplot(gs[1, 1])
    mp = _setup_map(ax, sim)
    ax_ts.set_title("Share of citizens with two-way contact over time")
    ax_ev.set_axis_off()
    ev_txt = ax_ev.text(0.0, 1.0, "", transform=ax_ev.transAxes, va="top", family="monospace", fontsize=7.8,
                        color=C.INK, linespacing=1.5)
    ro = readout(fig.add_axes([0.735, 0.035, 0.25, 0.165]))
    player = Player(fig)

    def draw(frame):
        on_batt = _draw_network(mp, sim, v)
        _draw_weather(mp, sim, v, frame)
        counts = np.bincount(st["cls"], minlength=6) / len(st["cls"])
        ro.set_text(_readout_text(sim, counts, on_batt))
        ro.set_color(status_colour(counts[:4].sum()))
        ev_txt.set_text("EVENT LOG\n" + "\n".join(st["events"][-12:]))
        return counts

    def draw_ts():
        _draw_timeseries(ax_ts, st["hist"], v["inc"].get("GLOF", True))

    def recompute(vals):
        v.update(peak=vals["peak"], speed=vals["speed"], crews=vals["crews"], batt=vals["batt"], depth=vals["depth"],
                 inc=vals["inc"])
        sim.assign()
        draw(st["frame"])
        fig.canvas.draw_idle()

    def restart():
        mp.mesh.set_segments(sim.restart())

    ctl = Controls(fig, recompute, rect=(0.015, 0.035, 0.58, 0.165), cols=2, rows=3)
    ctl.slider("peak", "Cloudburst peak (mm/h)", 40, 200, v["peak"], step=5, fmt="%.0f", color=C.COL["bad"])
    ctl.slider("speed", "Simulation speed", 0.25, 4, v["speed"], step=0.25, fmt="%.2f×")
    ctl.slider("crews", "Road crews (cuts cleared / h)", 0, 2, v["crews"], step=0.1, fmt="%.1f", color=C.COL["good"])
    ctl.slider("batt", "Site battery backup (h)", 0, 24, v["batt"], step=1, fmt="%.0f", color=C.COL["good"])
    ctl.slider("depth", "GLOF flood height (m)", 5, 60, v["depth"], step=1, fmt="%.0f", color=C.COL["bad"])
    ctl.check("inc", "Layers and hazards", ["UAV", "Mesh", "GLOF"], [True, True, True], [0.605, 0.075, 0.12, 0.125])
    ctl.button([0.605, 0.038, 0.058, 0.03], "▶ Play/Pause", player.toggle)
    ctl.button([0.667, 0.038, 0.058, 0.03], "↻ Restart", lambda: (restart(), draw_ts()))
    ctl.reset_button([0.44, 0.042, 0.14, 0.03], "Reset sliders")
    restart()
    draw(0)
    draw_ts()

    def step(frame):
        if not player.running:
            return
        st["frame"] += 1
        if st["t"] < HOURS:
            sim.advance(0.25 * v["speed"])
            if st["frame"] % 4 == 0:  # mesh is the slow bit, every 4th frame is enough
                mp.mesh.set_segments(sim.update_mesh())
            sim.assign()
            counts = draw(st["frame"])
            st["hist"].append([st["t"], *counts[:4], st["core"], min(st["rain0"] / 150, 1)])
            if st["frame"] % 3 == 0:
                draw_ts()
        else:
            if not st["done"]:
                sim.log("done. hit Restart to run it again")
                st["done"] = True
                draw_ts()
            draw(st["frame"])

    return fig, step, ctl
