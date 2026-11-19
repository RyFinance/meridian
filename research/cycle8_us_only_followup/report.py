from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'reports/cycle8_us_only_followup'
o=pd.read_csv(ROOT/'reports/cycle8_us_only/out/results.csv').set_index('key');r=pd.read_csv(P/'correction_risk.csv');d=pd.read_csv(P/'daily_risk.csv');c2=r[r['mode']=='C2'].set_index('key')
def pct(x):return 'NA' if pd.isna(x) else f'{100*x:.2f}%'
def num(x):return 'NA' if pd.isna(x) else f'{x:.3f}'
def table(h,rows):return '| '+' | '.join(h)+' |\n|'+ '|'.join(['---']*len(h))+'|\n'+''.join('| '+' | '.join(map(str,v))+' |\n' for v in rows)+'\n'
def link(name):return f'[{name}]({P/name})'
receipt=json.loads((P/'receipt.json').read_text());sha=hashlib.sha256((P/'receipt.json').read_bytes()).hexdigest();gsha=hashlib.sha256((P/'gold_receipt.json').read_bytes()).hexdigest()
text='''# Cycle 8 continuation — corrections, daily tails and direct LSE audit

**Portfolio construction from known US-tradable risk premia, not alpha research.** For a Canadian retail investor, the objective remains the highest expected long-run return from the fixed US-listed menu, subject to a 60/40 Sharpe hurdle and drawdown tolerances of 25%, 35% or 50%. The owner chooses the tolerance. No new portfolio, ticker substitution, optimized weight or leverage level is introduced. Zero validated alpha edges remain; earlier failed cycles remain spent.

Client date: **October 1, 2026, America/Vancouver**. Some UTC receipts fall on October 2. This is a post-result continuation, not an independent confirmatory experiment. Original US1 code, data snapshots, report and results are preserved.

## What changes the answer, and what does not

The independent audit found a real discrepancy between the expected-return formula and the forward overlay risk simulation. It also showed that month-end drawdown screening misses substantial daily risk. Those defects warranted new, separately frozen calculations. C1 corrects only overlay arithmetic premiums. C2 makes funded and overlay arithmetic means consistent with the declared ranking model, while retaining its approximate half-variance forecast. The daily supplement measures daily losses inside entire jointly sampled asset/FX months.

**The three-tolerance answer survives these checks:** no supported candidate at 25% or 35%; unlevered 60/40 remains the highest-return conditional candidate at 50%. Its corrected daily 20-year breach probability is 3.71%, compared with the original monthly estimate of 2.65%. No fully certified winner is established because official-close provenance, old gold tails, missing early trend history and historical house margin rules remain unresolved.

A third attempted repair used observed London gold fixings from a free historical archive. It produced an apparent 35% candidate, but deeper validation uncovered impossible fixing dates and a suspicious isolated crash/rebound. **C3 is quarantined and excluded from every decision.** A better-looking answer from defective source data is not evidence of a better portfolio.

'''
text+=table(['Tolerance','Supported conditional answer','Expected nominal return','Corrected forward risk evidence','Fully certified answer'],[
 ['25%','None','—','No joint Sharpe/risk pass; P3 daily breach 81.36%','None'],
 ['35%','None','—','P3 daily breach 45.07%; accepted non-P3 rows fail the joint gate','None'],
 ['50%','P3 at 1x: 60% SPY / 40% IEF style','4.21%–6.15%; center 5.21%','Daily breach 3.71%; month-end C2 2.60%','None']])
text+='''These ranges retain the frozen forward ranking assumptions; they are scenarios, not confidence intervals. Neutral expected CAD/USD log drift gives the same nominal growth expectation in both currencies, while currency still changes risk. The 20-year probability concerns drawdown in **either USD or CAD**. The original historical point Sharpe must meet same-window 60/40 in **both currencies**. Daily checks are available for P1/P2/P3; trend-containing C2 risks remain monthly and cannot establish a daily limit. P4 at 1.25x passes the accepted monthly 50% screen, with lower expected return, but is not certified. No externally borrowed row wins the highest-return comparison.

## Unlevered 60/40: daily versus month-end

'''
rows=[]
for _,v in d[d.key=='P3@1'].iterrows():
 for t in [25,35,50]:rows.append([v.lens,f'{t}%',pct(v[f'monthly_p{t}_20y_either']),pct(v[f'daily_p{t}_20y_either']),f'{pct(v[f"daily_p{t}_20y_either_mc_lo"])}–{pct(v[f"daily_p{t}_20y_either_mc_hi"])}'])
