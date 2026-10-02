"""
Physical-layer and network models used by every view.

All functions are pure (numbers in, numbers out) so the console calculations,
the interactive figures and the exported results always agree.

Sources for each equation are given as [n]; the full list is in references.py.
"""
import math
import numpy as np

C_LIGHT = 299_792_458.0
K_BOLTZ_DBW = -228.6           # 10 log10(1.38e-23)
R_EARTH = 6378.0               # km
THERMAL_DBM_HZ = -174.0        # kT at 290 K


# ---------------------------------------------------------------------------
#  Generic helpers
# ---------------------------------------------------------------------------
def db(x):
    return 10 * np.log10(np.maximum(x, 1e-30))


def undb(x):
    return 10 ** (np.asarray(x, dtype=float) / 10)


def qfunc(x):
    """Gaussian tail probability Q(x)."""
    x = np.asarray(x, dtype=float)
    return 0.5 * np.vectorize(math.erfc)(x / math.sqrt(2))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def fspl_db(d_km, f_mhz):
    """Free-space path loss, ITU-R P.525 [9]:  L = 32.44 + 20log d(km) + 20log f(MHz)."""
    return 32.44 + 20 * np.log10(np.maximum(d_km, 1e-6)) + 20 * np.log10(f_mhz)


_trapz = getattr(np, "trapezoid", None) or np.trapz


def bessel_j(n, beta, samples=400):
    """Bessel function of the first kind, J_n(beta) = (1/pi) ∫0..pi cos(n·t - beta·sin t) dt."""
    t = np.linspace(0, np.pi, samples)
    beta = np.atleast_1d(np.asarray(beta, dtype=float))
    vals = _trapz(np.cos(n * t[None, :] - beta[:, None] * np.sin(t[None, :])), t, axis=1) / np.pi
    return vals if vals.size > 1 else float(vals[0])


def erlang_b(traffic, channels):
    """Erlang-B blocking probability, recursive form [3]."""
    b = 1.0
    for k in range(1, int(channels) + 1):
        b = traffic * b / (k + traffic * b)
    return b


def erlang_b_capacity(channels, gos):
    """Largest offered traffic (Erlang) that keeps blocking <= gos."""
    lo, hi = 0.0, float(channels) * 2 + 10
    for _ in range(60):
        mid = (lo + hi) / 2
        if erlang_b(mid, channels) > gos:
            hi = mid
        else:
            lo = mid
    return lo


def storm_from_intensity(i):
    """Map one 0..1 'storm intensity' knob onto all hazard variables.
    i = 0.4 reproduces the default scenario exactly."""
    return dict(noise_rise=2 + 10 * i, rain=150 * i, towers_down=87.5 * i, surge=1 + 5 * i, wind=5 + 57.5 * i)


# Terrain modifiers used by the comparison view (dB of extra loss, or factors)
TERRAIN = {
    "Coastal city (assigned)": dict(clutter=0, shadow=8, uav_env="Urban", mesh_loss=8, sat_block=0.03, rain_mult=1.0),
    "Dense urban": dict(clutter=8, shadow=10, uav_env="Dense urban", mesh_loss=14, sat_block=0.15, rain_mult=1.0),
    "Mountainous": dict(clutter=14, shadow=12, uav_env="Suburban", mesh_loss=18, sat_block=0.10, rain_mult=0.9),
}


# ---------------------------------------------------------------------------
#  LAYER 1 - Analog emergency radio (AM / FM)        Unit I  [1][2][10][11]
# ---------------------------------------------------------------------------
def man_made_noise_fa(f_mhz):
    """External (man-made) noise figure in an urban area, ITU-R P.372 [10]: Fa = 76.8 - 27.7 log f."""
    return max(0.0, 76.8 - 27.7 * math.log10(f_mhz))


