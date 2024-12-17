"use strict";

document.addEventListener("DOMContentLoaded", function() {
    const checkUrlBtn = document.querySelector('.check-url-btn');

    if (checkUrlBtn) {
        checkUrlBtn.addEventListener('click', function() {
            const sourceCheckUrl = checkUrlBtn.getAttribute('data-source-check-url');
            const elCheckUrlText = checkUrlBtn.querySelector('span');

            blockLink(checkUrlBtn, elCheckUrlText);
            startTask(sourceCheckUrl, elCheckUrlText);
        });
    }

    function blockLink(button, textEl) {
        textEl.innerText = "Checking...";
        button.classList.add("disabled");
    }

    async function startTask(url, textEl) {
        try {
            const response = await fetch(url);
            const data = await response.json();
            const progressUrlTemplate = checkUrlBtn.getAttribute('data-progress-url-template');
            const progressUrl = progressUrlTemplate.replace('task_id', data.task_id);
            monitorTaskProgress(progressUrl, textEl);
        } catch (error) {
            console.error("Error starting task:", error);
            textEl.innerText = "Error starting task";
        }
    }

    async function monitorTaskProgress(url, textEl, count = 0) {
        try {
            const response = await fetch(url);
            const data = await response.json();

            if (data.state === "PENDING") {
                textEl.innerText = "Checking" + ".".repeat(count % 4);
                setTimeout(() => monitorTaskProgress(url, textEl, count + 1), 500);
            } else if (data.state === "SUCCESS") {
                window.location.reload();
            } else {
                textEl.innerText = "Check failed";
            }
        } catch (error) {
            console.error("Error monitoring task:", error);
            textEl.innerText = "Monitoring failed";
        }
    }
});
