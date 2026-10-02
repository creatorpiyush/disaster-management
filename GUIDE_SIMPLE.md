# What this simulator is, in plain words

*A guide for anyone, no engineering background needed.*

## The big idea

When a disaster hits a city, the phone network is often the first thing to break. Towers lose power, cables get cut and everyone tries to call at once. But that is exactly when people most need to call for help and hear warnings.

This project designs a **communication network that keeps working during a disaster**. It does not rely on one system. It stacks several systems so that when one fails, another takes over.

This program lets you **see and play with** that network on a computer. You move sliders, watch animations, and see which parts survive.

## Where it happens: Gangtok, Sikkim

Most disaster examples use a coastal city and a cyclone. We chose a **mountain city** instead: Gangtok, the capital of Sikkim, high in the Himalayas.

Mountains create problems a flat coastal city never has:

- **Ridges block signals.** A hill between you and a radio tower can cut the signal, as a wall blocks light.
- **Heavy rain causes landslides.** Landslides bury roads, and the internet cables laid along those roads are cut with them.
- **Glacial lakes can burst.** In October 2023 a glacial lake (South Lhonak) burst and a huge flood ran down the Teesta river. We include this kind of flood.

The map is **real**:
- The hills and valleys come from NASA satellite height measurements.
- The roads, rivers and towns come from OpenStreetMap.

The disaster itself (how much rain, how many towers fail) is made up but realistic. You can change it with the sliders.

## The story the simulator tells

1. **Cloudburst.** Extremely heavy rain falls over a few hours.
2. **Landslides.** Steep slopes give way. Roads are blocked, and the cables along them are cut.
3. **Mobile towers go silent.** They lose their internet cable or their power.
4. **Glacial-lake flood.** About two days later, a flood rushes down the Teesta valley.
5. **Recovery.** Road crews clear the landslides, and the network comes back step by step.

## The layers of the network

Think of the layers as **backup plans**. The first three are the ones the assignment asks for.

| Layer | Everyday comparison | Good at | Weak at |
|---|---|---|---|
| **1. Analog radio (AM/FM)** | The radio in a car or a cheap pocket radio | One tower can warn everyone at once, and radios run on batteries | One-way only: people can listen but not reply. Ridges create "shadow" areas |
| **2. Mobile network** | Your normal phone signal | Two-way calls, messages and data | Towers need power and cables, and they break easily in landslides |
| **3. Satellite** | A dish on a roof that talks to a satellite in space | Works even when everything on the ground is broken | Very heavy rain weakens the signal ("rain fade"), and it needs a clear view of the sky |

Two more layers **could also be used** to make the network even stronger. They are optional:

| Layer | Everyday comparison | Idea |
|---|---|---|
| **UAV (drone) base station** | A flying mobile tower | A drone carries a small tower over a cut-off area. It cannot fly in strong wind or heavy rain, and thin mountain air shortens its flight time |
| **Mesh network (LoRa / phone-to-phone)** | Passing a note from person to person | Phones or small radios pass an SOS message along a chain until it reaches someone who is connected |

The **"hybrid"** result is the most important one. It shows how many people can still be reached when **all the layers work together**.

## The main menu, explained

Run `python main.py`, then press a number.

| Key | What you see | What to look for |
|---|---|---|
| **1** | **Block diagram.** A picture of the whole network with moving dots (messages) | Click to "break" one part and watch the messages take another route. This is called **failover** |
| **2** | **Analog radio** | How sound is carried on radio waves, and a map of Gangtok showing which homes the FM signal reaches and which are hidden behind ridges |
| **3** | **Mobile network** | How a voice becomes numbers (digital), how noise causes errors, and how many calls the towers can carry when everyone calls at once |
| **4** | **Satellite** | How strong the signal is, how rain weakens it, and a "sky view" showing which parts of the sky the mountains hide |
| **5** | **Drone (optional)** | A drone flying over a real valley, and when wind or rain grounds it |
| **6** | **Mesh (optional)** | An SOS message hopping between phones across the hills |
| **7** | **Comparison** | All layers side by side, for different parts of the city (ridge town, slopes, valley floor) and different phases (cloudburst, flood, recovery) |
| **8** | **Noise lab** | What "noise" (static, interference) does to a signal, and how errors grow as noise grows |
| **9** | **Live disaster simulation** | The full story on the real map: rain moves across, landslides appear, roads and towers fail, the flood runs down the river, drones launch and crews repair roads. **This is the best view to show someone first** |
| **13** | **Live data hub** | Real data from the internet, right now (see below) |
| **10–12** | **Report tools** | Print all the calculations, save every picture to a folder, and list the sources |

