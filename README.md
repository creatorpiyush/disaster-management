# Disaster-Resilient Hybrid Communication Network: Interactive Simulator

This simulator models **Gangtok, Sikkim**, a Himalayan smart city, through a monsoon cloudburst. The cloudburst triggers landslides, and then a glacial-lake outburst flood (GLOF) runs down the Teesta valley.

The terrain is real:
- **Elevation:** NASA SRTM.
- **Roads, rivers and towns:** OpenStreetMap.

Each layer of the network opens as a live, animated window with sliders. Menu 13 adds live open data, such as today's weather, real satellites overhead, current disasters and space weather.

New to this? Read [GUIDE_SIMPLE.md](GUIDE_SIMPLE.md) first. It explains everything in plain language.

## Run it

```bash
python3 -m venv .venv               # create a virtual environment (first time only)
source .venv/bin/activate           # activate it (in every new terminal)
pip install -r requirements.txt     # install numpy + matplotlib (first time only)
python main.py              # menu: press a number, a live window opens
python main.py --live       # go straight to the live-data hub (menu 13)
python main.py --lite       # slower animation for low-power laptops (combine with others)
python main.py --export     # saves all figures to ./figures and all calculations to ./results
python main.py --selftest   # runs every window headless (live views use the bundled samples)
```

On Windows, activate with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

### Windows and low-power laptops

- Install Python from python.org (tick "Add Python to PATH"). Its installer includes Tk, which the windows need.
- Then run `py -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements.txt` and `python main.py`.
- Use **Windows Terminal** (the default on Windows 11) so the menu's colours and symbols display properly.
- On a slow computer, run `python main.py --lite`. The animations run at half the frame rate; all results are the same.
- Windows shrink automatically to fit small screens such as 1366 × 768.
- If an animation stutters, press **Space** to pause it. Sliders still update the results.

## Menu

| Key | View | What moves live |
|---|---|---|
| 1 | Block diagram | packets flow through each Tx → channel → Rx chain; break a channel to see the failover |
| 2 | Layer 1: Analog emergency radio (required) | AM/FM waves, Bessel spectrum, simulated demodulation, FM threshold, coverage on the real terrain (ridge diffraction, ITU-R P.526) |
| 3 | Layer 2: Digital mobile network (required) | PCM sampling and aliasing, SQNR, constellation, BER (Monte-Carlo), cells cut off by landslides, Erlang-B |
| 4 | Layer 3: Satellite backup (required) | GEO/LEO geometry, link-budget waterfall, rain fade (shorter rain path at 1.6 km altitude), margin, sky view with the real mountain skyline |
| 5 | Supplementary A: UAV aerial base station (optional) | drone over a real valley cross-section, thin-air endurance, optimal altitude, flying vs wind and rain |
| 6 | Supplementary B: LoRa / D2D mesh (optional) | SOS message flooding over the real terrain (ridges block links), SF trade-off, connectivity, ALOHA |
| 7 | Comparison + hybrid | radar profiles, reach bars, hazard sweep, failover share; zones (ridge town, slopes, valley floor) and phases (cloudburst, GLOF, recovery) |
| 8 | Noise & signal-quality lab | Gaussian + impulsive noise, histogram, eye diagram, live BER that converges to theory |
| 9 | Live disaster simulation | on the real map: cloudburst cell, landslides above the Caine threshold cut roads and the fibre on them, the GLOF runs down the Teesta, drones launch, road crews reopen roads |
| 13 | **Live data hub** (see below) | real-world data from free open APIs |
| 10–12 | Report tools | print all calculations, export figures and CSV, list references |

## Live data hub (menu 13)

All sources are free and need no API key.

| Key | View | Source | Link to the assignment |
|---|---|---|---|
| 1 | Weather → effect on every layer | Open-Meteo (forecast and ERA5 archive) | Real rain drives the landslide threshold, rain fade, drone limits and hybrid reach. It includes two replays: the October 2023 GLOF week, and the wettest days of the last monsoon. |
| 2 | Real satellites over Gangtok | CelesTrak | Starlink, OneWeb, Iridium, GEO (including India's GSAT/INSAT) and the ISS, propagated live. Shows which ones the ridges hide, plus live slant range, FSPL and delay. |
| 3 | Disasters and earthquakes | GDACS, NASA EONET, USGS | World alerts. Earthquakes around Sikkim, with a Gutenberg–Richter b-value. |
| 4 | Space weather | NOAA SWPC | Kp (geomagnetic storms), GOES X-ray flares, F10.7. Explains what each means for every layer. |
| 5 | Terrain path profile | OpenTopoData (SRTM 30 m) | Earth curvature, line of sight, first Fresnel zone and the knife-edge loss J(v) for real paths |
| 6 | Save a dated snapshot | all of the above | Writes `results/live_snapshot_<date>/` with the numbers, figures and citations, ready for the article |

Without internet, the hub uses the last download in `live_cache/`, or else the samples bundled in `resilient_net/data/live_samples/`. Every figure carries a badge (LIVE, CACHED or OFFLINE) saying which one it shows.

## Controls

- **Red dot** on every slider marks the default. Click the dot to snap back to it.
- **R** resets every control. **Space** pauses or plays the animation.
- Close the window to return to the menu.

## Code layout

```
main.py                       menu, export, self-test
resilient_net/config.py       team, layer names, colours, default values (the red dots)
resilient_net/models.py       every equation (AM/FM, PCM, BER, Hata, Erlang-B, FSPL, rain fade,
                              air-to-ground, LoRa, ALOHA, hybrid availability)
resilient_net/terrain.py      real Gangtok terrain: elevation, diffraction, skyline, flood zone,
                              road graph, citizens, cell sites, shelters
resilient_net/widgets.py      theme, slider with red default dot, control deck
resilient_net/ui.py           coloured console output and step-by-step calculations
resilient_net/references.py   sources behind each model
resilient_net/views/*.py      one interactive window per menu item 1–9 (1 = block diagram)
resilient_net/live/*.py       live-data hub (menu 13): downloader, orbit propagator, five views
resilient_net/data/           bundled SRTM grid, OpenStreetMap layers, map outlines, offline samples
tools/fetch_gangtok_data.py   re-downloads the terrain and map data (not needed to run)
tools/check_references.py     checks that every reference link (DOI or official page) still opens
```

## Notes

- Terrain, roads, rivers and towns are real data. Hazard intensities and network parameters are illustrative design assumptions; change them in `config.py` to match the values in the papers you cite.
- Data attribution: elevation © NASA SRTM (via OpenTopoData); map data © OpenStreetMap contributors (ODbL); weather © Open-Meteo.com (CC BY 4.0); outlines © Natural Earth (public domain).
