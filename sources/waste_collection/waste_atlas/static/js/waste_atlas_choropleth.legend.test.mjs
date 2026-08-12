// Dependency-free unit tests for legend entry ordering.
//
// The saved ``legendCategoryOrder`` has to survive the quartile classification,
// which replaces the stored classes with data-derived ``q1``-``q4`` entries.
// Run with:
//
//   docker compose run --rm assets node \
//     sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.legend.test.mjs
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
const { legend } = sandbox.WasteAtlasChoropleth;

// The legend of a quartile map: the classification keeps the special case and
// appends the four computed quartile classes.
function quartileCategories() {
  return [
    { value: "no_bio", label: "No separate biowaste collection", color: "#fff696" },
    { value: "q1", label: "9 – 39 (Q1)", color: "#d9f0d3" },
    { value: "q2", label: "39 – 71 (Q2)", color: "#a6d96a" },
    { value: "q3", label: "71 – 116 (Q3)", color: "#66bd63" },
    { value: "q4", label: "116 – 523 (Q4)", color: "#1a9850" },
  ];
}

function orderedValues(cfg) {
  return legend.orderedCategories(cfg).map((item) => item.value);
}

test("without a saved order the no-collection entry goes last", () => {
  assert.deepEqual(orderedValues({ categories: quartileCategories() }), [
    "q1",
    "q2",
    "q3",
    "q4",
    "no_bio",
  ]);
});

test("a saved order naming the quartile classes is applied verbatim", () => {
  assert.deepEqual(
    orderedValues({
      categories: quartileCategories(),
      legendCategoryOrder: ["q4", "q3", "q2", "q1", "no_bio"],
    }),
    ["q4", "q3", "q2", "q1", "no_bio"],
  );
});

test("a saved order that only knows the stored classes leaves the quartiles in place", () => {
  // Regression: the stored classes of an amount map (``very_high``…``low``) are
  // replaced by the quartile classes, so the saved order mentions only
  // ``no_bio``. That must not lift ``no_bio`` above the quartile entries.
  assert.deepEqual(
    orderedValues({
      categories: quartileCategories(),
      legendCategoryOrder: ["very_high", "high", "medium", "low", "no_bio"],
    }),
    ["q1", "q2", "q3", "q4", "no_bio"],
  );
});

test("unmentioned entries stay behind the mentioned entry they follow", () => {
  assert.deepEqual(
    orderedValues({
      categories: [
        { value: "a", label: "A" },
        { value: "new", label: "New" },
        { value: "b", label: "B" },
      ],
      legendCategoryOrder: ["b", "a"],
    }),
    ["b", "a", "new"],
  );
});

test("a no-data category only shows when the data needs it", () => {
  const categories = [{ value: "q1", label: "Q1" }, { value: "no_data", label: "No data" }];
  assert.deepEqual(orderedValues({ categories: categories }), ["q1"]);
  assert.deepEqual(orderedValues({ categories: categories, _hasNoDataCategory: true }), [
    "q1",
    "no_data",
  ]);
});
