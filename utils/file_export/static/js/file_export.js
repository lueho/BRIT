"use strict";

const POLLING_INTERVAL_MS = 500; // Polling interval in milliseconds

/**
 * Initiates the export process when a user clicks an export element.
 *
 * @param {HTMLElement} element - The clickable export element.
 * @param {string} format - The export file format (e.g., 'xlsx', 'csv').
 */
function export_to_file(element, format) {
    if (element.dataset.exportStatus === "READY") {
        element.dataset.exportStatus = "PENDING";

        prepare_export(format)
            .then(exportUrl => start_export(exportUrl, format))
            .then(monitorUrl => monitor_export_progress(monitorUrl, format))
            .catch(error => {
                console.error("Export process failed:", error);
                resetExportLink(format);
            });
    }
}

/**
 * Prepares the export URL by appending the format and current query parameters.
 *
 * @param {string} format - The export format.
 * @returns {Promise<string>} The complete export URL.
 */
async function prepare_export(format) {
    const elements = getLinkElements(format);
    if (!elements) {
        throw new Error(`Export elements for format "${format}" not found.`);
    }
    elements.link.classList.add("disabled");

    const element = document.getElementById('export_' + format);
    const baseExportUrl = element.dataset.exportUrl;
    // Get all current query params from the URL, preserving all filters
    const currentParams = window.location.search;
    let exportUrl = baseExportUrl;
    if (currentParams) {
        exportUrl += (baseExportUrl.includes('?') ? '&' : '?') + currentParams.slice(1);
    }
    // Always ensure format param is present/overridden
    const urlObj = new URL(exportUrl, window.location.origin);
    urlObj.searchParams.set('format', format);
    // Add list_type from data attribute if present
    const listType = element.dataset.listType;
    if (listType) {
        urlObj.searchParams.set('list_type', listType);
    }
    return urlObj.pathname + '?' + urlObj.searchParams.toString();
}

/**
 * Starts the export task on the server.
 *
 * @param {string} exportUrl - The export URL prepared by prepare_export.
 * @param {string} format - The export format.
 * @returns {Promise<string>} The URL to be used for monitoring export progress.
 */
async function start_export(exportUrl, format) {
    try {
        const response = await fetch(exportUrl);
        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.status}`);
        }
        const data = await response.json();
        if (!data.task_id) {
            throw new Error("Task ID missing in export response.");
        }
        const element = document.getElementById('export_' + format);
        // Dynamically replace a placeholder ('0') in the progress URL with the actual task_id
        return element.dataset.exportProgressUrl.replace('0', data.task_id);
    } catch (error) {
        console.error("Error starting export:", error);
        throw error;
    }
}

/**
 * Monitors the export progress by polling the server.
 *
 * @param {string} url - The monitoring URL.
 * @param {string} format - The export format.
 * @param {number} count - The current poll count (used for UI animation).
 */
async function monitor_export_progress(url, format, count = 0) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Monitoring response was not ok: ${response.status}`);
        }
        const data = await response.json();
        if (data.state === "PENDING") {
            updateProcessingLink(format, count + 1);
            setTimeout(() => monitor_export_progress(url, format, count + 1), POLLING_INTERVAL_MS);
        } else if (data.state === "SUCCESS") {
            cleanup_export(true, data, format);
        } else if (data.state === "FAILURE") {
            cleanup_export(false, data, format);
        } else {
            console.warn("Unexpected export state:", data.state);
        }
    } catch (error) {
        console.error("Error monitoring export progress:", error);
        resetExportLink(format);
    }
}

/**
 * Finalizes the export process.
 * On success, formats the download link; on failure, resets the export link.
 *
 * @param {boolean} exportSuccessful - Indicates if export succeeded.
 * @param {object} data - The response data from the export process.
 * @param {string} format - The export format.
 */
function cleanup_export(exportSuccessful, data, format) {
    if (exportSuccessful === true) {
        if (data.details) {
            formatDownloadLink(data.details, format);
        } else {
            console.error("Missing download details in export response.");
            resetExportLink(format);
        }
    } else {
        resetExportLink(format);
    }
}

/**
 * Attaches click event handlers to all export format items.
 * This function is intended to be called when new modal content is loaded.
 */
