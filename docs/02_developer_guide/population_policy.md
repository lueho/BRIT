# Population Statistics Policy

Population is not one interchangeable number per region and year. BRIT keeps
source observations separate from their use in calculations. This page is the
authoritative population policy; provider tooling and developer instructions
should link here rather than duplicate it.

## Choose The Right Statistic

- Standardized annual waste-per-resident calculations use **calendar-year
  average population** for the same year and catchment.
- A population stock, such as population on 1 January, remains a distinct
  **point-in-time** observation. It must not silently substitute for an average.
- Preserve source-reported waste rates as reported. Do not overwrite them with
  BRIT's preferred normalization.
- Household/property connection rates require their own denominators, not
  automatically resident population.

Missing suitable data means an unavailable calculation, not a different year,
another geographic level or an unlabelled fallback. A future stock-based
fallback must be explicitly requested and visibly identified; automatic annual
waste conversion does not offer one.

## Match And Preserve Source Meaning

Use the existing structured population models, import API and resolver.
Population observations are normalized to persons; unsupported units are
rejected. Missing data is not zero. A genuine zero population can be stored,
but cannot be used to produce a per-resident waste rate.

A geographic code alone does not establish compatible boundaries. An explicit
NUTS/LAU vintage must match; a different held vintage is not a substitute.
Without a version hint, imports use the current NUTS vintage or an unambiguous
LAU code. Providers must qualify the geography before importing: neither a
unique match nor a map-release year proves the population reference date.
Boundary transfers require separately verified correspondence, not a guessed
match.

Custom-region sums require all components for the requested year and temporal
basis, without overlapping territories. Different datasets remain visible as
mixed provenance; compatibility of definitions and census bases still needs
source review. Do not manufacture an annual average by combining incompatible
census series.

While a dataset contains observations, its provider, source code, temporal basis,
geographic scope/vintage and source unit cannot be relabelled by an import.
A different definition needs a different dataset slug. Ordinary releases of
the same series may revise observations under a new import run.

## Keep Results Reproducible

Official provisional and estimated observations may be used, but their quality
and raw flags must remain visible in provenance. Publication status is not a
claim that a statistical estimate is final.

New persisted derived waste values retain a snapshot of their formula, source
CPV input, population value and contributing observations/releases in their
existing description field. Published or archived derived results are not
automatically regenerated or deleted when inputs change; replacement requires
explicit review. Editable derived results may be recalculated.

This is not a new immutable statistics archive. Import runs and input snapshots
provide basic traceability; retention of original source downloads remains the
provider's responsibility. Legacy results are not retroactively certified or
rewritten by this policy. Legacy population attributes with an unknown basis
remain available for explicit compatibility reads, not automatic annual waste
conversion.

## Development And Tests

BRIT owns this policy and provider-neutral validation/selection. BRIT-data owns
source acquisition and provider-specific interpretation. Eurostat is the common
regional baseline; qualified official national/local sources provide finer
detail. GISCO boundaries are useful geographic references, not automatic
demographic authority.

When changing imports, selection or annual waste conversion, run the relevant
Django tests in Docker through the isolated worktree wrapper:

```sh
brit-worktree-test <task> -- maps.population.tests \
  sources.waste_collection.tests.test_derived_values
```

The existing CI test job discovers these regression tests; no separate policy
framework is required. Extend tests for demonstrated gaps, rather than adding a
parallel resolver or generic statistics infrastructure. Unit tests cannot
establish that an external source's claimed definitions are truthful.
