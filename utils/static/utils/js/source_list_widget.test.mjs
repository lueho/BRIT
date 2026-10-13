import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(HERE, "source_list_widget.js"), "utf8");

function setup() {
    const sandbox = {
        console,
        document: {
            addEventListener() {},
            querySelectorAll() {
                return [];
            },
        },
    };
    vm.runInNewContext(source, sandbox);
    return { sandbox };
}

// Objects created inside the vm context carry a different Object.prototype,
// so normalize them before comparing structurally.
const plain = (value) => JSON.parse(JSON.stringify(value));

test("parsePersonName splits 'Last, First' at the comma", () => {
    const { sandbox } = setup();
    assert.deepEqual(plain(sandbox.parsePersonName("Test, Herbert")), {
        first_names: "Herbert",
        last_names: "Test",
    });
});

test("parsePersonName splits 'First Last' at the last word", () => {
    const { sandbox } = setup();
    assert.deepEqual(plain(sandbox.parsePersonName("Herbert Test")), {
        first_names: "Herbert",
        last_names: "Test",
    });
    assert.deepEqual(plain(sandbox.parsePersonName("Hans Peter Schmidt")), {
        first_names: "Hans Peter",
        last_names: "Schmidt",
    });
});

test("parsePersonName stores a single word as last_names only", () => {
    const { sandbox } = setup();
    assert.deepEqual(plain(sandbox.parsePersonName("Madonna")), {
        first_names: "",
        last_names: "Madonna",
    });
});

test("parsePersonName rejects blank input and a missing surname", () => {
    const { sandbox } = setup();
    assert.equal(sandbox.parsePersonName("   "), null);
    assert.equal(sandbox.parsePersonName(", Herbert"), null);
});

test("personDisplayName renders 'Last, First' and bare surnames", () => {
    const { sandbox } = setup();
    assert.equal(
        sandbox.personDisplayName({ first_names: "Herbert", last_names: "Test" }),
        "Test, Herbert"
    );
    assert.equal(
        sandbox.personDisplayName({ first_names: "", last_names: "Madonna" }),
        "Madonna"
    );
});

test("buildAuthorCreateOptions offers explicit person and organization options", () => {
    const { sandbox } = setup();
    const options = sandbox.buildAuthorCreateOptions("Herbert Test");

    assert.equal(options.length, 2);

    const [person, organization] = options;
    assert.equal(person.author_type, "person");
    assert.equal(person.first_names, "Herbert");
    assert.equal(person.last_names, "Test");
    assert.equal(person.label, "Test, Herbert");
    assert.equal(person.create_label, 'Create person "Test, Herbert"');
    assert.equal(person.pending, true);

    assert.equal(organization.author_type, "organization");
    assert.equal(organization.organization_name, "Herbert Test");
    assert.equal(organization.create_label, 'Create organization "Herbert Test"');
    assert.equal(organization.pending, true);
});

test("buildAuthorCreateOptions keeps comma input as person too", () => {
    const { sandbox } = setup();
    const [person] = sandbox.buildAuthorCreateOptions("Test, Herbert");
    assert.equal(person.label, "Test, Herbert");
});

test("buildAuthorCreateOptions returns nothing for blank input", () => {
    const { sandbox } = setup();
    assert.equal(sandbox.buildAuthorCreateOptions("  ").length, 0);
});

test("authorOptionToMetadata sends pending authors without an id", () => {
    const { sandbox } = setup();
    const [person, organization] = sandbox.buildAuthorCreateOptions("Herbert Test");

    assert.deepEqual(plain(sandbox.authorOptionToMetadata(person)), {
        first_names: "Herbert",
        last_names: "Test",
    });
    assert.deepEqual(plain(sandbox.authorOptionToMetadata(organization)), {
        author_type: "organization",
        organization_name: "Herbert Test",
    });
});

test("authorOptionToMetadata sends existing authors by id only", () => {
    const { sandbox } = setup();
    assert.deepEqual(
        plain(sandbox.authorOptionToMetadata({ id: 42, label: "Test, Herbert" })),
        { id: "42" }
    );
    assert.equal(sandbox.authorOptionToMetadata(null), null);
});
