import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
    new URL("./catchment_draw_form.js", import.meta.url),
    "utf8",
);

const flush = () => new Promise((resolve) => setImmediate(resolve));

function deferred() {
    let resolve, reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

const FEATURE = {
    type: "Feature",
    properties: { id: 7 },
    geometry: {
        type: "Polygon",
        coordinates: [[[10, 50], [11, 50], [11, 51], [10, 51], [10, 50]]],
    },
};

function makeField(value = "") {
    const listeners = {};
    return {
        value,
        addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
        change(value) {
            if (value !== undefined) this.value = value;
            for (const fn of listeners.change || []) fn({ target: this });
        },
    };
}

function makeMap() {
    return {
        added: [],
        removed: [],
        fitted: [],
        addLayer(layer) { this.added.push(layer); },
        removeLayer(layer) { this.removed.push(layer); },
        fitBounds(bounds) { this.fitted.push(bounds); },
    };
}

function makeGeoJSONLayer(data, options) {
    const layers = (data.features || []).filter((f) => f.geometry);
    return {
        data,
        options,
        getLayers() { return layers; },
        getBounds() { return { valid: layers.length > 0 }; },
        addTo(map) { map.addLayer(this); return this; },
    };
}

function setup({ initialValue = "", map = makeMap(), withMap = true } = {}) {
    const configEl = {
        dataset: {
            geojsonUrl: "/maps/api/region/geojson/",
            regionFieldId: "id_parent_region",
            mapId: "id_geom-map",
        },
    };
    const field = makeField(initialValue);
    const elements = {
        "parent-region-preview": configEl,
        id_parent_region: field,
    };
    const windowListeners = {};
    const fetches = [];
    const createdLayers = [];
    const sandbox = {
        window: {
            location: new URL("http://localhost/maps/catchments/create/draw_custom/"),
            addEventListener(type, fn) { (windowListeners[type] ||= []).push(fn); },
            removeEventListener(type, fn) {
                windowListeners[type] = (windowListeners[type] || []).filter(
                    (f) => f !== fn,
                );
            },
        },
        document: {
            getElementById: (id) => elements[id] || null,
        },
        console: { ...console, error() {} },
        URL,
        fetch: (url) => {
            const d = deferred();
            fetches.push({ url: String(url), deferred: d });
            return d.promise;
        },
        L: {
            geoJSON: (data, options) => {
                const layer = makeGeoJSONLayer(data, options);
                createdLayers.push(layer);
                return layer;
            },
        },
    };
    if (withMap) {
        sandbox.window[`leafletmap${configEl.dataset.mapId}`] = map;
    }
    sandbox.window.dispatch = (type, detail) => {
        for (const fn of windowListeners[type] || []) fn({ detail });
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return { sandbox, field, map, fetches, createdLayers };
}

const okResponse = (data) => ({ ok: true, json: () => Promise.resolve(data) });

test("selecting a parent region fetches and draws its boundary", async () => {
    const { field, map, fetches, createdLayers } = setup();

    field.change("7");
    assert.equal(fetches.length, 1);
    assert.ok(fetches[0].url.endsWith("/maps/api/region/geojson/?id=7"));

    fetches[0].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();

    assert.equal(createdLayers.length, 1);
    assert.equal(createdLayers[0].options.interactive, false);
    assert.equal(map.added.length, 1);
    assert.equal(map.fitted.length, 1);
});

test("clearing the parent region removes the boundary layer", async () => {
    const { field, map, fetches, createdLayers } = setup();

    field.change("7");
    fetches[0].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();
    const layer = createdLayers[0];

    field.change("");
    assert.equal(fetches.length, 1, "no fetch for empty selection");
    assert.deepEqual(map.removed, [layer]);
});

test("switching regions replaces the boundary layer", async () => {
    const { field, map, fetches, createdLayers } = setup();

    field.change("7");
    fetches[0].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();
    const first = createdLayers[0];

    field.change("8");
    fetches[1].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();

    assert.deepEqual(map.removed, [first]);
    assert.equal(map.added.length, 2);
    assert.equal(map.fitted.length, 2);
});

test("a superseded fetch response does not render a stale boundary", async () => {
    const { field, map, fetches, createdLayers } = setup();

    field.change("7");
    field.change("8");
    assert.equal(fetches.length, 2);

    // The stale first request resolves after the newer one was issued.
    fetches[0].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();
    assert.equal(createdLayers.length, 0);

    fetches[1].deferred.resolve(okResponse({ features: [FEATURE] }));
    await flush();
    assert.equal(createdLayers.length, 1);
    assert.equal(map.added.length, 1);
});

test("a parent region without geometry is not rendered or zoomed to", async () => {
    const { field, map, fetches, createdLayers } = setup();

    field.change("9");
    fetches[0].deferred.resolve(
        okResponse({ features: [{ ...FEATURE, geometry: null }] }),
    );
    await flush();

    assert.equal(createdLayers.length, 1);
    assert.equal(map.added.length, 0);
    assert.equal(map.fitted.length, 0);
});

test("a preselected parent region loads its boundary on init", async () => {
    const { fetches } = setup({ initialValue: "11" });
    assert.equal(fetches.length, 1);
    assert.ok(fetches[0].url.endsWith("/maps/api/region/geojson/?id=11"));
});

test("waits for map:init when the map is not initialized yet", async () => {
    const { sandbox, field, map, fetches } = setup({ withMap: false });

    field.change("7");
    assert.equal(fetches.length, 0, "no fetch before the map exists");

    sandbox.window.dispatch("map:init", { id: "id_geom-map", map });
    // The pending selection is picked up once the map appears.
    assert.equal(fetches.length, 1);
    assert.ok(fetches[0].url.endsWith("/maps/api/region/geojson/?id=7"));
});
