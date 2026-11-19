# Registered follow-up: two-factor BTC/MSTR trend gate

The first, BTC-only SMA family had no robust development cluster and will not
be validated.  This is a separate economic hypothesis: MSTR may be held only
when **both** the underlying BTC regime and the equity's own observable trend
confirm one another, potentially avoiding an equity-specific premium collapse.

Before inspecting any results after 2022, test precisely four long/cash rules
on 2020-08-11 through 2022-12-30:

| Rule | BTC filter | MSTR filter |
| --- | --- | --- |
| TF-50-50 | BTC close > 50-session SMA | MSTR close > 50-session SMA |
| TF-50-100 | BTC close > 50-session SMA | MSTR close > 100-session SMA |
| TF-100-50 | BTC close > 100-session SMA | MSTR close > 50-session SMA |
| TF-100-100 | BTC close > 100-session SMA | MSTR close > 100-session SMA |

Signals are known after the 16:00 ET close and are executed at the next MSTR
official open.  Base and stress costs match `PROTOCOL.md` (3 bp + $0.005/share
per side; 6 bp + $0.010/share).  Cash earns zero.  A rule can be frozen only
if it belongs to a stable neighboring cluster, has a positive stressed
development result, and does not depend on a single calendar year.  At most two
rules will receive one 2023-01-03 through 2026-08-10 validation run.
