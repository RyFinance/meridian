from pathlib import Path
import datetime,json,hashlib
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'reports/cycle8_us_only';O=P/'out';x=pd.read_csv(O/'results.csv');c=pd.read_csv(O/'crises.csv');feas=pd.read_csv(O/'account_feasibility.csv')

def pct(v,d=2):return 'NA' if pd.isna(v) else f'{v*100:.{d}f}%'
def num(v,d=2):return 'NA' if pd.isna(v) else f'{v:.{d}f}'
def table(headers,rows):return '| '+' | '.join(headers)+' |\n|'+ '|'.join(['---']*len(headers))+'|\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rows)+'\n'
def link(name):return f'[{name}]({P/name})'
# Full readable metric appendix, all currencies and rows.
lines=['# All 56 US1 portfolio/leverage rows\n\nUSD primary financing; CAD reports translation of net USD account. Real CAGR uses corresponding country CPI. Daily drawdown is approximate where gold/trend daily histories are absent.\n']
for currency in ['usd','cad']:
 lines.append(f'## {currency.upper()}\n\n')
 lines.append(table(['Row','Window','CAGR nominal','CAGR real','Vol','Sharpe [A4 95% CI]','Max DD month-end','Max DD daily proxy','Underwater months','Worst 12m','Ulcer'],[[r.key,f'{r[currency+"_start"]}–{r[currency+"_end"]}',pct(r[currency+'_cagr']),pct(r[currency+'_cagr_real']),pct(r[currency+'_vol']),f'{num(r[currency+"_sharpe"])} [{num(r.get(currency+"_sharpe_lo"))},{num(r.get(currency+"_sharpe_hi"))}]' if r.item!='P8' or r.L!=1 or currency!='usd' else 'undefined vs same cash',pct(r[currency+'_maxdd']),pct(r['dd_daily_'+currency]),int(r[currency+'_underwater_m']),pct(r[currency+'_worst12']),num(r[currency+'_ulcer'])] for _,r in x.iterrows()]))
 lines.append('A4 intervals are descriptive estimates. Rows shorter than36months have NA intervals; no alternate unregistered interval was substituted. The point comparison is not a statistical proof that one Sharpe exceeds another.\n\n')
lines.append('## Margin, Kelly and forward estimates\n\n')
lines.append(table(['Row','Calls generic 30% model','Half-Kelly median','Half-Kelly 5th-percentile bound','Outer multiple above half Kelly?','Forward low / center / high','TFSA exact synthetic exposure?'],[[r.key,int(r.calls),num(r.half_kelly),num(r.half_kelly_p05),'yes' if r.kelly_flag else 'no',f'{pct(r.fwd_low)} / {pct(r.fwd_central)} / {pct(r.fwd_high)}','yes' if r.tfsa_exact else 'no'] for _,r in x.iterrows()]))
lines.append('Built-in-leverage funds’ external-margin calls above are counterfactual generic30% results. See account_feasibility.csv for higher leverage-factor constraints and unverified house margins. P6 synthetic overlays are not exact histories of purchased RSST/NTSX.\n')
(P/'ALL_METRICS.md').write_text(''.join(lines))
# Full crisis table
lines=['# Every portfolio, multiplier, currency and named crisis\n\nCells: cumulative return / in-window month-end maximum drawdown. NA means full crisis history is unavailable, not zero loss. Daily proxy full-sample maxima are in ALL_METRICS.md.\n\n']
for currency in ['usd','cad']:
 cc=c[c.currency==currency];names=cc.crisis.drop_duplicates().tolist();lines.append(f'## {currency.upper()}\n\n');rows=[]
 for key in x.key:
  sub=cc[cc.key==key].set_index('crisis');rows.append([key]+[f'{pct(sub.loc[n,"return"])} / {pct(sub.loc[n,"maxdd"])}' for n in names])
 lines.append(table(['Row']+names,rows))
