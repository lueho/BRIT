/**
 * Universal Formset JS - Handles dynamic formsets with or without TomSelect
 * 
 * This module provides functionality to add and remove formset rows while properly
 * initializing form components (including TomSelect if present) in dynamically added rows.
 */

"use strict";

class DynamicFormset {
    /**
     * Initialize a new dynamic formset handler
     * 
     * @param {Object} config Configuration options
     * @param {string} config.formPrefix The Django formset prefix
     * @param {string} [config.formId=null] Optional form ID prefix
     * @param {string} [config.formsetType="standard"] Formset type (standard or tomselect)
     * @param {string} [config.containerSelector=null] Optional custom container selector
     * @param {string} [config.emptyFormSelector=null] Optional custom empty form selector
     * @param {string} [config.addButtonSelector=null] Optional custom add button selector
     */
    constructor(config) {
        this.prefix = config.formPrefix;
        this.formId = config.formId || null;
        this.formsetType = config.formsetType || "standard";

        const idPre = this.formId ? `${this.formId}_` : "";
        this.selContainer = config.containerSelector || `#${idPre}formset-container`;
        this.selEmpty = config.emptyFormSelector || `#${idPre}empty-form-row`;
        this.selAddBtn = config.addButtonSelector || `#${idPre}add-form`;

        this.container = document.querySelector(this.selContainer);
        this.empty = document.querySelector(this.selEmpty);
        this.btnAdd = document.querySelector(this.selAddBtn);
        this.total = document.querySelector(`#id_${this.prefix}-TOTAL_FORMS`);

        if (this.container && this.empty && this.btnAdd && this.total) {
            this.init();
        } else {
            console.error("Formset: required elements missing for prefix", this.prefix);
        }
    }

    /**
     * Initialize event handlers
     */
    init() {
        this.btnAdd.addEventListener("click", (e) => this.addRow(e));

        // Add event delegation for remove buttons
        document.addEventListener("click", (e) => {
            if (e.target.closest(`${this.selContainer} .remove-form`)) {
                this.onRemove(e);
            }
        });

        console.debug(`Formset initialized: ${this.prefix} (type: ${this.formsetType})`);
    }

    /**
     * Add a new form row
     */
    addRow(e) {
        e.preventDefault();

        // Get the current total forms count
        const totalForms = parseInt(this.total.value);

        // Clone the empty form template
        const newRow = this.empty.cloneNode(true);
        newRow.classList.remove("d-none");
        newRow.id = "";

        // Replace all __prefix__ with the actual form count
        this.replaceAll(newRow, "__prefix__", totalForms);

        // Add the new row to the container
        this.container.appendChild(newRow);

        // Update the total forms count
        this.total.value = totalForms + 1;

        // Initialize any special widgets in the new row
        this.initWidgets(newRow);

        // Trigger a custom event that can be listened to by other code
        const event = new CustomEvent("formset:row-added", {
            detail: { row: newRow, formsetPrefix: this.prefix }
        });
        document.dispatchEvent(event);

        return newRow;
    }

    /**
     * Replace __prefix__ tokens everywhere (attributes + inline scripts)
     */
    replaceAll(node, search, repl) {
        const rx = typeof search === "string" ? new RegExp(search, "g") : search;

        // Replace in attributes
        Array.from(node.attributes || []).forEach((attr) => {
            const newVal = attr.value.replace(rx, repl);
            if (newVal !== attr.value) node.setAttribute(attr.name, newVal);
        });

        // Replace in inline scripts
        if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "SCRIPT") {
            if (rx.test(node.textContent)) {
                node.textContent = node.textContent.replace(rx, repl);
            }
        }

