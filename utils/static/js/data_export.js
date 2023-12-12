"use strict";

async function monitor_task_progress(url, format, count = 0) {
    const response = await fetch(url);
    const data = await response.json();
    const elExportWrapper = document.getElementById('export_' + format);
    const elExportLink = elExportWrapper.children[0];
    const elExportLinkText = elExportLink.children[1];
    if (data["state"] === "PENDING") {
        elExportLinkText.innerText = "Exporting to " + format + ".".repeat(count++ % 4);
        elExportLink.classList.add("processing-link");
        setTimeout(monitor_task_progress, 500, url, format, count);
    } else if (data["state"] === "SUCCESS") {
        elExportLinkText.innerText = "Download " + format;
        elExportLink.removeAttribute("onclick");
        elExportLink.href = data["details"];
        elExportLink.classList.remove("processing-link");
    } else if (data["state"] === "FAILURE") {
        elExportLinkText.innerText = "Export to " + format;
        elExportLink.classList.remove("processing-link");
    }
}

async function start_task(export_url, format) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.append('format', format);
    const url = export_url + "?" + urlParams.toString();
    const response = await fetch(url);
    const data = await response.json();
    return data["task_id"];
}

async function export_to_file(format) {
    const export_url = document.getElementById('export_xlsx').dataset.exportUrl;
    const taskId = await start_task(export_url, format);
    const url = document.getElementById('export_xlsx').dataset.exportProgressUrl.replace('0', taskId);
    monitor_task_progress(url, format);
}

function lockCustomElements() {
    // This function overrides a hook from maps.js which is called in filtered_map.html
    function addProcessingClass(elementId) {
        const wrapper = document.getElementById(elementId);
        if (wrapper && wrapper.children.length > 0) {
            wrapper.children[0].classList.add("processing-link");
        } else {
            console.warn(`Element with ID '${elementId}' or its first child was not found.`);
        }
    }

    // Apply the class to the first child of both elements
    addProcessingClass('export_csv');
    addProcessingClass('export_xlsx');
}

function unlockCustomElements() {
    // This function overrides a hook from maps.js which is called in filtered_map.html
    function removeProcessingClass(elementId, text) {
        const wrapper = document.getElementById(elementId);
        if (wrapper && wrapper.children.length > 0) {
            const link = wrapper.children[0];
            if (link.children.length > 1) {
                link.children[1].innerText = text;
                link.classList.remove("processing-link");
            } else {
                console.warn(`Second child of link in '${elementId}' was not found.`);
            }
        } else {
            console.warn(`Element with ID '${elementId}' or its first child was not found.`);
        }
    }

    // Reset the text and class for both elements
    removeProcessingClass('export_csv', 'Export to csv');
    removeProcessingClass('export_xlsx', 'Export to xlsx');
}


// add eventHandler for the export links
document.getElementById('export_xlsx').addEventListener('click', () => export_to_file('xlsx'), false);
document.getElementById('export_csv').addEventListener('click', () => export_to_file('csv'), false);