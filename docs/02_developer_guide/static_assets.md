# Static Assets (SCSS → CSS → minified)

BRIT serves **pre-built, committed** static assets. Templates reference the
minified files directly via `{% static %}`. Keeping the compiled output in git
means the production image and Heroku never need a Node toolchain.

In production the release-phase `collectstatic` is handled by
[Collectfasta](https://github.com/jasongi/collectfasta) on top of the S3
manifest storage (`brit.storages.StaticStorage`): it post-processes files —
hashing plus `url()` reference rewriting — in a local in-memory two-pass run,
then uploads only changed files to S3, skipping unchanged ones via cached
checksums. Development and tests use plain `StaticFilesStorage`, where
`collectstatic` just copies files.

**Ops settings** (defined in `brit/settings/heroku.py` only): checksum
metadata lives in a dedicated Redis cache alias (`COLLECTFASTA_CACHE =
"collectfasta"`, 30-day `TIMEOUT`, `MAX_ENTRIES=10000`, keys namespaced
`collectfasta:<bucket>:<location>`). Uploads run synchronously
(`COLLECTFASTA_THREADS = 0`) on purpose: upstream 3.3.5 never consumes the
`pool.map` iterators, so exceptions in worker threads would not propagate and
a failed upload could pass the release silently. `collectstatic
--disable-collectfasta` remains as an escape hatch to the stock command.

## Release deployment (guarded)

Heroku's release phase does not run plain `collectstatic`. The chain is

```
python manage.py collectstatic_safe --noinput --manifest-output /tmp/brit-staticfiles.json && \
  python manage.py verify_staticfiles --manifest /tmp/brit-staticfiles.json
```

`collectstatic_safe` (in `brit/management/commands/`) wraps Collectfasta with
deployment safeguards:

- **Manifest-last atomic publication.** `staticfiles.json` is deferred and
  PUT only after every asset upload, the fresh manifest has been validated,
  and the local receipt file has been written. An asset-upload error
  prevents publication entirely; S3 replaces the manifest atomically and
  only once every referenced object is present.
- **No deletions.** The atomic S3 wrapper turns every `delete()` into a
  no-op and overwrites under exact names (`file_overwrite=True`), so
  publication never removes existing keys — the previous manifest is never
  deleted and old hashed files are retained.
- **Fresh checks, not caches.** The manifest is re-compared against live
  remote bytes, and referenced objects are confirmed via a fresh
  `list_objects_v2` listing over the storage location — objects that are
  missing remotely but hidden by a stale checksum cache fail the release
  closed.
- **Guard rails.** `--clear`, `--no-post-process`, a disabled Collectfasta,
  and `COLLECTFASTA_THREADS != 0` are rejected before any write.

`verify_staticfiles` then re-reads the live `staticfiles.json`, validates
its schema/hash, requires its contents — paths, version and hash — to match
the receipt produced by the same build exactly, and re-lists the bucket to
confirm every referenced object exists. It exits non-zero on any mismatch and is the release gate — the
`/health` endpoint only reports liveness, not asset correctness.

Plain `collectstatic` (or `--disable-collectfasta`) is **not** release-safe:
it publishes the manifest during a normal multi-file upload with no
manifest-last guarantee and no remote verification. It must not replace the
guarded chain in `heroku.yml`.

Because the output is committed, it must always be **reproducible** and **in
sync** with its sources. That is what this pipeline guarantees.

## Pipeline

```
brit/static/scss/*.scss   --(dart-sass)-->  brit/static/css/*.css   --\
                                                                       >--(esbuild --minify)--> *.min.css
any  **/static/**/*.css   ------------------------------------------- /
any  **/static/**/*.js    --(esbuild --minify)--------------------------> *.min.js
```

- **Compile:** `dart-sass` compiles each non-partial `*.scss` under a
  `static/` tree to a sibling `css/` directory (e.g.
  `scss/brit-theme.scss → css/brit-theme.css`, with a source map).
- **Minify:** `esbuild` minifies every source `*.css` (including the compiled
  ones) to `*.min.css`, and every source `*.js` to `*.min.js`.
- **Excluded:** anything under `lib/` (vendored), `*.min.*`, and `*.src.js`
  (unbundled sources). Every other source asset gets a minified twin.

The toolchain is **pinned** in `docker/assets/Dockerfile`
(`sass` + `esbuild`) so developers, AI agents and CI produce byte-identical
output. The build script is `scripts/build_assets.mjs` (Node built-ins only;
it shells out to the pinned CLIs).

## Commands

All commands run in the Dockerized toolchain — no host Node required.

```bash
make assets         # one-shot build of all assets
make assets-watch   # rebuild changed assets on save (live dev feedback)
make assets-check   # rebuild and fail if committed output is stale (CI runs this)
```

Equivalent without make:

```bash
docker compose run --rm assets node scripts/build_assets.mjs [--watch]
```

## Development workflow

1. Edit the **source**: `*.scss`, or a hand-written `*.css` / `*.js`.
   Never edit `*.css` produced from SCSS, and never edit `*.min.*` by hand.
2. Run `make assets-watch` in a terminal. On save it recompiles the affected
   SCSS and re-minifies the changed file (typically well under a second), so a
   browser refresh shows your change.
3. Commit the regenerated artifacts together with your source change.

> **Disable any IDE "Live Sass" / auto-minify watcher.** Editor extensions
> compiled to inconsistent locations with an unpinned compiler, which is what
> caused the previous drift between `scss/`, `css/` and `.min.css`. This
> pipeline is now the single source of truth.

## CI / drift protection

The `assets` GitHub Actions workflow (`.github/workflows/assets.yml`) rebuilds
all assets in the pinned image and runs `git diff --exit-code`. If the
committed output does not match a fresh build, the job fails with a hint to run
`make assets`. This catches both "forgot to rebuild" and "edited a generated
file by hand".

## Adding a new asset

- **New SCSS entry:** add `brit/static/<...>/scss/<name>.scss` (partials are
  prefixed with `_`). It compiles to the sibling `css/` dir automatically.
- **New CSS/JS:** drop the source under any `static/` directory. `make assets`
  generates its `*.min.*` twin. Reference the `.min` file from templates.

_Last updated: 2026-06-04_