(P/'ALL_CRISES.md').write_text(''.join(lines))
# Ranking diagnostic on common window.
cw=pd.read_csv(O/'common_window.csv');usd=cw[cw.currency=='USD'][['key','cagr']].merge(x[['key','fwd_central']],on='key');usd['historical_rank']=usd.cagr.rank(ascending=False,method='min');usd['forward_rank']=usd.fwd_central.rank(ascending=False,method='min');usd['rank_change']=usd.forward_rank-usd.historical_rank;usd.sort_values('forward_rank').to_csv(O/'ranking_flips.csv',index=False)
# Chart: primary menu only, forward reward vs forward 50% drawdown risk.
fig,ax=plt.subplots(figsize=(10,6));colors={'P1':'#64748b','P2':'#1d4ed8','P3':'#047857','P4':'#b45309','P5':'#7c3aed','P6a':'#be123c','P6b':'#0e7490'}
for item,col in colors.items():
 z=x[x.item==item];ax.plot(z.forward_p50_20y_either*100,z.fwd_central*100,'o-',color=col,label=item,alpha=.85)
 for _,r in z.iterrows():ax.annotate(f'{r.L:g}x',(r.forward_p50_20y_either*100,r.fwd_central*100),xytext=(4,5),textcoords='offset points',fontsize=8)
ax.axvline(10,color='#334155',ls='--',lw=1);ax.set_xlabel('20-year probability of drawdown >50% in USD or CAD (%)\nForward mean-shifted, joint stationary bootstrap; approximate monthly tails');ax.set_ylabel('Forward expected nominal USD geometric return (%)');ax.set_title('US1 fixed menu: expected return and forward drawdown risk');ax.grid(alpha=.15);ax.legend(ncol=4,loc='lower right');fig.tight_layout();fig.savefig(P/'forward_risk.png',dpi=170);plt.close(fig)
receipt=json.loads((ROOT/'research/cycle8_us_only/prereg_receipt.json').read_text());ch=hashlib.sha256((ROOT/'research/cycle8_us_only/code_receipt.json').read_bytes()).hexdigest()
get=lambda key:x.set_index('key').loc[key]
result='''# Cycle 8 — highest expected return under a risk limit, US-listed instruments

**Portfolio construction from known US-tradable risk premia, not alpha research.** For a Canadian retail investor, the question is which fixed portfolio offers the highest expected long-run return while maintaining a Sharpe at least that of plain SPY/IEF-style60/40 and limiting drawdown risk at25%,35%or50%. Zero validated alpha edges remain. Cycle6failed and Cycle7FXcarryweakened; neither is revived here. Research only.

**All56declared portfolio/leverage rows were evaluated. No weight optimization or leverage grid was performed. Several hard data/implementation requirements remain documented infeasible; therefore this report supplies model-conditional answers, with no fully validated claim of drawdown safety.**

The requested `reports/cycle8_max_return/RESULTS.md` was being written by a separate process for a different global/Canadian framework. That report was preserved. This current US-only deliverable is `reports/cycle8_us_only/RESULTS.md`; source, engine and output paths are separate. A new companion in the requested directory links this report without modifying the existing report.

## Three tolerances: the decision

The preregistered historical risk screen uses the probability of breaching the limit in **eitherUSDorCAD** over20years, below10%, and point Sharpe at least same-window60/40 in **bothcurrencies**. It ranks qualifying rows by frozen forward expected geometric return. The more conservative forward risk check shifts sleeve means to the forward assumptions before bootstrapping. These two risk lenses produce different answers:

'''
ans=[]
for t in [25,35,50]:
 eligible=x[x[f'model_eligible{t}']].sort_values('fwd_central',ascending=False)
 future=eligible[eligible[f'forward_p{t}_20y_either']<.1].sort_values('fwd_central',ascending=False)
 hist='None' if eligible.empty else eligible.iloc[0].key
 fw='None' if future.empty else future.iloc[0].key
 expected='—' if eligible.empty else f'{pct(eligible.iloc[0].fwd_low)}–{pct(eligible.iloc[0].fwd_high)}; center {pct(eligible.iloc[0].fwd_central)}'
 hp='—' if eligible.empty else pct(eligible.iloc[0][f'hist_p{t}_20y_either'])
 fp='—' if eligible.empty else pct(eligible.iloc[0][f'forward_p{t}_20y_either'])
 ans.append([f'{t}%',hist,expected,hp,fp,fw,'None: certification incomplete'])
