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


def _provably_disjoint(member_a, member_b):
    """True when disjointness of a member pair is actually established.

    ``validate_region_composition`` only rejects overlaps it can prove;
    consumers that combine member territories need the stronger guarantee
    that each pair is provably disjoint — by administrative ancestry or by
    a spatial check on complete geometry.
    """
    if member_a.geom is not None and member_b.geom is not None:
        # The composition validator already excluded positive-area overlap
        # for geometry-bearing pairs.
        return True

    nuts_a = _as_nuts(member_a)
    lau_a = None if nuts_a is not None else _as_lau(member_a)
    nuts_b = _as_nuts(member_b)
    lau_b = None if nuts_b is not None else _as_lau(member_b)

    if nuts_a is not None and nuts_b is not None:
        # Distinct NUTS ids with no ancestor relation partition territory;
        # a missing id cannot be placed administratively.
        return bool(nuts_a.nuts_id and nuts_b.nuts_id)
    if lau_a is not None and lau_b is not None:
        # LAU ids partition municipalities within a country.
        return lau_a.cntr_code != lau_b.cntr_code or bool(lau_a.lau_id and lau_b.lau_id)

    nuts, lau = (nuts_a, lau_b) if nuts_a is not None else (nuts_b, lau_a)
    if nuts is None or lau is None or not nuts.nuts_id:
        return False
    parent = lau.nuts_parent
    if parent is None or not parent.nuts_id:
        # The LAU cannot be anchored inside the NUTS hierarchy.
        return False
    # The LAU lives inside its parent's subtree. A NUTS member inside or on
    # that subtree may share the LAU's territory, and one containing the
    # parent provably does (both already rejected by the composition
    # validator); anything outside is disjoint.
    return (
        parent.nuts_id != nuts.nuts_id
        and parent.nuts_id not in _nuts_ancestor_ids(nuts)
        and nuts.nuts_id not in _nuts_ancestor_ids(parent)
    )


def validate_disjoint_regions(members):
    """Require that every member pair is *provably* disjoint.

    ``validate_region_composition`` accepts members it cannot prove to
    overlap — e.g. a LAU with no ``nuts_parent`` and no geometry next to an
    enclosing NUTS region. Consumers that combine member territories, such
    as population sums, must not rely on that weaker contract and should
    run this check in addition.

    Raises :class:`RegionCompositionError` for pairs whose disjointness
    cannot be established.
    """
    members = list(members)
    for index, member_a in enumerate(members):
        for member_b in members[index + 1 :]:
            if _provably_disjoint(member_a, member_b):
                continue
            raise RegionCompositionError(
                f"Cannot verify that components '{_identifier(member_a)}' and "
                f"'{_identifier(member_b)}' are disjoint; their territories "
                "must not be combined.",
                conflicts=[_identifier(member_a), _identifier(member_b)],
            )
