-- === CREATE: District-level Green Waste ACPVs for Mecklenburg-Vorpommern ===
--
-- Two-dimensional aggregation:
--   1. By region: Nordwestmecklenburg = NWM AWB (3613) + Wismar (3206)
--   2. By collection system: all green waste collections within each region
--
-- For single-region districts, the ACPV links to that region's base collection(s).
-- For NWM (multi-region), the ACPV links to collections across both sub-regions.
--
-- Values are derived from existing CPVs where available.
-- NWM+Wismar values are NULL (to be filled from MV waste atlas).

BEGIN;

-- === STEP 1: Delete all existing green waste ACPVs for MV districts ===
DELETE FROM waste_collection_aggregatedcollectionpropertyvalue_sources
WHERE aggregatedcollectionpropertyvalue_id IN (
    SELECT id FROM waste_collection_aggregatedcollectionpropertyvalue
    WHERE name LIKE '%Green waste%'
      OR id IN (
          SELECT acpv.id
          FROM waste_collection_aggregatedcollectionpropertyvalue acpv
          JOIN waste_collection_aggregatedcollectionpropertyvalue_collections ac ON acpv.id = ac.aggregatedcollectionpropertyvalue_id
          JOIN waste_collection_collection c ON ac.collection_id = c.id
          WHERE c.waste_category_id = 2
            AND c.catchment_id IN (115, 263, 183, 3613, 170, 145, 566, 213, 3206)
      )
);

DELETE FROM waste_collection_aggregatedcollectionpropertyvalue_collections
WHERE aggregatedcollectionpropertyvalue_id IN (
    SELECT id FROM waste_collection_aggregatedcollectionpropertyvalue
    WHERE name LIKE '%Green waste%'
      OR id IN (
          SELECT acpv.id
          FROM waste_collection_aggregatedcollectionpropertyvalue acpv
          JOIN waste_collection_aggregatedcollectionpropertyvalue_collections ac ON acpv.id = ac.aggregatedcollectionpropertyvalue_id
          JOIN waste_collection_collection c ON ac.collection_id = c.id
          WHERE c.waste_category_id = 2
            AND c.catchment_id IN (115, 263, 183, 3613, 170, 145, 566, 213, 3206)
      )
);

DELETE FROM waste_collection_aggregatedcollectionpropertyvalue
WHERE name LIKE '%Green waste%'
   OR id IN (
      SELECT acpv.id
      FROM waste_collection_aggregatedcollectionpropertyvalue acpv
      JOIN waste_collection_aggregatedcollectionpropertyvalue_collections ac ON acpv.id = ac.aggregatedcollectionpropertyvalue_id
      JOIN waste_collection_collection c ON ac.collection_id = c.id
      WHERE c.waste_category_id = 2
        AND c.catchment_id IN (115, 263, 183, 3613, 170, 145, 566, 213, 3206)
  );

-- === STEP 2: Create ACPVs for each district and year ===
-- For each district: property_id=1 (specific, kg/cap/year) and property_id=9 (total, Mg/year)
-- Years: 2017-2024

CREATE TEMP TABLE tmp_acpv_defs (
    district_name TEXT,
    year INTEGER,
    property_id INTEGER,
    unit_id INTEGER,
    average NUMERIC,
    collection_ids BIGINT[]
);

