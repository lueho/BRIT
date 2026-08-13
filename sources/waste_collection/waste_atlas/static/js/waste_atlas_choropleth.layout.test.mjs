// Dependency-free unit tests for the export-legend layout helpers.
//
// These cover the pure pieces of the constraint-driven layout engine
// (configuration resolution, candidate generation, hard-invariant validation
// and deterministic scoring) without a browser: the module is evaluated in a
// vm context and only DOM-free helpers are exercised. Run with:
//
//   docker compose run --rm assets node \
//     sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.layout.test.mjs
//
// (wrapped by `make js-test`). The full geometric layout — placement choice
// for wide/tall/compact/irregular maps and non-overlap — is verified in the
// browser, since it depends on d3 projection and text measurement.

// Non-strict assert: the module is evaluated in a vm realm, so its arrays and
// objects have that realm's prototypes; loose deepEqual compares by structure.
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
const { layout, setRenderDefaults } = sandbox.WasteAtlasChoropleth;

// Minimal render defaults so DOM-free helpers that read export geometry work.
function renderDefaults(exportLegend = {}) {
  return {
    export: {
      dpi: 300,
      widthMm: 160,
      heightMm: 110,
      maxHeightMm: 180,
      legendFontSizePt: 9,
      legendFontFamily: "sans-serif",
      legendMaxWidthFraction: 0.52,
    },
    exportLegend: Object.assign(
      {
        placement: "auto",
        columns: "auto",
        itemFlow: "column",
        maxWidthFraction: 0.52,
      },
      exportLegend,
    ),
  };
}

setRenderDefaults(renderDefaults());

// Run `body` against atlas-wide defaults overridden by `exportLegend`.
function withAtlasDefaults(exportLegend, body) {
  setRenderDefaults(renderDefaults(exportLegend));
  try {
    body();
  } finally {
    setRenderDefaults(renderDefaults());
  }
}

const EXPORT_WIDTH = Math.round((160 / 25.4) * 300); // 1890
const PAGE_HEIGHT = Math.round((110 / 25.4) * 300); // 1299

function validCandidate(overrides = {}) {
  return Object.assign(
    {
      name: "right",
      overlay: false,
      columns: 1,
      heightMm: 110,
      height: PAGE_HEIGHT,
      legend: { x: 46, y: 46, width: 400, height: 400 },
      mapWidth: 800,
      mapHeight: 900,
      mapScale: 1000,
      mapArea: 720000,
      legendArea: 160000,
      textWidth: 200,
      minTextWidth: 75,
      itemCount: 3,
      overlapsShapes: false,
      wrappedLines: 0,
    },
    overrides,
  );
}

test("resolveExportLegend returns explicit auto values verbatim", () => {
  assert.deepEqual(
    layout.resolveExportLegend({
      exportLegend: { placement: "auto", columns: "auto", maxWidthFraction: 0.4 },
    }),
    {
      placement: "auto",
      columns: "auto",
      itemFlow: "column",
      maxWidthFraction: 0.4,
    },
  );
});

test("resolveExportLegend keeps fixed values", () => {
  assert.deepEqual(
    layout.resolveExportLegend({
      exportLegend: {
        placement: "left",
        columns: 2,
        itemFlow: "row",
        maxWidthFraction: 0.38,
      },
    }),
    { placement: "left", columns: 2, itemFlow: "row", maxWidthFraction: 0.38 },
  );
});

test("resolveExportLegend falls back to atlas defaults when absent", () => {
  assert.deepEqual(layout.resolveExportLegend({}), {
    placement: "auto",
    columns: "auto",
    itemFlow: "column",
    maxWidthFraction: 0.52,
  });
});

test("resolveExportLegend rejects an unknown item flow", () => {
  assert.equal(
    layout.resolveExportLegend({ exportLegend: { itemFlow: "diagonal" } }).itemFlow,
    "column",
  );
});

