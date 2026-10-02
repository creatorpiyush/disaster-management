"""Constants: team, layer names, colours, slider defaults (our own assumptions, only the terrain is real)."""

PROJECT = "Disaster-Resilient Hybrid Communication Network for a Smart City"
STUDY = "Study area: Gangtok, Sikkim (Himalayan smart city), monsoon cloudburst, landslides and a glacial-lake flood"
MEMBERS = [("Manasvi Choudhary", "2430112"),
           ("Kumari Sweta", "2430211"),
           ("Srishti Anand", "2430221")]

# layer names - first 3 are the ones the assignment asks for, last 2 are extras
L_AN = "Analog emergency radio"
L_MO = "Digital mobile network"
L_SA = "Satellite backup"
L_UAV = "UAV aerial base station"
L_MESH = "LoRa / D2D mesh"
CORE_LAYERS = [L_AN, L_MO, L_SA]
EXTRA_LAYERS = [L_UAV, L_MESH]
ALL_LAYERS = CORE_LAYERS + EXTRA_LAYERS

# dark theme. each layer keeps the same colour in every plot
BG = "#121417"  # figure background
PANEL = "#1a1a19"  # axes background
GRID = "#2c2d2b"
INK = "#f2f2ee"  # primary text
INK2 = "#c3c2b7"  # secondary text
MUTED = "#8a897f"

COL = {
    L_MO: "#3987e5",  # blue
    L_AN: "#d95926",  # orange
    L_SA: "#199e70",  # aqua
    L_UAV: "#c98500",  # yellow
    L_MESH: "#d55181",  # magenta
    "hybrid": "#f2f2ee",
    "violet": "#9085e9",
    "good": "#2fb344",
    "warn": "#e0a400",
    "bad": "#e66767",
    "noise": "#6f6e66",
}
SHORT = {L_AN: "Analog", L_MO: "Mobile", L_SA: "Satellite", L_UAV: "UAV", L_MESH: "Mesh"}

# defaults (where the red dot on each slider points)
STORM = dict(
    noise_rise=6.0,  # dB rise of the noise floor (lightning, static, diesel generators)
    rain=80.0,  # mm/h rain rate (IMD calls ≥ 100 mm/h a cloudburst)
    towers_down=40.0,  # % of cell sites off-air: fibre cut by landslides, power lost, site buried
    surge=3.0,  # x normal call traffic
    wind=12.0,  # m/s thunderstorm gusts funnelled along the valleys
)

ANALOG = dict(fc_mhz=100.0, p_kw=0.1, dist_km=20.0, mu=0.8, df_khz=5.0, fm_khz=3.0,
              gt_db=6.0, gr_db=-10.0, nf_db=8.0, clutter_db=12.0, terrain_db=23.0)  # terrain = median over homes

DIGITAL = dict(fs_khz=8.0, bits=8, w_khz=3.4, rolloff=0.35, f_mhz=900.0, ptx_dbm=43.0,
               h_bs=30.0, h_ms=1.5, r_cell_km=2.0, nf_db=7.0, bw_mhz=0.2,
               channels=56, erl_per_cell=40.0, gos=0.02, split=0)

SAT = dict(band="Ku", orbit="GEO", elev=57.5, eirp_dbw=50.0, dish_m=1.2, rate_kbps=256.0,
           req_ebn0=6.0, eff=0.6, t_sys=200.0, hpa_w=20.0, h_station=1.6)  # GEO at 83° E seen from Gangtok

UAV = dict(h_m=500.0, f_ghz=2.0, ptx_dbm=23.0, rx_sens_dbm=-92.0, env="Urban", n_uav=6,
           wind_limit=15.0, endurance_min=35.0, alt_msl=1600.0)  # launched from Gangtok (~1600 m)

MESH = dict(sf=9, bw_khz=125.0, ptx_dbm=20.0, n_nodes=120, alive=70.0, payload=24,
            msgs_per_hr=12.0, area_km=8.0)  # IN865 band (865–867 MHz) allows up to 1 W

TERRAINS = ["Whole district", "Ridge town (Gangtok)", "Hill-slope villages", "Valley floor (Teesta)"]  # = terrain.ZONES