text+=table(['Lens','Limit','Month-end risk, same paths','Daily risk','95% Monte Carlo interval for daily estimate'],rows)
text+='''The intervals quantify finite simulation sampling only. They do not cover expected-return uncertainty, structural change, missing crises, source errors or model error. For the 50% forward result, the 95% Monte Carlo interval is 3.36%–4.10%. For 35%, the daily estimate is much larger than 10%. The original historical 35% month-end probability was 4.90%; measuring the same sampled history daily raises it to 8.10%. Lower future expected returns raise the corrected daily figure to 45.07%.

The daily simulation keeps complete observed equity, Treasury and FX paths within each sampled month. Months are drawn jointly with a 24-month mean stationary-block length, using 10,000 paths and the unchanged seed. It discards the same 36-month burn-in and evaluates 240 subsequent months. Portfolio targets reset monthly; margin accrues and is checked daily. Padding slots have zero returns and carry and add no elapsed time. No trend or old gold daily returns are invented in this supplement. Treasury-calendar and FX observation-time approximations remain. Drawdown is close-to-close, not intraday.

## What the model correction fixes

Original central XT expected arithmetic premium was 1.0000% annually in the risk bootstrap, but 1.7730% in the ranking formula. XB was 0.6000% versus 0.8699%, including the bond fee. A 50% overlay therefore had an annual portfolio-mean mismatch of approximately 0.3865 or 0.1350 percentage points at outer 1x. C1 fits those overlay arithmetic targets and leaves other means unchanged. C2 scales primitive gross simple returns to match the ranking's monthly arithmetic mean exactly, and defines each overlay as its corresponding funded sleeve return minus the same forward cash.

'''
rows=[]
for key in ['P3@1','P4@1','P4@1.25','P6a@1','P6b@1']:
 c1=r[(r.key==key)&(r['mode']=='C1')]
 rows.append([key,pct(o.loc[key,'forward_p50_20y_either']),pct(c1.iloc[0].p50_20y_either) if len(c1) else 'not rerun',pct(c2.loc[key,'p50_20y_either']),pct(o.loc[key,'fwd_central'])])
