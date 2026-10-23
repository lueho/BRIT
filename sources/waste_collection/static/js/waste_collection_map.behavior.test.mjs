import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_collection_map.js"), "utf8");
// In production the base template loads the shared helpers before this file.
const formatUtilsSource = readFileSync(
    join(HERE, "../../../../utils/static/js/format_utils.js"),
    "utf8"
);
const mapFeatureUtilsSource = readFileSync(
    join(HERE, "../../../../maps/static/js/map_feature_utils.js"),
    "utf8"
);

test("selecting a collection activates the Summary tab before details load", () => {
  let detailsRequested = false;
  let summaryTabShown = false;
  const elements = {
    "summary-container": { innerHTML: "" },
    "summary-tab": {},
  };
  const sandbox = {
    AbortController,
    CustomEvent: class CustomEvent {
      constructor(type, init) {
        this.type = type;
        this.detail = init.detail;
      }
    },
    URLSearchParams,
    console,
    document: {
      getElementById(id) {
        return elements[id] || null;
      },
      addEventListener() {},
      dispatchEvent() {},
    },
    getFeatureDetails() {
      detailsRequested = true;
      return new Promise(() => {});
    },
    bootstrap: {
      Tab: {
        getOrCreateInstance() {
          return {
            show() {
              summaryTabShown = true;
            },
          };
        },
      },
    },
    dispatchEvent() {},
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(formatUtilsSource, sandbox);
  vm.runInContext(mapFeatureUtilsSource, sandbox);
  vm.runInContext(source, sandbox);

  vm.runInContext("SelectionController", sandbox).select(42);

  assert.equal(detailsRequested, true);
  assert.equal(summaryTabShown, true);
});

test("popup links carry data-wc-select and no inline onclick handler", () => {
  const popupHtml = [];
  const polygons = [11, 22].map(id => ({
    feature: {
      properties: { id, catchment: "C", waste_category: "W", collection_system: "S" },
    },
    toGeoJSON() {
      return { geometry: {} };
    },
  }));
  class Polygon {}
  const sandbox = {
    AbortController,
    CustomEvent: class CustomEvent {},
    URLSearchParams,
    console,
    L: { Polygon, point: (x, y) => ({ x, y }) },
    turf: { inside: () => true },
    map: {
      openPopup(html) {
        popupHtml.push(html);
      },
    },
    document: {
      getElementById: () => null,
      addEventListener() {},
      dispatchEvent() {},
    },
    getFeatureDetails: () => new Promise(() => {}),
    bootstrap: { Tab: { getOrCreateInstance: () => ({ show() {} }) } },
  };
  polygons.forEach(layer => Object.setPrototypeOf(layer, Polygon.prototype));
  const featureGroup = { eachLayer: cb => polygons.forEach(cb) };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(formatUtilsSource, sandbox);
  vm.runInContext(mapFeatureUtilsSource, sandbox);
  vm.runInContext(source, sandbox);

  sandbox.featureClickHandler({ latlng: { lng: 14, lat: 55 } }, featureGroup);

  assert.match(popupHtml[0], /data-wc-select="11"/);
  assert.match(popupHtml[0], /data-wc-select="22"/);
  assert.doesNotMatch(popupHtml[0], /onclick=/);
});

test("a delegated click on a popup link selects the feature without a page reload", () => {
  let clickHandler = null;
  let prevented = false;
  const sandbox = {
    AbortController,
    CustomEvent: class CustomEvent {},
    URLSearchParams,
    console,
    document: {
      getElementById: () => null,
      addEventListener(type, cb) {
        if (type === "click") clickHandler = cb;
      },
      dispatchEvent() {},
    },
    getFeatureDetails: () => new Promise(() => {}),
    bootstrap: { Tab: { getOrCreateInstance: () => ({ show() {} }) } },
    dispatchEvent() {},
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(formatUtilsSource, sandbox);
  vm.runInContext(mapFeatureUtilsSource, sandbox);
  vm.runInContext(source, sandbox);
  vm.runInContext(
    "SelectionController.select = (fid) => { window.__testSelectedId = fid; };",
    sandbox
  );

  const link = { dataset: { wcSelect: "42" } };
  const event = {
    target: { closest: () => link },
    preventDefault() {
      prevented = true;
    },
  };
  clickHandler(event);

  assert.equal(sandbox.__testSelectedId, "42");
  assert.equal(prevented, true);
  assert.equal(sandbox.__wc_selectFromPopup, undefined);
});
