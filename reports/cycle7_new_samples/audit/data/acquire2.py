"""Part 2: MSCI EM index levels (free MSCI end-of-month endpoint) + vehicle fact pages."""
import json, pandas as pd, sys
sys.argv=[""]; exec(open("acquire.py").read().split("# 1 LRV")[0])  # reuse get/note/man
for var, tag in [("GRTR", "gross"), ("NETR", "net"), ("STRD", "price")]:
    url = f"https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph?currency_symbol=USD&index_variant={var}&start_date=19970101&end_date=20260926&data_frequency=END_OF_MONTH&index_codes=891800"
    p, rec = get(url, f"msci_em_891800_{var}_usd_monthly.json")
    try:
        L = json.loads(p.read_bytes())["indexes"]["INDEX_LEVELS"]
        d = pd.DataFrame(L); d["date"] = pd.to_datetime(d.calc_date.astype(str)) + pd.offsets.MonthEnd(0); d = d.set_index("date")[["level_eod"]]
        note(f"msci_em_{tag}", rec, d, out=f"msci_em_{tag}_usd_monthly", notes=f"MSCI Emerging Markets (code 891800) {var} USD end-of-month levels from MSCI public graph endpoint")
    except Exception as e:
        note(f"msci_em_{tag}", rec, None, status="FAILED", error=str(e)[:200])
pages = {"ishares_EEM": "https://www.ishares.com/us/products/239637/ishares-msci-emerging-markets-etf",
         "ishares_LEMB": "https://www.ishares.com/us/products/239528/ishares-emerging-markets-local-currency-bond-etf",
         "ssga_EBND": "https://www.ssga.com/us/en/intermediary/etfs/spdr-bloomberg-emerging-markets-local-bond-etf-ebnd",
         
         "stockanalysis_CEW": "https://stockanalysis.com/etf/cew/", "stockanalysis_EMLC": "https://stockanalysis.com/etf/emlc/",
         "stockanalysis_HYG": "https://stockanalysis.com/etf/hyg/",
         "wisdomtree_CEW": "https://www.wisdomtree.com/investments/etfs/currency/cew"}
for k, u in pages.items():
    p, rec = get(u, f"page_{k}.html"); note(f"page_{k}", rec)
MAN.write_text(json.dumps(man, indent=1, default=str))
