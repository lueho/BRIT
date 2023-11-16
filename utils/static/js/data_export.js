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
    const elExportCSVWrapper = document.getElementById('export_csv');
    const elExportCSVLink = elExportCSVWrapper.children[0];
    elExportCSVLink.classList.add("processing-link");
    const elExportXLSXWrapper = document.getElementById('export_xlsx');
    const elExportXLSXLink = elExportXLSXWrapper.children[0];
    elExportXLSXLink.classList.add("processing-link");
}

function unlockCustomElements() {
    // This function overrides a hook from maps.js which is called in filtered_map.html
    const elExportCSVWrapper = document.getElementById('export_csv');
    const elExportCSVLink = elExportCSVWrapper.children[0];
    const elExportCSVLinkText = elExportCSVLink.children[1];
    elExportCSVLinkText.innerText = "Export to csv";
    elExportCSVLink.classList.remove("processing-link");
    const elExportXLSXWrapper = document.getElementById('export_xlsx');
    const elExportXLSXLink = elExportXLSXWrapper.children[0];
    const elExportXLSXLinkText = elExportXLSXLink.children[1];
    elExportXLSXLinkText.innerText = "Export to xlsx";
    elExportXLSXLink.classList.remove("processing-link");
}

// add eventHandler for the export links
document.getElementById('export_xlsx').addEventListener('click', () => export_to_file('xlsx'), false);
document.getElementById('export_csv').addEventListener('click', () => export_to_file('csv'), false);