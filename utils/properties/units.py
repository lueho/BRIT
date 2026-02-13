from functools import lru_cache


class UnitConversionError(ValueError):
    """Raised when conversion between two Unit objects is not possible."""


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