def am_metrics(mu, fm_khz):
    return dict(bw_khz=2 * fm_khz, eff=mu ** 2 / (2 + mu ** 2), pt_over_pc=1 + mu ** 2 / 2,
                sideband_db=20 * math.log10(max(mu, 1e-6) / 2))


def fm_metrics(df_khz, fm_khz):
    beta = df_khz / fm_khz
    return dict(beta=beta, carson_khz=2 * (df_khz + fm_khz), gain_db=10 * math.log10(1.5 * beta ** 2 + 1e-12),
                n_sig=int(math.floor(beta)) + 1)


def analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, bw_khz):
    """Received power, noise and carrier-to-noise ratio for the broadcast link."""
    pt_dbm = 10 * math.log10(p_kw * 1e6)
    # beyond the radio horizon d_h = 4.12(√ht + √hr) km (150 m mast, 1.5 m receiver) add a diffraction loss
    d_h = 4.12 * (math.sqrt(150) + math.sqrt(1.5))
    pl = float(fspl_db(dist_km, fc_mhz)) + clutter_db + 0.8 * max(0.0, dist_km - d_h)
    pr = pt_dbm + gt_db + gr_db - pl
    fa = man_made_noise_fa(fc_mhz)
    f_total = 10 * math.log10(10 ** (fa / 10) + 10 ** (nf_db / 10) - 1)
    noise = THERMAL_DBM_HZ + 10 * math.log10(bw_khz * 1e3) + f_total + noise_rise
    return dict(pt_dbm=pt_dbm, pl=pl, pr=pr, fa=fa, f_total=f_total, noise=noise, cnr=pr - noise)


def fm_output_snr(cnr_db, beta):
    """FM output SNR with the threshold effect (tone modulation, Taub & Schilling [11]):
    SNRo = 1.5 β² γ / (1 + (12β/π) γ exp(-CNR)),  γ = CNR·B_T/W."""
    cnr = undb(cnr_db)
    gamma = cnr * 2 * (beta + 1)
    out = 1.5 * beta ** 2 * gamma / (1 + (12 * beta / np.pi) * gamma * np.exp(-cnr))
    return db(out)


def am_output_snr(cnr_db, mu):
    """Envelope-detected AM: SNRo = μ²/(2+μ²) · γ above threshold, square-law suppression below
    (approximation of Haykin [1] ch.2)."""
    cnr = undb(cnr_db)
    gamma = 2 * cnr
    eta = mu ** 2 / (2 + mu ** 2)
    return db(eta * gamma * cnr / (cnr + 1))


def analog_layer(p_kw=1.0, dist_km=40.0, fc_mhz=100.0, mu=0.8, df_khz=5.0, fm_khz=3.0, gt_db=6.0, gr_db=-10.0,
                 nf_db=8.0, clutter_db=30.0, noise_rise=6.0, shadow_db=8.0, wind=28.0, **_):
    """Complete analog-layer evaluation, incl. probability a citizen hears an intelligible alert."""
    fm = fm_metrics(df_khz, fm_khz)
    am = am_metrics(mu, fm_khz)
    lf = analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, fm["carson_khz"])
    la = analog_link(p_kw, dist_km, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, am["bw_khz"])
    snr_fm = float(fm_output_snr(lf["cnr"], fm["beta"]))
    snr_am = float(am_output_snr(la["cnr"], mu))
    # Reach: citizens spread uniformly over a disc of radius dist_km around the transmitter,
    # log-normal shadowing sigma = shadow_db; intelligible speech needs >= 20 dB output SNR.
    r = np.sqrt(np.linspace(0.02, 1, 40)) * dist_km
    reach = 0.0
    for ri in r:
        li = analog_link(p_kw, ri, fc_mhz, gt_db, gr_db, nf_db, clutter_db, noise_rise, fm["carson_khz"])
        reach += float(1 - qfunc((float(fm_output_snr(li["cnr"], fm["beta"])) - 20) / shadow_db))
    reach /= len(r)
    radio_ownership = 0.85   # share of households with a battery / phone FM receiver
    mast_ok = 1 / (1 + math.exp((wind - 55) / 4))   # broadcast mast survives up to ~55 m/s gusts
    return dict(mast_ok=mast_ok, fm=fm, am=am, link_fm=lf, link_am=la, snr_fm=snr_fm, snr_am=snr_am,
                reach=reach * radio_ownership * mast_ok, coverage=reach)


