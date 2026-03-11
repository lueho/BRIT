BEGIN;

CREATE TEMP TABLE bw_sw1_capacity_rows (
    catchment_name text,
    nuts_or_lau_id text,
    collection_system_name text,
    waste_category_name text,
    valid_from date,
    min_bin_size numeric,
    required_bin_capacity_reference text
);

INSERT INTO bw_sw1_capacity_rows (
    catchment_name,
    nuts_or_lau_id,
    collection_system_name,
    waste_category_name,
    valid_from,
    min_bin_size,
    required_bin_capacity_reference
) VALUES
    ('Catchment of Landratsamt Reutlingen - Abfallentsorgung', '', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Catchment of Landratsamt Reutlingen - Abfallentsorgung', '', 'Door to door', 'Residual waste', '2024-01-01', 140.0, NULL),
    ('Catchment of Müllabfuhrzweckverband Rielasingen-Worblingen (MZV)', '', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Catchment of Müllabfuhrzweckverband Rielasingen-Worblingen (MZV)', '', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Aach, Stadt (08335001)', '08335001', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Aach, Stadt (08335001)', '08335001', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Allensbach (08335002)', '08335002', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Allensbach (08335002)', '08335002', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Büsingen am Hochrhein (08335015)', '08335015', 'Door to door', 'Biowaste', '2024-01-01', 240.0, NULL),
    ('Büsingen am Hochrhein (08335015)', '08335015', 'Door to door', 'Residual waste', '2024-01-01', 17.0, NULL),
    ('Eigeltingen (08335021)', '08335021', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Eigeltingen (08335021)', '08335021', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Gaienhofen (08335025)', '08335025', 'Door to door', 'Biowaste', '2024-01-01', 40.0, NULL),
    ('Gaienhofen (08335025)', '08335025', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Konstanz, Universitätsstadt (08335043)', '08335043', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Konstanz, Universitätsstadt (08335043)', '08335043', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Moos (08335055)', '08335055', 'Door to door', 'Biowaste', '2024-01-01', 40.0, NULL),
    ('Moos (08335055)', '08335055', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Mühlingen (08335057)', '08335057', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Mühlingen (08335057)', '08335057', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Öhningen (08335061)', '08335061', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Öhningen (08335061)', '08335061', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Radolfzell am Bodensee, Stadt (08335063)', '08335063', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Radolfzell am Bodensee, Stadt (08335063)', '08335063', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Reichenau (08335066)', '08335066', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Reichenau (08335066)', '08335066', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Singen (Hohentwiel), Stadt (08335075)', '08335075', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Singen (Hohentwiel), Stadt (08335075)', '08335075', 'Door to door', 'Residual waste', '2024-01-01', 120.0, NULL),
    ('Steißlingen (08335077)', '08335077', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Steißlingen (08335077)', '08335077', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Stockach, Stadt (08335079)', '08335079', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Stockach, Stadt (08335079)', '08335079', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Tengen, Stadt (08335080)', '08335080', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Tengen, Stadt (08335080)', '08335080', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Volkertshausen (08335081)', '08335081', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Volkertshausen (08335081)', '08335081', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Hohenfels (08335096)', '08335096', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Hohenfels (08335096)', '08335096', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Mühlhausen-Ehingen (08335097)', '08335097', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Mühlhausen-Ehingen (08335097)', '08335097', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Bodman-Ludwigshafen (08335098)', '08335098', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Bodman-Ludwigshafen (08335098)', '08335098', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Orsingen-Nenzingen (08335099)', '08335099', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Orsingen-Nenzingen (08335099)', '08335099', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Metzingen, Stadt (08415050)', '08415050', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Metzingen, Stadt (08415050)', '08415050', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Pfullingen, Stadt (08415059)', '08415059', 'Door to door', 'Biowaste', '2024-01-01', 140.0, NULL),
    ('Pfullingen, Stadt (08415059)', '08415059', 'Door to door', 'Residual waste', '2024-01-01', 140.0, NULL),
    ('Reutlingen, Stadt (08415061)', '08415061', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Reutlingen, Stadt (08415061)', '08415061', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Esslingen (DE113)', 'DE113', 'Door to door', 'Residual waste', '2024-01-01', NULL, 'person'),
    ('Main-Tauber-Kreis (DE11B)', 'DE11B', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Freiburg im Breisgau, Stadtkreis (DE131)', 'DE131', 'Door to door', 'Residual waste', '2024-01-01', 35.0, NULL),
    ('Waldshut (DE13A)', 'DE13A', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Waldshut (DE13A)', 'DE13A', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Tübingen, Landkreis (DE142)', 'DE142', 'Door to door', 'Biowaste', '2024-01-01', 40.0, NULL),
    ('Tübingen, Landkreis (DE142)', 'DE142', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Zollernalbkreis (DE143)', 'DE143', 'Door to door', 'Biowaste', '2024-01-01', 80.0, NULL),
    ('Zollernalbkreis (DE143)', 'DE143', 'Door to door', 'Residual waste', '2024-01-01', 80.0, NULL),
    ('Ulm, Stadtkreis (DE144)', 'DE144', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Ulm, Stadtkreis (DE144)', 'DE144', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Alb-Donau-Kreis (DE145)', 'DE145', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Alb-Donau-Kreis (DE145)', 'DE145', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Biberach (DE146)', 'DE146', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Bodenseekreis (DE147)', 'DE147', 'Door to door', 'Biowaste', '2024-01-01', 60.0, NULL),
    ('Bodenseekreis (DE147)', 'DE147', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL),
    ('Ravensburg (DE148)', 'DE148', 'Door to door', 'Biowaste', '2024-01-01', 40.0, NULL),
    ('Ravensburg (DE148)', 'DE148', 'Door to door', 'Residual waste', '2024-01-01', 40.0, NULL),
    ('Sigmaringen (DE149)', 'DE149', 'Door to door', 'Residual waste', '2024-01-01', 60.0, NULL);

CREATE TEMP TABLE bw_sw1_capacity_keys AS
SELECT DISTINCT
    catchment_name,
    nuts_or_lau_id,
    collection_system_name,
    waste_category_name,
    valid_from
FROM bw_sw1_capacity_rows;

SELECT COUNT(*) AS workbook_collection_keys
FROM bw_sw1_capacity_keys;

CREATE TEMP TABLE bw_sw1_target_collections AS
SELECT
    c.id AS collection_id,
    catchment.name AS catchment_name,
    COALESCE(nuts.nuts_id, lau.lau_id, '') AS nuts_or_lau_id,
    cs.name AS collection_system_name,
    wc.name AS waste_category_name,
    c.valid_from,
    c.min_bin_size,
    c.required_bin_capacity_reference
FROM soilcom_collection c
JOIN maps_catchment catchment ON catchment.id = c.catchment_id
LEFT JOIN maps_nutsregion nuts ON nuts.region_ptr_id = catchment.region_id
LEFT JOIN maps_lauregion lau ON lau.region_ptr_id = catchment.region_id
JOIN soilcom_collectionsystem cs ON cs.id = c.collection_system_id
JOIN soilcom_wastecategory wc ON wc.id = c.waste_category_id
JOIN bw_sw1_capacity_keys keys
    ON cs.name = keys.collection_system_name
   AND wc.name = keys.waste_category_name
   AND c.valid_from = keys.valid_from
   AND (
        (keys.nuts_or_lau_id <> '' AND COALESCE(nuts.nuts_id, lau.lau_id, '') = keys.nuts_or_lau_id)
        OR (keys.nuts_or_lau_id = '' AND catchment.name = keys.catchment_name)
   );

SELECT COUNT(*) AS matched_collections
FROM bw_sw1_target_collections;

SELECT
    keys.catchment_name,
    keys.nuts_or_lau_id,
    keys.collection_system_name,
    keys.waste_category_name,
    keys.valid_from
FROM bw_sw1_capacity_keys keys
LEFT JOIN bw_sw1_target_collections target
    ON target.collection_system_name = keys.collection_system_name
   AND target.waste_category_name = keys.waste_category_name
   AND target.valid_from = keys.valid_from
   AND (
        (keys.nuts_or_lau_id <> '' AND target.nuts_or_lau_id = keys.nuts_or_lau_id)
        OR (keys.nuts_or_lau_id = '' AND target.catchment_name = keys.catchment_name)
   )
WHERE target.collection_id IS NULL
ORDER BY
    keys.valid_from,
    keys.nuts_or_lau_id,
    keys.catchment_name,
    keys.collection_system_name,
    keys.waste_category_name;

CREATE TEMP TABLE bw_sw1_capacity_rows_resolved AS
SELECT DISTINCT
    target.collection_id,
    rows.min_bin_size,
    rows.required_bin_capacity_reference
FROM bw_sw1_capacity_rows rows
JOIN bw_sw1_target_collections target
    ON target.collection_system_name = rows.collection_system_name
   AND target.waste_category_name = rows.waste_category_name
   AND target.valid_from = rows.valid_from
   AND (
        (rows.nuts_or_lau_id <> '' AND target.nuts_or_lau_id = rows.nuts_or_lau_id)
        OR (rows.nuts_or_lau_id = '' AND target.catchment_name = rows.catchment_name)
   );

SELECT
    COUNT(*) FILTER (WHERE min_bin_size IS NOT NULL) AS rows_with_min_bin_size,
    COUNT(*) FILTER (WHERE required_bin_capacity_reference IS NOT NULL) AS rows_with_required_bin_capacity_reference
FROM bw_sw1_capacity_rows_resolved;

SELECT
    COUNT(*) FILTER (
        WHERE resolved.min_bin_size IS NOT NULL
          AND collection.min_bin_size IS NULL
    ) AS min_bin_size_missing_before,
    COUNT(*) FILTER (
        WHERE resolved.required_bin_capacity_reference IS NOT NULL
          AND COALESCE(collection.required_bin_capacity_reference, '') = ''
    ) AS required_bin_capacity_reference_missing_before
FROM bw_sw1_capacity_rows_resolved resolved
JOIN soilcom_collection collection ON collection.id = resolved.collection_id;

UPDATE soilcom_collection collection
SET min_bin_size = CASE
        WHEN resolved.min_bin_size IS NOT NULL AND collection.min_bin_size IS NULL
            THEN resolved.min_bin_size
        ELSE collection.min_bin_size
    END,
    required_bin_capacity_reference = CASE
        WHEN resolved.required_bin_capacity_reference IS NOT NULL
             AND COALESCE(collection.required_bin_capacity_reference, '') = ''
            THEN resolved.required_bin_capacity_reference
        ELSE collection.required_bin_capacity_reference
    END
FROM bw_sw1_capacity_rows_resolved resolved
WHERE collection.id = resolved.collection_id
  AND (
        (resolved.min_bin_size IS NOT NULL AND collection.min_bin_size IS NULL)
        OR (
            resolved.required_bin_capacity_reference IS NOT NULL
            AND COALESCE(collection.required_bin_capacity_reference, '') = ''
        )
  );

SELECT
    COUNT(*) FILTER (
        WHERE resolved.min_bin_size IS NOT NULL
          AND collection.min_bin_size IS NULL
    ) AS min_bin_size_missing_after,
    COUNT(*) FILTER (
        WHERE resolved.required_bin_capacity_reference IS NOT NULL
          AND COALESCE(collection.required_bin_capacity_reference, '') = ''
    ) AS required_bin_capacity_reference_missing_after
FROM bw_sw1_capacity_rows_resolved resolved
JOIN soilcom_collection collection ON collection.id = resolved.collection_id;

COMMIT;
