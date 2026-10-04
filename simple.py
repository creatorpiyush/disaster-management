#!/usr/bin/env python3
"""Simple version: the 3 required layers + the hybrid in one window. No terrain, no live data.

python simple.py            window with sliders
python simple.py --print    calculations only
python simple.py --save     writes figures/simple.png

The equations are copied from resilient_net/models.py so this file works on its own
(only numpy + matplotlib). `python main.py --selftest` checks the two still agree.
"""
import math
import os
import sys

import numpy as np
import matplotlib

if __name__ == "__main__" and "--save" in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.widgets import RadioButtons, Slider  # noqa: E402

C_LIGHT = 299_792_458.0
K_BOLTZ_DBW = -228.6  # 10 log10(1.38e-23)
R_EARTH = 6378.0  # km
THERMAL_DBM_HZ = -174.0  # kT at 290 K
GEO_KM = 35786.0

# defaults, same values as resilient_net/config.py
STORM = dict(noise_rise=6.0, rain=80.0, towers_down=40.0, surge=3.0, wind=12.0)
ANALOG = dict(fc_mhz=100.0, p_kw=0.1, dist_km=20.0, mu=0.8, df_khz=5.0, fm_khz=3.0,
              gt_db=6.0, gr_db=-10.0, nf_db=8.0, clutter_db=12.0, terrain_db=23.0)  # terrain = median over homes
DIGITAL = dict(fs_khz=8.0, bits=8, f_mhz=900.0, ptx_dbm=43.0, h_bs=30.0, h_ms=1.5, r_cell_km=2.0,
               nf_db=7.0, bw_mhz=0.2, channels=56, erl_per_cell=40.0)
SAT = dict(band="Ku", elev=57.5, eirp_dbw=50.0, dish_m=1.2, rate_kbps=256.0, req_ebn0=6.0, eff=0.6,
           t_sys=200.0, hpa_w=20.0, h_station=1.6)  # GEO at 83° E seen from Gangtok

PHASES = ["During cloudburst", "Glacial-lake flood", "Recovery (first 72 h)"]
MODS = {"BPSK": 1, "QPSK": 2, "16-QAM": 4}  # bits/symbol
BANDS = {  # uplink GHz, downlink GHz, ITU-R P.838-3 (k, alpha) at downlink
    "C": dict(fu=6.0, fd=4.0, k=0.00065, a=1.121, sat_gt=0.0),
    "Ku": dict(fu=14.0, fd=12.0, k=0.02386, a=1.1825, sat_gt=5.0),
    "Ka": dict(fu=30.0, fd=20.0, k=0.09164, a=1.0568, sat_gt=10.0),
}
RAIN_HEIGHT_KM = 5.0  # ITU-R P.839: 0 °C isotherm + 0.36 km, monsoon at 27° N
COL = dict(an="#d95926", mo="#3987e5", sa="#199e70", hy="#333333", bad="#e66767")


def db(x):
    return 10 * np.log10(np.maximum(x, 1e-30))


def undb(x):
    return 10 ** (np.asarray(x, dtype=float) / 10)


def qfunc(x):
    x = np.asarray(x, dtype=float)
    return 0.5 * np.vectorize(math.erfc)(x / math.sqrt(2))


def fspl_db(d_km, f_mhz):
    # ITU-R P.525: L = 32.44 + 20log d(km) + 20log f(MHz)
    return 32.44 + 20 * np.log10(np.maximum(d_km, 1e-6)) + 20 * np.log10(f_mhz)


def erlang_b(traffic, channels):
    b = 1.0
    for k in range(1, int(channels) + 1):
        b = traffic * b / (k + traffic * b)
    return b


def storm_for(rain, towers, noise, phase=PHASES[0]):
    # same phase rules as menu 7 (views/compare.py), whole district
    s = dict(rain=rain, towers_down=towers, noise_rise=noise, surge=STORM["surge"], wind=STORM["wind"])
    if phase == PHASES[1]:  # lake bursts: rain eases, the flood takes out more sites
        s.update(rain=rain * 0.3, wind=min(s["wind"], 8.0), towers_down=min(95.0, towers + 12),
                 surge=s["surge"] * 1.3)
    elif phase == PHASES[2]:  # rain stops, blocked roads keep crews away
        s.update(wind=min(s["wind"], 6.0), rain=rain * 0.05, noise_rise=noise * 0.5,
                 towers_down=towers * 0.85, surge=s["surge"] * 1.2)
    return s