text+=table(['Row','Original forward 50% risk','C1 overlay correction','C2 coherent means','Frozen forward expected return center'],rows)
text+='''Correcting the overlay discrepancy reduces the trend stack's modeled 50% risk slightly, but leaves it far above 10%. The daily C2 60/40 simulation has median realized 20-year CAGR of 5.26%, close to the 5.21% approximate ranking center; this is a model diagnostic, not a new forecast or a confidence bound.

C2 is not exact lognormal mathematics. The original model's variance estimate comes from a common historical window; its annual arithmetic target adds half variance to the geometric scenario, and cash/financing use annual simple rates divided by twelve. The implied geometric sleeve means are saved in moment_checks.csv. The corrected US equity and bond geometric means for the P3 window are approximately 5.43% and 4.12%, respectively. Target-fitting and exact overlay identities pass deterministic checks; remaining approximation is visible rather than silently removed.

## Direct LSE audit: stronger evidence, incomplete repair

The desktop tool inventory still exposes no LSE tool, but the repository's existing read-only stdio bridge successfully reached its already configured Terminal. No configuration or credential was changed. This supersedes the earlier session's availability finding, which remains preserved with its date.

The direct audit sampled three full SPY minute sessions, August 17–19, 2026, and compared them with LSE daily bars and the existing exchange-local ETF series. All sessions extend from 08:00 UTC to 23:59 UTC. In August, 20:00 UTC corresponds to 16:00 Eastern. The daily close exactly equals the final 23:59 UTC minute on all three dates.

'''
la=pd.read_csv(P/'LSE_MINUTE_CLOSE_AUDIT.csv')
text+=table(['Date','Parsed 1-minute bars','LSE daily close','Last 23:59 UTC close','19:59 UTC close','20:00 UTC close','Saved exchange close'],[[v['date'],int(v.bars),f'{v.daily_lse_close:.2f}',f'{v.last_UTC_day:.2f}',f'{v["1559_ET"]:.2f}',f'{v["1600_ET"]:.2f}',f'{v.yahoo_exchange_close:.2f}'] for _,v in la.iterrows()])
text+='''The three-day request advertised 2,820 bars but its text output was truncated at roughly 60,000 characters. The audit therefore reacquired one complete day per request and verified 936, 954 and 930 rows. Reported header coverage alone is not proof of complete delivered data. The history tool's ISO-time example also failed: this provider requires YYYY-MM-DD date arguments. Those failures and successful requests are snapshotted.

For all fourteen named ETFs, an August daily request returned SPY, VTI, GLD and TLT; the other ten reported no candle data. Returned histories contain all 21 SPY calendar dates for the requested completed month. In SPY, 20 of 21 closes differ from the saved exchange close by more than one cent; the largest difference is $4.54. This demonstrates that the vendor daily close cannot be substituted as a regular-session total-return close for this study. A 19:59 or 20:00 minute close also does not uniquely establish the closing auction, so the audit does not claim a completed official-close reconstruction.

The LSE US10Y series was compared with the frozen DGS10 yield source in 1990 and 2026. Median absolute gaps are 0.90 and 0.80 basis points; maximum gaps are 13.20 and 3.00 basis points, with level correlations 0.995 and 0.998. This is useful overlap evidence, but different market-observation conventions and calendar coverage remain. LSE catalog metadata offers US10Y from 1990, insufficient to replace the earlier crisis history. Policy-rate catalog metadata offers a US series from 1971; its target definition must be established before replacing effective FEDFUNDS. No benchmark type was silently substituted.

Current observations are documented in LSE_MINUTE_CLOSE_AUDIT.csv, LSE_ETF_AUGUST_AUDIT.csv and LSE_RATES_AUDIT.json. Every raw reply is archived and hashed. The empirical result is consistent with the [maintainer's earlier caveat](https://github.com/OlegDyukel/lse-data-mcp#data-caveats), but establishes only the sampled SPY convention, not a proof about every asset or vendor revision.

## Failed gold repair: quarantine record

The free [Center for Financial Stability archive](https://www.centerforfinancialstability.org/hfs.php) supplied a March 2015 workbook with daily London AM and PM gold prices and source metadata referring to LBMA. The PM USD extraction contains 10,745 numerical observations from April 1968 through December 2010, no duplicate dates, positive prices and no missing month ends in 1971–2004. Those initial checks were insufficient.

A deeper audit found **584 weekend PM observations**. London fixing benchmarks are not published on weekends, according to the [LBMA pricing documentation](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices). A February 5, 1983 Saturday observation falls from $498.50 to $342.40 and then rebounds to $490.25 on the next observation: approximately −31.31% followed by +43.18%. After 1999, many quotes appear on Tuesday–Saturday, suggesting a calendar alignment problem. The daily overlap with GLD does not reconcile, although level and monthly correlations are high. High level correlation is therefore inadequate for validating daily paths.

C3 was preregistered as a source correction before its portfolio returns. It replaced old monthly-average gold with observed month ends, holding the fixed P4/P5 rules unchanged. It produced a numerical P5 at 1.25x Sharpe pass and a 3.88% forward monthly probability of breaching 35%, with an expected center of 4.52%. **That apparent new 35% answer is rejected because the source failed validation.** The tables are kept only as a failed diagnostic and are prominently listed in GOLD_QUARANTINE.json. No arbitrary weekend removal or one-day shift is accepted without independent primary confirmation.

The official [LBMA historical table](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices) now directs users to licensed portal access. No paid data was purchased or restricted access bypassed. An additional LSE gold-price search returned no commodity price series or XAUUSD instrument. The old gold-tail gate remains unresolved. The [AQR century trend paper](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) describes a longer reconstruction, while its [downloadable TSMOM factor page](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly?aqrPDF=1) explicitly begins in January 1985. A paper figure is not an obtained numerical series; the missing 1970s trend gate remains unresolved.

## Accounts, crises and 12% growth

The supported conditional implementation remains fully paid 60% SPY / 40% IEF, monthly rebalance, with the original approximately 0.1167% weighted fund fee plus declared trading and FX costs. It can be held without account margin in a TFSA or RRSP subject to eligibility. The original withholding and account-source note remains linked; this continuation does not update fee forecasts, assume universal treaty treatment or claim that a generic maintenance calculation is a broker's initial-margin permission.

The exact original worst named CAD 60/40 crisis remains 1973–74: −25.22% cumulative and 31.09% month-end drawdown, with full-sample CAD daily proxy drawdown of 32.98%. The crisis helper has a genuine endpoint-coverage defect: it accepts a series ending before a named crisis ends. A strict consecutive-month endpoint check found **zero affected saved original crisis rows**. The demonstrated bug should be corrected before reuse on partial future windows, but no original crisis result is silently rewritten.

Kelly remains an approximate historical growth diagnostic. It does not authorize the same multiple for portfolios with different embedded gross exposure. Generic 30% maintenance results for leveraged funds are counterfactual, because actual initial/house requirements are unverified. The unlevered candidate avoids that account borrowing issue.

The stronger daily risk evidence further weakens a 12% growth target. In the C2 forward supplement, 2x US equity has a 97.94% probability of exceeding 50% drawdown over twenty years, and 2x 60/40 has 73.49%. Their original forward return centers are 3.50% and 4.53%, respectively, not 12%. Higher leverage does not supply a 12% central expected return under the frozen retail-financing assumptions. The old historical examples with roughly 80%–90% losses remain relevant; no accepted correction pairs a 12% expected return with a validated 25%, 35% or 50% ceiling.

## All corrected monthly rows

These are C2 central forward probabilities, before applying the historical Sharpe hurdle and certification exclusions. The original forward expected-return centers are retained for comparison. Cash's Sharpe against itself is undefined, P7 remains cautionary, and short actual fund histories remain excluded from winner certification. A tiny risk number from RSSB's short history is not accepted evidence of long-run safety.

'''
text+=table(['Row','Original forward center','C2 P(DD>25%)','C2 P(DD>35%)','C2 P(DD>50%)','Original joint Sharpe pass'],[[key,pct(o.loc[key,'fwd_central']),pct(v.p25_20y_either),pct(v.p35_20y_either),pct(v.p50_20y_either),'yes' if o.loc[key,'sharpe_pass'] else 'no'] for key,v in c2.iterrows()])
text+='## All daily-risk rows\n\n'
text+=table(['Row','Lens','Daily P25','Daily P35','Daily P50','Month-end P50, same paths','Mean calls over 20 years'],[[v.key,v.lens,pct(v.daily_p25_20y_either),pct(v.daily_p35_20y_either),pct(v.daily_p50_20y_either),pct(v.monthly_p50_20y_either),num(v.calls_mean20)] for _,v in d.iterrows()])
text+='''## Receipts, verification and limitations

'''
text+=table(['Artifact','UTC receipt','SHA-256'],[['C1/C2/daily preregistration and code receipt',receipt['utc'],sha],['C3 gold repair receipt',json.loads((P/'gold_receipt.json').read_text())['utc'],gsha]])
text+='''C1/C2 evaluated 64 correction rows: eight minimal overlay corrections and all 56 coherent-mean rows. The daily supplement evaluated 24 combinations: three portfolios, four leverage levels, two lenses, each with 10,000 paths. C3 evaluated eight gold-dependent combinations; all are quarantined for source failure. A default interpreter lacked numba for C3 intervals; rerunning with the existing project virtual environment completed the unchanged code. No environment settings or system packages were modified. A workbook reader was installed only in the new follow-up directory to inspect the free archive.

Checks passed for exact arithmetic means, overlay identity, source month-end anchoring, joint asset/FX indexing, threshold and horizon probability monotonicity, daily drawdown at least month-end drawdown on the same paths, matching P3 at 1x month-end probabilities against the original and C2, strict saved crisis coverage, and unchanged frozen receipt files. Original code and numerical snapshot hashes are verified again. These verify calculation consistency, not model truth.

Three subagents were dispatched. One returned the overlay inconsistency before all three hit usage limits. The coordinator reproduced it independently and completed the computations and audit. Unavailable evidence remains unavailable; usage limits do not justify accepting incomplete gates.

'''
text+='## Artifacts\n\n'
for name in ['AUDIT_MODEL.md','correction_risk.csv','daily_risk.csv','moment_checks.csv','verification.json','receipt.json','LSE_MINUTE_CLOSE_AUDIT.csv','LSE_ETF_AUGUST_AUDIT.csv','LSE_DAILY_CLOSE_COMPARISON.csv','LSE_RATES_AUDIT.json','GOLD_QUARANTINE.json','GOLD_WEEKEND_FLAGS.csv','GOLD_1983_BAD_PRINT.csv','gold_overlap.json','gold_receipt.json']:
 text+=f'- {link(name)}\n'
