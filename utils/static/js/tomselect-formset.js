/*
 * TomSelect Formset JS – v4 (bug‑fix release)
 * -------------------------------------------
 * Fixes the crash “First argument to String.prototype.includes must not be a
 * regular expression” by **eliminating the accidental duplicate replaceAll()
 * definition** that still used `.includes()`. Only the safe implementation
 * remains.
 */

"use strict";

// -----------------------------------------------------------------------------
// 1) Polyfill for vanished helper (unchanged)
// -----------------------------------------------------------------------------
if (typeof window.resetVarName === "undefined") {
    window.resetVarName = function (val, index) {
        if (typeof val === "string") return val.replace(/__prefix__/g, index);
        if (typeof val === "function") {
            const src = val.toString().replace(/__prefix__/g, index);
            // eslint-disable-next-line no-new-func
            return new Function(`return (${src})`)();
        }
        return val;
    };
    console.debug("[TS‑Formset] fallback resetVarName() installed");
}

class TomSelectFormset {
    constructor(cfg) {
        this.prefix = cfg.formPrefix;
        this.formId = cfg.formId || null;

        const idPre = this.formId ? `${this.formId}_` : "";
        this.selContainer = cfg.containerSelector || `#${idPre}formset-container`;
        this.selEmpty = cfg.emptyFormSelector || `#${idPre}empty-form-row`;
        this.selAddBtn = cfg.addButtonSelector || `#${idPre}add-form`;

        this.container = document.querySelector(this.selContainer);
        this.empty = document.querySelector(this.selEmpty);
        this.btnAdd = document.querySelector(this.selAddBtn);
        this.total = document.querySelector(`#id_${this.prefix}-TOTAL_FORMS`);

        if (this.container && this.empty && this.btnAdd && this.total) {
            this.init();
        } else {
            console.error("TS‑Formset: required elements missing for prefix", this.prefix);
        }
    }

    init() {
        const cleanBtn = this.btnAdd.cloneNode(true);
        this.btnAdd.replaceWith(cleanBtn);
        this.btnAdd = cleanBtn;

        this.btnAdd.addEventListener("click", (e) => this.addRow(e));
        this.container.addEventListener("click", (e) => this.onRemove(e));

        console.info(`TS‑Formset ready (‘${this.prefix}’)`);
    }

    // ---------------------------------------------------------------------------
    // Add a new form row
    // ---------------------------------------------------------------------------
    addRow(e) {
        e?.preventDefault();
        const idx = Number(this.total.value);

        const row = this.empty.cloneNode(true);
        row.classList.remove("d-none");
        row.removeAttribute("id");

        this.replaceAll(row, "__prefix__", idx);

        this.container.appendChild(row);
        this.total.value = idx + 1;

        this.initWidgets(row);
        console.debug(`[TS‑Formset] row ${idx} added for '${this.prefix}'`);
    }

    // ---------------------------------------------------------------------------
    // Replace __prefix__ tokens everywhere (attributes + inline scripts)
    // ---------------------------------------------------------------------------
    replaceAll(node, search, repl) {
        const rx = typeof search === "string" ? new RegExp(search, "g") : search;

        // 1. attributes
        Array.from(node.attributes || []).forEach((attr) => {
            const newVal = attr.value.replace(rx, repl);
            if (newVal !== attr.value) node.setAttribute(attr.name, newVal);
        });

        // 2. inline <script> contents
        if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "SCRIPT") {
            if (rx.test(node.textContent)) {
                node.textContent = node.textContent.replace(rx, repl);
            }
        }

        // 3. recurse
        Array.from(node.childNodes).forEach((child) => this.replaceAll(child, rx, repl));
    }

    // ---------------------------------------------------------------------------
    // Initialise TomSelect widgets via official helper
    // ---------------------------------------------------------------------------
    initWidgets(row) {
        row.querySelectorAll(".ts-wrapper").forEach((w) => w.remove());

        if (window.djangoTomSelect?.reinitialize) {
            try {
                window.djangoTomSelect.reinitialize(row);
            } catch (err) {
                console.error("[TS‑Formset] reinitialize failed:", err);
            }
        } else {
            row.querySelectorAll("select[data-tomselect='true']").forEach((sel) => {
                sel.classList.remove("tomselected", "ts-hidden-accessible");
                if (sel.tomselect) sel.tomselect.destroy();
                window.djangoTomSelect?.initialize ?
                    window.djangoTomSelect.initialize(sel) : new TomSelect(sel);
            });
        }

        document.dispatchEvent(
            new CustomEvent("formset:row:added", { bubbles: true, detail: { row } })
        );
    }

    // ---------------------------------------------------------------------------
    // Remove / soft‑delete
    // ---------------------------------------------------------------------------
    onRemove(e) {
        const btn = e.target.closest(".remove-form");
        if (!btn) return;
        const row = btn.closest(".formset-form-row");
        if (!row) return;

        const del = row.querySelector("input[name$='-DELETE']");
        if (del) {
            del.checked = true;
            row.style.opacity = 0.5;
            row.style.pointerEvents = "none";
        } else {
            row.remove();
            this.renumber();
        }
    }

    renumber() {
        const rows = this.container.querySelectorAll(".formset-form-row:not(.d-none)");
        this.total.value = rows.length;

        rows.forEach((row, idx) => {
            row.querySelectorAll("[name]").forEach((el) => {
                if (el.name)
                    el.name = el.name.replace(new RegExp(`${this.prefix}-\\d+`), `${this.prefix}-${idx}`);
                if (el.id)
                    el.id = el.id.replace(new RegExp(`id_${this.prefix}-\\d+`), `id_${this.prefix}-${idx}`);
            });
        });
    }
}

function initTomSelectFormset(cfg) {
    return new TomSelectFormset(cfg);
}

if (!window._tsFormsets) window._tsFormsets = new Set();

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-tomselect-formset]").forEach((el) => {
        const p = el.dataset.tomselectFormset;
        const id = el.dataset.tomselectFormsetId || "";
        const k = `${p}-${id}`;
        if (window._tsFormsets.has(k)) return;
        window._tsFormsets.add(k);
        initTomSelectFormset({ formPrefix: p, formId: id || null });
        console.info(`[TS‑Formset] auto‑init '${k}'`);
    });
});

window.initTomSelectFormset = initTomSelectFormset;
