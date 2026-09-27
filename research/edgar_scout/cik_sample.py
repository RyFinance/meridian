"""Curated CIK sample for the submissions-API probe: active large/mid caps (breadth check),
known institutional 13F filers (13F-HR filing-history check), and delisted/bankrupt/acquired
issuers (survivorship + point-in-time-to-delisting check). CIKs are from memory/public
knowledge -- each is verified against the "name" field returned by data.sec.gov before use;
unresolved (404 or name-mismatch) entries are logged, not silently trusted.
"""

ACTIVE = {
    "AAPL": 320193, "MSFT": 789019, "AMZN": 1018724, "GOOGL": 1652044, "META": 1326801,
    "NVDA": 1045810, "TSLA": 1318605, "JPM": 19617, "BAC": 70858, "WFC": 72971,
    "XOM": 34088, "JNJ": 200406, "PG": 80424, "KO": 21344, "WMT": 104169,
    "DIS": 1744489, "IBM": 51143, "INTC": 50863, "CSCO": 858877, "ORCL": 1341439,
    "CRM": 1108524, "ADBE": 796343, "PFE": 78003, "MRK": 310158, "UNH": 731766,
    "HD": 354950, "V": 1403161, "MA": 1141391, "GS": 886982, "C": 831001,
    "BA": 12927, "CAT": 18230, "GE": 40545, "T": 732717, "VZ": 732712,
    "CVX": 93410, "LLY": 59478, "COST": 909832, "NKE": 320187, "PLTR": 1321655,
}

INSTITUTIONAL_13F = {
    "BERKSHIRE_HATHAWAY": 1067983, "BLACKROCK": 1364742, "STATE_STREET_CORP": 93751,
    "VANGUARD_GROUP": 102909, "T_ROWE_PRICE": 1113169, "RENAISSANCE_TECH": 1037389,
    "CITADEL_ADVISORS": 1423053, "SOROS_FUND_MGMT": 1029160, "BRIDGEWATER": 1350694,
    "D_E_SHAW": 1009207,
}

DELISTED_FAILED = {
    # SIGNATURE_BANK deliberately omitted: our best-guess CIK (1288776) resolved to an
    # unrelated filer (Google Inc's old CIK) and a corrected CIK could not be found via
    # efts.sec.gov full-text search within budget (www.sec.gov/cgi-bin/browse-edgar and
    # company_tickers.json, the normal name->CIK lookups, are blocked in this environment;
    # see the access-probe results). Logged as an unresolved name, not silently dropped.
    "SIVB_SVB_FINANCIAL": 719739, "FIRST_REPUBLIC_BANK": 1132979,
    "BED_BATH_BEYOND": 886158, "CELGENE": 816284, "TWITTER": 1418091,
    "SEARS_HOLDINGS": 1310067, "LEHMAN_BROTHERS_HOLDINGS": 806085, "WASHINGTON_MUTUAL": 933136,
    "RITE_AID": 84129, "PARTY_CITY_HOLDCO": 1592058, "WEWORK": 1813756,
    "SILVERGATE_CAPITAL": 1312109, "ENRON": 1024401, "GENERAL_MOTORS_OLD": 40730,
}

# ticker used for the (separate, price-only, no-return) yfinance coverage probe
DELISTED_TICKERS = {
    "SIVB_SVB_FINANCIAL": "SIVB", "FIRST_REPUBLIC_BANK": "FRC", "SIGNATURE_BANK": "SBNY",
    "BED_BATH_BEYOND": "BBBY", "CELGENE": "CELG", "TWITTER": "TWTR",
    "SEARS_HOLDINGS": "SHLDQ", "LEHMAN_BROTHERS_HOLDINGS": "LEHMQ", "WASHINGTON_MUTUAL": "WAMUQ",
    "RITE_AID": "RAD", "PARTY_CITY_HOLDCO": "PRTY", "WEWORK": "WE",
    "SILVERGATE_CAPITAL": "SI", "ENRON": "ENRNQ", "GENERAL_MOTORS_OLD": "MTLQQ",
}

ALL = {**{f"active/{k}": v for k, v in ACTIVE.items()},
       **{f"institutional_13f/{k}": v for k, v in INSTITUTIONAL_13F.items()},
       **{f"delisted/{k}": v for k, v in DELISTED_FAILED.items()}}