# Layer 1: analog radio
def man_made_noise_fa(f_mhz):
    # ITU-R P.372 urban: Fa = 76.8 - 27.7 log f
    return max(0.0, 76.8 - 27.7 * math.log10(f_mhz))


def analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, bw_khz, terrain_db=0.0):
    pt_dbm = 10 * math.log10(p_kw * 1e6)
    pl = fspl_db(dist_km, fc_mhz) + clutter_db + terrain_db
    pr = pt_dbm + gt_db + gr_db - pl
    fa = man_made_noise_fa(fc_mhz)
    f_total = 10 * math.log10(10 ** (fa / 10) + 10 ** (nf_db / 10) - 1)
    noise = THERMAL_DBM_HZ + 10 * math.log10(bw_khz * 1e3) + f_total + noise_rise
    return dict(pt_dbm=pt_dbm, pl=pl, pr=pr, noise=noise, cnr=pr - noise)


def fm_output_snr(cnr_db, beta):
    # tone FM with the threshold effect: SNRo = 1.5 β² γ / (1 + (12β/π) γ exp(-CNR)), γ = CNR·B_T/W
    cnr = undb(cnr_db)
    gamma = cnr * 2 * (beta + 1)
    return db(1.5 * beta ** 2 * gamma / (1 + (12 * beta / np.pi) * gamma * np.exp(-cnr)))


def am_output_snr(cnr_db, mu):
    # envelope detector: SNRo = μ²/(2+μ²) · γ above threshold, square-law suppression below
    cnr = undb(cnr_db)
    return db(mu ** 2 / (2 + mu ** 2) * 2 * cnr * cnr / (cnr + 1))


def analog_layer(noise_rise, wind, p_kw, dist_km, fc_mhz, mu, df_khz, fm_khz, gt_db, gr_db, nf_db, clutter_db,
                 terrain_db, shadow_db=6.0):
    beta = df_khz / fm_khz
    carson = 2 * (df_khz + fm_khz)
    lf = analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, carson, terrain_db)
    la = analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, 2 * fm_khz, terrain_db)
    # people spread evenly over a disc, speech needs >= 20 dB, log-normal shadowing
    d = np.sqrt(np.linspace(0.02, 1, 40)) * dist_km
    li = analog_link(p_kw, d, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, carson, np.full(40, terrain_db))
    coverage = float(np.mean(1 - qfunc((fm_output_snr(li["cnr"], beta) - 20) / shadow_db)))
    radio_ownership = 0.85
    mast_ok = 1 / (1 + math.exp((wind - 45) / 4))  # ridge mast survives gusts up to ~45 m/s
    return dict(beta=beta, carson=carson, link=lf, snr_fm=float(fm_output_snr(lf["cnr"], beta)),
                snr_am=float(am_output_snr(la["cnr"], mu)), coverage=coverage, mast_ok=mast_ok,
                reach=coverage * radio_ownership * mast_ok)


# Layer 2: mobile network
def ber_theory(mod, ebn0_db):
    g = undb(ebn0_db)
    if mod in ("BPSK", "QPSK"):
        return qfunc(np.sqrt(2 * g))
    if mod == "16-QAM":
        return 0.75 * qfunc(np.sqrt(0.8 * g))
    raise ValueError(mod)


def required_ebn0(mod, target=1e-3):
    lo, hi = -5.0, 30.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if float(ber_theory(mod, mid)) > target:
            lo = mid
        else:
            hi = mid
    return hi


def hata_urban(d_km, f_mhz=900.0, hb=30.0, hm=1.5):
    lf = math.log10(f_mhz)
    a_hm = (1.1 * lf - 0.7) * hm - (1.56 * lf - 0.8)
    return 69.55 + 26.16 * lf - 13.82 * math.log10(hb) - a_hm + (44.9 - 6.55 * math.log10(hb)) * np.log10(
        np.maximum(d_km, 0.02))


