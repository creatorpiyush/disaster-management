"""Shared bits for the live views: cached downloads (live -> cache -> bundled sample) and map drawing."""
import datetime as dt
import json
import os
import time
import urllib.request

from matplotlib.patches import Polygon

from .. import config as C

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SAMPLES = os.path.join(DATA, "live_samples")
CACHE = "live_cache"
UA = {"User-Agent": "disaster-net-student-project/1.0 (educational)"}
GANGTOK = (27.3314, 88.6138)


def _days_ago(n):
    return (dt.datetime.utcnow() - dt.timedelta(days=n)).strftime("%Y-%m-%d")


# name: (url builder, max cache age in hours, provider shown on figures)
SOURCES = {
    "weather": (lambda: "https://api.open-meteo.com/v1/forecast?latitude=27.3314&longitude=88.6138&elevation=1650"
                        "&hourly=precipitation,rain,wind_speed_10m,wind_gusts_10m,cloud_cover,relative_humidity_2m,"
                        "temperature_2m&current=precipitation,wind_speed_10m,wind_gusts_10m,temperature_2m"
                        "&past_days=3&forecast_days=3&timezone=Asia%2FKolkata&wind_speed_unit=ms",
                0.5, "Open-Meteo.com (CC BY 4.0)"),
    "wx_2023": (lambda: _archive("2023-10-01", "2023-10-06"), 24 * 365, "Open-Meteo historical archive (ERA5)"),
    "wx_monsoon_daily": (lambda: "https://archive-api.open-meteo.com/v1/archive?latitude=27.3314&longitude=88.6138"
                                 f"&elevation=1650&start_date={monsoon_year()}-06-01&end_date={monsoon_year()}-09-30"
                                 "&daily=precipitation_sum&timezone=Asia%2FKolkata", 24 * 30,
                         "Open-Meteo historical archive (ERA5)"),
    "wx_monsoon": (lambda: _archive(*wettest_window()), 24 * 30, "Open-Meteo historical archive (ERA5)"),
    "sat_starlink": (lambda: "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json", 6,
                     "CelesTrak GP data"),
    "sat_oneweb": (lambda: "https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=json", 6,
                   "CelesTrak GP data"),
    "sat_iridium": (lambda: "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=json", 6,
                    "CelesTrak GP data"),
    "sat_geo": (lambda: "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=json", 12, "CelesTrak GP data"),
    "sat_stations": (lambda: "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json", 6,
                     "CelesTrak GP data"),
    "quakes": (lambda: "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime="
                       f"{_days_ago(90)}&minlatitude=20&maxlatitude=35&minlongitude=78&maxlongitude=98&minmagnitude=3",
               1, "USGS Earthquake Hazards Program"),
    "gdacs": (lambda: "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=EQ;TC;FL;VO;DR;WF"
                      f"&alertlevel=green;orange;red&fromdate={_days_ago(30)}&todate={_days_ago(-1)}",
              1, "GDACS (UN OCHA / European Commission JRC)"),
    "eonet": (lambda: "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=300", 2, "NASA EONET v3"),
    "kp": (lambda: "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", 1, "NOAA SWPC"),
    "xray": (lambda: "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json", 0.5, "NOAA SWPC (GOES)"),
    "f107": (lambda: "https://services.swpc.noaa.gov/json/f107_cm_flux.json", 6, "NOAA SWPC"),
}


def monsoon_year():
    t = dt.date.today()
    return t.year if t.month >= 10 else t.year - 1


def _archive(start, end):
    return ("https://archive-api.open-meteo.com/v1/archive?latitude=27.3314&longitude=88.6138&elevation=1650"
            f"&start_date={start}&end_date={end}&hourly=precipitation,wind_gusts_10m&timezone=Asia%2FKolkata"
            "&wind_speed_unit=ms")


def wettest_window():
    # +-3 days around the wettest 3-day stretch of last monsoon
    import numpy as np
    d = get("wx_monsoon_daily").data["daily"]
    p = np.nan_to_num(np.array(d["precipitation_sum"], dtype=float))
    k = int(np.argmax(np.convolve(p, np.ones(3), "valid"))) + 1  # +1 -> middle day
    mid = dt.date.fromisoformat(d["time"][k])
    return str(mid - dt.timedelta(days=3)), str(mid + dt.timedelta(days=2))


