import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("./evaluation_progress.js", import.meta.url), "utf8");

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
        dataset: { statusUrl: "/inventories/scenarios/evaluating/__task__/" },
        querySelectorAll: () => rows,
        querySelector: (selector) => elements[selector],
    };
    return { root, badges, progress, bar, count };
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

test("polls pending tasks until all are finished, then reloads", async () => {
    const { initEvaluationProgress } = load();
    const page = fakePage(["a", "b"]);
    const replies = { a: ["SUCCESS"], b: ["STARTED", "SUCCESS"] };
    const requested = [];
    const scheduled = [];
    let reloaded = 0;
    const reload = () => { reloaded += 1; };

    await initEvaluationProgress(page.root, {
        fetchJson: async (url) => {
            requested.push(url);
            const taskId = url.split("/").at(-2);
            return { task_status: replies[taskId].shift() };
        },
        reload,
        schedule: (callback) => scheduled.push(callback),
    });

    assert.deepEqual(requested, [
        "/inventories/scenarios/evaluating/a/",
        "/inventories/scenarios/evaluating/b/",
    ]);
    assert.equal(page.badges.a.textContent, "Done");
    assert.equal(page.badges.b.className, "badge text-bg-info");
    assert.equal(page.bar.style.width, "50%");
    assert.equal(page.progress.attributes["aria-valuenow"], "1");
    assert.equal(page.count.textContent, "1 of 2 inventories calculated");
    assert.notEqual(scheduled.at(-1), reload);

    await scheduled.at(-1)();

    assert.equal(requested.length, 3, "finished tasks are not polled again");
    assert.equal(page.bar.style.width, "100%");
    assert.equal(scheduled.at(-1), reload);
    assert.equal(reloaded, 0);
});

test("keeps polling when a status request fails", async () => {
    const { initEvaluationProgress } = load();
    const page = fakePage(["a"]);
    const scheduled = [];

    await initEvaluationProgress(page.root, {
        fetchJson: async () => { throw new Error("offline"); },
        reload: () => {},
        schedule: (callback) => scheduled.push(callback),
    });

    assert.equal(page.badges.a.textContent, "Queued");
    assert.equal(page.count.textContent, "0 of 1 inventories calculated");
    assert.equal(scheduled.length, 1);
});

test("reloads to pick up tasks that are not registered yet", async () => {
    const { initEvaluationProgress } = load();
    const page = fakePage([]);
    const scheduled = [];
    const reload = () => {};

    await initEvaluationProgress(page.root, {
        reload,
        schedule: (callback, delay) => scheduled.push([callback, delay]),
    });

    assert.deepEqual(scheduled, [[reload, 3000]]);
});