## The live data hub (menu 13)

This part uses **real, current data** from free public websites. You don't need an account or a key.

| Key | What it shows |
|---|---|
| **1** | **Today's weather in Gangtok**, and what it would do to each layer: landslide risk, satellite rain fade, and whether drones could fly. It can also replay the October 2023 flood week and the wettest days of the last monsoon |
| **2** | **Real satellites above Gangtok right now**: Starlink, OneWeb, Iridium, India's GSAT/INSAT and the Space Station, and which ones the mountains hide |
| **3** | **Disasters happening in the world** now, and recent **earthquakes around Sikkim** |
| **4** | **Space weather.** The Sun sometimes sends bursts that disturb radio and satellite signals. This shows how calm or stormy it is today |
| **5** | **Terrain profile.** Pick two places and see the land between them, and whether a radio signal can pass over the hills |
| **6** | **Save a snapshot.** Saves today's numbers, pictures and the list of sources into a dated folder |

**No internet?** It still works. It uses the last download or a sample saved inside the project. A small label on every picture says **LIVE**, **CACHED** or **OFFLINE**, so you always know which one you are looking at.

## How to use the windows

- **Sliders** change the situation, for example "more rain" or "more towers down". The pictures update straight away.
- The **red dot** on each slider marks the normal (default) value. Click it to go back.
- Press **R** to reset everything. Press **Space** to pause or play the animation.
- **Close the window** to go back to the menu.

## What the simulator shows (the main lessons)

- **No single layer is enough.** Each one fails in a different way: radio is blocked by ridges, mobile by landslides, satellite by heavy rain. Together they cover each other's weak spots.
- **In mountains, the land matters as much as the weather.** On a typical home's radio path, a ridge weakens the signal a lot. Homes in deep valleys are the hardest to reach.
- **Satellites are a strong backup in Gangtok.** The main Indian satellite sits high in the sky (about 57° up), above most ridges. Heavy rain still weakens it, and more so in the low valleys.
- **The valley floor is the most at-risk area during the flood.** With only the three required layers, roughly 4 in 10 people there can be reached. Adding the optional drone and mesh layers raises that to about 3 in 4.

## Words you may see

| Word | Meaning |
|---|---|
| **Signal / dB** | How strong a signal is. dB (decibels) is the unit: a few dB more loss means a much weaker signal |
| **Noise** | Unwanted "static" that drowns out the signal |
| **Coverage** | The area or share of people the signal reaches |
| **Failover** | Automatically switching to a backup when something breaks |
| **Diffraction / ridge loss** | Signal bending over a hilltop and getting weaker as it does |
| **Rain fade** | Heavy rain soaking up a satellite signal |
| **Fibre / backhaul** | The cable that connects a mobile tower to the rest of the internet |
| **GEO / LEO** | GEO satellites stay fixed in the sky, very far away. LEO satellites (like Starlink) are closer and move quickly across the sky |
| **GLOF** | Glacial Lake Outburst Flood: a lake held back by ice or rubble suddenly bursts |
| **Cloudburst** | Extremely heavy rain over a small area in a short time |
| **Hybrid** | All the layers working together |

## How to run it (step by step)

1. Install Python from python.org. On Windows, tick **"Add Python to PATH"** during installation.
2. Open a terminal in this project folder.
3. Type these lines one at a time:

   **Mac / Linux**
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

   **Windows**
   ```
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

4. Press a number from the menu. Try **9** first.

On a slow laptop, run `python main.py --lite` instead. The animations are slower but the results are the same.

For the technical details (formulas, code layout, data sources), see `README.md`.
