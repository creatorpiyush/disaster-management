#!/usr/bin/env python3
"""Disaster-resilient hybrid comms network for Gangtok - simulator.

python main.py [--export | --selftest | --live | --lite]
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

if "--lite" in sys.argv:
    os.environ["RN_LITE"] = "1"
if "--export" in sys.argv or "--selftest" in sys.argv:
    matplotlib.use("Agg")

# these have to come after matplotlib.use() above
from resilient_net import config as C, ui  # noqa: E402
from resilient_net.references import print_references  # noqa: E402
from resilient_net.views import analog, block, city, compare, digital, mesh, noise, satellite, uav  # noqa: E402
from resilient_net.views._base import launch  # noqa: E402

VIEWS = {
    "1": ("Block diagram (animated, with failover)", "Tx → channel → Rx", block, "01_block_diagram"),
    "2": ("Layer 1: Analog emergency radio (AM / FM)", "required", analog, "02_layer1_analog_radio"),
    "3": ("Layer 2: Digital mobile network", "required", digital, "03_layer2_mobile_network"),
    "4": ("Layer 3: Satellite backup", "required", satellite, "04_layer3_satellite"),
    "5": ("Supplementary A: UAV aerial base station", "optional extension", uav, "05_suppA_uav"),
    "6": ("Supplementary B: LoRa / D2D mesh", "optional extension", mesh, "06_suppB_mesh"),
    "7": ("Comparison of all layers + hybrid", "radar, sweeps, failover", compare, "07_comparison"),
    "8": ("Noise & signal-quality lab", "SNR, BER, eye diagram", noise, "08_noise_lab"),
    "9": ("Live disaster simulation", "cloudburst, landslides, flood", city, "09_live_city_simulation"),
}
EXPORT_FRAMES = {"9": 190}  # frame 190 is ~47 h in, right when the flood hits


def main_menu():
    def row(k):
        return (k, VIEWS[k][0], VIEWS[k][1])

    items = ["SYSTEM OVERVIEW", row("1"),
             None, "THE THREE REQUIRED LAYERS", *map(row, "234"),
             None, "OPTIONAL EXTENSIONS (could complement the required layers)", *map(row, "56"),
             None, "ANALYSIS AND SIMULATION", *map(row, "789"),
             None, "LIVE DATA (needs internet, uses saved data if offline)",
             ("13", "Live data hub", "weather, satellites, disasters, space weather, terrain"),
             None, "REPORT TOOLS",
             ("10", "Print every calculation", "formula, values, result"),
             ("11", "Export all figures + calculations", "./figures, ./results"),
             ("12", "References used in the models", ""),
             ("0", "Exit", "")]
    return ui.menu("MAIN MENU - press a number", items)


def open_view(key):
    title, _, mod, name = VIEWS[key]
    mod.print_calculations()
    print()
    ui.controls_help()
    ui.pause()
    try:
        launch(mod.build, name)
    except Exception as exc:  # don't let one broken plot kill the whole menu
        print(ui.red(f"  Window crashed: {exc}"))


def all_calculations():
    block.print_calculations()
    for k in "234567":
        VIEWS[k][2].print_calculations()
    noise.print_calculations()


def export_all():
    os.makedirs("results", exist_ok=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        all_calculations()
        print_references()
    text = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
    with open(os.path.join("results", "calculations.txt"), "w", encoding="utf-8") as f:
        f.write(f"{C.PROJECT}\n{C.STUDY}\n" + "".join(f"{n} ({r})\n" for n, r in C.MEMBERS) + text)
    print(ui.green("  saved results/calculations.txt"))
    _export_sweeps()
    for k, (title, _, mod, name) in VIEWS.items():
        path = launch(mod.build, name, test_frames=EXPORT_FRAMES.get(k, 40), exercise=False, dpi=200)
        print(ui.green(f"  saved {path}") + ui.grey(f"   ({title})"))


def _export_sweeps():
    # reach of each layer as the storm gets worse - used for the tables in the article
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
    print(ui.green("  saved results/reach_vs_storm.csv"))


def selftest():
    from resilient_net.live import hub
    ok = True
    for k, (title, _, mod, name) in VIEWS.items():
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mod.print_calculations()
            launch(mod.build, f"selftest_{name}", test_frames=15)
            print(ui.green("  ok    ") + title)
        except Exception as exc:
            ok = False
            print(ui.red(f"  FAIL  {title}: {exc!r}"))
    try:
        check_simple()
        print(ui.green("  ok    ") + "Simple version (simple.py)")
    except Exception as exc:
        ok = False
        print(ui.red(f"  FAIL  Simple version (simple.py): {exc!r}"))
    return hub.selftest() and ok


def check_simple():
    # simple.py has its own copy of the equations, make sure it still gives the same numbers
    import matplotlib.pyplot as plt
    import simple
    from resilient_net import models as M
    from resilient_net.views import compare
    for name in ("STORM", "ANALOG", "DIGITAL", "SAT"):
        mine, full = getattr(simple, name), getattr(C, name)
        diff = [k for k in mine if mine[k] != full[k]]
        assert not diff, f"simple.{name} differs from config.py: {diff}"
    for phase in simple.PHASES:
        a, b = simple.storm_for(80, 40, 6, phase), compare.storm_for(0.4, phase)
        assert all(abs(a[k] - b[k]) < 1e-9 for k in a), f"phase rules differ for {phase}"
        for rain, towers, noise in ((0, 0, 0), (80, 40, 6), (200, 95, 25)):
            r = simple.evaluate(rain, towers, noise, phase)
            s = r["storm"]
            want = dict(
                an=M.analog_layer(**{**C.ANALOG, "noise_rise": s["noise_rise"], "wind": s["wind"]}),
                mo=M.mobile_layer(**{**C.DIGITAL, "mod": "QPSK", "towers_down": s["towers_down"],
                                     "surge": s["surge"], "noise_rise": s["noise_rise"]}),
                sa=M.satellite_layer(**{**C.SAT, "rain": s["rain"], "wind": s["wind"]}))
            for k, w in want.items():
                assert abs(r[k]["reach"] - w["reach"]) < 1e-9, \
                    f"{k} reach {r[k]['reach']:.6f} != models.py {w['reach']:.6f} ({phase}, {rain}/{towers}/{noise})"
    fig, sliders, radio = simple.build()
    for sl in sliders.values():
        sl.set_val(sl.valmin)
        sl.set_val(sl.valmax)
    for i in range(len(simple.PHASES)):
        radio.set_active(i)
    fig.canvas.draw()
    plt.close(fig)


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    if "--export" in sys.argv:
        export_all()
        return
    if "--live" in sys.argv:
        from resilient_net.live import hub
        hub.menu()
        return
    ui.banner()
    backend = matplotlib.get_backend().lower()
    if backend in ("agg", "pdf", "svg", "ps", "cairo", "template"):
        print(ui.yellow(f"  warning: matplotlib backend '{backend}' can't open windows (no tkinter?). "
                        "Option 11 still exports the figures."))
    while True:
        ch = main_menu()
        if ch == "0":
            print("\n  bye!\n")
            return
        if ch in VIEWS:
            open_view(ch)
            continue
        if ch == "13":
            from resilient_net.live import hub
            hub.menu()
            continue

        if ch == "10":
            all_calculations()
        elif ch == "11":
            print(ui.grey("  Exporting, takes about a minute..."))
            old = matplotlib.get_backend()
            matplotlib.use("Agg", force=True)
            try:
                export_all()
            finally:
                matplotlib.use(old, force=True)
        elif ch == "12":
            print_references()
        ui.pause("Press Enter to go back")


if __name__ == "__main__":
    main()
