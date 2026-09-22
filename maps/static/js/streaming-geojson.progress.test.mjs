// Dependency-free unit tests for StreamingGeoJSONLoader progress reporting.
//
// The module is evaluated in a vm context with a stubbed `window`; the
// streaming parser is fed a synthetic FeatureCollection through a fake
// response body. Run with:
//
//   docker compose run --rm assets node \
//     maps/static/js/streaming-geojson.progress.test.mjs
//
// (wrapped by `make js-test`).
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

test("streamed progress never moves backward", async () => {
  const total = 1000;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(total) });
  const reported = [];
  const loader = new StreamingGeoJSONLoader({
    onProgress: (loaded, totalCount) => reported.push([loaded, totalCount]),
  });

  // No Content-Length: the loader falls back to the 3 KB/feature estimate,
  // which badly understates these ~80-byte features.
  const geojson = await loader._parseStreamingResponse(fakeResponse(payload, 16 * 1024), total, 0);

  assert.strictEqual(geojson.features.length, total);
  assert.ok(reported.length > 2);
  for (let i = 1; i < reported.length; i++) {
    assert.ok(
      reported[i][0] >= reported[i - 1][0],
      `progress regressed at call ${i}: ${reported[i - 1][0]} -> ${reported[i][0]}`,
    );
    assert.strictEqual(reported[i][1], total);
  }
  assert.deepStrictEqual(reported[reported.length - 1], [total, total]);
});

test("completion reports the exact parsed count when the stream is short", async () => {
  // Server skipped one feature mid-stream but X-Total-Count still says 1000.
  const advertised = 1000;
  const streamed = 999;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(streamed) });
  const reported = [];
  const loader = new StreamingGeoJSONLoader({
    onProgress: (loaded, totalCount) => reported.push([loaded, totalCount]),
  });

  // Content-Length matches the body, so byte progress reaches `advertised`.
  const geojson = await loader._parseStreamingResponse(
    fakeResponse(payload, 16 * 1024),
    advertised,
    payload.length,
  );

  assert.strictEqual(geojson.features.length, streamed);
  assert.deepStrictEqual(reported[reported.length - 1], [streamed, advertised]);
});

test("progress still advances between chunks", async () => {
  const total = 1000;
  const payload = JSON.stringify({ type: "FeatureCollection", features: makeFeatures(total) });
  const reported = [];
  const loader = new StreamingGeoJSONLoader({
    onProgress: (loaded) => reported.push(loaded),
  });

  await loader._parseStreamingResponse(fakeResponse(payload, 16 * 1024), total, payload.length);

  const distinct = new Set(reported);
  assert.ok(distinct.size >= 4, `expected several distinct progress values, got ${[...distinct]}`);
});