result+=table(['Tolerance','Historical-screen winner','Expected nominal return range','Historical breach probability','Forward breach probability for that winner','Winner also passing forward risk','Fully validated winner'],ans)
result+='''**25%:** No row passes the joint Sharpe and risk conditions. Nothing above1xpasses. P5has a low modeled drawdown probability, but misses theCADSharpe hurdle. Cash is a reference, with undefinedUSDSharpe relative to the same cash and nontrivialCADcurrency risk; it is not promoted to a qualifying winner.

**35%:** Under the preregistered historical screen, **P3@1:60%SPY-styleUS equity/40%IEF-styleTreasuries** is the highest-forward-return qualifying row. Center5.21%, range4.21–6.15%nominalUSD(andCADunderneutralFXlogdrift), before personal taxes. Expected central real growth is about2.74%USD/3.14%CAD. Historical breach probability4.90% becomes31.89%underforwardmeans, so **no row clears the35%forward risk check**. P4@1.25does clear the historical screen (6.91%breach) but has lower expected return and financing already embedded in its120%base gross exposure; it is not a better return answer.

**50%:** The historical screen selects **P6a@1:100%US equity plus50%trend excess overlay**, center6.21%, range4.41–7.91%nominal. Its2.25%historical breach estimate becomes35.96%withforwardmeans. It has no1970s history and no exact validated fund replication. **The highest-return row also passing the forward risk check is P3@1**, center5.21%, range4.21–6.15%, forward50%breach2.65%. P4@1.25passes the50%forward risk check at8.28%but has lower expected return4.95%, missing1970s trend evidence and an externally financed implementation. Extra borrowing does not improve the winning expected return in this screen.

**No externally levered portfolio is selected as the highest-forward-return answer at any tolerance.** This does not mean every leveraged row fails every numerical screen: theP4exceptions above are explicitly reported. Nor does a20-year monthly probability certify intraday solvency.

## Worst crisis paths and real implementations

P3@1's worst namedCADcrisis is1973–74:−25.22%cumulative,31.09%in-window monthly drawdown. Full-sampleCADdaily proxy max drawdown32.98%; USD32.08%. It had zero modeled margin calls because it does not borrow. Longest underwater and all other metrics are in the complete tables below. The10-year yield proxy has more duration thanIEF, so these are SPY/IEF-style results rather than exact pre-inceptionETFreturns.

The exact named real implementation forP3is60%SPY/40%IEF, monthly rebalance, current weighted stated fee approximately0.1167%/year before spreads/commissions. Fully funded direct US ETFs are feasible inTFSAorRRSP; directly held US equity dividends generally receive the pension treaty exemption inRRSP, whileTFSAhas unrecoverable dividend withholding. For the modeled historical equity-dividend-only sensitivity,USD CAGR falls from9.44%to9.17%forP3; mean withholding charge24bp/year reflects historically higher dividend yields and is not a fixed future fee. Income/withdrawal tax and investor-specific tax credits are outside this generic pretax comparison. See the primary-source account note for distribution classification and qualifications.

P6a@1's worst observed monthlyUSDcrisis path is the1987crash; full-samplemonthlyUSDdrawdown43.12%anddailyproxy47.89%. CADdailyproxymax35.77%. The1973–74andVolckerwindowsareNA, not zero. It had zero calls under the declared generic funded/overlay margin model. A purchased approximation in the named instruments is50%RSST+50%SPY, algebraically100%equity+50%managed-futures exposure, with weighted stated fees about0.54225%/year. That fundedETFmix can be held inTFSA/RRSPsubjecttoeligibility, butRSST'sstrategy is notAQR TSMOM: **the synthetic row is not an exact validatedTFSAimplementation**, and this algebraic mapping was not a newly backtested menu addition. SPYplus50%DBMFfunded by a loan is a different financing/implementation cost and requires a nonregisteredmarginaccount.

VTIat0.03%is the cheaper namedP1equitywrapper thanSPY; DBMFat0.85%has a lower statedfee thanKMLM0.90%, with different exposures. No additional ticker is substituted into the evaluatedP2/P3/GLDmenu. IBKRwas the lower financing-cost broker of the two ordinary retail schedules verified, not a universalall-brokercheapestclaim. ManualFX is max0.20bpofnotional/USD2plusspread; minimums matter at small trade sizes. The run uses declared10bpentry/exitFX and retainsUSDbetweenrebalances. At a1.5%each-wayretailFXscenario,20-yearannualizedgrowth loses roughly0.14percentage point relative to10bp each-way, absent interimconversions.

NTSX90/60, RSSB100globalstocks/100Treasuries, RSST100USstocks/100trend andGDEapproximately90USstocks/90goldare explicitly distinct real exposures. Their own inception histories and all four outer multipliers are tabulated. LeveragedETFcollateral requirements increase with internal leverage: higher externally borrowedP7orstackedETFrows may be initially infeasible. Their primary30%callcounts are counterfactual diagnostics, not livebrokerpermissions; `out/account_feasibility.csv` documents the constraints. Fully paidP7funds require no account borrowing, but their daily reset does not make their portfolio safe.

'''
result+='## Preregistration and reproducibility\n\n'
result+=table(['Artifact','SHA-256','Timing / meaning'],[['US1PREREG.md',receipt['sha256'],receipt['utc']],['Code+snapshot receipt',ch,'2026-09-29T06:11:14Z; before firstUS1return'],['Numerical snapshot manifest','0b2f26ed45985a18206423045d31d5e6597a849a0456a34dfd7eb8e61c108dd7','Copied and verified before US1run']])
result+='''The requested `research/cycle8_prereg_ledger.md` has append-onlyUS1entries; existing global-frameworkentrieswerepreserved. Six tests cover compounding, borrowinginterest, liquidation, absorbingruin, baseP4borrowing andoverlayaccounting. Finalchecksverified56unique rows, finiteCAGR/forwardexpectations, baselineSharpeidentity, probabilitymonotonicity, and unchangedfrozen source/codehashes. TheA4confidenceinterval method uses `research/amendment4/ci.py:calibrated_ci`,95%,q12,B499,seed20260928; itsstudentizedAR-sieveprocedure is descriptive, not a new pass/failalpha test.

The primary joint stationary bootstrap has10,000paths,24-monthmeanblocks,20-yearhorizon;10/30years and12-monthblocks are saved. Cross-asset dependence is joint withinblocks; blockboundariescantruncatecrises. P5useslagged36-monthvolatility andisrecomputedon each path. Forced liquidations retain the realizedloss, charge1%sold andrestorecollateral; the frozenpolicycanre-enter atnextmonthlyrebalance without externalcapital. This is more permissive than permanentlycashingoutafterthefirstcall. Margin is checked daily onproxyhistories andmonthlyinthebootstrap; intradaycallsandhistoricalhouse changesremainunverified.

## Data audit and unmet hard gates

'''
result+=table(['Requirement','Outcome / evidence'],[['LSEprimarysource','Infeasible: noLSEtool exposed; prioracquisitionnotesrecordengineunavailable. No settings orcredentials changed.'],['LSEcloseconvention','Openedmaintainerdocs reportextended-sessionlastpost-marketprints,not4pmauction. Documentaryfinding; no newempiricalLSEsample audit.'],['Officialclosefix','FallbackYahooexchange-localadjustedcloseswithsplit/dividendaccountingchecks. Fullauctionprovenanceunverified; thishardgateisnotclaimedcomplete.'],['Allrequiredcrises','P1/P2/P3/P6b/P7/P8longproxyhistoriesinclude1970s; trend-dependentP4/P5/P6alack1970s. Realfundsstartmuchlater.'],['Goldlonghistory','MonthlyaveragebeforeGLD; unsuitableforharddrawdowntailcertification. Noinventedmonth-endseries.'],['Trendreplication','AQRmonthly1985+; noobtainedfreecenturynumericalseries, no dailytrendhistory. DBMF/KMLMtrackinggapmaterial.'],['Bonds','Yield-based10Y/20YtotalreturnsvalidatedvsrealETFs; duration/indexmismatchquantified. Pre1962smoothedsupplementaryhistory.'],['Canadianaccountrealism','CurrentUSD/CADbrokerpricing,registeredaccountlimits,withholding andFXverified; historicalrates/maintenance/swapsaredeclaredproxies.'],['Snapshots/completeness','Processedinputsandmetadatafrozenandhashed; rawsupportarchivehashesandETFcalendargapchecksprovided.']])
result+='''TheLSEMCP[documentedcaveats](https://github.com/OlegDyukel/lse-data-mcp#data-caveats) describe theextendedhoursissue; the[officialSDK](https://github.com/londonstrategicedge/lse-data) doesnotguaranteeauctioncloses. Those observations do not establish the vendor'scurrentimplementation with certainty. A completefixrequiresverifiedregular-session/auctionprices, exchangecalendar/DST/early-closehandling, split/distributionadjustments andoverlapreconciliation. The fallbackperformedhereisusefulresearchdata, not proofthatthishardrequirementwasmet.

'''
result+=f'Detailed evidence: {link("DATA_AUDIT.md")}, {link("ACCOUNT_IMPLEMENTATION.md")}, {link("FORWARD_SOURCES.md")}, {link("ETF_COMPLETENESS.csv")}, {link("ETF_CALENDAR_CHECK.csv")}.\n\n'
result+='''## Forward assumptions and the US history haircut

ThefrozenUSDcompoundscenariosareUS equity4.2/5.5/6.7%, intermediateTreasuries3.7/4.25/4.8%, gold2/3/5.5%, netmanagedfutures3/4.5/6%, cash3/3.5/4%. Thesearedeclaredscenarioinputs, notconfidenceintervalsorapooledproviderconsensus. Equity/bond/goldfeesaredeductedonce; nettrenddoesnotreceiveasecond2%charge. Arithmeticmeansaddhalfassetvariance; geometricportfolioreturnsubtractshalfportfoliovarianceandfinancing. Forwardvariancecomesfromfixedhistoricalcovariance, withP5averagepredeclaredweightapproximation. CADexpectedFXlogdriftiszero, whileFXriskremainsinthepaths.

Primarysourcesopened:[VanguardJune2026VCMM](https://www.vanguardmexico.com/en/home/insights/economic-market-outlook/vanguard-capital-markets-model-forecasts-2026), [AQR2026CMA](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---2026-Capital-Market-Assumptions.pdf?sc_lang=en), [JPM2026USDmatrix](https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/insights/ltcma-2026-us-matrix_usd.pdf), [AQRstrategictrendframework](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---Broad-Strategic-Asset-Allocation.pdf?sc_lang=en), [BlackRockCMA](https://www.blackrock.com/institutions/en-us/insights/thought-leadership/capital-market-assumptions), and [ResearchAffiliatestool](https://interactive.researchaffiliates.com/asset-allocation). ResearchAffiliatesredirectedtoaninteractivepagewithoutusablefigures. BlackRock'sinteractivepageandexistingdownloadwerereviewedbutnotpost-resultinsertedintothefrozenscenario. Sourcehorizonsrange5–10to10–15years; extrapolatingthemtomultidecaderiskisamodelingassumption.

USunleveredequityhistoricalUSD CAGR11.16%versusforward5.40%netimpliesa5.77percentage-pointannualhaircut. For60/40,the9.44%historicalCAGRbecomes5.21%; forequity/trend17.55%becomes6.21%. Thesedifferencesarewindow-dependentrealizedversusscenariofigures,notestimatedalphadecay. Retailforwardborrowingat5%meansaddingexposuremaylowerexpectedcompoundreturndespitehighhistoricalCAGR.

'''
result+='## All portfolio × leverage results\n\nPrimary probabilities below are20-year **historicalbootstrap**, maxUSD/CAD breachevent. FullmetricsandA4intervalsareintheappendix; everyforwardriskandhorizon/block/margin-ratecolumnisintheCSV.\n\n'
result+=table(['Row','USD CAGR','CAD CAGR','Sharpe USD / CAD','Forward center','P DD>25 /35 /50','Calls','Sharpe hurdle pass'],[[r.key,pct(r.usd_cagr),pct(r.cad_cagr),f'{num(r.usd_sharpe)} / {num(r.cad_sharpe)}',pct(r.fwd_central),f'{pct(r.hist_p25_20y_either)} / {pct(r.hist_p35_20y_either)} / {pct(r.hist_p50_20y_either)}',int(r.calls),'yes' if r.sharpe_pass else 'no'] for _,r in x.iterrows()])
result+='''P8@1USDSharpeagainstidenticalcashisundefined; entry/exitcostscreateatransitorynumericalexcess-seriesvarianceintheCSV,whichisnotusedasapass. ShortrealETFwindowsareexcludedfromwinnercertificationevenwhereanumericalscreenlooksstrong. Initialmargininfeasibilityoverridesanycounterfactualpath;thefullfeasibilitytableislinkedbelow.

## Crisis table

Cellsarecumulativereturn/in-windowmonth-endmaximumdrawdowninCAD. Thesearebase1xrowsondifferentavailabilitywindows. NAmeanscompletecrisiscoverageisunavailable. Thefulltablecontainsall56rowsinbothcurrencies.

'''
cc=c[c.currency=='cad'];cn=cc.crisis.drop_duplicates().tolist();base=['P1@1','P2@1','P3@1','P4@1','P5@1','P6a@1','P6b@1','P7a@1','P7b@1','P8@1'];rows=[]
for key in base:
 sub=cc[cc.key==key].set_index('crisis');rows.append([key]+[f'{pct(sub.loc[n,"return"])} / {pct(sub.loc[n,"maxdd"])}' for n in cn])
