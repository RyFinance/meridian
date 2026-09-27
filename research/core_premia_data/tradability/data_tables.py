"""
Static reference data for the Core Premia Book tradability audit.

IMPORTANT: this module contains NO strategy return data, NO backtests, and NO
alpha signals. It is a compiled reference table of publicly available
instrument facts (tickers, inception dates, AUM class, expense ratios,
contract specs, regulatory facts) assembled from issuer web pages, exchange
contract-spec pages, and IBKR/CIRO published fee/margin schedules, current as
of 2026-09-26. Numbers are best-effort snapshots for a feasibility audit, not
live quotes -- see the `source` field on each record and re-verify before any
real allocation decision.

All AUM figures are bucketed into coarse classes (see AUM_CLASS legend) rather
than stated as precise dollar figures, because AUM drifts daily and precision
here would be false precision.
"""

AUM_CLASS_LEGEND = {
    "mega": ">$10B",
    "large": "$1B-$10B",
    "mid": "$100M-$1B",
    "small": "$10M-$100M",
    "micro": "<$10M (closure/liquidity risk)",
}

# ---------------------------------------------------------------------------
# 1. ETF universe
# ---------------------------------------------------------------------------
# spread_bps is a *typical* quoted-spread estimate in normal market hours,
# sourced from issuer fact sheets where published, else a qualitative
# yfinance bid/ask snapshot taken 2026-09-25, else marked "est." from issuer
# ADV/AUM class as a rule of thumb. Treat as indicative only.

