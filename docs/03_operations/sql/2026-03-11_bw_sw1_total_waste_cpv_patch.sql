BEGIN;

CREATE TEMP TABLE bw_sw1_cfg AS
SELECT
    (
        SELECT c.id
        FROM maps_catchment c
        JOIN maps_nutsregion n ON n.region_ptr_id = c.region_id
        WHERE n.nuts_id = 'DE1'
        LIMIT 1
    ) AS bw_root_catchment_id,
    (
        SELECT id
        FROM properties_property
        WHERE lower(name) = 'specific waste collected'
        LIMIT 1
    ) AS specific_property_id,
    (
        SELECT id
        FROM properties_property
        WHERE lower(name) = 'total waste collected'
        LIMIT 1
    ) AS total_property_id,
    (
        SELECT id
        FROM properties_unit
        WHERE name = 'kg/(cap.*a)'
        LIMIT 1
    ) AS specific_unit_id,
    (
        SELECT id
        FROM properties_unit
        WHERE name = 'Mg/a'
        LIMIT 1
    ) AS total_unit_id,
    (
        SELECT id
        FROM maps_attribute
        WHERE lower(name) = 'population'
        LIMIT 1
    ) AS population_attribute_id;

SELECT * FROM bw_sw1_cfg;

CREATE TEMP TABLE bw_sw1_bad_manual_cpv AS
WITH RECURSIVE bw_catchments AS (
    SELECT bw_root_catchment_id AS id
    FROM bw_sw1_cfg
    UNION ALL
    SELECT c.id
    FROM maps_catchment c
    JOIN bw_catchments bw ON c.parent_id = bw.id
)
SELECT cpv.*
FROM soilcom_collectionpropertyvalue cpv
JOIN soilcom_collection col ON col.id = cpv.collection_id
JOIN bw_sw1_cfg cfg ON TRUE
WHERE col.catchment_id IN (SELECT id FROM bw_catchments)
  AND cpv.is_derived = FALSE
  AND cpv.property_id = cfg.specific_property_id
  AND cpv.year BETWEEN 2015 AND 2024
  AND cpv.unit_id IN (cfg.specific_unit_id, cfg.total_unit_id);

SELECT
    cpv.year,
    u.name AS unit_name,
    COUNT(*) AS manual_specific_rows
FROM bw_sw1_bad_manual_cpv cpv
JOIN properties_unit u ON u.id = cpv.unit_id
GROUP BY cpv.year, u.name
ORDER BY cpv.year, u.name;

CREATE TEMP TABLE bw_sw1_existing_manual_total AS
SELECT DISTINCT ON (bad.id)
    bad.id AS bad_cpv_id,
    total.id AS total_cpv_id,
    bad.collection_id,
    bad.year
FROM bw_sw1_bad_manual_cpv bad
JOIN soilcom_collectionpropertyvalue total
    ON total.collection_id = bad.collection_id
   AND total.year = bad.year
   AND total.is_derived = FALSE
JOIN bw_sw1_cfg cfg ON TRUE
WHERE total.property_id = cfg.total_property_id
  AND total.id <> bad.id
ORDER BY bad.id, total.lastmodified_at DESC NULLS LAST, total.id DESC;

INSERT INTO soilcom_collectionpropertyvalue_sources (collectionpropertyvalue_id, source_id)
SELECT DISTINCT
    existing_total.total_cpv_id,
    rel.source_id
FROM bw_sw1_existing_manual_total existing_total
JOIN soilcom_collectionpropertyvalue_sources rel
    ON rel.collectionpropertyvalue_id = existing_total.bad_cpv_id
LEFT JOIN soilcom_collectionpropertyvalue_sources already_present
    ON already_present.collectionpropertyvalue_id = existing_total.total_cpv_id
   AND already_present.source_id = rel.source_id
WHERE already_present.id IS NULL;

CREATE TEMP TABLE bw_sw1_candidate_keys AS
SELECT DISTINCT collection_id, year
FROM bw_sw1_bad_manual_cpv;

DELETE FROM soilcom_collectionpropertyvalue derived
USING bw_sw1_candidate_keys keys, bw_sw1_cfg cfg
WHERE derived.collection_id = keys.collection_id
  AND derived.year = keys.year
  AND derived.is_derived = TRUE
  AND derived.property_id IN (cfg.specific_property_id, cfg.total_property_id);

DELETE FROM soilcom_collectionpropertyvalue bad
USING bw_sw1_existing_manual_total existing_total
WHERE bad.id = existing_total.bad_cpv_id;

