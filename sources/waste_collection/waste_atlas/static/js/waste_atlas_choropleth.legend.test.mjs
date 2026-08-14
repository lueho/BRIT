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

const sandbox = {
  console,
  d3: {
    quantile(values, probability) {
      const position = (values.length - 1) * probability;
      const lower = Math.floor(position);
      const upper = Math.ceil(position);
      const weight = position - lower;
      return values[lower] * (1 - weight) + values[upper] * weight;
    },
  },
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { legend, quartiles, transforms } = sandbox.WasteAtlasChoropleth;

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

test("without a saved order the configured category order is preserved", () => {
  assert.deepEqual(orderedValues({ categories: quartileCategories() }), [
    "no_bio",
    "q1",
    "q2",
    "q3",
    "q4",
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

test("an explicit order anchors unknown entries relative to their configured order", () => {
  assert.deepEqual(
    orderedValues({
      categories: quartileCategories(),
      legendCategoryOrder: ["very_high", "high", "medium", "low", "no_bio"],
    }),
    ["no_bio", "q1", "q2", "q3", "q4"],
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

test("RLP outer collection-count classes only show when present", () => {
  const categories = [
    { value: "under_13", label: "< 13" },
    { value: "13", label: "13" },
    { value: "over_52", label: "> 52" },
  ];
  const config = {
    categories: categories,
    showOnlyPresentCategories: true,
    _presentCategoryValues: { 13: true },
  };

  assert.deepEqual(orderedValues(config), ["13"]);
  config._presentCategoryValues.under_13 = true;
  assert.deepEqual(orderedValues(config), ["under_13", "13"]);
  config._presentCategoryValues.over_52 = true;
  assert.deepEqual(orderedValues(config), ["under_13", "13", "over_52"]);
});

test("RLP ratio values of at least 2 use the 2:1 class", () => {
  assert.equal(
    sandbox.WasteAtlasChoropleth.transforms.rpCollectionCountRatio([
      { catchment_id: 1, bio_is_door_to_door: true, ratio: 3.15 },
    ])[0]._classified,
    "two_to_one",
  );
});

test("RLP ratios below one to one are classified, not dropped as no data", () => {
  const classified = sandbox.WasteAtlasChoropleth.transforms.rpCollectionCountRatio([
    { catchment_id: 1, bio_is_door_to_door: true, ratio: 0.5 },
    { catchment_id: 2, bio_is_door_to_door: true, ratio: null },
  ]);
  assert.equal(classified[0]._classified, "below_one_to_one");
  assert.equal(classified[1]._classified, null);
});

test("biowaste fees distinguish non-door-to-door systems from missing data", () => {
  const classified = sandbox.WasteAtlasChoropleth.transforms.biowasteFeeSystem([
    { catchment_id: 1, fee_system: "Bring point" },
    { catchment_id: 2, fee_system: "No separate collection" },
    { catchment_id: 3, fee_system: "Flat fee" },
    { catchment_id: 4, fee_system: "no_data" },
  ]);
  assert.deepEqual(
    classified.map((row) => row._classified),
    ["no_door_to_door", "no_door_to_door", "Flat fee", "no_data"],
  );
});

test("connection-rate fixed bands keep full connection separate", () => {
  const classified = transforms.connectionRate([
    { catchment_id: 1, connection_rate: 1, is_door_to_door: true },
    { catchment_id: 2, connection_rate: 0.97, is_door_to_door: true },
  ]);

  assert.deepEqual(
    classified.map((row) => row._classified),
    ["full_connection", "75-99"],
  );
});

test("connection-rate quartiles exclude full connection as a special class", () => {
  const config = {
    numericField: "connection_rate",
    dataField: "_classified",
    transformName: "connectionRate",
    categories: [
      { value: "full_connection", label: "100% – full connection", color: "#003f5c" },
      { value: "75-99", label: "75% – <100%", color: "#00608e" },
      { value: "no_d2d", label: "No door to door", color: "#fff696" },
    ],
    quartileColors: ["#d1e7e6", "#7fcce9", "#0090cb", "#00608e"],
    quartileDisplayMultiplier: 100,
    quartilePreserveClasses: ["no_d2d"],
    quartileSpecialCases: [
      {
        field: "connection_rate",
        equals: 1,
        classValue: "full_connection",
        label: "100% – full connection",
        color: "#003f5c",
      },
    ],
  };
  const records = [
    { catchment_id: 1, connection_rate: 0.1, is_door_to_door: true },
    { catchment_id: 2, connection_rate: 0.2, is_door_to_door: true },
    { catchment_id: 3, connection_rate: 0.3, is_door_to_door: true },
    { catchment_id: 4, connection_rate: 0.4, is_door_to_door: true },
    { catchment_id: 5, connection_rate: 1, is_door_to_door: true },
    { catchment_id: 6, connection_rate: null, is_door_to_door: false },
  ];

  const quartileConfig = quartiles.apply(config, records);
  const classified = quartileConfig.transformData(records);

  assert.deepEqual(
    classified.map((row) => row._classified),
    ["q1", "q2", "q3", "q4", "full_connection", "no_d2d"],
  );
  assert.deepEqual(
    quartileConfig.categories.map((category) => category.value),
    ["no_d2d", "full_connection", "q1", "q2", "q3", "q4"],
  );
});

test("RLP collection counts below 13 use the matching outer class", () => {
  const { rpBiowasteCollectionCount, rpResidualCollectionCount } =
    sandbox.WasteAtlasChoropleth.transforms;
  assert.equal(
    rpBiowasteCollectionCount([
      { catchment_id: 1, is_door_to_door: true, collection_count: 12 },
    ])[0]._classified,
    "under_13",
  );
  assert.equal(
    rpBiowasteCollectionCount([
      { catchment_id: 1, is_door_to_door: true, collection_count: null },
    ])[0]._classified,
    null,
  );
  assert.equal(
    rpResidualCollectionCount([{ catchment_id: 1, collection_count: 6 }])[0]._classified,
    "under_13",
  );
  assert.equal(
    rpResidualCollectionCount([{ catchment_id: 1, collection_count: null }])[0]._classified,
    null,
  );
});
