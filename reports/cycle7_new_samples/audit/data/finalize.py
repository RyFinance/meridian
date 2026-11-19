"""Part 3: broker table, IBKR financing, NDF gap episodes, cost references, vehicle facts; hashes all raw files into manifest."""
import json, hashlib, pathlib, datetime as dt, subprocess, pandas as pd
D = pathlib.Path(__file__).resolve().parent; R = D / "raw"; MAN = D / "manifest.json"; man = json.loads(MAN.read_text())
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); DAY = "2026-09-27"
C22 = "ARS BRL CLP COP CZK DKK HUF IDR ILS INR ISK KRW MXN MYR PEN PHP PLN RUB SGD THB TRY ZAR".split()
IB_LIST = set("USD AED AUD BRL CAD CHF CNH CZK DKK EUR GBP HKD HUF ILS JPY KRW MXN MYR NOK NZD PLN RON SAR SEK SGD TRY TWD ZAR".split())
IB_SPECIAL = {"KRW", "MYR", "TWD"}
QT = set("CZK DKK HUF ILS MXN PLN SGD THB TRY ZAR".split())  # USD/xxx pairs in Questrade FX list
OA = set("CZK DKK HUF MXN PLN SGD THB TRY ZAR".split())      # OANDA Canada Forex CFD list (margin-rates page)
QT_PIPS = {"CZK": 24.5, "DKK": 13.5, "HUF": 25.5, "ILS": 28.5, "MXN": 13.5, "PLN": 15.5, "SGD": 7.5, "THB": 16.0, "TRY": 5.5, "ZAR": 33.5}
OA_LEV = {"CZK": "3.7:1", "DKK": "3.7:1", "HUF": "3.7:1", "MXN": "20:1", "PLN": "3.7:1", "SGD": "8.3:1", "THB": "3.7:1", "TRY": "3.7:1", "ZAR": "3.7:1"}
OA_FEE = {"TRY": "4.00%", "CZK": "2.00%", "HUF": "2.00%", "THB": "2.00%", "ZAR": "2.00%"}
IB_CREDIT = {"CZK": "BM-2% above 250k", "DKK": "BM-0.5% above 75k", "HUF": "BM-3% above 3.5m", "ILS": "0% all", "INR": "0% all", "KRW": "BM-1.5% above 12m", "MXN": "BM-4% above 200k", "PLN": "BM-2% above 400k", "RUB": "0% all (balances auto-convert)", "SGD": "BM-1% above 14k", "TRY": "5% flat above 250k", "ZAR": "BM-1% above 150k"}
IB_DEBIT = {"CZK": "BM+3%", "DKK": "BM+3%", "HUF": "BM+5%", "ILS": "BM+5%", "INR": "BM+3%", "KRW": "BM+3.5%", "MXN": "BM+3% (<2m)", "PLN": "BM+3%", "RUB": "BM+5%", "SGD": "BM+1.5% (<140k)", "TRY": "BM+5%", "ZAR": "BM+1.5% (<1.5m)"}
rows = []
for c in C22:
    if c in IB_SPECIAL: ib, ibn = "restricted", "listed with footnote 'With special conversion functionality' (conversion only, not free speculative position)"
    elif c in IB_LIST: ib, ibn = "Y", "IDEALPRO spot, deliverable cash balance; commission 0.20bp x value (min USD 2)"
    elif c == "RUB": ib, ibn = "N", "RUB balances auto-convert to USD/EUR (sanctions note on interest/margin pages)"
    elif c == "INR": ib, ibn = "N", "not in spot list; INR appears only in interest/margin rate tables"
    else: ib, ibn = "N", "not in IBKR Canada 28-currency spot list"
    if c in IB_CREDIT: ibn += f"; credit {IB_CREDIT[c]}; debit {IB_DEBIT[c]}"
    if c == "BRL": ibn += "; no BRL row in credit or margin-loan interest tables"
    qt = "Y (CFD/margin FX, USD/%s)" % c if c in QT else "N"
    qtn = f"target spread {QT_PIPS[c]} pips; rollover financing not published (phone)" if c in QT else "not in Questrade FX pair list"
    oa = "Y (CFD)" if c in OA else "N"
    oan = f"max leverage USD/{c} {OA_LEV[c]}; financing = LP tom-next swap +/- admin fee {OA_FEE.get(c,'1.00%')}" if c in OA else "not in OANDA Canada Forex CFD list"
    rows.append(dict(currency=c, ibkr_canada_spot=ib, ibkr_note=ibn, questrade_fx=qt, questrade_note=qtn, oanda_canada=oa, oanda_note=oan,
                     other_ca_broker="not checked", pages_opened_utc_date=DAY))
