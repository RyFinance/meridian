"""Declared parameters, ETF universe, supported configs and fixed recipes (SPEC.md sections 1-4).

Recipe weights are kept as exact ``Fraction`` values so a unit test can check that every recipe reproduces its
config's exposures exactly; the engine uses their float values.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from fractions import Fraction as F
from pathlib import Path
from typing import Any

SLEEVES = ("EQ", "BOND", "GOLD", "TREND")
ACCOUNT_TYPES = ("tfsa", "rrsp", "nonreg_cash", "nonreg_margin")
NO_BORROW_ACCOUNTS = ("tfsa", "rrsp", "nonreg_cash")
OWNER_TOLERANCES_PCT = (25, 35, 50)
USDCAD = "USDCAD"

# --- section 1: supported configurations (exposures per unit of L) ---------------------------------------------
_BASE = {
    "P3": {"EQ": F("0.60"), "BOND": F("0.40")},
    "P4": {"EQ": F("0.48"), "BOND": F("0.32"), "GOLD": F("0.10"), "TREND": F("0.10")},
    "P6a": {"EQ": F("1.00"), "TREND": F("0.50")},
}
_LEVELS = {"P3": ("1.0", "1.25", "1.5"), "P4": ("1.0", "1.25", "1.5"), "P6a": ("1.0", "1.25")}


def _config_table() -> dict[str, dict[str, Any]]:
    table = {}
    for family, levels in _LEVELS.items():
        for level in levels:
            lev = F(level)
            exposures = {s: _BASE[family].get(s, F(0)) * lev for s in SLEEVES}
            table[f"{family}@{level}"] = {"family": family, "L": lev, "exposures": exposures,
                                          "target_gross": sum(exposures.values(), F(0))}
    return table


CONFIGS: dict[str, dict[str, Any]] = _config_table()

# --- section 2: ETF universe -------------------------------------------------------------------------------------
UNIVERSE: dict[str, dict[str, Any]] = {
    "XEQT.TO": {"ccy": "CAD", "exp": {"EQ": F(1)}, "note": "global one-ticket equity"},
    "ZAG.TO": {"ccy": "CAD", "exp": {"BOND": F(1)}, "note": "Canadian aggregate bonds"},
    "ZGLD.TO": {"ccy": "CAD", "exp": {"GOLD": F(1)}, "note": "gold bullion (CAD units)"},
    "DBMF": {"ccy": "USD", "exp": {"TREND": F(1)}, "note": "managed-futures replication"},
    "RSSB": {"ccy": "USD", "exp": {"EQ": F(1), "BOND": F(1)},
             "note": "stacked global equity + US Treasuries (the bond leg is US Treasuries)"},
    "RSST": {"ccy": "USD", "exp": {"EQ": F(1), "TREND": F(1)},
             "note": "stacked US equity + managed futures (the equity leg is US-only)"},
    "GDE": {"ccy": "USD", "exp": {"EQ": F("0.9"), "GOLD": F("0.9")},
            "note": "stacked US equity + gold (equity leg US-only; kept in the universe, not used by default recipes)"},
    "SSO": {"ccy": "USD", "exp": {"EQ": F(2)},
            "note": "2x daily-reset S&P 500 leveraged ETF (US-only equity; path-dependent daily reset)"},
    "CASH.TO": {"ccy": "CAD", "exp": {}, "note": "cash buffer vehicle (or broker cash)"},
}
for _t in UNIVERSE.values():
    _t["exp"] = {s: _t["exp"].get(s, F(0)) for s in SLEEVES}

# --- section 3: recipes (weights of invested capital, before the cash buffer) -------------------------------------
_W = F
STACKED: dict[str, dict[str, F]] = {
    "P3@1.0": {"XEQT.TO": _W(".60"), "ZAG.TO": _W(".40")},
    "P3@1.25": {"RSSB": _W(".25"), "XEQT.TO": _W(".50"), "ZAG.TO": _W(".25")},
    "P3@1.5": {"RSSB": _W(".50"), "XEQT.TO": _W(".40"), "ZAG.TO": _W(".10")},
    "P4@1.0": {"XEQT.TO": _W(".48"), "ZAG.TO": _W(".32"), "ZGLD.TO": _W(".10"), "DBMF": _W(".10")},
    "P4@1.25": {"RSSB": _W(".125"), "RSST": _W(".125"), "ZGLD.TO": _W(".125"), "ZAG.TO": _W(".275"),
                "XEQT.TO": _W(".35")},
    "P4@1.5": {"RSSB": _W(".35"), "RSST": _W(".15"), "ZGLD.TO": _W(".15"), "ZAG.TO": _W(".13"),
               "XEQT.TO": _W(".22")},
    "P6a@1.0": {"RSST": _W(".50"), "XEQT.TO": _W(".50")},
    "P6a@1.25": {"RSST": _W(".625"), "SSO": _W(".25"), "XEQT.TO": _W(".125")},
}
MARGIN: dict[str, dict[str, F]] = {  # key "loan" = margin loan as a fraction of NAV
    "P3@1.0": {"XEQT.TO": _W(".60"), "ZAG.TO": _W(".40"), "loan": _W(0)},
    "P3@1.25": {"XEQT.TO": _W(".75"), "ZAG.TO": _W(".50"), "loan": _W(".25")},
    "P3@1.5": {"XEQT.TO": _W(".90"), "ZAG.TO": _W(".60"), "loan": _W(".50")},
    "P4@1.0": {"XEQT.TO": _W(".48"), "ZAG.TO": _W(".32"), "ZGLD.TO": _W(".10"), "DBMF": _W(".10"), "loan": _W(0)},
    "P4@1.25": {"XEQT.TO": _W(".60"), "ZAG.TO": _W(".40"), "ZGLD.TO": _W(".125"), "DBMF": _W(".125"),
                "loan": _W(".25")},
    "P4@1.5": {"XEQT.TO": _W(".72"), "ZAG.TO": _W(".48"), "ZGLD.TO": _W(".15"), "DBMF": _W(".15"),
               "loan": _W(".50")},
    "P6a@1.0": {"RSST": _W(".50"), "XEQT.TO": _W(".50"), "loan": _W(0)},
    "P6a@1.25": {"XEQT.TO": _W(".625"), "RSST": _W(".625"), "loan": _W(".25")},
}
LETF_CONFIGS = {cid for cid, r in STACKED.items() if "SSO" in r}


def recipe_for(config_id: str, account_type: str) -> tuple[dict[str, F], F, str]:
    """Return (ticker weights, loan fraction, recipe kind) for a supported config/account pair."""
    if account_type == "nonreg_margin":
        r = dict(MARGIN[config_id])
        loan = r.pop("loan")
        return r, loan, "margin"
    return dict(STACKED[config_id]), F(0), "stacked"


def recipe_exposures(weights: dict[str, F]) -> dict[str, F]:
    return {s: sum((w * UNIVERSE[t]["exp"][s] for t, w in weights.items()), F(0)) for s in SLEEVES}


# --- section 4: declared parameters ------------------------------------------------------------------------------
HALF_SPREAD = {"XEQT.TO": 0.0005, "ZAG.TO": 0.0005, "CASH.TO": 0.0005, "SSO": 0.0003,
               "ZGLD.TO": 0.0010, "DBMF": 0.0010, "RSSB": 0.0010, "RSST": 0.0010, "GDE": 0.0010}

DECLARED: dict[str, Any] = {
    "cash_buffer": 0.01,               # fraction of NAV; targets = (1 - buffer) x recipe weights
    "cash_buffer_vehicle": "broker_cash",
    "band_abs": 0.05,                  # trade if abs drift > 5.0 pp
    "band_rel": 0.25,                  # ... or relative drift > 25% of target
    "band_rel_min_abs": 0.01,          # ... and abs drift > 1.0 pp
    "margin_leverage_band": 0.10,      # margin: trade if |assets/equity - target| > 0.10
    "calendar_months": [3, 6, 9, 12],  # quarter-end reports
    "calendar_abs": 0.01,              # rebalance at quarter-end if any abs drift > 1.0 pp
    "min_trade_cad": 100.0,            # skip trades < CAD 100
    "fx_cost": 0.001,                  # broker conversion cost 0.10%
    "commission_cad": 0.0,             # per trade
    "half_spread": dict(HALF_SPREAD),
    "freshness_days": 5,               # calendar days
    "leverage_cap_addon": 0.15,        # gross exposure / NAV <= target gross + 0.15
    "equity_assets_floor": 0.40,       # margin accounts, after trades
    "max_position": 0.65,              # of NAV, after trades (every ticker except SSO and the one-ticket funds)
    "max_position_sso": 0.30,
    "one_ticket_cap_addon": 0.05,      # XEQT.TO / ZAG.TO cap = their target weight (after the buffer) + 5 pp
    "alert_levels": {"INFO": 0.50, "WARNING": 0.75, "BREACH": 1.00},  # fraction of owner tolerance
}

# Overridable parameters and their allowed ranges.  Risk limits may only be tightened (conservative reading of
# "optional overrides of the declared parameters"); see IMPLEMENTATION_NOTES.md.
OVERRIDE_RANGES: dict[str, tuple[float, float]] = {
    "cash_buffer": (0.01, 0.10),
    "band_abs": (0.0, 0.20),
    "band_rel": (0.0, 1.0),
    "band_rel_min_abs": (0.0, 0.05),
    "margin_leverage_band": (0.0, 0.50),
    "calendar_abs": (0.0, 0.05),
    "min_trade_cad": (0.0, 10_000.0),
    "fx_cost": (0.001, 0.05),          # cost estimates may only be raised above the declared values
    "commission_cad": (0.0, 100.0),
    "freshness_days": (0, 5),
    "leverage_cap_addon": (0.0, 0.15),
    "equity_assets_floor": (0.40, 1.0),
    "max_position": (0.0, 0.65),
    "max_position_sso": (0.0, 0.30),
    "one_ticket_cap_addon": (0.0, 0.05),
}
OVERRIDE_OTHER = ("half_spread", "cash_buffer_vehicle")
CASH_VEHICLES = ("broker_cash", "CASH.TO")
CONFIG_KEYS = {"config_id", "account_type", "owner_tolerance_pct", "overrides", "portfolio_id", "label"}
LABEL_MAX_CHARS = 200


class ConfigError(ValueError):
    """The config file is unreadable (fatal) or describes an unsupported configuration (refusal)."""


@dataclass(frozen=True)
class Config:
    config_id: str
    account_type: str
    owner_tolerance_pct: int
    portfolio_id: str
    overrides: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    error: str | None = None     # set when the config is unsupported -> the run is refused
    label: str | None = None     # optional free-text banner printed at the top of the report (e.g. "HYPOTHETICAL")

    @property
    def supported(self) -> bool:
        return self.error is None


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _effective_params(overrides: dict[str, Any], account_type: str) -> dict[str, Any]:
    params = json.loads(json.dumps(DECLARED))
    for key, value in sorted(overrides.items()):
        if key in OVERRIDE_RANGES:
            lo, hi = OVERRIDE_RANGES[key]
            if not _is_number(value) or not (lo <= float(value) <= hi):
                raise ConfigError(f"override {key}={value!r} outside allowed range [{lo}, {hi}]")
            if key == "freshness_days":
                if int(value) != value:
                    raise ConfigError("override freshness_days must be a whole number of days")
                params[key] = int(value)
            else:
                params[key] = float(value)
        elif key == "half_spread":
            if not isinstance(value, dict):
                raise ConfigError("override half_spread must map ticker -> rate")
            for ticker, rate in sorted(value.items()):
                if ticker not in UNIVERSE or not _is_number(rate) or not (HALF_SPREAD[ticker] <= float(rate) <= 0.05):
                    raise ConfigError(f"override half_spread[{ticker!r}]={rate!r} invalid (allowed: declared "
                                      f"{HALF_SPREAD.get(ticker)} up to 0.05; cost estimates may only be raised)")
                params["half_spread"][ticker] = float(rate)
        elif key == "cash_buffer_vehicle":
            if value not in CASH_VEHICLES:
                raise ConfigError(f"override cash_buffer_vehicle must be one of {CASH_VEHICLES}")
            if value == "CASH.TO" and account_type == "nonreg_margin":
                raise ConfigError("cash_buffer_vehicle CASH.TO is not supported in margin accounts")
            params[key] = value
        else:
            raise ConfigError(f"unknown or non-overridable parameter: {key!r}")
    return params


def parse_config(raw: Any) -> Config:
    """Build a Config from parsed JSON.  Structural problems raise ConfigError (fatal: nothing can be reported
    against an unidentifiable config); an unsupported but identifiable config returns ``Config(error=...)``."""
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    config_id = raw.get("config_id")
    if not isinstance(config_id, str) or not config_id.strip():
        raise ConfigError("config_id missing")
    account_type = raw.get("account_type")
    account_type = account_type if isinstance(account_type, str) else repr(account_type)
    tol = raw.get("owner_tolerance_pct")
    overrides = raw.get("overrides", {}) or {}
    portfolio_id = raw.get("portfolio_id")
    errors = []
    unknown = sorted(set(raw) - CONFIG_KEYS)
    if unknown:
        errors.append(f"unknown config keys {unknown}")
    if config_id not in CONFIGS:
        errors.append(f"unsupported config id {config_id!r} (supported: {sorted(CONFIGS)})")
    if account_type not in ACCOUNT_TYPES:
        errors.append(f"unsupported account type {account_type!r} (supported: {list(ACCOUNT_TYPES)})")
    if not (isinstance(tol, int) and not isinstance(tol, bool) and tol in OWNER_TOLERANCES_PCT):
        errors.append(f"owner_tolerance_pct must be one of {list(OWNER_TOLERANCES_PCT)}; got {tol!r}")
        tol = 0
    if not isinstance(overrides, dict):
        errors.append("overrides must be a JSON object")
        overrides = {}
    overrides = dict(overrides)
    if portfolio_id is None:
        portfolio_id = f"{config_id}|{account_type}"
    elif not isinstance(portfolio_id, str) or not portfolio_id.strip():
        errors.append("portfolio_id must be a non-empty string")
        portfolio_id = f"{config_id}|{account_type}"
    label = raw.get("label")
    if label is not None and (not isinstance(label, str) or not label.strip() or len(label) > LABEL_MAX_CHARS
                              or any(c in label for c in "\r\n")):
        errors.append(f"label must be a non-empty single-line string of at most {LABEL_MAX_CHARS} characters")
        label = None
    params: dict[str, Any] = {}
    if not errors:
        try:
            params = _effective_params(overrides, account_type)
        except ConfigError as exc:
            errors.append(str(exc))
    return Config(config_id=config_id, account_type=account_type, owner_tolerance_pct=int(tol),
                  portfolio_id=portfolio_id, overrides=overrides, params=params,
                  error="; ".join(errors) if errors else None, label=label)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def strict_json_loads(text: str) -> Any:
    """``json.loads`` that rejects duplicate keys and NaN/Infinity literals."""
    def _bad_constant(name: str) -> Any:
        raise ValueError(f"non-finite JSON number {name}")
    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_bad_constant)


def load_config(path: Path) -> tuple[Config, bytes]:
    """Read and parse a config file.  Unreadable/invalid JSON raises ConfigError (fatal)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ConfigError(f"config file unreadable: {exc.strerror or exc}") from exc
    try:
        raw = strict_json_loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ConfigError(f"config file is not valid JSON: {exc}") from exc
    return parse_config(raw), data


