# Disaster-Resilient Hybrid Communication Network: Interactive Simulator

This simulator models a coastal smart city hit by a cyclone. Each layer of the network opens as a live, animated window with sliders.

## Run it

```bash
python3 -m venv .venv               # create a virtual environment (first time only)
source .venv/bin/activate           # activate it (in every new terminal)
pip install -r requirements.txt     # install numpy + matplotlib (first time only)
python main.py              # menu: press a number, a live window opens
python main.py --export     # saves all figures to ./figures and all calculations to ./results
python main.py --selftest   # runs every window headless and moves every control
```

On Windows, activate with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

## Menu

| Key | View | What moves live |
|---|---|---|
| 1 | Layer 1: Analog emergency radio (required) | AM/FM waves, Bessel spectrum, simulated demodulation, FM threshold, coverage rings |
| 2 | Layer 2: Digital mobile network (required) | PCM sampling and aliasing, SQNR, constellation, BER (Monte-Carlo), cell map with failures, Erlang-B |
| 3 | Layer 3: Satellite backup (required) | GEO/LEO geometry with signal pulses, link-budget waterfall, rain fade per band, margin, latency |
| 4 | Supplementary A: UAV aerial base station (optional) | drone side and top views, air-to-ground path loss, optimal altitude, flying vs wind |
| 5 | Supplementary B: LoRa / D2D mesh (optional) | SOS message flooding hop by hop, SF trade-off, connectivity, ALOHA collisions |
| 6 | Comparison + hybrid | radar profiles, reach bars, storm sweep, failover share, terrain and phase |
| 7 | Block diagram | packets flow through each Tx → channel → Rx chain; break a channel to see the failover |
| 8 | Noise & signal-quality lab | Gaussian + impulsive noise, histogram, eye diagram, live BER that converges to theory |
| 9 | Live disaster simulation | cyclone crosses the city; towers fail, drones launch, crews repair; each citizen is coloured by the layer serving them |
| 10–12 | Report tools | print all calculations, export figures and CSV, list references |

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
resilient_net/widgets.py      theme, slider with red default dot, control deck
resilient_net/ui.py           coloured console output and step-by-step calculations
resilient_net/references.py   sources behind each model
resilient_net/views/*.py      one interactive window per menu item
```

All parameters are illustrative design assumptions. Change them in `config.py` to match the values in the papers you cite.