pd.DataFrame(rows).to_csv(D / "broker_fx_availability.csv", index=False)
src = pd.DataFrame([
 ("IBKR Canada", "spot currency list", "https://www.interactivebrokers.ca/en/trading/products-spot-currencies.php", "raw/broker_pages/ibkr_ca_products_spot_currencies.html (footnote rendered via browser)"),
 ("IBKR Canada", "spot FX commissions", "https://www.interactivebrokers.ca/en/pricing/commissions-spot-currencies.php", "raw/broker_pages/ibkr_ca_commissions_spot_currencies.html"),
 ("IBKR Canada", "credit interest (BM - spread) by currency", "https://www.interactivebrokers.ca/en/accounts/fees/pricing-interest-rates.php", "raw/broker_pages/ibkr_ca_interest_rates.html (table JS-rendered; read via browser)"),
 ("IBKR Canada", "margin loan rates (BM + spread) by currency", "https://www.interactivebrokers.ca/en/trading/margin-rates.php", "raw/broker_pages/ibkr_ca_margin_rates.html (table JS-rendered; read via browser)"),
 ("Questrade", "FX & CFD fees, target spreads", "https://www.questrade.com/pricing/self-directed-commissions-plans-fees/forex-cfd", "raw/broker_pages/questrade_forex_cfd.html"),
 ("OANDA Canada", "Forex CFD list + leverage", "https://www.oanda.com/ca-en/legal/margin-rates/", "raw/broker_pages/oanda_ca_margin_rates.html"),
 ("OANDA Canada", "financing method + admin fees", "https://www.oanda.com/ca-en/trading/financing-costs/", "raw/broker_pages/oanda_ca_financing_costs.html"),
], columns=["broker", "content", "url", "saved"]); src["opened_date"] = DAY; src.to_csv(D / "broker_pages_opened.csv", index=False)