def target_weights(cfg: Config) -> dict[str, float]:
    """Target weight of NAV per ticker: (1 - cash buffer) x recipe weight (+ the buffer in CASH.TO if chosen)."""
    weights, _loan, _kind = recipe_for(cfg.config_id, cfg.account_type)
    keep = 1.0 - float(cfg.params["cash_buffer"])
    out = {t: keep * float(w) for t, w in sorted(weights.items())}
    if cfg.params.get("cash_buffer_vehicle") == "CASH.TO":
        out["CASH.TO"] = out.get("CASH.TO", 0.0) + float(cfg.params["cash_buffer"])
    return out


# SPEC section 4 (change 2026-09-29): diversified one-ticket funds whose single-position cap is their own target
# weight (after the cash buffer) + 5 pp instead of the flat 65% of NAV.
ONE_TICKET_FUNDS = ("XEQT.TO", "ZAG.TO")


def position_cap(ticker: str, target: dict[str, float], params: dict[str, Any]) -> tuple[float, str]:
    """(cap as a fraction of NAV, rule name) for one ticker, given the target weights of NAV (after the buffer).

    SSO: ``max_position_sso``; XEQT.TO / ZAG.TO: target + ``one_ticket_cap_addon`` (a held one-ticket fund with
    target 0 gets the add-on alone); every other ticker: ``max_position``."""
    if ticker == "SSO":
        return float(params["max_position_sso"]), "max_position_sso"
    if ticker in ONE_TICKET_FUNDS:
        return float(target.get(ticker, 0.0)) + float(params["one_ticket_cap_addon"]), "target + one_ticket_cap_addon"
    return float(params["max_position"]), "max_position"


def borrow_capacity_fraction(cfg: Config) -> float:
    """CAD the engine may borrow to fund buys, as a fraction of pre-trade NAV: the recipe loan (L - 1) for
    ``nonreg_margin`` (0 for L = 1.0), and 0 for every other account type."""
    if cfg.account_type != "nonreg_margin":
        return 0.0
    return float(recipe_for(cfg.config_id, cfg.account_type)[1])


def target_gross(cfg: Config) -> float:
    """Config target gross exposure / NAV (sum of section-1 exposures), the base of the leverage cap."""
    return float(CONFIGS[cfg.config_id]["target_gross"])
