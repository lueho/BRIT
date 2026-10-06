import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./maps.js", import.meta.url), "utf8");

const ASSET_VERSION = "0123456789abcdef0123456789abcdef";
const assetUrl = `http://localhost/maps/regions/5/geojson/${ASSET_VERSION}.json?id=5`;
const ordinaryUrl = "http://localhost/maps/api/region/geojson/?id=5";

function fakeIndexedDB(storeData) {
    const requestFor = (resultFactory) => {
        const req = {};
        queueMicrotask(() => req.onsuccess?.({ target: { result: resultFactory() } }));
        return req;
    };
    const objectStore = () => ({
        get: (key) => requestFor(() => storeData.get(key)),
        put: (entry) => {
            storeData.set(entry.url, entry);
            return requestFor(() => undefined);
        },
        delete: (key) => {
            storeData.delete(key);
            return requestFor(() => undefined);
        },
        index: () => ({ openCursor: () => requestFor(() => null) }),
    });
    const db = {
        objectStoreNames: { contains: () => true },
        createObjectStore: () => objectStore(),
        transaction: () => ({ objectStore }),
    };
    return {
        open: () => {
            const req = {};
            queueMicrotask(() => {
                req.onupgradeneeded?.({ target: { result: db } });
                req.onsuccess?.({ target: { result: db } });
            });
            return req;
        },
    };
}

function makeHeaders(entries) {
    return new Map(Object.entries(entries));
}

function setup({ mapConfig = {} } = {}) {
    const store = new Map();
    const fetchCalls = [];
    const sandbox = {
        window: {
            location: new URL("http://localhost/maps/geodatasets/3/map/"),
            history: { replaceState() {} },
            addEventListener() {},
        },
        document: { getElementById: () => null },
        console,
        URL,
        URLSearchParams,
        Date,
        indexedDB: fakeIndexedDB(store),
        mapConfig,
        fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            const isAsset = url.includes(`/geojson/${ASSET_VERSION}.json`);
            return {
                ok: true,
                status: 200,
                statusText: "OK",
                json: async () => ({
                    type: "FeatureCollection",
                    features: [],
                    version: "server-version",
                }),
                headers: makeHeaders(
                    isAsset
                        ? {
                              "X-Data-Version": ASSET_VERSION,
                              "Cache-Control": "public, max-age=31536000, immutable",
                          }
                        : { "X-Data-Version": "server-version" }
                ),
            };
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return { sandbox, store, fetchCalls };
}

test("immutable region asset URL is recognized only for same-origin versioned paths", () => {
    const { sandbox } = setup();
    assert.equal(sandbox.isImmutableRegionAssetUrl(assetUrl), true);
    assert.equal(
        sandbox.isImmutableRegionAssetUrl(
            `https://evil.example.com/maps/regions/5/geojson/${ASSET_VERSION}.json`
        ),
        false
    );
    assert.equal(sandbox.isImmutableRegionAssetUrl(ordinaryUrl), false);
    assert.equal(
        sandbox.isImmutableRegionAssetUrl(
            "http://localhost/maps/regions/5/geojson/not-hex.json"
        ),
        false
    );
});

test("immutable asset cache hit is reused without any network request", async () => {
    const { sandbox, store, fetchCalls } = setup();
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    store.set(cacheKey, {
        url: cacheKey,
        data: { type: "FeatureCollection", features: [{ stale: true }] },
        timestamp: Date.now() - 3 * 86400000,
        version: ASSET_VERSION,
    });
    const result = await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(result.fromCache, true);
    assert.equal(result.data.features[0].stale, true);
    assert.equal(fetchCalls.length, 0);
});

test("cached asset entry with wrong version is not reused", async () => {
    const { sandbox, store, fetchCalls } = setup();
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    store.set(cacheKey, {
        url: cacheKey,
        data: { type: "FeatureCollection", features: [{ stale: true }] },
        timestamp: Date.now(),
        version: "ffffffffffffffffffffffffffffffff",
    });
    const result = await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(result.fromCache, false);
    assert.equal(fetchCalls.length, 1);
});

test("immutable asset miss fetches once and stores with X-Data-Version", async () => {
    const { sandbox, store, fetchCalls } = setup();
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    const result = await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(result.fromCache, false);
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, assetUrl);
    assert.equal(store.get(cacheKey).version, ASSET_VERSION);
});

test("asset response with no-store Cache-Control is returned but not cached", async () => {
    const { sandbox, store, fetchCalls } = setup();
    sandbox.fetch = async (url) => {
        fetchCalls.push({ url });
        return {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ type: "FeatureCollection", features: [] }),
            headers: makeHeaders({
                "X-Data-Version": ASSET_VERSION,
                "Cache-Control": "no-store",
            }),
        };
    };
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    const first = await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(first.fromCache, false);
    assert.equal(store.has(cacheKey), false);
    const second = await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(second.fromCache, false);
    assert.equal(fetchCalls.length, 2);
});

