import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./maps.js", import.meta.url), "utf8");

// Function declarations inside maps.js overwrite same-named sandbox globals at
// evaluation time, so spies for those must be installed after eval. Stubs for
// externals that live in other files (filter_utils.js) are seeded beforehand.
function setup({
    confirmResult = true,
    parsedParams = new URLSearchParams(),
    sliders = [],
} = {}) {
    const calls = {
        loadLayers: [],
        showMapOverlay: 0,
        confirm: 0,
        prepareMapRefresh: 0,
        cleanup: 0,
    };
    const mapConfig = { loadFeatures: false };
    const sliderElements = sliders.map(({ id, rangeMin, rangeMax }) => ({
        id,
        dataset: { range_min: rangeMin, range_max: rangeMax },
    }));
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
            getElementById: (id) => {
                for (const { id: sliderId, name } of sliders) {
                    for (const suffix of ["min", "max", "is_null"]) {
                        if (id === `${sliderId}_${suffix}`) {
                            return { name: `${name}_${suffix}` };
                        }
                    }
                }
                return null;
            },
            querySelector: () => null,
            querySelectorAll: (selector) => (
                selector === ".numeric-slider-range" ? sliderElements : []
            ),
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

test("untouched slider state is not constraining", () => {
    const { sandbox } = setup({
        sliders: [{
            id: "id_plantation_year",
            name: "plantation_year",
            rangeMin: "1900",
            rangeMax: "2025",
        }],
    });
    const params = new URLSearchParams(
        "plantation_year_min=1900.00&plantation_year_max=2025.00&" +
        "plantation_year_is_null=true&scope=published",
    );
    assert.equal(sandbox.hasConstrainingFilterParameters(params), false);
});

test("narrowed slider is constraining", () => {
    const { sandbox } = setup({
        sliders: [{
            id: "id_plantation_year",
            name: "plantation_year",
            rangeMin: "1900",
            rangeMax: "2025",
        }],
    });
    const params = new URLSearchParams(
        "plantation_year_min=1950.00&plantation_year_max=2025.00&" +
        "plantation_year_is_null=true",
    );
    assert.equal(sandbox.hasConstrainingFilterParameters(params), true);
});

test("excluding unknowns is constraining", () => {
    const { sandbox } = setup({
        sliders: [{
            id: "id_plantation_year",
            name: "plantation_year",
            rangeMin: "1900",
            rangeMax: "2025",
        }],
    });
    const params = new URLSearchParams(
        "plantation_year_min=1900.00&plantation_year_max=2025.00&" +
        "plantation_year_is_null=false",
    );
    assert.equal(sandbox.hasConstrainingFilterParameters(params), true);
});

test("default slider values on a guarded map still trigger confirmation", () => {
    const untouchedParams = new URLSearchParams(
        "plantation_year_min=1900.00&plantation_year_max=2025.00&" +
        "plantation_year_is_null=true&scope=published",
    );
    const { sandbox, calls, mapConfig } = setup({
        confirmResult: false,
        sliders: [{
            id: "id_plantation_year",
            name: "plantation_year",
            rangeMin: "1900",
            rangeMax: "2025",
        }],
        parsedParams: untouchedParams,
    });
    mapConfig.guardUnfilteredLoad = true;
    sandbox.clickedFilterButton();
    assert.equal(calls.confirm, 1);
    assert.equal(calls.loadLayers.length, 0);
});

test("range-like params without a matching slider remain constraining", () => {
    const { sandbox } = setup();
    assert.equal(
        sandbox.hasConstrainingFilterParameters(new URLSearchParams("foo_min=1")),
        true,
    );
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

test("loadLayers skips refreshMap when the feature load was superseded", async () => {
    const { sandbox, calls, mapConfig } = setup();
    mapConfig.loadFeatures = true;
    let refreshes = 0;
    let hides = 0;
    sandbox.refreshMap = () => { refreshes += 1; };
    sandbox.hideLoadingIndicator = () => { hides += 1; };
    sandbox.fetchFeatureGeometries = () => Promise.resolve({ superseded: true });

    sandbox.loadLayers(new URLSearchParams({ name: "oak" }));
    await new Promise((r) => setImmediate(r));

    assert.equal(refreshes, 0);
    assert.equal(calls.cleanup, 0);
    // Leaflet.Spin refcounts spin(true) calls, so the superseded load must
    // still release its own reference without touching the filter lock.
    assert.equal(hides, 1);
});

test("loadLayers refreshes when the feature load completed normally", async () => {
    const { sandbox, mapConfig } = setup();
    mapConfig.loadFeatures = true;
    let refreshes = 0;
    sandbox.refreshMap = () => { refreshes += 1; };
    sandbox.fetchFeatureGeometries = () => Promise.resolve();

    sandbox.loadLayers(new URLSearchParams({ name: "oak" }));
    await new Promise((r) => setImmediate(r));

    assert.equal(refreshes, 1);
});

test("loadLayers cleans up once when the current feature load rejects", async () => {
    const { sandbox, calls, mapConfig } = setup();
    mapConfig.loadFeatures = true;
    let refreshes = 0;
    sandbox.refreshMap = () => { refreshes += 1; };
    sandbox.fetchFeatureGeometries = () => Promise.reject(new Error("stream truncated"));

    sandbox.loadLayers(new URLSearchParams({ name: "oak" }));
    await new Promise((r) => setImmediate(r));

    assert.equal(refreshes, 0);
    assert.equal(calls.cleanup, 1);
});

test("a superseded loadLayers call does not render its companion layers", async () => {
    const { sandbox, mapConfig } = setup();
    mapConfig.loadFeatures = true;
    mapConfig.loadRegion = true;
    mapConfig.regionId = 7;
    mapConfig.regionLayerGeometriesUrl = "/regions/geojson/";
    mapConfig.loadFeaturesLayerSummary = true;
    mapConfig.featuresLayerSummariesUrl = "/summaries/";
    const rendered = [];
    sandbox.renderRegion = (data) => rendered.push(["region", data]);
    sandbox.renderSummaries = (data) => rendered.push(["summary", data]);
    sandbox.refreshMap = () => {};

    // setup() stubs the companion fetchers; put the real ones back so the
    // generation guard inside them is exercised.
    const fresh = vm.createContext({ ...sandbox });
    vm.runInContext(source, fresh);
    sandbox.fetchRegionGeometry = fresh.fetchRegionGeometry;
    sandbox.fetchFeaturesLayerSummary = fresh.fetchFeaturesLayerSummary;
    fresh.mapConfig = mapConfig;
    fresh.renderRegion = sandbox.renderRegion;
    fresh.renderSummaries = sandbox.renderSummaries;

    let releaseA;
    const gateA = new Promise((r) => { releaseA = r; });
    let fetchCount = 0;
    fresh.fetchWithVersionValidation = async () => {
        fetchCount += 1;
        if (fetchCount === 1) await gateA;
        return { data: { id: fetchCount } };
    };
    let summaryCount = 0;
    fresh.fetch = async () => {
        summaryCount += 1;
        if (summaryCount === 1) await gateA;
        const id = summaryCount;
        return { ok: true, json: async () => ({ id }) };
    };
    let featureCount = 0;
    sandbox.fetchFeatureGeometries = () => {
        featureCount += 1;
        return featureCount === 1
            ? Promise.resolve({ superseded: true })
            : Promise.resolve();
    };

    sandbox.loadLayers(new URLSearchParams({ name: "oak" }));
    sandbox.loadLayers(new URLSearchParams({ name: "beech" }));
    await new Promise((r) => setImmediate(r));
    releaseA();
    for (let i = 0; i < 5; i++) await new Promise((r) => setImmediate(r));

    assert.deepEqual(rendered, [["region", { id: 2 }], ["summary", { id: 2 }]]);
});

function fakeBounds(tag) {
    return { tag, isValid: () => true };
}

function setupFeatureRendering() {
    const { sandbox, window } = setup();
    const map = { removeLayer() {} };
    window.listeners["map:init"]({ detail: { map } });
    const calls = { created: [], added: [], batches: [] };
    sandbox.L = {
        geoJson(data, options) {
            calls.created.push({ data, options });
            return {
                on() {},
                addTo(target) { calls.added.push(target); },
                addData(features) { calls.batches.push(features); },
            };
        },
    };
    return { sandbox, calls, map };
}

const locatedFeature = {
    type: "Feature",
    id: 2,
    geometry: { type: "Point", coordinates: [14, 55] },
    properties: {},
};
const unlocatedFeature = { type: "Feature", id: 1, geometry: null, properties: {} };

test("renderFeatures ignores null geometries before and after located points", () => {
    const { sandbox, calls, map } = setupFeatureRendering();
    const geoJson = {
        type: "FeatureCollection",
        features: [unlocatedFeature, locatedFeature, unlocatedFeature],
    };

    sandbox.renderFeatures(geoJson);

    assert.deepEqual(Array.from(calls.created[0].data.features), [locatedFeature]);
    assert.equal(typeof calls.created[0].options.pointToLayer, "function");
    assert.deepEqual(calls.added, [map]);
    assert.equal(geoJson.features.length, 3);
});

test("renderFeatures leaves no layer for an all-null collection", () => {
    const { sandbox, calls } = setupFeatureRendering();
    sandbox.renderFeatures({ type: "FeatureCollection", features: [unlocatedFeature] });
    assert.equal(calls.created.length, 0);
    assert.equal(vm.runInContext("featuresLayer", sandbox), null);
});

test("addFeatureBatch skips null geometry batches and filters mixed batches", () => {
    const { sandbox, calls, map } = setupFeatureRendering();
    assert.equal(sandbox.addFeatureBatch([unlocatedFeature]), false);
    assert.equal(calls.created.length, 0);
    assert.equal(sandbox.addFeatureBatch([unlocatedFeature, locatedFeature]), true);
    assert.equal(sandbox.addFeatureBatch([locatedFeature, unlocatedFeature]), true);
    assert.equal(sandbox.addFeatureBatch([unlocatedFeature]), false);
    assert.equal(calls.created.length, 1);
    assert.equal(typeof calls.created[0].options.pointToLayer, "function");
    assert.deepEqual(calls.added, [map]);
    assert.deepEqual(calls.batches.map(batch => Array.from(batch)), [
        [locatedFeature], [locatedFeature],
    ]);
});

function fakeLayer(bounds) {
    return {
        addTo() {},
        on() {},
        getBounds: () => bounds,
    };
}

function setupBoundsScenario({ sandbox, window, mapConfig }) {
    mapConfig.adjustBoundsToLayer = "region";
    const fitted = [];
    const fakeMap = { fitBounds: (b) => fitted.push(b), removeLayer() {} };
    window.listeners["map:init"]({ detail: { map: fakeMap } });

    const regionBounds = fakeBounds("region");
    const regionLayer = fakeLayer(regionBounds);
    sandbox.L = { geoJson: () => regionLayer };
    sandbox.renderRegion({ type: "FeatureCollection", features: [] });

    const featureBounds = fakeBounds("features");
    const featuresLayer = fakeLayer(featureBounds);
    sandbox.createFeaturesLayer = () => featuresLayer;
    const geoJson = {
        type: "FeatureCollection",
        features: [{
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [] },
            properties: {},
        }],
    };
    return { fitted, regionBounds, featureBounds, geoJson };
}

test("adjustMapBounds zooms to the filtered feature selection", () => {
    const { sandbox, window, mapConfig } = setup();
    const { fitted, featureBounds, geoJson } = setupBoundsScenario({
        sandbox, window, mapConfig,
    });
    sandbox.renderFeatures(geoJson);

    sandbox.adjustMapBounds(new URLSearchParams({ name: "oak" }));

    assert.equal(fitted.length, 1);
    assert.equal(fitted[0], featureBounds);
});

test("adjustMapBounds keeps the configured layer when unconstrained", () => {
    const { sandbox, window, mapConfig } = setup();
    const { fitted, regionBounds, geoJson } = setupBoundsScenario({
        sandbox, window, mapConfig,
    });
    sandbox.renderFeatures(geoJson);

    sandbox.adjustMapBounds(new URLSearchParams());

    assert.equal(fitted.length, 1);
    assert.equal(fitted[0], regionBounds);
});

test("an empty filtered result falls back instead of zooming to stale features", () => {
    const { sandbox, window, mapConfig } = setup();
    const { fitted, regionBounds, geoJson } = setupBoundsScenario({
        sandbox, window, mapConfig,
    });
    sandbox.renderFeatures(geoJson);
    sandbox.renderFeatures({ type: "FeatureCollection", features: [] });

    sandbox.adjustMapBounds(new URLSearchParams({ name: "oak" }));

    assert.equal(fitted.length, 1);
    assert.equal(fitted[0], regionBounds);
});

test("loadLayers forwards the filter parameters to refreshMap", async () => {
    const { sandbox, mapConfig } = setup();
    mapConfig.loadFeatures = true;
    let seen;
    sandbox.refreshMap = (promises, filterParameters) => {
        seen = filterParameters;
    };
    sandbox.fetchFeatureGeometries = () => Promise.resolve();

    sandbox.loadLayers(new URLSearchParams({ name: "oak" }));
    await new Promise((r) => setImmediate(r));

    assert.equal(seen?.get("name"), "oak");
});

test("map:init points Leaflet's default icon path at the leaflet static dir", () => {
    const { sandbox, window } = setup();
    sandbox.L = { Icon: { Default: {} } };
    sandbox.document.querySelector = (selector) => (
        selector === 'script[src*="/leaflet/leaflet."]'
            ? { src: "https://cdn.example/static/leaflet/leaflet.25c3da10cb19.js" }
            : null
    );

    window.listeners["map:init"]({ detail: { map: {} } });

    assert.equal(
        sandbox.L.Icon.Default.imagePath,
        "https://cdn.example/static/leaflet/images/",
    );
});

test("map:init keeps an explicitly configured default icon path", () => {
    const { sandbox, window } = setup();
    sandbox.L = { Icon: { Default: { imagePath: "/custom/" } } };
    sandbox.document.querySelector = () => ({
        src: "https://cdn.example/static/leaflet/leaflet.js",
    });

    window.listeners["map:init"]({ detail: { map: {} } });

    assert.equal(sandbox.L.Icon.Default.imagePath, "/custom/");
});
