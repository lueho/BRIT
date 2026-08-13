// Dependency-free unit tests for the ACPV marker style (hatching + group
// outline).
//
// Screen and export share one resolver, so the two renderings can only differ
// by the canvas they are drawn on. Run with:
//
//   docker compose run --rm assets node \
//     sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.acpv.test.mjs
//
// (wrapped by `make js-test`).

import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_atlas_choropleth.js"), "utf8");

const sandbox = { console };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { acpv, setRenderDefaults } = sandbox.WasteAtlasChoropleth;

const ATLAS_DEFAULTS = {
  hatchColor: "#1f2937",
  hatchOpacity: 0.9,
  outlineColor: "#ffffff",
  outlineOpacity: 0.95,
  outlineWidth: 1.35,
};

// The two canvases the atlas renders on: the screen SVG (CSS pixels) and the
// export page (160 mm at 300 dpi).
const SCREEN_WIDTH = 900;
const EXPORT_WIDTH = Math.round((160 / 25.4) * 300); // 1890

setRenderDefaults({ acpv: Object.assign({}, ATLAS_DEFAULTS) });

function withAtlasDefaults(overrides, body) {
  setRenderDefaults({ acpv: Object.assign({}, ATLAS_DEFAULTS, overrides) });
  try {
    body();
  } finally {
    setRenderDefaults({ acpv: Object.assign({}, ATLAS_DEFAULTS) });
  }
}

test("the atlas-wide default colors apply to a map that configures nothing", () => {
  withAtlasDefaults({ hatchColor: "#123456", outlineColor: "#654321" }, () => {
    const style = acpv.style({}, SCREEN_WIDTH);

    assert.equal(style.hatchColor, "#123456");
    assert.equal(style.outlineColor, "#654321");
  });
});

test("a per-map color wins over the atlas default", () => {
  withAtlasDefaults({ hatchColor: "#123456" }, () => {
    const style = acpv.style(
      { acpvHatchColor: "#ff0000", acpvOutlineColor: "#00ff00" },
      SCREEN_WIDTH,
    );

    assert.equal(style.hatchColor, "#ff0000");
    assert.equal(style.outlineColor, "#00ff00");
  });
});

test("per-map opacity and outline width override the atlas defaults", () => {
  const style = acpv.style(
    { acpvHatchOpacity: 0.4, acpvOutlineOpacity: 0.5, acpvOutlineWidth: 4 },
    SCREEN_WIDTH,
  );

  assert.equal(style.hatchOpacity, 0.4);
  assert.equal(style.outlineOpacity, 0.5);
  assert.equal(style.outlineWidth, 4);
});

test("an explicit zero opacity is honoured instead of falling back", () => {
  const style = acpv.style({ acpvHatchOpacity: 0 }, SCREEN_WIDTH);

  assert.equal(style.hatchOpacity, 0);
});

test("the hatch keeps the same appearance on the screen and on the export page", () => {
  const screen = acpv.style({}, SCREEN_WIDTH);
  const exported = acpv.style({}, EXPORT_WIDTH);
  const factor = EXPORT_WIDTH / SCREEN_WIDTH;

  // Everything geometric scales with the canvas, so hatch density, line
  // thickness and outline weight are identical relative to the map.
  assert.ok(Math.abs(exported.hatchSpacing - screen.hatchSpacing * factor) < 1e-9);
  assert.ok(
    Math.abs(exported.hatchStrokeWidth - screen.hatchStrokeWidth * factor) < 1e-9,
  );
  assert.ok(Math.abs(exported.outlineWidth - screen.outlineWidth * factor) < 1e-9);
  assert.equal(exported.hatchAngle, screen.hatchAngle);
  assert.equal(exported.hatchColor, screen.hatchColor);
});

test("a missing canvas width falls back to the reference canvas", () => {
  assert.deepEqual(acpv.style({}), acpv.style({}, SCREEN_WIDTH));
});

test("the hatch covers a readable share of the reference canvas", () => {
  const style = acpv.style({}, SCREEN_WIDTH);

  assert.ok(style.hatchStrokeWidth > 0);
  assert.ok(style.hatchStrokeWidth < style.hatchSpacing);
});