ETF_UNIVERSE = [
    # -- Equity index ETFs by country --------------------------------------
    dict(bucket="equity_index", country="US (S&P500)", ticker="IVV", listing="NYSE Arca",
         inception="2000-05-15", aum_class="mega", expense_ratio=0.03, spread_bps=1,
         shortable="Yes (IBKR: easy-to-borrow, HTB rare)", cad_hedged_alt=None,
         source="https://www.ishares.com/us/products/239726/ (issuer page); IBKR shortable list (generic, not re-queried live)"),
    dict(bucket="equity_index", country="US (Total Market)", ticker="VTI", listing="NYSE Arca",
         inception="2001-05-24", aum_class="mega", expense_ratio=0.03, spread_bps=1,
         shortable="Yes (easy-to-borrow)", cad_hedged_alt="XUU.TO (unhedged), XSU.TO (hedged small-mid)",
         source="https://investor.vanguard.com/investment-products/etfs/profile/vti"),
    dict(bucket="equity_index", country="Canada (S&P/TSX60)", ticker="XIU.TO", listing="TSX",
         inception="1999-09-29", aum_class="large", expense_ratio=0.18, spread_bps=2,
         shortable="Yes on TSX (borrow via IBKR Canada, generally available)", cad_hedged_alt="native CAD, no hedge needed",
         source="https://www.blackrock.com/ca/investors/en/products/239832 (iShares XIU fact sheet)"),
    dict(bucket="equity_index", country="UK (FTSE 100)", ticker="EWU", listing="NYSE Arca",
         inception="1996-03-12", aum_class="mid", expense_ratio=0.5, spread_bps=6,
         shortable="Yes, but thinner borrow than mega-cap US ETFs", cad_hedged_alt="none listed on TSX",
         source="https://www.ishares.com/us/products/239631/ (iShares MSCI UK ETF)"),
    dict(bucket="equity_index", country="Germany (DAX/MSCI Germany)", ticker="EWG", listing="NYSE Arca",
         inception="1996-03-12", aum_class="mid", expense_ratio=0.5, spread_bps=6,
         shortable="Yes, moderate borrow availability", cad_hedged_alt="none listed on TSX",
         source="https://www.ishares.com/us/products/239644/ (iShares MSCI Germany ETF)"),
    dict(bucket="equity_index", country="Japan (MSCI Japan/Nikkei)", ticker="EWJ", listing="NYSE Arca",
         inception="1996-03-12", aum_class="large", expense_ratio=0.5, spread_bps=3,
         shortable="Yes, easy-to-borrow (large AUM)", cad_hedged_alt="ZJPN.TO (BMO, hedged) is CAD-hedged Japan equity",
         source="https://www.ishares.com/us/products/239665/ (iShares MSCI Japan ETF)"),
    dict(bucket="equity_index", country="Australia (MSCI Australia)", ticker="EWA", listing="NYSE Arca",
         inception="1996-03-12", aum_class="mid", expense_ratio=0.5, spread_bps=6,
         shortable="Yes, moderate", cad_hedged_alt=None,
         source="https://www.ishares.com/us/products/239600/ (iShares MSCI Australia ETF)"),
    dict(bucket="equity_index", country="Emerging Markets (broad)", ticker="EEM", listing="NYSE Arca",
         inception="2003-04-07", aum_class="mega", expense_ratio=0.70, spread_bps=2,
         shortable="Yes, easy-to-borrow (very liquid)", cad_hedged_alt="XEC.TO / ZEM.TO (unhedged EM, CAD-listed)",
         source="https://www.ishares.com/us/products/239637/ (iShares MSCI EM ETF)"),
    dict(bucket="equity_index", country="Eurozone (broad, EMU)", ticker="EZU", listing="NYSE Arca",
         inception="2000-07-25", aum_class="mid", expense_ratio=0.5, spread_bps=4,
         shortable="Yes, moderate", cad_hedged_alt="ZDM.TO/ZEA.TO broad developed-ex-NA CAD-hedged (not pure Eurozone)",
         source="https://www.ishares.com/us/products/239635/ (iShares MSCI Eurozone ETF)"),
    dict(bucket="equity_index", country="China (large cap)", ticker="FXI", listing="NYSE Arca",
         inception="2004-10-05", aum_class="large", expense_ratio=0.74, spread_bps=2,
         shortable="Yes, easy-to-borrow", cad_hedged_alt=None,
         source="https://www.ishares.com/us/products/239647/ (iShares China Large-Cap ETF)"),

    # -- Government bond ETFs by country/duration --------------------------
    dict(bucket="gov_bond", country="US Treasury 1-3y", ticker="SHY", listing="Nasdaq",
         inception="2002-07-22", aum_class="large", expense_ratio=0.15, spread_bps=1,
         shortable="Yes, easy-to-borrow", cad_hedged_alt="ZTS.TO/XSB.TO (Canada short bond, not US-hedged)",
         source="https://www.ishares.com/us/products/239452/ (iShares 1-3Y Treasury Bond ETF)"),
    dict(bucket="gov_bond", country="US Treasury 7-10y", ticker="IEF", listing="Nasdaq",
         inception="2002-07-22", aum_class="large", expense_ratio=0.15, spread_bps=1,
         shortable="Yes, easy-to-borrow", cad_hedged_alt="ZFL.TO/XGGB.TO variants exist but not exact 7-10y US match; ZTL.TO (long)",
         source="https://www.ishares.com/us/products/239456/ (iShares 7-10Y Treasury Bond ETF)"),
    dict(bucket="gov_bond", country="US Treasury 20y+", ticker="TLT", listing="Nasdaq",
         inception="2002-07-22", aum_class="mega", expense_ratio=0.15, spread_bps=1,
         shortable="Yes, very liquid borrow (popular short/hedge vehicle)", cad_hedged_alt="HTA.TO / ZTL.TO approximate long-duration CAD-hedged exposure",
         source="https://www.ishares.com/us/products/239454/ (iShares 20+Y Treasury Bond ETF)"),
    dict(bucket="gov_bond", country="Canada (broad govt)", ticker="XGB.TO", listing="TSX",
         inception="2011-08-16", aum_class="mid", expense_ratio=0.17, spread_bps=3,
         shortable="Limited borrow relative to US treasuries", cad_hedged_alt="native CAD",
         source="https://www.blackrock.com/ca/investors/en/products/251421 (iShares XGB fact sheet)"),
    dict(bucket="gov_bond", country="Canada short (1-5y)", ticker="XSB.TO", listing="TSX",
         inception="2000-02-22", aum_class="large", expense_ratio=0.10, spread_bps=2,
         shortable="Yes, moderate borrow", cad_hedged_alt="native CAD",
         source="https://www.blackrock.com/ca/investors/en/products/239486 (iShares XSB fact sheet)"),
    dict(bucket="gov_bond", country="Canada long (10y+)", ticker="XLB.TO", listing="TSX",
         inception="2000-02-22", aum_class="mid", expense_ratio=0.16, spread_bps=4,
         shortable="Limited borrow", cad_hedged_alt="native CAD",
         source="https://www.blackrock.com/ca/investors/en/products/239488 (iShares XLB fact sheet)"),
    dict(bucket="gov_bond", country="Germany/Eurozone govt (EUR)", ticker="IS0L.DE / IGLE (varies)", listing="EU exchanges (not US/TSX-listed)",
         inception="n/a", aum_class="mid", expense_ratio=0.16, spread_bps=None,
         shortable="Not readily accessible from a Canadian retail account without EU broker access",
         cad_hedged_alt="ZGB.TO does NOT exist; practical gap -- see gap note",
         source="issuer: iShares Core Euro Government Bond UCITS (EU-listed); no equivalent widely available via IBKR Canada in USD/CAD share classes"),
    dict(bucket="gov_bond", country="UK Gilts", ticker="IGLT (LSE) / no direct US ticker", listing="LSE (UCITS)",
         inception="2004-01-23", aum_class="mid", expense_ratio=0.20, spread_bps=None,
         shortable="Access gap: UK-domiciled UCITS ETF, buyable via IBKR on LSE but with FX + UK stamp/PTM considerations",
         cad_hedged_alt="none on TSX", source="https://www.ishares.com/uk/individual/en/products/251771 (iShares Core UK Gilts UCITS ETF)"),
    dict(bucket="gov_bond", country="Japan JGB", ticker="No liquid US/TSX-listed pure JGB ETF", listing="n/a",
         inception="n/a", aum_class="n/a", expense_ratio=None, spread_bps=None,
         shortable="Access gap: practically unavailable to retail ex-futures (see JGB futures note under CME/other)",
         cad_hedged_alt=None, source="qualitative finding; no major US/TSX-listed JGB ETF identified as of 2026-09"),
    dict(bucket="gov_bond", country="Australia govt bonds", ticker="No direct US/TSX-listed pure AUD govt ETF",
         listing="n/a", inception="n/a", aum_class="n/a", expense_ratio=None, spread_bps=None,
         shortable="Access gap", cad_hedged_alt=None,
         source="qualitative finding; ASX-listed options (e.g. VGB.AX) not reachable via standard IBKR Canada retail without ASX access"),

    # -- Currency ETFs (Invesco CurrencyShares) ----------------------------
    dict(bucket="currency", country="EUR", ticker="FXE", listing="NYSE Arca", inception="2005-12-09",
         aum_class="mid", expense_ratio=0.40, spread_bps=3, shortable="Yes, moderate borrow",
         cad_hedged_alt="n/a (currency exposure vehicle)",
         source="https://www.invesco.com/us/financial-products/etfs/product-detail?audienceType=Investor&ticker=FXE"),
    dict(bucket="currency", country="JPY", ticker="FXY", listing="NYSE Arca", inception="2007-02-13",
         aum_class="small", expense_ratio=0.40, spread_bps=4, shortable="Yes, but thinner than FXE",
         cad_hedged_alt="n/a", source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=FXY"),
    dict(bucket="currency", country="GBP", ticker="FXB", listing="NYSE Arca", inception="2006-06-21",
         aum_class="small", expense_ratio=0.40, spread_bps=4, shortable="Yes, thin", cad_hedged_alt="n/a",
         source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=FXB"),
    dict(bucket="currency", country="AUD", ticker="FXA", listing="NYSE Arca", inception="2006-06-21",
         aum_class="small", expense_ratio=0.40, spread_bps=5, shortable="Yes, thin", cad_hedged_alt="n/a",
         source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=FXA"),
    dict(bucket="currency", country="CAD", ticker="FXC", listing="NYSE Arca", inception="2006-06-21",
         aum_class="small", expense_ratio=0.40, spread_bps=5, shortable="Yes, thin", cad_hedged_alt="n/a (this IS the CAD exposure vehicle)",
         source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=FXC"),
    dict(bucket="currency", country="CHF", ticker="FXF", listing="NYSE Arca", inception="2006-06-21",
         aum_class="micro", expense_ratio=0.40, spread_bps=6, shortable="Thin, may be HTB at times", cad_hedged_alt="n/a",
         source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=FXF"),
    dict(bucket="currency", country="SEK (CLOSED)", ticker="FXS", listing="was NYSE Arca (delisted)",
         inception="2006-09; closed/liquidated 2020-05-22", aum_class="n/a (closed)", expense_ratio=None,
         spread_bps=None, shortable="N/A -- fund liquidated, not tradable",
         cad_hedged_alt=None,
         source="Invesco press release 2019-12-13 announcing closures; fund ceased operations 2020-05-22 (https://www.prnewswire.com/news-releases/invesco-announces-changes-to-its-us-etf-and-mutual-fund-product-lines-300974616.html)"),
    dict(bucket="currency", country="CNY (CLOSED)", ticker="FXCH", listing="was NYSE Arca (delisted)",
         inception="2011; closed ~2016-17", aum_class="n/a (closed)", expense_ratio=None, spread_bps=None,
         shortable="N/A -- fund closed", cad_hedged_alt=None,
         source="Invesco CurrencyShares Chinese Renminbi Trust product page shows fund history/closure; verify current status directly with Invesco before relying on this (https://www.invesco.com/us-rest/contentdetail?contentId=bcc53c5611e6f610VgnVCM1000006e36b50aRCRD)"),

    # -- Commodity ETFs ------------------------------------------------------
    dict(bucket="commodity", country="Gold", ticker="GLD", listing="NYSE Arca", inception="2004-11-18",
         aum_class="mega", expense_ratio=0.40, spread_bps=1, shortable="Yes, very easy-to-borrow",
         cad_hedged_alt="ZGLD.TO / CGL.TO (hedged), CGL.C.TO (unhedged)",
         source="https://www.spdrgoldshares.com/ (SPDR Gold Shares fact sheet)"),
    dict(bucket="commodity", country="Gold (low-cost)", ticker="IAU", listing="NYSE Arca", inception="2005-01-21",
         aum_class="mega", expense_ratio=0.25, spread_bps=1, shortable="Yes, easy-to-borrow",
         cad_hedged_alt="CGL.TO", source="https://www.ishares.com/us/products/239561/ (iShares Gold Trust)"),
    dict(bucket="commodity", country="Silver", ticker="SLV", listing="NYSE Arca", inception="2006-04-21",
         aum_class="large", expense_ratio=0.50, spread_bps=2, shortable="Yes, easy-to-borrow",
         cad_hedged_alt="CSIV.TO (BMO)", source="https://www.ishares.com/us/products/239855/ (iShares Silver Trust)"),
    dict(bucket="commodity", country="Broad commodity basket", ticker="DBC", listing="NYSE Arca", inception="2006-02-03",
         aum_class="mid", expense_ratio=0.87, spread_bps=4, shortable="Yes, moderate borrow",
         cad_hedged_alt=None, source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=DBC"),
    dict(bucket="commodity", country="Crude oil (front-month, futures-based)", ticker="USO", listing="NYSE Arca",
         inception="2006-04-10", aum_class="mid", expense_ratio=0.60, spread_bps=3,
         shortable="Yes; note K-1 tax form + heavy contango/roll drag, poor trend proxy vs. futures",
         cad_hedged_alt="HUC.TO (Horizons, uses forward agreement structure)",
         source="https://www.uscfinvestments.com/uso (USO fund page)"),
    dict(bucket="commodity", country="Natural gas (futures-based)", ticker="UNG", listing="NYSE Arca",
         inception="2007-04-18", aum_class="small", expense_ratio=1.10, spread_bps=6,
         shortable="Yes but very high roll cost/decay; poor buy-and-hold trend proxy",
         cad_hedged_alt="HUN.TO (Horizons)", source="https://www.uscfinvestments.com/ung (UNG fund page)"),
    dict(bucket="commodity", country="Copper", ticker="CPER", listing="NYSE Arca", inception="2011-11-15",
         aum_class="small", expense_ratio=0.85, spread_bps=6, shortable="Thin borrow, not always available",
         cad_hedged_alt=None, source="https://www.uscfinvestments.com/cper (CPER fund page)"),
    dict(bucket="commodity", country="Agriculture broad", ticker="DBA", listing="NYSE Arca", inception="2007-01-05",
         aum_class="mid", expense_ratio=0.93, spread_bps=5, shortable="Yes, moderate borrow",
         cad_hedged_alt=None, source="https://www.invesco.com/us/financial-products/etfs/product-detail?ticker=DBA"),
]

# ---------------------------------------------------------------------------
# 2. Futures specs (micro/mini contracts relevant to a diversified trend book)
# ---------------------------------------------------------------------------
# notional_usd is *indicative only*, computed from an approximate late-Sept-2026
# reference price level noted in `ref_price`. This is NOT a return/backtest
# input -- purely a contract-sizing fact for the rounding-error arithmetic.

FUTURES_SPECS = [
    dict(exchange="CME", symbol="MES", name="Micro E-mini S&P 500", asset_class="equity_index",
         multiplier=5.0, ref_price=6650, tick=0.25, tick_value=1.25,
         notional_usd=5 * 6650, ibkr_commission_usd=0.62, exch_fee_usd=1.02,
         source="https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp500.contractSpecs.html ; IBKR fee page https://www.interactivebrokers.com/en/accounts/fees/CME.php"),
    dict(exchange="CME", symbol="MNQ", name="Micro E-mini Nasdaq-100", asset_class="equity_index",
         multiplier=2.0, ref_price=24500, tick=0.25, tick_value=0.50,
         notional_usd=2 * 24500, ibkr_commission_usd=0.62, exch_fee_usd=1.02,
         source="https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html"),
    dict(exchange="CME", symbol="M2K", name="Micro E-mini Russell 2000", asset_class="equity_index",
         multiplier=10.0, ref_price=2350, tick=0.10, tick_value=1.00,
         notional_usd=10 * 2350, ibkr_commission_usd=0.62, exch_fee_usd=1.02,
         source="https://www.cmegroup.com/markets/equities/russell/e-micro-russell-2000-index.contractSpecs.html"),
    dict(exchange="CME", symbol="MYM", name="Micro E-mini Dow", asset_class="equity_index",
         multiplier=0.50, ref_price=46000, tick=1.0, tick_value=0.50,
         notional_usd=0.5 * 46000, ibkr_commission_usd=0.62, exch_fee_usd=1.02,
         source="https://www.cmegroup.com/markets/equities/dow-jones/micro-e-mini-dow.contractSpecs.html"),
    dict(exchange="CME", symbol="2YY", name="Micro 2-Year Yield futures", asset_class="gov_bond",
         multiplier=10.0, ref_price=350, tick=0.1, tick_value=1.00,  # BPV $10/bp; price in "yield bps" convention differs, see note
         notional_usd=None, ibkr_commission_usd=0.65, exch_fee_usd=0.55,
         source="https://www.cmegroup.com/markets/interest-rates/us-treasury/2-year-yield.contractSpecs.html ; yield futures are cash-settled on yield, BPV $10/bp -- notional concept doesn't map 1:1 like price-based futures, see rounding_error methodology note"),
    dict(exchange="CME", symbol="10Y", name="Micro 10-Year Yield futures", asset_class="gov_bond",
         multiplier=10.0, ref_price=420, tick=0.1, tick_value=1.00,
         notional_usd=None, ibkr_commission_usd=0.65, exch_fee_usd=0.55,
         source="https://www.cmegroup.com/markets/interest-rates/us-treasury/10-year-yield.contractSpecs.html"),
    dict(exchange="CME", symbol="30Y", name="Micro 30-Year Yield futures", asset_class="gov_bond",
         multiplier=10.0, ref_price=460, tick=0.1, tick_value=1.00,
         notional_usd=None, ibkr_commission_usd=0.65, exch_fee_usd=0.55,
         source="https://www.cmegroup.com/markets/interest-rates/us-treasury/30-year-yield.contractSpecs.html"),
    dict(exchange="CME", symbol="ZT/ZN/ZB (standard, no micro price-based note)", name="Note: CME does not offer 'micro' PRICE-based T-note/bond futures (only yield futures are micro-sized); smallest price-based US treasury exposure is the standard 2Y/10Y/30Y note/bond contract at $200k/$100k face",
         asset_class="gov_bond", multiplier=None, ref_price=None, tick=None, tick_value=None,
         notional_usd=None, ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.cmegroup.com/markets/interest-rates/us-treasury.html ; qualitative access-gap note for rounding-error section"),
    dict(exchange="CME", symbol="M6E", name="Micro EUR/USD", asset_class="fx",
         multiplier=12500.0, ref_price=1.08, tick=0.0001, tick_value=1.25,
         notional_usd=12500 * 1.08, ibkr_commission_usd=0.42, exch_fee_usd=0.35,
         source="https://www.cmegroup.com/markets/fx/g10/e-micro-euro.contractSpecs.html"),
    dict(exchange="CME", symbol="M6A", name="Micro AUD/USD", asset_class="fx",
         multiplier=10000.0, ref_price=0.65, tick=0.0001, tick_value=1.00,
         notional_usd=10000 * 0.65, ibkr_commission_usd=0.42, exch_fee_usd=0.35,
         source="https://www.cmegroup.com/markets/fx/g10/e-micro-australian-dollar.contractSpecs.html"),
    dict(exchange="CME", symbol="M6B", name="Micro GBP/USD", asset_class="fx",
         multiplier=6250.0, ref_price=1.27, tick=0.0001, tick_value=0.625,
         notional_usd=6250 * 1.27, ibkr_commission_usd=0.42, exch_fee_usd=0.35,
         source="https://www.cmegroup.com/markets/fx/g10/e-micro-british-pound.contractSpecs.html"),
    dict(exchange="CME", symbol="MCD", name="Micro CAD/USD", asset_class="fx",
         multiplier=10000.0, ref_price=0.73, tick=0.0001, tick_value=1.00,
         notional_usd=10000 * 0.73, ibkr_commission_usd=0.42, exch_fee_usd=0.35,
         source="https://www.cmegroup.com/markets/fx/g10/e-micro-cad.html (verify exact symbol/listing status directly -- CAD micro liquidity is thin)"),
    dict(exchange="CME", symbol="M6J", name="Micro JPY/USD (quoted M6J, not MJY)", asset_class="fx",
         multiplier=1250000.0, ref_price=0.0068, tick=0.0000005, tick_value=0.625,
         notional_usd=1250000 * 0.0068, ibkr_commission_usd=0.42, exch_fee_usd=0.35,
         source="https://www.cmegroup.com/markets/fx/g10/e-micro-japanese-yen.contractSpecs.html (note: correct ticker is M6J, not 'MJY')"),
    dict(exchange="COMEX", symbol="MGC", name="Micro Gold", asset_class="commodity",
         multiplier=10.0, ref_price=3800, tick=0.10, tick_value=1.00,
         notional_usd=10 * 3800, ibkr_commission_usd=0.47, exch_fee_usd=0.45,
         source="https://www.cmegroup.com/markets/metals/precious/e-micro-gold.contractSpecs.html"),
    dict(exchange="COMEX", symbol="SIL", name="Micro Silver", asset_class="commodity",
         multiplier=1000.0, ref_price=44, tick=0.005, tick_value=5.00,
         notional_usd=1000 * 44, ibkr_commission_usd=0.47, exch_fee_usd=0.45,
         source="https://www.cmegroup.com/markets/metals/precious/micro-silver.contractSpecs.html"),
    dict(exchange="NYMEX", symbol="MCL", name="Micro WTI Crude Oil", asset_class="commodity",
         multiplier=100.0, ref_price=65, tick=0.01, tick_value=1.00,
         notional_usd=100 * 65, ibkr_commission_usd=0.47, exch_fee_usd=0.45,
         source="https://www.cmegroup.com/markets/energy/crude-oil/micro-wti.contractSpecs.html"),
    dict(exchange="NYMEX", symbol="MNG (verify)", name="Micro Henry Hub Natural Gas -- NOTE: CME's micro nat-gas ticker should be verified directly (commonly cited as MNG or via M-suite); treat with caution",
         asset_class="commodity", multiplier=2500.0, ref_price=3.2, tick=0.005, tick_value=12.5,
         notional_usd=2500 * 3.2, ibkr_commission_usd=0.47, exch_fee_usd=0.45,
         source="https://www.cmegroup.com/markets/energy/natural-gas/micro-henry-hub-natural-gas.contractSpecs.html (confirm exact symbol before use)"),
    dict(exchange="Eurex", symbol="FDXM", name="Mini-DAX", asset_class="equity_index",
         multiplier=5.0, ref_price=24000, tick=0.5, tick_value=2.5,
         notional_usd=5 * 24000 * 1.06,  # EUR->approx USD, indicative only
         ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.eurex.com/ex-en/find/contracts (Mini-DAX Futures FDXM contract specs); IBKR does provide Eurex access but confirm CAD-account routing/fees directly"),
    dict(exchange="Eurex", symbol="FESX (mini)/FSXE (micro)", name="EURO STOXX 50 mini / micro futures",
         asset_class="equity_index", multiplier=10.0, ref_price=5400, tick=1.0, tick_value=10.0,
         notional_usd=10 * 5400 * 1.06,
         ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.eurex.com/ex-en/find/contracts (EURO STOXX 50 Index Futures family incl. Micro variant FSXE)"),
    dict(exchange="MX (Montreal Exchange)", symbol="CGB", name="10-Year Government of Canada Bond futures",
         asset_class="gov_bond", multiplier=1000.0, ref_price=100.0, tick=0.01, tick_value=10.0,
         notional_usd=100000,  # CAD100,000 face value, quoted per $100 nominal
         ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.m-x.ca/en/markets/interest-rate-derivatives/cgb ; CAD100,000 nominal face value per contract"),
    dict(exchange="MX (Montreal Exchange)", symbol="SXF", name="S&P/TSX 60 Index Standard futures",
         asset_class="equity_index", multiplier=200.0, ref_price=1450, tick=0.1, tick_value=20.0,
         notional_usd=200 * 1450,
         ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.m-x.ca/en/markets/equity-index-derivatives/sxf (SXF contract multiplier CAD200 x index)"),
    dict(exchange="MX (Montreal Exchange)", symbol="SXM", name="S&P/TSX 60 Index Mini futures",
         asset_class="equity_index", multiplier=50.0, ref_price=1450, tick=0.1, tick_value=5.0,
         notional_usd=50 * 1450,
         ibkr_commission_usd=None, exch_fee_usd=None,
         source="https://www.m-x.ca/en/markets/equity-index-derivatives/sxm (SXM = 1/4 size of SXF, CAD50 x index)"),
]

# ---------------------------------------------------------------------------
# 3. Account-type / regulatory facts
# ---------------------------------------------------------------------------
ACCOUNT_FACTS = [
    dict(topic="TFSA - futures/margin",
         finding=("TFSAs are not eligible for margin and short selling is not permitted. Futures contracts "
                  "where the holder's risk of loss can exceed the initial cost are not qualified investments "
                  "in a TFSA (or RRSP/RRIF/RESP/RDSP/FHSA). Holding a non-qualified investment triggers a 50% "
                  "tax on fair market value under ITA s.207.01/207.04, borne by the account holder."),
         source="CRA Income Tax Folio S3-F10-C1 (Qualified Investments) and S3-F10-C2 (Prohibited Investments): "
                "https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-3-property-investments-savings-plans/series-3-property-investments-savings-plan-folio-10-registered-plans-individuals/income-tax-folio-s3-f10-c1-qualified-investments-rrsps-resps-rrifs-rdsps-tfsas.html"),
     dict(topic="RRSP - futures/margin/shorting",
         finding=("Same qualified-investment rules apply to RRSP as TFSA: leveraged futures positions and short "
                  "selling are generally not permitted inside an RRSP at retail brokers, and naked futures are "
                  "not a qualified investment. A long-only, fully-funded ETF sleeve (no margin, no short) IS "
                  "permitted in both TFSA and RRSP."),
         source="Same CRA folios as above; broker-level confirmation e.g. Questrade/RBC Direct Investing account "
                "type pages (https://www.questrade.com/learning/accounts-taxes/tfsa-and-margin-accounts)"),
    dict(topic="RRSP US-dividend withholding treaty exemption vs TFSA",
         finding=("Under Article XXI of the Canada-US tax treaty, US-source dividends paid into an RRSP/RRIF are "
                  "exempt from the normal 15% US withholding tax. This exemption does NOT extend to a TFSA (or "
                  "RESP/RDSP): US dividends held in a TFSA are subject to the full 15% US withholding, non-recoverable "
                  "because a TFSA is not recognized as a pension vehicle under the treaty. This matters directly for "
                  "a Core Premia Book that holds long equity-index and bond ETFs with US dividend/coupon distributions -- "
                  "RRSP is the tax-preferred registered wrapper for the long-only US-listed ETF sleeve, TFSA is not."),
         source="CRA / IRS treaty guidance, summarized at e.g. https://www.taxtips.ca/rrsp/qualified-investments-rrsp-rrif-resp-rdsp-tfsa.htm ; "
                "primary source Canada-US Tax Convention Article XXI(2)"),
    dict(topic="Margin account requirements for futures and shorting (IIROC/CIRO)",
         finding=("A prospective futures trader must open a separate futures-approved margin account, complete a "
                  "futures trading application, pass KYC/suitability review, and sign futures-specific risk-disclosure "
                  "agreements. Margin for futures at IIROC/CIRO-regulated dealers follows the 'greatest of' methodology "
                  "under Dealer Member Rule/Form 1 s.5790 (SPAN or exchange-minimum margin, whichever the dealer's model "
                  "requires); brokers commonly require CAD 5,000-25,000+ minimum futures account equity in practice "
                  "(broker-specific, not an IIROC minimum) and demonstrated experience/net worth thresholds for approval. "
                  "Short selling equities/ETFs requires a standard margin account (not cash/registered) and is subject to "
                  "CIRO UMIR short-sale marking and locate/borrow rules."),
         source="CIRO (formerly IIROC) Rules s.5790 futures margin framework; CIRO UMIR short-sale guidance: "
                "https://www.ciro.ca/newsroom/publications/guidance-umir-requirements-related-short-selling-and-failed-trades ; "
                "broker futures-account minimums are broker-specific (verify with IBKR Canada directly, not an IIROC/CIRO rule)"),
]

TAX_NOTE = (
    "NOT TAX ADVICE -- consult a qualified Canadian tax professional before implementing. In a non-registered "
    "(taxable) account: (1) Gains/losses on exchange-traded futures held by an individual are generally reported "
    "as capital gains/losses under ITA s.9/s.39, with an election available under s.39(4) to have ALL futures/"
    "commodity transactions treated on capital account consistently (once elected, binding for all subsequent years). "
    "(2) FX gains/losses on personal, non-business foreign-currency transactions are capital in nature, subject to "
    "the CAD 200 de minimis exemption (s.39(1.1)); FX conversion via Norbert's Gambit (buying/selling DLR/DLR.U) "
    "itself is a securities trade, not a currency trade, so its own gain/loss is capital in nature. (3) The CRA "
    "may recharacterize an active/frequent trading pattern (high turnover, short holding periods, use of leverage, "
    "time devoted, specialized knowledge) as carrying on a business, converting gains to fully-taxable business "
    "income (and losses to fully-deductible business losses) rather than capital gains/losses (50% inclusion). A "
    "systematic trend/carry book with monthly-or-faster rebalancing across 40-60 futures markets is a plausible "
    "candidate for business-income characterization -- this is a facts-and-circumstances determination the CRA "
    "makes, not a bright-line rule, and the s.39(4) capital-treatment election does NOT protect a trader whose "
    "overall conduct looks like a business. Get a professional opinion before implementation."
)
