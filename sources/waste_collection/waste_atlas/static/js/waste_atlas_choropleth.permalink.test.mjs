import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "waste_atlas_choropleth.js"), "utf8");

const sandbox = { console, window: { location: { pathname: "/current/" } } };
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const { permalink } = sandbox.WasteAtlasChoropleth;

const target = {
  base: "https://example.test/waste_collection/waste-atlas/p/DE-BW/collection_system/",
  country: "DE",
  nutsPrefix: "DE1",
  nutsLevel: "1",
  years: "2020,2021,2022,2023,2024",
};

test("an in-place year change moves the permalink to that year", () => {
  assert.equal(
    permalink.urlFor(target, { country: "DE", nutsPrefix: "DE1", nutsLevel: 1, year: 2023 }),
    `${target.base}2023/`,
  );
});

test("a region other than the permalink's own yields no permalink", () => {
  for (const loaded of [
    { country: "SE", nutsPrefix: "DE1", nutsLevel: 1, year: 2024 },
    { country: "DE", nutsPrefix: "DE2", nutsLevel: 1, year: 2024 },
    { country: "DE", nutsPrefix: "DE1", nutsLevel: 2, year: 2024 },
    { country: "DE", year: 2024 },
  ]) {
    assert.equal(permalink.urlFor(target, loaded), "");
  }
});

test("years without a permalink and change maps yield no permalink", () => {
  const loaded = { country: "DE", nutsPrefix: "DE1", nutsLevel: 1 };
  assert.equal(permalink.urlFor(target, { ...loaded, year: 2019 }), "");
  assert.equal(permalink.urlFor(target, { ...loaded, year: 2024, changeMode: true }), "");
});

test("a rejected clipboard write falls back to copying the selected field", async () => {
  const field = { value: "https://example.test/p/", select() {} };
  const clipboard = { writeText: () => Promise.reject(new Error("denied")) };
  let fallbackCalls = 0;

  const copied = await permalink.copy(field, clipboard, () => {
    fallbackCalls += 1;
    return true;
  });

  assert.equal(copied, true);
  assert.equal(fallbackCalls, 1);
});

test("copy reports failure when neither the clipboard nor the fallback works", async () => {
  const field = { value: "https://example.test/p/", select() {} };
  const clipboard = { writeText: () => Promise.reject(new Error("denied")) };

  assert.equal(await permalink.copy(field, clipboard, () => false), false);
  assert.equal(await permalink.copy(field, undefined, () => { throw new Error("no"); }), false);
});

test("copy uses the clipboard when it is allowed", async () => {
  const field = { value: "https://example.test/p/", select() {} };
  let written = null;
  const clipboard = { writeText: (text) => { written = text; return Promise.resolve(); } };

  assert.equal(await permalink.copy(field, clipboard, () => false), true);
  assert.equal(written, field.value);
});
