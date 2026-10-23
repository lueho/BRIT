import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./map_feature_utils.js", import.meta.url), "utf8");

function setup() {
    class FakePolygon {}
    const sandbox = { console, L: { Polygon: FakePolygon } };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return { sandbox, FakePolygon };
}

function recordingLayer() {
    const layer = { calls: [] };
    layer.setStyle = (style) => layer.calls.push(["setStyle", style]);
    layer.bringToFront = () => layer.calls.push(["bringToFront"]);
    layer.bringToBack = () => layer.calls.push(["bringToBack"]);
    return layer;
}

test("selectMapFeature applies the default highlight and promotes the layer", () => {
    const { sandbox } = setup();
    const layer = recordingLayer();
    sandbox.selectMapFeature(layer);
    // The style object is created inside the vm realm, so compare fields.
    assert.equal(layer.calls[0][0], "setStyle");
    assert.equal(layer.calls[0][1].color, "#f49a33");
    assert.deepEqual(layer.calls[1], ["bringToFront"]);
    assert.equal(layer.calls.length, 2);
});

test("selectMapFeature accepts a custom style and promote predicate", () => {
    const { sandbox, FakePolygon } = setup();
    const polygon = Object.assign(new FakePolygon(), recordingLayer());
    const marker = recordingLayer();
    const promote = (layer) => !(layer instanceof FakePolygon);

    const style = { color: "#123456" };
    sandbox.selectMapFeature(polygon, { style, promote });
    sandbox.selectMapFeature(marker, { style, promote });

    assert.deepEqual(polygon.calls, [["setStyle", style]]);
    assert.deepEqual(marker.calls, [["setStyle", style], ["bringToFront"]]);
});

test("selectMapFeature tolerates missing layers and layer methods", () => {
    const { sandbox } = setup();
    sandbox.selectMapFeature(null);
    sandbox.selectMapFeature({});
});

test("resetMapFeatureStyles resets the group and demotes it by default", () => {
    const { sandbox } = setup();
    const calls = [];
    const group = {
        resetStyle: () => calls.push("resetStyle"),
        bringToBack: () => calls.push("bringToBack"),
    };
    sandbox.resetMapFeatureStyles(group);
    assert.deepEqual(calls, ["resetStyle", "bringToBack"]);
});

test("resetMapFeatureStyles applies an explicit style to each layer", () => {
    const { sandbox } = setup();
    const layers = [recordingLayer(), recordingLayer()];
    const group = {
        eachLayer: (cb) => layers.forEach(cb),
        resetStyle() { throw new Error("resetStyle must not run when a style is given"); },
    };
    const style = { color: "#999" };
    sandbox.resetMapFeatureStyles(group, { style, demote: "none" });
    assert.deepEqual(layers[0].calls, [["setStyle", style]]);
    assert.deepEqual(layers[1].calls, [["setStyle", style]]);
});

test("resetMapFeatureStyles demotes only polygons when asked", () => {
    const { sandbox, FakePolygon } = setup();
    const polygon = Object.assign(new FakePolygon(), recordingLayer());
    const marker = recordingLayer();
    const group = { eachLayer: (cb) => [polygon, marker].forEach(cb), resetStyle() {} };

    sandbox.resetMapFeatureStyles(group, { demote: "polygons" });

    assert.deepEqual(polygon.calls, [["bringToBack"]]);
    assert.deepEqual(marker.calls, []);
});

test("resetMapFeatureStyles tolerates a missing group", () => {
    const { sandbox } = setup();
    sandbox.resetMapFeatureStyles(null);
    sandbox.resetMapFeatureStyles(undefined);
});
