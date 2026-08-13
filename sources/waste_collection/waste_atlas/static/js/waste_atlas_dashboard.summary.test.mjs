// Dependency-free unit tests for the dashboard's pure aggregation helpers.
//
// The chart rendering itself needs d3 and a DOM, so only the DOM-free parts are
// exercised here: request building, class counting, trend rows and the headline
// figures. Run with:
//
//   docker compose run --rm assets node \
//     sources/waste_collection/waste_atlas/static/js/waste_atlas_dashboard.summary.test.mjs
//
// (wrapped by `make js-test`).

import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_atlas_dashboard.js"), "utf8");

const sandbox = { console };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { chartDataUrl, escapeHtml, summarise, trendRows, kpisFrom } =
  sandbox.WasteAtlasDashboard;

const systemPanel = {
  theme: "collection_system",
  dataUrl: "/waste_collection/api/waste-atlas/collection-system/",
  dataField: "collection_system",
  categories: [
    { value: "Door to door", label: "Door to door", color: "#d0fcd5" },
    { value: "Bring point", label: "Bring point", color: "#3dc7dc" },
  ],
};

test("requests are scoped to the dashboard region and year", () => {
  const url = chartDataUrl(systemPanel, { country: "DE", nutsPrefix: "DEA" }, 2022);

  assert.strictEqual(
    url,
    "/waste_collection/api/waste-atlas/collection-system/?country=DE&year=2022&nuts_prefix=DEA",
  );
});

test("a region without a NUTS prefix does not send an empty one", () => {
  const url = chartDataUrl(systemPanel, { country: "IT", nutsPrefix: "" }, 2024);

  assert.ok(!url.includes("nuts_prefix"));
});

test("classes are counted in legend order with their shares", () => {
  const summary = summarise(systemPanel, [
    { collection_system: "Door to door" },
    { collection_system: "Door to door" },
    { collection_system: "Bring point" },
    { collection_system: "Door to door" },
  ]);

  assert.deepEqual(
    summary.bars.map((bar) => [bar.label, bar.count]),
    [
      ["Door to door", 3],
      ["Bring point", 1],
    ],
  );
  assert.strictEqual(summary.bars[0].share, 0.75);
  assert.strictEqual(summary.total, 4);
  assert.strictEqual(summary.noData, 0);
});

test("missing and unmapped values are reported as one no-data class", () => {
  const summary = summarise(systemPanel, [
    { collection_system: "Door to door" },
    { collection_system: null },
    { collection_system: "Something else" },
  ]);

  const noData = summary.bars[summary.bars.length - 1];
  assert.strictEqual(noData.label, "No data");
  assert.strictEqual(noData.count, 2);
  assert.strictEqual(summary.withData, 1);
});

test("a panel's stored no-data label and colour are used", () => {
  const summary = summarise(
    { ...systemPanel, noDataLabel: "Keine Daten", noDataColor: "#cccccc" },
    [{ collection_system: null }],
  );

  assert.strictEqual(summary.bars[summary.bars.length - 1].label, "Keine Daten");
  assert.strictEqual(summary.bars[summary.bars.length - 1].color, "#cccccc");
});

test("empty responses summarise to an empty chart instead of throwing", () => {
  const summary = summarise(systemPanel, []);

  assert.strictEqual(summary.total, 0);
  assert.deepEqual(
    summary.bars.map((bar) => bar.count),
    [0, 0],
  );
});

test("trend rows are ordered by year and carry each year's shares", () => {
  const rows = trendRows(systemPanel, {
    2024: [{ collection_system: "Door to door" }],
    2020: [{ collection_system: "Bring point" }, { collection_system: "Bring point" }],
  });

  assert.deepEqual(
    rows.map((row) => row.year),
    [2020, 2024],
  );
  assert.strictEqual(rows[0].bars[1].share, 1);
  assert.strictEqual(rows[1].bars[0].share, 1);
});

test("configured labels are escaped before they reach a tooltip", () => {
  assert.strictEqual(
    escapeHtml('<img src=x onerror="alert(1)">'),
    "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;",
  );
  assert.strictEqual(escapeHtml("Bring point & door to door"), "Bring point &amp; door to door");
});

test("headline figures count only charts that loaded data", () => {
  const kpis = kpisFrom([
    { total: 400, withData: 380, bars: [] },
    { total: 400, withData: 0, bars: [] },
    null,
  ]);

  assert.deepEqual(kpis, {
    charts: 1,
    chartsTotal: 3,
    catchments: 400,
    values: 380,
  });
});