test("resolveExportLegend inherits the atlas-wide item flow", () => {
  withAtlasDefaults({ itemFlow: "row" }, () => {
    // Absent, invalid and flat-key configs all fall back to the atlas default,
    // exactly like the maximum width does.
    assert.equal(layout.resolveExportLegend({}).itemFlow, "row");
    assert.equal(
      layout.resolveExportLegend({ exportLegend: { itemFlow: "diagonal" } }).itemFlow,
      "row",
    );
    assert.equal(layout.resolveExportLegend({ exportLegendColumns: 2 }).itemFlow, "row");
    assert.equal(
      layout.resolveExportLegend({ exportLegendItemFlow: "column" }).itemFlow,
      "column",
    );
  });
});

function flowItems(heights) {
  return heights.map((height, index) => ({ label: "item " + index, height: height }));
}

test("column flow balances the columns", () => {
  const columns = layout.distributeLegendItems(flowItems([10, 10, 10, 10]), 2, "column", 0);
  assert.deepEqual(
    columns.map((column) => column.map((item) => item.label)),
    [
      ["item 0", "item 2"],
      ["item 1", "item 3"],
    ],
  );
});

test("row flow fills across the columns in order", () => {
  const columns = layout.distributeLegendItems(flowItems([10, 10, 10, 10, 10]), 3, "row", 0);
  assert.deepEqual(
    columns.map((column) => column.map((item) => item.label)),
    [["item 0", "item 3"], ["item 1", "item 4"], ["item 2"]],
  );
});

test("row flow gives every entry of a row the row's height so rows line up", () => {
  const items = flowItems([10, 30, 10, 10]);
  layout.distributeLegendItems(items, 2, "row", 0);
  assert.deepEqual(
    items.map((item) => item.slotHeight),
    [30, 30, 10, 10],
  );
});

// A realm with a canvas stub that reports bold text wider than regular text and
// records every font it measured with, so wrapping can be observed without a DOM.
function measuringRealm() {
  const fonts = [];
  const context = {
    font: "",
    measureText(text) {
      fonts.push(this.font);
      const perChar = String(this.font).indexOf("bold") === 0 ? 12 : 6;
      return { width: String(text).length * perChar };
    },
  };
  const realm = {
    console,
    document: { createElement: () => ({ getContext: () => context }) },
  };
  vm.createContext(realm);
  vm.runInContext(source, realm);
  realm.WasteAtlasChoropleth.setRenderDefaults(renderDefaults());
  return { atlas: realm.WasteAtlasChoropleth, fonts };
}

test("text is measured with the face it is rendered in", () => {
  const { atlas, fonts } = measuringRealm();
  const title = "Annual collection count ratio - Biowaste : Residual waste";
  const font = { family: atlas.legend.screenFontFamily, weight: "bold" };

  const bold = atlas.layout.wrapTextToWidth(title, 240, 13, font);
  const regular = atlas.layout.wrapTextToWidth(title, 240, 13, {
    family: font.family,
  });

  // The legend title is drawn bold: measuring it regular underestimates its
  // width and the title then overflows the legend box instead of wrapping.
  assert.ok(bold.length > regular.length);
  assert.ok(fonts.includes("bold 13px 'Nunito', sans-serif"));
  assert.ok(fonts.includes("13px 'Nunito', sans-serif"));
});

test("the export legend title is measured in the bold face it is printed in", () => {
  const { atlas, fonts } = measuringRealm();

  const opts = atlas.layout.measureExportLegend(
    {
      legendTitle: "Annual collection count ratio - Biowaste : Residual waste",
      categories: [{ value: "a", label: "A label", color: "#000000" }],
    },
    200,
    1,
    "column",
  );

  // Every title line must fit the box it was wrapped for when measured bold,
  // the face the export draws it in; measuring it regular overflows the box.
  const maxWidth = opts.width - opts.paddingX * 2;
  assert.ok(opts.titleLines.length > 1);
  opts.titleLines.forEach((line) => {
    assert.ok(line.length * 12 <= maxWidth, line);
  });
  assert.ok(fonts.some((font) => font.indexOf("bold") === 0));
});

test("a row-flow column is measured on the slot heights, so columns stay aligned", () => {
  // The screen legend shares this measurement, so a wrapped (taller) entry may
  // not push its column out of step with its neighbour.
  const items = flowItems([10, 30, 10, 10]);
  const columns = layout.distributeLegendItems(items, 2, "row", 4);
  assert.deepEqual(
    columns.map((column) => layout.legendColumnHeight(column, 4)),
    [44, 44],
  );
});

