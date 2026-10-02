#!/usr/bin/env python3
"""One-off download of the SRTM + OSM data (already bundled in resilient_net/data)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "resilient_net", "data")
UA = {"User-Agent": "disaster-net-student-project/1.0"}

INNER = dict(lat=(27.20, 27.42), lon=(88.45, 88.70), n=(100, 100), dataset="srtm30m")  # ~25 km, 250 m cells
OUTER = dict(lat=(26.85, 27.85), lon=(88.10, 89.10), n=(46, 46), dataset="srtm90m")  # ~110 km, 2.4 km cells


def _get(url, data=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as exc:  # rate limit or network hiccup -> back off
            print(f"    retry {k + 1}: {exc}")
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"failed: {url[:80]}")


def fetch_grid(spec):
    lats = np.linspace(*spec["lat"], spec["n"][0])
    lons = np.linspace(*spec["lon"], spec["n"][1])
    pts = [(la, lo) for la in lats for lo in lons]
    z = []
    for i in range(0, len(pts), 100):  # public API: 100 points per call, 1 call / s
        chunk = "|".join(f"{la:.5f},{lo:.5f}" for la, lo in pts[i:i + 100])
        res = _get(f"https://api.opentopodata.org/v1/{spec['dataset']}?locations={chunk}")["results"]
        z += [r["elevation"] if r["elevation"] is not None else np.nan for r in res]
        sys.stdout.write(f"\r    {spec['dataset']}: {min(i + 100, len(pts))}/{len(pts)} points")
        sys.stdout.flush()
        time.sleep(1.1)
    print()
    z = np.array(z, dtype=float).reshape(len(lats), len(lons))
    if np.isnan(z).any():  # fill rare voids with the mean of the grid
        z[np.isnan(z)] = np.nanmean(z)
    return lats, lons, z


def fetch_osm():
    b = f"{INNER['lat'][0]},{INNER['lon'][0]},{INNER['lat'][1]},{INNER['lon'][1]}"
    q = (f'[out:json][timeout:90];('
         f'way["highway"~"^(trunk|primary|secondary)$"]({b});'
         f'way["waterway"="river"]({b});'
         f'node["place"~"^(city|town|suburb|village|hamlet)$"]({b});'
         f'node["man_made"~"^(mast|tower|communications_tower)$"]({b}););out geom tags;')
    d = _get("https://overpass-api.de/api/interpreter", urllib.parse.urlencode({"data": q}).encode())
    out = dict(roads=[], rivers=[], places=[], masts=[])
    for e in d["elements"]:
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e:
            line = [[round(p["lat"], 5), round(p["lon"], 5)] for p in e["geometry"]]
            if "highway" in t:
                out["roads"].append(dict(ref=t.get("ref", ""), name=t.get("name", ""), kind=t["highway"], line=line))
            elif t.get("waterway") == "river":
                out["rivers"].append(dict(name=t.get("name", ""), line=line))
        elif e["type"] == "node":
            if "place" in t:
                out["places"].append(dict(name=t.get("name", "?"), kind=t["place"], lat=e["lat"], lon=e["lon"]))
            elif "man_made" in t:
                out["masts"].append(dict(kind=t["man_made"], lat=e["lat"], lon=e["lon"],
                                         use=t.get("tower:type", t.get("communication:mobile_phone", ""))))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    print("  Elevation, inner grid (town and Teesta valley)")
    la, lo, z = fetch_grid(INNER)
    print("  Elevation, outer grid (far ridges for the satellite skyline)")
    la2, lo2, z2 = fetch_grid(OUTER)
    np.savez_compressed(os.path.join(OUT, "gangtok_dem.npz"), lat=la, lon=lo, z=z.astype(np.float32),
                        lat_outer=la2, lon_outer=lo2, z_outer=z2.astype(np.float32),
                        fetched=time.strftime("%Y-%m-%d"))
    print("  OpenStreetMap layers")
    osm = fetch_osm()
    osm["fetched"] = time.strftime("%Y-%m-%d")
    osm["attribution"] = "© OpenStreetMap contributors, ODbL"
    with open(os.path.join(OUT, "gangtok_osm.json"), "w") as f:
        json.dump(osm, f, separators=(",", ":"))
    print(f"  done: {len(osm['roads'])} roads, {len(osm['rivers'])} rivers, {len(osm['places'])} places, "
          f"{len(osm['masts'])} masts; DEM {z.min():.0f}–{z.max():.0f} m")


if __name__ == "__main__":
    main()
