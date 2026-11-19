import pandas as pd
d=pd.read_pickle('cache/ATKR_1d.pkl'); print(len(d), d.index[-3:]); 
d=d.loc['2025-06-01':'2025-06-12']; print(d)
h=pd.read_pickle('cache/ATKR_60m.pkl'); h.index=h.index.tz_convert('America/New_York'); print(h.loc['2025-06-05':'2025-06-09'].iloc[:20])
