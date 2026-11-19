-- Read-only local-data inventory for the MSTR-versus-IBIT option-IV study.
-- Run from the repository root with:
--   duckdb -noheader -csv < research/mstr_btc_0dte/agent_ivspread/inventory.sql
--
-- This deliberately inspects schemas and coverage only.  It does not infer
-- implied volatilities from last-sale OHLC bars and it does not write data.

SELECT 'mstr_daily_options_schema' AS section;
DESCRIBE SELECT *
FROM read_parquet('data/lse/options_mstr/MSTR.parquet')
LIMIT 0;

SELECT 'mstr_daily_options_coverage' AS section;
SELECT
  min(ts) AS first_ts,
  max(ts) AS last_ts,
  count(*) AS rows,
  count(DISTINCT osi) AS contracts,
  count(DISTINCT expiry) AS expiries
FROM read_parquet('data/lse/options_mstr/MSTR.parquet');

SELECT 'mstr_1m_options_schema' AS section;
DESCRIBE SELECT *
FROM read_parquet('data/lse/options_mstr/1m/chunk_000_2020-08-10.parquet')
LIMIT 0;

SELECT 'mstr_1m_options_coverage' AS section;
SELECT
  min(ts) AS first_ts,
  max(ts) AS last_ts,
  count(*) AS rows,
  count(DISTINCT osi) AS contracts,
  count(DISTINCT expiry) AS expiries
FROM read_parquet('data/lse/options_mstr/1m/chunk_*.parquet', union_by_name = true);

SELECT 'ibit_underlying_schema' AS section;
DESCRIBE SELECT *
FROM read_parquet('research/btc_session/ibit_1m_lse.parquet')
LIMIT 0;

SELECT 'ibit_underlying_coverage' AS section;
SELECT
  min(ts) AS first_ts,
  max(ts) AS last_ts,
  count(*) AS rows,
  count(DISTINCT symbol) AS symbols
FROM read_parquet('research/btc_session/ibit_1m_lse.parquet');
