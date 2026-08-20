import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_atlas_choropleth.js"), "utf8");

function quantile(values, probability) {
  const position = (values.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  const weight = position - lower;
  return values[lower] * (1 - weight) + values[upper] * weight;
}

function geoMercator() {
  const projection = (point) => point;
  projection.extent = null;
  projection.fitExtent = (extent) => {
    projection.extent = extent;
    return projection;
  };
  projection.scale = () => projection.extent[1][0] - projection.extent[0][0];
  return projection;
}

function geoPath() {
  let projection;
  return {
    projection(next) {
      projection = next;
      return this;
    },
    bounds() {
      return projection.extent;
    },
  };
}

const assignedUrls = [];
const sandbox = {
  console,
  d3: { geoMercator, geoPath, quantile },
  window: {
    location: {
      assign(url) {
        assignedUrls.push(url);
      },
      pathname: "/current/",
    },
  },
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);

const atlas = sandbox.WasteAtlasChoropleth;
atlas.setRenderDefaults({
  changeColors: {
    boundaryChanged: "#777777",
    changed: "#666666",
    decrease: "#111111",
    increase: "#333333",
    new: "#444444",
    noChange: "#222222",
    removed: "#555555",
  },
  export: {
    dpi: 300,
    heightMm: 110,
    legendFontFamily: "sans-serif",
    legendFontSizePt: 9,
    legendMaxWidthFraction: 0.52,
    maxHeightMm: 180,
    widthMm: 160,
  },
  exportLegend: {
    columns: "auto",
    itemFlow: "column",
    maxWidthFraction: 0.52,
    placement: "auto",
  },
  noDataColor: "#cccccc",
  quartileColors: ["#1", "#2", "#3", "#4"],
});

const { changes, collections, layout, legend, quartiles, selection } = atlas;

test("quartile categories use rounded whole-number labels", () => {
  const categories = quartiles.categories([10, 20, 30, 40], ["a", "b", "c", "d"]);

  assert.deepEqual(
    categories.map((category) => category.label),
    ["10 – 18 (Q1)", "18 – 25 (Q2)", "25 – 33 (Q3)", "33 – 40 (Q4)"],
  );
});

test("quartile labels apply the configured percentage multiplier", () => {
  const categories = quartiles.categories([0.1, 0.2, 0.3, 0.4], null, 100);

  assert.deepEqual(
    categories.map((category) => category.label),
    ["10 – 18 (Q1)", "18 – 25 (Q2)", "25 – 33 (Q3)", "33 – 40 (Q4)"],
  );
});

test("legend statuses follow collection categories and overlay patterns become footnotes", () => {
  const config = {
    categories: [
      { value: "no_collection", label: "No collection", color: "#eeeeee" },
      { value: "no_data", label: "No data", color: "#dddddd" },
    ],
    _hasNoDataCategory: true,
    _hasOverlayPattern: true,
    overlayPatternField: "source",
    overlayPatternLegendLabel: "Estimated from grouped values",
  };

  assert.deepEqual(
    legend.items(config, false).map((item) => item.label),
    ["No collection", "No data"],
  );
  assert.equal(legend.footnote(config, false), "Estimated from grouped values");
});

test("no-data legend entries depend on displayed catchments", () => {
  const config = {
    categories: [{ value: "available", label: "Available", color: "#111111" }],
    dataField: "status",
    noDataLabel: "No data",
  };
  const data = {
    catchments: { features: [{ properties: { catchment_id: 1 } }] },
    thematicData: [{ catchment_id: 1, status: "available" }],
  };

  legend.annotateFeatures(data, config);
  assert.deepEqual(legend.items(config, false).map((item) => item.label), ["Available"]);

  data.catchments.features.push({ properties: { catchment_id: 2 } });
  legend.annotateFeatures(data, config);
  assert.deepEqual(
    legend.items(config, false).map((item) => item.label),
    ["Available", "No data"],
  );
});

test("numeric change records classify increases, decreases, equality, additions and removals", () => {
  const records = changes.numericRecords(
    { dataField: "category", numericField: "amount" },
    [
      { catchment_id: 1, amount: 10 },
      { catchment_id: 2, amount: 4 },
      { catchment_id: 3, amount: 7 },
      { catchment_id: 5, amount: 6 },
    ],
    [
      { catchment_id: 1, amount: 12 },
      { catchment_id: 2, amount: 1 },
      { catchment_id: 4, amount: 9 },
      { catchment_id: 5, amount: 6 },
    ],
  );

  assert.deepEqual(
    Object.fromEntries(records.map((record) => [record.catchment_id, record.change_type])),
    { 1: "increase", 2: "decrease", 3: "removed", 4: "new", 5: "no_change" },
  );
});

test("numeric and categorical change maps use distinct legend titles", () => {
  assert.equal(
    changes.renderConfig({ fromYear: 2023, numericField: "amount", year: 2024 }, "Amounts")
      .legendTitle,
    "Difference",
  );
  assert.equal(
    changes.renderConfig({ fromYear: 2023, year: 2024 }, "Systems").legendTitle,
    "Change",
  );
});

test("export legend measurement fits short content and preserves explicit title lines", () => {
  const config = {
    categories: [{ value: "yes", label: "Yes", color: "#111111" }],
    legendTitle: "First line\nSecond line",
  };
  const measured = layout.measureExportLegend(config, 900, 1, "column");

  assert.ok(measured.width < 900);
  assert.deepEqual(measured.titleLines, ["First line", "Second line"]);
});

test("fixed export layout keeps the map outside a two-column right legend", () => {
  const config = {
    categories: [
      { value: "a", label: "Available data", color: "#111111" },
      { value: "b", label: "Missing data", color: "#222222" },
    ],
    dataField: "status",
    exportLegend: {
      columns: 2,
      itemFlow: "column",
      maxWidthFraction: 0.52,
      placement: "right",
    },
    legendTitle: "Status",
  };
  const data = {
    catchments: {
      features: [{ properties: { catchment_id: 1 } }],
      type: "FeatureCollection",
    },
    countryBorder: {
      features: [{ geometry: { coordinates: [], type: "Polygon" }, properties: {} }],
      type: "FeatureCollection",
    },
    thematicData: [{ catchment_id: 1, status: "a" }],
  };

  const exported = layout.exportLayout(data, config);

  assert.equal(exported.legendPlacement, "right");
  assert.equal(exported.legendColumns, 2);
  assert.ok(exported.mapExtent[1][0] < exported.legend.x);
  assert.equal(exported.warning, null);
});

test("selector scope uses the option ISO country and clears a missing NUTS level", () => {
  const attributes = {
    "data-country": "DE",
    "data-nuts-level": "",
    "data-nuts-prefix": "DEF",
  };
  const select = {
    options: [
      {
        getAttribute(name) {
          return attributes[name];
        },
      },
    ],
    selectedIndex: 0,
    value: "germany-schleswig-holstein",
  };
  const region = selection.regionFromSelect(select);
  const config = selection.configForSelection(
    { country: "FR", nutsLevel: 3, nutsPrefix: "FR1" },
    region,
    2024,
    false,
  );

  assert.equal(region.country, "DE");
  assert.equal(config.country, "DE");
  assert.equal(config.nutsPrefix, "DEF");
  assert.equal("nutsLevel" in config, false);
  assert.match(selection.queryString(2024, null, region), /country=DE/);
  assert.doesNotMatch(selection.queryString(2024, null, region), /germany-schleswig/);
});

test("collection activation opens the detail URL behind the displayed feature", () => {
  const feature = { properties: { collection_detail_url: "/collections/42/" } };

  assert.equal(collections.detailUrl(feature), "/collections/42/");
  collections.openChoice({}, feature);
  assert.deepEqual(assignedUrls, ["/collections/42/"]);
  assert.equal(collections.detailUrl({ properties: {} }), null);
  assert.equal(collections.detailUrl(null), null);
});
