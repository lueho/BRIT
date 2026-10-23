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
const atlas = sandbox.WasteAtlasChoropleth;
atlas.setRenderDefaults({
  changeColors: {
    noChange: "#000",
    changed: "#111",
    boundaryChanged: "#222",
    new: "#333",
    removed: "#444",
    decrease: "#555",
    increase: "#666",
  },
});

test("change catchment URL maps both data endpoints to their change variant", () => {
  assert.strictEqual(
    atlas.changes.catchmentUrl("/api/collector-geojson/"),
    "/api/collector-change-geojson/",
  );
  assert.strictEqual(
    atlas.changes.catchmentUrl("/api/collection-geojson/"),
    "/api/collection-change-geojson/",
  );
});

test("change records key classification on overlay feature provenance", () => {
  const cfg = { dataField: "system" };
  const fromRaw = [{ catchment_id: 1, system: "d2d" }];
  const toRaw = [{ catchment_id: 2, system: "d2d" }];
  const changeFeatures = [
    {
      properties: {
        from_catchment_id: 1,
        to_catchment_id: 2,
        spatial_change: "transferred",
        change_feature_id: 42,
      },
    },
    {
      properties: {
        from_catchment_id: null,
        to_catchment_id: 3,
        spatial_change: "added",
      },
    },
    {
      properties: {
        from_catchment_id: 9,
        to_catchment_id: null,
        spatial_change: "removed",
      },
    },
  ];

  const records = atlas.changes.records(cfg, fromRaw, toRaw, changeFeatures);

  assert.strictEqual(records[0].catchment_id, 42);
  assert.strictEqual(records[0].change_type, "boundary_changed");
  assert.strictEqual(records[0].spatial_change, "transferred");
  assert.strictEqual(records[0].from_catchment_id, 1);
  assert.strictEqual(records[0].to_catchment_id, 2);
  assert.strictEqual(records[1].change_type, "new");
  assert.strictEqual(records[2].change_type, "removed");
});

test("change legend declares a dedicated boundary_changed entry", () => {
  const entry = atlas.changes
    .categories(2024)
    .find((item) => item.value === "boundary_changed");

  assert.strictEqual(entry.label, "Catchment reassigned");
  assert.ok(entry.color, "boundary_changed needs its own color");
  assert.notStrictEqual(
    entry.color,
    atlas.changes.categories(2024).find((i) => i.value === "changed").color,
  );
});
