# Beyond-menu development trial ledger

This ledger counts every candidate for which this run calculated a development strategy return. Each was evaluated once against its locked, exposure-matched control. No holdout return was calculated. `K=4`, so the fixed positive threshold is a strictly smaller calibrated one-sided p-value than `0.05/4 = 0.0125`, together with positive stressed active mean and a maximum-year share no greater than 40%.

| Trial | Candidate | Frozen input version | Development window | Locked holdout | Result |
|---:|---|---|---|---|---|
| 1 | Factor momentum | `sol_beyond_menu_dev_v1` | 1990-01–2013-12 | 2014-01–2022-07 | FAIL |
| 2 | SPY overnight versus intraday | `sol_beyond_menu_dev_v1` | 1993-02–2014-12 | 2015-01–2022-12 | FAIL |
| 3 | Aggregate short interest | `sol_beyond_menu_dev_v1` | 2004-01–2016-12 | 2017-01–2021-12 | FAIL |
| 4 | Scheduled FOMC risk | `sol_fomc_dev_v1` | 1994-01–2012-12 | 2013-01–2019-12 | FAIL |

The two execution/parser errors are disclosed in [BUG_LOG.md](BUG_LOG.md). A result-summary recovery and updates to the displayed final multiplicity threshold were not new strategy-return trials.
