"""Reference list, numbers match the [n] tags in models.py. Check links with tools/check_references.py."""
import textwrap

from . import ui

REFERENCES = [
    ("[1]", "S. Haykin and M. Moher, Communication Systems, 5th ed. Wiley, 2009.",
     "AM/FM modulation, envelope detection, FM figure of merit",
     "https://books.google.com/books?vid=ISBN9780471697909"),
    ("[2]", "J. G. Proakis and M. Salehi, Digital Communications, 5th ed. McGraw-Hill, 2008.",
     "BER of ASK/BPSK/QPSK/16-QAM, Q-function, Monte-Carlo method",
     "https://books.google.com/books?vid=ISBN9780072957167"),
    ("[3]", "T. S. Rappaport, Wireless Communications: Principles and Practice, 2nd ed. Prentice Hall, 2002.",
     "cellular concept, frequency reuse, C/I, cell splitting, Erlang-B",
     "https://books.google.com/books?vid=ISBN9780130422323"),
    ("[4]", "B. P. Lathi and Z. Ding, Modern Digital and Analog Communication Systems, 4th ed. OUP, 2009.",
     "sampling theorem, PCM, quantisation noise, SQNR = 6.02n + 1.76 dB",
     "https://books.google.com/books?vid=ISBN9780195331455"),
    ("[5]", "G. Maral, M. Bousquet and Z. Sun, Satellite Communications Systems, 6th ed. Wiley, 2020.",
     "slant range, link budget, C/N0, uplink/downlink combination",
     "https://doi.org/10.1002/9781119673811"),
    ("[6]", "T. Pratt and J. E. Allnutt, Satellite Communications, 3rd ed. Wiley, 2019.",
     "G/T, rain noise temperature, GEO vs LEO",
     "https://books.google.com/books?vid=ISBN9781119482178"),
    ("[7]", "ITU-R Recommendation P.618, Propagation data and prediction methods required for the design of "
            "Earth-space telecommunication systems.", "rain-attenuation path reduction",
     "https://www.itu.int/rec/R-REC-P.618/en"),
    ("[8]", "ITU-R Recommendation P.838-3, Specific attenuation model for rain for use in prediction methods, 2005.",
     "γ = k·R^α coefficients",
     "https://www.itu.int/rec/R-REC-P.838-3-200503-I/en"),
    ("[9]", "ITU-R Recommendation P.525, Calculation of free-space attenuation.", "FSPL formula",
     "https://www.itu.int/rec/R-REC-P.525/en"),
    ("[10]", "ITU-R Recommendation P.372, Radio noise.", "man-made noise figure in urban areas",
     "https://www.itu.int/rec/R-REC-P.372/en"),
    ("[11]", "H. Taub, D. L. Schilling and G. Saha, Taub's Principles of Communication Systems, 4th ed. McGraw-Hill, 2013.",
     "FM threshold effect (click-noise model)",
     "https://books.google.com/books?vid=ISBN9781259029851"),
    ("[12]", "M. Hata, \"Empirical formula for propagation loss in land mobile radio services,\" IEEE Trans. "
             "Vehicular Technology, vol. 29, no. 3, pp. 317–325, 1980.", "Okumura–Hata urban path loss",
     "https://doi.org/10.1109/T-VT.1980.23859"),
    ("[13]", "A. Al-Hourani, S. Kandeepan and S. Lardner, \"Optimal LAP altitude for maximum coverage,\" IEEE "
             "Wireless Communications Letters, vol. 3, no. 6, pp. 569–572, 2014.", "UAV air-to-ground model",
     "https://doi.org/10.1109/LWC.2014.2342736"),
    ("[14]", "M. Mozaffari, W. Saad, M. Bennis, Y.-H. Nam and M. Debbah, \"A tutorial on UAVs for wireless "
             "networks: applications, challenges, and open problems,\" IEEE Communications Surveys & Tutorials, "
             "vol. 21, no. 3, pp. 2334–2360, 2019.", "UAV base stations for disaster recovery",
     "https://doi.org/10.1109/COMST.2019.2902862"),
    ("[15]", "N. Abramson, \"The ALOHA system — another alternative for computer communications,\" Proc. AFIPS "
             "Fall Joint Computer Conference, pp. 281–285, 1970.", "pure-ALOHA collision model",
     "https://doi.org/10.1145/1478462.1478502"),
    ("[16]", "Semtech Corp., SX1276/77/78/79 LoRa transceiver datasheet (time-on-air formula).", "LoRa time on air, bit rate",
     "https://www.semtech.com/products/wireless-rf/lora-connect/sx1276"),
    ("[17]", "J. Petäjäjärvi, K. Mikhaylov, A. Roivainen, T. Hänninen and M. Pettissalo, \"On the coverage of "
             "LPWANs: range evaluation and channel attenuation model for LoRa technology,\" Proc. 14th Int. Conf. "
             "on ITS Telecommunications (ITST), pp. 55–59, 2015.", "measured LoRa path-loss model",
     "https://doi.org/10.1109/ITST.2015.7377400"),
    ("[18]", "M. E. J. Newman, Networks: An Introduction. Oxford University Press, 2010.",
     "giant-component (percolation) approximation",
     "https://doi.org/10.1093/acprof:oso/9780199206650.001.0001"),
    ("[19]", "T. Sakano et al., \"Disaster-resilient networking: a new vision based on movable and deployable "
             "resource units,\" IEEE Network, vol. 27, no. 4, pp. 40–46, 2013.",
     "lessons of the 2011 Great East Japan Earthquake; deployable units",
     "https://doi.org/10.1109/MNET.2013.6574664"),
    ("[20]", "FCC Public Safety and Homeland Security Bureau, \"2017 Atlantic Hurricane Season Impact on "
             "Communications: Report and Recommendations,\" Aug. 2018.", "cell-site outages after hurricanes",
     "https://docs.fcc.gov/public/attachments/DOC-353805A1.pdf"),
    ("[21]", "A. Augustin, J. Yi, T. Clausen and W. M. Townsley, \"A study of LoRa: long range & low power networks "
             "for the Internet of Things,\" Sensors, vol. 16, no. 9, 1466, 2016.", "LoRa physical layer",
     "https://doi.org/10.3390/s16091466"),
    ("[22]", "M. C. Bor, U. Roedig, T. Voigt and J. M. Alonso, \"Do LoRa low-power wide-area networks scale?\" "
             "Proc. ACM MSWiM, pp. 59–67, 2016.", "LoRa collisions and scalability",
     "https://doi.org/10.1145/2988287.2989163"),
    ("[23]", "C. E. Shannon, \"A mathematical theory of communication,\" Bell System Technical Journal, vol. 27, "
             "no. 3, pp. 379–423, 1948.", "channel capacity C = B log2(1 + SNR)",
     "https://doi.org/10.1002/j.1538-7305.1948.tb01338.x"),
    ("[24]", "J. R. Carson, \"Notes on the theory of modulation,\" Proc. IRE, vol. 10, no. 1, pp. 57–64, 1922.",
     "Carson bandwidth rule",
     "https://doi.org/10.1109/JRPROC.1922.219793"),
    ("[25]", "3GPP TR 38.811, Study on New Radio (NR) to support non-terrestrial networks.",
     "satellite integration with mobile networks",
     "https://portal.3gpp.org/desktopmodules/Specifications/SpecificationDetails.aspx?specificationId=3234"),
    ("[26]", "I. del Portillo, B. G. Cameron and E. F. Crawley, \"A technical comparison of three low earth orbit "
             "satellite constellation systems to provide global broadband,\" Acta Astronautica, vol. 159, "
             "pp. 123–135, 2019.", "LEO constellation link budgets and latency",
     "https://doi.org/10.1016/j.actaastro.2019.03.040"),
    ("[27]", "D. Middleton, \"Statistical-physical models of electromagnetic interference,\" IEEE Trans. "
             "Electromagnetic Compatibility, vol. EMC-19, no. 3, pp. 106–127, 1977.", "impulsive (storm) noise",
     "https://doi.org/10.1109/TEMC.1977.303527"),
    ("[28]", "ITU-R Recommendation P.526, Propagation by diffraction.",
     "knife-edge diffraction loss J(v) over the Himalayan ridges",
     "https://www.itu.int/rec/R-REC-P.526/en"),
    ("[29]", "ITU-R Recommendation P.839, Rain height model for prediction methods.",
     "rain height; shorter rain path for a station at 1.6 km altitude",
     "https://www.itu.int/rec/R-REC-P.839/en"),
    ("[30]", "ICAO Doc 7488/3, Manual of the ICAO Standard Atmosphere, 1993.",
     "air density at altitude (UAV thrust and endurance)",
     "https://store.icao.int/en/manual-of-the-icao-standard-atmosphere-extended-to-80-kilometres-262500-feet-doc-7488"),
    ("[31]", "N. Caine, \"The rainfall intensity–duration control of shallow landslides and debris flows,\" "
             "Geografiska Annaler: Series A, vol. 62, no. 1–2, pp. 23–27, 1980.", "landslide rainfall threshold "
     "I = 14.82·D^−0.39",
     "https://doi.org/10.1080/04353676.1980.11879996"),
    ("[32]", "F. Guzzetti, S. Peruccacci, M. Rossi and C. P. Stark, \"The rainfall intensity–duration control of "
             "shallow landslides and debris flows: an update,\" Landslides, vol. 5, no. 1, pp. 3–17, 2008.",
     "landslide thresholds (update and discussion)",
     "https://doi.org/10.1007/s10346-007-0112-1"),
    ("[33]", "T. G. Farr et al., \"The Shuttle Radar Topography Mission,\" Reviews of Geophysics, vol. 45, "
             "no. 2, RG2004, 2007.", "elevation data (SRTM) for Gangtok and the Teesta valley",
     "https://doi.org/10.1029/2005RG000183"),
    ("[34]", "A. D. Nobre et al., \"Height Above the Nearest Drainage – a hydrologically relevant new terrain "
             "model,\" Journal of Hydrology, vol. 404, no. 1–2, pp. 13–29, 2011.", "flood zone of the GLOF (height above "
     "the Teesta)",
     "https://doi.org/10.1016/j.jhydrol.2011.03.051"),
    ("[35]", "A. Sattar et al., \"The Sikkim flood of October 2023: drivers, causes and impacts of a multihazard "
             "cascade,\" Science, vol. 387, no. 6740, eads2659, 2025.", "the 2023 South Lhonak GLOF down the Teesta",
     "https://doi.org/10.1126/science.ads2659"),
    ("[36]", "OpenStreetMap contributors, map data (roads, rivers, settlements), openstreetmap.org, ODbL licence.",
     "real roads (fibre and power routes), rivers and settlements",
     "https://www.openstreetmap.org/copyright"),
    ("[37]", "OpenTopoData public API, opentopodata.org (SRTM 30 m and 90 m datasets).",
     "access to the elevation data",
     "https://www.opentopodata.org/"),
    ("[38]", "K. Aki, \"Maximum likelihood estimate of b in the formula log N = a − bM and its confidence limits,\" "
             "Bulletin of the Earthquake Research Institute, vol. 43, pp. 237–239, 1965.", "b-value of the Sikkim "
     "earthquake catalogue",
     ""),
    ("[39]", "B. Gutenberg and C. F. Richter, \"Frequency of earthquakes in California,\" Bulletin of the "
             "Seismological Society of America, vol. 34, no. 4, pp. 185–188, 1944.", "magnitude–frequency law",
     "https://doi.org/10.1785/BSSA0340040185"),
    ("[40]", "D. A. Vallado, Fundamentals of Astrodynamics and Applications, 4th ed. Microcosm Press, 2013.",
     "Kepler propagation, J2 drift, look angles of real satellites",
     "https://books.google.com/books?vid=ISBN9781881883180"),
    ("[41]", "NOAA Space Weather Prediction Center, \"NOAA Space Weather Scales\", swpc.noaa.gov.",
     "G (geomagnetic) and R (radio blackout) scales",
     "https://www.swpc.noaa.gov/noaa-scales-explanation"),
    ("[42]", "Live data services (accessed on the date of the snapshot): Open-Meteo forecast and historical "
             "(ERA5) APIs; CelesTrak GP data; GDACS; NASA EONET v3; USGS earthquake catalogue; NOAA SWPC; "
             "OpenTopoData; Natural Earth.", "menu 13, live-data hub (option 6 writes the exact citations)",
     "https://open-meteo.com/"),
]


def print_references():
    ui.head("REFERENCES USED IN THE MODELS", ui.cyan)
    ui.note("Under each one: what we used it for. Double check the edition against the library copy.")
    for tag, ref, use, link in REFERENCES:
        print()
        lines = textwrap.wrap(ref, ui.W - 10)
        print(f"  {ui.bold(f'{tag:>5}')} {lines[0]}")
        for ln in lines[1:]:
            print(f"        {ln}")
        if link:
            print(ui.cyan(f"        {link}"))
        print(ui.grey(f"        used for: {use}"))
