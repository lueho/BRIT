# Repository Boundaries

BRIT is published as an open-source Django application. Keep the public
repository focused on code, tests, public documentation, and small semantic
assets required to run the app. Development infrastructure and data-management
workflows may exist around the app, but they must not become part of the
published runtime image or public app surface by accident.

## Public App Repository

These files belong in this repository:

- Django apps, migrations, templates, static source files, and committed static
  build outputs required by the web app.
- Tests and fixtures that exercise app behavior without containing production
  or raw research data.
- Public documentation for users, contributors, architecture, and app behavior.
- Small public semantic assets, such as ontology files and controlled
  vocabularies, when they are part of the app's behavior.
- Reproducible contributor tooling, such as the Dockerized asset pipeline and
  public CI checks.

## Internal Data And Operations

Keep these files outside the public app repository, preferably in a private
sibling repository such as `BRIT-data` or `BRIT-ops`:

- Raw source files: PDFs, spreadsheets, GIS datasets, database dumps, and
  downloaded web archives.
- One-off SQL, production repair scripts, QGIS styling helpers, and manual
  backfills.
- Country- or source-specific ETL clients that parse local files and call the
  BRIT API.
- Production deployment overlays, environment files, backup/restore runbooks,
  and monitoring configuration.
- Agent-local configuration, prompts, workflows, and private review notes.

Recommended sibling layout:

```text
BRIT-data/
  src/brit_data_tools/
    clients/
    waste_collection/
    quality/
  data/
    raw/
    interim/
    processed/
    manifests/
  sql/
    one_off/
    archived/
  runbooks/
```

```text
BRIT-ops/
  compose.dev.yml
  compose.prod.yml
  env/
  monitoring/
  runbooks/
  agent/
```

## Boundary Rules

- Keep generic server-side app behavior in Django apps. For example, an API
  import service that validates and writes BRIT models belongs in the app.
- Keep local ETL parsers outside Django management commands. If a tool parses a
  source spreadsheet/PDF and POSTs to the API, it belongs in `BRIT-data`.
- Keep reusable, documented management commands in the app only when they are
  safe for contributors and operators to run in normal app environments.
- Never commit raw data, local `.env` files, production credentials, database
  dumps, or agent-local files.
- Do not add new `scripts/` helpers unless they are public contributor tooling.
  Internal scripts belong in the private data or ops repository.

## Runtime Image Boundary

The runtime Docker image copies the repository build context into `/app`, so
`.dockerignore` is the last line of defense against accidentally packaging
local-only files. Keep `.dockerignore` aligned with `.gitignore`, especially for
raw data, one-off SQL, agent directories, and temporary helper scripts.

## Extracted Import Tooling

The source-specific waste-collection importers and one-off operations SQL have
been extracted to private data/ops tooling. Do not reintroduce source-specific
ETL management commands here. Keep only the generic app API/service in BRIT and
run parser/scraper workflows from `BRIT-data`.

This boundary is intentionally documented as a human/PR-review rule rather than
enforced by a narrow filename allowlist. Simple pattern checks create a false
sense of security: they miss many real boundary violations and overfit to past
incidents. Review new helper infrastructure, data files, operations scripts, and
agent setup explicitly against the rules above.
