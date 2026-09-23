import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./nuts_region_map.js", import.meta.url), "utf8");

function deferred() {
    let resolve, reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

// Stubs for functions that live in maps.js are seeded before eval; the file
// itself only declares the NUTS-specific lifecycle (updateLayers, cleanup, ...).
function setup() {
    const calls = {
        refreshMap: 0,
        hideLoadingIndicator: 0,
        unlockForm: 0,
        unlockFilter: 0,
        prepareMapRefresh: 0,
        regionGuards: [],
        catchmentGuards: [],
    };
    const featureLoads = [];
    const sandbox = {
        window: { location: new URL("http://localhost/maps/nuts/"), fetch: () => {} },
        document: {
            addEventListener() {},
            getElementById: () => null,
            querySelector: () => null,
            querySelectorAll: () => [],
        },
        console: { ...console, log() {}, error() {} },
        URL,
        URLSearchParams,
        Request: class {},
        mapConfig: {},
        catchmentLayer: null,
        removeExistingLayer() {},
        fetchRegionGeometry: (params, isCurrent) => {
            calls.regionGuards.push(isCurrent);
            return Promise.resolve();
        },
        fetchCatchmentGeometry: (params, isCurrent) => {
            calls.catchmentGuards.push(isCurrent);
            return Promise.resolve();
        },
        fetchFeatureGeometries: () => {
            const d = deferred();
            featureLoads.push(d);
            return d.promise;
        },
        prepareMapRefresh: () => { calls.prepareMapRefresh += 1; },
        refreshMap: () => { calls.refreshMap += 1; },
        hideLoadingIndicator: () => { calls.hideLoadingIndicator += 1; },
        unlockFilter: () => { calls.unlockFilter += 1; },
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    const realUnlockForm = sandbox.unlockForm;
    sandbox.unlockForm = () => { calls.unlockForm += 1; return realUnlockForm(); };
    return { sandbox, calls, featureLoads };
}

test("a superseded NUTS update releases its spinner without refreshing or unlocking", async () => {
    const { sandbox, calls, featureLoads } = setup();

    const first = sandbox.updateLayers({ region_params: { id: 1 }, feature_params: { levl_code: 0 } });
    const second = sandbox.updateLayers({ region_params: { id: 2 }, feature_params: { levl_code: 1 } });
    assert.equal(calls.regionGuards[0](), false, "first region render must be guarded off");
    assert.equal(calls.regionGuards[1](), true);

    featureLoads[0].resolve({ superseded: true });
    await first;
    assert.equal(calls.refreshMap, 0);
    assert.equal(calls.unlockForm, 0);
    assert.equal(calls.unlockFilter, 0);
    assert.equal(calls.hideLoadingIndicator, 1);

    featureLoads[1].resolve(undefined);
    await second;
    assert.equal(calls.refreshMap, 1);
    assert.equal(calls.hideLoadingIndicator, 1);
});

test("a failed current NUTS update runs cleanup once", async () => {
    const { sandbox, calls, featureLoads } = setup();

    const update = sandbox.updateLayers({ catchment_params: { id: 3 }, feature_params: { id: 3 } });
    assert.equal(calls.catchmentGuards[0](), true);
    featureLoads[0].reject(new Error("boom"));
    await update;
    assert.equal(calls.refreshMap, 0);
    assert.equal(calls.hideLoadingIndicator, 1);
    assert.equal(calls.unlockForm, 1);
    assert.equal(calls.unlockFilter, 1);
});