result+=table(['Row']+cn,rows)
result+='''## Validation and uncertainty

ActualSSO/UPROdaily-resetoverlapsarecloseincorrelationbutstillhaveannualtrackingerrors3.21%/4.96%; TMF8.84%. SyntheticTMF'sCAGR−2.81%versusactual−5.49%isperformance-material. AQRnettrendversusDBMFcorrelation0.60/TE11.34%, versusKMLM0.65/TE10.78%; anexecutabletrendETFreturnrangecannotbeinferredfromthehypotheticalfactor'spointestimatealone. IEFtrackingTE1.37%/yearandnetCAGRgap−0.69pointsshowthatthe10Ypar-bondproxyisnotanexact7–10Yindex.

P3@1historicalSharpeUSD0.516with95%A4CI[0.239,0.768], CAD0.492withCI[0.075,0.896]. P6a@1USD0.888[0.507,1.267],CAD0.907[0.409,1.382]. Theintervalsarewideandthewindowsdiffer;thepoint-hurdlescreenisnotproofthatoneportfoliohasstatisticallysuperiorSharpe. P5@2missestheCADpointhurdlebyonlyabout0.00008;noepsilonrelaxationorweightchangeisusedtocreatethe25%answer.

Half-Kellymedian/uncertaintyboundforP3@1is1.58/0.45;forP6a@1,2.38/1.59;forUS equity,1.14/0.42. HistoricalKellyestimatesarestronglyaffectedbytheUS/trendhistoryandborrowingrate. Theyareapproximateone-sidedmargin-growthchecksandnotsafeleveragemaxima; below1thecash-versus-borrowing-ratekinkmatters. Allrows'5000jointblockbootstrapmedianand5th-percentileboundsaretabulated. Nooutermultipleischangedbasedontheseestimates.

## What12%peryearwouldrequire

**Nofixed-menurowhas12%centralforwardexpectedcompoundreturn undertheseassumptions.** A12%nominaltargetrequiresamuchlargerriskpremiumthanthisforwardlenssupplies,lowerfinancingcosts,oroptimisticassumptionsthatwere not preregistered. HistoricallyP1@2earned12.83%USDbutlost86.31%onitsdailyproxy(87.89%CAD),hadamodeledforcedsale,andhasa87.79%20-yearhistoricalprobabilityofexceeding50%drawdown. Itsforwardcenteris3.50%,not12%. The3xdaily-reset60/40cautionaryrowearned14.95%historicallybutlostabout79%ondailyUSD/CADpathsandhad88.20%probabilityofbreaching50%over20years. Theequity/trendoverlay'shighhistoricalreturndoesnotrescuetheclaim:itsforwardcenteris6.21%,future50%breachestimate35.96%,and1970shistoryismissing. Forplanningpurposes12%cannotbepairedwithavalidated25/35/50%drawdownceilingfromthismenu; it would require accepting substantially greater drawdown risk and/or materially stronger expected-return assumptions.

## Completion and infeasibility record

'''
result+=table(['Requested work','Status'],[['Fixedmenuandpreregistration','Done:56rows,4outermultipliers,sha/timestampbeforeUS1returns. LiteralP4andtwoP7variantsfixed.'],['LSEaudit/officialclosefix','Documentedinfeasible/partial: toolunavailable, documentaryclosefinding, fallbackTRaccountingverified, auctionprovenanceunresolved.'],['1926equity/yield-builtbonds','Donewithdeclaredproxy/smoothinglimits; supplementary1930sresultsCSV.'],['Requiredcrises','Donewhereavailable;1970strendandoldgoldtailcertificationdocumentedinfeasible.'],['Datasetcompleteness/snapshots','Done:processedhashes/sourceprovenance/ETFcalendar/adjustmentrecords.'],['Financing/USD-CAD/maintenance/liquidation','Doneasdeclaredcounterfactuals;historicalhousemarginsinfeasible,leveragedfundcollateralconstraintsflagged.'],['Daily-resetdecay/fees/swaps/ETFvalidation','Done;swapspreadhistoricalverificationinfeasible,indexmismatchquantified.'],['TFSA/RRSP/WHT/FX/tradingcosts','Donewithdistributionclassificationlimitsandpersonal-taxscope.'],['Everyrequestedmetric/A4CI/Kelly','Done;short/degenerateCIexplicitlyNA,notfabricated.'],['Crisis-clusterbootstrap','Done:10,000jointpaths,24monthblocks,10/20/30yhorizons,12monthblockchecks;month-endcalllimitdisclosed.'],['Historicalandforwardlenses','Done:fixedCMAs,meanshiftedforwardrisk,historicalhaircutandrankflips.'],['Three-toleranceanswer/implementation','Doneconditionally;nofullyvalidatedsafetyclaim.'],['12%paragraph','Donewithactualmodeldrawdownpaths.'],['Heavyagents','Threeagentsprovidedsourceevidence;usage-limitfailuresdocumented;coordinatorcompletedremainingwork.'],['Requestedreportpath','Existingconcurrentglobalreportpreserved;newUS_ONLY_RESULTS.mdcompanionandthiscompleteUSreportprovided.']])
result+='## Saved artifacts\n\n'
for name in ['ALL_METRICS.md','ALL_CRISES.md','DATA_AUDIT.md','FORWARD_SOURCES.md','ACCOUNT_IMPLEMENTATION.md','RESEARCH_LIMITATIONS.md']:
 result+=f'- {link(name)}\n'