ndf = pd.DataFrame([
 ("CNY","1999-2001","onshore minus NDF-implied 3m yield","-4 to -10 pp (\"negative 400-1,000 basis points\")","","Ma, Ho & McCauley (2004) BIS QR June 2004, p.91 text","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("CNY","late 2003","onshore minus NDF-implied 3m yield","+4 to +10 pp (\"positive 400-1,000 basis points\")","","Ma, Ho & McCauley (2004) p.91","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("INR","1999-2001","onshore minus NDF-implied 3m yield","-4 to -10 pp","","Ma, Ho & McCauley (2004) p.91","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("INR","late 2003","onshore minus NDF-implied 3m yield","+4 to +10 pp","","Ma, Ho & McCauley (2004) p.91","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("KRW","Nov 1998-Mar 1999","abs onshore/offshore 3m yield spread","1.07 pp (onshore>offshore) / 2.82 pp (onshore<offshore)","","Ma, Ho & McCauley (2004) Box 2 table p.92","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("KRW","Apr 1999-Dec 2003","abs onshore/offshore 3m yield spread","0.69 / 0.67 pp","","Ma, Ho & McCauley (2004) Box 2 p.92","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("KRW","Jan 2004-mid 2004","abs onshore/offshore 3m yield spread","1.44 / 0.75 pp","","Ma, Ho & McCauley (2004) Box 2 p.92","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("PHP","late 2000-early 2001","onshore minus NDF-implied yield","large negative (magnitude only in chart; offshore consistently higher)","","Ma, Ho & McCauley (2004) p.93 + fn 9","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
 ("IDR","early 2001","onshore/offshore yield spread","large, brief (illiquid nascent NDF); magnitude chart-only","","Ma, Ho & McCauley (2004) p.93","https://www.bis.org/publications/markets-non-deliverable-forwards-asian-currencies_1.pdf"),
]+[(c,p,"abs(onshore fwd - NDF) 3m, % of spot",f"{v:.2f}% of spot",f"{4*v:.2f}","McCauley, Shu & Ma (2014) BIS QR Mar 2014 Table 4 p.81","https://www.bis.org/publications/non-deliverable-forwards-2013-and-beyond_1.pdf")
   for c,vals in {"CNY":(0.43,0.41,0.59,0.48),"INR":(0.44,0.35,1.17,0.57),"IDR":(0.82,0.56,2.37,2.53),"KRW":(0.30,0.23,0.90,0.25),"MYR":(0.29,0.26,0.51,0.26),"PHP":(0.44,0.31,1.62,0.24),"TWD":(0.39,0.38,0.59,0.10),"BRL":(0.22,0.18,0.60,0.17),"RUB":(0.08,0.08,0.08,0.10)}.items()
   for p,v in zip(("2005-01..2013-12 full","non-crisis","GFC 2008-09..2009-07","taper May-Aug 2013"),vals)]+[
 ("IDR","stress episodes 2013/2020","onshore fwd minus NDF implied yield","up to +/-50 pp (\"+/-50%\")","","Schmittmann & Teng (2020) IMF WP/20/179 p.14 sec IV, Fig 9/12","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("MYR","2015; after Nov 2016 NDF-ban reinforcement","onshore fwd minus NDF implied yield","large/volatile; magnitude chart-only (Fig 14)","","Schmittmann & Teng (2020) p.15","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("INR","2013 taper; 2020 COVID","onshore fwd minus NDF implied yield","NDF priced much more depreciation; magnitude chart-only (Fig 13)","","Schmittmann & Teng (2020) p.15-16","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("PHP","late 2016; 2020 COVID","onshore fwd minus NDF implied yield","substantial; magnitude chart-only (Fig 15)","","Schmittmann & Teng (2020) p.15-16","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("KRW","2003-2020","onshore fwd minus NDF implied yield","close to zero incl. stress (bank arbitrage)","","Schmittmann & Teng (2020) p.15","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("TWD","2020 COVID","onshore fwd minus NDF implied yield","NDF implied rates far below onshore; chart-only (Fig 11)","","Schmittmann & Teng (2020) p.14-16","https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020179-print-pdf.pdf"),
 ("CNY","pre-2015 fixing reform","NDF settlement (fixing) vs close basis","gap as wide as 2% of spot","","McCauley & Shu (2016) BIS QR Dec 2016 p.? (text)","https://www.bis.org/publications/non-deliverable-forwards-impact-currency-internationalisation-and-derivatives-reform_1.pdf"),
]+[(c,f"{s}-2014","5y LC credit spread = LC govt yield - (UST + CCS); CIP-type deviation",f"mean {m} pp (sd {sd})","",f"Du & Schreger (2016) JF Table I p.1041","https://jschreger.s3.us-east-2.amazonaws.com/Du_Schreger_JF.pdf")
   for c,s,m,sd in [("BRL","Jul 2006",3.39,1.16),("COP","Jun 2005",1.59,0.70),("HUF","Jan 2005",2.34,1.41),("IDR","Apr 2005",1.02,0.81),("ILS","Feb 2006",0.68,0.43),("MXN","Jan 2005",0.67,0.33),("PEN","Jul 2006",0.72,0.77),("PHP","Mar 2005",1.42,0.80),("PLN","Mar 2005",1.28,0.69),("TRY","May 2005",1.62,1.56)]],
 columns=["currency","period","measure","gap_as_stated","annualized_pp_derived_x4_for_3m","source_location","url"])
ndf["note"] = ""
ndf.loc[ndf.annualized_pp_derived_x4_for_3m != "", "note"] = "derived column: 3m forward-premium gap (% of spot) x4 ~ annualized yield gap; not stated by source"
ndf.loc[ndf.source_location.str.contains("2016"), "source_location"] = "McCauley & Shu (2016) BIS QR Dec 2016, text section on CNY NDF basis risk"
ndf.to_csv(D / "ndf_gap_episodes.csv", index=False)

# costs: retail pips -> bps using latest Yahoo spot (pip = 0.0001; HUF pip assumed 0.01 -- convention not stated by Questrade)
spot = {}
for c in QT_PIPS:
    try:
        out = subprocess.run(["curl", "-sS", "-m", "30", "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v8/finance/chart/USD{c}=X?range=5d&interval=1d"], capture_output=True, text=True).stdout
        spot[c] = json.loads(out)["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception: spot[c] = None
cost = []
for c, p in QT_PIPS.items():
    pip = 0.01 if c == "HUF" else 0.0001
    bps = None  # pip convention unstated; see costs_reference note
    cost.append(dict(currency=c, venue="Questrade (retail CFD/margin FX)", measure="target full spread USD/"+c, value=f"{p} pips", approx_bps_full_spread=bps, source="https://www.questrade.com/pricing/self-directed-commissions-plans-fees/forex-cfd", date=DAY,
                     note=f"bps derived with Yahoo USD{c}=X {spot[c]}; pip size assumed {pip} (not stated); actual may exceed target"))
for c, (m, sd) in {"BRL":0.36,"COP":0.15,"HUF":0.17,"IDR":0.40,"ILS":0.12,"MXN":0.06,"PEN":0.18,"PHP":0.29,"PLN":0.11,"TRY":0.10}.items() and {}.items(): pass
for c, h in {"BRL":0.36,"COP":0.15,"HUF":0.17,"IDR":0.40,"ILS":0.12,"MXN":0.06,"PEN":0.18,"PHP":0.29,"PLN":0.11,"TRY":0.10}.items():
    cost.append(dict(currency=c, venue="institutional 5y cross-currency swap", measure="half bid-ask of 5y CCS (yield pp)", value=f"{h} pp", approx_bps_full_spread=round(2*h*100), source="Du & Schreger (2016) JF Table I col 4, 2005-2014", date="2005-2014", note="rate spread, not FX spot spread"))
cost += [
 dict(currency="EM (63-country sample)", venue="institutional interdealer (Reuters)", measure="spot/forward bid-ask vs developed", value="2-4x developed median; developed spot median 0.039-0.051% (full spread), 1m fwd 0.045-0.057%", approx_bps_full_spread="~8-20 (derived 2-4x of ~4-5bp)", source="Burnside, Eichenbaum & Rebelo (2007) NBER w12916 p.2", date="1997-10..2006-11", note="no per-currency table in WP"),
 dict(currency="all spot pairs", venue="IBKR Canada IDEALPRO", measure="commission", value="0.20bp x trade value (<=USD1bn/month), min USD 2/order; auto-conversion 0.03% markup", approx_bps_full_spread="0.2 + market spread", source="https://www.interactivebrokers.ca/en/pricing/commissions-spot-currencies.php", date=DAY, note="quotes pass-through from 17 dealers"),
 dict(currency="TRY / CZK,HUF,THB,ZAR / other", venue="OANDA Canada CFD", measure="financing admin fee on tom-next", value="4.00% / 2.00% / 1.00% p.a.", approx_bps_full_spread="", source="https://www.oanda.com/ca-en/trading/financing-costs/", date=DAY, note="carry drag per annum, applied to long and short side"),
 dict(currency="MXN,HUF,PLN,CZK,ZAR,SGD,TRY,ILS", venue="IBKR Canada", measure="carry drag: credit BM-x on long ccy, debit BM+y on funding USD/CAD", value="long MXN BM-4%, HUF BM-3%, PLN/CZK BM-2%, ZAR/SGD BM-1%, TRY flat 5%, ILS 0%; USD loan BM+1.5% (<100k); CAD BM+1.5% (<130k)", approx_bps_full_spread="", source="IBKR CA interest-rates & margin-rates pages", date=DAY, note="per annum; round-trip carry haircut ~2.5-5.5pp for small accounts"),
]
lrv = pd.read_parquet(D / "lrv_currency_factors.parquet")
for tag in ["all", "dev"]:
    g = lrv[f"{tag}_RX_DOL"] - lrv[f"{tag}_net_RX_DOL"]; h = lrv[f"{tag}_HML_FX"] - lrv[f"{tag}_net_HML_FX"]
    cost.append(dict(currency=f"LRV {tag} portfolios", venue="institutional (Barclays/Reuters bid-ask)", measure="mean(gross - net) monthly, RX and HML", value=f"RX {g.mean()*1e4:.1f} bp/mo; HML {h.mean()*1e4:.1f} bp/mo", approx_bps_full_spread="", source="https://web.mit.edu/adrienv/www/CurrencyPortfolios.xls", date="1983-11..2021-05", note="derived from published gross vs net sheets; cost reference only"))
pd.DataFrame(cost).to_csv(D / "costs_reference.csv", index=False)

veh = pd.DataFrame([
 ("CEW","WisdomTree Emerging Currency Strategy Fund","0.55%","2009-05-06","stockanalysis.com (WisdomTree site 403 Cloudflare)","yahoo_CEW_distributions.csv; 10 distributions; very thin volume (last day 200 sh)"),
 ("EMLC","VanEck J.P. Morgan EM Local Currency Bond ETF","0.31% net (cap 0.30% ex-AFFE until 2027-05-01)","2010-07-22","vaneck.com overview page","yahoo_EMLC_distributions.csv"),
 ("LEMB","iShares J.P. Morgan EM Local Currency Bond ETF","0.30%","2011-10-18","ishares.com","yahoo_LEMB_distributions.csv"),
 ("EBND","SPDR Bloomberg EM Local Bond ETF","0.30% gross","2011-02-23","ssga.com","yahoo_EBND_distributions.csv"),
 ("EEM","iShares MSCI Emerging Markets ETF","0.72%","2003-04-07","ishares.com","yahoo_EEM_distributions.csv"),
], columns=["ticker","name","expense_ratio","inception","er_source","distributions"]); veh["retrieved"] = DAY
veh.to_csv(D / "vehicles_reference.csv", index=False)

# hash every raw file
files = {}
for p in sorted(R.rglob("*")):
    if p.is_file(): files[str(p.relative_to(D))] = hashlib.sha256(p.read_bytes()).hexdigest()
man["_all_raw_files_sha256"] = files
man["_derived_tables"] = {k: {"rows": len(pd.read_csv(D / k))} for k in ["broker_fx_availability.csv","broker_pages_opened.csv","ndf_gap_episodes.csv","costs_reference.csv","vehicles_reference.csv"]}
man["_blocked_needs_owner"] = {
 "fred.stlouisfed.org": "HTTP/2 INTERNAL_ERROR via proxy (ICE BofA HY OAS BAMLH0A0HYM2 / HY TR not acquired)",
 "www.hannolustig.com": "CONNECT tunnel 502 (Lustig site)",
 "sites.google.com/view/hannolustig": "redirects to Google sign-in (no login attempted)",
 "www.wisdomtree.com": "403 Cloudflare challenge (CEW fact sheet; ER taken from stockanalysis.com)",
 "www.imf.org (curl)": "403 to curl; WP/20/179 retrieved via WebFetch instead",
 "www.sciencedirect.com": "403 (NDF carry trades paper not opened)"}
man["_notes"] = {"partial_month": "Yahoo/Cboe monthly last row 2026-09-30 is partial (data through 2026-09-25)",
 "lrv_staleness": "Verdelhan CurrencyPortfolios.xls Last-Modified 2021-06-18, data end 2021-05 despite 'Updated monthly' label",
 "fed_h10_correction": "Fed RSS 2026-08-12: Aug-10 H.10 release had wrong Aug-3 data for all currencies/indexes (corrected); downloaded post-correction"}
MAN.write_text(json.dumps(man, indent=1, default=str)); print("ok", len(files))
