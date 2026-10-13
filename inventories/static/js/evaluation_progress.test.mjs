import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./evaluation_progress.js", import.meta.url), "utf8");
const STATUS_URL = "/inventories/scenarios/8/evaluation-status/";

function load() {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    return context;
}

function fakePage(taskIds) {
    const badges = {};
    const rows = taskIds.map((taskId) => {
        const badge = { className: "badge text-bg-secondary", textContent: "Queued" };
        badges[taskId] = badge;
        return { dataset: { taskId }, querySelector: () => badge };
    });
    const progress = { attributes: {}, setAttribute(name, value) { this.attributes[name] = value; } };
    const bar = { style: {} };
    const count = { textContent: "" };
    const elements = {
        '[role="progressbar"]': progress,
        "[data-progress-bar]": bar,
        "[data-progress-count]": count,
    };
    const root = {
        dataset: { statusUrl: STATUS_URL },
        querySelectorAll: () => rows,
        querySelector: (selector) => elements[selector],
    };
    return { root, badges, progress, bar, count };
}

function run(page, replies) {
    const { initEvaluationProgress } = load();
    const requested = [];
    const scheduled = [];
    const reloads = [];
    const promise = initEvaluationProgress(page.root, {
        fetchJson: async (url) => {
            requested.push(url);
            const reply = replies.shift();
            if (reply instanceof Error) throw reply;
            return reply;
        },
        reload: () => reloads.push(true),
        schedule: (callback) => scheduled.push(callback),
    });
    return { promise, requested, scheduled, reloads };
}

test("describeTaskStatus turns Celery states into readable labels", () => {
    const { describeTaskStatus } = load();

    assert.equal(describeTaskStatus("PENDING").label, "Queued");
    assert.equal(describeTaskStatus("STARTED").label, "Calculating…");
    assert.equal(describeTaskStatus("SUCCESS").finished, true);
    assert.equal(describeTaskStatus("FAILURE").tone, "danger");
    assert.equal(describeTaskStatus("SOMETHING_NEW").finished, false);
});

test("summarizeProgress counts succeeded and failed tasks as finished", () => {
    const { summarizeProgress } = load();

    const progress = summarizeProgress({ a: "SUCCESS", b: "FAILURE", c: "STARTED" }, 4);

    assert.deepEqual({ ...progress }, { finished: 2, total: 4, percent: 50, complete: false });
});

test("shows task progress from the scenario status while it is running", async () => {
    const page = fakePage(["a", "b"]);
    const { promise, requested, scheduled, reloads } = run(page, [
        { running: true, tasks: { a: "SUCCESS", b: "STARTED" } },
    ]);
    await promise;

    assert.deepEqual(requested, [STATUS_URL]);
    assert.equal(page.badges.a.textContent, "Done");
    assert.equal(page.badges.b.className, "badge text-bg-info");
    assert.equal(page.bar.style.width, "50%");
    assert.equal(page.progress.attributes["aria-valuenow"], "1");
    assert.equal(page.count.textContent, "1 of 2 inventories calculated");
    assert.equal(scheduled.length, 1);
    assert.equal(reloads.length, 0);
});

test("waits for the results to be saved after all tasks are done", async () => {
    const page = fakePage(["a"]);
    const { promise, scheduled, reloads } = run(page, [
        { running: true, tasks: { a: "SUCCESS" } },
        { running: false, tasks: {} },
    ]);
    await promise;

    assert.equal(page.bar.style.width, "100%");
    assert.equal(page.count.textContent, "All inventories calculated. Saving the results…");
    assert.equal(reloads.length, 0, "no reload while the scenario is still running");

    await scheduled.at(-1)();

    assert.equal(reloads.length, 1);
    assert.equal(page.badges.a.textContent, "Done", "finished tasks keep their state");
});

test("reloads once the scenario stops running, also for failed evaluations", async () => {
    const page = fakePage(["a"]);
    const { promise, reloads, scheduled } = run(page, [
        { running: false, tasks: { a: "FAILURE" } },
    ]);
    await promise;

    assert.equal(reloads.length, 1);
    assert.equal(scheduled.length, 0);
});

test("keeps polling when a status request fails", async () => {
    const page = fakePage(["a"]);
    const { promise, scheduled, reloads } = run(page, [new Error("offline")]);
    await promise;

    assert.equal(page.badges.a.textContent, "Queued");
    assert.equal(page.count.textContent, "0 of 1 inventories calculated");
    assert.equal(scheduled.length, 1);
    assert.equal(reloads.length, 0);
});

test("polls instead of reloading when no tasks are registered yet", async () => {
    const page = fakePage([]);
    const { promise, requested, scheduled, reloads } = run(page, [
        { running: true, tasks: {} },
        { running: false, tasks: {} },
    ]);
    await promise;

    assert.deepEqual(requested, [STATUS_URL]);
    assert.equal(reloads.length, 0);

    await scheduled.at(-1)();

    assert.equal(reloads.length, 1);
});

test("reloads to list tasks registered after the page was rendered", async () => {
    const page = fakePage([]);
    const { promise, scheduled, reloads } = run(page, [
        { running: true, tasks: { a: "STARTED" } },
    ]);
    await promise;

    assert.equal(reloads.length, 1);
    assert.equal(scheduled.length, 0);
});