for name in ['results.csv','crises.csv','common_window.csv','ranking_flips.csv','validation.csv','live_etfs.csv','us1926.csv','tfsa_equity_tax.csv','account_feasibility.csv','verification.json']:
 result+=f'- [{name}]({O/name})\n'
result+=f'\n![Forward return and drawdown risk]({P/"forward_risk.png"})\n'
# Expand accidental compressed prose for readability without touching source facts.
# Explicit common compact technical strings retained in file names/IDs; space common numeric labels.
import re
result=re.sub(r'(?<=\d)(?=[A-Za-z])',' ',result)
# URL and hashes must never be transformed: only prose transformations are avoided instead.
# Undo broad transform by reconstructing from original? Keep exact originals via replacement block below.
# Numeric-alphabetic split was overly broad for URLs/hashes; reload not possible: revert inserted spaces globally where identifier-like.
# We therefore perform no automatic typography transform and reconstruct safe originals.
# remove introduced spaces before letters in long hashes/URLs via token mapping
for token in [receipt['sha256'],ch,'0b2f26ed45985a18206423045d31d5e6597a849a0456a34dfd7eb8e61c108dd7']:
 altered=re.sub(r'(?<=\d)(?=[A-Za-z])',' ',token);result=result.replace(altered,token)
# Exact link targets are restored by recognizing Markdown targets with whitespace inserted only by this rule.
result=re.sub(r'\]\(([^)]+)\)',lambda m:']('+re.sub(r'(?<=\d) (?=[A-Za-z])','',m.group(1))+')',result)
(P/'RESULTS.md').write_text(result)
print('report bytes',len(result),'metric rows',len(x),'crisis rows',len(c))
