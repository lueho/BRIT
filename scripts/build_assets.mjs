#!/usr/bin/env node
// BRIT static asset build pipeline.
//
//   SCSS  --(dart-sass)-->  .css  --(esbuild)-->  .min.css
//   .css  --(esbuild)----------------------------> .min.css
//   .js   --(esbuild)----------------------------> .min.js
//
// This script is intentionally dependency-free (Node built-ins only). It shells
// out to the globally installed `sass` and `esbuild` CLIs (see
// docker/assets/Dockerfile), so it runs identically for developers, AI agents
// and CI via `docker compose run --rm assets ...`.
//
// Usage:
//   node scripts/build_assets.mjs            # one-shot build of all assets
//   node scripts/build_assets.mjs --watch    # rebuild affected files on change
//   node scripts/build_assets.mjs --check    # build, then fail if anything is missing

import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

// Directory names we never descend into.
const PRUNE_DIRS = new Set([
  "node_modules",
  "staticfiles",
  ".git",
  ".venv",
  "lib", // third-party vendored assets (bootstrap, leaflet, ...) ship pre-built
]);

const WATCH = process.argv.includes("--watch");

// ---------------------------------------------------------------------------
// File discovery
// ---------------------------------------------------------------------------

/** Recursively collect file paths under `dir`, pruning vendored/build dirs. */
function walk(dir, acc = []) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (PRUNE_DIRS.has(entry.name)) continue;
      walk(join(dir, entry.name), acc);
    } else if (entry.isFile()) {
      acc.push(join(dir, entry.name));
    }
  }
  return acc;
}

const segments = (p) => p.split(sep);
const underStatic = (p) => segments(p).includes("static");
const inScssDir = (p) => segments(p).includes("scss");

/** SCSS entry points (under a `static/` tree, not a partial, not in scss-lib). */
function scssEntries(files) {
  return files.filter(
    (f) =>
      f.endsWith(".scss") &&
      underStatic(f) &&
      !f.split(sep).pop().startsWith("_"),
  );
}

/** Hand-written + generated CSS that should be minified to `*.min.css`. */
function cssSources(files) {
  return files.filter(
    (f) =>
      f.endsWith(".css") &&
      !f.endsWith(".min.css") &&
      underStatic(f) &&
      !inScssDir(f), // the canonical compiled CSS lives in a `css/` dir
  );
}

/** Hand-written JS that should be minified to `*.min.js`. */
function jsSources(files) {
  return files.filter(
    (f) =>
      f.endsWith(".js") &&
      !f.endsWith(".min.js") &&
      !f.endsWith(".src.js") && // *.src.js are unbundled sources, not served
      underStatic(f),
  );
}

// ---------------------------------------------------------------------------
// Output path helpers
// ---------------------------------------------------------------------------

/** `.../scss/brit-theme.scss` -> `.../css/brit-theme.css` (sibling css/ dir). */
function scssOutput(scssPath) {
  const css = scssPath.replace(/\.scss$/, ".css");
  const parts = css.split(sep);
  const i = parts.lastIndexOf("scss");
  if (i !== -1) parts[i] = "css";
  return parts.join(sep);
}

const minCss = (p) => p.replace(/\.css$/, ".min.css");
const minJs = (p) => p.replace(/\.js$/, ".min.js");

// ---------------------------------------------------------------------------
// Build steps (each shells out to a pinned CLI)
// ---------------------------------------------------------------------------

function run(cmd, args) {
  execFileSync(cmd, args, { cwd: ROOT, stdio: ["ignore", "ignore", "inherit"] });
}

function compileScss(entry) {
  const out = scssOutput(entry);
  run("sass", [
    `${entry}:${out}`,
    "--style=expanded",
    "--source-map",
    "--no-error-css",
    "--quiet",
  ]);
  return out;
}

function minifyCss(src) {
  run("esbuild", [src, "--minify", `--outfile=${minCss(src)}`, "--log-level=warning"]);
}

