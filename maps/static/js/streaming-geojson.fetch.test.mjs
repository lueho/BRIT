// Dependency-free unit tests for fetchFeatureGeometriesWithProgress:
// overlapping loads and failed streams must not leave mixed or partial
// feature layers on the map.
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "streaming-geojson.js"), "utf8");

function makeFeatures(count, tag) {
  const features = [];
  for (let i = 0; i < count; i++) {
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [10.0 + i / 1000, 53.5] },
      properties: { id: i, tag },
    });
  }
  return features;
}

// A streaming response whose chunks are released one at a time by the test.
function controlledResponse(payload, chunkSize, { failAfterChunks = Infinity } = {}) {
  const bytes = new TextEncoder().encode(payload);
  let offset = 0;
  let chunksRead = 0;
  const waiters = [];
  let released = 0;
  const release = (n = 1) => {
    released += n;
    while (waiters.length && released > 0) {
      released--;
      waiters.shift()();
    }
  };
  const waitForRelease = () =>
    new Promise((resolve) => {
      if (released > 0) {
        released--;
        resolve();
      } else {
        waiters.push(resolve);
      }
    });
  const response = {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: {
      get(name) {
        const map = {
          "X-Total-Count": "5000",
          "X-Cache-Status": "STREAM",
          "Content-Length": String(bytes.length),
          "X-Data-Version": "v1",
        };
        return map[name] ?? null;
      },
    },
    body: {
      getReader() {
        return {
          async read() {
            await waitForRelease();
            if (response.signal && response.signal.aborted) {
              const err = new Error("aborted");
              err.name = "AbortError";
              throw err;
            }
            if (chunksRead >= failAfterChunks) {
              throw new Error("connection dropped");
            }
            if (offset >= bytes.length) return { done: true, value: undefined };
            const value = bytes.slice(offset, offset + chunkSize);
            offset += chunkSize;
            chunksRead++;
            return { done: false, value };
          },
        };
      },
    },
  };
  return { response, release };
}

function makeSandbox(responsesByUrl, { cached = {} } = {}) {
  const calls = { batches: [], resets: 0, rendered: [], errors: [], progressVisible: false };
  const element = () => ({
    dataset: {},
    textContent: "",
    setAttribute() {},
    classList: {
      add(name) { if (name === "map-progress-visible") calls.progressVisible = true; },
      remove(name) { if (name === "map-progress-visible") calls.progressVisible = false; },
    },
    style: {},
    querySelector() { return element(); },
    appendChild() {},
    innerHTML: "",
  });
  const sandbox = {
    console: { ...console, log() {} },
    URLSearchParams,
    AbortController,
    TextDecoder,
    TextEncoder,
    document: {
      getElementById() { return element(); },
      createElement() { return element(); },
      querySelector() { return element(); },
    },
    mapConfig: { featuresLayerGeometriesUrl: "/geom", featuresId: null },
    hideMapOverlay() {},
    buildUrl(base, params) { return `${base}?${params.toString()}`; },
    normalizeUrl(url) { return url; },
    async getFromIndexedDB(key) { return cached[key] || null; },
    async storeInIndexedDB() {},
    async cleanupCache() {},
    orderLayers() {},
    displayErrorMessage(error) { calls.errors.push(error); },
    renderFeatures(geojson) { calls.rendered.push(geojson); },
    resetFeaturesLayer() { calls.resets++; },
    addFeatureBatch(batch) {
      calls.batches.push(batch.map((f) => f.properties.tag));
      return true;
    },
    fetch(url, options) {
      const entry = responsesByUrl[url];
      if (!entry) throw new Error(`unexpected fetch ${url}`);
      entry.response.signal = options.signal;
      return Promise.resolve(entry.response);
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  return { sandbox, calls };
}

const tick = () => new Promise((r) => setImmediate(r));
async function settle(n = 20) {
  for (let i = 0; i < n; i++) await tick();
}

test("a newer load aborts the previous one and ignores its stale batches", async () => {
  const a = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "A") }),
    120000,
  );
  const b = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "B") }),
    120000,
  );
  const { sandbox, calls } = makeSandbox({ "/geom?f=a": a, "/geom?f=b": b });

  const loadA = sandbox.fetchFeatureGeometriesWithProgress({ f: "a" });
  a.release(1);
  await settle();
  assert.ok(calls.batches.length >= 1, "A rendered its first batch");
  assert.ok(calls.batches.every((tags) => tags.every((t) => t === "A")));

  const loadB = sandbox.fetchFeatureGeometriesWithProgress({ f: "b" });
  await settle();
  const resetsAfterBStart = calls.resets;
  assert.equal(resetsAfterBStart, 2, "B resets the layer on start");

  // A tries to continue; it must be aborted and contribute nothing more.
  a.release(10);
  b.release(10);
  await settle();
  await Promise.allSettled([loadA, loadB]);

  const afterB = calls.batches.slice(1);
  assert.ok(afterB.length >= 1, "B rendered batches");
  assert.ok(
    afterB.every((tags) => tags.every((t) => t === "B")),
    "no batches from A after B started",
  );
  assert.equal(calls.resets, resetsAfterBStart, "A's abort does not reset B's layer");
  assert.equal(calls.rendered.length, 0, "no fallback full render");
});