class Result:
    """Downloaded data + where it came from (live / cache / stale / sample)."""

    def __init__(self, name, data, mode, when, provider=None):
        self.name, self.data, self.mode, self.when = name, data, mode, when
        self.provider = provider or (SOURCES[name][2] if name in SOURCES else "")

    @property
    def badge(self):
        stamp = time.strftime("%d %b %Y %H:%M", time.localtime(self.when))
        return {"live": f"Live: fetched {stamp}", "cache": f"CACHED · fetched {stamp}",
                "stale": f"OFFLINE · last fetched {stamp}", "sample": f"OFFLINE · bundled sample ({stamp})"}[self.mode]

    @property
    def colour(self):
        return {"live": C.COL["good"], "cache": C.COL["good"], "stale": C.COL["warn"],
                "sample": C.COL["warn"]}[self.mode]


def offline():
    return os.environ.get("LIVE_OFFLINE") == "1"


def get(name, timeout=20):
    url_fn, max_age_h, _ = SOURCES[name]
    path = os.path.join(CACHE, f"{name}.json")
    have = os.path.exists(path)
    if have and not offline() and time.time() - os.path.getmtime(path) < max_age_h * 3600:
        return Result(name, _load(path), "cache", os.path.getmtime(path))
    if not offline():
        try:
            req = urllib.request.Request(url_fn(), headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, separators=(",", ":"))
            return Result(name, data, "live", time.time())
        except Exception:
            pass
    if have:
        return Result(name, _load(path), "stale", os.path.getmtime(path))
    sample = os.path.join(SAMPLES, f"{name}.json")
    return Result(name, _load(sample), "sample", _sample_time())


def _sample_time():
    try:
        with open(os.path.join(SAMPLES, "FETCHED.txt")) as f:
            return time.mktime(time.strptime(f.read().strip(), "%Y-%m-%d %H:%M"))
    except (OSError, ValueError):
        return time.time()


def get_url(name, url, max_age_h, provider, fallback, timeout=20):
    """get() but for a URL built at runtime. fallback() is used if offline and nothing cached."""
    path = os.path.join(CACHE, f"{name}.json")
    have = os.path.exists(path)
    if have and not offline() and time.time() - os.path.getmtime(path) < max_age_h * 3600:
        return Result(name, _load(path), "cache", os.path.getmtime(path), provider)
    if not offline():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                data = json.load(r)
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, separators=(",", ":"))
            return Result(name, data, "live", time.time(), provider)
        except Exception:
            pass
    if have:
        return Result(name, _load(path), "stale", os.path.getmtime(path), provider)
    return Result(name, fallback(), "sample", _sample_time(), "bundled SRTM grid (250 m)")


def _load(path):
    with open(path) as f:
        return json.load(f)


def badge(fig, results, y=0.943):
    # little status label top-right, shows the worst source (e.g. 'sample' if any one was offline)
    order = ["sample", "stale", "cache", "live"]
    worst = min(results, key=lambda r: order.index(r.mode))
    providers = ", ".join(sorted({r.provider for r in results}))
    fig.text(0.985, y, f"  {worst.badge}  ", fontsize=8, color=C.BG, va="top", ha="right", fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.3", fc=worst.colour, ec="none"))
    fig.text(0.985, 0.022, f"data: {providers}", fontsize=6.5, color=C.MUTED, ha="right", va="bottom")


def draw_geojson(ax, name, fc="#26292c", ec="#4a4d50", lw=0.6, zorder=0):
    with open(os.path.join(DATA, name)) as f:
        g = json.load(f)
    for feat in g["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for poly in polys:
            ax.add_patch(Polygon(poly[0], closed=True, fc=fc, ec=ec, lw=lw, zorder=zorder))


def haversine_km(lat1, lon1, lat2, lon2):
    import numpy as np
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))