def mobile_layer(towers_down, surge, noise_rise, fs_khz, bits, f_mhz, ptx_dbm, h_bs, h_ms, r_cell_km, nf_db,
                 bw_mhz, channels, erl_per_cell, mod="QPSK", shadow_db=8.0):
    surv = min(1, max(0.02, 1 - towers_down / 100))
    r_eff = r_cell_km / math.sqrt(surv)  # survivors have to cover a bigger area
    ant_gain, penetration = 15.0, 12.0
    pr_edge = ptx_dbm + ant_gain - float(hata_urban(r_eff, f_mhz, h_bs, h_ms)) - penetration
    noise = THERMAL_DBM_HZ + 10 * math.log10(bw_mhz * 1e6) + nf_db + noise_rise
    rb = bits * fs_khz * 1e3  # 64 kbps PCM voice
    ebn0_edge = pr_edge - noise + 10 * math.log10(bw_mhz * 1e6 / rb)
    req = required_ebn0(mod)
    rr = np.sqrt(np.linspace(0.02, 1, 40)) * r_eff
    ebn0_r = ptx_dbm + ant_gain - hata_urban(rr, f_mhz, h_bs, h_ms) - penetration - noise \
        + 10 * math.log10(bw_mhz * 1e6 / rb)
    coverage = float(np.mean(qfunc((req - ebn0_r) / shadow_db)))
    ch = max(4, int(channels * MODS[mod] / 2))
    load = erl_per_cell * surge / surv  # dead cells dump their calls on the ones still up
    block = erlang_b(load, ch)
    return dict(surv=surv, r_eff=r_eff, pr_edge=pr_edge, noise=noise, ebn0_edge=ebn0_edge, req=req,
                coverage=coverage, channels=ch, load=load, block=block,
                reach=coverage * (1 - block) * surv ** 0.15)


# Layer 3: satellite
def slant_range_km(alt_km, elev_deg):
    e = math.radians(elev_deg)
    r = R_EARTH + alt_km
    return math.sqrt(r ** 2 - (R_EARTH * math.cos(e)) ** 2) - R_EARTH * math.sin(e)


def rain_attenuation(rain, f_ghz, k, a, elev_deg, h_station=0.0):
    # simplified ITU-R P.618, gamma = k R^alpha. Hill stations see a shorter rain path
    if rain <= 0 or h_station >= RAIN_HEIGHT_KM:
        return 0.0
    gam = k * rain ** a
    e = math.radians(max(elev_deg, 5))
    ls = (RAIN_HEIGHT_KM - h_station) / math.sin(e)
    lg = ls * math.cos(e)
    rf = 1 / (1 + 0.78 * math.sqrt(lg * gam / f_ghz) - 0.38 * (1 - math.exp(-2 * lg)))
    return gam * ls * rf


def dish_gain(d_m, f_ghz, eff=0.6):
    lam = C_LIGHT / (f_ghz * 1e9)
    return 10 * math.log10(eff * (math.pi * d_m / lam) ** 2)


def satellite_layer(rain, wind, band, elev, eirp_dbw, dish_m, rate_kbps, req_ebn0, eff, t_sys, hpa_w, h_station):
    b = BANDS[band]
    d = slant_range_km(GEO_KM, elev)
    lu, ld = float(fspl_db(d, b["fu"] * 1e3)), float(fspl_db(d, b["fd"] * 1e3))
    a_d = rain_attenuation(rain, b["fd"], b["k"], b["a"], elev, h_station=h_station)
    a_u = a_d * (b["fu"] / b["fd"]) ** 1.72
    t_rain = 275 * (1 - 10 ** (-a_d / 10))  # sky noise from the rain
    point = 0.5 * (max(0, wind - 20) / 10) ** 2  # small dish pushed off by the wind
    gt = dish_gain(dish_m, b["fd"], eff) - 10 * math.log10(t_sys + t_rain)
    atm = 0.5
    cn0_d = eirp_dbw - ld - a_d - atm - point + gt - K_BOLTZ_DBW
    eirp_up = 10 * math.log10(hpa_w) + dish_gain(dish_m, b["fu"], eff)
    cn0_u = eirp_up - lu - a_u - atm - point + b["sat_gt"] - K_BOLTZ_DBW
    cn0 = -10 * math.log10(10 ** (-cn0_u / 10) + 10 ** (-cn0_d / 10))
    ebn0 = cn0 - 10 * math.log10(rate_kbps * 1e3)
    margin = ebn0 - req_ebn0
    p_link = float(1 - qfunc(margin / 2.0))  # 2 dB fade variability
    terminal_share = 0.75  # citizens near a VSAT shelter / hotspot
    return dict(d=d, ld=ld, a_d=a_d, gt=gt, cn0=cn0, ebn0=ebn0, margin=margin, p_link=p_link,
                reach=p_link * terminal_share)


