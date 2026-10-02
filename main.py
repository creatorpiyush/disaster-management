#!/usr/bin/env python3
"""
Disaster-Resilient Hybrid Communication Network for a Smart City — interactive simulator.

    pip install -r requirements.txt
    python main.py              interactive menu (press a number, a live window opens)
    python main.py --export     save every figure to ./figures and every calculation to ./results
    python main.py --selftest   run every view headless and move every control (checks for errors)

Required layers  : analog emergency radio, digital mobile network, satellite backup.
Optional layers  : UAV aerial base station, LoRa / D2D mesh — extensions that may complement them.
"""
import contextlib
import io
import os
import re
import sys

try:
    import numpy  # noqa: F401
    import matplotlib
except ImportError:
    print("This program needs numpy and matplotlib.\n    pip install -r requirements.txt")
    sys.exit(1)

if "--export" in sys.argv or "--selftest" in sys.argv:
    matplotlib.use("Agg")

from resilient_net import config as C, ui                       # noqa: E402
from resilient_net.references import print_references          # noqa: E402
from resilient_net.views import (analog, block, city, compare, digital, mesh, noise,  # noqa: E402
                                 satellite, uav)
from resilient_net.views._base import launch                   # noqa: E402

VIEWS = {
    "1": ("Layer 1 · Analog emergency radio (AM / FM)", "required", analog, "01_layer1_analog_radio"),
    "2": ("Layer 2 · Digital mobile network", "required", digital, "02_layer2_mobile_network"),
    "3": ("Layer 3 · Satellite backup", "required", satellite, "03_layer3_satellite"),
    "4": ("Supplementary A · UAV aerial base station", "optional extension", uav, "04_suppA_uav"),
    "5": ("Supplementary B · LoRa / D2D mesh", "optional extension", mesh, "05_suppB_mesh"),
    "6": ("Comparison of all layers + hybrid", "radar, sweeps, failover", compare, "06_comparison"),
    "7": ("Block diagram (animated, with failover)", "Tx → channel → Rx", block, "07_block_diagram"),
    "8": ("Noise & signal-quality lab", "SNR, BER, eye diagram", noise, "08_noise_lab"),
    "9": ("Live disaster simulation", "cyclone crosses the city", city, "09_live_city_simulation"),
}
EXPORT_FRAMES = {"9": 260}


def main_menu():
    items = ["THE THREE REQUIRED LAYERS"]
    items += [(k, VIEWS[k][0], VIEWS[k][1]) for k in "123"]
    items += [None, "OPTIONAL EXTENSIONS (could complement the required layers)"]
    items += [(k, VIEWS[k][0], VIEWS[k][1]) for k in "45"]
    items += [None, "ANALYSIS AND SIMULATION"]
    items += [(k, VIEWS[k][0], VIEWS[k][1]) for k in "6789"]
    items += [None, "REPORT TOOLS"]
    items += [("10", "Print every calculation", "formula → values → result"),
              ("11", "Export all figures + calculations", "./figures, ./results"),
              ("12", "References used in the models", ""),
              ("0", "Exit", "")]
    return ui.menu("MAIN MENU — press a number", items)


def open_view(key):
    title, _, mod, name = VIEWS[key]
    mod.print_calculations()
    print()
    ui.note("Controls: drag a slider · click its RED DOT to return to the default · R resets everything · "
            "Space pauses the animation · close the window to come back to this menu.")
    ui.pause()
    try:
        launch(mod.build, name)
    except Exception as exc:                      # keep the menu alive whatever happens in a window
        print(ui.red(f"  The window closed with an error: {exc}"))


def all_calculations():
    for k in "123456":
        VIEWS[k][2].print_calculations()
    noise.print_calculations()
    block.print_calculations()


def export_all():
    os.makedirs("results", exist_ok=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        all_calculations()
        print_references()
    text = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
    with open(os.path.join("results", "calculations.txt"), "w", encoding="utf-8") as f:
        f.write(f"{C.PROJECT}\n{C.STUDY}\n" + "".join(f"{n} ({r})\n" for n, r in C.MEMBERS) + text)
    print(ui.green("  ✔ results/calculations.txt"))
    _export_sweeps()
    for k, (title, _, mod, name) in VIEWS.items():
        path = launch(mod.build, name, test_frames=EXPORT_FRAMES.get(k, 40), exercise=False, dpi=200)
        print(ui.green(f"  ✔ {path}") + ui.grey(f"   {title}"))


def _export_sweeps():
    """CSV of every layer's reach vs storm intensity — handy for tables in the article."""
    from resilient_net import models as M
    rows = ["intensity,noise_rise_dB,rain_mm_h,towers_down_pct,surge_x,wind_m_s," +
            ",".join(C.SHORT[l] for l in C.ALL_LAYERS) + ",hybrid_required,hybrid_with_optional"]
    for i in [x / 20 for x in range(21)]:
        s = M.storm_from_intensity(i)
        e = M.evaluate_all(s)
        rows.append(f"{i:.2f},{s['noise_rise']:.2f},{s['rain']:.1f},{s['towers_down']:.1f},{s['surge']:.2f},"
                    f"{s['wind']:.1f}," + ",".join(f"{e['reach'][l]:.4f}" for l in C.ALL_LAYERS) +
                    f",{e['hybrid_core']:.4f},{e['hybrid_ext']:.4f}")
    with open(os.path.join("results", "reach_vs_storm.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")
    print(ui.green("  ✔ results/reach_vs_storm.csv"))


def selftest():
    ok = True
    for k, (title, _, mod, name) in VIEWS.items():
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mod.print_calculations()
            launch(mod.build, f"selftest_{name}", test_frames=15)
            print(ui.green("  ✔ ") + title)
        except Exception as exc:
            ok = False
            print(ui.red(f"  ✖ {title}: {exc!r}"))
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    if "--export" in sys.argv:
        export_all()
        return
    ui.banner()
    ui.boot()
    backend = matplotlib.get_backend().lower()
    if backend in ("agg", "pdf", "svg", "ps", "cairo", "template"):
        print(ui.yellow(f"  ! matplotlib backend '{backend}' cannot open windows. Install tkinter or run "
                        "on a desktop. Figures can still be exported with option 11."))
    while True:
        ch = main_menu()
        if ch == "0":
            print("\n  Thank you. Stay safe.\n")
            return
        if ch in VIEWS:
            open_view(ch)
        elif ch == "10":
            all_calculations()
            ui.pause("Press Enter to return to the menu")
        elif ch == "11":
            print(ui.grey("  Exporting… (about a minute)"))
            backend_before = matplotlib.get_backend()
            matplotlib.use("Agg", force=True)
            try:
                export_all()
            finally:
                matplotlib.use(backend_before, force=True)
            ui.pause("Press Enter to return to the menu")
        elif ch == "12":
            print_references()
            ui.pause("Press Enter to return to the menu")


if __name__ == "__main__":
    main()