test("a failed stream removes its partially rendered layer", async () => {
  const a = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "A") }),
    120000,
    { failAfterChunks: 1 },
  );
  const { sandbox, calls } = makeSandbox({ "/geom?f=a": a });

  const load = sandbox.fetchFeatureGeometriesWithProgress({ f: "a" });
  a.release(1);
  await settle();
  assert.ok(calls.batches.length >= 1, "first batch rendered before failure");
  assert.equal(calls.resets, 1);

  a.release(1);
  await assert.rejects(load, /connection dropped/);
  assert.equal(calls.resets, 2, "partial layer removed after the stream failed");
  assert.equal(calls.errors.length, 1);
});

test("a cached replacement hides the aborted load's progress bar", async () => {
  const a = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "A") }),
    120000,
  );
  const cachedB = { type: "FeatureCollection", features: makeFeatures(3, "B") };
  const head = {
    response: { ok: true, headers: { get: (n) => (n === "X-Data-Version" ? "v1" : null) } },
  };
  const { sandbox, calls } = makeSandbox(
    { "/geom?f=a": a, "/geom?f=b": head },
    { cached: { "/geom?f=b": { data: cachedB, version: "v1" } } },
  );

  const loadA = sandbox.fetchFeatureGeometriesWithProgress({ f: "a" });
  a.release(1);
  await settle();
  assert.equal(calls.progressVisible, true, "A shows the progress bar");

  await sandbox.fetchFeatureGeometriesWithProgress({ f: "b" });
  a.release(10);
  await Promise.allSettled([loadA]);

  assert.equal(calls.progressVisible, false, "bar hidden after cached replacement");
  assert.deepEqual(calls.rendered, [cachedB]);
  assert.equal(calls.errors.length, 0);
});

test("a superseded load resolves with a superseded marker instead of undefined", async () => {
  const a = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "A") }),
    120000,
  );
  const b = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "B") }),
    120000,
  );
  const { sandbox } = makeSandbox({ "/geom?f=a": a, "/geom?f=b": b });

  const loadA = sandbox.fetchFeatureGeometriesWithProgress({ f: "a" });
  a.release(1);
  await settle();
  const loadB = sandbox.fetchFeatureGeometriesWithProgress({ f: "b" });
  a.release(10);
  b.release(10);

  const [resultA, resultB] = await Promise.all([loadA, loadB]);
  assert.deepEqual(resultA, { superseded: true });
  assert.equal(resultB, undefined);
});

test("a failure inside the first batch still removes the attached layer", async () => {
  const a = controlledResponse(
    JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500, "A") }),
    120000,
  );
  const { sandbox, calls } = makeSandbox({ "/geom?f=a": a });
  sandbox.addFeatureBatch = () => { throw new Error("Invalid GeoJSON object."); };

  const load = sandbox.fetchFeatureGeometriesWithProgress({ f: "a" });
  a.release(10);
  await assert.rejects(load, /Invalid GeoJSON/);
  assert.equal(calls.resets, 2, "layer reset after the first-batch failure");
});
