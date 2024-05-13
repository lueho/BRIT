"use strict";

const fetchTaskStatus = async (taskElement) => {
    const taskId = taskElement.dataset.taskId;
    const url = taskElement.dataset.statusUrl;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const json = await response.json();
        const status = json.task_status;
        const statusElement = document.getElementById(`${taskId}_status`);
        if (statusElement) {
            statusElement.innerHTML = status;
        }
        return status;
    } catch (error) {
        console.error(`Failed to fetch task status for task ID: ${taskId}`, error);
        const statusElement = document.getElementById(`${taskId}_status`);
        if (statusElement) {
            statusElement.innerHTML = 'ERROR';
        }
        return 'ERROR';
    }
};

const observeTasks = async () => {
    while (true) {
        try {
            const tasks = Array.from(document.querySelectorAll("#tasks tr"));
            const statuses = await Promise.all(tasks.map(fetchTaskStatus));
            if (statuses.includes('PENDING')) {
                await new Promise(resolve => setTimeout(resolve, 1000));
            } else if (statuses.every(status => status === 'SUCCESS')) {
                document.getElementById('completion-message').style.display = 'block';
                setTimeout(() => window.location.reload(), 1000);
                break;
            } else if (statuses.includes('FAILURE')) {
                document.getElementById('error-message').style.display = 'block';
                break;
            } else {
                break;
            }
        } catch (error) {
            console.error('Error fetching task statuses:', error);
            document.getElementById('error-message').style.display = 'block';
            break;
        }
    }
};


document.addEventListener('DOMContentLoaded', observeTasks);