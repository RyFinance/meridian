"""Hand-picked pilot of known delisted US common stocks, 2001-2023 (mostly 2008-2023).

Fields are *expected facts from general knowledge*, used only as validation targets; the chain
must re-derive them from free sources. `event_date` = deal close (acquisition), seizure/petition
date (failure/bankruptcy) or liquidation delisting. `cik_guess` is a hint only: the chain accepts it
solely if data.sec.gov's entity name / former names match `name_q`; otherwise it falls back to the
EDGAR company-name autocomplete. `successor` = an OTC ticker known to have been used after the
exchange delisting (bankruptcies), None if unknown/none.
Also includes two *control* rows (still-listed, ticker changed) to test the ticker-history chain.
"""
from __future__ import annotations

# (key, name_q, cik_guess, exchange, ticker, event_type, event_date, successor)
PILOT = [
    # --- failures / bankruptcies -------------------------------------------------------------
    ("ENRON", "ENRON CORP", 1024401, "NYSE", "ENE", "bankruptcy", "2001-12-02", "ENRNQ"),
    ("LEHMAN", "LEHMAN BROTHERS HOLDINGS", 806085, "NYSE", "LEH", "bankruptcy", "2008-09-15", "LEHMQ"),
    ("WAMU", "WASHINGTON MUTUAL", 933136, "NYSE", "WM", "bankruptcy", "2008-09-26", "WAMUQ"),
    ("CIRCUITCITY", "CIRCUIT CITY STORES", 104599, "NYSE", "CC", "bankruptcy", "2008-11-10", "CCTYQ"),
    ("GM_OLD", "GENERAL MOTORS CORP", 40730, "NYSE", "GM", "bankruptcy", "2009-06-01", "MTLQQ"),
    ("BLOCKBUSTER", "BLOCKBUSTER INC", 1085734, "NYSE", "BBI", "bankruptcy", "2010-09-23", "BLOAQ"),
    ("AMR", "AMR CORP", 6201, "NYSE", "AMR", "bankruptcy", "2011-11-29", "AAMRQ"),
    ("KODAK", "EASTMAN KODAK", 31235, "NYSE", "EK", "bankruptcy", "2012-01-19", "EKDKQ"),
    ("A123", "A123 SYSTEMS", None, "NASDAQ", "AONE", "bankruptcy", "2012-10-16", "AONEQ"),
    ("RADIOSHACK", "RADIOSHACK CORP", 96289, "NYSE", "RSH", "bankruptcy", "2015-02-05", "RSHCQ"),
    ("SUNEDISON", "SUNEDISON", 945436, "NYSE", "SUNE", "bankruptcy", "2016-04-21", "SUNEQ"),
    ("SEARS", "SEARS HOLDINGS", 1310067, "NASDAQ", "SHLD", "bankruptcy", "2018-10-15", "SHLDQ"),
    ("PIER1", "PIER 1 IMPORTS", 278130, "NYSE", "PIR", "bankruptcy", "2020-02-17", "PIRRQ"),
    ("FRONTIER", "FRONTIER COMMUNICATIONS CORP", 20520, "NASDAQ", "FTR", "bankruptcy", "2020-04-14", "FTRCQ"),
    ("JCPENNEY", "PENNEY J C CO", 1166126, "NYSE", "JCP", "bankruptcy", "2020-05-15", "JCPNQ"),
    ("HERTZ", "HERTZ GLOBAL HOLDINGS", 1657853, "NYSE", "HTZ", "bankruptcy", "2020-05-22", "HTZGQ"),
    ("CHESAPEAKE", "CHESAPEAKE ENERGY", 895126, "NYSE", "CHK", "bankruptcy", "2020-06-28", "CHKAQ"),
    ("PARTYCITY", "PARTY CITY HOLDCO", 1592058, "NYSE", "PRTY", "bankruptcy", "2023-01-17", "PRTYQ"),
    ("SVB", "SVB FINANCIAL GROUP", 719739, "NASDAQ", "SIVB", "failure", "2023-03-10", "SIVBQ"),
    ("SIGNATURE", "SIGNATURE BANK", None, "NASDAQ", "SBNY", "failure", "2023-03-12", "SBNYQ"),
    ("BBBY", "BED BATH & BEYOND", 886158, "NASDAQ", "BBBY", "bankruptcy", "2023-04-23", "BBBYQ"),
    ("FIRSTREPUBLIC", "FIRST REPUBLIC BANK", None, "NYSE", "FRC", "failure", "2023-05-01", "FRCB"),
    ("RITEAID", "RITE AID CORP", 84129, "NYSE", "RAD", "bankruptcy", "2023-10-15", "RADCQ"),
    ("WEWORK", "WEWORK INC", 1813756, "NYSE", "WE", "bankruptcy", "2023-11-06", "WEWKQ"),
    # --- acquisitions / take-privates / liquidations ------------------------------------------
    ("BEARSTEARNS", "BEAR STEARNS COMPANIES", 777001, "NYSE", "BSC", "acquired", "2008-05-30", None),
    ("COUNTRYWIDE", "COUNTRYWIDE FINANCIAL", 25191, "NYSE", "CFC", "acquired", "2008-07-01", None),
    ("ANHEUSER", "ANHEUSER-BUSCH COMPANIES", 310569, "NYSE", "BUD", "acquired", "2008-11-18", None),
    ("WACHOVIA", "WACHOVIA CORP", 36995, "NYSE", "WB", "acquired", "2008-12-31", None),
    ("MERRILL", "MERRILL LYNCH & CO", 65100, "NYSE", "MER", "acquired", "2009-01-01", None),
    ("GENENTECH", "GENENTECH INC", 318771, "NYSE", "DNA", "acquired", "2009-03-26", None),
    ("WYETH", "WYETH", 5187, "NYSE", "WYE", "acquired", "2009-10-15", None),
    ("SUNMICRO", "SUN MICROSYSTEMS", 709519, "NASDAQ", "JAVA", "acquired", "2010-01-26", None),
    ("BNSF", "BURLINGTON NORTHERN SANTA FE", 934612, "NYSE", "BNI", "acquired", "2010-02-12", None),
    ("MOTOMOBILITY", "MOTOROLA MOBILITY HOLDINGS", 1495569, "NYSE", "MMI", "acquired", "2012-05-22", None),
    ("HEINZ", "HEINZ H J CO", 46640, "NYSE", "HNZ", "acquired", "2013-06-07", None),
    ("DELL_OLD", "DELL INC", 826083, "NASDAQ", "DELL", "acquired", "2013-10-29", None),
    ("EMC", "EMC CORP", 790070, "NYSE", "EMC", "acquired", "2016-09-07", None),
    ("LINKEDIN", "LINKEDIN CORP", 1271024, "NYSE", "LNKD", "acquired", "2016-12-08", None),
    ("WHOLEFOODS", "WHOLE FOODS MARKET", 865436, "NASDAQ", "WFM", "acquired", "2017-08-28", None),
    ("MONSANTO", "MONSANTO CO", 1110783, "NYSE", "MON", "acquired", "2018-06-07", None),
    ("TIMEWARNER", "TIME WARNER INC", 1105705, "NYSE", "TWX", "acquired", "2018-06-14", None),
    ("REDHAT", "RED HAT INC", 1087423, "NYSE", "RHT", "acquired", "2019-07-09", None),
    ("ALTABA", "ALTABA INC", 1011006, "NASDAQ", "AABA", "liquidation", "2019-10-02", None),
    ("CELGENE", "CELGENE CORP", 816284, "NASDAQ", "CELG", "acquired", "2019-11-20", None),
    ("TIFFANY", "TIFFANY & CO", 98246, "NYSE", "TIF", "acquired", "2021-01-07", None),
    ("SLACK", "SLACK TECHNOLOGIES", 1764925, "NYSE", "WORK", "acquired", "2021-07-21", None),
    ("XILINX", "XILINX INC", 743988, "NASDAQ", "XLNX", "acquired", "2022-02-14", None),
    ("TWITTER", "TWITTER INC", 1418091, "NYSE", "TWTR", "acquired", "2022-10-27", None),
    ("ACTIVISION", "ACTIVISION BLIZZARD", 718877, "NASDAQ", "ATVI", "acquired", "2023-10-13", None),
]

# Controls: still listed, ticker changed (tests the ticker-history link, not delisting).
CONTROLS = [
    ("META_CTRL", "META PLATFORMS", 1326801, "NASDAQ", "FB", "ticker_change", "2022-06-09", "META"),
    ("YAHOO_CTRL", "ALTABA INC", 1011006, "NASDAQ", "YHOO", "ticker_change", "2017-06-19", "AABA"),
]

FIELDS = ("key", "name_q", "cik_guess", "exchange", "ticker", "event_type", "event_date", "successor")


def rows(include_controls: bool = True) -> list[dict]:
    src = PILOT + (CONTROLS if include_controls else [])
    return [dict(zip(FIELDS, r)) for r in src]
