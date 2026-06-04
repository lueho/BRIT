-- === CREATE: District-level Green Waste ACPVs for Mecklenburg-Vorpommern ===
--
-- Creates Aggregated Collection Property Values for each district/year,
-- linking all green waste collection systems for that district and year.
-- Values are derived from existing CPV data where available.
--
-- Districts covered:
--   115  Landkreis Rostock
--   263  Ludwigslust-Parchim
--   183  Mecklenburgische Seenplatte
--   3613 NWM AWB
--   170  Rostock city
--   145  Schwerin
--   566  Vorpommern-Greifswald
--   213  Vorpommern-Rügen
--   3206 Wismar

BEGIN;

-- === STEP 1: Delete all existing green waste ACPVs for MV districts ===
-- This ensures a clean slate and removes any duplicates or erroneous ACPVs.

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
-- For each district, we create ACPVs for property_id=1 (specific, kg/cap/year)
-- and property_id=9 (total, tonnes/year) for years 2017-2024.
--
-- Value derivation:
-- - For single-system districts: use the collection's CPV
-- - For multi-system districts where only one has data: use that system's CPV
-- - For districts with no CPV data: NULL (to be filled later from MV atlas)

-- Create a temporary table to hold the ACPV definitions
CREATE TEMP TABLE tmp_acpv_defs (
    district_name TEXT,
    year INTEGER,
    property_id INTEGER,
    unit_id INTEGER,
    average NUMERIC,
    collection_ids BIGINT[]
);

-- === Landkreis Rostock (115): single system (Recycling) ===
INSERT INTO tmp_acpv_defs
SELECT 'Landkreis Rostock', y.year, 9, 8, cpv.average, ARRAY[16768::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 527 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Landkreis Rostock', y.year, 1, 2, cpv.average, ARRAY[16768::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 527 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Ludwigslust-Parchim (263): single system (Recycling) ===
INSERT INTO tmp_acpv_defs
SELECT 'Ludwigslust-Parchim', y.year, 9, 8, cpv.average, ARRAY[9812::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 28125 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Ludwigslust-Parchim', y.year, 1, 2, cpv.average, ARRAY[9812::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 28125 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Mecklenburgische Seenplatte (183): single system (Recycling) ===
INSERT INTO tmp_acpv_defs
SELECT 'Mecklenburgische Seenplatte', y.year, 9, 8, cpv.average, ARRAY[16770::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 16770 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Mecklenburgische Seenplatte', y.year, 1, 2, cpv.average, ARRAY[16770::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 16770 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === NWM AWB (3613): single system (Recycling), no CPV data ===
INSERT INTO tmp_acpv_defs
SELECT 'Nordwestmecklenburg', y.year, 9, 8, NULL, ARRAY[28191::bigint]
FROM generate_series(2017, 2024) AS y(year);

INSERT INTO tmp_acpv_defs
SELECT 'Nordwestmecklenburg', y.year, 1, 2, NULL, ARRAY[28191::bigint]
FROM generate_series(2017, 2024) AS y(year);

-- === Rostock city (170): multiple systems (Door to door + On demand + Recycling)
-- Only Door to door has CPV data
INSERT INTO tmp_acpv_defs
SELECT 'Rostock', y.year, 9, 8, cpv.average, ARRAY[9754::bigint, 9755::bigint, 9753::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 526 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Rostock', y.year, 1, 2, cpv.average, ARRAY[9754::bigint, 9755::bigint, 9753::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 526 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Schwerin (145): multiple systems (Door to door + Recycling)
-- Only Recycling has CPV data
INSERT INTO tmp_acpv_defs
SELECT 'Schwerin', y.year, 9, 8, cpv.average, ARRAY[9746::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 9746 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Schwerin', y.year, 1, 2, cpv.average, ARRAY[9746::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 9746 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Vorpommern-Greifswald (566): multiple systems (Door to door + Recycling)
-- Only Door to door has CPV data
INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Greifswald', y.year, 9, 8, cpv.average, ARRAY[9842::bigint, 9840::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 1194 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Greifswald', y.year, 1, 2, cpv.average, ARRAY[9842::bigint, 9840::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 1194 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Vorpommern-Rügen (213): single system (Recycling) ===
INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Rügen', y.year, 9, 8, cpv.average, ARRAY[9834::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 9834 AND cpv.property_id = 9 AND cpv.year = y.year;

INSERT INTO tmp_acpv_defs
SELECT 'Vorpommern-Rügen', y.year, 1, 2, cpv.average, ARRAY[9834::bigint]
FROM generate_series(2017, 2024) AS y(year)
LEFT JOIN waste_collection_collectionpropertyvalue cpv
    ON cpv.collection_id = 9834 AND cpv.property_id = 1 AND cpv.year = y.year;

-- === Wismar (3206): multiple systems (On demand + Recycling), no CPV data ===
INSERT INTO tmp_acpv_defs
SELECT 'Wismar', y.year, 9, 8, NULL, ARRAY[9756::bigint, 9757::bigint]
FROM generate_series(2017, 2024) AS y(year);

INSERT INTO tmp_acpv_defs
SELECT 'Wismar', y.year, 1, 2, NULL, ARRAY[9756::bigint, 9757::bigint]
FROM generate_series(2017, 2024) AS y(year);

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
    AND acpv.year = d.year
    AND acpv.property_id = d.property_id
    AND acpv.unit_id = d.unit_id,
LATERAL UNNEST(d.collection_ids) AS cid
JOIN waste_collection_collection c ON c.id = cid
ON CONFLICT DO NOTHING;

-- === STEP 5: Link MV waste atlas sources to ACPVs ===
INSERT INTO waste_collection_aggregatedcollectionpropertyvalue_sources
    (aggregatedcollectionpropertyvalue_id, source_id)
SELECT acpv.id, s.id
FROM waste_collection_aggregatedcollectionpropertyvalue acpv
JOIN tmp_acpv_defs d ON acpv.name = d.district_name || ' Green waste ' || CASE WHEN d.property_id = 1 THEN 'specific' ELSE 'total' END || ' ' || d.year
CROSS JOIN bibliography_source s
WHERE s.title LIKE 'Daten zur Abfallwirtschaft ' || d.year || ' in Mecklenburg-Vorpommern%'
ON CONFLICT DO NOTHING;

DROP TABLE tmp_acpv_defs;

COMMIT;
