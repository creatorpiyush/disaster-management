"""Sources behind every model in the simulator (numbers match the [n] tags in models.py).

Check each entry against the edition or version available to you before citing it in the article.
"""
from . import ui

REFERENCES = [
    ("[1]", "S. Haykin and M. Moher, Communication Systems, 5th ed. Wiley, 2009.",
     "AM/FM modulation, envelope detection, FM figure of merit"),
    ("[2]", "J. G. Proakis and M. Salehi, Digital Communications, 5th ed. McGraw-Hill, 2008.",
     "BER of ASK/BPSK/QPSK/16-QAM, Q-function, Monte-Carlo method"),
    ("[3]", "T. S. Rappaport, Wireless Communications: Principles and Practice, 2nd ed. Prentice Hall, 2002.",
     "cellular concept, frequency reuse, C/I, cell splitting, Erlang-B"),
    ("[4]", "B. P. Lathi and Z. Ding, Modern Digital and Analog Communication Systems, 4th ed. OUP, 2009.",
     "sampling theorem, PCM, quantisation noise, SQNR = 6.02n + 1.76 dB"),
    ("[5]", "G. Maral, M. Bousquet and Z. Sun, Satellite Communications Systems, 6th ed. Wiley, 2020.",
     "slant range, link budget, C/N0, uplink/downlink combination"),
    ("[6]", "T. Pratt and J. E. Allnutt, Satellite Communications, 3rd ed. Wiley, 2019.",
     "G/T, rain noise temperature, GEO vs LEO"),
    ("[7]", "ITU-R Recommendation P.618, Propagation data and prediction methods required for the design of "
            "Earth-space telecommunication systems.", "rain-attenuation path reduction"),
    ("[8]", "ITU-R Recommendation P.838-3, Specific attenuation model for rain for use in prediction methods, 2005.",
     "γ = k·R^α coefficients"),
    ("[9]", "ITU-R Recommendation P.525, Calculation of free-space attenuation.", "FSPL formula"),
    ("[10]", "ITU-R Recommendation P.372, Radio noise.", "man-made noise figure in urban areas"),
    ("[11]", "H. Taub, D. L. Schilling and G. Saha, Principles of Communication Systems, 4th ed. McGraw-Hill, 2013.",
     "FM threshold effect (click-noise model)"),
    ("[12]", "M. Hata, \"Empirical formula for propagation loss in land mobile radio services,\" IEEE Trans. "
             "Vehicular Technology, vol. 29, no. 3, pp. 317–325, 1980.", "Okumura–Hata urban path loss"),
    ("[13]", "A. Al-Hourani, S. Kandeepan and S. Lardner, \"Optimal LAP altitude for maximum coverage,\" IEEE "
             "Wireless Communications Letters, vol. 3, no. 6, pp. 569–572, 2014.", "UAV air-to-ground model"),
    ("[14]", "M. Mozaffari, W. Saad, M. Bennis, Y.-H. Nam and M. Debbah, \"A tutorial on UAVs for wireless "
             "networks: applications, challenges, and open problems,\" IEEE Communications Surveys & Tutorials, "
             "vol. 21, no. 3, pp. 2334–2360, 2019.", "UAV base stations for disaster recovery"),
    ("[15]", "N. Abramson, \"The ALOHA system — another alternative for computer communications,\" Proc. AFIPS "
             "Fall Joint Computer Conference, 1970.", "pure-ALOHA collision model"),
    ("[16]", "Semtech Corp., AN1200.13 \"LoRa Modem Designer's Guide\", 2013.", "LoRa time on air, bit rate"),
    ("[17]", "J. Petäjäjärvi, K. Mikhaylov, A. Roivainen, T. Hänninen and M. Pettissalo, \"On the coverage of "
             "LPWANs: range evaluation and channel attenuation model for LoRa technology,\" Proc. 14th Int. Conf. "
             "on ITS Telecommunications (ITST), 2015.", "measured LoRa path-loss model"),
    ("[18]", "M. E. J. Newman, Networks: An Introduction. Oxford University Press, 2010.",
     "giant-component (percolation) approximation"),
    ("[19]", "T. Sakano et al., \"Disaster-resilient networking: a new vision based on movable and deployable "
             "resource units,\" IEEE Network, vol. 27, no. 4, pp. 40–46, 2013.",
     "lessons of the 2011 Great East Japan Earthquake; deployable units"),
    ("[20]", "FCC Public Safety and Homeland Security Bureau, \"2017 Atlantic Hurricane Season Impact on "
             "Communications: Report and Recommendations,\" Aug. 2018.", "cell-site outages after hurricanes"),
    ("[21]", "A. Augustin, J. Yi, T. Clausen and W. M. Townsley, \"A study of LoRa: long range & low power networks "
             "for the Internet of Things,\" Sensors, vol. 16, no. 9, 1466, 2016.", "LoRa physical layer"),
    ("[22]", "M. C. Bor, U. Roedig, T. Voigt and J. M. Alonso, \"Do LoRa low-power wide-area networks scale?\" "
             "Proc. ACM MSWiM, 2016.", "LoRa collisions and scalability"),
    ("[23]", "C. E. Shannon, \"A mathematical theory of communication,\" Bell System Technical Journal, vol. 27, "
             "1948.", "channel capacity C = B log2(1 + SNR)"),
    ("[24]", "J. R. Carson, \"Notes on the theory of modulation,\" Proc. IRE, vol. 10, no. 1, pp. 57–64, 1922.",
     "Carson bandwidth rule"),
    ("[25]", "3GPP TR 38.811, Study on New Radio (NR) to support non-terrestrial networks.",
     "satellite integration with mobile networks"),
    ("[26]", "I. del Portillo, B. G. Cameron and E. F. Crawley, \"A technical comparison of three low earth orbit "
             "satellite constellation systems to provide global broadband,\" Acta Astronautica, vol. 159, "
             "pp. 123–135, 2019.", "LEO constellation link budgets and latency"),
    ("[27]", "D. Middleton, \"Statistical-physical models of electromagnetic interference,\" IEEE Trans. "
             "Electromagnetic Compatibility, vol. EMC-19, no. 3, pp. 106–127, 1977.", "impulsive (storm) noise"),
]


def print_references():
    ui.head("REFERENCES USED IN THE MODELS", ui.cyan)
    ui.note("Each entry is followed by what it is used for in the simulator. Please verify the edition or "
            "version you cite against your library copy.")
    for tag, ref, use in REFERENCES:
        print()
        lines = ui._wrap(ref, ui.W - 10)
        print(f"  {ui.bold(f'{tag:>5}')} {lines[0]}")
        for ln in lines[1:]:
            print(f"        {ln}")
        print(ui.grey(f"        used for: {use}"))