function initExportHandlers() {
    const formatItems = document.querySelectorAll('.export-format-item');
    if (formatItems) {
        formatItems.forEach(item => {
            item.addEventListener('click', function () {
                const format = this.dataset.format;
                export_to_file(this, format);
            });
        });
    }
}

/**
 * Retrieves the relevant export link elements based on the format.
 *
 * @param {string} format - The export format.
 * @returns {object|null} An object containing wrapper, linkText, and statusElement, or null if not found.
 */
function getLinkElements(format) {
    const wrapper = document.getElementById('export_' + format);
    if (!wrapper) {
        return null;
    }
    const linkText = wrapper.querySelector('.export-text');
    const statusElement = wrapper.querySelector('.export-status');

    return {
        wrapper: wrapper,
        link: wrapper, // Assumes the wrapper itself is clickable
        linkText: linkText,
        statusElement: statusElement
    };
}

/**
 * Updates the UI to indicate the export is in progress.
 *
 * @param {string} format - The export format.
 * @param {number} count - The current poll count (used to animate the loading dots).
 */
function updateProcessingLink(format, count) {
    const elements = getLinkElements(format);
    if (!elements) {
        return;
    }
    elements.linkText.innerText = `Exporting to ${format.toUpperCase()}${'.'.repeat(count % 4)}`;

    // Add a spinner if one is not already present
    if (elements.statusElement && !elements.statusElement.querySelector('.spinner-border')) {
        elements.statusElement.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"><span class="sr-only">Loading...</span></div>';
    }
}

/**
 * Updates the UI to display the download link after a successful export.
 *
 * @param {string} downloadUrl - The URL from which the exported file can be downloaded.
 * @param {string} format - The export format.
 */
function formatDownloadLink(downloadUrl, format) {
    const elements = getLinkElements(format);
    if (!elements) {
        return;
    }
    elements.wrapper.dataset.exportStatus = "SUCCESS";
    elements.linkText.innerText = `Download ${format.toUpperCase()}`;

    if (elements.statusElement) {
        elements.statusElement.innerHTML = `<a href="${downloadUrl}" class="btn btn-sm btn-outline-primary"><i class="fas fa-download"></i></a>`;
    }

    elements.link.classList.remove("disabled");
    elements.wrapper.onclick = function (e) {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = downloadUrl;
    };
}

/**
 * Resets the export link UI to its initial "ready" state.
 *
 * @param {string} format - The export format.
 */
function resetExportLink(format) {
    const elements = getLinkElements(format);
    if (!elements) {
        return;
    }
    elements.wrapper.dataset.exportStatus = "READY";
    elements.linkText.innerText = `Export to ${format}`;

    if (elements.statusElement) {
        elements.statusElement.innerHTML = '';
    }

    elements.link.classList.remove("disabled");

    elements.wrapper.onclick = function (e) {
        e.preventDefault();
        e.stopPropagation();
        export_to_file(elements.wrapper, format);
    };
}

/**
 * Locks all export format elements to disable user interactions.
 */
function lockCustomElements() {
    try {
        const formatItems = document.querySelectorAll('.export-format-item');
        formatItems.forEach(item => {
            item.classList.add("disabled");
        });
    } catch (error) {
        console.warn(`Failed to lock export links: ${error.message}`);
    }
}

/**
 * Unlocks export format elements that are ready for interaction.
 */
function unlockCustomElements() {
    try {
        const formatItems = document.querySelectorAll('.export-format-item');
        formatItems.forEach(item => {
            if (item.dataset.exportStatus === "READY") {
                item.classList.remove("disabled");
            }
        });
    } catch (error) {
        console.warn(`Failed to unlock export links: ${error.message}`);
    }
}

// Attach event handler to initialize export handlers when the modal is shown.
// Uses vanilla JavaScript with Bootstrap 5 modal events.
document.addEventListener('DOMContentLoaded', function () {
    // Listen for Bootstrap modal shown event on the document
    document.addEventListener('shown.bs.modal', function (event) {
        // Check if the event target is the modal we're interested in
        if (event.target && event.target.id === 'modal') {
            initExportHandlers();
        }
    });
});
