# Waste Atlas biowaste semantics

## Biowaste map scope

In Waste Atlas map names, **biowaste** is shorthand for the combined
`Biowaste` and `Food waste` waste-category scope. A catchment has a separate
biowaste collection when either category has a separate collection. The
primary-collection selection gives actual collection systems priority over
`No separate collection`, so a no-collection record for one category must not
hide a collection recorded for the other category.

## Collection-state categories

These states are distinct:

- **No separate biowaste collection** (or **No separate collection**) means
  neither Food waste nor Biowaste is collected separately from residual waste.
  It is a statement about the existence of a separate collection.
- **No separate door-to-door biowaste collection** is used only on maps whose
  metric applies to door-to-door service. It also covers catchments that do
  have a separate Biowaste or Food waste collection when that collection uses
  Bring point, Recycling centre, Home-composting, or another non-door-to-door
  system. It is a statement about the applicability of the map metric, not the
  absence of all separate collection.
- **No data** means the relevant collection exists and the map metric applies,
  but its value is unavailable.

APIs should retain the actual collection-system value for a non-door-to-door
collection. A door-to-door-specific renderer may group those values into the
`no_door_to_door` presentation class. It must not rewrite them to
`No separate collection`.
