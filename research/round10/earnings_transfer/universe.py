CLUSTERS = {
 'big_banks': 'JPM BAC C WFC GS MS',
 'regional_banks': 'PNC USB TFC FITB KEY RF HBAN CFG MTB ZION CMA',
 'custody_banks': 'STT BK NTRS',
 'brokers_am': 'SCHW BLK RJF LPLA IBKR',
 'airlines': 'DAL UAL AAL LUV ALK JBLU',
 'railroads': 'UNP CSX NSC',
 'homebuilders': 'DHI LEN PHM NVR TOL KBH TMHC MTH',
 'semis_analog': 'TXN ADI MCHP ON NXPI SWKS QRVO',
 'semis_digital': 'NVDA AMD INTC AVGO QCOM MU MRVL',
 'semis_equip': 'AMAT LRCX KLAC TER',
 'payments': 'V MA PYPL FIS GPN AXP',
 'consumer_fin': 'COF SYF AXP ALLY',
 'big_pharma': 'PFE MRK JNJ LLY ABBV BMY AMGN GILD',
 'oil_services': 'SLB HAL BKR NOV FTI WFRD',
 'big_oil': 'XOM CVX COP OXY',
 'retail_mass': 'WMT TGT COST DG DLTR BJ KR',
 'home_improve': 'HD LOW TSCO FND',
 'restaurants': 'MCD SBUX CMG YUM DRI QSR DPZ WING TXRH',
 'trucking_freight': 'ODFL JBHT KNX SAIA XPO CHRW WERN ARCB UPS FDX',
 'staples_food': 'PG KO PEP MDLZ CL KMB GIS KHC PM MO CPB CAG HSY HRL SJM',
 'managed_care': 'UNH ELV CI HUM CVS CNC MOH',
 'telecom_cable': 'T VZ TMUS CMCSA CHTR',
 'autos': 'GM F',
 'defense': 'LMT NOC GD RTX LHX',
 'industrials': 'GE HON MMM CAT DE EMR ETN',
 'insurers': 'TRV CB PGR ALL AIG MET PRU',
 'medtech': 'ABT ISRG SYK BSX MDT TMO DHR',
 'chemicals': 'DOW LYB DD LIN APD SHW PPG',
}
CLUSTERS = {k: v.split() for k, v in CLUSTERS.items()}
ALL = sorted({t for v in CLUSTERS.values() for t in v})
MEGA = set('JPM BAC C WFC GS MS V MA AXP PYPL NVDA AMD INTC AVGO QCOM TXN MU AMAT LRCX PFE MRK JNJ LLY ABBV BMY AMGN GILD WMT TGT COST HD LOW MCD SBUX PG KO PEP MO PM XOM CVX COP UNH CVS T VZ TMUS CMCSA GM F LMT RTX GE HON CAT UPS DE BLK SCHW ABT MDT TMO ISRG DAL UAL UNP CSX MDLZ CL SLB COF ELV CI ADI KLAC'.split())
THIN = set('JBLU ARCB WERN TMHC MTH NVR FND TXRH WING WFRD CMA ZION QRVO CHX FTI KBH SAIA KNX'.split())
def side_cost(t):  # per-side cost in return units
    return 0.0002 if t in MEGA else (0.0010 if t in THIN else 0.0005)