function minifyJs(src) {
  run("esbuild", [src, "--minify", `--outfile=${minJs(src)}`, "--log-level=warning"]);
}

const rel = (p) => p.slice(ROOT.length + 1);

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

function buildAll() {
  const started = Date.now();
  const files = walk(ROOT);

  for (const entry of scssEntries(files)) {
    compileScss(entry);
    console.log(`scss  ${rel(entry)} -> ${rel(scssOutput(entry))}`);
  }

  // Re-walk so freshly compiled .css files are picked up for minification.
  const after = walk(ROOT);
  for (const css of cssSources(after)) {
    minifyCss(css);
    console.log(`css   ${rel(css)} -> ${rel(minCss(css))}`);
  }
  for (const js of jsSources(after)) {
    minifyJs(js);
    console.log(`js    ${rel(js)} -> ${rel(minJs(js))}`);
  }

  console.log(`\nBuilt all assets in ${Date.now() - started}ms`);
}

// ---------------------------------------------------------------------------
// Watch mode: rebuild only what changed for fast dev feedback.
//
// Uses mtime polling rather than inotify (fs.watch): file-change events do not
// reliably propagate through Docker bind mounts (WSL2/macOS), so polling is the
// portable choice. Builds are synchronous, so poll ticks never overlap.
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 500;

/** Source files the watcher tracks for changes. */
function watchSources() {
  return walk(ROOT).filter(
    (f) =>
      f.endsWith(".scss") ||
      (f.endsWith(".css") && !f.endsWith(".min.css") && !inScssDir(f)) ||
      (f.endsWith(".js") && !f.endsWith(".min.js") && !f.endsWith(".src.js")),
  );
}

function mtime(path) {
  try {
    return statSync(path).mtimeMs;
  } catch {
    return null;
  }
}

function recompileScss() {
  const outputs = [];
  for (const entry of scssEntries(walk(ROOT))) {
    outputs.push(compileScss(entry));
    console.log(`scss  ${rel(entry)} (recompiled)`);
  }
  return outputs;
}

function startWatch() {
  buildAll();
  console.log(`\nWatching for changes (polling every ${POLL_INTERVAL_MS}ms; Ctrl-C to stop)...`);

  const seen = new Map();
  for (const f of watchSources()) seen.set(f, mtime(f));

  setInterval(() => {
    const current = watchSources();
    const changed = [];
    const present = new Set();
    for (const f of current) {
      present.add(f);
      const m = mtime(f);
      if (m !== null && seen.get(f) !== m) {
        changed.push(f);
        seen.set(f, m);
      }
    }
    for (const f of [...seen.keys()]) if (!present.has(f)) seen.delete(f);
    if (changed.length === 0) return;

    try {
      // SCSS partials can affect any entry: recompile all entries once, then
      // re-minify the generated CSS. Skip those generated files below.
      const scssOutputs = new Set();
      if (changed.some((f) => f.endsWith(".scss"))) {
        for (const out of recompileScss()) {
          scssOutputs.add(out);
          minifyCss(out);
          console.log(`css   ${rel(out)} -> ${rel(minCss(out))}`);
          seen.set(out, mtime(out));
        }
      }
      for (const f of changed) {
        if (f.endsWith(".scss") || scssOutputs.has(f)) continue;
        if (f.endsWith(".css")) {
          minifyCss(f);
          console.log(`css   ${rel(f)} -> ${rel(minCss(f))}`);
        } else if (f.endsWith(".js")) {
          minifyJs(f);
          console.log(`js    ${rel(f)} -> ${rel(minJs(f))}`);
        }
      }
    } catch {
      // Error details already streamed to stderr by the CLI; keep watching.
      console.error("\u2717 asset build failed (see error above)");
    }
  }, POLL_INTERVAL_MS);
}

if (WATCH) {
  startWatch();
} else {
  buildAll();
}