text+=f'- [Original complete US1 results]({ROOT/"reports/cycle8_us_only/RESULTS.md"})\n- [Frozen follow-up protocol]({ROOT/"research/cycle8_us_only_followup/PREREG.md"})\n'
# Shared comparative chart: no new portfolios or smoothed trials.
fig,axes=plt.subplots(1,2,figsize=(12,5));labels=['25%','35%','50%'];u=d[(d.key=='P3@1')&(d.lens=='C2')].iloc[0];z=o.loc['P3@1'];b=c2.loc['P3@1'];idx=np.arange(3);width=.25
for j,(lab,vals,col) in enumerate([('Original monthly',[z[f'forward_p{t}_20y_either'] for t in [25,35,50]],'#94a3b8'),('Corrected monthly',[b[f'p{t}_20y_either'] for t in [25,35,50]],'#0891b2'),('Corrected daily',[u[f'daily_p{t}_20y_either'] for t in [25,35,50]],'#4338ca')]):
 axes[0].bar(idx+(j-1)*width,np.array(vals)*100,width,label=lab,color=col)
axes[0].set_xticks(idx,labels);axes[0].set_title('Unlevered 60/40: measuring drawdown daily');axes[0].set_ylabel('20-year breach probability, USD or CAD (%)');axes[0].axhline(10,color='#be123c',ls='--');axes[0].legend(fontsize=8);axes[0].set_ylim(0,100)
z=d[d.lens=='C2']
for item,col in [('P1','#64748b'),('P2','#0891b2'),('P3','#4338ca')]:
 v=z[z.key.str.startswith(item+'@')];axes[1].plot([float(k.split('@')[1]) for k in v.key],v.daily_p50_20y_either*100,'o-',label=item,color=col)
