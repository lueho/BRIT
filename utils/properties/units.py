from decimal import Decimal
from functools import lru_cache


class UnitConversionError(ValueError):
    """Raised when conversion between two Unit objects is not possible."""


WEIGHT_FRACTION_FACTORS_TO_PERCENT = {
    "%": Decimal("1"),
    "percent": Decimal("1"),
    "wt%": Decimal("1"),
    "g/100g": Decimal("1"),
    "‰": Decimal("0.1"),
    "permille": Decimal("0.1"),
    "g/kg": Decimal("0.1"),
    "gperkg": Decimal("0.1"),
    "mg/g": Decimal("0.1"),
    "kg/t": Decimal("0.1"),
    "mg/kg": Decimal("0.0001"),
    "mgperkg": Decimal("0.0001"),
    "g/g": Decimal("100"),
    "kg/kg": Decimal("100"),
}

WEIGHT_FRACTION_UNIT_TOKENS = frozenset(WEIGHT_FRACTION_FACTORS_TO_PERCENT)


def _normalize_unit_token(token):
    return (token or "").strip().lower().replace(" ", "")


def is_weight_fraction_unit_token(token):
    return _normalize_unit_token(token) in WEIGHT_FRACTION_UNIT_TOKENS


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
    # Normal gas volume at 0 degrees C and 101325 Pa. A separate dimension
    # prevents conversion to actual volume without the gas reference conditions.
    ("normal_liter", "normal_liter = [normal_volume] = NL"),
    ("normal_milliliter", "normal_milliliter = 0.001 * normal_liter = NmL"),
    # Physically dimensionless, but semantically distinct from mass fractions.
    # Do not alias to percent: Pint would then permit mass/volume conversion.
    ("volume_fraction", "volume_fraction = [volume_fraction]"),
    ("volume_percent", "volume_percent = 0.01 * volume_fraction = vol_percent"),
    ("percent", "percent = 0.01 * count = %"),
    ("permille", "permille = 0.001 * count = ‰"),
    ("dry_matter_basis", "dry_matter_basis = [] = DM"),
    ("milliequivalent", "milliequivalent = 0.001 * mole = meq"),
    ("meq_per_100g", "meq_per_100g = 0.01 * milliequivalent / gram = meq_100g"),
    (
        "count_per_1000mL",
        "count_per_1000mL = 0.001 * count / milliliter = count_1000mL",
    ),
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
    for unit_name, definition in CUSTOM_PINT_DEFINITIONS:
        try:
            registry.Unit(unit_name)
            continue
        except Exception:
            pass
        try:
            registry.define(definition)
        except Exception:
            # Keep startup resilient even if a custom definition already exists.
            pass
    return registry