def evaluate(rain, towers, noise, phase=PHASES[0]):
    s = storm_for(rain, towers, noise, phase)
    an = analog_layer(noise_rise=s["noise_rise"], wind=s["wind"], **ANALOG)
    mo = mobile_layer(s["towers_down"], s["surge"], s["noise_rise"], **DIGITAL)
    sa = satellite_layer(s["rain"], s["wind"], **SAT)
    hybrid = 1 - (1 - mo["reach"]) * (1 - sa["reach"])  # two-way, analog is listen-only
    alert = 1 - (1 - an["reach"]) * (1 - mo["reach"]) * (1 - sa["reach"])
    return dict(storm=s, an=an, mo=mo, sa=sa, hybrid=hybrid, alert=alert)


def print_calculations(r):
    s, an, mo, sa = r["storm"], r["an"], r["mo"], r["sa"]
    rows = [
        ("Storm", f"rain {s['rain']:.0f} mm/h, towers down {s['towers_down']:.0f} %, noise +{s['noise_rise']:.1f} dB, "
                  f"surge {s['surge']:.1f}x, wind {s['wind']:.0f} m/s"),
        ("Analog: FM β", f"β = Δf/fm = {ANALOG['df_khz']}/{ANALOG['fm_khz']} = {an['beta']:.2f}, "
                         f"Carson BW = 2(Δf + fm) = {an['carson']:.0f} kHz"),
        ("Analog: link at edge", f"Pr = {an['link']['pr']:.1f} dBm, N = {an['link']['noise']:.1f} dBm, "
                                 f"CNR = {an['link']['cnr']:.1f} dB"),
        ("Analog: output SNR", f"FM {an['snr_fm']:.1f} dB, AM {an['snr_am']:.1f} dB (speech needs 20 dB)"),
        ("Analog: reach", f"{an['coverage']:.1%} covered · 85 % own a radio · mast {an['mast_ok']:.0%} = "
                          f"{an['reach']:.1%}"),
        ("Mobile: cell edge", f"R' = R/√surv = {DIGITAL['r_cell_km']}/√{mo['surv']:.2f} = {mo['r_eff']:.2f} km, "
                              f"Eb/N0 = {mo['ebn0_edge']:.1f} dB (QPSK needs {mo['req']:.1f} dB)"),
        ("Mobile: Erlang-B", f"load = {DIGITAL['erl_per_cell']:.0f}·{s['surge']:.1f}/{mo['surv']:.2f} = "
                             f"{mo['load']:.0f} E on {mo['channels']} ch → blocking {mo['block']:.1%}"),
        ("Mobile: reach", f"{mo['coverage']:.1%} covered · (1 - blocking) · surv^0.15 = {mo['reach']:.1%}"),
        ("Satellite: path", f"d = {sa['d']:.0f} km, FSPL down = {sa['ld']:.1f} dB, rain fade = {sa['a_d']:.2f} dB"),
        ("Satellite: budget", f"C/N0 = {sa['cn0']:.1f} dBHz, Eb/N0 = {sa['ebn0']:.1f} dB, margin = {sa['margin']:.1f} dB"),
        ("Satellite: reach", f"P(link) {sa['p_link']:.1%} · 75 % near a terminal = {sa['reach']:.1%}"),
        ("Hybrid (two-way)", f"1 - (1 - {mo['reach']:.3f})·(1 - {sa['reach']:.3f}) = {r['hybrid']:.1%}"),
        ("Alert (any layer)", f"{r['alert']:.1%}"),
    ]
    w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{w}}  {v}")