UPDATE soilcom_collectionpropertyvalue bad
SET property_id = cfg.total_property_id,
    unit_id = cfg.total_unit_id,
    name = CONCAT(col.name, ' ', total_prop.name, ' ', bad.year),
    lastmodified_at = NOW()
FROM bw_sw1_cfg cfg,
     soilcom_collection col,
     properties_property total_prop
WHERE bad.id IN (
        SELECT id FROM bw_sw1_bad_manual_cpv
        EXCEPT
        SELECT bad_cpv_id FROM bw_sw1_existing_manual_total
    )
  AND col.id = bad.collection_id
  AND total_prop.id = cfg.total_property_id;

CREATE TEMP TABLE bw_sw1_fixed_source_totals AS
SELECT DISTINCT ON (cpv.collection_id, cpv.year)
    cpv.id,
    cpv.collection_id,
    cpv.year,
    cpv.average,
    cpv.owner_id,
    cpv.created_by_id,
    cpv.lastmodified_by_id,
    cpv.publication_status,
    cpv.submitted_at,
    cpv.approved_at,
    cpv.approved_by_id
FROM soilcom_collectionpropertyvalue cpv
JOIN bw_sw1_candidate_keys keys
    ON keys.collection_id = cpv.collection_id
   AND keys.year = cpv.year
JOIN bw_sw1_cfg cfg ON TRUE
WHERE cpv.is_derived = FALSE
  AND cpv.property_id = cfg.total_property_id
ORDER BY cpv.collection_id, cpv.year, cpv.lastmodified_at DESC NULLS LAST, cpv.id DESC;

INSERT INTO soilcom_collectionpropertyvalue (
    created_at,
    lastmodified_at,
    name,
    description,
    average,
    standard_deviation,
    year,
    collection_id,
    created_by_id,
    lastmodified_by_id,
    owner_id,
    property_id,
    unit_id,
    publication_status,
    approved_at,
    approved_by_id,
    submitted_at,
    is_derived
)
SELECT
    NOW(),
    NOW(),
    CONCAT(col.name, ' ', specific_prop.name, ' ', src.year),
    '',
    ROUND((src.average * 1000.0 / pop.value)::numeric, 2)::double precision,
    NULL,
    src.year,
    src.collection_id,
    src.created_by_id,
    src.lastmodified_by_id,
    src.owner_id,
    cfg.specific_property_id,
    cfg.specific_unit_id,
    src.publication_status,
    src.approved_at,
    src.approved_by_id,
    src.submitted_at,
    TRUE
FROM bw_sw1_fixed_source_totals src
JOIN bw_sw1_cfg cfg ON TRUE
JOIN soilcom_collection col ON col.id = src.collection_id
JOIN maps_catchment catchment ON catchment.id = col.catchment_id
JOIN properties_property specific_prop ON specific_prop.id = cfg.specific_property_id
JOIN LATERAL (
    SELECT rav.value
    FROM maps_regionattributevalue rav
    WHERE rav.region_id = catchment.region_id
      AND rav.attribute_id = cfg.population_attribute_id
    ORDER BY
        CASE
            WHEN EXTRACT(YEAR FROM rav.date) = src.year THEN 0
            ELSE 1
        END,
        rav.date DESC NULLS LAST,
        rav.id DESC
    LIMIT 1
) pop ON TRUE
WHERE pop.value IS NOT NULL
  AND pop.value > 0
  AND NOT EXISTS (
        SELECT 1
        FROM soilcom_collectionpropertyvalue manual_specific
        WHERE manual_specific.collection_id = src.collection_id
          AND manual_specific.year = src.year
          AND manual_specific.is_derived = FALSE
          AND manual_specific.property_id = cfg.specific_property_id
    );

SELECT
    cpv.year,
    p.name AS property_name,
    u.name AS unit_name,
    cpv.is_derived,
    COUNT(*) AS row_count
FROM soilcom_collectionpropertyvalue cpv
JOIN bw_sw1_candidate_keys keys
    ON keys.collection_id = cpv.collection_id
   AND keys.year = cpv.year
JOIN properties_property p ON p.id = cpv.property_id
JOIN properties_unit u ON u.id = cpv.unit_id
GROUP BY cpv.year, p.name, u.name, cpv.is_derived
ORDER BY cpv.year, p.name, cpv.is_derived, u.name;

SELECT COUNT(*) AS remaining_bad_manual_rows
FROM soilcom_collectionpropertyvalue cpv
JOIN bw_sw1_candidate_keys keys
    ON keys.collection_id = cpv.collection_id
   AND keys.year = cpv.year
JOIN bw_sw1_cfg cfg ON TRUE
WHERE cpv.is_derived = FALSE
  AND cpv.property_id = cfg.specific_property_id;

COMMIT;
