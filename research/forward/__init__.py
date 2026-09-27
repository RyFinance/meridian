"""Tamper-evident forward-prediction registry (append-only, SHA-256 hash chain).

Modules:
  registry   -- canonical hashing, locked append, chain verification
  nyse       -- NYSE session calendar (holidays, early closes, session times)
  prices     -- official session opens/closes: LSE intraday reconstruction, yfinance
  adapters   -- pead_bot_v1 (read-only ingest), momentum_gold_v1, generic targets
  record     -- manual CLI entry point (never scheduled)
  verify     -- chain verifier CLI + head line for external anchoring
  evaluate   -- forward-only evaluator (clean decisions only)
"""
