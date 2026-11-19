"""Quantify a timing bug in shares_mgmt/sim.py: for 'time' exits, the exit price is O[k] even when the
entry e is after k (so the exit is BEFORE the entry). Split the prior rule's dev trades by valid/invalid."""
import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/shares_mgmt')
import numpy as np, pandas as pd
import sim
for d, entry in [('with', 'PB10'), ('against', 'PB10'), ('conv', 'PB10')]:
    for K in (60, 150):
        rows = []
        for r in sim.ROWS:
            if r['period'] != 'dev':
                continue
            sb = sim.sign_base(r, d)
            if sb == 0:
                continue
            ent = sim.entry_of(entry, r, sb, False)
            if ent is None:
                continue
            e, P = ent
            g = sim.sim_exit(('time', K), r, e, P, sb, r['atr']) - sim.COST
            rows.append((r['date'], e, K, g))
        t = pd.DataFrame(rows, columns=['date', 'e', 'K', 'net'])
        ok = t[t.e < K]; bad = t[t.e >= K]
        print(f"{d}|PB1%|time{K}: all n={len(t)} mean={t.net.mean()*1e4:+.1f}bp | "
              f"entry before exit n={len(ok)} mean={ok.net.mean()*1e4 if len(ok) else float('nan'):+.1f}bp | "
              f"entry AFTER exit (invalid) n={len(bad)} mean={bad.net.mean()*1e4 if len(bad) else float('nan'):+.1f}bp")
