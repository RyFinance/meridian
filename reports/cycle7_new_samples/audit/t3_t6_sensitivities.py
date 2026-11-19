"""Tests 3a/3c (NDF), 6 (decay, concentration) — SENSITIVITIES, labelled; cannot create a pass."""
from harness import *
base, res = run(return_res=True)
rows = [summarize("BASE (ledgered, full)", base),
        summarize("BASE post-KMVP 2013-09+ (live-expectation)", base, start=KMVP_CUT),
        summarize("BASE 1988-02..2008-08", base, end="2008-08"),
        summarize("BASE 2009-01+", base, start="2009-01")]
ndf = ndf_ids()
for label, kw in [("3a deliverable-only (drop all ever-NDF)", dict(drop=ndf)),
                  ("3c NDF carry haircut 1pp", dict(haircut_pp=1, haircut_ids=ndf)),
                  ("3c NDF carry haircut 2pp", dict(haircut_pp=2, haircut_ids=ndf)),
                  ("3c NDF carry haircut 4pp", dict(haircut_pp=4, haircut_ids=ndf)),
                  ("6 drop TRY", dict(drop=["FX_TRY"])), ("6 drop RUB", dict(drop=["FX_RUB"])),
                  ("6 drop TRY+RUB", dict(drop=["FX_TRY", "FX_RUB"])),
                  ("6 drop top-3 (TRY,RUB,BRL)", dict(drop=["FX_TRY", "FX_RUB", "FX_BRL"]))]:
    a = run(**kw)
    rows.append(summarize(label, a)); rows.append(summarize(label + " | post-KMVP", a, start=KMVP_CUT))
t = pd.DataFrame(rows); pd.set_option("display.width", 250); print(t.round(3).to_string(index=False))
t.to_csv(OUT / "t3_t6_sensitivities.csv", index=False)
# rolling 5-year active Sharpe
r5 = base.rolling(60).apply(lambda x: x.mean() / x.std() * np.sqrt(12), raw=True)
r5.to_csv(OUT / "t6_rolling5y.csv")
print("rolling 5y Sharpe: min", round(r5.min(), 2), str(r5.idxmin()), "max", round(r5.max(), 2), "last", round(r5.iloc[-1], 2),
      "share of windows < 0:", round((r5.dropna() < 0).mean(), 2))
print(r5.dropna().iloc[::24].round(2).to_string())
