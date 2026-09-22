import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./maps.js", import.meta.url), "utf8");

// Function declarations inside maps.js overwrite same-named sandbox globals at
// evaluation time, so spies for those must be installed after eval. Stubs for
// externals that live in other files (filter_utils.js) are seeded beforehand.
function setup({ confirmResult = true, parsedParams = new URLSearchParams() } = {}) {
    const calls = {
        loadLayers: [],
        showMapOverlay: 0,
        confirm: 0,
        prepareMapRefresh: 0,
        cleanup: 0,
    };
    const mapConfig = { loadFeatures: false };
    const window = {
        location: new URL("http://localhost/maps/geodatasets/3/map/"),
        history: { replaceState() {} },
        listeners: {},
        addEventListener(type, cb) { this.listeners[type] = cb; },
        confirm() { calls.confirm += 1; return confirmResult; },
    };
    const sandbox = {
        window,
        document: {
            getElementById: () => null,
            querySelector: () => null,
            querySelectorAll: () => [],
        },
        console,
        URL,
        URLSearchParams,
        mapConfig,
        // Externals provided by filter_utils.js
        parseFilterParameters: () => parsedParams,
        lockFilter: () => {},
        unlockFilter: () => {},
        lockCustomElements: () => {},
        unlockCustomElements: () => {},
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);

    // Spy on loadLayers; stub functions that would hit fetch/indexedDB/Leaflet.
    const realLoadLayers = sandbox.loadLayers;
    sandbox.loadLayers = (params) => {
        calls.loadLayers.push(params);
        return realLoadLayers(params);
    };
    const realShowMapOverlay = sandbox.showMapOverlay;
    sandbox.showMapOverlay = () => {
        calls.showMapOverlay += 1;
        return realShowMapOverlay();
    };
    const realPrepareMapRefresh = sandbox.prepareMapRefresh;
    sandbox.prepareMapRefresh = () => {
        calls.prepareMapRefresh += 1;
        return realPrepareMapRefresh();
    };
    const realCleanup = sandbox.cleanup;
    sandbox.cleanup = () => {
        calls.cleanup += 1;
        return realCleanup();
    };
    sandbox.getQueryParameters = () => new URLSearchParams();
    sandbox.fetchRegionGeometry = () => Promise.resolve();
    sandbox.fetchCatchmentGeometry = () => Promise.resolve();
    sandbox.fetchFeatureGeometries = () => Promise.resolve();
    sandbox.fetchFeaturesLayerSummary = () => Promise.resolve();
    sandbox.removeExistingLayer = () => {};
    sandbox.refreshMap = () => {};
    sandbox.hideLoadingIndicator = () => {};
    sandbox.showLoadingIndicator = () => {};
    return { sandbox, calls, mapConfig, window };
}

test("hasConstrainingFilterParameters ignores scope and navigation params", () => {
    const { sandbox } = setup();
    const onlyScope = new URLSearchParams({ scope: "published", page: "2" });
    assert.equal(sandbox.hasConstrainingFilterParameters(onlyScope), false);
    assert.equal(sandbox.hasConstrainingFilterParameters(new URLSearchParams()), false);
    assert.equal(sandbox.hasConstrainingFilterParameters(null), false);
});

test("hasConstrainingFilterParameters detects a real filter value", () => {
    const { sandbox } = setup();
    const params = new URLSearchParams({ scope: "published", name: "oak" });
    assert.equal(sandbox.hasConstrainingFilterParameters(params), true);
});

test("deferred features flag the unfiltered-load guard", () => {
    const { sandbox, calls, mapConfig } = setup();
    sandbox.loadLayers(new URLSearchParams());
    assert.equal(mapConfig.guardUnfilteredLoad, true);
    assert.equal(calls.showMapOverlay, 1);
});

test("unfiltered click on a guarded map asks for confirmation and aborts when declined", () => {
    const { sandbox, calls, mapConfig } = setup({ confirmResult: false });
    mapConfig.guardUnfilteredLoad = true;
    sandbox.clickedFilterButton();
    assert.equal(calls.confirm, 1);
    assert.equal(calls.loadLayers.length, 0);
    assert.equal(calls.prepareMapRefresh, 0);
    assert.equal(mapConfig.loadFeatures, false);
    assert.equal(calls.showMapOverlay, 1);
});

test("unfiltered click on a guarded map loads after confirmation", () => {
    const { sandbox, calls, mapConfig } = setup({ confirmResult: true });
    mapConfig.guardUnfilteredLoad = true;
    sandbox.clickedFilterButton();
    assert.equal(calls.confirm, 1);
    assert.equal(calls.loadLayers.length, 1);
    assert.equal(mapConfig.loadFeatures, true);
    assert.equal(mapConfig.guardUnfilteredLoad, false);
});

test("constrained click on a guarded map loads without confirmation", () => {
    const { sandbox, calls, mapConfig } = setup({
        parsedParams: new URLSearchParams({ name: "spruce" }),
    });
    mapConfig.guardUnfilteredLoad = true;
    sandbox.clickedFilterButton();
    assert.equal(calls.confirm, 0);
    assert.equal(calls.loadLayers.length, 1);
});

test("unguarded map does not ask for confirmation", () => {
    const { sandbox, calls } = setup();
    sandbox.clickedFilterButton();
    assert.equal(calls.confirm, 0);
    assert.equal(calls.loadLayers.length, 1);
});
