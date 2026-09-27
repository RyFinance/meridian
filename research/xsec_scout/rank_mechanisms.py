"""Ex-ante ranking of cross-sectional mechanisms for quant_v7 (Workload C, research cycle 4, 2026-09-24/25).

NO RETURN LOOKING. Inputs: literature (magnitudes flagged 'approx.' are from memory and must be verified before
any registration), the project's own already-viewed OSAP decay table (reports/edge_graveyard/predictor_decay.csv),
data-availability probes (reports/survivorship_audit/*.json) and the synthetic survivorship simulation.

Power: research.power.designs.long_short_core (quintile long-short, factor-tilt correlation model), with an extra
true-IC regime variance tau (IC_t = IC + tau * z_t) added to the spread variance. Development-gate power uses the
Amendment-1 per-candidate gate  S_hat >= 1.8 / sqrt(Y_dev):  P = Phi(S_net * sqrt(Y_dev) - 1.8)  (kappa ~ 1).

Outputs: reports/xsec_scout/mechanism_ranking.csv, mechanism_ranking.json, power_top5.csv
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/xsec_scout/rank_mechanisms.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import norm

from research.power.designs import long_short_core

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/xsec_scout"
OUT.mkdir(parents=True, exist_ok=True)

# criterion weights, in the brief's priority order
W = {"power": 0.24, "mechanism": 0.18, "pit": 0.15, "survivorship": 0.14, "indep_obs": 0.11,
     "implementation": 0.10, "independence": 0.08}

# power inputs: N (tradable names), q (periods/yr), sig (cross-sectional residual sd per period), ic (post-decay,
# gross, per period), tau (true IC regime sd), rho_resid/rho_signal (bet correlation), ac (signal autocorr per
# period -> turnover), c (one-way cost bps), borrow (bps/yr on short leg), years (free PIT history), dev share.
M = [
 dict(id="C1", name="Crypto perp funding-rate carry (Binance USD-M, incl. delisted)", N=100, q=52, sig=0.09, ic=0.02,
      tau=0.08, rho_resid=0.10, rho_signal=0.3, ac=0.85, c=8, borrow=0, years=6.6,
      mechanism="Leveraged (mostly retail) longs pay funding to shorts/basis arbitrageurs; persists because spot-short "
                "and exchange/counterparty capital are scarce and levered demand is procyclical",
      literature="He-Manela-Ross-von Wachter (2022/24) perp-spot deviations large, carry arbitrage Sharpe >1 on majors "
                 "(approx.); Schmeling-Schrimpf-Todorov (2023 BIS WP) crypto carry >10%/yr on average, predicts crashes "
                 "(approx.); cross-sectional funding-sort evidence thin/working papers",
      decay="Basis/funding compressed after 2023 (institutional basis capital, delta-neutral stablecoin products); expect >=50% decay vs 2020-21",
      data="data.binance.vision fundingRate monthly from 2020-01, 8h timestamps; klines to final settlement; 952 funding symbols archived, 385 not trading now (40%)",
      prior="never tested (only BTC/ETH TS trend, SPENT)",
      surv_note="survivor-free archive; live-only list would bias carry IN FAVOUR by ~+17 to +34%/yr (sim T2)",
      pit_traps="symbol reuse (LUNAUSDT spot = Terra 2.0 after 2022-05), BUSD/USDT duplicates, stock-token perps (AAPLUSDT...), funding interval changes 8h->4h, listing-date selection",
      impl="Binance.com not open to US persons (verify jurisdiction); taker 5bp; exchange counterparty risk; capacity fine at $100k",
      scores=dict(mechanism=4, pit=5, survivorship=5, indep_obs=4, implementation=2, independence=5)),
 dict(id="C2", name="Crypto cross-sectional 1-4 week momentum / reversal (same archive)", N=100, q=52, sig=0.09, ic=0.015,
      tau=0.10, rho_resid=0.10, rho_signal=0.3, ac=0.5, c=8, borrow=0, years=6.6,
      mechanism="Attention-driven under/over-reaction and liquidity provision among retail-dominated coins",
      literature="Liu-Tsyvinski-Wu (2022 JF): CMKT/CSIZE/CMOM, 1-4 week momentum (2014-18, CoinMarketCap); Dobrynskaya (2023) momentum then reversal (approx.)",
      decay="large-coin momentum weaker post-2020 in several replications (approx.)",
      data="same Binance archive (spot klines 2017+, perps 2020+)", prior="never tested cross-sectionally",
      surv_note="survivor-free archive; momentum/reversal loadings on dying coins large (sim SURV_ALL MOMENTUM -39%/yr)",
      pit_traps="as C1; plus author knows the 2022-25 alt-vs-BTC path (knowledge contamination)",
      impl="as C1; higher turnover", scores=dict(mechanism=3, pit=5, survivorship=5, indep_obs=4, implementation=2, independence=3)),
 dict(id="C3", name="Crypto leverage crowding: open-interest growth x funding (Binance metrics)", N=80, q=52, sig=0.09, ic=0.015,
      tau=0.10, rho_resid=0.10, rho_signal=0.3, ac=0.6, c=8, borrow=0, years=6.0,
      mechanism="Forced deleveraging: crowded levered positions are liquidated into thin books; liquidity providers are paid to absorb",
      literature="crowding/deleveraging literature (equities: Brunnermeier-Pedersen 2009 funding liquidity); crypto liquidation-cascade studies (working papers)",
      decay="unknown; mechanism tied to leverage availability",
      data="futures/um/daily/metrics (OI, long/short ratios) archived from 2020-09", prior="never tested",
      surv_note="survivor-free archive", pit_traps="5-min snapshot timestamps; metrics coverage for small perps starts later",
      impl="as C1", scores=dict(mechanism=4, pit=4, survivorship=5, indep_obs=3, implementation=2, independence=5)),
 dict(id="U1", name="US daily short-sale volume (FINRA Reg SHO), 20-day smoothed abnormal ratio, weekly holding", N=450, q=52, sig=0.031, ic=0.008,
      tau=0.04, rho_resid=0.15, rho_signal=0.2, ac=0.8, c=3, borrow=40, years=8.1,
      mechanism="Informed short sellers trade ahead of bad news; they are paid by uninformed buyers; persists because shorting is costly/risky",
      literature="Boehmer-Jones-Zhang (2008 JF): heavily vs lightly shorted -1.16%/20d (NYSE order data 2000-04); Diether-Lee-Werner (2009 RFS, 2005 Reg SHO) ~1.4%/mo gross (approx.); Engelberg-Reed-Ringgenberg (2012 JFE)",
      decay="FINRA files public since 2009; market-maker shorting (~40-50% of off-exchange volume) dilutes the signal",
      data="cdn.finra.org regsho daily: per-facility files verified from 2009-08 (FNYX); consolidated CNMS fetchable from 2018-08 (other scout); off-exchange volume only",
      prior="never tested; not an OSAP predictor",
      surv_note="bias AGAINST 'high short volume underperforms'; 2018-26 weekly: +0.8 to +2.2%/yr on the high-minus-low spread (sim T1)",
      pit_traps="file date vs publication time; FINRA symbol conventions (BRK.B); ticker changes; ETFs in files",
      impl="large caps 2-4bp; weekly turnover ~0.7/leg: costs ~ gross", scores=dict(mechanism=3, pit=4, survivorship=4, indep_obs=4, implementation=3, independence=5)),
 dict(id="U2", name="US short interest / days-to-cover changes (FINRA biweekly)", N=450, q=24, sig=0.044, ic=0.015,
      tau=0.05, rho_resid=0.15, rho_signal=0.3, ac=0.7, c=3, borrow=60, years=8.7,
      mechanism="Informed/constrained shorting (Miller 1977); crowded shorts",
      literature="Asquith-Pathak-Ritter (2005 JFE); Boehmer-Huszar-Jordan (2010); Hong et al. (2016) days-to-cover ~1.2%/mo EW (approx.)",
      decay="OSAP ShortInterest 2015+ Sharpe 0.79 EW, 0.21 ex-microcap, 0.18 VW (project table, VIEWED)",
      data="cdn.finra.org biweekly files verified 2017-12-29 onward; settlement date only (publication ~7-8 business days later)",
      prior="OSAP ShortInterest / IO_ShortInterest viewed in edge graveyard -> contaminated",
      surv_note="bias AGAINST hypothesis (toward zero)", pit_traps="publication lag, revisionFlag restatements, split flag",
      impl="short leg = hard-to-borrow names; borrow fees", scores=dict(mechanism=4, pit=3, survivorship=4, indep_obs=3, implementation=3, independence=2)),
 dict(id="U3", name="US liquidity-provision reversal (industry-residual, non-news, liquidity-shock conditioned)", N=450, q=52, sig=0.031, ic=0.02,
      tau=0.05, rho_resid=0.15, rho_signal=0.2, ac=0.0, c=3, borrow=40, years=8.1,
      mechanism="Liquidity providers are paid by demanders of immediacy; compensation rises with VIX/funding stress",
      literature="Nagel (2012 RFS); Da-Liu-Schaumburg (2014 MS); Avramov-Chordia-Goyal (2006); Khandani-Lo (2011) decline 1995-2007",
      decay="OSAP STreversal 2015+ 0.38 EW, 0.31 ex-micro, -0.11 VW (VIEWED)",
      data="repo prices (survivor) + PIT S&P mask; LSE live stocks raise PIT coverage 77%->89% (2019)",
      prior="Codex 2026-09-21 registration crashed before any stock result; OSAP monthly version viewed",
      surv_note="bias IN FAVOUR (losers leg inflated), +0.4 to +2%/yr in index views at h=1-5 (sim); needs a pre-registered haircut",
      pit_traps="earnings dates (BMO/AMC) for news filter; close vs next open", impl="high turnover; net is marginal in large caps",
      scores=dict(mechanism=4, pit=4, survivorship=2, indep_obs=4, implementation=2, independence=3)),
 dict(id="U4", name="SEC fails-to-deliver shocks", N=450, q=24, sig=0.044, ic=0.006, tau=0.04, rho_resid=0.15, rho_signal=0.2,
      ac=0.5, c=3, borrow=60, years=17,
      mechanism="Binding short-sale constraints / settlement stress -> overpricing (Miller)",
      literature="Evans-Geczy-Musto-Reed (2009 RFS); Autore-Boulton-Braga-Alves (2015) FTD stocks overvalued (approx.)",
      decay="unknown; not in OSAP", data="SEC FTD files 2004+ (complete 2008-09+); SEC returns 403 without a declared contact User-Agent (user decision)",
      prior="never tested", surv_note="bias AGAINST hypothesis", pit_traps="publication lag ~2 weeks; settlement-date convention changed (T+2 2017, T+1 2024)",
      impl="events sparse in large caps", scores=dict(mechanism=3, pit=3, survivorship=4, indep_obs=2, implementation=3, independence=5)),
 dict(id="U5", name="13F institutional breadth / ownership changes", N=450, q=4, sig=0.11, ic=0.02, tau=0.06, rho_resid=0.15,
      rho_signal=0.3, ac=0.5, c=3, borrow=40, years=12.5,
      mechanism="Institutional demand pressure; breadth as short-sale-constraint proxy (Chen-Hong-Stein 2002)",
      literature="Chen-Hong-Stein (2002 JFE); Gompers-Metrick (2001 QJE); Lewellen (2011) no institutional alpha",
      decay="OSAP DelBreadth 2015+ 0.52 (ex-micro 0.52, VW 0.29) VIEWED", data="SEC 13F structured data sets 2013-Q3+; 45-day lag",
      prior="OSAP breadth viewed", surv_note="bias AGAINST (falling-breadth losers missing)",
      pit_traps="use filing date; 13F-HR/A amendments; CUSIP->ticker mapping over time; confidential treatment",
      impl="cheap, quarterly", scores=dict(mechanism=3, pit=3, survivorship=4, indep_obs=2, implementation=4, independence=2)),
 dict(id="U6", name="Quality minus junk / distress spread", N=450, q=12, sig=0.07, ic=0.02, tau=0.08, rho_resid=0.15, rho_signal=0.5,
      ac=0.9, c=3, borrow=40, years=15,
      mechanism="Risk (junk pays) vs mispricing (distress puzzle); debated", literature="Asness-Frazzini-Pedersen (2019 RAS) QMJ; Campbell-Hilscher-Szilagyi (2008 JF)",
      decay="OSAP GP 2015+ 0.85 (VIEWED); OScore 0.94 EW / 0.23 ex-micro", data="SEC XBRL / LSE financial_reports with acceptance times, 2009+",
      prior="fundamentals family partially used; OSAP viewed", surv_note="QMJ biased AGAINST (junk leg inflated); 'buy distressed' biased IN FAVOUR",
      pit_traps="filed vs period dates, restatements, 10-K/A", impl="cheap", scores=dict(mechanism=3, pit=3, survivorship=4, indep_obs=2, implementation=4, independence=2)),
 dict(id="U7", name="Net issuance / buybacks", N=450, q=12, sig=0.07, ic=0.02, tau=0.08, rho_resid=0.15, rho_signal=0.4, ac=0.95, c=3,
      borrow=40, years=15, mechanism="Managers time equity issuance against mispricing", literature="Pontiff-Woodgate (2008 JF); Daniel-Titman (2006 JF)",
      decay="OSAP ShareIss1Y/5Y 2015+ 0.82/0.88 (VIEWED)", data="SEC XBRL share counts", prior="F1 dev FAIL; 2015+ validation LOCKED for delisted-inclusive data",
      surv_note="bias AGAINST (failed issuers missing)", pit_traps="basic vs diluted, split guards, filed dates", impl="cheap",
      scores=dict(mechanism=4, pit=4, survivorship=4, indep_obs=2, implementation=4, independence=1)),
 dict(id="U8", spent=True, name="Insider buying/selling (Form 4)", N=450, q=12, sig=0.07, ic=0.015, tau=0.08, rho_resid=0.15, rho_signal=0.3, ac=0.6,
      c=3, borrow=40, years=20, mechanism="Insiders' private information", literature="Cohen-Malloy-Pomorski (2012 JF) opportunistic trades",
      decay="-", data="SEC Form 4 on disk", prior="SPENT: N3/N4 dev pass, validation FAIL", surv_note="mixed", pit_traps="filing lag 2 days", impl="cheap",
      scores=dict(mechanism=4, pit=4, survivorship=3, indep_obs=2, implementation=4, independence=1)),
 dict(id="U9", name="Dividend initiations / omissions", N=12, q=12, sig=0.07, ic=0.03, tau=0.10, rho_resid=0.15, rho_signal=0.3, ac=0.9, c=3,
      borrow=40, years=20, mechanism="Signalling + slow reaction", literature="Michaely-Thaler-Womack (1995 JF)",
      decay="OSAP DivOmit 0.82 EW / 0.36 ex-micro; DivInit 0.34 / -0.03 (VIEWED)", data="LSE dividends incl. delisted payers (prices missing)",
      prior="unused as signal; OSAP viewed", surv_note="omission leg biased AGAINST", pit_traps="declaration vs ex-date; special dividends",
      impl="too few large-cap events", scores=dict(mechanism=3, pit=4, survivorship=3, indep_obs=1, implementation=4, independence=3)),
 dict(id="U10", spent=True, name="Earnings-information diffusion (peer spillover, not PEAD)", N=450, q=52, sig=0.031, ic=0.005, tau=0.04, rho_resid=0.2,
      rho_signal=0.5, ac=0.5, c=3, borrow=40, years=11, mechanism="Slow diffusion of peer news (economic links)",
      literature="Thomas-Zhang (2008); Cohen-Frazzini (2008) customer momentum", decay="OSAP M5 links 2015+ -0.04 (dead); CustomerMomentum 0.21 (VIEWED)",
      data="earnings dates on disk (heavily mined)", prior="PEAD family SPENT", surv_note="mixed", pit_traps="BMO/AMC timing",
      impl="moderate", scores=dict(mechanism=2, pit=3, survivorship=3, indep_obs=3, implementation=3, independence=1)),
 dict(id="U11", spent=True, name="Options demand across stocks", N=100, q=52, sig=0.031, ic=0.01, tau=0.05, rho_resid=0.15, rho_signal=0.3, ac=0.5, c=3,
      borrow=40, years=12, mechanism="Informed option demand / hedging pressure", literature="Xing-Zhang-Zhao (2010) SmileSlope; Cremers-Weinbaum (2010)",
      decay="SmileSlope 2015+ 1.47 (VIEWED)", data="no free OI or bid/ask", prior="SPENT (H1-H4, V1-V3)", surv_note="-", pit_traps="prints not quotes",
      impl="-", scores=dict(mechanism=4, pit=2, survivorship=3, indep_obs=3, implementation=2, independence=1)),
 dict(id="U12", name="Forced index / ETF flows (S&P changes, Russell, ETF creations)", N=20, q=12, sig=0.07, ic=0.05, tau=0.10, rho_resid=0.1,
      rho_signal=0.3, ac=0.0, c=5, borrow=40, years=15, mechanism="Price pressure from index-tracking demand", literature="Harris-Gurel (1986); Chen-Noronha-Singal (2004); Brown-Davies-Ringgenberg (2021 RoF)",
      decay="S&P inclusion pop dead; Russell marginal (graveyard catalogue)", data="Wikipedia add/remove ledger (announcement vs effective ambiguity); deleted names lack prices",
      prior="stock level untested", surv_note="deletion leg = missing names", pit_traps="announcement vs effective date", impl="event-driven",
      scores=dict(mechanism=4, pit=3, survivorship=2, indep_obs=2, implementation=3, independence=4)),
 dict(id="U13", name="Attention (Wikipedia pageviews)", N=450, q=52, sig=0.031, ic=0.005, tau=0.04, rho_resid=0.15, rho_signal=0.3, ac=0.6, c=3,
      borrow=40, years=11, mechanism="Retail attention price pressure then reversal (Barber-Odean 2008)", literature="Da-Engelberg-Gao (2011 JF) Google SVI",
      decay="Twitter/Google-Trends signals dead (graveyard catalogue)", data="Wikimedia REST pageviews 2015-07+", prior="never tested",
      surv_note="ambiguous", pit_traps="article renames/redirects mapped with today's names; bot-agent reclassification; UTC days",
      impl="cheap", scores=dict(mechanism=2, pit=2, survivorship=3, indep_obs=3, implementation=3, independence=5)),
 dict(id="U14", name="Low risk / betting against beta", N=450, q=12, sig=0.07, ic=0.015, tau=0.08, rho_resid=0.15, rho_signal=0.6, ac=0.95, c=3,
      borrow=40, years=20, mechanism="Leverage-constrained investors overpay for beta", literature="Frazzini-Pedersen (2014 JFE)",
      decay="OSAP Beta 2015+ 0.20, IdioVol3F 0.15 (VIEWED)", data="prices", prior="price data mined", surv_note="BAB biased AGAINST (high-beta failures missing)",
      pit_traps="-", impl="leverage on low-beta leg", scores=dict(mechanism=3, pit=4, survivorship=4, indep_obs=2, implementation=3, independence=2)),
 dict(id="G1", spent=True, name="Country equity indices: value / momentum / carry (30+ markets)", N=30, q=12, sig=0.04, ic=0.05, tau=0.10, rho_resid=0.3,
      rho_signal=0.5, ac=0.9, c=5, borrow=0, years=25, mechanism="Risk premia + slow macro diffusion", literature="Asness-Moskowitz-Pedersen (2013 JF); Koijen et al. (2018 JFE)",
      decay="value/momentum everywhere roughly halved post-publication (approx.)", data="index/ETF prices free; survivor-free",
      prior="SPENT (etf_hybrids E1/E2 validation FAIL; multiasset XS momentum; policy_trend)", surv_note="survivor-free by universe",
      pit_traps="ETF inception dates; dividend treatment", impl="cheap", scores=dict(mechanism=4, pit=5, survivorship=5, indep_obs=1, implementation=4, independence=1)),
 dict(id="G2", spent=True, name="Currencies: carry / momentum / value (20-40)", N=25, q=12, sig=0.02, ic=0.05, tau=0.10, rho_resid=0.3, rho_signal=0.5,
      ac=0.9, c=3, borrow=0, years=25, mechanism="Crash-risk compensation", literature="Lustig-Roussanov-Verdelhan (2011 RFS); Menkhoff et al. (2012 JFE)",
      decay="G10 carry weak since 2008", data="spot free; EM forwards not free", prior="SPENT (fx_carry_vol, multiasset carry)", surv_note="survivor-free",
      pit_traps="pegs, euro entry", impl="cheap", scores=dict(mechanism=4, pit=4, survivorship=5, indep_obs=1, implementation=4, independence=1)),
 dict(id="G3", spent=True, name="Commodity futures: basis / momentum (~25)", N=25, q=12, sig=0.06, ic=0.05, tau=0.10, rho_resid=0.2, rho_signal=0.5,
      ac=0.9, c=5, borrow=0, years=25, mechanism="Hedging pressure / inventories", literature="Gorton-Hayashi-Rouwenhorst (2013); Bakshi-Gao-Rossi (2019)",
      decay="moderate", data="no free contract curves (EIA energy only)", prior="commodity_roll SPENT", surv_note="survivor-free",
      pit_traps="roll dates, continuous-contract splicing", impl="futures access", scores=dict(mechanism=4, pit=2, survivorship=5, indep_obs=1, implementation=3, independence=1)),
]


def power_row(m: dict) -> dict:
    core = long_short_core(m["N"], m["ic"], m["sig"], 0.2, m["rho_resid"], m["rho_signal"], m["ac"], m["c"], m["q"],
                           m["borrow"], "factor_tilt")
    sd = math.sqrt(core["spread_sd"] ** 2 + (m["sig"] * core["E_signal_spread"] * m["tau"]) ** 2)
    sr_g = core["spread_mean_gross"] / sd * math.sqrt(m["q"])
    sr_n = core["spread_mean_net"] / sd * math.sqrt(m["q"])
    ydev = 0.6 * m["years"]
    rb = m["rho_resid"] * m["rho_signal"]
    n_eff = m["N"] / (1 + (m["N"] - 1) * rb)
    return {"n_eff_linear": round(n_eff, 1), "periods_total": round(m["q"] * m["years"]),
            "turnover_leg": round(core["turnover_one_way_per_leg"], 2),
            "gross_spread_ann": round(core["spread_mean_gross"] * m["q"], 4),
            "cost_ann": round(core["cost_per_period"] * m["q"], 4),
            "sharpe_gross": round(sr_g, 2), "sharpe_net": round(sr_n, 2),
            "fund_law_sharpe_no_tau": round(m["ic"] * math.sqrt(n_eff * m["q"]), 2),
            "t_net_full_history": round(sr_n * math.sqrt(m["years"]), 2),
            "dev_years": round(ydev, 1),
            "power_dev_gate_1.8": round(float(norm.cdf(sr_n * math.sqrt(ydev) - 1.8)), 3),
            "power_dev_gate_2.4": round(float(norm.cdf(sr_n * math.sqrt(ydev) - 2.4)), 3),
            "power_gross_ic_test_t1.8": round(float(norm.cdf(sr_g * math.sqrt(ydev) - 1.8)), 3)}


def main() -> None:
    rows = []
    for m in M:
        pr = power_row(m)
        # power score from the net t over the full free history (1 = <0.5, 5 = >=3)
        t = pr["t_net_full_history"]
        pscore = 1 if t < 0.5 else 2 if t < 1.2 else 3 if t < 2.0 else 4 if t < 3.0 else 5
        if m.get("spent"):
            pscore = 1   # SPENT family: its history is viewed, so clean evidence is forward-only
        sc = dict(m["scores"], power=pscore)
        total = sum(W[k] * sc[k] for k in W)
        rows.append({"id": m["id"], "name": m["name"], "spent": bool(m.get("spent", False)), "score": round(total, 2), **{f"s_{k}": sc[k] for k in W},
                     **pr, "N": m["N"], "periods_per_year": m["q"], "ic_assumed": m["ic"], "tau": m["tau"],
                     "cost_bps": m["c"], "free_years": m["years"],
                     **{k: m[k] for k in ("mechanism", "literature", "decay", "data", "prior", "surv_note", "pit_traps", "impl")}})
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    df.index += 1
    df.to_csv(OUT / "mechanism_ranking.csv", index_label="rank")
    (OUT / "mechanism_ranking.json").write_text(json.dumps({"weights": W, "rows": df.to_dict("records")}, indent=1))
    cols = ["id", "score", "s_power", "s_mechanism", "s_pit", "s_survivorship", "s_indep_obs", "s_implementation",
            "s_independence", "n_eff_linear", "sharpe_gross", "sharpe_net", "t_net_full_history", "power_dev_gate_1.8",
            "power_gross_ic_test_t1.8"]
    pd.set_option("display.width", 250)
    print(df[cols].to_string())


if __name__ == "__main__":
    main()
