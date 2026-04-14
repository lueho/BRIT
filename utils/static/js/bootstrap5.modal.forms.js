"use strict";

function resolveModalSettings(options) {
    return {
        modalID: '#modal',
        modalContent: '.modal-content',
        modalForm: '.modal-content form',
        formURL: null,
        isDeleteForm: false,
        errorClass: 'is-invalid',
        asyncUpdate: false,
        asyncSettings: {
            closeOnSubmit: false,
            successMessage: null,
            dataUrl: null,
            dataElementId: null,
            dataKey: null,
            addModalFormFunction: null,
        },
        ...options,
        asyncSettings: {
            closeOnSubmit: false,
            successMessage: null,
            dataUrl: null,
            dataElementId: null,
            dataKey: null,
            addModalFormFunction: null,
            ...(options && options.asyncSettings ? options.asyncSettings : {}),
        },
    };
}

function getModalInstance(modal) {
    let modalInstance = bootstrap.Modal.getInstance(modal);
    if (modalInstance === null) {
        modalInstance = new bootstrap.Modal(modal, { keyboard: false });
    }
    return modalInstance;
}

function clearElement(element) {
    while (element.lastChild) {
        element.removeChild(element.lastChild);
    }
}

function normalizeErrorClass(errorClass) {
    if (!errorClass) {
        return '';
    }
    return errorClass.startsWith('.') ? errorClass.slice(1) : errorClass;
}

function validateAsyncSettings(settings) {
    const missingSettings = [];

    if (!settings.successMessage) {
        missingSettings.push('successMessage');
    }
    if (!settings.dataUrl) {
        missingSettings.push('dataUrl');
    }
    if (!settings.dataElementId) {
        missingSettings.push('dataElementId');
    }
    if (!settings.dataKey) {
        missingSettings.push('dataKey');
    }
    if (!settings.addModalFormFunction) {
        missingSettings.push('addModalFormFunction');
    }

    return missingSettings.length === 0;
}

async function loadModalContent(settings) {
    const modal = document.querySelector(settings.modalID);
    const content = modal.querySelector(settings.modalContent);
    const response = await fetch(settings.formURL);
    const data = await response.text();
    content.innerHTML = data;
    const form = modal.querySelector(settings.modalForm);
    if (form) {
        form.setAttribute('action', settings.formURL);
    }
    return { modal, form };
}

async function isFormValid(settings, callback) {
    const modal = document.querySelector(settings.modalID);
    let form = modal.querySelector(settings.modalForm);
    const submitButton = modal.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
    }

    const response = await fetch(form.getAttribute('action'), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        method: form.getAttribute('method'),
        body: new FormData(form),
    });
    const data = await response.text();

    if (data.includes(normalizeErrorClass(settings.errorClass))) {
        modal.querySelector(settings.modalContent).innerHTML = data;
        form = modal.querySelector(settings.modalForm);
        if (!form) {
            return;
        }
        form.setAttribute('action', settings.formURL);
        addEventHandlers(modal, form, settings);
        return;
    }

    callback(settings);
}

async function submitForm(settings) {
    const modal = document.querySelector(settings.modalID);
    let form = modal.querySelector(settings.modalForm);

    if (!settings.asyncUpdate) {
        form.submit();
        return;
    }

    if (!validateAsyncSettings(settings.asyncSettings)) {
        return;
    }

    const formData = new FormData(form);
    formData.append('asyncUpdate', 'True');

    await fetch(form.getAttribute('action'), {
        method: form.getAttribute('method'),
        body: formData,
    });

    const body = document.body;
    if (body && settings.asyncSettings.successMessage) {
        const doc = new DOMParser().parseFromString(settings.asyncSettings.successMessage, 'text/html');
        const successNode = doc.body.firstElementChild;
        if (successNode) {
            body.insertBefore(successNode, body.firstChild);
        }
    }

    if (settings.asyncSettings.dataUrl) {
        const response = await fetch(settings.asyncSettings.dataUrl);
        const data = await response.json();
        const dataElement = document.querySelector(settings.asyncSettings.dataElementId);
        if (dataElement) {
            dataElement.innerHTML = data[settings.asyncSettings.dataKey];
        }
        if (settings.asyncSettings.addModalFormFunction) {
            settings.asyncSettings.addModalFormFunction();
        }
    }

    if (settings.asyncSettings.closeOnSubmit) {
        getModalInstance(modal).hide();
        return;
    }

    const loaded = await loadModalContent(settings);
    form = loaded.form;
    if (form) {
        addEventHandlers(loaded.modal, form, settings);
    }
}

function addEventHandlers(modal, form, settings) {
    if (form.dataset.modalFormBound === 'true') {
        return;
    }
    form.dataset.modalFormBound = 'true';

    form.addEventListener('submit', function (event) {
        if (settings.isDeleteForm === false) {
            event.preventDefault();
            isFormValid(settings, submitForm);
            return false;
        }
        return true;
    });

    if (modal.dataset.modalClearBound !== 'true') {
        modal.dataset.modalClearBound = 'true';
        modal.addEventListener('hidden.bs.modal', function () {
            const content = modal.querySelector(settings.modalContent);
            clearElement(content);
        });
    }
}

async function modalFormCallback(settings) {
    const loaded = await loadModalContent(settings);
    const modalInstance = getModalInstance(loaded.modal);
    modalInstance.show();
    if (loaded.form) {
        addEventHandlers(loaded.modal, loaded.form, settings);
    }
}

function modalForm(elem, options) {
    const settings = resolveModalSettings(options || {});
    elem.addEventListener('click', function () {
        modalFormCallback(settings);
    });
    return elem;
}

window.modalForm = modalForm;
