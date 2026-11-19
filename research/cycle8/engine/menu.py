"""The fixed cycle-8 menu (FRAMEWORK §3). No other item may be added."""
from __future__ import annotations

LEVELS = (1.0, 1.25, 1.5, 2.0)

# funded sleeves at 1.0x (EQ is resolved to the TFSA or margin variant by leverage), overlays at 1.0x
MENU = {
    "P1u": {"funded": {"EQ_G": 1.0}, "overlay": {}},
    "P1h": {"funded": {"EQ_GH": 1.0}, "overlay": {}},
    "P2": {"funded": {"EQ_G": 0.8, "BOND": 0.2}, "overlay": {}},
    "P3": {"funded": {"EQ_G": 0.6, "BOND": 0.4}, "overlay": {}},
    "P4": {"funded": {"EQ_G": 0.48, "BOND": 0.32, "GOLD": 0.10, "TREND": 0.10}, "overlay": {}},
    "P5": {"funded": "RISK_PARITY", "overlay": {}},
    "P6a": {"funded": {"EQ_G": 1.0}, "overlay": {"X_TREND": 0.5}},
    "P6b": {"funded": {"EQ_G": 1.0}, "overlay": {"X_BOND": 0.5}},
    "P8": {"funded": {"CASH": 1.0}, "overlay": {}},
}
RP_SLEEVES = ("EQ_G", "BOND", "GOLD", "TREND")
ANSWER_ITEMS = ("P1u", "P1h", "P2", "P3", "P4", "P5", "P6a", "P6b")

COST = {"EQ_G": 0.0005, "EQ_GH": 0.0005, "BOND": 0.0005, "GOLD": 0.0010, "TREND": 0.0010 + 0.0010, "CASH": 0.0}
COST_OVERLAY = {"X_TREND": 0.0002, "X_BOND": 0.0002}


def levels(item):
    return (1.0,) if item == "P8" else LEVELS


def eq_col(name: str, L: float) -> str:
    """TFSA variant (WHT drag) at L = 1.0, margin-account variant above (ADDENDUM_1 §4)."""
    if name in ("EQ_G", "EQ_GH"):
        return f"{name}_{'tfsa' if L == 1.0 else 'margin'}"
    return name