        // Recursively process child nodes
        Array.from(node.childNodes).forEach((child) => this.replaceAll(child, rx, repl));
    }

    /**
     * Initialize widgets in a new form row
     */
    initWidgets(row) {
        // Initialize TomSelect widgets if this is a tomselect formset
        if (this.formsetType === "tomselect") {
            this.initTomSelectWidgets(row);
        }

        // Additional widget initialization can be added here
    }

    /**
     * Initialize TomSelect widgets in a new row (only for tomselect formsets)
     */
    initTomSelectWidgets(row) {
        // First clean up any existing TomSelect wrappers
        row.querySelectorAll(".ts-wrapper").forEach((w) => w.remove());

        // Execute any scripts in the row to ensure configuration is set up
        this.executeScripts(row);

        // Use the djangoTomSelect.reinitialize method if available (preferred)
        if (window.djangoTomSelect?.reinitialize) {
            try {
                window.djangoTomSelect.reinitialize(row);
                // Fallback: ensure each select gets initialized even if no config found
                row.querySelectorAll('select[data-tomselect]').forEach((sel) => {
                    if (!sel.tomselect) {
                        if (window.djangoTomSelect?.initialize) {
                            window.djangoTomSelect.initialize(sel, {});
                        } else if (typeof TomSelect !== 'undefined') {
                            new TomSelect(sel);
                        }
                    }
                });
            } catch (err) {
                console.error("TomSelect reinitialize failed:", err);
            }
        }
        // Fallback to individual initialization
        else if (window.djangoTomSelect?.initialize) {
            row.querySelectorAll("select[data-tomselect='true']").forEach((select) => {
                try {
                    select.classList.remove("tomselected", "ts-hidden-accessible");
                    if (select.tomselect) select.tomselect.destroy();
                    window.djangoTomSelect.initialize(select);
                } catch (error) {
                    console.error("Failed to initialize django-tomselect:", error);
                }
            });
        }
        // Last resort for custom TomSelect implementations
        else if (typeof TomSelect !== "undefined") {
            row.querySelectorAll("select[data-tomselect]").forEach((select) => {
                try {
                    if (select.tomselect) select.tomselect.destroy();

                    // Initialize with config if available
                    if (select.dataset.tomselect && select.dataset.tomselect !== 'true') {
                        const config = JSON.parse(select.dataset.tomselect);
                        new TomSelect(select, config);
                    } else {
                        new TomSelect(select);
                    }
                } catch (error) {
                    console.error("Failed to initialize TomSelect:", error);
                }
            });
        } else {
            console.warn("TomSelect not loaded but trying to initialize TomSelect widgets");
        }
    }

    /**
     * Execute scripts within a newly added row
     * This is necessary for widgets that rely on inline scripts for initialization
     */
    executeScripts(container) {
        // Find and execute all script tags
        container.querySelectorAll('script').forEach(oldScript => {
            const newScript = document.createElement('script');

            // Copy all attributes
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });

            // Copy the script content
            let scriptContent = oldScript.textContent;

            // Special handling for TomSelect initialization scripts that use DOMContentLoaded
            // Since DOMContentLoaded has already fired, we need to execute the initialization immediately
            if (scriptContent.includes('window.djangoTomSelect.initialize') &&
                scriptContent.includes('DOMContentLoaded')) {

                console.debug('Modifying TomSelect script for dynamic formset row');

                // Replace DOMContentLoaded listener with immediate execution
                // Pattern: document.addEventListener('DOMContentLoaded', () => { ... });
                // Replace with: (() => { ... })();
                scriptContent = scriptContent.replace(
                    /document\.addEventListener\s*\(\s*['"`]DOMContentLoaded['"`]\s*,\s*\(\s*\)\s*=>\s*\{([\s\S]*?)\}\s*\)\s*;/g,
                    '(() => {$1})();'
                );

                // Also handle function form: document.addEventListener('DOMContentLoaded', function() { ... });
                scriptContent = scriptContent.replace(
                    /document\.addEventListener\s*\(\s*['"`]DOMContentLoaded['"`]\s*,\s*function\s*\(\s*\)\s*\{([\s\S]*?)\}\s*\)\s*;/g,
                    '(function() {$1})();'
                );
            }

            newScript.textContent = scriptContent;

            // Replace the old script with the new one to execute it
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    /**
     * Handle remove button click
     */
    onRemove(e) {
        e.preventDefault();

        const btn = e.target.closest(".remove-form");
        const row = btn.closest(".formset-form-row");
        const deletedInput = row.querySelector(`input[id$="-DELETE"]`);

        if (deletedInput) {
            // If there's a DELETE field, mark for deletion rather than removing
            deletedInput.value = "on";
            row.style.display = "none";
        } else {
            // Otherwise remove the row and renumber
            row.remove();
            this.renumber();
        }

        // Trigger custom event
        const event = new CustomEvent("formset:row-removed", {
            detail: { row: row, formsetPrefix: this.prefix }
        });
        document.dispatchEvent(event);
    }

    /**
     * Renumber all form instances after deletion
     */
    renumber() {
        const totalForms = document.querySelector(`#id_${this.prefix}-TOTAL_FORMS`);
        const rows = this.container.querySelectorAll(".formset-form-row:not(.d-none)");

        totalForms.value = rows.length;

        rows.forEach((row, index) => {
            // Update all ids and names in this row
            row.querySelectorAll("input, select, textarea, label").forEach((field) => {
                if (field.name) {
                    field.name = field.name.replace(/\d+/, index);
                }
                if (field.id) {
                    field.id = field.id.replace(/\d+/, index);
                }
                if (field.htmlFor) {
                    field.htmlFor = field.htmlFor.replace(/\d+/, index);
                }
            });
        });
    }
}

/**
 * Initialize dynamic formset handling for an element
 * @param {Object} config - Configuration object
 */
function initDynamicFormset(config) {
    return new DynamicFormset(config);
}

// Immediately log that the script was loaded
console.log("formset.js loaded");

// Global initialization function that runs when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
    console.log("DOMContentLoaded event fired in formset.js");

    // Find all formset elements
    const formsetElements = document.querySelectorAll("[data-formset]");
    console.log(`Found ${formsetElements.length} formset elements:`, formsetElements);

    // Initialize any formsets found on the page
    formsetElements.forEach(element => {
        const formsetType = element.dataset.formsetType || "standard";
        const formPrefix = element.dataset.formset;
        const formId = element.dataset.formsetId || null;

        console.log(`Initializing formset: ${formPrefix} (type: ${formsetType}, id: ${formId || 'none'})`);

        initDynamicFormset({
            formPrefix: formPrefix,
            formId: formId,
            formsetType: formsetType
        });
    });
});

// Also try with window.onload as a fallback
window.onload = function () {
    console.log("window.onload event fired in formset.js");
};
