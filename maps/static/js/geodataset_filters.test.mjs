// Dependency-free unit tests for GeoDataset filter select enhancement.
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "geodataset_filters.js"), "utf8");

function makeSandbox(selects) {
  const created = [];
  const sandbox = {
    console,
    fetch: undefined,
    document: {
      addEventListener() {},
    },
    TomSelect: class {
      constructor(select, options) {
        select.tomselect = this;
        created.push({ select, options });
      }
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  const root = { querySelectorAll: () => selects };
  return { sandbox, root, created };
}

function select(dataset) {
  return { dataset };
}

test("choice selects become searchable multi-selects without remote loading", () => {
  const choice = select({ geodatasetFilter: "choice", placeholder: "Any" });
  const { sandbox, root, created } = makeSandbox([choice]);

  sandbox.initGeoDatasetFilterSelects(root);

  assert.strictEqual(created.length, 1);
  assert.deepStrictEqual([...created[0].options.plugins], ["remove_button"]);
  assert.strictEqual(created[0].options.placeholder, "Any");
  assert.strictEqual(created[0].options.load, undefined);
});

test("selects are only enhanced once", () => {
  const choice = select({ geodatasetFilter: "choice" });
  const { sandbox, root, created } = makeSandbox([choice]);

  sandbox.initGeoDatasetFilterSelects(root);
  sandbox.initGeoDatasetFilterSelects(root);

  assert.strictEqual(created.length, 1);
});

test("autocomplete selects query the options endpoint", async () => {
  const autocomplete = select({
    geodatasetFilter: "autocomplete",
    autocompleteUrl: "/maps/geodatasets/1/filter-options/art/",
  });
  const requested = [];
  const { sandbox } = makeSandbox([]);
  const fetchImpl = async (url) => {
    requested.push(url);
    return { ok: true, json: async () => ({ results: [{ value: "Eiche", text: "Eiche" }] }) };
  };

  const options = sandbox.geoDatasetFilterSelectOptions(autocomplete, fetchImpl);
  const results = await new Promise((resolve) => options.load("Ei che", resolve));

  assert.deepStrictEqual(requested, ["/maps/geodatasets/1/filter-options/art/?q=Ei%20che"]);
  assert.strictEqual(results[0].value, "Eiche");
  assert.strictEqual(options.valueField, "value");
  assert.strictEqual(options.shouldLoad(""), false);
  assert.strictEqual(options.shouldLoad("E"), true);
});

test("autocomplete failures resolve with no options", async () => {
  const autocomplete = select({ geodatasetFilter: "autocomplete", autocompleteUrl: "/x/" });
  const { sandbox } = makeSandbox([]);
  const options = sandbox.geoDatasetFilterSelectOptions(autocomplete, async () => {
    throw new Error("offline");
  });

  const results = await new Promise((resolve) => options.load("a", resolve));

  assert.strictEqual(results, undefined);
});

test("missing TomSelect leaves native selects untouched", () => {
  const { sandbox, root } = makeSandbox([select({ geodatasetFilter: "choice" })]);
  sandbox.TomSelect = undefined;

  assert.doesNotThrow(() => sandbox.initGeoDatasetFilterSelects(root));
});
