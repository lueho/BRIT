from decimal import Decimal
from functools import lru_cache


class UnitConversionError(ValueError):
    """Raised when conversion between two Unit objects is not possible."""


WEIGHT_FRACTION_FACTORS_TO_PERCENT = {
    "%": Decimal("1"),
    "percent": Decimal("1"),
    "g/kg": Decimal("0.1"),
    "gperkg": Decimal("0.1"),
    "mg/kg": Decimal("0.0001"),
    "mgperkg": Decimal("0.0001"),
}


def _normalize_unit_token(token):
    return (token or "").strip().lower().replace(" ", "")


def convert_weight_fraction_value(value, source_token, target_token):
    """Convert between supported weight-fraction units via percent factors."""
    source_key = _normalize_unit_token(source_token)
    target_key = _normalize_unit_token(target_token)
    source_factor = WEIGHT_FRACTION_FACTORS_TO_PERCENT.get(source_key)
    target_factor = WEIGHT_FRACTION_FACTORS_TO_PERCENT.get(target_key)

    if source_factor is None or target_factor is None:
        raise UnitConversionError(
            f"Unsupported weight-fraction conversion from '{source_token}' to '{target_token}'."
        )

    return Decimal(str(value)) * source_factor / target_factor


CUSTOM_PINT_DEFINITIONS = (
    "percent = 0.01 * count = %",
    "permille = 0.001 * count = ‰",
    "dry_matter_basis = [] = DM",
)


@lru_cache(maxsize=1)
def get_unit_registry():
    """
    Return a singleton pint UnitRegistry or None when pint is unavailable.
    """
    try:
        import pint
    except ImportError:
        return None

    registry = pint.UnitRegistry()
    for definition in CUSTOM_PINT_DEFINITIONS:
        try:
            registry.define(definition)
        except Exception:
            # Keep startup resilient even if a custom definition already exists.
            pass
    return registry
