"use strict";
/**
 * Show required-field feedback on TomSelect fields.
 *
 * TomSelect hides the original field (clipped to one pixel) and renders its
 * own control. Native constraint validation still targets the hidden field,
 * so a failed submit focuses something invisible and no error is readable.
 * Mark the visible control instead, print the browser's message and move
 * focus to the control when it is the first invalid field of the form.
 *
 * The message sits above the control: focusing a TomSelect opens its
 * dropdown, which would cover a message placed below.
 */

const TOMSELECT_FEEDBACK_CLASS = "tomselect-required-feedback";
let tomSelectInvalidFocusPending = false;

function isTomSelectField(field) {
    return Boolean(field && field.tomselect && field.classList.contains("tomselected"));
}

function tomSelectFeedback(field) {
    const sibling = field.previousElementSibling;
    return sibling && sibling.classList.contains(TOMSELECT_FEEDBACK_CLASS) ? sibling : null;
}

function showTomSelectInvalid(field) {
    const { wrapper, control_input: controlInput } = field.tomselect;
    field.dataset.requiredFeedback = "true";
    wrapper.classList.add("is-invalid");
    if (controlInput) controlInput.setAttribute("aria-invalid", "true");
    let feedback = tomSelectFeedback(field);
    if (!feedback) {
        feedback = document.createElement("div");
        feedback.classList.add("invalid-feedback", "d-block", "mt-0", "mb-1", TOMSELECT_FEEDBACK_CLASS);
        field.insertAdjacentElement("beforebegin", feedback);
    }
    feedback.textContent = field.validationMessage;
}

function clearTomSelectInvalid(field) {
    const { wrapper, control_input: controlInput } = field.tomselect;
    delete field.dataset.requiredFeedback;
    wrapper.classList.remove("is-invalid");
    if (controlInput) controlInput.removeAttribute("aria-invalid");
    const feedback = tomSelectFeedback(field);
    if (feedback) feedback.remove();
}

function focusFirstInvalidTomSelect(field) {
    const first = field.form
        ? Array.from(field.form.elements).find((el) => el.willValidate && !el.validity.valid)
        : field;
    if (!isTomSelectField(first)) return;
    first.tomselect.wrapper.scrollIntoView({ block: "center" });
    first.tomselect.focus();
}

document.addEventListener("invalid", (event) => {
    const field = event.target;
    if (!isTomSelectField(field)) return;
    // The native bubble would be anchored to the hidden field.
    event.preventDefault();
    showTomSelectInvalid(field);
    if (tomSelectInvalidFocusPending) return;
    tomSelectInvalidFocusPending = true;
    // Wait until the browser has reported every invalid field of this submit.
    setTimeout(() => {
        tomSelectInvalidFocusPending = false;
        focusFirstInvalidTomSelect(field);
    }, 0);
}, true);

document.addEventListener("change", (event) => {
    const field = event.target;
    if (!isTomSelectField(field) || field.dataset.requiredFeedback !== "true") return;
    if (field.validity.valid) clearTomSelectInvalid(field);
});