-- === Landkreis Rostock (115): single system (Recycling centre 2022) ===
INSERT INTO tmp_acpv_defs
SELECT 'Landkreis Rostock', y.year, 9, 8, cpv.average, ARRAY[527::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 527 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Landkreis Rostock', y.year, 1, 2, cpv.average, ARRAY[527::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 527 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Ludwigslust-Parchim (263): single system (Recycling centre 2022) ===
INSERT INTO tmp_acpv_defs
SELECT 'Ludwigslust-Parchim', y.year, 9, 8, cpv.average, ARRAY[28125::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 28125 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Ludwigslust-Parchim', y.year, 1, 2, cpv.average, ARRAY[28125::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 28125 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Mecklenburgische Seenplatte (183): single system (Recycling centre 2024) ===
INSERT INTO tmp_acpv_defs
SELECT 'Mecklenburgische Seenplatte', y.year, 9, 8, cpv.average, ARRAY[16770::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 16770 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Mecklenburgische Seenplatte', y.year, 1, 2, cpv.average, ARRAY[16770::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 16770 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Nordwestmecklenburg (3613 + 3206): NWM Recycling + Wismar Recycling ===
-- No individual CPV data; values to be filled from MV atlas
INSERT INTO tmp_acpv_defs
SELECT 'Nordwestmecklenburg', y.year, 9, 8, NULL, ARRAY[28126::bigint, 28158::bigint]
FROM generate_series(2017, 2024) AS y(year);

INSERT INTO tmp_acpv_defs
SELECT 'Nordwestmecklenburg', y.year, 1, 2, NULL, ARRAY[28126::bigint, 28158::bigint]
FROM generate_series(2017, 2024) AS y(year);

-- === Rostock city (170): Door to door 2022 + On demand 2022 + Recycling 2022 ===
-- Only Door to door has CPV data
INSERT INTO tmp_acpv_defs
SELECT 'Rostock', y.year, 9, 8, cpv.average, ARRAY[526::bigint, 524::bigint, 525::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 526 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Rostock', y.year, 1, 2, cpv.average, ARRAY[526::bigint, 524::bigint, 525::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 526 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Schwerin (145): Recycling centre 2024 ===
INSERT INTO tmp_acpv_defs
SELECT 'Schwerin', y.year, 9, 8, cpv.average, ARRAY[9746::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 9746 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Schwerin', y.year, 1, 2, cpv.average, ARRAY[9746::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 9746 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Vorpommern-Greifswald (566): Door to door 2022 + Recycling 2022 ===
-- Only Door to door has CPV data
INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Greifswald', y.year, 9, 8, cpv.average, ARRAY[1194::bigint, 1195::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 1194 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Greifswald', y.year, 1, 2, cpv.average, ARRAY[1194::bigint, 1195::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 1194 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Vorpommern-Rügen (213): Recycling centre 2024 ===
INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Rügen', y.year, 9, 8, cpv.average, ARRAY[9834::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 9834 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Rügen', y.year, 1, 2, cpv.average, ARRAY[9834::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv ON cpv.collection_id = 9834 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === STEP 3: Insert ACPVs ===
INSERT INTO waste_collection_aggregatedcollectionpropertyvalue
    (name, description, average, year, property_id, unit_id, publication_status,
     created_at, created_by_id, lastmodified_at, lastmodified_by_id, owner_id)
SELECT 
    d.district_name || ' Green waste ' || CASE WHEN d.property_id = 1 THEN 'specific' ELSE 'total' END || ' ' || d.year,
    'District-level aggregate for ' || d.district_name || ' green waste (' || d.year || ')',
    COALESCE(d.average, 0), d.year, d.property_id, d.unit_id, 'published',
    NOW(), 1, NOW(), 1, 1155
FROM tmp_acpv_defs d
ON CONFLICT DO NOTHING;

-- === STEP 4: Link ACPVs to collections ===
INSERT INTO waste_collection_aggregatedcollectionpropertyvalue_collections
    (aggregatedcollectionpropertyvalue_id, collection_id)
SELECT acpv.id, cid
FROM tmp_acpv_defs d
JOIN waste_collection_aggregatedcollectionpropertyvalue acpv
    ON acpv.name = d.district_name || ' Green waste ' || CASE WHEN d.property_id = 1 THEN 'specific' ELSE 'total' END || ' ' || d.year
    AND acpv.year = d.year AND acpv.property_id = d.property_id AND acpv.unit_id = d.unit_id,
LATERAL UNNEST(d.collection_ids) AS cid
JOIN waste_collection_collection c ON c.id = cid
ON CONFLICT DO NOTHING;

-- === STEP 5: Link MV waste atlas sources ===
INSERT INTO waste_collection_aggregatedcollectionpropertyvalue_sources
    (aggregatedcollectionpropertyvalue_id, source_id)
SELECT acpv.id, s.id
FROM waste_collection_aggregatedcollectionpropertyvalue acpv
JOIN tmp_acpv_defs d ON acpv.name = d.district_name || ' Green waste ' || CASE WHEN d.property_id = 1 THEN 'specific' ELSE 'total' END || ' ' || d.year
JOIN bibliography_source s ON s.title LIKE 'Daten zur Abfallwirtschaft ' || d.year || ' in Mecklenburg-Vorpommern%'
ON CONFLICT DO NOTHING;

DROP TABLE tmp_acpv_defs;

COMMIT;
