-- One-off data fix: Correct source 9404 (Hertel KREIS research report)
-- Created: 2026-09-11
-- Affected tables: bibliography_source, bibliography_sourceauthor
-- Expected outcome: Source 9404 metadata corrected from malformed "Hertel, Saskia (2019)"
--   to the actual 2018 TUHH KREIS research report, with SourceAuthor links to
--   Saskia Hertel (ID 17) and Ina Körner (ID 11).
--
-- Research source: https://doi.org/10.15480/882.1585
--   Title: Nutzung regionaler abfall- und abwasserstämmiger Bioressourcen am
--          Beispiel des Hamburger Demonstrationsvorhabens „Jenfelder Au“ :
--          Inventur, Lagerung, Aufbereitung, Vergärung und Gärrestverwertung
--   Year: 2018
--   Type: Working Paper (research report)
--   Authors: Hertel, Saskia; Körner, Ina
--   DOI: 10.15480/882.1585
--   URL: https://tore.tuhh.de/entities/publication/4fc3f78d-1279-4ad7-b1d7-d2f0edfc56d1

BEGIN;

-- 1. Correct source 9404 metadata
UPDATE bibliography_source
SET
    title = 'Nutzung regionaler abfall- und abwasserstämmiger Bioressourcen am Beispiel des Hamburger Demonstrationsvorhabens „Jenfelder Au“ : Inventur, Lagerung, Aufbereitung, Vergärung und Gärrestverwertung',
    year = 2018,
    type = 'custom',
    doi = '10.15480/882.1585',
    url = 'https://tore.tuhh.de/entities/publication/4fc3f78d-1279-4ad7-b1d7-d2f0edfc56d1',
    citation_key = 'Hertel & Körner 2018'
WHERE id = 9404;

-- 2. Add SourceAuthor links (Hertel at position 1, Körner at position 2)
INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (9404, 17, 1)
ON CONFLICT DO NOTHING;

INSERT INTO bibliography_sourceauthor (source_id, author_id, position)
VALUES (9404, 11, 2)
ON CONFLICT DO NOTHING;

COMMIT;

-- Verification queries
-- SELECT id, title, year, type, doi, citation_key, url FROM bibliography_source WHERE id = 9404;
-- SELECT sa.source_id, sa.author_id, sa.position, a.first_names, a.last_names
--   FROM bibliography_sourceauthor sa
--   JOIN bibliography_author a ON a.id = sa.author_id
--   WHERE sa.source_id = 9404 ORDER BY sa.position;
