# Waste Collection Controlled Vocabulary & Ontology (Draft)

This directory starts the semantic harmonization layer for the waste collection module.

## Goals

1. Define a stable, versioned controlled vocabulary for waste collection concepts.
2. Define an ontology for the module data model and semantics.
3. Support harmonization of raw data from multiple European countries.

## Current artifacts

- `vocabulary.ttl` — SKOS concept schemes and controlled concepts.
- `ontology.ttl` — OWL ontology draft for core waste-collection classes and properties, with waste semantics modeled directly on `Collection` via `waste_category`, `allowed_materials`, and `forbidden_materials`.
- `shapes/collection_import_record.shacl.ttl` — SHACL draft for import-record validation.
- `mappings/` — source-term crosswalk files (country/language specific).
  - `sweden_raw_term_crosswalk.csv`
  - `germany_brandenburg_raw_term_crosswalk.csv`
  - `netherlands_raw_term_crosswalk.csv`
  - `denmark_raw_term_crosswalk.csv`
  - `belgium_raw_term_crosswalk.csv`
  - `uk_raw_term_crosswalk.csv`
- `export/` — generated machine snapshots from Django data.

The live snapshot now includes controlled lists for additional import domains:

- `collection_frequencies`
- `materials`
- `collection_properties`
- `units`

Country-pack crosswalk files for NL, DK, BE, and UK now include curated seed
mappings for waste categories, collection systems, sorting methods, fee
systems, connection types, and required bin-capacity reference terms.

## How to export the live vocabulary snapshot

Run inside Docker:

```bash
docker compose exec -T web python manage.py export_waste_collection_vocabulary
```

Optional strict mode (fails if country codes have no language mapping):

```bash
docker compose exec -T web python manage.py export_waste_collection_vocabulary --fail-on-unmapped
```

Default output:

- `/app/sources/waste_collection/ontology/export/controlled_vocabulary.json`

## Governance rules (URI contract)

1. Every concept gets a stable URI and MUST NOT be renamed in place.
2. Labels may evolve, IDs/URIs are immutable once released.
3. New country imports must add:
   - language mapping in `sources/waste_collection/vocabulary.py`
   - source crosswalk files under `ontology/mappings/`
   - explicit `target_label` values in crosswalk CSV rows
4. Vocabulary version increases in `sources/waste_collection/vocabulary.py`.

The exported vocabulary snapshot includes a machine-readable `semantic_contract`
object with:

- canonical identifier field: `target_concept_uri`
- concept lifecycle statuses: `active`, `deprecated`, `superseded`
- controlled change types: `new_concept`, `label_only`, `deprecate`,
  `semantic_split`, `semantic_merge`
- explicit equivalence policy requiring agent matching by concept URI

## Equivalence modeling for harmonization

- Canonical source of truth is always the concept URI (`target_concept_uri`).
- Use `skos:prefLabel` for the preferred label in each language.
- Use `skos:altLabel` for language-specific synonyms (e.g., `Restmüll`, `Hausmüll`).
- Use `skos:hiddenLabel` for search/index variants (e.g., ASCII forms like `Hausmuell`).
- Crosswalk rows should map each raw source term to the same canonical
  `target_concept_uri` so research agents can treat all variants as equivalent.

## Agent interpretation rules

Recurring interpretation rules that affect collection research, imports, or review
should be promoted here instead of remaining only in chat memory.

- **Biowaste with home-composter exception**
  If an official source states that biowaste participation is obligatory except
  for households that compost at home, map the collection to
  `Collection.connection_type = MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION`.

- **Opt-in biowaste service**
  If an official source frames the biowaste bin as an orderable or requestable
  service and does not also state a mandatory participation rule, map the
  collection to `Collection.connection_type = VOLUNTARY`.

- **Combined food-waste and green-waste path**
  If one source-supported collection path jointly accepts food waste and green
  waste, represent it as the parent `Biowaste` collection with
  `allowed_materials`, `forbidden_materials`, and description evidence. Create
  separate `Food waste` or `Green waste` records only when sources establish a
  genuinely distinct path, such as a different collection system, access route,
  participation rule, fee logic, frequency, or validity period.

- **Residual waste material lists**
  For ordinary `Residual waste` collections, `allowed_materials` and
  `forbidden_materials` may be omitted unless source evidence shows a special
  inclusion or exclusion scope that must be modeled explicitly.

## Next planned steps

1. Add SHACL-enforced URI integrity checks for crosswalk `target_concept_uri` values.
2. Add multilingual labels and definitions for all concepts.
3. Wire SHACL validation into importer pre-processing.
4. Expand country-pack mappings with frequency/material terms and regional variants.
