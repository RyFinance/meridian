"""Power-first design tools for quant_v7 research plans.

The package is intentionally independent of the historical and forward registries.  It
creates a hashable power disclosure that a researcher may register *before* calculating
returns; it never edits a registry or unlocks validation itself.
"""

from research.power_framework.core import (
    POWER_GRID,
    SUPPORTED_CATEGORIES,
    DesignSpec,
    analyze_design,
)
from research.power_framework.preregistration import (
    PreregistrationPowerSpec,
    analyze_preregistration,
    freeze_disclosure,
    render_markdown,
    verify_disclosure,
)

__all__ = [
    "POWER_GRID",
    "SUPPORTED_CATEGORIES",
    "DesignSpec",
    "PreregistrationPowerSpec",
    "analyze_design",
    "analyze_preregistration",
    "freeze_disclosure",
    "render_markdown",
    "verify_disclosure",
]
