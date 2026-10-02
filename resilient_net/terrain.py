"""Real terrain (SRTM) + OSM map data for Gangtok and the Teesta valley, and the propagation helpers.

Coords are local km: x east, y north, (0, 0) = MG Marg. Data comes from tools/fetch_gangtok_data.py.
"""
import heapq
import json
import math
import os
from functools import lru_cache

import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ORIGIN = (27.3314, 88.6138)  # Gangtok, MG Marg (lat, lon)
KM_LAT = 110.95
KM_LON = 111.32 * math.cos(math.radians(ORIGIN[0]))
R_EARTH = 6371.0
K_FACTOR = 4 / 3  # standard refractive atmosphere
GEO_SLOT_E = 83.0  # an Indian GEO orbital slot (degrees east)
WEIGHT = {"city": 0.50, "town": 0.07, "suburb": 0.05, "village": 0.012, "hamlet": 0.005}


def to_xy(lat, lon):
    return (np.asarray(lon) - ORIGIN[1]) * KM_LON, (np.asarray(lat) - ORIGIN[0]) * KM_LAT


def knife_edge_db(v):
    """J(v) knife-edge loss, ITU-R P.526 eq. 31 (0 dB below v = -0.78)."""
    v = np.asarray(v, dtype=float)
    j = 6.9 + 20 * np.log10(np.sqrt((v - 0.1) ** 2 + 1) + v - 0.1)
    return np.where(v > -0.78, j, 0.0)


def geo_look_angles(lat_deg, lon_deg, sat_lon_deg=GEO_SLOT_E):
    """az/el to a GEO sat, spherical earth"""
    lat, dl = math.radians(lat_deg), math.radians(sat_lon_deg - lon_deg)
    cg = math.cos(lat) * math.cos(dl)
    g = math.acos(cg)
    el = math.degrees(math.atan((cg - 6378.0 / 42164.0) / math.sin(g)))
    az = (180 - math.degrees(math.atan2(math.tan(dl), math.sin(lat)))) % 360  # sat to the west -> az > 180
    return az, el


def _interp(gx, gy, Z, x, y):
    fx = np.clip((np.asarray(x, float) - gx[0]) / (gx[1] - gx[0]), 0, len(gx) - 1.0001)
    fy = np.clip((np.asarray(y, float) - gy[0]) / (gy[1] - gy[0]), 0, len(gy) - 1.0001)
    i, j = fx.astype(int), fy.astype(int)
    tx, ty = fx - i, fy - j
    return (Z[j, i] * (1 - tx) * (1 - ty) + Z[j, i + 1] * tx * (1 - ty) +
            Z[j + 1, i] * (1 - tx) * ty + Z[j + 1, i + 1] * tx * ty)


