"use strict";

function addForm() {
    const totalFormsInput = document.querySelector('[id$="-TOTAL_FORMS"]');
    const emptyForm = document.getElementById('empty-form-row').cloneNode(true);
    emptyForm.setAttribute('class', 'formset-form-row');
    const regex = new RegExp('__prefix__', 'g');
    const currentFormCount = document.getElementsByClassName('formset-form-row').length;
    emptyForm.innerHTML = emptyForm.innerHTML.replace(regex, currentFormCount);
    totalFormsInput.setAttribute('value', `${currentFormCount + 1}`);
    const formContainer = document.getElementById('formset-container');
    formContainer.append(emptyForm);
}

function loadAddFormButton() {
    const addFormButton = document.getElementById('add-form');
    if (addFormButton) {
        addFormButton.addEventListener('click', (e) => {
            if (e) {
                e.preventDefault();
            }
            addForm();
        });
    }
}

loadAddFormButton();