"""Menu 13: live data hub. Free open data, no keys, falls back to cached / bundled data offline."""
import contextlib
import io
import os
import re
import time

from .. import ui
from ..views._base import launch
from . import disasters, profile, sky, spacewx, weather

VIEWS = {
    "1": ("Live weather → effect on every layer", "Open-Meteo", weather, "live_1_weather"),
    "2": ("Real satellites over Gangtok right now", "CelesTrak", sky, "live_2_satellites"),
    "3": ("Active disasters + earthquakes around Sikkim", "GDACS, EONET, USGS", disasters, "live_3_disasters"),
    "4": ("Space weather and the ionosphere", "NOAA SWPC", spacewx, "live_4_space_weather"),
    "5": ("Terrain path profile and Fresnel zone", "OpenTopoData SRTM 30 m", profile, "live_5_profile"),
}
CITATIONS = [
    "Open-Meteo.com, Weather Forecast API and Historical Weather API (ERA5 reanalysis), CC BY 4.0.",
    "CelesTrak, GP element sets (Starlink, OneWeb, Iridium NEXT, GEO, space stations), celestrak.org.",
    "GDACS, Global Disaster Alert and Coordination System (UN OCHA / European Commission JRC), gdacs.org.",
    "NASA Earth Observatory Natural Event Tracker (EONET) v3, eonet.gsfc.nasa.gov.",
    "U.S. Geological Survey, Earthquake Catalog (FDSN event web service), earthquake.usgs.gov.",
    "NOAA Space Weather Prediction Center, planetary K-index, GOES X-ray flux and F10.7, swpc.noaa.gov.",
    "OpenTopoData public API, SRTM 30 m dataset, opentopodata.org.",
    "Natural Earth, 1:110m land and 1:50m admin-0 boundaries (public domain), naturalearthdata.com.",
]


def menu():
    while True:
        items = ["Free open data, no API keys. Offline = last download or the bundled sample."]
        items += [(k, t, h) for k, (t, h, _, _) in VIEWS.items()]
        items += [None, ("6", "Save a dated snapshot for the report", "figures + numbers + citations"),
                  ("0", "Back to the main menu", "")]
        ch = ui.menu("LIVE DATA HUB - press a number", items)
        if ch == "0":
            return
        if ch == "6":
            snapshot()
            ui.pause("Press Enter to return to the live-data menu")
            continue
        title, _, mod, name = VIEWS[ch]
        print(ui.grey("  fetching..."))
        try:
            mod.print_calculations()
        except Exception as exc:
            print(ui.red(f"  Could not prepare the data: {exc}"))
            continue
        print()
        ui.controls_help()
        ui.pause()
        try:
            launch(mod.build, name)
        except Exception as exc:
            print(ui.red(f"  Window crashed: {exc}"))


def snapshot():
    # grab everything once and save it with today's date so the report has a fixed copy
    import matplotlib
    stamp = time.strftime("%Y-%m-%d_%H%M")
    out = os.path.join("results", f"live_snapshot_{stamp}")
    os.makedirs(out, exist_ok=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for k, (title, _, mod, _) in VIEWS.items():
            try:
                mod.print_calculations()
            except Exception as exc:
                print(f"  {title}: not available ({exc})")
    text = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
    with open(os.path.join(out, "live_numbers.txt"), "w", encoding="utf-8") as f:
        f.write(f"Live-data snapshot taken {time.strftime('%d %B %Y, %H:%M %Z')}\n{text}")
    with open(os.path.join(out, "data_sources.txt"), "w", encoding="utf-8") as f:
        f.write(f"Data sources (accessed {time.strftime('%d %B %Y')}):\n\n")
        f.write("\n".join(f"[{i + 1}] {c}" for i, c in enumerate(CITATIONS)) + "\n")
    print(ui.green(f"  saved {out}/live_numbers.txt"))
    print(ui.green(f"  saved {out}/data_sources.txt"))
    before = matplotlib.get_backend()
    matplotlib.use("Agg", force=True)
    try:
        for k, (title, _, mod, name) in VIEWS.items():
            try:
                p = launch(mod.build, name, test_frames=25, exercise=False, dpi=200)
                dest = os.path.join(out, os.path.basename(p))
                os.replace(p, dest)
                print(ui.green(f"  saved {dest}") + ui.grey(f"   ({title})"))
            except Exception as exc:
                print(ui.red(f"  FAIL  {title}: {exc}"))
    finally:
        matplotlib.use(before, force=True)
    return out


def selftest():
    # offline on purpose so the test doesn't depend on the internet
    os.environ["LIVE_OFFLINE"] = "1"
    ok = True
    try:
        for k, (title, _, mod, name) in VIEWS.items():
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    mod.print_calculations()
                launch(mod.build, f"selftest_{name}", test_frames=12)
                print(ui.green("  ok    ") + "Live: " + title)
            except Exception as exc:
                ok = False
                print(ui.red(f"  FAIL  Live: {title}: {exc!r}"))
    finally:
        os.environ.pop("LIVE_OFFLINE", None)
    return ok