class Terrain:
    def __init__(self):
        d = np.load(os.path.join(DATA, "gangtok_dem.npz"))
        self.fetched = str(d["fetched"])
        self.gx, self.gy = to_xy(d["lat"][0], d["lon"])[0], to_xy(d["lat"], d["lon"][0])[1]
        self.z = d["z"].astype(float)
        self.ox, self.oy = to_xy(d["lat_outer"][0], d["lon_outer"])[0], to_xy(d["lat_outer"], d["lon_outer"][0])[1]
        self.oz = d["z_outer"].astype(float)
        self.extent = (self.gx[0], self.gx[-1], self.gy[0], self.gy[-1])
        self.cell_km = float(self.gx[1] - self.gx[0])
        with open(os.path.join(DATA, "gangtok_osm.json")) as f:
            osm = json.load(f)
        self.attribution = osm.get("attribution", "© OpenStreetMap contributors")
        xy = lambda line: np.array(to_xy(*np.array(line).T)).T
        self.roads = [dict(ref=r["ref"], name=r["name"], kind=r["kind"], xy=xy(r["line"])) for r in osm["roads"]]
        self.rivers = [dict(name=r["name"], xy=xy(r["line"])) for r in osm["rivers"]]
        self.places = []
        for p in osm["places"]:
            x, y = to_xy(p["lat"], p["lon"])
            if self.inside(x, y, margin=0.3):
                self.places.append(dict(name=p["name"], kind=p["kind"], x=float(x), y=float(y)))
        self.masts = [np.array(to_xy(m["lat"], m["lon"])) for m in osm["masts"]]

    # -- elevation
    def inside(self, x, y, margin=0.0):
        x0, x1, y0, y1 = self.extent
        return (x0 + margin <= x <= x1 - margin) and (y0 + margin <= y <= y1 - margin)

    def elev(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        x0, x1, y0, y1 = self.extent
        inner = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        out = _interp(self.ox, self.oy, self.oz, x, y)
        return np.where(inner, _interp(self.gx, self.gy, self.z, x, y), out)

    def mesh(self):
        return np.meshgrid(self.gx, self.gy)

    @lru_cache(maxsize=None)
    def slope_deg(self):
        dzdy, dzdx = np.gradient(self.z, self.cell_km * 1000, self.cell_km * 1000)
        return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))

    @lru_cache(maxsize=None)
    def hillshade(self, az=315.0, alt=40.0):
        dzdy, dzdx = np.gradient(self.z, self.cell_km * 1000, self.cell_km * 1000)
        slope = np.arctan(np.hypot(dzdx, dzdy))
        aspect = np.arctan2(-dzdx, dzdy)
        a, e = math.radians(az), math.radians(alt)
        hs = np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)
        return np.clip(hs, 0, 1)

    # -- radio paths over terrain
    def diffraction_db(self, tx, h_tx, rx, h_rx, f_mhz, n=48):
        """Worst single ridge between tx and each rx (P.526 4.1). rx is (N, 2), heights in m above ground.
        returns loss_dB, v_max, d_km"""
        rx = np.atleast_2d(rx)
        t = np.linspace(0, 1, n + 2)[1:-1]
        px = tx[0] + np.outer(rx[:, 0] - tx[0], t)
        py = tx[1] + np.outer(rx[:, 1] - tx[1], t)
        zs = self.elev(px, py)
        z0 = float(self.elev(*tx)) + h_tx
        z1 = self.elev(rx[:, 0], rx[:, 1]) + h_rx
        dk = np.maximum(np.hypot(rx[:, 0] - tx[0], rx[:, 1] - tx[1]), 1e-3)
        d1, d2 = np.outer(dk, t), np.outer(dk, 1 - t)
        line = z0 + np.outer(z1 - z0, t)
        bulge = d1 * d2 * 1000 / (2 * K_FACTOR * R_EARTH)
        h = zs + bulge - line
        lam = 299.792458 / f_mhz
        v = h * np.sqrt(2 / lam * (1 / (d1 * 1000) + 1 / (d2 * 1000)))
        vmax = v.max(axis=1)
        return knife_edge_db(vmax), vmax, dk

    def line_of_sight(self, a, b, h_a=2.0, h_b=2.0, n=24):
        # a, b: (N, 2). True where the straight line a[i]-b[i] stays above ground
        a, b = np.atleast_2d(a), np.atleast_2d(b)
        t = np.linspace(0, 1, n + 2)[1:-1]
        px = a[:, :1] + (b[:, :1] - a[:, :1]) * t
        py = a[:, 1:] + (b[:, 1:] - a[:, 1:]) * t
        za = self.elev(a[:, 0], a[:, 1]) + h_a
        zb = self.elev(b[:, 0], b[:, 1]) + h_b
        line = za[:, None] + (zb - za)[:, None] * t
        return (self.elev(px, py) <= line).all(axis=1)

    def profile(self, a, b, n=240):
        t = np.linspace(0, 1, n)
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        return t * math.hypot(b[0] - a[0], b[1] - a[1]), self.elev(x, y), x, y

    def skyline(self, x, y, h=3.0, az_step=5.0):
        # horizon elevation (deg) all the way round, with earth curvature
        az = np.arange(0, 360, az_step)
        d = np.r_[np.arange(0.25, 12, 0.25), np.arange(12, 55, 1.0)]
        a = np.radians(az)
        px = x + np.outer(np.sin(a), d)
        py = y + np.outer(np.cos(a), d)
        z = self.elev(px, py)
        z0 = float(self.elev(x, y)) + h
        ang = np.degrees(np.arctan(((z - z0) / 1000 - d ** 2 / (2 * K_FACTOR * R_EARTH)) / d))
        return az, np.maximum(ang.max(axis=1), 0)

    def site_latlon(self, x, y):
        return ORIGIN[0] + y / KM_LAT, ORIGIN[1] + x / KM_LON

    # -- hydrology: height above the Teesta (where a GLOF can reach)
    @lru_cache(maxsize=None)
    def teesta(self):
        # height above the nearest bit of Teesta riverbed (m) + the river cells sorted N to S
        pts = []
        for r in self.rivers:
            if r["name"] != "Teesta":
                continue
            for p, q in zip(r["xy"][:-1], r["xy"][1:]):
                k = max(2, int(math.hypot(*(q - p)) / 0.08))
                pts.append(p + (q - p) * np.linspace(0, 1, k)[:, None])
        pts = np.vstack(pts)
        pts = pts[[self.inside(*p) for p in pts]]
        bed = self.elev(pts[:, 0], pts[:, 1])
        order = np.argsort(-pts[:, 1])  # the river flows north -> south
        pts, bed = pts[order], np.minimum.accumulate(bed[order])  # bed never rises downstream
        X, Y = self.mesh()
        dd = np.hypot(X.ravel()[:, None] - pts[None, :, 0], Y.ravel()[:, None] - pts[None, :, 1])
        k = dd.argmin(axis=1)
        hand = (self.z.ravel() - bed[k]).reshape(self.z.shape)
        dist = dd.min(axis=1).reshape(self.z.shape)
        return np.where(dist < 1.6, hand, 1e4), pts, dist

    def hand_at(self, x, y):
        hand, _, _ = self.teesta()
        return _interp(self.gx, self.gy, hand, x, y)

    # -- road graph (fibre and power lines follow the roads)
    @lru_cache(maxsize=None)
    def road_graph(self):
        key = {}
        nodes, edges = [], {}
        for r in self.roads:
            ids = []
            for p in r["xy"]:
                k = (round(p[0], 3), round(p[1], 3))
                if k not in key:
                    key[k] = len(nodes)
                    nodes.append(p)
                ids.append(key[k])
            for a, b in zip(ids[:-1], ids[1:]):
                if a != b:
                    edges.setdefault(tuple(sorted((a, b))), r["ref"])
        nodes = np.array(nodes)
        self.edge_ref = list(edges.values())
        edges = np.array(list(edges.keys()))
        mid = (nodes[edges[:, 0]] + nodes[edges[:, 1]]) / 2
        return nodes, edges, mid

    def reachable(self, start, cut):
        # plain BFS over the road graph skipping cut edges
        nodes, edges, _ = self.road_graph()
        adj = [[] for _ in nodes]
        for (a, b), c in zip(edges, cut):
            if not c:
                adj[a].append(b)
                adj[b].append(a)
        seen = np.zeros(len(nodes), bool)
        seen[start] = True
        stack = [start]
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
        return seen

    def nearest_node(self, x, y):
        nodes, _, _ = self.road_graph()
        return int(np.argmin(np.hypot(nodes[:, 0] - x, nodes[:, 1] - y)))

    def path_length_km(self, start):
        # dijkstra
        nodes, edges, _ = self.road_graph()
        adj = [[] for _ in nodes]
        for a, b in edges:
            w = float(np.hypot(*(nodes[a] - nodes[b])))
            adj[a].append((b, w))
            adj[b].append((a, w))
        dist = np.full(len(nodes), np.inf)
        dist[start] = 0
        pq = [(0.0, start)]
        while pq:
            du, u = heapq.heappop(pq)
            if du > dist[u]:
                continue
            for w, l in adj[u]:
                if du + l < dist[w]:
                    dist[w] = du + l
                    heapq.heappush(pq, (du + l, w))
        return dist