test("asset response missing immutable Cache-Control is not cached", async () => {
    const { sandbox, store, fetchCalls } = setup();
    sandbox.fetch = async (url) => {
        fetchCalls.push({ url });
        return {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ type: "FeatureCollection", features: [] }),
            headers: makeHeaders({ "X-Data-Version": ASSET_VERSION }),
        };
    };
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(store.has(cacheKey), false);
});

test("asset response with mismatched version header is not cached", async () => {
    const { sandbox, store, fetchCalls } = setup();
    sandbox.fetch = async (url) => {
        fetchCalls.push({ url });
        return {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ type: "FeatureCollection", features: [] }),
            headers: makeHeaders({
                "X-Data-Version": "ffffffffffffffffffffffffffffffff",
                "Cache-Control": "public, max-age=31536000, immutable",
            }),
        };
    };
    const cacheKey = sandbox.normalizeUrl(assetUrl);
    await sandbox.fetchWithVersionValidation(assetUrl, cacheKey);
    assert.equal(store.has(cacheKey), false);
});

test("ordinary cached URL still validates the version over the network", async () => {
    const { sandbox, store, fetchCalls } = setup();
    const cacheKey = sandbox.normalizeUrl(ordinaryUrl);
    store.set(cacheKey, {
        url: cacheKey,
        data: { type: "FeatureCollection", features: [] },
        timestamp: Date.now(),
        version: "server-version",
    });
    const result = await sandbox.fetchWithVersionValidation(ordinaryUrl, cacheKey);
    assert.equal(result.fromCache, true);
    assert.equal(fetchCalls.length, 1);
    assert.ok(fetchCalls[0].url.includes("/version/"));
});

test("ordinary cached URL older than 24h is expired and refetched", async () => {
    const { sandbox, store, fetchCalls } = setup();
    const cacheKey = sandbox.normalizeUrl(ordinaryUrl);
    store.set(cacheKey, {
        url: cacheKey,
        data: { type: "FeatureCollection", features: [{ stale: true }] },
        timestamp: Date.now() - 2 * 86400000,
        version: "server-version",
    });
    const result = await sandbox.fetchWithVersionValidation(ordinaryUrl, cacheKey);
    assert.equal(result.fromCache, false);
    assert.ok(fetchCalls.length >= 1);
});

test("fetchRegionGeometry uses the asset URL for the configured region", async () => {
    const mapConfig = {
        regionLayerGeometriesUrl: `/maps/regions/5/geojson/${ASSET_VERSION}.json`,
        regionLayerDynamicGeometriesUrl: "/maps/api/region/geojson/",
        regionId: 5,
    };
    const { sandbox, fetchCalls } = setup({ mapConfig });
    const fetched = [];
    sandbox.fetchWithVersionValidation = async (url) => {
        fetched.push(url);
        return { data: { type: "FeatureCollection", features: [] } };
    };
    let rendered = null;
    sandbox.renderRegion = (data) => { rendered = data; };
    await sandbox.fetchRegionGeometry({ id: 5 });
    assert.equal(fetched.length, 1);
    assert.ok(fetched[0].includes(`/geojson/${ASSET_VERSION}.json`));
    assert.notEqual(rendered, null);
});

test("fetchRegionGeometry falls back to dynamic URL for a different region", async () => {
    const mapConfig = {
        regionLayerGeometriesUrl: `/maps/regions/5/geojson/${ASSET_VERSION}.json`,
        regionLayerDynamicGeometriesUrl: "/maps/api/region/geojson/",
        regionId: 5,
    };
    const { sandbox, fetchCalls } = setup({ mapConfig });
    const fetched = [];
    sandbox.fetchWithVersionValidation = async (url) => {
        fetched.push(url);
        return { data: { type: "FeatureCollection", features: [{ other: true }] } };
    };
    let rendered = null;
    sandbox.renderRegion = (data) => { rendered = data; };
    await sandbox.fetchRegionGeometry({ id: 42 });
    assert.equal(fetched.length, 1);
    assert.ok(fetched[0].startsWith("http://localhost/maps/api/region/geojson/"));
    assert.ok(fetched[0].includes("id=42"));
    assert.equal(rendered.features[0].other, true);
    assert.equal(fetchCalls.length, 0);
});

test("fetchRegionGeometry without dynamic URL fails instead of serving wrong region", async () => {
    const mapConfig = {
        regionLayerGeometriesUrl: `/maps/regions/5/geojson/${ASSET_VERSION}.json`,
        regionId: 5,
    };
    const { sandbox } = setup({ mapConfig });
    const fetched = [];
    sandbox.fetchWithVersionValidation = async (url) => {
        fetched.push(url);
        return { data: {} };
    };
    const errors = [];
    sandbox.displayErrorMessage = (error) => errors.push(error);
    await sandbox.fetchRegionGeometry({ id: 42 });
    assert.equal(fetched.length, 0);
    assert.equal(errors.length, 1);
});
