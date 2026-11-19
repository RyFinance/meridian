# Frozen candidates for the sealed holdout (2026-08-11..2026-10-16)

Each entry is written before any holdout number for it is computed.

## F0: CME-break hour (frozen earlier, registered as btc_cme_break_v1)
Long BTC 17:00→18:00 ET on NYSE weekdays.
Holdout result (computed 2026-10-17): n 48, −1.0 bp gross, t −0.2. Too few trades to judge; the forward test continues.

## F1: Boyaa (0434.HK) BTC-residual dip buy, long-only (frozen 2026-10-17)
- m = BTC log move from the HK close (08:00 UTC, previous session) to 01:29 UTC.
- g = ln(open / previous close).
- beta = rolling 120-session OLS of g on m, past-only.
- res = g − beta·m; z = (res − rolling mean) / rolling std, 120 sessions, past-only.
- If z ≤ −1.0: buy at the HK open, sell at the HK close. Cost: 60 bp round trip (stamp duty 0.1% each side, spread, commission).
- Evidence: dev ≤ 2022 is not meaningful (beta ≈ 0 before Boyaa held BTC). 2023..2026-08-10: n 101, +99 bp, t 3.1, win 61%.
- Caveats:
  - The long-only side and the z ≥ 1.0 threshold were chosen after seeing 2023+ results, so this is selection-biased.
  - 2024 was −204 bp.
  - The stock trades around HK$2.7; one tick is about 0.37%.
- Code: research/btc_ah/lead_verify/boyaa_resid.py
- **Tradability check (2026-10-17, before the holdout):** the 09:30 open both defines the signal and is the fill, so entering after the open is the honest test. 2023-10..2026-08 (n 72): at the open print +65 bp; at the 10:30 HKT bar open −25 bp (t −0.7); 10:30 + 1 tick −80 bp (t −2.3). The whole edge sits in the opening print and the first hour. It is only reachable with a pre-open auction order (HK pre-opening session 09:00–09:20) using the indicative price, and that is untested because there is no pre-open data. **Status: not tradable as tested. Holdout not run.** (`lead_verify/boyaa_late_entry.py`)

## F2: SPY gap-down 1.0–1.5% (index_gaps agent): buy at the open, exit at the prior close or the day's close
Weak (check +34 bp, n 42, t 2.8, from a search of 288 variants). Not BTC-linked, and it has the same open-print fill problem. The holdout will hold 0–2 events. Not run.

## F3: ZB overnight → homebuilders, first hour (frozen 2026-10-17, before any holdout number)
- m = ln(ZB=F 60m close of the bar ending 09:00 ET / ZB=F 60m close of the bar ending 16:00 ET on the previous session).
- If m > 0: buy ITB at the 09:30 open and sell at 10:30 (close of the first 60m bar). If m < 0: short ITB over the same window. Cost: 2 bp per side.
- Evidence (yfinance 60m, 2024-08..2026-08-10): dev (to 2025-06) +15.7 bp, t 2.8; check (2025-07..08-10) +27.4 bp, t 3.9, n 267, win 58%.
  - It replicates in XHB, LEN, DHI, PHM, TOL, KBH and NVR (check t 2.1–3.1).
  - Placebos XLU, KRE and SPY are about 0.
  - Found by the fx_rates agent (288 variants); verified independently in `lead_verify/zb_itb.py`.
- Holdout plan: the same code on 2026-08-11..2026-10-16. Pass = mean > 0 and t > 1.65 (one-sided 5%). Run once.
