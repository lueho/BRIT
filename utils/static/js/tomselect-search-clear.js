"use strict";
/**
 * Clear the TomSelect search textbox after an item is selected.
 *
 * The bundled TomSelect build clears typed text on selection only when the
 * `clearAfterSelect` option is set, which neither the emitted widget config
 * nor the workspace autocomplete settings use. Untouched text then lingers
 * behind selected chips and keeps filtering the dropdown, which surfaces as
 * "No results found". Hook `item_add` on every multi-select TomSelect
 * instance instead so the textbox is cleared on each pick.
 */

function wireTomSelectSearchClear(select) {
    if (!select || !select.multiple || !select.tomselect) return;
    if (select.dataset.searchClearWired === "true") return;
    select.dataset.searchClearWired = "true";
    select.tomselect.on("item_add", () => select.tomselect.setTextboxValue(""));
}

function scanTomSelectSearchClear(root) {
    if (!root) return;
    if (typeof root.matches === "function" && root.matches("select.tomselected")) {
        wireTomSelectSearchClear(root);
    }
    if (typeof root.querySelectorAll === "function") {
        root.querySelectorAll("select.tomselected").forEach(wireTomSelectSearchClear);
    }
}

function initTomSelectSearchClear() {
    scanTomSelectSearchClear(document.documentElement);
    new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.type === "childList") {
                mutation.addedNodes.forEach(scanTomSelectSearchClear);
            } else if (mutation.type === "attributes") {
                scanTomSelectSearchClear(mutation.target);
            }
        }
    }).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class"],
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTomSelectSearchClear);
} else {
    initTomSelectSearchClear();
}
