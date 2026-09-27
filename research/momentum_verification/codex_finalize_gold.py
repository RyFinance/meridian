import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research.return_search.run import cash_rates,stats
from research.momentum_verification.codex_fund_designs import load
from research.momentum_verification.codex_ledger import ledger
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/momentum_gold_20260919'


def main():
    d=json.loads((OUT/'results.json').read_text());p=load('2026-09-17');rf=cash_rates(p['close'].index,'2026-09-17');t=pd.read_csv(OUT/'momentum_gold_targets.csv',index_col=0,parse_dates=True)
    independent={}
    for fee in [0.,1.]:
        f,fills,c,error=ledger(p['open'],p['close'],t,rf,'2020-01-01',order_fee=fee)
        source=pd.read_csv(OUT/'momentum_gold_later_base.csv',index_col=0,parse_dates=True)
        if not fee:assert (source.nav-f.nav).abs().max()<1e-10
        assert abs(error)<1e-6
        independent[str(fee)]={'max_nav_difference_vs_baseline':float((source.nav-f.nav).abs().max()),'metrics':stats(f,rf,252),'fills':len(fills),'total_cost_dollars':float(f.cost_dollars.sum()),'pnl_reconciliation_dollars':error}
        f.to_csv(OUT/f'independent_fee_{int(fee)}.csv')
    (OUT/'independent_check.json').write_text(json.dumps(independent,indent=2))
    uncertainty={};rng=np.random.default_rng(20260920)
    for name in ['earlier','later','full']:
        f=pd.read_csv(OUT/f'momentum_gold_{name}_base.csv',index_col=0,parse_dates=True);x=(f['return']-rf.reindex(f.index)).to_numpy();n=len(x);sr=[]
        for _ in range(4000):
            ix=((rng.integers(n,size=int(np.ceil(n/20)))[:,None]+np.arange(20))%n).ravel()[:n];b=x[ix];sr.append(b.mean()/b.std(ddof=1)*np.sqrt(252))
        uncertainty[name]={'excess_sharpe_ci95':np.quantile(sr,[.025,.975]).tolist(),'block_sessions':20,'draws':4000,'note':'no adjustment for project-wide repeated testing'}
    (OUT/'uncertainty.json').write_text(json.dumps(uncertainty,indent=2))
    code=ROOT/'research/momentum_verification/codex_momentum_gold.py'
    paper={'strategy':'momentum_gold_v1','registered_date':'2026-09-20','status':'frozen for forward paper evaluation; no fills yet','weights':{'SPMO':.5,'GLD':.5},'capital_usd':100000,'leverage':1,'decision':'first NYSE session close each month','fill':'following NYSE session open','expected_next_decision':'2026-10-01','expected_next_fill':'2026-10-02','base_cost_per_side_bps':5,'stress_cost_per_side_bps':15,'additional_order_fee_usd':1,'marks':'daily adjusted total-return NAV; actual paper fills must record nominal prices, dividends, splits, shares and fees separately','benchmark':{'SPY':.5,'GLD':.5},'code_sha256':hashlib.sha256(code.read_bytes()).hexdigest(),'freeze_rule':'No changing weights, assets, timing or cost assumptions based on subsequent paper performance without registering a new strategy version.'}
    (OUT/'forward_paper_spec.json').write_text(json.dumps(paper,indent=2))
    log=OUT/'forward_paper_events.jsonl'
    if not log.exists():log.write_text(json.dumps({'event':'strategy_registered','date':'2026-09-20','strategy':'momentum_gold_v1','spec_sha256':hashlib.sha256((OUT/'forward_paper_spec.json').read_bytes()).hexdigest(),'executed_orders':0})+'\n')
    lines=['# Momentum + gold: research result and forward specification','','**Fixed 50% SPMO / 50% GLD, monthly rebalance, no leverage.** Net simulated CAGR is 19.91% with 1.03 excess Sharpe over 2020–September 2026, and 17.98% with 1.06 Sharpe over 2017–September 2026. Maximum daily marked drawdown is 18.74%.','','## Exact implementation','','At the close of the first trading session each month, set equal dollar targets in SPMO and GLD. Execute at the next session open. Hold actual adjusted units between rebalances, so weights drift naturally. No trend filter, forecasts, leverage, fitted allocation weights, or individual-stock universe. The ETF return histories include embedded fund expenses and distributions. Base costs are 5bps per side of traded notional; stress is 15bps per side. Final liquidation is charged. Figures are before personal taxes and any account-specific currency-conversion fees.','','SPMO is an actual momentum fund, with inception in October 2015; [Invesco fund information](https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Institutional&ticker=SPMO). GLD tracks gold less fund expenses; [SPDR fund information](https://www.spdrgoldshares.com/usa/gld/). The prices used here are adjusted daily fund histories from Yahoo, not reconstructed current-member stock portfolios. This portfolio itself is simulated, not an actual managed account track record.','','## Results','','| Portfolio / period | Net CAGR | Excess Sharpe | Max drawdown |','|---|---:|---:|---:|']
    for key in ['momentum_gold','market_gold']:
        for period,label in [('earlier','2017–2019'),('later','2020–2026-09-17'),('full','2017–2026-09-17')]:
            b=d[key][period]['base'];lines.append(f"| {key}, {label} | {b['cagr']:.2%} | {b['excess_sharpe']:.2f} | {b['max_dd']:.2%} |")
    stress=d['momentum_gold']['later']['stress'];fee=independent['1.0']['metrics'];ci=uncertainty['later']['excess_sharpe_ci95'];active=d['active_later']
    lines += ['',f"Tripling modeled transaction costs leaves the later-period result at **{stress['cagr']:.2%} CAGR / {stress['excess_sharpe']:.2f} Sharpe**. An independently written ledger reconciles daily NAV to within 1e-10 and all dollar P&L within $0.000001. Adding a $1 fee per order to the 5bps proportional charge on a $100,000 paper account yields {fee['cagr']:.2%} CAGR / {fee['excess_sharpe']:.2f} Sharpe.",'','The unmodified SPMO fund returned 21.75% annually / 0.84 Sharpe with a 30.95% drawdown over the same 2020–2026 window. The equal allocation gives up some return for lower volatility and drawdown. It is not the highest raw-return portfolio tested.','','## Calendar-year total returns','','| Year | Momentum/gold | Market/gold control |','|---|---:|---:|']
    for year,value in d['momentum_gold']['yearly'].items():
        label=year+' through Sep 17' if year=='2026' else year
        lines.append(f"| {label} | {value['total_return']:.2%} | {d['market_gold']['yearly'][year]['total_return']:.2%} |")
    lines += ['','## What this supports, and what it does not','',f"Later-period excess-Sharpe 95% interval from a 20-session block bootstrap: **{ci[0]:.2f} to {ci[1]:.2f}**. The annual arithmetic active return over 50% SPY / 50% GLD is {active['annual_mean']:.2%}, with HAC t={active['t_hac']:.2f} and a 95% interval of {active['ci95'][0]:.2%} to {active['ci95'][1]:.2%}. That does not establish significant unique alpha above the simpler diversified control.",'','This was a follow-up hypothesis after three other fund designs were tested. The simple equal weights were recorded before this run and not optimized, but these years had already been examined in the broader project. This is a reproducible historical candidate with genuine traded-fund inputs, not an untouched holdout or proven future edge. Results may depend on the strong equity-momentum and gold regimes in this sample. SPMO does not supply a pre-2015 live record.','','The original stock strategy remains provisional: a membership filter materially weakened it; missing removed stocks prevent a full point-in-time universe validation. No attempt was made to reinterpret that result as clean proof.','','## All preceding fixed fund designs, 2020–2026','','| Design | Net CAGR | Excess Sharpe | Max drawdown |','|---|---:|---:|---:|']
    other=json.loads((ROOT/'reports/momentum_fund_designs_20260919/evaluation_results.json').read_text())
    for key,row in other.items():
        b=row['base'];lines.append(f"| {key} | {b['cagr']:.2%} | {b['excess_sharpe']:.2f} | {b['max_dd']:.2%} |")
    lines += ['','## Forward paper work','','The exact weights and timing are now frozen in [forward_paper_spec.json](forward_paper_spec.json). A registration event is recorded in an append-only paper event file, with zero orders or fills. The expected next scheduled decision is the October 1, 2026 NYSE close, followed by the October 2 open. Calendar/data availability must be checked at execution. No live order was placed, no broker strategy changed, and no background scheduler was started.','','- [All results](results.json)','- [Independent ledger verification](independent_check.json)','- [Uncertainty](uncertainty.json)','- [Equity and drawdown chart](equity_and_drawdown.png)']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for key,label,color in [('momentum_gold','50% SPMO / 50% GLD','#007e80'),('market_gold','50% SPY / 50% GLD','#8e719a')]:
        f=pd.read_csv(OUT/f'{key}_full_base.csv',index_col=0,parse_dates=True);nav=(1+f['return']).cumprod()
        axes[0].plot(nav.index,nav*100000,label=label,color=color,lw=1.8);axes[1].plot(nav.index,(nav/nav.cummax().clip(lower=1)-1)*100,color=color,lw=1.2)
    axes[0].set_title('Fixed equal-weight momentum + gold: net simulated performance',loc='left',fontweight='bold');axes[0].set_ylabel('Value of $100,000');axes[0].legend();axes[1].set_ylabel('Drawdown (%)')
    for ax in axes:ax.grid(alpha=.2)
    fig.text(.09,.015,'Monthly next-open rebalance; 5bps/side; no leverage. Historical simulation on previously researched data.',fontsize=9);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(OUT/'equity_and_drawdown.png',dpi=160)
    print(OUT/'REPORT.md')
if __name__=='__main__':main()
