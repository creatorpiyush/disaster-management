"""
Shared constants: team, scenario defaults, colours and layer names.

Every number marked "default" is the value the red dot on each slider points
back to. They are illustrative design assumptions for a coastal smart city hit
by a cyclone; replace them with values from your cited sources if needed.
"""

PROJECT = "Disaster-Resilient Hybrid Communication Network for a Smart City"
STUDY = "Study area: coastal smart city hit by a severe cyclone"
MEMBERS = [("Manasvi Choudhary", "2430112"),
           ("Kumari Sweta", "2430211"),
           ("Srishti Anand", "2430221")]

# --------------------------------------------------------------------------
#  Layer names. The first three are the layers the assignment requires; the
#  last two are supplementary layers that can be added to the same design.
# --------------------------------------------------------------------------
L_AN = "Analog emergency radio"
L_MO = "Digital mobile network"
L_SA = "Satellite backup"
L_UAV = "UAV aerial base station"
L_MESH = "LoRa / D2D mesh"
CORE_LAYERS = [L_AN, L_MO, L_SA]
EXTRA_LAYERS = [L_UAV, L_MESH]
ALL_LAYERS = CORE_LAYERS + EXTRA_LAYERS

# --------------------------------------------------------------------------
#  Theme ("mission control" dark). Categorical hues follow a fixed order so
#  the same layer always keeps the same colour in every figure.
# --------------------------------------------------------------------------
BG = "#121417"          # figure background
PANEL = "#1a1a19"       # axes background
GRID = "#2c2d2b"
INK = "#f2f2ee"         # primary text
INK2 = "#c3c2b7"        # secondary text
MUTED = "#8a897f"

COL = {
    L_MO: "#3987e5",     # blue
    L_AN: "#d95926",     # orange
    L_SA: "#199e70",     # aqua
    L_UAV: "#c98500",    # yellow
    L_MESH: "#d55181",   # magenta
    "hybrid": "#f2f2ee",  # hybrid curves drawn in primary ink, thick
    "violet": "#9085e9",
    "good": "#2fb344",
    "warn": "#e0a400",
    "bad": "#e66767",
    "noise": "#6f6e66",
}
SHORT = {L_AN: "Analog", L_MO: "Mobile", L_SA: "Satellite", L_UAV: "UAV", L_MESH: "Mesh"}

# --------------------------------------------------------------------------
#  Scenario defaults (the red-dot values)
# --------------------------------------------------------------------------
STORM = dict(
    noise_rise=6.0,      # dB rise of the noise floor (lightning, static, generators)
    rain=60.0,           # mm/h rain rate
    towers_down=35.0,    # % of cell sites destroyed or without power
    surge=3.0,           # x normal call traffic
    wind=28.0,           # m/s sustained wind (Category-1 cyclone ~ 33 m/s)
)

ANALOG = dict(fc_mhz=100.0, p_kw=1.0, dist_km=40.0, mu=0.8, df_khz=5.0, fm_khz=3.0,
              gt_db=6.0, gr_db=-10.0, nf_db=8.0, clutter_db=30.0)

DIGITAL = dict(fs_khz=8.0, bits=8, w_khz=3.4, rolloff=0.35, f_mhz=900.0, ptx_dbm=43.0,
               h_bs=30.0, h_ms=1.5, r_cell_km=2.0, nf_db=7.0, bw_mhz=0.2,
               channels=56, erl_per_cell=40.0, gos=0.02, split=0)

SAT = dict(band="Ku", orbit="GEO", elev=50.0, eirp_dbw=50.0, dish_m=1.2, rate_kbps=256.0,
           req_ebn0=6.0, eff=0.6, t_sys=200.0, hpa_w=20.0)

UAV = dict(h_m=500.0, f_ghz=2.0, ptx_dbm=23.0, rx_sens_dbm=-92.0, env="Urban", n_uav=6,
           wind_limit=15.0, endurance_min=35.0)

MESH = dict(sf=9, bw_khz=125.0, ptx_dbm=14.0, n_nodes=120, alive=70.0, payload=24,
            msgs_per_hr=12.0, area_km=8.0)

TERRAINS = ["Coastal city (assigned)", "Dense urban", "Mountainous"]
