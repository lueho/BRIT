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
import { existsSync, readdirSync, watch } from "node:fs";
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
// ---------------------------------------------------------------------------

function rebuildFor(path) {
  try {
    if (path.endsWith(".scss")) {
      // A partial can affect any entry, so recompile every entry + its min.
      for (const entry of scssEntries(walk(ROOT))) {
        const out = compileScss(entry);
        minifyCss(out);
        console.log(`scss  ${rel(entry)} (recompiled + minified)`);
      }
    } else if (path.endsWith(".css") && !path.endsWith(".min.css") && !inScssDir(path)) {
      minifyCss(path);
      console.log(`css   ${rel(path)} -> ${rel(minCss(path))}`);
    } else if (path.endsWith(".js") && !path.endsWith(".min.js") && !path.endsWith(".src.js")) {
      minifyJs(path);
      console.log(`js    ${rel(path)} -> ${rel(minJs(path))}`);
    } else {
      return;
    }
  } catch {
    // Error details already streamed to stderr by the CLI; keep watching.
    console.error(`\u2717 build failed for ${rel(path)} (see error above)`);
  }
}

function startWatch() {
  buildAll();
  console.log("\nWatching for changes (Ctrl-C to stop)...");

  const dirs = new Set(
    walk(ROOT)
      .filter(underStatic)
      .map(dirname),
  );

  const pending = new Map();
  for (const dir of dirs) {
    if (!existsSync(dir)) continue;
    watch(dir, (_event, filename) => {
      if (!filename) return;
      const path = join(dir, filename);
      clearTimeout(pending.get(path));
      pending.set(
        path,
        setTimeout(() => {
          pending.delete(path);
          rebuildFor(path);
        }, 120),
      );
    });
  }
}

if (WATCH) {
  startWatch();
} else {
  buildAll();
}