@lru_cache(maxsize=None)
def load():
    return Terrain()


# citizens, cell sites, VSAT shelters, FM mast - all placed from the real data
@lru_cache(maxsize=None)
def scenario(n_citizens=420, seed=2023):
    T = load()
    rng = np.random.default_rng(seed)
    slope = T.slope_deg()
    places = [p for p in T.places if p["kind"] in WEIGHT]
    w = np.array([WEIGHT[p["kind"]] for p in places])
    w /= w.sum()
    spread = {"city": 1.1, "town": 0.45, "suburb": 0.4, "village": 0.25, "hamlet": 0.18}
    cit = []
    while len(cit) < n_citizens:
        p = places[rng.choice(len(places), p=w)]
        q = np.array([p["x"], p["y"]]) + rng.normal(0, spread[p["kind"]], 2)
        if not T.inside(*q, margin=0.2):
            continue
        s = _interp(T.gx, T.gy, slope, q[0], q[1])
        if s < 38 and T.hand_at(*q) > 3:  # people do not live on cliffs or in the riverbed
            cit.append(q)
    cit = np.array(cit)
    z = T.elev(cit[:, 0], cit[:, 1])
    hand = T.hand_at(cit[:, 0], cit[:, 1])
    centre = np.hypot(cit[:, 0], cit[:, 1]) < 3.2
    zone = np.where(hand < 80, "Valley floor (Teesta)", np.where(centre & (z > 1350), "Ridge town (Gangtok)",
                                                                 "Hill-slope villages"))
    # FM broadcast mast: highest ground within 6 km of the town centre
    X, Y = T.mesh()
    near = np.hypot(X, Y) < 6
    j, i = np.unravel_index(np.argmax(np.where(near, T.z, -1)), T.z.shape)
    mast = np.array([T.gx[i], T.gy[j]])
    # cell sites: real OSM masts + one hill-top site per cluster of citizens (k-means on homes)
    k = 26
    cen = cit[rng.choice(len(cit), k, replace=False)]
    for _ in range(25):
        lab = np.argmin(np.hypot(cit[:, None, 0] - cen[None, :, 0], cit[:, None, 1] - cen[None, :, 1]), axis=1)
        cen = np.array([cit[lab == c].mean(axis=0) if (lab == c).any() else cen[c] for c in range(k)])
    sites = []
    for c in cen:  # move each site to the highest point within 0.8 km
        m = np.hypot(X - c[0], Y - c[1]) < 0.8
        jj, ii = np.unravel_index(np.argmax(np.where(m, T.z, -1)), T.z.shape)
        sites.append([T.gx[ii], T.gy[jj]])
    for m in T.masts:
        if T.inside(*m) and np.min(np.hypot(*(np.array(sites) - m).T)) > 0.6:
            sites.append(list(m))
    sites = np.array(sites)
    # VSAT emergency shelters at the main settlements
    want = ["Gangtok", "Singtam", "Ranipool", "Pakyong", "Dikchu", "Martam", "Rumtek"]
    shelters, s_names = [], []
    for nm in want:
        for p in T.places:
            if p["name"].lower().startswith(nm.lower()) and nm not in s_names:
                shelters.append([p["x"], p["y"]])
                s_names.append(nm)
    shelters = np.array(shelters[:5])
    s_names = s_names[:5]
    # exchange / core node of the fibre network: road node nearest the town centre
    core = T.nearest_node(0.0, 0.0)
    site_node = np.array([T.nearest_node(*s) for s in sites])
    microwave = T.line_of_sight(np.repeat(mast[None, :], len(sites), 0), sites, 30, 30) & \
        (np.hypot(*(sites - mast).T) < 15)
    return dict(T=T, cit=cit, z=z, hand=hand, zone=zone, mast=mast, sites=sites, site_node=site_node,
                microwave=microwave, shelters=shelters, shelter_names=s_names, core=core)


