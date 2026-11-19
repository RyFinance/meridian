# Slow BTC-trend → MSTR regime tests — rejected in development

This folder contains two pre-holdout exploratory families.  Neither was sent to
the 2023+ validation sample because neither met the stability bar in the
2020-08-11 through 2022-12-30 development period.

## 1. BTC-only long/cash SMA gate

At each 16:00 ET close, hold MSTR from the next official open only if BTC was
above its trailing SMA.  Execution used 3 bp plus $0.005/share per MSTR side;
the stress case doubled both.  The 20, 40, 60, 100, 150, and 200-session family
was evaluated by `regime_dev.py`.

| BTC SMA | Base total return | Stress total return | Base Sharpe | 2021 | 2022 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | -18.3% | -20.5% | 0.23 | -11.5% | -68.3% |
| 40 | +87.6% | +85.4% | 0.74 | +30.3% | -36.4% |
| 60 | -33.2% | -34.0% | 0.05 | -4.1% | -44.7% |
| 100 | -58.4% | -58.6% | -0.50 | -48.7% | -19.0% |
| 150 | -53.9% | -54.2% | -0.94 | -53.9% | -0.0% |
| 200 | -18.4% | -18.9% | -0.22 | -17.7% | -0.9% |

The 40-session row is an isolated winner and has an unacceptable 2022 result;
all immediate neighboring lookbacks are negative.  It is not a plausible
out-of-sample candidate.

## 2. Two-factor BTC/MSTR confirmation gate

`TWO_FACTOR_PROTOCOL.md` registered four standard combinations before results
were calculated: BTC and MSTR each above their 50- or 100-session SMA.  The
same execution and costs apply.

| BTC SMA | MSTR SMA | Base total return | Stress total return | Base Sharpe | 2021 | 2022 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | 50 | +29.8% | +28.5% | 0.48 | +23.7% | -45.2% |
| 50 | 100 | -59.8% | -60.2% | -0.49 | -29.7% | -42.8% |
| 100 | 50 | -53.2% | -53.5% | -0.63 | -42.2% | -19.0% |
| 100 | 100 | -44.5% | -44.8% | -0.31 | -39.2% | -8.7% |

Again, the sole positive cell is surrounded by negative variants and loses
roughly 45% in 2022.  It was rejected without opening the holdout results.

## Conclusion

No slow BTC trend filter tested here is being proposed as a tradeable MSTR
method.  The development tests serve as a guardrail against promoting a generic
one-regime crypto bull-market fit as a durable edge.
