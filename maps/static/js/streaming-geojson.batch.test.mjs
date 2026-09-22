// Dependency-free unit tests for StreamingGeoJSONLoader incremental feature
// batches (progressive map rendering).
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "streaming-geojson.js"), "utf8");

const sandbox = { console, window: {}, TextDecoder, AbortController, document: undefined };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { StreamingGeoJSONLoader } = sandbox.window;

function makeFeatures(count) {
  const features = [];
  for (let i = 0; i < count; i++) {
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [10.0 + i / 1000, 53.5] },
      properties: { id: i },
    });
  }
  return features;
}

function fakeResponse(payload, chunkSize) {
  const bytes = new TextEncoder().encode(payload);
  let offset = 0;
  return {
    body: {
      getReader() {
        return {
          async read() {
            if (offset >= bytes.length) return { done: true, value: undefined };
            const value = bytes.slice(offset, offset + chunkSize);
            offset += chunkSize;
            return { done: false, value };
          },
        };
      },
    },
  };
}

test("onFeatureBatch receives parsed features before onComplete", async () => {
  const total = 1500;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(total) });
  const batches = [];
  const order = [];
  const loader = new StreamingGeoJSONLoader({
    onFeatureBatch: (batch) => {
      order.push("batch");
      batches.push(batch.slice());
    },
    onComplete: () => order.push("complete"),
  });

  const geojson = await loader._parseStreamingResponse(
    fakeResponse(payload, 16 * 1024),
    total,
    payload.length,
  );

  assert.ok(batches.length >= 2, `expected multiple batches, got ${batches.length}`);
  // Batches must arrive before completion, and cover every feature exactly
  // once, in stream order.
  assert.strictEqual(order[order.length - 1], "complete");
  const flat = batches.flat();
  assert.strictEqual(flat.length, total);
  // vm-realm objects fail deepStrictEqual on prototype; compare ids.
  assert.strictEqual(
    JSON.stringify(flat.map((f) => f.properties.id)),
    JSON.stringify(geojson.features.map((f) => f.properties.id)),
  );
});

test("batch sizes stay bounded", async () => {
  const total = 3000;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(total) });
  const batches = [];
  const loader = new StreamingGeoJSONLoader({
    onFeatureBatch: (batch) => batches.push(batch.length),
  });

  await loader._parseStreamingResponse(fakeResponse(payload, 64 * 1024), total, payload.length);

  assert.ok(batches.length >= 3, `expected several batches, got ${batches}`);
  assert.ok(
    batches.every((n) => n <= 1000),
    `batch exceeds 1000 features: ${batches}`,
  );
  assert.strictEqual(batches.reduce((a, b) => a + b, 0), total);
});

test("empty stream emits no batches but still completes", async () => {
  const payload = JSON.stringify({ type: "FeatureCollection", features: [] });
  let batchCalls = 0;
  let completed = null;
  const loader = new StreamingGeoJSONLoader({
    onFeatureBatch: () => batchCalls++,
    onComplete: (geojson) => { completed = geojson; },
  });

  await loader._parseStreamingResponse(fakeResponse(payload, 16 * 1024), 0, payload.length);

  assert.strictEqual(batchCalls, 0);
  assert.strictEqual(completed.features.length, 0);
});

test("loader without onFeatureBatch still works", async () => {
  const total = 120;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(total) });
  let completed = null;
  const loader = new StreamingGeoJSONLoader({
    onComplete: (geojson) => { completed = geojson; },
  });

  const geojson = await loader._parseStreamingResponse(
    fakeResponse(payload, 16 * 1024),
    total,
    payload.length,
  );

  assert.strictEqual(geojson.features.length, total);
  assert.strictEqual(completed.features.length, total);
});

test("an async onFeatureBatch is awaited before the next batch and onComplete", async () => {
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(2500) });
  const order = [];
  const loader = new StreamingGeoJSONLoader({
    onFeatureBatch: async (batch) => {
      order.push(`start:${batch.length}`);
      await new Promise((r) => setTimeout(r, 5));
      order.push(`end:${batch.length}`);
    },
    onComplete: () => order.push("complete"),
  });
  await loader._parseStreamingResponse(fakeResponse(payload, 4096), 2500);
  assert.deepEqual(order, [
    "start:1000", "end:1000",
    "start:1000", "end:1000",
    "start:500", "end:500",
    "complete",
  ]);
});
