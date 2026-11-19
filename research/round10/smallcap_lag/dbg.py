from core import *
p=P['ATKR']; print(p.index[:5], p.index.to_series().diff().dt.days.value_counts().head(8))
print(p.loc['2024-05-25':'2024-06-10'][['O','c1030','o1030','Cl']])
print(p.loc['2025-06-01':'2025-06-10'][['O','c1030','o1030','Cl','gap']])
print(p.loc['2026-02-01':'2026-02-10'][['O','c1030','o1030','Cl','gap']])
