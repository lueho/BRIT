"use strict";

// load filter_utils.js before this if combined with filter forms

function export_to_file(element, format) {
    if (element.dataset.exportStatus === "READY") {
        element.setAttribute('data-export-status', "PENDING");

        prepare_export(format)
            .then(export_url => start_export(export_url, format))
            .then(monitoring_url => monitor_export_progress(monitoring_url, format));
    }
}

async function prepare_export(format) {
    const elements = getLinkElements(format);
    elements.link.classList.add("disabled");
    const base_export_url = document.getElementById('export_xlsx').dataset.exportUrl;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.append('format', format);
    return base_export_url + "?" + urlParams.toString();
}

async function start_export(export_url) {
    const response = await fetch(export_url);
    const data = await response.json();
    return document.getElementById('export_xlsx').dataset.exportProgressUrl.replace('0', data.task_id);
}

async function monitor_export_progress(url, format, count = 0) {
    const response = await fetch(url);
    const data = await response.json();
    if (data.state === "PENDING") {
        count++;
        updateProcessingLink(format, count);
        setTimeout(monitor_export_progress, 500, url, format, count);
    } else if (data.state === "SUCCESS") {
        cleanup_export(true, data, format);
    } else if (data.state === "FAILURE") {
        cleanup_export(false, data, format);
    }
}

function cleanup_export(export_successful, data, format) {
    if (export_successful === true) {
        formatDownloadLink(data.details, format);
    } else {
        resetExportLink(format);
    }
}

function addClickEventHandler(format) {
    const element = document.getElementById('export_' + format);
    if (element) {
        element.addEventListener('click', function() {
            export_to_file(this, format);
        }, false);
    }
}

function getLinkElements(format) {
    return {
        wrapper: document.getElementById('export_' + format),
        link: document.getElementById('export_' + format).children[0],
        linkText: document.getElementById('export_' + format).children[0].children[1]
    };
}

function updateProcessingLink(format, count) {
    const elements = getLinkElements(format);
    elements.linkText.innerText = "Exporting to " + format + ".".repeat(count % 4);
}

function formatDownloadLink(download_url, format) {
    const elements = getLinkElements(format);
    elements.wrapper.setAttribute("data-export-status", "SUCCESS");
    elements.linkText.innerText = "Download " + format;
    elements.link.href = download_url;
    elements.link.removeAttribute("onclick");
    elements.link.classList.remove("disabled");
}

function resetExportLink(format) {
    const elements = getLinkElements(format);
    elements.wrapper.setAttribute("data-export-status", "READY");
    // elements.link.setAttribute("href", "javascript:void(0)");
    elements.link.removeAttribute("href");
    elements.linkText.innerText = "Export to " + format;
    addClickEventHandler(format);
    elements.link.classList.remove("disabled");
}

function lockCustomElements() {
    // This function overrides a hook from filter_utils.js
    try {
        const elementsCSV = getLinkElements('csv');
        elementsCSV.link.classList.add("disabled");

        const elementsXLSX = getLinkElements('xlsx');
        elementsXLSX.link.classList.add("disabled");
    } catch (error) {
        console.warn(`Failed to lock export links: ${error.message}`);
    }

}

function unlockCustomElements() {
    // This function overrides a hook from filter_utils.js
    try {
        resetExportLink('csv');
        resetExportLink('xlsx');

        const elementsCSV = getLinkElements('csv');
        elementsCSV.link.classList.remove("disabled");

        const elementsXLSX = getLinkElements('xlsx');
        elementsXLSX.link.classList.remove("disabled");
    } catch (error) {
        console.warn(`Failed to unlock export links: ${error.message}`);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    addClickEventHandler('csv');
    addClickEventHandler('xlsx');
});