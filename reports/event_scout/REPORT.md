# Event-data scout report — workload D, research cycle 4

*Written by the cycle-4 event scout agent (2026-09-24). Saved by the director session. Director's note: the literature CARs cited include the announcement reaction itself. A tradable design earns only the post-next-open drift, which is usually far smaller. Power must be computed against the drift, not the CAR.*

**Scope discipline followed:** no event→return relationship was computed anywhere in this session. Ranking is from mechanism, literature and data properties only. No existing files were edited, nothing was committed, `bot/`, `reports/forward/registry.jsonl`, launchd/cron were untouched.

**Outputs on disk:**
- `reports/event_scout/ranking.csv` — 10 families × 19 fields, machine-readable
- `reports/event_scout/families.json` — full structured detail per family, incl. per-criterion H/M/L scores
- `reports/event_scout/probe_log.json` — manifest of 7 polite HTTP probes (all 200 OK, `User-Agent: quant_v7-research/1.0`, no email)
- `data/event_scout/` — small raw samples (92 KB total, capped 20KB each) backing the probes
- `research/event_scout/probe_sources.py` — the probe script (reproducible)

**Note on `~/.Codex/skills/graphify/SKILL.md` and `graphify-out/`:** the referenced Codex skill file doesn't exist on this machine, it isn't in this session's available-skills list, and `graphify-out/` is empty (no knowledge graph has been built for this repo). I proceeded with direct file reads/grep instead — a technical limitation, not a judgment call.

---

## Contamination check (before ranking)

Grepped `research/`, `reports/`, and `research/RESEARCH_LEDGER_2026-09-23.md` for every avoid-list term plus every candidate family's key nouns. Confirmed **absent** from any executed trial: macro-surprise, FX news continuation, PEAD/earnings, policy trend, Treasury/sector month-end, FX hedge-rebal, LETF close rebalancing, OpEx SPY put-writing, auction cycle, COT-via-commodity-ETFs. `research/EDGE_GRAVEYARD_PLAN.md` Phase 3 flagged "index reconstitution" as a candidate (A3) but it was **never executed** — genuinely open, though the literature-level mechanism (S&P inclusion pop) is independently listed as dead in the project's own `reports/edge_graveyard/REPORT.md`.

## Ranked table (all 8+ required fields are in `families.json`/`ranking.csv`; summarized here)

| Rank | Family | Source (free?) | Events/yr | Clustering | Survivorship risk | Contamination |
|---|---|---|---|---|---|---|
| 1 | 8-K item events (5.02 officer departure, 4.01 auditor change, 4.02 non-reliance restatement, 3.01 delisting notice) | SEC EDGAR submissions API, **confirmed free**, `acceptanceDateTime` to the second | ~2,000–3,900 combined | near-zero | moderate (Sharadar needed for full history) | **Genuinely new** |
| 2 | Overnight/marketed follow-on offerings (424B2/424B5 bought-deal discount) | SEC EDGAR, **confirmed free** | several hundred | low-moderate | moderate | **Genuinely new** |
| 3 | Buyback authorizations + dividend initiations/cuts/specials (declaration date) | SEC EDGAR 8-K 8.01/7.01, free | ~1,150–2,050 informative subset | low | moderate | **Partially used** — fundamentals family tested a monthly issuance ratio on the same data (failed); discrete declaration-date design is untested |
| 4 | IPO lockup expirations (~180 days) | IPO prospectus on EDGAR, free | ~150–400 | low-moderate | **best-in-class low** | Genuinely new |
| 5 | Single-stock options-expiration OI pinning/unwinding | OCC daily OI, **confirmed free** (aggregate only; per-symbol unconfirmed) | thousands of underlying-cells, ~12 real dates/yr | high within a date | moderate | Genuinely new (index-level breadth already SPENT and FAILED, this is single-name OI, different) |
| 6 | Crypto perpetual funding-rate settlements (8h) | Binance API, **confirmed free**, exact 8h spacing verified | ~624,000 (Binance alone, 570 live perpetuals) | **extreme** (3 shared clock-times/day) | **severe** (no delisted-inclusive crypto history) | Genuinely new mechanism; may overlap the parallel Binance-crypto workload |
| 7 | Index reconstitution (Russell semi-annual from Dec-2026, S&P 400/500/600, MSCI) | Official press releases, free but manual | hundreds–1,000+ name-changes | **extreme** (~6–10 independent calendar dates/yr for ALL of it) | moderate | Genuinely new as a trial; literature-dead on the headline "pop" |
| 8 | Reg SHO threshold-list additions | Nasdaq/NYSE, **confirmed free** | low-to-mid hundreds | low | **high** (distressed-name pool) | Genuinely new event design |
| 9 | Stock splits / reverse splits (announcement) | SEC EDGAR, free | tens (forward) to several hundred (reverse) | low | **severe** (reverse-split leg ≈ pre-delisting population) | Genuinely new |
| 10 | Crypto token-unlock vesting cliffs | Web calendars, **no confirmed free bulk API** | hundreds–low thousands (claimed) | low-moderate | severe | Genuinely new, weakest implementation realism |

