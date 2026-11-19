"""Build dev-stage Day objects (engine.prepare('dev'), Mon/Fri, < 2024-01-01), keep <= 2023-12-31, cache."""
import pickle, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/Users/rytty/CCP/quant_v7")
from research.mstr_btc_0dte import engine as eng
H = Path(__file__).parent
days = [d for d in eng.prepare("dev") if d.d <= pd.Timestamp("2023-12-31")]
print("dev days", len(days), days[0].d.date(), days[-1].d.date())
pickle.dump(days, open(H / "dev_days_vol.pkl", "wb"))