@lru_cache(maxsize=None)
def link_tables(f_mobile=900.0, f_fm=100.0):
    # terrain loss citizen<->FM mast and citizen<->each cell site
    S = scenario()
    T, cit = S["T"], S["cit"]
    fm_loss, _, fm_d = T.diffraction_db(S["mast"], 50.0, cit, 1.5, f_fm)
    n, m = len(cit), len(S["sites"])
    site_loss = np.zeros((n, m))
    site_d = np.zeros((n, m))
    for j, s in enumerate(S["sites"]):
        site_loss[:, j], _, site_d[:, j] = T.diffraction_db(s, 30.0, cit, 1.5, f_mobile, n=32)
    return dict(fm_loss=fm_loss, fm_d=fm_d, site_loss=site_loss, site_d=site_d)


@lru_cache(maxsize=None)
def sky_tables():
    # from each home: is GEO hidden behind a ridge, and how much open sky for LEO
    S = scenario()
    T, cit = S["T"], S["cit"]
    az_geo, el_geo = geo_look_angles(*T.site_latlon(0, 0))
    geo_block, leo_open = np.zeros(len(cit), bool), np.zeros(len(cit))
    for i, (x, y) in enumerate(cit):
        az, sky = T.skyline(x, y, 3.0, 10.0)
        k = int(round(az_geo / 10)) % len(az)
        geo_block[i] = sky[k] >= el_geo - 2
        leo_open[i] = np.mean(np.clip((60 - np.maximum(sky, 25)) / 35, 0, 1))  # usable LEO sky above 25°
    return dict(az_geo=az_geo, el_geo=el_geo, geo_block=geo_block, leo_open=leo_open)


