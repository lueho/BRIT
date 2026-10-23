import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./format_utils.js", import.meta.url), "utf8");

function setup() {
    const sandbox = { console };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    return sandbox;
}

test("formatHeader humanizes snake_case and camelCase keys", () => {
    const sandbox = setup();
    assert.equal(sandbox.formatHeader("waste_category"), "Waste Category");
    assert.equal(sandbox.formatHeader("collectionSystem"), "Collection System");
    assert.equal(sandbox.formatHeader("name"), "Name");
});

test("formatList renders a ul for separator-delimited values", () => {
    const sandbox = setup();
    const html = sandbox.formatList("paper, glass , metal", ", ");
    assert.match(html, /^<ul class="list-disc pl-4">/);
    assert.equal(html.match(/<li>/g).length, 3);
    assert.match(html, /<li>glass<\/li>/);
});

test("formatList returns an empty string for empty input", () => {
    const sandbox = setup();
    assert.equal(sandbox.formatList(null, ", "), "");
    assert.equal(sandbox.formatList("", ", "), "");
    assert.equal(sandbox.formatList(" , ", ", "), "");
});

test("truncateUrl shortens only overlong urls", () => {
    const sandbox = setup();
    const short = "https://example.com";
    assert.equal(sandbox.truncateUrl(short), short);
    const long = `https://example.com/${"a".repeat(60)}`;
    const truncated = sandbox.truncateUrl(long);
    assert.equal(truncated.length, 43);
    assert.ok(truncated.endsWith("..."));
});

test("formatUrls renders one linked li per url", () => {
    const sandbox = setup();
    assert.equal(sandbox.formatUrls(""), "");
    const html = sandbox.formatUrls("https://a.example, https://b.example");
    assert.equal(html.match(/<li>/g).length, 2);
    assert.match(html, /href="https:\/\/a\.example"/);
    assert.match(html, /rel="noopener noreferrer"/);
});

test("createFieldConfig expands boolean shorthand with the default format", () => {
    const sandbox = setup();
    const config = sandbox.createFieldConfig({ name: true, internal: false });
    assert.equal(config.name.include, true);
    assert.equal(config.internal.include, false);
    assert.equal(config.name.format("oak"), "oak");
    assert.equal(config.name.format(null), "");
});

test("createFieldConfig keeps custom formatters and include flags", () => {
    const sandbox = setup();
    const config = sandbox.createFieldConfig({
        population: { include: false, format: (v) => v.toLocaleString() },
    });
    assert.equal(config.population.include, false);
    assert.equal(config.population.format(1200), (1200).toLocaleString());
});

test("createFieldConfig defaults include to true and format to identity", () => {
    const sandbox = setup();
    const config = sandbox.createFieldConfig({ notes: {} });
    assert.equal(config.notes.include, true);
    assert.equal(config.notes.format("text"), "text");
});
