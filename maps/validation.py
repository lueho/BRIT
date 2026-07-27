"""Central validation for custom ``Region`` compositions.

A custom region may be composed of NUTS (level 0-3) and LAU regions via
``Region.composed_of``. The composition must describe a complete,
non-overlapping partition of the custom territory:

- only NUTS and LAU components are allowed (no nested custom regions),
- a region must not contain itself,
- no component may be a parent or descendant of another component,
- no two components may share the same logical territory,
- components must not spatially overlap with positive area
  (boundary-only contact is valid).
"""

from django.core.exceptions import ValidationError

from .models import LauRegion, NutsRegion


class RegionCompositionError(ValidationError):
    """Composition of a custom region violates the overlap policy."""

    def __init__(self, message, conflicts=None):
        super().__init__(message)
        self.conflicts = list(conflicts or [])


def _as_nuts(region):
    if isinstance(region, NutsRegion):
        return region
    try:
        return region.nutsregion
    except NutsRegion.DoesNotExist:
        return None


def _as_lau(region):
    if isinstance(region, LauRegion):
        return region
    try:
        return region.lauregion
    except LauRegion.DoesNotExist:
        return None


def _identifier(region):
    return region.nuts_or_lau_id or f"region:{region.pk}"


def _nuts_ancestor_ids(nuts_region):
    """Return nuts_ids of all ancestors, using parent links with an id-prefix fallback."""
    ancestors = set()
    parent = nuts_region.parent
    while parent is not None:
        if parent.nuts_id:
            ancestors.add(parent.nuts_id)
        parent = parent.parent
    if nuts_region.nuts_id:
        for length in range(2, len(nuts_region.nuts_id)):
            ancestors.add(nuts_region.nuts_id[:length])
    return ancestors


def validate_region_composition(members, region=None):
    """Validate the direct components of a custom region.

    ``members`` are the regions intended for ``region.composed_of``.
    Raises :class:`RegionCompositionError` on any violation.
    """
    members = list(members)

    if region is not None and region.pk is not None:
        for member in members:
            if member.pk == region.pk:
                raise RegionCompositionError(
                    "A custom region must not contain itself.",
                    conflicts=[_identifier(member)],
                )

    seen_pks = set()
    for member in members:
        if member.pk in seen_pks:
            raise RegionCompositionError(
                f"Duplicate component '{_identifier(member)}' in custom region composition.",
                conflicts=[_identifier(member)],
            )
        seen_pks.add(member.pk)

    typed = []
    for member in members:
        nuts = _as_nuts(member)
        lau = None if nuts is not None else _as_lau(member)
        if nuts is None and lau is None:
            raise RegionCompositionError(
                f"Component '{member}' is not a NUTS or LAU region. "
                "Nested custom regions are not allowed in a composition.",
                conflicts=[_identifier(member)],
            )
        typed.append((member, nuts, lau))

    nuts_ids = {}
    lau_keys = {}
    for member, nuts, lau in typed:
        if nuts is not None and nuts.nuts_id:
            if nuts.nuts_id in nuts_ids:
                raise RegionCompositionError(
                    f"Components duplicate the territory '{nuts.nuts_id}'.",
                    conflicts=[nuts.nuts_id, nuts.nuts_id],
                )
            nuts_ids[nuts.nuts_id] = member
        if lau is not None and lau.lau_id:
            key = (lau.cntr_code, lau.lau_id)
            if key in lau_keys:
                raise RegionCompositionError(
                    f"Components duplicate the territory '{lau.lau_id}'.",
                    conflicts=[lau.lau_id, lau.lau_id],
                )
            lau_keys[key] = member

    for member, nuts, lau in typed:
        if nuts is not None:
            ancestors = _nuts_ancestor_ids(nuts)
        else:
            ancestors = set()
            if lau.nuts_parent is not None:
                if lau.nuts_parent.nuts_id:
                    ancestors.add(lau.nuts_parent.nuts_id)
                ancestors |= _nuts_ancestor_ids(lau.nuts_parent)
        conflict = next((a for a in sorted(ancestors) if a in nuts_ids), None)
        if conflict is not None:
            raise RegionCompositionError(
                f"Components overlap: '{_identifier(member)}' is contained "
                f"in component '{conflict}'.",
                conflicts=[_identifier(member), conflict],
            )

    for index, (member_a, _nuts_a, _lau_a) in enumerate(typed):
        geom_a = member_a.geom
        if geom_a is None:
            continue
        for member_b, _nuts_b, _lau_b in typed[index + 1 :]:
            geom_b = member_b.geom
            if geom_b is None:
                continue
            # "2********" matches interiors intersecting with a 2D area.
            if geom_a.relate_pattern(geom_b, "2********"):
                raise RegionCompositionError(
                    f"Components overlap spatially: '{_identifier(member_a)}' "
                    f"and '{_identifier(member_b)}'.",
                    conflicts=[_identifier(member_a), _identifier(member_b)],
                )
