# User manual

This is the full manual for the Gangtok disaster-network simulator. It goes window by window: what each panel shows, what every control does, and what to look for.

- New to the project? Read [GUIDE_SIMPLE.md](GUIDE_SIMPLE.md) first for the story in plain words.
- Want the code layout and data credits? See [README.md](README.md).

## Contents

1. [Install and start](#1-install-and-start)
2. [Command-line options](#2-command-line-options)
3. [The console menu](#3-the-console-menu)
4. [Controls that work in every window](#4-controls-that-work-in-every-window)
5. [The storm variables](#5-the-storm-variables)
6. [Window guide, menu 1 to 9](#6-window-guide-menu-1-to-9)
7. [Live data hub, menu 13](#7-live-data-hub-menu-13)
8. [Report tools, menu 10 to 12](#8-report-tools-menu-10-to-12)
9. [Workflows for the article](#9-workflows-for-the-article)
10. [Changing the assumptions](#10-changing-the-assumptions)
11. [Troubleshooting](#11-troubleshooting)
12. [Files the program writes](#12-files-the-program-writes)
13. [Simple version](#13-simple-version)

---

## 1. Install and start

You need Python 3.9 or newer with Tk (the python.org installers include it). The only packages are numpy and matplotlib.

**Mac / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Windows**
```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

You only create the environment and install once. After that, run `source .venv/bin/activate` (or `.venv\Scripts\activate`) in each new terminal, then `python main.py`.

To check that everything works, run `python main.py --selftest`. You should see 15 lines starting with `ok`.

## 2. Command-line options

| Command | What it does |
|---|---|
| `python main.py` | Opens the menu. Press a number and Enter. |
| `python main.py --live` | Skips the main menu and opens the live data hub (menu 13). |
| `python main.py --lite` | Runs the animations at a slower frame rate for weak laptops. Results are the same. Combine it with other options, for example `--live --lite`. |
| `python main.py --export` | No windows. Saves every figure to `figures/` and every calculation to `results/`. Takes about a minute. |
| `python main.py --selftest` | No windows. Runs every view for a few frames, pushes every slider to both ends, and reports `ok` or `FAIL`. Live views use the bundled offline samples, so no internet is needed. Exit code is 0 when all pass. |

## 3. The console menu

When you pick a window, the console first prints that layer's calculations (formula, values, result, the way you would write them in an exam). Read them, then press Enter to open the window. Close the window to come back to the menu.

```
SYSTEM OVERVIEW
   1  Block diagram (animated, with failover)
THE THREE REQUIRED LAYERS
   2  Layer 1: Analog emergency radio (AM / FM)
   3  Layer 2: Digital mobile network
   4  Layer 3: Satellite backup
OPTIONAL EXTENSIONS (could complement the required layers)
   5  Supplementary A: UAV aerial base station
   6  Supplementary B: LoRa / D2D mesh
ANALYSIS AND SIMULATION
   7  Comparison of all layers + hybrid
   8  Noise & signal-quality lab
   9  Live disaster simulation
LIVE DATA
  13  Live data hub
REPORT TOOLS
  10  Print every calculation
  11  Export all figures + calculations
  12  References used in the models
   0  Exit
```

If a window crashes, the menu prints `Window crashed: ...` and carries on. One broken plot never closes the program.

## 4. Controls that work in every window

| Control | Action |
|---|---|
| Slider | Drag it. All panels update straight away. |
| Red dot on a slider | Marks the default value. Click the dot to snap back to it. |
| **R** key | Resets every control in the window. |
| **Space** key | Pauses or plays the animation. Sliders still work while paused. |
| Reset button | Same as **R**. Its label varies ("Reset all", "Reset to red dots", "Repair everything"). |
| Play / pause button | Same as **Space**. |
| Close the window | Goes back to the menu. |

The animation speeds itself down on a slow computer so the sliders stay responsive. If it still stutters, pause with **Space** or restart with `--lite`.

## 5. The storm variables

Most windows share five storm variables. Their defaults (the red dots) live in `resilient_net/config.py` under `STORM`.

| Variable | Default | Meaning |
|---|---|---|
| Noise rise | 6 dB | How much the noise floor goes up: lightning, static, diesel generators |
| Rain rate | 80 mm/h | IMD calls 100 mm/h or more a cloudburst |
| Towers down | 40 % | Cell sites off-air: fibre cut by landslides, power lost, site buried |
| Call surge | 3 × | Call traffic compared with a normal day |
| Wind | 12 m/s | Thunderstorm gusts funnelled along the valleys |

Menu 7 and the CSV export drive all five from one **hazard intensity** knob from 0 to 1:

```
noise_rise = 2 + 10·i     rain = 200·i     towers_down = 100·i     surge = 1 + 5·i     wind = 4 + 20·i
```

Intensity 0.4 gives back the defaults above.

### How "hybrid" is worked out

Each layer gives a **reach**: the share of citizens it can serve (0 to 1). Layers fail for different reasons, so they are treated as independent:

- **Hybrid, 3 required layers** (two-way) = 1 − (1 − mobile)·(1 − satellite). Analog is one-way, so it only counts as an alert.
- **Hybrid, with optional layers** (two-way) = 1 − product of (1 − reach) over mobile, satellite, UAV and mesh.
- **Alert reach** = the same formula over all five layers, including analog.

---

## 6. Window guide, menu 1 to 9

### Menu 1: Block diagram

**Shows** the transmitter, channel and receiver of every layer, with packets moving through each chain.

| Control | Effect |
|---|---|
| "Break a channel" tick boxes | FM mast off-air, fibre cut by landslides, satellite rain fade, drones grounded by rain, and mesh batteries flat. Tick one and watch the traffic reroute to the next layer (failover). |
| "Show" | Required + optional layers, or required layers only. |
| Repair everything | Unticks all failures. |

**Try:** tick "Fibre cut by landslides". Mobile packets stop and the traffic moves to satellite. Then add "Satellite rain fade" to see what is left.

### Menu 2: Layer 1, analog emergency radio

**Panels:** live AM/FM transmitter output, spectrum around the carrier (Bessel sidebands for FM), what the listener hears after noise, and coverage on the real Gangtok terrain (ridge diffraction, ITU-R P.526).

| Slider | Default | Effect |
|---|---|---|
| AM index μ | 0.80 | Modulation depth. Above 1 would over-modulate, so the slider stops at 1. |
| FM deviation Δf | 5 kHz | Wider deviation means more sidebands and a better output SNR above threshold. |
| Message freq fm | 3 kHz | Audio tone frequency. Sets β = Δf / fm. |
| Tx power | 0.1 kW | Transmitter power. |
| District edge | 20 km | Distance of the farthest listener. |
| Storm noise rise | 6 dB | Raises the noise floor. |
| Ridge loss at edge | 23 dB | Extra loss from ridges, the median over homes. |

**Look for:** the FM threshold. Above it FM sounds much cleaner than AM. Below it FM collapses quickly. On the map, the shadowed valleys behind ridges are the homes the mast cannot reach.

### Menu 3: Layer 2, digital mobile network

**Panels:** sampling and quantisation (live), SQNR vs bits, received constellation at the cell edge, BER vs Eb/N0 (Monte-Carlo dots on the theory curves), cell layout with sites cut off by landslides, and call blocking (Erlang-B).

| Control | Default | Effect |
|---|---|---|
| Sampling fs | 8 kHz | Below 2W (6.8 kHz for 3.4 kHz voice) the panel warns about aliasing and shows the alias frequency. |
| Bits per sample n | 8 | More bits give more quantisation levels: about 6 dB of SQNR per bit. |
| Cell-split level | 0 | Splits cells into smaller ones. More capacity, more sites to lose. |
| Sites off-air | 40 % | Towers knocked out. The surviving cells must stretch, so the edge signal gets weaker. |
| Call surge | 3 × | Offered traffic. Watch the blocking probability climb past the 2 % design target. |
| Storm noise rise | 6 dB | Lowers Eb/N0 at the cell edge. |
| Modulation | QPSK | ASK (OOK), BPSK, QPSK or 16-QAM. Higher orders carry more bits but need more Eb/N0. |

**Look for:** the readout line `load ... E -> blocking ...`. During a surge, blocking (not signal) is usually what stops calls.

### Menu 4: Layer 3, satellite backup

**Panels:** live link geometry (GEO or LEO), the link-budget waterfall ("where the decibels go"), rain fade and margin, and a sky view with the real mountain skyline.

| Control | Default | Effect |
|---|---|---|
| Rain rate | 80 mm/h | Rain fade (ITU-R P.838 / P.839). The rain path is shorter because the terminal sits at 1.6 km. |
| Elevation angle | 57.5° | The Indian GEO slot at 83° E, seen from Gangtok. Lower angles mean a longer path through rain. |
| Satellite EIRP | 50 dBW | Satellite transmit strength. |
| Dish diameter | 1.2 m | Bigger dish, more gain. |
| Data rate | 256 kbps | Higher rate needs more power for the same Eb/N0. |
| Terminal HPA | 20 W | Uplink amplifier power. |
| Band | Ku | C band barely notices rain. Ka band fades badly. |
| Orbit | GEO | LEO is closer: less path loss and delay, but it moves. |
| Terminal site | Gangtok ridge | Also Singtam valley and Dikchu gorge. Valley sites lose more sky to the ridges. |

**Look for:** the margin bar. Positive margin means the link holds. Push rain past 100 mm/h in Ka band and watch it go negative.

### Menu 5: Optional A, UAV aerial base station

**Panels:** side view of a drone over the real Ranipool valley, top view of drones over Gangtok, path loss vs distance, coverage radius vs altitude (star = optimum), line-of-sight probability vs elevation angle, and flight availability vs wind.

| Control | Default | Effect |
|---|---|---|
| Altitude h | 500 m | Too low and ridges block it. Too high and path loss grows. |
| User Tx power | 23 dBm | Phone uplink power, which limits the cell radius. |
| Number of drones | 6 | More drones cover more users. |
| Valley wind gusts | 12 m/s | Above the drone's limit it is grounded. |
| Rain rate | 80 mm/h | Heavy rain also grounds drones. |
| Drone wind limit | 15 m/s | What the airframe can handle. |
| Storm noise rise | 6 dB | Raises the noise floor. |
| Launch site altitude | 1600 m | Thin air at altitude shortens endurance. |
| Environment | Urban | Al-Hourani channel parameters (suburban, urban, dense urban, high-rise urban). |

**Look for:** the side view text says `FLYING` or grounded. Green lines are clear paths and red lines are blocked by a ridge or out of range.

### Menu 6: Optional B, LoRa / D2D mesh

**Panels:** live SOS flooding over the real terrain, connectivity vs number of radios, time on air with the 1 % duty-cycle budget, ALOHA collisions, and the spreading-factor trade-off.

| Control | Default | Effect |
|---|---|---|
| Spreading factor SF | 9 | Higher SF reaches farther but is slower and stays on air longer. |
| Tx power | 20 dBm | IN865 band allows up to 1 W. |
| Radios deployed | 120 | Across 8 × 8 km. Too few and the mesh breaks into islands. |
| Radios with battery | 70 % | Dead radios cannot relay. |
| Messages per radio per hour | 12 | More traffic means more collisions. |
| Storm noise rise | 6 dB | Shortens the hop range. |
| New SOS button | | Starts a new message from a random radio. |

**Look for:** "nodes reached x / y" on the map. Ridges block hops, so the message has to go around them.

### Menu 7: Comparison and hybrid

**Panels:** radar profile of each layer, citizens reached by each layer and by the hybrid, reach vs hazard intensity, data rate vs latency (bubble size = reach), and who serves a citizen (failover order).

| Control | Default | Effect |
|---|---|---|
| Hazard intensity | 0.40 | One knob for all five storm variables (see section 5). |
| Phase of the disaster | During cloudburst | Also "Glacial-lake flood" (rain eases, more towers down) and "Recovery (first 72 h)". |
| Where in Gangtok | Whole district | Also ridge town, hill-slope villages, valley floor (Teesta). |
| Optional layers | UAV and Mesh ticked | Untick to see the 3 required layers alone. |

**Look for:** the two hybrid bars side by side. Choose "Valley floor" and "Glacial-lake flood". Required layers alone reach roughly 4 in 10 people. With the optional layers it is about 3 in 4.

### Menu 8: Noise and signal-quality lab

**Panels:** signal through the noisy channel, noise histogram (with kurtosis), eye diagram, constellation (red = wrong decision), live BER vs theory, and a capacity panel showing where each layer operates.

| Control | Default | Effect |
|---|---|---|
| Eb/N0 | 8 dB | Signal-to-noise per bit. |
| Roll-off α | 0.35 | Raised-cosine pulse shape. Smaller α means a narrower spectrum but a tighter eye. |
| Impulsive noise | 0 % | Share of samples hit by a storm impulse. |
| Impulse strength | 15 dB | How big the impulses are. |
| Modulation | BPSK | Same list as menu 3. |

**Look for:** with impulsive noise at 0, the measured BER converges to the theory curve and the kurtosis reads about 3 (Gaussian). Add impulses and the kurtosis jumps, the eye closes, and the BER sits above theory.

### Menu 9: Live disaster simulation

The best window to show someone first. It plays 96 hours over the real map:

1. A cloudburst cell drifts from south-west to north-east, peaking at about hour 22.
2. Slopes steeper than 30° under heavy rain slide. Roads break, and the fibre along them breaks too. A cell site whose fibre route is cut goes off-air once its battery runs out.
3. Around hour 44 the glacial-lake flood runs down the Teesta at about 15 km/h.
4. Drones launch when wind and rain allow. Road crews clear cuts and sites come back.

**Map colours:** each citizen dot is coloured by who serves them, in the order mobile, UAV, satellite, mesh. Orange means analog alert only, grey means no contact. Brown crosses are landslides, red lines are cut roads and blue is the flood.

| Control | Default | Effect |
|---|---|---|
| Cloudburst peak | 130 mm/h | Peak rain. More rain, more landslides. |
| Simulation speed | 1.00 × | Playback speed. |
| Road crews | 0.6 cuts/h | How fast cuts are cleared. 0 means no repair. |
| Site battery backup | 6 h | Hours a site runs after losing mains power. |
| GLOF flood height | 30 m | Flood depth in the valley. |
| Layers and hazards | UAV, Mesh, GLOF ticked | Untick to remove a layer or turn off the flood. |
| Play/Pause, Restart | | Restart goes back to hour 0. |

**Readout (top right):** sites on air and on battery, road cuts, call blocking, two-way reach (hybrid and required-only), two-way reach on the valley floor, alert-only and no-contact shares. The bottom graph tracks two-way contact over time.

**Try:** set battery to 0 h and road crews to 0. Then set battery to 24 h and compare how deep the dip goes.

---

## 7. Live data hub, menu 13

Open it from the main menu with 13, or straight away with `python main.py --live`. All sources are free and need no key.

| Key | Window | Source | Controls |
|---|---|---|---|
| 1 | Weather and its effect on every layer | Open-Meteo | Hour slider (−72 to +72 h, 0 = now); peak/hourly rain factor (default 2.0, turns hourly totals into short-burst peaks); Period: live now ± 3 days, replay of the Oct 2023 GLOF week, or replay of the wettest days of the last monsoon; "Back to now"; "Sweep" plays through the hours. |
| 2 | Real satellites over Gangtok | CelesTrak | Clock speed (1 to 600 × real time, default 60); minimum elevation (default 25°); terminal site; tick boxes for each constellation (Starlink, OneWeb, Iridium, GEO, stations); "Now" jumps back to real time. Ridges are drawn in brown. |
| 3 | Disasters and earthquakes | GDACS, NASA EONET, USGS | Radius around Gangtok (default 500 km); days back (default 90); world map filter by disaster type. Shows a Gutenberg–Richter b-value for quakes near Sikkim. |
| 4 | Space weather | NOAA SWPC | Play/pause only. Kp index, GOES X-ray flares and F10.7, with what each means for every layer. |
| 5 | Terrain path profile | OpenTopoData SRTM 30 m | Frequency (default 100 MHz); k-factor (refraction, default 4/3); Tx mast and Rx antenna heights; path picker. Shows earth curvature, line of sight, the first Fresnel zone and the knife-edge loss J(v). |
| 6 | Save a dated snapshot | all of the above | No window. Writes `results/live_snapshot_<date>_<time>/` (see section 12). |

### Online and offline

Every live window tries three things in order:

1. **Download** fresh data (each source has its own cache age, from 30 minutes for weather to a year for the 2023 archive).
2. **Cached:** the last download in `live_cache/`.
3. **Bundled sample** in `resilient_net/data/live_samples/`.

A badge on every figure tells you which one you are looking at:

| Badge | Meaning |
|---|---|
| `Live: fetched <time>` | Fresh download |
| `CACHED · fetched <time>` | Recent download reused |
| `OFFLINE · last fetched <time>` | Download failed, older cache used |
| `OFFLINE · bundled sample (<time>)` | No cache, shipped sample used |

To force offline mode (for example in a lab with blocked internet), set `LIVE_OFFLINE=1` before running:

```bash
LIVE_OFFLINE=1 python main.py --live
```

## 8. Report tools, menu 10 to 12

| Key | What it does |
|---|---|
| 10 | Prints every calculation from menus 1 to 8 to the console. |
| 11 | Same as `--export`: saves all nine figures at 200 dpi, `results/calculations.txt` and `results/reach_vs_storm.csv`. The menu 9 figure is taken at frame 190 (about hour 47, as the flood hits). |
| 12 | Lists the references behind each model. Run `python tools/check_references.py` to check every link still opens. |

## 9. Workflows for the article

**Get every figure and number in one go**
1. `python main.py --export`
2. Figures are in `figures/01_...png` to `figures/09_...png`.
3. Formulas with worked values are in `results/calculations.txt`.
4. The reach-vs-storm table is in `results/reach_vs_storm.csv` (21 rows, intensity 0 to 1 in steps of 0.05).

**Freeze today's live data**
1. `python main.py --live`, then press 6.
2. Cite from `data_sources.txt` in the new snapshot folder. It has the access date filled in.

**Get a figure with your own settings**
1. Open the window and set the sliders.
2. Use the save icon in the matplotlib toolbar at the bottom of the window.

**Compare zones for a table**
1. Open menu 7.
2. Change "Where in Gangtok" and "Phase" and note the hybrid bars for each combination.

## 10. Changing the assumptions

The terrain, roads, rivers and towns are real. Hazard levels and network parameters are design assumptions. To change them, edit `resilient_net/config.py`:

| Block | What it holds |
|---|---|
| `STORM` | The five storm defaults (section 5) |
| `ANALOG` | Carrier, power, distance, modulation, antenna gains, noise figure, clutter and median ridge loss |
| `DIGITAL` | PCM settings, 900 MHz Hata link, cell radius, channels per cell, Erlang load, grade of service |
| `SAT` | Band, orbit, elevation, EIRP, dish, data rate, required Eb/N0, system temperature |
| `UAV` | Altitude, frequency, power, sensitivity, environment, fleet size, wind limit, endurance |
| `MESH` | SF, bandwidth, power, node count, battery share, payload, message rate, area |
| `MEMBERS` | Team names shown on the export |

The slider red dots follow these values. After editing, run `python main.py --selftest`, then `--export` to refresh the figures.

The equations themselves are in `resilient_net/models.py`, one function per layer, with the source noted next to each.

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `This program needs numpy and matplotlib.` | The virtual environment is not active or the install was skipped. Activate it and run `pip install -r requirements.txt`. |
| `warning: matplotlib backend 'agg' can't open windows (no tkinter?)` | Python was built without Tk. Install Python from python.org (or `brew install python-tk` on a Homebrew Mac). Menu 11 still exports figures meanwhile. |
| Window is bigger than the screen | Windows shrink to fit screens down to 1366 × 768. On smaller screens, maximise the window. |
| Animation stutters or sliders lag | Press **Space** to pause, or restart with `--lite`. |
| Menu colours show as `[32m` codes on Windows | Use Windows Terminal instead of the old Command Prompt. |
| Live window shows OFFLINE | The source could not be reached. Check the internet, or carry on: the numbers come from the cache or sample. |
| `Could not prepare the data: ...` in the live hub | That source failed and had no fallback. Try another key, or run the hub with `LIVE_OFFLINE=1`. |
| `Window crashed: ...` | Run `python main.py --selftest` to see which view fails, and share the `FAIL` line. |
| Window closed but the menu hangs (macOS) | Press Enter once. If it is still stuck, press Ctrl+C and restart. |

## 12. Files the program writes

| Path | Written by | Safe to delete? |
|---|---|---|
| `figures/01_...png` to `09_...png` | `--export`, menu 11 | Yes, re-export to rebuild |
| `figures/simple.png` | `python simple.py --save` | Yes |
| `figures/selftest_*.png` | `--selftest` | Yes (git ignores them) |
| `results/calculations.txt` | `--export`, menu 11 | Yes |
| `results/reach_vs_storm.csv` | `--export`, menu 11 | Yes |
| `results/live_snapshot_<date>_<time>/` | live hub, key 6 | Keep any snapshot you cite in the article |
| `live_cache/` | live hub | Yes (git ignores it). Rebuilt on the next download. |

## 13. Simple version

`simple.py` is a one-window version that covers only what the assignment asks for: the three required layers and the hybrid. Use it for a quick demo, a viva, or the article appendix. It needs only numpy and matplotlib and imports nothing from `resilient_net`.

```bash
python simple.py            # window with sliders
python simple.py --print    # calculations for all three phases, no window
python simple.py --save     # writes figures/simple.png (200 dpi)
```

**Panels:** analog output SNR vs distance (FM and AM, with the FM threshold), mobile BER at the cell edge with Erlang-B call blocking, satellite margin vs rain for C, Ku and Ka band, and bars for each layer's reach plus the hybrid. The panel on the right shows the storm values after the phase is applied, each layer's reach, and the hybrid and alert reach.

| Control | Range | Default (red dot) |
|---|---|---|
| Rain | 0 to 200 mm/h | 80 |
| Towers down | 0 to 95 % | 40 |
| Noise rise | 0 to 25 dB | 6 |
| Phase | cloudburst / glacial-lake flood / recovery | cloudburst |

Press **R** to reset. Call surge (3 ×) and wind (12 m/s) have no slider, so the phase is the only thing that changes them. It uses the same rules as menu 7. For example, the flood phase multiplies rain by 0.3 and adds 12 % to towers down.

**How it differs from the full simulator:** there is no terrain. Analog uses the median ridge loss (23 dB) for every home, and the satellite ignores the mountain skyline. Both layers come out a little more optimistic than in menu 7. The equations and defaults are the same.

**Keeping it in step:** `simple.py` has its own copy of the equations and defaults. `python main.py --selftest` checks that its defaults match `config.py`, its phase rules match menu 7, and each layer's reach matches `models.py` at 9 settings. If you change an equation or a default in one place, change it in the other too, or the self-test fails.
