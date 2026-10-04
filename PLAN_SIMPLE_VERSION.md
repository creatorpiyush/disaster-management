# Plan: a simpler version of the simulator

## Goal

One self-contained file, `simple.py`, that covers only what the assignment asks for: the three required layers, noise, and the hybrid result. It opens one window with three storm sliders and a phase picker. It runs in a few seconds on any laptop.

It is for:
- explaining the project in a viva or class demo without walking through 14 windows
- a teammate who wants to read the whole logic in one sitting
- the article appendix, since it only needs numpy and matplotlib
- a fallback if the live APIs or a slow laptop cause trouble on the day

The full simulator stays as it is. Nothing in `resilient_net/` changes.

## Decisions (agreed)

| Question | Answer |
|---|---|
| Controls | Three separate sliders: rain, towers down, noise rise. Shows cause and effect better than one intensity knob. |
| Self-contained? | Yes. `simple.py` imports only numpy, math and matplotlib. It can be pasted into the appendix as is. |
| Phase picker? | Yes. During cloudburst, glacial-lake flood, recovery (first 72 h). |

## What it keeps and what it drops

| Keep | Drop |
|---|---|
| Analog, mobile and satellite layers | UAV and mesh layers (optional anyway) |
| Rain, towers down and noise sliders | Real terrain, OSM roads, the city map (menu 9) |
| Phase picker | Zone picker (whole district only) |
| Hybrid reach of the 3 required layers | Live data hub and all downloads |
| BER vs Eb/N0 with the noise effect | Animations, eye diagram, Monte-Carlo |
| Rain fade and satellite margin | Sky view, link geometry, block diagram |
| Erlang-B call blocking | Band, orbit, modulation and dish pickers (fixed at config defaults) |
| Printed calculations | Export, snapshot and menu system |

## Copying the equations

`simple.py` copies the functions it needs from `resilient_net/models.py`, unchanged apart from trimming unused return fields:

- helpers: `db`, `undb`, `qfunc`, `fspl_db`, `erlang_b`
- analog: `man_made_noise_fa`, `fm_metrics`, `am_metrics`, `analog_link`, `fm_output_snr`, `am_output_snr`, `analog_layer`
- mobile: `ber_theory`, `required_ebn0`, `hata_urban`, `mobile_layer` (with the bit rate worked out inline instead of calling `pcm`)
- satellite: `BANDS`, `slant_range_km`, `rain_attenuation`, `dish_gain`, `satellite_layer`
- phase: `storm_for` from `views/compare.py`, reduced to the five storm variables

The defaults it needs from `config.py` (ANALOG, DIGITAL, SAT, STORM) go in as one small dict block at the top.

That is about 130 lines of copied code. The whole file should come out around 300 lines.

**Risk:** the copy drifts from `models.py` if someone edits one and not the other. That would put two different numbers in the article.
**Guard:** `main.py --selftest` imports both and checks that `simple.py` gives the same reach as `models.py` for each layer, for a handful of slider and phase settings. The test fails if the difference is more than 1e-9.

**Known difference:** without terrain, analog reach uses the even-disc model with the median ridge loss (23 dB), and satellite reach has no skyline blocking. Both come out a little more optimistic than menu 7. The window subtitle says so.

## Controls

| Control | Range | Default (red dot) |
|---|---|---|
| Rain rate | 0 to 200 mm/h | 80 |
| Towers down | 0 to 95 % | 40 |
| Noise rise | 0 to 25 dB | 6 |
| Phase | cloudburst / flood / recovery | cloudburst |

R resets everything.

Surge (3 ×) and wind (12 m/s) have no slider. They stay at the defaults, and the phase changes them the same way menu 7 does.

How the phase acts on the slider values (same rules as `views/compare.py`):

| Phase | Rain | Towers down | Noise | Surge | Wind |
|---|---|---|---|---|---|
| During cloudburst | as set | as set | as set | 3 × | 12 m/s |
| Glacial-lake flood | × 0.3 | + 12 (max 95) | as set | × 1.3 | max 8 |
| Recovery (first 72 h) | × 0.05 | × 0.85 | × 0.5 | × 1.2 | max 6 |

The readout shows the effective values after the phase, so nobody wonders why 80 mm/h turned into 24.

Sliders and radio buttons use `matplotlib.widgets` directly, not `resilient_net/widgets.py`, so the file stays self-contained. Matplotlib marks a slider's starting value with a line, which stands in for the red dot.

## The window

One figure: 2 × 2 panels, a control strip at the bottom and a readout on the right.

| Panel | Shows | Reacts to |
|---|---|---|
| Top left: Analog | FM and AM output SNR vs distance, with the 20 dB speech line and the FM threshold | noise |
| Top right: Mobile | BER vs Eb/N0 for BPSK, QPSK and 16-QAM, a dot at the current cell-edge Eb/N0, and Erlang-B blocking in a text line | towers down, noise, phase (surge) |
| Bottom left: Satellite | Margin vs rain rate for C, Ku and Ka band, a dot at the current rain | rain, phase |
| Bottom right: Hybrid | Bars for analog, mobile, satellite and hybrid (3 required) | everything |

Readout: the effective storm values, each layer's reach, hybrid two-way reach (`1 - (1 - mobile)·(1 - satellite)`), and alert reach including analog.

## Tasks

### 1. Equations and console output
- Create `simple.py` with the copied functions and the defaults block.
- Add `evaluate(rain, towers, noise, phase)`, which returns each layer's reach and the hybrid.
- `python simple.py --print` prints one block per layer: formula, values, result.
- **Done when** the drift check (task 4) passes for the defaults.

### 2. The four panels, static
- Draw the four panels at the default settings.
- `python simple.py --save` writes `figures/simple.png` at 200 dpi.
- **Done when** the PNG reads clearly at A4 width.

### 3. Sliders and phase picker
- Add the three sliders, the phase radio buttons, and the R key.
- Any change redraws the dots, bars, text and readout. The curves only redraw when noise changes.
- **Done when** every control updates the right panels with no visible lag on a slow laptop.

### 4. Drift check and docs
- Add a `simple` step to `selftest()` in `main.py`:
  - render `simple.py` once headless
  - compare its reach with `models.py` at 3 phases × 3 slider settings, with a tolerance of 1e-9
- Add a short "Simple version" section to `README.md` and `MANUAL.md`: what it shows, how to run it, and how it differs from the full version.
- **Done when** `python main.py --selftest` shows 15 `ok` lines, and changing a constant in only one of the two files makes it fail.

## Estimate

About half a day. Tasks 1 to 3 in one sitting, task 4 after.