@lru_cache(maxsize=None)
def fm_loss_grid(f_mhz=100.0, h_mast=50.0):
    # FM mast -> every map cell: ridge loss + distance (for the coverage heatmap)
    S = scenario()
    T = S["T"]
    X, Y = T.mesh()
    loss, _, d = T.diffraction_db(S["mast"], h_mast, np.c_[X.ravel(), Y.ravel()], 1.5, f_mhz)
    return loss.reshape(X.shape), d.reshape(X.shape)


ZONES = ["Whole district", "Ridge town (Gangtok)", "Hill-slope villages", "Valley floor (Teesta)"]


@lru_cache(maxsize=None)
def zone_stats(zone="Whole district"):
    """Per-zone terrain numbers the models need. Cached."""
    S, L, K = scenario(), link_tables(), sky_tables()
    m = np.ones(len(S["cit"]), bool) if zone == ZONES[0] else S["zone"] == zone
    best_site = L["site_loss"][m].min(axis=1)
    # share of neighbour pairs (≤ 2 km apart) whose straight path is blocked by a ridge -> extra mesh loss
    c = S["cit"][m]
    ii, jj = np.nonzero(np.triu(np.hypot(c[:, None, 0] - c[None, :, 0], c[:, None, 1] - c[None, :, 1]) <= 2.0, 1))
    blocked = 1 - S["T"].line_of_sight(c[ii], c[jj], 1.5, 1.5).mean() if len(ii) else 0.5
    return dict(n=int(m.sum()), mask=m, alt_m=float(np.mean(S["z"][m])), fm_d=L["fm_d"][m], fm_loss=L["fm_loss"][m],
                mobile_extra=float(np.median(best_site)), geo_block=float(K["geo_block"][m].mean()),
                leo_open=float(K["leo_open"][m].mean()), share=float(m.mean()), blocked=float(blocked),
                mesh_loss=float(6 + 20 * blocked))
