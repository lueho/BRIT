import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_atlas_choropleth.js"), "utf8");

let opened = [];
let navigated = [];
const windowStub = {
  open(url, target) {
    const handle = { opener: "tab" };
    opened.push({ url, target, handle });
    return handle;
  },
  location: { assign: (url) => navigated.push(url) },
};
const sandbox = { console, window: windowStub };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const atlas = sandbox.WasteAtlasChoropleth;

const single = { properties: { collection_detail_url: "/collections/7/" } };
const composite = {
  properties: {
    collection_details: [
      { url: "/collections/1/", label: "Biowaste" },
      { url: "/collections/2/", label: "Residual" },
    ],
  },
};

test("middle click suppression fires only on the middle button", () => {
  let prevented = false;
  const event = { button: 1, preventDefault: () => (prevented = true) };
  atlas.collections.suppressAutoscroll(event);
  assert.strictEqual(prevented, true);

  prevented = false;
  atlas.collections.suppressAutoscroll({
    button: 0,
    preventDefault: () => (prevented = true),
  });
  assert.strictEqual(prevented, false);
});

test("openInNewTab opens the single collection in a blank tab without an opener", () => {
  assert.strictEqual(atlas.collections.openInNewTab(single), true);
  assert.strictEqual(opened[0].url, "/collections/7/");
  assert.strictEqual(opened[0].target, "_blank");
  assert.strictEqual(opened[0].handle.opener, null);
});

test("openInNewTab declines composite catchments so the picker can take over", () => {
  assert.strictEqual(atlas.collections.openInNewTab(composite), false);
});

test("openChoice navigates in the same tab for a single collection", () => {
  atlas.collections.openChoice({}, single);
  assert.deepStrictEqual(navigated, ["/collections/7/"]);
});
