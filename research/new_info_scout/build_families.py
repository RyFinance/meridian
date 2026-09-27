"""Assemble reports/new_info_scout/families.{csv,json} from the family descriptions below and the plan_check
outputs in reports/new_info_scout/power/. No returns are read anywhere.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.new_info_scout.build_families
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PW = ROOT / "reports" / "new_info_scout" / "power"
OUT = ROOT / "reports" / "new_info_scout"

# fmt: off
FAMILIES = [
 dict(id="F1", spec="nis_f1_pd_treasury_inventory", family="Primary-dealer Treasury inventory (dealer positioning)",
      information="NY Fed FR 2004 weekly net outright positions of primary dealers in Treasury coupons by maturity bucket (>5y 1998-2001; 6-11y,>11y 2001-13; 6-7,7-11,>11 / 11-21,>21 2013+)",
      source="markets.newyorkfed.org/api/pd/get/all/timeseries.csv (keyless; 26.8 MB, 2,290 series, 1998-01-28..2026-09-16)",
      mechanism="Dealers are the marginal, balance-sheet-constrained holders of duration. When their inventory is abnormally high they need a price concession to carry it; the concession is earned back as inventory is distributed. End investors who push inventory onto dealers pay.",
      pit="As-of Wednesday, released following Thursday ~16:15 ET (8-day lag). API serves latest values only (no vintages); revisions unauditable but rare. Series breaks 2001-07, 2013-04, 2015-01, 2022-01, 2024-07 change bucket definitions.",
      survivorship="None: an aggregate across whichever dealers were primary dealers that week (panel composition shifts, e.g. 2008 exits, are part of the signal).",
      raw_n="~1,495 weekly signals; ~7,100 daily P&L days (28.1y)", eff_n="D=1.0-1.1 on daily P&L -> 6,400-7,100 effective days; one asset, no cross-sectional rho",
      lit="Fleming & Rosenberg (2008, NY Fed SR 299): dealers earn inventory compensation around auctions (approx., verify); intermediary asset pricing (He-Kelly-Manela 2017; Adrian-Etula-Muir 2014). No published weekly timing Sharpe; implied net Sharpe after decay 0.2-0.45 (ASSUMPTION).",
      independence="New information (never downloaded by the project). SAME mechanism as the registered tsy_auction_demand (dealer absorption) and spent auction_cycle: partial overlap, must be checked on signals before dev (see design).",
      contamination="Director has seen tsy_auction_demand dev results (same mechanism) and auction_cycle FAIL; knows 2020-03 dealer balance-sheet episode and the 2022 bond crash. No dealer-position value or relation has been viewed by anyone in the project; this scout computed coverage only.",
      assemblable=True, decision="RECOMMEND #1"),
 dict(id="F2", spec="nis_f2_fed_custody_official_flows", family="Foreign official Treasury custody flows",
      information="H.4.1 marketable Treasuries held in custody at the NY Fed for foreign official and international accounts (FRED WMTSECL1, weekly Wed level, 2002-12-18..2026-09-23)",
      source="fred.stlouisfed.org/graph/fredgraph.csv?id=WMTSECL1 (keyless)",
      mechanism="Reserve managers are price-inelastic; large official sales (FX defence) or purchases move term premia; slow-moving flows may continue or reverse. Who pays is ambiguous.",
      pit="Released Thursday 16:30 ET for Wednesday (1-day lag); face-value holdings, not revalued; FRED holds latest values (small revisions possible).",
      survivorship="None (aggregate).", raw_n="~1,235 weeks; ~5,850 daily P&L days (23.2y)", eff_n="D~1.1 -> ~5,300",
      lit="Warnock & Warnock (2009), Beltran et al. (2013): foreign official flows lower yields mostly contemporaneously; no clean predictive evidence. Implied 0.1-0.3.",
      independence="New info, but adjacent to the spent japan_us_flow (cross-border official/MOF flows) and FX-intervention narratives.",
      contamination="Director knows the 2014-16 China reserve drawdown and 2022 Japan intervention episodes.",
      assemblable=True, decision="REJECT (direction not identified a priori; MARGINAL 0.39 at k=2)"),
 dict(id="F3", spec="nis_f3_margin_debt_deleveraging", family="Retail leverage / margin debt",
      information="FINRA monthly debit balances in customers' securities margin accounts, 1997-01..2026-08 (356 months)",
      source="finra.org/sites/default/files/2021-03/margin-statistics.xlsx (keyless; urllib gets a bot page, curl works)",
      mechanism="Margin calls force leveraged investors to sell into declines (mechanical deleveraging); high leverage -> fragile, negatively skewed forward returns.",
      pit="Published ~3rd week of the following month; definitional change when FINRA replaced NYSE data (2010); no vintages.",
      survivorship="None (aggregate).", raw_n="~353 months (29.4y)", eff_n="D~1.2 -> ~294 effective months",
      lit="Mostly contemporaneous co-movement; weak predictive evidence; outcome dominated by 3 episodes (2000, 2008, 2022).",
      independence="New info; near the spent credit-timing / macro families in spirit (market-level risk timing).",
      contamination="High: the 'margin debt peaks precede crashes' folklore is known, and the whole result hinges on 3 known episodes.",
      assemblable=True, decision="REJECT (strongly MARGINAL 0.46 on years, but ~3 effective regimes and known-episode contamination)"),
 dict(id="F4", spec="nis_f4_treasury_supply_maturity", family="Treasury duration supply (Greenwood-Vayanos)",
      information="Monthly Statement of the Public Debt, marketable debt by maturity (fiscaldata MSPD 2001-01..2026-08)",
      source="api.fiscaldata.treasury.gov mspd_table_1 (keyless)",
      mechanism="Preferred-habitat arbitrageurs demand a higher term premium when duration supply is high (Vayanos-Vila).",
      pit="Monthly, published ~4th business day; final.", survivorship="None.",
      raw_n="~306 months (25.5y)", eff_n="signal AR~0.99: 2-3 independent regimes; D>=1.5",
      lit="Greenwood & Vayanos (2014 RFS) 1952-2008 in-sample; decays; implied 0.2-0.4.",
      independence="Rates/duration information family is EXHAUSTED; supply is new info but same asset.",
      contamination="Director knows the 2022 supply surge + bond crash (hindsight-favourable).", assemblable=True,
      decision="REJECT (MARGINAL 0.28; slow signal = few regimes; contamination)"),
 dict(id="F5", spec="nis_f5_crypto_dated_basis_term", family="Crypto dated-futures basis term structure",
      information="Quarterly/dated futures per contract: BitMEX XBT 2014-11+, Deribit 2016-12+, Binance COIN-M 2020-09+/USD-M 2021-01+ (USD-M delivery folders: BTC/ETH only, 50 contracts)",
      source="data.binance.vision, Deribit JSON-RPC, BitMEX REST + S3 (keyless; confirmed by futures_archive_scout)",
      mechanism="Basis = price of leverage; high basis = crowded long leverage demand paid by leveraged longs to basis arbitrageurs.",
      pit="Exchange prints, final; contract-level, survivor-free.", survivorship="Clean (expired contracts retained).",
      raw_n="~4,230 days (11.6y, BTC only)", eff_n="D~1.1; no cross-section (2 coins)",
      lit="Crypto carry literature (Schmeling-Schrimpf-Todorov 2023: futures basis/carry predicts crash risk). Implied 0.3-0.8.",
      independence="Basis is the dated-contract twin of perp funding (same leverage-price information). Treated as a funding sibling -> forbidden in spirit.",
      contamination="Frozen Binance funding claim; director knows 2021 basis >40% and 2022 collapse.", assemblable=True,
      decision="REJECT (INCAPABLE 0.13: 11.6y max; funding sibling)"),
 dict(id="F6", spec="nis_f6_cross_venue_basis_dispersion", family="Cross-exchange basis dispersion",
      information="Same-coin spot vs perp vs dated prices across Binance/Bybit/BitMEX/Deribit/OKX",
      source="venue archives (keyless; OKX/Kraken history not confirmed survivor-free)",
      mechanism="Segmented venues with capital/withdrawal frictions; dispersion converges as arbitrage capital arrives.",
      pit="Prints final; timestamps must be aligned across venues (UTC).", survivorship="Venue-level (FTX gone; Bybit/BitMEX ok).",
      raw_n="~2,400 days (6.6y)", eff_n="D~1.3", lit="Makarov & Schoar (2020): large cross-exchange arbitrage deviations, mostly pre-2019 and capital-controlled pairs.",
      independence="Largely price-derived (price differences); partial funding overlap via perps.",
      contamination="Kimchi-premium era known.", assemblable=False, decision="REJECT (INCAPABLE 0.04; price transformation)"),
 dict(id="F7", spec="nis_f7_binance_oi_positioning_xs", family="Open-interest / long-short positioning (crypto)",
      information="Binance USD-M 'metrics' (5-min OI, top-trader account/position long-short ratios, taker buy/sell), 2020-09-01+",
      source="data.binance.vision/data/futures/um/daily/metrics (keyless)",
      mechanism="Crowded leveraged positioning unwinds; taker imbalance = liquidity demand paid to makers.",
      pit="Snapshots final; ratios are Binance-defined and may change definition.", survivorship="Delisted symbols retained (40% of archive not trading).",
      raw_n="100 perps x 2,190 days (6.0y)", eff_n="factor-tilt N_eff 9-17 (rho_resid 0.2-0.4 x rho_signal 0.25); literal rho 0.3 -> 3.3",
      lit="xsec_scout C3 IC ~0.015 -> net Sharpe 0.28. IC 0.03 needed for power.",
      independence="New info but OI x funding crowding sibling; same universe/window as frozen funding claim.",
      contamination="Same Binance window as the frozen funding claim.", assemblable=True, decision="REJECT (INCAPABLE 0.05)"),
 dict(id="F8", spec="nis_f8_liquidation_cascades", family="Forced liquidations / cascade after-effects",
      information="Binance COIN-M liquidationSnapshot (BTCUSD_PERP 2023-06-25..2024-10-14 only; none for USD-M); OI-drop proxy from metrics 2020-09+",
      source="data.binance.vision cm liquidationSnapshot (keyless)",
      mechanism="Forced sellers pay immediacy; post-cascade reversal compensates liquidity providers.",
      pit="Snapshot archive discontinued; proxy is derived.", survivorship="n/a", raw_n="~40 cascade days/yr",
      eff_n="clusters of 3 coins, icc 0.5 -> deff 2.4; 101 effective events in 6y", lit="Reversal after liquidation cascades documented informally; no clean academic magnitude.",
      independence="New info.", contamination="Director knows 2021-05, 2022-06, 2022-11 cascades.", assemblable=False,
      decision="REJECT (INCAPABLE 0.05; archive covers 1.3y)"),
 dict(id="F9", spec="nis_f9_stablecoin_supply", family="Stablecoin supply / flows",
      information="DefiLlama aggregate stablecoin circulating supply (USDT from 2017-11-29; 3,223 daily points)",
      source="stablecoins.llama.fi (keyless)", mechanism="Net issuance = fiat inflow to crypto; minting precedes buying.",
      pit="NOT point-in-time: history is re-derived by the aggregator; chain-level mint timestamps would be needed.",
      survivorship="Dead stablecoins (UST) included by DefiLlama but history re-derived.", raw_n="~2,770 days (7.6y usable)",
      eff_n="D~1.1", lit="Griffin & Shams (2020) Tether issuance and 2017 prices; later evidence weak.",
      independence="New info.", contamination="UST collapse and Tether narrative known.", assemblable=False,
      decision="REJECT (INCAPABLE 0.07; not PIT)"),
 dict(id="F10", spec="nis_f10_index_inclusion_flows", family="Index inclusion / deletion flows",
      information="S&P 500 change announcements and effective dates (Wikipedia ledger; S&P press releases)",
      source="Wikipedia (keyless) for the ledger; prices: none free for removed/acquired names",
      mechanism="Index funds must buy at the effective close; pre-positioned arbitrageurs are paid by indexers.",
      pit="Wikipedia effective dates reliable, announcement dates incomplete pre-2000.",
      survivorship="SEVERE on the price side: added names later acquired/removed have no free prices (repo PIT S&P coverage 50% in 2008).",
      raw_n="~1,400 events (31y)", eff_n="deff 1.08 -> ~1,300", lit="Announcement->effective 3-7% (1990s) -> <1% (2010s) (Greenwood & Sammon 2025).",
      independence="New as a trial; graveyard lists it 'dead'.", contamination="Decay path known (graveyard).", assemblable=False,
      decision="REJECT (DECISIVE 0.62 on years but data not assemblable; known decay makes dev-pass/val-fail the expected path)"),
 dict(id="F11", spec="nis_f11_cftc_tff_dealer", family="Dealer positioning in futures (CFTC TFF)",
      information="CFTC Traders in Financial Futures: dealer/intermediary net positions, Treasury and equity-index futures, weekly 2006-06+",
      source="cftc.gov historical compressed files (keyless; probe of one legacy filename 404'd, annual files known to work per public_scout)",
      mechanism="Dealers warehouse hedging demand of asset managers; balance-sheet cost of the inventory.",
      pit="Tuesday positions, Friday release; revisions rare.", survivorship="None.", raw_n="~1,050 weeks (20.1y)", eff_n="D~1.1",
      lit="COT hedging-pressure literature; TFF dealer-specific evidence thin. Implied 0.2-0.3.",
      independence="Positioning family EXHAUSTED (research/cot, crowding_unwind).", contamination="COT results viewed.", assemblable=True,
      decision="REJECT (MARGINAL 0.32; exhausted family)"),
 dict(id="F12", spec="nis_f12_repo_quarter_end_gsib", family="Collateral / regulatory-capital window dressing (repo, SOFR, G-SIB quarter-ends)",
      information="SOFR/TGCR (NY Fed, 2018-04+), ON RRP operations (FRED RRPONTSYD 2003-02+), GCF repo (DTCC, 2005+)",
      source="markets.newyorkfed.org, FRED (keyless); FX swap basis: no free source",
      mechanism="Foreign G-SIBs shrink balance sheets at quarter-ends (snapshot-based leverage ratio); repo spikes and basis widening paid by those who need quarter-end funding.",
      pit="Rates final.", survivorship="None.", raw_n="4 events/yr (34 in 8.4y)", eff_n="34", lit="Correa-Du-Liao (2020), Du-Tepper-Verdelhan (2018): quarter-end CIP deviations large but not tradable at retail.",
      independence="Calendar/flow family; sibling of forbidden Treasury/sector month-end.", contamination="Month-end family results known.",
      assemblable=False, decision="REJECT (INCAPABLE 0.09; calendar sibling; tradable instrument not free)"),
 dict(id="F13", spec="nis_f13_13f_holdings_changes", family="Institutional holdings changes (13F)",
      information="SEC 13F structured data sets 2013q2+ (raw text 1999+)",
      source="sec.gov/files (keyless but intermittently 403 without email)", mechanism="Institutional demand shocks / herding; breadth changes proxy short-sale constraint.",
      pit="Filing date up to 45 days after quarter end; amendments.", survivorship="Filer side clean; price side survivor-only.",
      raw_n="~1,000 stocks x 52 quarters (13y)", eff_n="deff_cross 76 -> ~685", lit="Chen-Hong-Stein breadth (2002); decayed.",
      independence="New dataset for the project.", contamination="OSAP DelBreadth / IO predictors viewed 2015-2024.",
      assemblable=False, decision="REJECT (INCAPABLE 0.19; OSAP contamination; survivor prices)"),
 dict(id="F14", spec="nis_f14_borrow_constraint_proxy", family="Borrow constraints / securities lending",
      information="No free lending-fee/utilisation history exists (Markit/S3/EquiLend are paid). Proxy: FINRA bi-monthly short interest (bulk 2018-01+)",
      source="cdn.finra.org (keyless)", mechanism="Short-sale constraints keep overpriced stocks overpriced; lenders are paid.",
      pit="Settlement date + ~8 business days.", survivorship="Price side survivor-only; bias against the hypothesis.",
      raw_n="500 x 204 periods (8.5y)", eff_n="deff_cross 38 -> ~2,650", lit="Short interest/lending-fee anomalies (Drechsler-Drechsler 2014) large on fees, small on SI after decay.",
      independence="SI covered by public/xsec scouts.", contamination="OSAP ShortInterest viewed.", assemblable=False,
      decision="REJECT (no free lending data; proxy INCAPABLE 0.09)"),
 dict(id="F15", spec="nis_f15_tga_reserves_liquidity", family="Reserve / TGA liquidity plumbing",
      information="H.4.1 Treasury General Account (WTREGEN), reserves, ON RRP (RRPONTSYD); weekly 2002-12+",
      source="FRED (keyless)", mechanism="TGA/RRP swings drain or add bank reserves; balance-sheet capacity of intermediaries.",
      pit="Weekly, 1-day lag; final.", survivorship="None.", raw_n="~5,850 days (23.2y)", eff_n="D~1.1",
      lit="Mostly 2021-23 practitioner narrative; no pre-2020 academic predictive evidence.",
      independence="Close to forbidden policy-trend / macro families.", contamination="2022-23 'liquidity' narrative widely known.",
      assemblable=True, decision="REJECT (MARGINAL 0.39; regime contamination)"),
 dict(id="F16", spec="nis_f16_buyback_issuance_events", family="Issuance / buybacks (discrete announcements)",
      information="8-K text for buyback authorisations; 424B follow-on pricings (EDGAR 2004-08+)",
      source="EDGAR efts / data.sec.gov (keyless, bulk access throttled)", mechanism="Managers time the market; follow-on discount pays liquidity providers.",
      pit="Acceptance timestamps to the second.", survivorship="Price side survivor-only (no free delisted prices).",
      raw_n="~22,000 events (22y)", eff_n="deff 3.9 -> ~5,600", lit="Ikenberry-Lakonishok-Vermaelen (1995) drift; Corwin (2003) offer discount 2-3% (mostly at pricing).",
      independence="fundamentals F1 (issuance) FAILED dev; validation locked pending delisted prices.", contamination="OSAP ShareIss/Repurchase viewed.",
      assemblable=False, decision="REJECT (MARGINAL 0.41 on years; data not assemblable; contaminated)"),
 dict(id="F17", spec=None, family="ETF creation / redemption",
      information="Daily ETF shares outstanding / primary-market flows", source="No free historical source (issuer sites current only; N-PORT 2019-09+ quarterly-public, 60-day lag)",
      mechanism="APs arbitrage NAV gaps; flow pressure on underlyings.", pit="n/a", survivorship="ETF closures 5-8%/yr",
      raw_n="0 clean years", eff_n="n/a", lit="Ben-David-Franzoni-Moussawi (2018).", independence="ETF structure family EXHAUSTED.",
      contamination="etf_convergence/etf_basis viewed.", assemblable=False, decision="REJECT (no data)"),
 dict(id="F18", spec=None, family="Option market-maker inventory proxies",
      information="Per-underlying open interest / MM net gamma", source="OCC: aggregate daily OI only; per-symbol history not free; CBOE P/C archive ends 2019",
      mechanism="Dealer gamma hedging amplifies/dampens moves.", pit="n/a", survivorship="n/a", raw_n="0 clean years", eff_n="n/a",
      lit="Ni-Pearson-Poteshman (2005) pinning; Baltussen et al. (2021) gamma.", independence="Options information family EXHAUSTED; index option volume forbidden.",
      contamination="options_signals, index_option_breadth viewed.", assemblable=False, decision="REJECT (no data; exhausted)"),
 dict(id="F19", spec=None, family="Cross-market segmentation (TIPS-nominal, ADR-local, CEF discounts)",
      information="Relative-value gaps between economically identical claims", source="Inflation swaps, ADR ratios, CEF NAV histories: none free and PIT",
      mechanism="Segmented investor bases; arbitrage capital limits.", pit="n/a", survivorship="CEF/ADR delistings", raw_n="0 clean years", eff_n="n/a",
      lit="Fleckenstein-Longstaff-Lustig (2014) TIPS puzzle; Gagnon-Karolyi ADR parity.", independence="New.", contamination="Low.",
      assemblable=False, decision="REJECT (no free PIT data; not retail-tradable)"),
 dict(id="F20", spec=None, family="Settlement mechanics (Treasury settlement fails)",
      information="Primary-dealer fails to deliver/receive (NY Fed PD statistics)", source="Same NY Fed bulk file as F1",
      mechanism="Collateral scarcity / specialness; fails charge since 2009.", pit="Weekly, 8-day lag", survivorship="None", raw_n="weekly 2001+",
      eff_n="n/a", lit="Fleming-Garbade (2005).", independence="Would share F1's dataset and dealer mechanism.",
      contamination="Low.", assemblable=True, decision="REJECT (no identified tradable return; a fails->price mapping would be invented post hoc)"),
]
# fmt: on


def main() -> None:
    rows = []
    for f in FAMILIES:
        r = dict(f)
        if f["spec"]:
            rep = json.loads((PW / f"{f['spec']}.json").read_text())
            spec_path = ROOT / "research" / "new_info_scout" / "specs" / f"{f['spec']}.json"
            r["spec_file"] = str(spec_path.relative_to(ROOT))
            r["spec_sha256"] = hashlib.sha256(spec_path.read_bytes()).hexdigest()
            r["years_total"] = rep["windows"]["dev_years"] + (rep["windows"].get("val_years") or 0)
            r["joint_power_at_0.7"] = round(rep["joint_power_at_0.7"], 3)
            r["false_pass"] = round(rep["false_pass_zero_net"], 4)
            r["verdict_amendment3_k2"] = rep["verdict_with_proposed_val_gate"]
            m = rep["mde"]
            r["mde_sharpe_single_test"] = round(m["single_test_all_years"]["sharpe"], 2)
            r["mde_sharpe_joint"] = round(m["joint_with_proposed_val_gate"]["sharpe"], 2)
            r["mde_natural_joint"] = m["joint_with_proposed_val_gate"]["natural"]
            imp = [w for w in rep["power"] if w.get("world") == "implied_by_primitives"]
            r["implied_net_sharpe"] = round(imp[0]["true_net_sharpe"], 2) if imp else None
            r["joint_power_at_implied"] = round(imp[0]["p_joint_proposed"], 3) if imp else None
            y07 = [y for y in rep.get("years_for_power", []) if abs(y["true_net_sharpe"] - 0.7) < 1e-9]
            r["years_80pct_joint_at_0.7"] = y07[0]["joint_proposed"] if y07 else None
        else:
            r.update(spec_file=None, years_total=0, verdict_amendment3_k2="NO DATA")
        rows.append(r)
    (OUT / "families.json").write_text(json.dumps(rows, indent=1, default=str))
    cols = ["id", "family", "information", "source", "mechanism", "pit", "survivorship", "raw_n", "eff_n", "lit",
            "years_total", "joint_power_at_0.7", "false_pass", "verdict_amendment3_k2", "implied_net_sharpe",
            "joint_power_at_implied", "mde_sharpe_single_test", "mde_sharpe_joint", "years_80pct_joint_at_0.7", "independence", "contamination", "assemblable", "decision", "spec_file", "spec_sha256"]
    with open(OUT / "families.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    for r in rows:
        print(r["id"], r.get("years_total"), r.get("joint_power_at_0.7"), r["verdict_amendment3_k2"],
              r.get("implied_net_sharpe"), r.get("joint_power_at_implied"), r["decision"][:40])


if __name__ == "__main__":
    main()
