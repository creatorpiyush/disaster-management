"""Console look-and-feel: colours, banner, menus and step-by-step calculation printing."""
import os
import sys
import time

from . import config as C

W = 86
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
if os.name == "nt":
    os.system("")            # enables ANSI escape codes on Windows 10+
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _c(code):
    return (lambda s: f"\033[{code}m{s}\033[0m") if _COLOR else (lambda s: str(s))


bold, dim, red, green, yellow, blue, magenta, cyan, grey = (
    _c("1"), _c("2"), _c("91"), _c("92"), _c("93"), _c("94"), _c("95"), _c("96"), _c("90"))
LAYER_TINT = {C.L_AN: _c("38;5;208"), C.L_MO: blue, C.L_SA: cyan, C.L_UAV: yellow, C.L_MESH: magenta}


def hr(ch="─", col=grey):
    print(col(ch * W))


def type_out(text, delay=0.004):
    if not _COLOR:
        print(text)
        return
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def banner():
    art = [
        r"   ____  ___ ____    _    ____ _____ _____ ____      _   _ _____ _____ ",
        r"  |  _ \|_ _/ ___|  / \  / ___|_   _| ____|  _ \    | \ | | ____|_   _|",
        r"  | | | || |\___ \ / _ \ \___ \ | | |  _| | |_) |   |  \| |  _|   | |  ",
        r"  | |_| || | ___) / ___ \ ___) || | | |___|  _ <    | |\  | |___  | |  ",
        r"  |____/|___|____/_/   \_\____/ |_| |_____|_| \_\   |_| \_|_____| |_|  ",
    ]
    print()
    for line in art:
        print(cyan(line))
    hr("═", cyan)
    print(bold(C.PROJECT.center(W)))
    print(grey(C.STUDY.center(W)))
    hr("═", cyan)
    print(bold("  PROJECT TEAM"))
    for n, r in C.MEMBERS:
        print(f"    • {n:<24} Roll no. {r}")
    hr()


def boot():
    steps = ["Loading propagation models (Hata, ITU-R P.525 / P.618 / P.838)",
             "Loading modulation library (AM, FM, ASK, BPSK, QPSK, 16-QAM)",
             "Loading satellite link budget (GEO / LEO)",
             "Loading supplementary layers (UAV air-to-ground, LoRa mesh)",
             "Calibrating cyclone scenario"]
    for s in steps:
        sys.stdout.write(f"  {grey('›')} {s} ")
        sys.stdout.flush()
        for _ in range(3):
            time.sleep(0.05 if _COLOR else 0)
            sys.stdout.write(grey("."))
            sys.stdout.flush()
        print(" " + green("ok"))


def head(title, tint=cyan):
    print()
    hr("━", tint)
    print(tint(bold("  " + title)))
    hr("━", tint)


def sub(title):
    print()
    print(bold("  ▸ " + title))


def note(text):
    for line in _wrap(text, W - 6):
        print(grey("    " + line))


def calc(label, formula, working, result, unit=""):
    """Print one textbook-style calculation: formula → substituted values → answer."""
    print(f"    {bold(label)}")
    print(f"      {grey('formula ')} {formula}")
    if working:
        print(f"      {grey('values  ')} {working}")
    print(f"      {grey('result  ')} {green(result)} {unit}")


def kv(key, val, good=None):
    v = str(val)
    if good is True:
        v = green(v)
    elif good is False:
        v = red(v)
    print(f"    {key:<44} {v}")


def bar(label, frac, colour=green, width=34):
    frac = max(0.0, min(1.0, float(frac)))
    n = int(round(frac * width))
    print(f"    {label:<30} {colour('█' * n)}{grey('░' * (width - n))} {frac * 100:5.1f} %")


def ask(prompt, valid):
    valid = [str(v) for v in valid]
    while True:
        try:
            s = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Session ended. Thank you.")
            sys.exit(0)
        if s in valid:
            return s
        print(red(f"  ✖  '{s}' is not an option. Please type one of: {', '.join(valid)}"))


def menu(title, items):
    """items: list of (key, label, hint) or None for a divider line."""
    print()
    hr("─")
    print(bold("  " + title))
    hr("─")
    keys = []
    for it in items:
        if it is None:
            print()
            continue
        if isinstance(it, str):
            print(grey("  " + it))
            continue
        k, lab, hint = it
        keys.append(k)
        print(f"   {bold(cyan(f'[{k:>2}]'))}  {lab:<46} {grey(hint)}")
    hr("─")
    nums = sorted(int(k) for k in keys if k.isdigit())
    rng = f"{nums[0]}–{nums[-1]}" if nums else ", ".join(keys)
    return ask(f"  Enter your choice ({rng}) ➜ ", keys)


def pause(msg="Press Enter to open the interactive simulation"):
    try:
        input(grey(f"\n  {msg} ↵ "))
    except (EOFError, KeyboardInterrupt):
        print()


def _wrap(text, width):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + ([line] if line else [])
