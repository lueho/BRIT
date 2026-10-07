"use strict";

// Polls the Celery state of every algorithm task of a running scenario
// evaluation, shows it as a progress bar and reloads the page once all tasks
// are finished, so the result (or failure) page replaces the progress page.

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

    if (rows.length === 0) {
        // The tasks are not registered yet; look again shortly.
        schedule(reload, 3000);
        return Promise.resolve();
    }

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
        const pending = rows.filter(
            (row) => !describeTaskStatus(statuses[row.dataset.taskId]).finished,
        );
        await Promise.all(pending.map(async (row) => {
            const taskId = row.dataset.taskId;
            const url = root.dataset.statusUrl.replace("__task__", encodeURIComponent(taskId));
            try {
                const result = await fetchJson(url);
                statuses[taskId] = result.task_status;
                renderTask(row, result.task_status);
            } catch {
                // A failed status request is retried on the next poll.
            }
        }));
        const progress = summarizeProgress(statuses, rows.length);
        renderProgress(progress);
        schedule(progress.complete ? reload : poll, pollInterval);
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
