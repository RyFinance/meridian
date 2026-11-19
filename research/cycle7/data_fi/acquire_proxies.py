"""Pre-declared traded proxies (Yahoo chart JSON, adjusted close): KR 148070.KS, IN LTGILTBEES.NS, ZA STXGOV.JO.
AU IGB.AX is read from the repo (cycle-6 bytes). Run: PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fi.acquire_proxies"""
from research.cycle7.data_fi.acquire_web import get, save

URL = "https://query2.finance.yahoo.com/v8/finance/chart/{t}?period1=0&period2=1790000000&interval=1d&events=div,split"

if __name__ == "__main__":
    log = []
    for t in ("148070.KS", "LTGILTBEES.NS", "STXGOV.JO"):
        b, c, e = get(URL.format(t=t), 60)
        save("yahoo", t, b, URL.format(t=t), c, "json", log)
        print(t, c, len(b))