test("placement candidates: auto expands, fixed pins", () => {
  const auto = layout.placementCandidates("auto");
  assert.deepEqual(auto.slice(0, 3), ["right", "left", "bottom"]);
  assert.equal(auto.length, 7);
  assert.deepEqual(layout.placementCandidates("left"), ["left"]);
});

test("column candidates: auto expands 1..4, fixed pins", () => {
  assert.deepEqual(layout.columnCandidates("auto"), [1, 2, 3, 4]);
  assert.deepEqual(layout.columnCandidates(2), [2]);
  assert.deepEqual(layout.columnCandidates("3"), [3]);
});

test("a well-placed candidate has no violations", () => {
  assert.deepEqual(layout.candidateViolations(validCandidate()), []);
});

test("a legend outside the page margins is clipped", () => {
  const c = validCandidate({ legend: { x: 10, y: 46, width: 400, height: 400 } });
  assert.ok(layout.candidateViolations(c).includes("clipped"));
});

test("a legend taller than the page is clipped", () => {
  const c = validCandidate({
    legend: { x: 46, y: 46, width: 400, height: PAGE_HEIGHT },
  });
  assert.ok(layout.candidateViolations(c).includes("clipped"));
});

test("a non-positive map area is rejected", () => {
  assert.ok(
    layout.candidateViolations(validCandidate({ mapWidth: 0 })).includes("invalid-map"),
  );
});

test("too-narrow text columns are rejected as unreadable", () => {
  const c = validCandidate({ textWidth: 40, minTextWidth: 75 });
  assert.ok(layout.candidateViolations(c).includes("readability"));
});

test("more columns than items is rejected", () => {
  const c = validCandidate({ columns: 4, itemCount: 3 });
  assert.ok(layout.candidateViolations(c).includes("columns"));
});

test("an overlay legend covering shapes is rejected", () => {
  const c = validCandidate({ overlay: true, overlapsShapes: true });
  assert.ok(layout.candidateViolations(c).includes("overlap"));
});

test("scoring prefers the preferred page height", () => {
  const preferred = layout.scoreCandidate(validCandidate({ heightMm: 110 }), 110);
  const taller = layout.scoreCandidate(validCandidate({ heightMm: 150 }), 110);
  assert.ok(preferred > taller);
});

function scoredCandidate(violations, score) {
  return { violations, violationCost: layout.candidateViolationCost({ violations }), score };
}

test("violation cost sums per-violation weights", () => {
  assert.equal(layout.candidateViolationCost({ violations: [] }), 0);
  assert.equal(layout.candidateViolationCost({ violations: ["columns"] }), 100);
  assert.equal(
    layout.candidateViolationCost({ violations: ["clipped", "columns"] }),
    1000100,
  );
});

test("least-bad prefers a columns-only violation over a clipped legend", () => {
  const clipped = scoredCandidate(["clipped"], 9e9);
  const columnsOnly = scoredCandidate(["columns"], -9e9);
  // Despite its far higher score, the clipped candidate must lose.
  assert.strictEqual(layout.pickLeastBad([clipped, columnsOnly]), columnsOnly);
});

test("least-bad breaks equal-cost ties by score", () => {
  const worse = scoredCandidate(["columns"], 10);
  const better = scoredCandidate(["columns"], 50);
  assert.strictEqual(layout.pickLeastBad([worse, better]), better);
});

test("scoring prefers a larger map and penalises label wrapping", () => {
  const bigMap = layout.scoreCandidate(validCandidate({ mapScale: 1200 }), 110);
  const smallMap = layout.scoreCandidate(validCandidate({ mapScale: 900 }), 110);
  assert.ok(bigMap > smallMap);

  const tidy = layout.scoreCandidate(validCandidate({ wrappedLines: 0 }), 110);
  const wrapped = layout.scoreCandidate(validCandidate({ wrappedLines: 6 }), 110);
  assert.ok(tidy > wrapped);
});
