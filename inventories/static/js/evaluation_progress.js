"use strict";

// Polls the evaluation status of a running scenario, shows the Celery state of
// each algorithm task as a progress bar and reloads the page once the scenario
// has stopped running, so the result (or failure) page replaces it.

const EVALUATION_TASK_STATES = {
    PENDING: { label: "Queued", tone: "secondary", finished: false },
    RECEIVED: { label: "Queued", tone: "secondary", finished: false },
    STARTED: { label: "Calculating…", tone: "info", finished: false },
    RETRY: { label: "Retrying…", tone: "warning", finished: false },
    SUCCESS: { label: "Done", tone: "success", finished: true },
    FAILURE: { label: "Failed", tone: "danger", finished: true },
    REVOKED: { label: "Cancelled", tone: "danger", finished: true },
};

const UNKNOWN_TASK_STATE = { label: "Queued", tone: "secondary", finished: false };

function describeTaskStatus(status) {
    return EVALUATION_TASK_STATES[status] || UNKNOWN_TASK_STATE;
}

function summarizeProgress(statuses, total) {
    const finished = Object.values(statuses).filter(
        (status) => describeTaskStatus(status).finished,
    ).length;
    return {
        finished,
        total,
        percent: total ? Math.round((finished * 100) / total) : 0,
        complete: finished >= total,
    };
}

function progressMessage(progress) {
    if (progress.complete) {
        return "All inventories calculated. Saving the results…";
    }
    return `${progress.finished} of ${progress.total} inventories calculated`;
}

async function fetchTaskStatus(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
        throw new Error(`Status request failed: ${response.status}`);
    }
    return response.json();
}

function initEvaluationProgress(root, {
    fetchJson = fetchTaskStatus,
    reload = () => window.location.reload(),
    schedule = (callback, delay) => setTimeout(callback, delay),
    pollInterval = 1500,
} = {}) {
    const rows = Array.from(root.querySelectorAll("[data-task-id]"));
    const progressElement = root.querySelector('[role="progressbar"]');
    const bar = root.querySelector("[data-progress-bar]");
    const count = root.querySelector("[data-progress-count]");
    const statuses = {};

    function renderTask(row, status) {
        const state = describeTaskStatus(status);
        const badge = row.querySelector("[data-task-status]");
        badge.className = `badge text-bg-${state.tone}`;
        badge.textContent = state.label;
    }

    function renderProgress(progress) {
        bar.style.width = `${progress.percent}%`;
        progressElement.setAttribute("aria-valuenow", String(progress.finished));
        count.textContent = progressMessage(progress);
    }

    async function poll() {
        let result;
        try {
            result = await fetchJson(root.dataset.statusUrl);
        } catch {
            // A failed status request is retried on the next poll.
        }
        if (result && !result.running) {
            // The result page now shows the results or the failure.
            reload();
            return;
        }
        for (const row of rows) {
            const status = result && result.tasks[row.dataset.taskId];
            if (status) {
                statuses[row.dataset.taskId] = status;
                renderTask(row, status);
            }
        }
        if (rows.length) {
            renderProgress(summarizeProgress(statuses, rows.length));
        }
        schedule(poll, pollInterval);
    }

    return poll();
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
        const root = document.querySelector("[data-evaluation-progress]");
        if (root) {
            initEvaluationProgress(root);
        }
    });
}