axes[1].set_title('Daily probability of exceeding 50% drawdown');axes[1].set_xlabel('Fixed outer leverage');axes[1].set_ylabel('20-year breach probability (%)');axes[1].axhline(10,color='#be123c',ls='--');axes[1].set_ylim(0,100);axes[1].set_xticks([1,1.25,1.5,2]);axes[1].legend()
for ax in axes:ax.grid(axis='y',alpha=.15)
fig.suptitle('Cycle 8 follow-up: corrected forward assumptions, joint 10,000-path bootstrap');fig.tight_layout();fig.savefig(P/'daily_risk_comparison.png',dpi=160);plt.close(fig)
text+=f'\n![Daily risk comparison]({P/"daily_risk_comparison.png"})\n'
(P/'RESULTS.md').write_text(text)
companion=ROOT/'reports/cycle8_max_return/FOLLOWUP_2026-10-01.md'
if not companion.exists():companion.write_text(f'# Cycle 8 US-only follow-up — October 1, 2026\n\nThe complete [correction and daily-risk report]({P/"RESULTS.md"}) preserves the original fixed menu. The supported conditional answers remain none at 25%/35% and unlevered 60/40 at 50%. Corrected daily forward 50% breach probability is 3.71%; no fully certified result is claimed.\n\nThe direct LSE sample empirically identifies an extended-session daily close. An attempted historical gold repair failed validation and is quarantined. All original reports are preserved.\n')
print('report_bytes',len(text.encode()))
