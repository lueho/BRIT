import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_collection_map.js"), "utf8");

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
  vm.runInContext(source, sandbox);

  sandbox.SelectionController.select(42);

  assert.equal(detailsRequested, true);
  assert.equal(summaryTabShown, true);
});