def simulate_am_fm(mu, beta, cnr_db, n=4000, cycles=6, seed=0):
    """Complex-baseband simulation of AM and FM through AWGN with real demodulators.
    Returns time axis, message, AM rx envelope, FM demodulated output and measured SNRs."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, cycles, n, endpoint=False)          # time in message periods
    m = np.cos(2 * np.pi * t)
    os_ = n / cycles                                        # samples per message period
    # noise of bandwidth = full sample rate; CNR is defined in the transmission bandwidth
    bt_am = 2.0
    bt_fm = 2 * (beta + 1)
    sig_am = 1 + mu * m
    p_am = np.mean(sig_am ** 2)
    n0_am = p_am / undb(cnr_db) / bt_am                     # per unit (message-frequency) bandwidth
    w_am = np.sqrt(n0_am * os_ / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    env = np.abs(sig_am + _bandlimit(w_am, os_, bt_am / 2))          # IF filter, then envelope detector
    am_out = _lowpass(env - np.mean(env), os_, 1.05) / max(mu, 1e-6)
    phase = 2 * np.pi * beta * np.cumsum(m) / os_
    s_fm = np.exp(1j * phase)
    n0_fm = 1 / undb(cnr_db) / bt_fm
    w_fm = np.sqrt(n0_fm * os_ / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    r = s_fm + _bandlimit(w_fm, os_, bt_fm / 2)                      # IF filter (Carson bandwidth)
    inst = np.angle(r[1:] * np.conj(r[:-1])) * os_ / (2 * np.pi * max(beta, 1e-6))
    fm_out = _lowpass(np.concatenate([[inst[0]], inst]), os_, 1.05)
    trim = slice(int(os_ // 2), n - int(os_ // 2))

    def meas(y):
        e = y[trim] - m[trim]
        return float(db(np.mean(m[trim] ** 2) / max(np.mean(e ** 2), 1e-12)))

    return dict(t=t, m=m, am_tx=sig_am, am_env=env, am_out=am_out, fm_out=fm_out, fm_phase=phase,
                snr_am=meas(am_out), snr_fm=meas(fm_out))


def _bandlimit(x, samples_per_period, half_bw):
    X = np.fft.fft(x)
    f = np.fft.fftfreq(len(x), 1 / samples_per_period)
    X[np.abs(f) > half_bw] = 0
    return np.fft.ifft(X)


def _lowpass(x, samples_per_period, cutoff_harm):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / samples_per_period)
    X[f > cutoff_harm] = 0
    return np.fft.irfft(X, len(x))


# ---------------------------------------------------------------------------
#  LAYER 2 - Digital mobile network              Unit III / IV   [2][3][4][12]
# ---------------------------------------------------------------------------
MODS = {  # name: bits/symbol
    "ASK (OOK)": 1, "BPSK": 1, "QPSK": 2, "16-QAM": 4,
}


def ber_theory(mod, ebn0_db):
    g = undb(ebn0_db)
    if mod == "ASK (OOK)":
        return qfunc(np.sqrt(g))
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


def pcm(w_khz=3.4, fs_khz=8.0, bits=8, vmax=1.0, rolloff=0.35, mod="BPSK"):
    levels = 2 ** bits
    step = 2 * vmax / levels
    rb = bits * fs_khz * 1e3
    k = MODS[mod]
    return dict(nyquist_khz=2 * w_khz, ok=fs_khz >= 2 * w_khz, ts_us=1e3 / fs_khz, levels=levels, step=step,
                qerr_max=step / 2, qnoise=step ** 2 / 12, sqnr=6.02 * bits + 1.76, rb=rb,
                bw_null=2 * rb / k, bw_rc=rb * (1 + rolloff) / k, rs=rb / k)


def hata_urban(d_km, f_mhz=900.0, hb=30.0, hm=1.5):
    """Okumura-Hata urban path loss, 150-1500 MHz [12]."""
    lf = math.log10(f_mhz)
    a_hm = (1.1 * lf - 0.7) * hm - (1.56 * lf - 0.8)
    return 69.55 + 26.16 * lf - 13.82 * math.log10(hb) - a_hm + (44.9 - 6.55 * math.log10(hb)) * np.log10(
        np.maximum(d_km, 0.02))


def mobile_layer(towers_down=35.0, surge=3.0, noise_rise=6.0, mod="QPSK", bits=8, fs_khz=8.0, f_mhz=900.0,
                 ptx_dbm=43.0, h_bs=30.0, h_ms=1.5, r_cell_km=2.0, nf_db=7.0, bw_mhz=0.2, channels=56,
                 erl_per_cell=40.0, split=0, extra_loss=0.0, shadow_db=8.0, **_):
    surv = clamp(1 - towers_down / 100, 0.02, 1)
    r_eff = r_cell_km / (2 ** split) / math.sqrt(surv)       # survivors must cover a larger area
    ant_gain, penetration = 15.0, 12.0
    pr_edge = ptx_dbm + ant_gain - float(hata_urban(r_eff, f_mhz, h_bs, h_ms)) - penetration - extra_loss
    noise = THERMAL_DBM_HZ + 10 * math.log10(bw_mhz * 1e6) + nf_db + noise_rise
    snr_edge = pr_edge - noise
    p = pcm(fs_khz=fs_khz, bits=bits, mod=mod)
    ebn0_edge = snr_edge + 10 * math.log10(bw_mhz * 1e6 / p["rb"])
    req = required_ebn0(mod)
    # area coverage: average the per-radius outage over a disc (users uniform in area)
    rr = np.sqrt(np.linspace(0.02, 1, 40)) * r_eff
    ebn0_r = ptx_dbm + ant_gain - hata_urban(rr, f_mhz, h_bs, h_ms) - penetration - extra_loss - noise \
        + 10 * math.log10(bw_mhz * 1e6 / p["rb"])
    cov = float(np.mean(qfunc((req - ebn0_r) / shadow_db)))
    # capacity: traffic of destroyed cells is pushed onto survivors; channels per cell scale with modulation
    k = MODS[mod]
    ch = max(4, int(channels * k / 2))       # QPSK = reference; 16-QAM doubles voice channels, BPSK halves
    load = erl_per_cell * surge / surv / (4 ** split)
    block = erlang_b(load, ch)
    ber_edge = float(ber_theory(mod, ebn0_edge))
    reach = cov * (1 - block) * surv ** 0.15
    return dict(surv=surv, r_eff=r_eff, pr_edge=pr_edge, noise=noise, snr_edge=snr_edge, ebn0_edge=ebn0_edge,
                ber_edge=ber_edge, req=req, coverage=cov, channels=ch, load=load, block=block, reach=reach, pcm=p)


def hex_cells(rings, r=1.0):
    """Centres of a hexagonal cell layout (axial coordinates)."""
    pts = []
    for q in range(-rings, rings + 1):
        for s in range(max(-rings, -q - rings), min(rings, -q + rings) + 1):
            x = r * math.sqrt(3) * (q + s / 2)
            y = r * 1.5 * s
            pts.append((x, y))
    return np.array(pts)


def cochannel_ci(cluster, n_exp=4.0):
    """Signal-to-co-channel interference for 6 first-tier interferers: C/I = (sqrt(3N))^n / 6 [3]."""
    return 10 * math.log10((math.sqrt(3 * cluster)) ** n_exp / 6)


def monte_carlo_ber(mod, ebn0_db, nbits=200_000, rng=None):
    rng = rng or np.random.default_rng(0)
    sym, bits = modulate(mod, nbits, rng)
    rx = add_awgn(sym, mod, ebn0_db, rng)
    return float(np.mean(demodulate(mod, rx) != bits))


def modulate(mod, nbits, rng):
    k = MODS[mod]
    nbits -= nbits % k
    bits = rng.integers(0, 2, nbits)
    if mod == "ASK (OOK)":
        return bits.astype(complex) * math.sqrt(2), bits          # Eb_avg = 1
    if mod == "BPSK":
        return (2 * bits - 1).astype(complex), bits
    if mod == "QPSK":
        b = bits.reshape(-1, 2)
        return ((2 * b[:, 0] - 1) + 1j * (2 * b[:, 1] - 1)) / math.sqrt(2), bits
    b = bits.reshape(-1, 4)                                          # Gray 16-QAM
    lv = lambda b1, b0: (2 * b1 - 1) * (3 - 2 * b0)
    return (lv(b[:, 0], b[:, 1]) + 1j * lv(b[:, 2], b[:, 3])) / math.sqrt(10), bits


def add_awgn(sym, mod, ebn0_db, rng):
    k = MODS[mod]
    es = 1.0 if mod != "ASK (OOK)" else 1.0
    n0 = es / (k * undb(ebn0_db))
    sigma = math.sqrt(n0 / 2)
    if mod in ("ASK (OOK)", "BPSK"):
        return sym + sigma * rng.standard_normal(len(sym)) + 1j * sigma * rng.standard_normal(len(sym))
    return sym + sigma * (rng.standard_normal(len(sym)) + 1j * rng.standard_normal(len(sym)))


def demodulate(mod, rx):
    if mod == "ASK (OOK)":
        return (rx.real > math.sqrt(2) / 2).astype(int)
    if mod == "BPSK":
        return (rx.real > 0).astype(int)
    if mod == "QPSK":
        return np.column_stack([rx.real > 0, rx.imag > 0]).astype(int).ravel()
    s = rx * math.sqrt(10)
    out = np.column_stack([s.real > 0, np.abs(s.real) < 2, s.imag > 0, np.abs(s.imag) < 2]).astype(int)
    return out.ravel()


# ---------------------------------------------------------------------------
#  LAYER 3 - Satellite backup                    Unit IV   [5][6][7][8][9]
# ---------------------------------------------------------------------------
BANDS = {  # uplink GHz, downlink GHz, ITU-R P.838-3 (k, alpha) at downlink (horizontal pol., approx.)
    "C": dict(fu=6.0, fd=4.0, k=0.00065, a=1.121, sat_gt=0.0),
    "Ku": dict(fu=14.0, fd=12.0, k=0.02386, a=1.1825, sat_gt=5.0),
    "Ka": dict(fu=30.0, fd=20.0, k=0.09164, a=1.0568, sat_gt=10.0),
}
ORBITS = {"GEO": 35786.0, "LEO": 550.0}


def slant_range_km(alt_km, elev_deg):
    e = math.radians(elev_deg)
    r = R_EARTH + alt_km
    return math.sqrt(r ** 2 - (R_EARTH * math.cos(e)) ** 2) - R_EARTH * math.sin(e)


def rain_attenuation(rain, f_ghz, k, a, elev_deg, rain_height=5.0):
    """Simplified ITU-R P.618 [7] with P.838 [8] specific attenuation γ = k R^α."""
    if rain <= 0:
        return 0.0, 0.0
    gam = k * rain ** a
    e = math.radians(max(elev_deg, 5))
    ls = rain_height / math.sin(e)
    lg = ls * math.cos(e)
    rf = 1 / (1 + 0.78 * math.sqrt(lg * gam / f_ghz) - 0.38 * (1 - math.exp(-2 * lg)))
    return gam * ls * rf, gam


def dish_gain(d_m, f_ghz, eff=0.6):
    lam = C_LIGHT / (f_ghz * 1e9)
    return 10 * math.log10(eff * (math.pi * d_m / lam) ** 2)


def satellite_layer(rain=60.0, band="Ku", orbit="GEO", elev=50.0, eirp_dbw=50.0, dish_m=1.2, rate_kbps=512.0,
                    req_ebn0=6.0, eff=0.6, t_sys=200.0, wind=28.0, hpa_w=20.0, block=0.03, **_):
    b = BANDS[band]
    d = slant_range_km(ORBITS[orbit], elev)
    lu, ld = float(fspl_db(d, b["fu"] * 1e3)), float(fspl_db(d, b["fd"] * 1e3))
    a_d, gam = rain_attenuation(rain, b["fd"], b["k"], b["a"], elev)
    a_u = a_d * (b["fu"] / b["fd"]) ** 1.72           # frequency scaling of rain fade (P.618 §2.2.1.3 style)
    t_rain = 275 * (1 - 10 ** (-a_d / 10))           # sky noise added by the rain cell
    g_rx = dish_gain(dish_m, b["fd"], eff)
    g_tx = dish_gain(dish_m, b["fu"], eff)
    point = 0.5 * (max(0, wind - 20) / 10) ** 2       # wind-induced pointing loss of a small dish
    gt = g_rx - 10 * math.log10(t_sys + t_rain)
    atm = 0.5
    cn0_d = eirp_dbw - ld - a_d - atm - point + gt - K_BOLTZ_DBW
    eirp_up = 10 * math.log10(hpa_w) + g_tx
    cn0_u = eirp_up - lu - a_u - atm - point + b["sat_gt"] - K_BOLTZ_DBW
    cn0 = -10 * math.log10(10 ** (-cn0_u / 10) + 10 ** (-cn0_d / 10))
    ebn0 = cn0 - 10 * math.log10(rate_kbps * 1e3)
    margin = ebn0 - req_ebn0
    p_link = float(1 - qfunc(margin / 2.0))           # 2 dB fade-variability
    terminal_share = 0.75                             # citizens within reach of a VSAT shelter / hotspot
    reach = p_link * terminal_share * (1 - block)
    delay_ms = 2 * d / 299.792458                     # user -> satellite -> gateway (bent pipe)
    return dict(d=d, lu=lu, ld=ld, a_d=a_d, a_u=a_u, gam=gam, t_rain=t_rain, g_rx=g_rx, g_tx=g_tx, gt=gt,
                point=point, cn0_u=cn0_u, cn0_d=cn0_d, cn0=cn0, ebn0=ebn0, margin=margin, p_link=p_link,
                reach=reach, delay_ms=delay_ms, eirp_up=eirp_up, atm=atm)


# ---------------------------------------------------------------------------
#  SUPPLEMENTARY LAYER A - UAV aerial base station   [13][14]
# ---------------------------------------------------------------------------
UAV_ENV = {  # Al-Hourani et al. 2014 [13]: a, b, eta_LoS, eta_NLoS (dB)
    "Suburban": (4.88, 0.43, 0.1, 21.0),
    "Urban": (9.61, 0.16, 1.0, 20.0),
    "Dense urban": (12.08, 0.11, 1.6, 23.0),
    "High-rise urban": (27.23, 0.08, 2.3, 34.0),
}


def p_los(theta_deg, env):
    a, b, _, _ = UAV_ENV[env]
    return 1 / (1 + a * np.exp(-b * (np.asarray(theta_deg) - a)))


def uav_pathloss(h_m, r_m, f_ghz, env):
    """Air-to-ground mean path loss: FSPL + P_LoS·η_LoS + (1-P_LoS)·η_NLoS [13]."""
    _, _, el, en = UAV_ENV[env]
    d = np.sqrt(h_m ** 2 + np.asarray(r_m, dtype=float) ** 2)
    theta = np.degrees(np.arctan2(h_m, np.maximum(r_m, 1e-3)))
    pl = 20 * np.log10(4 * np.pi * f_ghz * 1e9 * d / C_LIGHT)
    pr = p_los(theta, env)
    return pl + pr * el + (1 - pr) * en


def uav_radius(h_m, f_ghz, env, pl_max):
    r = np.linspace(1, 20000, 4000)
    ok = uav_pathloss(h_m, r, f_ghz, env) <= pl_max
    return float(r[ok].max()) if ok.any() else 0.0


def uav_optimal_altitude(f_ghz, env, pl_max):
    hs = np.linspace(20, 5000, 250)
    rs = np.array([uav_radius(h, f_ghz, env, pl_max) for h in hs])
    i = int(np.argmax(rs))
    return float(hs[i]), float(rs[i]), hs, rs


def uav_layer(h_m=300.0, f_ghz=2.0, ptx_dbm=23.0, rx_sens_dbm=-92.0, env="Urban", n_uav=4, wind=28.0,
              wind_limit=15.0, noise_rise=6.0, city_km2=100.0, **_):
    pl_max = ptx_dbm - (rx_sens_dbm + noise_rise)
    r = uav_radius(h_m, f_ghz, env, pl_max)
    area = n_uav * math.pi * (r / 1000) ** 2
    cover = min(1.0, area / city_km2) * 0.95
    fly = 1 / (1 + math.exp((wind - wind_limit) / 2.0))   # drones are grounded in strong wind
    reach = cover * fly
    return dict(pl_max=pl_max, radius_m=r, area_km2=area, cover=cover, fly=fly, reach=reach)


# ---------------------------------------------------------------------------
#  SUPPLEMENTARY LAYER B - LoRa / device-to-device mesh   [15][16][17][18]
# ---------------------------------------------------------------------------
LORA_SNR_REQ = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}


def lora_bitrate(sf, bw_khz, cr=1):
    return sf * (bw_khz * 1e3) / 2 ** sf * 4 / (4 + cr)


def lora_sensitivity(sf, bw_khz, nf=6.0):
    return THERMAL_DBM_HZ + 10 * math.log10(bw_khz * 1e3) + nf + LORA_SNR_REQ[sf]


def lora_airtime(sf, bw_khz, payload, cr=1, preamble=8, header=True):
    """Time on air, Semtech AN1200.13 [16]."""
    tsym = 2 ** sf / (bw_khz * 1e3)
    de = 1 if (sf >= 11 and bw_khz <= 125) else 0
    h = 0 if header else 1
    num = 8 * payload - 4 * sf + 28 + 16 - 20 * h
    n_pay = 8 + max(math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamble + 4.25) * tsym + n_pay * tsym


def lora_range_km(sf, bw_khz, ptx_dbm, noise_rise=0.0, extra_loss=8.0):
    """Range from the measured 868 MHz model PL = 128.95 + 23.2 log10(d km) (Petäjäjärvi et al. [17])."""
    mcl = ptx_dbm + 2.0 - (lora_sensitivity(sf, bw_khz) + noise_rise) - extra_loss
    return 10 ** ((mcl - 128.95) / 23.2)


def giant_component(mean_degree):
    """Fraction of nodes in the giant component, S = 1 - exp(-k S) [18]."""
    s = 0.99
    for _ in range(200):
        s = 1 - math.exp(-mean_degree * s)
    return max(0.0, s)


def mesh_layer(sf=9, bw_khz=125.0, ptx_dbm=14.0, n_nodes=120, alive=70.0, payload=24, msgs_per_hr=12.0,
               area_km=8.0, noise_rise=6.0, extra_loss=8.0, **_):
    r = lora_range_km(sf, bw_khz, ptx_dbm, noise_rise, extra_loss)
    n_alive = n_nodes * alive / 100
    dens = n_alive / area_km ** 2
    k = dens * math.pi * min(r, area_km) ** 2
    conn = giant_component(k)
    toa = lora_airtime(sf, bw_khz, payload)
    hops = max(1.0, area_km / 2 / max(r, 0.05))
    g = n_alive * msgs_per_hr / 3600 * toa * hops         # offered load per channel (Erlang)
    p_aloha = math.exp(-2 * g)                              # pure ALOHA success [15]
    duty_ok = toa * msgs_per_hr / 3600 <= 0.01               # EU 868 MHz 1 % duty cycle
    reach = conn * p_aloha * 0.7                             # 0.7: share of citizens with a mesh-capable device
    return dict(range_km=r, rb=lora_bitrate(sf, bw_khz), sens=lora_sensitivity(sf, bw_khz), toa=toa,
                mean_degree=k, conn=conn, g=g, p_aloha=p_aloha, duty_ok=duty_ok, hops=hops,
                n_alive=n_alive, reach=reach)


# ---------------------------------------------------------------------------
#  HYBRID NETWORK
# ---------------------------------------------------------------------------
LAYER_STATIC = {  # qualitative 0..1 scores, from the surveyed literature (see references)
    # name: (deploy speed, cost efficiency, two-way, energy independence)
    "Analog emergency radio": (0.9, 0.95, 0.1, 0.8),
    "Digital mobile network": (0.3, 0.8, 1.0, 0.3),
    "Satellite backup": (0.6, 0.35, 1.0, 0.7),
    "UAV aerial base station": (0.85, 0.5, 1.0, 0.4),
    "LoRa / D2D mesh": (0.9, 0.9, 1.0, 0.9),
}
DATA_RATE = {"Analog emergency radio": 15e3, "Digital mobile network": 2e6, "Satellite backup": 512e3,
             "UAV aerial base station": 10e6, "LoRa / D2D mesh": 1.8e3}


def evaluate_all(storm, terrain="Coastal city (assigned)", overrides=None):
    """Reach (0..1) of every layer for a given storm, plus hybrid availabilities."""
    from . import config as C
    t = TERRAIN[terrain]
    o = overrides or {}
    an = analog_layer(**{**C.ANALOG, "noise_rise": storm["noise_rise"], "wind": storm["wind"],
                         "clutter_db": C.ANALOG["clutter_db"] + t["clutter"], "shadow_db": t["shadow"],
                         **o.get("an", {})})
    mo = mobile_layer(**{**C.DIGITAL, "mod": "QPSK", "towers_down": storm["towers_down"], "surge": storm["surge"],
                         "noise_rise": storm["noise_rise"], "extra_loss": t["clutter"], "shadow_db": t["shadow"],
                         **o.get("mo", {})})
    sa = satellite_layer(**{**C.SAT, "rain": storm["rain"] * t["rain_mult"], "wind": storm["wind"],
                            "block": t["sat_block"], **o.get("sa", {})})
    ua = uav_layer(**{**C.UAV, "env": t["uav_env"], "wind": storm["wind"], "noise_rise": storm["noise_rise"],
                      **o.get("ua", {})})
    me = mesh_layer(**{**C.MESH, "noise_rise": storm["noise_rise"], "extra_loss": t["mesh_loss"],
                       **o.get("me", {})})
    res = {C.L_AN: an, C.L_MO: mo, C.L_SA: sa, C.L_UAV: ua, C.L_MESH: me}
    reach = {k: v["reach"] for k, v in res.items()}
    two_way = [C.L_MO, C.L_SA, C.L_UAV, C.L_MESH]
    core = 1 - (1 - reach[C.L_MO]) * (1 - reach[C.L_SA])
    ext = 1 - np.prod([1 - reach[k] for k in two_way])
    alert = 1 - np.prod([1 - reach[k] for k in reach])
    return dict(layers=res, reach=reach, hybrid_core=core, hybrid_ext=float(ext), alert=float(alert))
