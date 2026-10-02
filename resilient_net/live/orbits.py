"""Satellite positions from CelesTrak elements. Kepler + J2, numpy only (not SGP4, but close enough)."""
import datetime as dt
import math

import numpy as np

MU = 398600.4418  # km³/s²
RE = 6378.137  # km
J2 = 1.08262668e-3
OMEGA_E = 7.2921150e-5  # rad/s


class Constellation:
    def __init__(self, records, label):
        self.label = label
        r = [x for x in records if x.get("MEAN_MOTION")]
        self.names = [x["OBJECT_NAME"] for x in r]
        self.epoch = np.array([_parse(x["EPOCH"]) for x in r])
        self.n = np.array([x["MEAN_MOTION"] for x in r]) * 2 * math.pi / 86400  # rad/s
        self.ndot = np.array([x.get("MEAN_MOTION_DOT", 0.0) for x in r]) * 2 * math.pi / 86400 ** 2
        self.e = np.array([x["ECCENTRICITY"] for x in r])
        self.i = np.radians([x["INCLINATION"] for x in r])
        self.raan0 = np.radians([x["RA_OF_ASC_NODE"] for x in r])
        self.argp0 = np.radians([x["ARG_OF_PERICENTER"] for x in r])
        self.m0 = np.radians([x["MEAN_ANOMALY"] for x in r])
        self.a = (MU / self.n ** 2) ** (1 / 3)
        p = self.a * (1 - self.e ** 2)
        k = 1.5 * self.n * J2 * (RE / p) ** 2
        self.raan_dot = -k * np.cos(self.i)
        self.argp_dot = 0.5 * k * (5 * np.cos(self.i) ** 2 - 1)

    def __len__(self):
        return len(self.names)

    def eci(self, t):
        """Position (km) in the inertial frame at UTC datetime t, shape (N, 3)."""
        dts = np.array([(t - e).total_seconds() for e in self.epoch]) if len(self.epoch) < 50 else \
            (np.datetime64(t.replace(tzinfo=None)) - self._ep64()).astype("timedelta64[ms]").astype(float) / 1000
        m = self.m0 + self.n * dts + self.ndot * dts ** 2 / 2
        E = m.copy()
        for _ in range(8):  # Newton iterations on Kepler's equation
            E -= (E - self.e * np.sin(E) - m) / (1 - self.e * np.cos(E))
        nu = 2 * np.arctan2(np.sqrt(1 + self.e) * np.sin(E / 2), np.sqrt(1 - self.e) * np.cos(E / 2))
        r = self.a * (1 - self.e * np.cos(E))
        u = self.argp0 + self.argp_dot * dts + nu
        raan = self.raan0 + self.raan_dot * dts
        cu, su, cO, sO, ci, si = np.cos(u), np.sin(u), np.cos(raan), np.sin(raan), np.cos(self.i), np.sin(self.i)
        return np.c_[r * (cO * cu - sO * su * ci), r * (sO * cu + cO * su * ci), r * su * si]

    def _ep64(self):
        if not hasattr(self, "_e64"):
            self._e64 = np.array([np.datetime64(e.replace(tzinfo=None)) for e in self.epoch])
        return self._e64

    def look(self, t, lat, lon, h_km=0.0):
        """Azimuth, elevation (deg) and slant range (km) from a ground site."""
        r = self.eci(t)
        th = gmst(t)
        c, s = math.cos(th), math.sin(th)
        x = c * r[:, 0] + s * r[:, 1]  # inertial -> Earth-fixed
        y = -s * r[:, 0] + c * r[:, 1]
        z = r[:, 2]
        la, lo = math.radians(lat), math.radians(lon)
        o = (RE + h_km) * np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
        d = np.c_[x - o[0], y - o[1], z - o[2]]
        e_ = np.array([-math.sin(lo), math.cos(lo), 0])
        n_ = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
        u_ = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
        E, N, U = d @ e_, d @ n_, d @ u_
        rng = np.sqrt(E ** 2 + N ** 2 + U ** 2)
        return np.degrees(np.arctan2(E, N)) % 360, np.degrees(np.arcsin(U / rng)), rng


def gmst(t):
    """Greenwich mean sidereal time (rad) for a UTC datetime."""
    jd = (t - dt.datetime(2000, 1, 1, 12, tzinfo=dt.timezone.utc)).total_seconds() / 86400 + 2451545.0
    return math.radians((280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360)


def _parse(s):
    s = s.rstrip("Z")
    fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in s else "%Y-%m-%dT%H:%M:%S"
    return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)


def now():
    return dt.datetime.now(dt.timezone.utc)