def build():
    fig = plt.figure(figsize=(14, 8.6))
    fig.suptitle("Simple version: the three required layers and the hybrid", fontweight="bold", y=0.985)
    fig.text(0.5, 0.94, "No terrain or live data. Analog uses the median ridge loss (23 dB) and satellite ignores "
             "the skyline, so both read a bit higher than the full simulator.", ha="center", fontsize=9, color="#666")
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.72, top=0.89, bottom=0.31, hspace=0.45, wspace=0.28)
    ax_an, ax_mo, ax_sa, ax_hy = (fig.add_subplot(gs[i, j]) for i in (0, 1) for j in (0, 1))
    ax_ro = fig.add_axes([0.75, 0.31, 0.24, 0.58])
    ax_ro.axis("off")
    ro = ax_ro.text(0, 1, "", va="top", family="monospace", fontsize=8.5)

    # analog: output SNR vs distance
    dist = np.linspace(0.5, 40, 200)
    fm_line, = ax_an.plot([], [], color=COL["an"], lw=2, label="FM")
    am_line, = ax_an.plot([], [], color=COL["an"], lw=1.5, ls="--", label="AM")
    thr = ax_an.axvline(0, color="#999", ls=":", lw=1)
    thr_txt = ax_an.text(0, 70, " FM threshold", fontsize=7.5, color="#666")
    ax_an.axhline(20, color=COL["bad"], lw=0.8)
    ax_an.text(39, 14, "speech needs 20 dB", ha="right", va="top", fontsize=7.5, color=COL["bad"])
    ax_an.set(title="Layer 1: Analog radio, output SNR vs distance", xlabel="distance from mast (km)",
              ylabel="output SNR (dB)", xlim=(0, 40), ylim=(-30, 80))
    ax_an.legend(loc="upper right", fontsize=8)

    # mobile: BER curves don't change, only the dot moves
    eb = np.linspace(-2, 22, 200)
    # BPSK and QPSK have the same BER per bit, so one curve
    ax_mo.semilogy(eb, ber_theory("QPSK", eb), color=COL["mo"], lw=1.5, label="BPSK / QPSK")
    ax_mo.semilogy(eb, ber_theory("16-QAM", eb), color=COL["mo"], ls="--", lw=1.5, label="16-QAM")
    mo_edge = ax_mo.axvline(0, color=COL["mo"], lw=2.5, alpha=0.6)  # BER here is often below the axis
    ax_mo.axhline(1e-3, color=COL["bad"], lw=0.8)
    ax_mo.text(-1.5, 1.4e-3, "voice target 10⁻³", fontsize=7.5, color=COL["bad"])
    mo_txt = ax_mo.text(0.97, 0.95, "", transform=ax_mo.transAxes, ha="right", va="top", fontsize=8)
    ax_mo.set(title="Layer 2: Mobile, BER at the cell edge", xlabel="Eb/N0 (dB)", ylabel="bit error rate",
              xlim=(-2, 22), ylim=(1e-7, 0.6))
    ax_mo.legend(loc="lower left", fontsize=8)

    # satellite: margin vs rain for each band
    rains = np.arange(0, 201, 5)
    sa_lines = {b: ax_sa.plot([], [], color=COL["sa"], lw=1.5, ls=ls, label=f"{b} band")[0]
                for b, ls in zip(BANDS, (":", "-", "--"))}
    sa_dot, = ax_sa.plot([], [], "o", color=COL["sa"], ms=9, mec="k")
    ax_sa.axhline(0, color=COL["bad"], lw=0.8)
    ax_sa.text(198, -1.5, "link lost below 0", ha="right", va="top", fontsize=7.5, color=COL["bad"])
    ax_sa.set(title="Layer 3: Satellite (GEO), margin vs rain", xlabel="rain rate (mm/h)",
              ylabel="link margin (dB)", xlim=(0, 200))
    ax_sa.legend(loc="lower left", fontsize=8)

    # hybrid bars
    names = ["Analog\n(listen only)", "Mobile", "Satellite", "Hybrid\n(two-way)"]
    bars = ax_hy.bar(names, [0] * 4, color=[COL["an"], COL["mo"], COL["sa"], COL["hy"]])
    bar_txt = [ax_hy.text(i, 0, "", ha="center", va="bottom", fontsize=9) for i in range(4)]
    ax_hy.set(title="Share of citizens reached", ylim=(0, 1.1), yticks=[0, 0.25, 0.5, 0.75, 1],
              yticklabels=["0", "25 %", "50 %", "75 %", "100 %"])

    sliders = dict(
        rain=Slider(fig.add_axes([0.13, 0.19, 0.42, 0.03]), "Rain (mm/h)", 0, 200, valinit=STORM["rain"],
                    valstep=1, color=COL["sa"]),
        towers=Slider(fig.add_axes([0.13, 0.135, 0.42, 0.03]), "Towers down (%)", 0, 95,
                      valinit=STORM["towers_down"], valstep=1, color=COL["mo"]),
        noise=Slider(fig.add_axes([0.13, 0.08, 0.42, 0.03]), "Noise rise (dB)", 0, 25,
                     valinit=STORM["noise_rise"], valstep=0.5, color=COL["an"]),
    )
    for sl in sliders.values():  # red dot = default, like the main program
        sl.ax.plot(sl.valinit, 0.5, "o", color=COL["bad"], ms=5, zorder=1)
    fig.text(0.65, 0.235, "Phase of the disaster", fontsize=9, fontweight="bold")
    radio = RadioButtons(fig.add_axes([0.65, 0.07, 0.17, 0.155]), PHASES)
    fig.text(0.13, 0.03, "Drag a slider or pick a phase. R resets everything. The red dot on each slider "
             "is the default.", fontsize=8, color="#666")

    def update(_=None):
        r = evaluate(sliders["rain"].val, sliders["towers"].val, sliders["noise"].val, radio.value_selected)
        s, an, mo, sa = r["storm"], r["an"], r["mo"], r["sa"]

        # analog curves move with the noise
        kw = {k: ANALOG[k] for k in ("p_kw", "fc_mhz", "gt_db", "gr_db", "nf_db", "clutter_db")}
        lf = analog_link(dist_km=dist, noise_rise=s["noise_rise"], bw_khz=an["carson"],
                         terrain_db=ANALOG["terrain_db"], **kw)
        la = analog_link(dist_km=dist, noise_rise=s["noise_rise"], bw_khz=2 * ANALOG["fm_khz"],
                         terrain_db=ANALOG["terrain_db"], **kw)
        fm_line.set_data(dist, fm_output_snr(lf["cnr"], an["beta"]))
        am_line.set_data(dist, am_output_snr(la["cnr"], ANALOG["mu"]))
        below = np.nonzero(lf["cnr"] < 10)[0]  # FM threshold ~ 10 dB CNR
        thr.set_visible(bool(below.size))
        thr_txt.set_visible(bool(below.size))
        if below.size:
            x = dist[below[0]]
            thr.set_xdata([x, x])
            thr_txt.set_x(x)

        e = min(max(mo["ebn0_edge"], -2), 22)
        mo_edge.set_xdata([e, e])
        mo_txt.set_text(f"QPSK edge Eb/N0 {mo['ebn0_edge']:.1f} dB\n{mo['channels']} ch/cell, load {mo['load']:.0f} E"
                        f"\ncall blocking {mo['block']:.0%}")

        margins = {b: [satellite_layer(x, s["wind"], **{**SAT, "band": b})["margin"] for x in rains] for b in BANDS}
        for b, ln in sa_lines.items():
            ln.set_data(rains, margins[b])
        sa_dot.set_data([s["rain"]], [sa["margin"]])
        allm = np.concatenate(list(margins.values()))
        ax_sa.set_ylim(min(-5, allm.min() - 1), allm.max() + 2)

        for i, v in enumerate((an["reach"], mo["reach"], sa["reach"], r["hybrid"])):
            bars[i].set_height(v)
            bar_txt[i].set_position((i, v + 0.02))
            bar_txt[i].set_text(f"{v:.0%}")

        ro.set_text(
            "AFTER THE PHASE IS APPLIED\n"
            f"rain        {s['rain']:6.1f} mm/h\n"
            f"towers down {s['towers_down']:6.1f} %\n"
            f"noise rise  {s['noise_rise']:6.1f} dB\n"
            f"call surge  {s['surge']:6.1f} x\n"
            f"wind        {s['wind']:6.1f} m/s\n\n"
            "REACH\n"
            f"analog      {an['reach']:6.1%}\n"
            f"mobile      {mo['reach']:6.1%}\n"
            f"satellite   {sa['reach']:6.1%}\n\n"
            f"hybrid      {r['hybrid']:6.1%}\n"
            "  two-way, 1-(1-mo)(1-sa)\n"
            f"alert       {r['alert']:6.1%}\n"
            "  any layer incl. analog\n\n"
            f"FM SNR at {ANALOG['dist_km']:.0f} km  {an['snr_fm']:5.1f} dB\n"
            f"sat rain fade    {sa['a_d']:5.2f} dB\n"
            f"sat margin       {sa['margin']:5.1f} dB")
        fig.canvas.draw_idle()

    def key(ev):
        if ev.key == "r":
            for sl in sliders.values():
                sl.reset()
            radio.set_active(0)

    for sl in sliders.values():
        sl.on_changed(update)
    radio.on_clicked(update)
    fig.canvas.mpl_connect("key_press_event", key)
    update()
    fig._simple = (sliders, radio)  # keep the widgets alive
    return fig, sliders, radio


def main():
    if "--print" in sys.argv:
        for phase in PHASES:
            print(f"\n{phase} (defaults)")
            print_calculations(evaluate(STORM["rain"], STORM["towers_down"], STORM["noise_rise"], phase))
        return
    fig, _, _ = build()
    if "--save" in sys.argv:
        os.makedirs("figures", exist_ok=True)
        fig.savefig(os.path.join("figures", "simple.png"), dpi=200)
        print("saved figures/simple.png")
        return
    plt.show()


if __name__ == "__main__":
    main()
