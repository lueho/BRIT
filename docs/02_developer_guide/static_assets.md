# Static Assets (SCSS → CSS → minified)

BRIT serves **pre-built, committed** static assets. Templates reference the
minified files directly via `{% static %}` (Django uses plain
`StaticFilesStorage`, so `collectstatic` just copies them — there is no
runtime asset processing). Keeping the compiled output in git means the
production image and Heroku never need a Node toolchain.

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
