// Dependency-free unit tests for incremental feature rendering in maps.js.
//
// Leaflet and the DOM are stubbed; maps.js is evaluated in a vm context.
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "maps.js"), "utf8");

function makeSandbox() {
  const created = [];
  const removed = [];
  const listeners = {};
  const fakeMap = {
    removeLayer(l) { removed.push(l); },
    eachLayer() {},
    on() {},
  };
  const sandbox = {
    console,
    URLSearchParams,
    AbortController,
    L: {
      geoJson(data, options) {
        const layer = {
          options,
          added: [],
          on() {},
          addTo(m) { this.map = m; return this; },
          addData(d) { this.added.push(d); },
          getBounds() { return { isValid: () => false }; },
        };
        created.push(layer);
        return layer;
      },
      circleMarker() { return {}; },
      canvas() { return {}; },
      GeoJSON: class {},
    },
    map: fakeMap,
    document: {
      getElementById() { return null; },
      createElement() { return { style: {} }; },
    },
    addEventListener(type, fn) { listeners[type] = fn; },
    dispatchEvent() {},
    indexedDB: undefined,
    mapConfig: {
      featuresLayerStyle: { radius: 3 },
      regionLayerStyle: {},
      catchmentLayerStyle: {},
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  // maps.js binds its internal `map` variable from the "map:init" event.
  listeners["map:init"]({ detail: { map: fakeMap } });
  sandbox.initializeRenderers();
  return { sandbox, created, removed };
}

function pointFeature(i) {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [10 + i / 1000, 53.5] },
    properties: { id: i },
  };
}

test("addFeatureBatch lazily creates one layer and appends batches", () => {
  const { sandbox, created } = makeSandbox();

  assert.equal(sandbox.addFeatureBatch([pointFeature(0), pointFeature(1)]), true);
  assert.equal(sandbox.addFeatureBatch([pointFeature(2)]), true);

  assert.strictEqual(created.length, 1, "expected a single incremental layer");
  assert.strictEqual(created[0].added.length, 2);
  assert.strictEqual(created[0].added[0].length, 2);
  assert.strictEqual(created[0].added[1].length, 1);
  assert.strictEqual(typeof created[0].options.pointToLayer, "function");
});

test("resetFeaturesLayer clears the layer so the next batch starts fresh", () => {
  const { sandbox, created, removed } = makeSandbox();

  sandbox.addFeatureBatch([pointFeature(0)]);
  sandbox.resetFeaturesLayer();
  sandbox.addFeatureBatch([pointFeature(1)]);

  assert.strictEqual(created.length, 2, "expected a new layer after reset");
  assert.strictEqual(removed.length, 1, "old layer should be removed from map");
});

test("addFeatureBatch with unsupported geometry returns false for fallback", () => {
  const { sandbox } = makeSandbox();
  const line = {
    type: "Feature",
    geometry: { type: "LineString", coordinates: [[10, 53], [11, 54]] },
    properties: {},
  };

  assert.strictEqual(sandbox.addFeatureBatch([line]), false);
});

test("addFeatureBatch ignores empty batches", () => {
  const { sandbox, created } = makeSandbox();
  assert.strictEqual(sandbox.addFeatureBatch([]), false);
  assert.strictEqual(created.length, 0);
});