## Top 3 recommendations

**1. 8-K item-level events, especially after-hours-filed.** Definition: item 5.02 (officer/director departure), 4.01 (auditor dismissal/resignation), 4.02 (non-reliance restatement), 3.01 (delisting notice) 8-Ks, timestamped by `acceptanceDateTime` (verified this session: second-precision UTC, e.g. `2026-04-20T21:29:51.000Z`, item tags included in every record). Timing: signal at acceptance, execute at next regular-session open for after-16:00-ET acceptances. Universe: Russell-3000-sized filers for tradability. Effective sample: thousands/year combined, near-zero clustering (best of any candidate). Literature to power against: CEO/officer-turnover CAR ≈ −1% to −5% (Denis & Denis 1995; Huson, Malatesta & Parrino 2004); non-reliance restatements mean 3-day CAR ≈ −9% (Palmrose, Richardson & Scholz 2004); auditor-dismissal reaction −2% to −3% (DeFond & Zhang 2014 survey). Against quant_v7's own dev gate (1.8/√T, T in years), a multi-hundred-event/year family clears easily on N even at modest per-event magnitude.

**2. Overnight/marketed follow-on equity offerings (424B2/424B5 bought-deal discount).** Definition: same-day-priced corporate equity offerings, discrete from ATM programmatic draws (which have no real-time timestamp). Timing: EDGAR acceptance of the 424B, cross-checked against the same filer's pricing 8-K; execute next open. Universe: Russell-3000-sized issuers. Effective sample: several hundred/year, low clustering. Literature: overnight/marketed-offering discount ≈ 2–3% (Corwin 2003; Gao & Ritter 2010). Mechanistically distinct from every spent family (compensated liquidity provision, not macro/FX/PEAD-style continuation).

**3. Buyback authorizations + dividend initiations/cuts/specials (declaration date).** Definition: first-time/re-up buyback authorizations and dividend initiations, omissions, cuts, and specials, via 8-K 8.01/7.01. Effective sample: ~1,100–2,000 informative events/year. Literature: buyback CAR +2–3% (Vermaelen 1981; Ikenberry, Lakonishok & Vermaelen 1995); dividend initiations +3.4%/omissions −7% (Michaely, Thaler & Womack 1995). **Caveat flagged explicitly**: this carries more contamination than #1/#2 — quant_v7's `fundamentals` family already tested a monthly net-issuance ratio on the same underlying data (failed), though the discrete-declaration-date construction is genuinely different. If the director weights independence-from-prior-research more heavily, **IPO lockup expirations** (rank 4 — pristine on every axis except raw count, which sits at the low end of "hundreds") is the cleaner substitute for this slot.

## Key data-feasibility findings from this session's probes
- SEC EDGAR's `data.sec.gov/submissions/` API returned 200 OK **without an email in the User-Agent** (SEC's own guidance asks for one; single light requests worked, but bulk/sustained use without an email risks throttling — worth revisiting if this scales).
- OCC publishes a genuinely free daily open-interest CSV, but only as **exchange-wide aggregates** in the confirmed endpoint; a per-symbol query tool exists (`marketdata.theocc.com/mdapi/series-search`, returned a structured 400 rather than a block) but needs follow-up work before relying on it — this directly addresses the mandate's instruction to check CBOE/OCC given the LSE has no OI.
- Binance's funding-rate API is fully free, unauthenticated, and confirmed 570 live perpetuals settling exactly every 8 hours.
- Reg SHO threshold lists (Nasdaq) and FINRA daily short-volume files are both free and reachable; the latter is explicitly another agent's territory and was only cross-checked, not analyzed.
- No free, bulk, structured token-unlock calendar was found — this is the one candidate family with an unresolved data-access gap.

## Limitations
- Event counts for buyback/dividend/split/lockup families are order-of-magnitude estimates from general capital-markets knowledge, not counted from a bulk pull (out of scope/budget for this session); a pre-registration should verify exact counts before committing to a gate.
- OCC per-symbol OI, EDGAR bulk-scale rate limits, and token-unlock data access all need a short follow-up feasibility pass before any of those three families is preregistered.
- The index-reconstitution ranking leans heavily on the project's own prior finding (S&P inclusion pop is dead) plus a clustering argument under quant_v7's √T-scaled gate; a director who reads "T" differently (e.g., as event-count rather than calendar-time) might rank this family higher — I flagged the reasoning explicitly rather than silently deciding.
- I did not coordinate live with the SEC/EDGAR, public-market-data, or LSE-breadth agents (their output directories were empty at the time of this session); overlap flags (crypto funding-rate data, Reg SHO/FINRA short data) are noted for the director to route.