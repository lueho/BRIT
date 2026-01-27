"use strict";

// Load 'lib/turf-inside/inside.min.js' script before this
// Load 'js/maps.js' script before this

const fieldConfig = {
    catchment: {
        include: true,
        format: (value) => value || ''
    },
    collector: {
        include: true,
        format: (value) => value || ''
    },
    collection_system: {
        include: true,
        format: (value) => value || ''
    },
    waste_category: {
        include: true,
        format: (value) => value || ''
    },
    allowed_materials: {
        include: false,
        format: (value) => {
            if (!value) return '';
            const str = Array.isArray(value) ? value.join(', ') : value;
            return formatList(str, ', ');
        }
    },
    forbidden_materials: {
        include: false,
        format: (value) => {
            if (!value) return '';
            const str = Array.isArray(value) ? value.join(', ') : value;
            return formatList(str, ', ');
        }
    },
    fee_system: {
        include: true,
        format: (value) => value || ''
    },
    population: {
        include: false,
        format: (value) => value ? value.toLocaleString() : ''
    },
    population_density: {
        include: false,
        format: (value) => value ? value.toFixed(2) : ''
    },
    comments: {
        include: false,
        format: (value) => formatList(value, '; ')
    },
    valid_from: {
        include: false,
        format: (value) => value ? new Date(value).toLocaleDateString() : ''
    },
    lastmodified_at: {
        include: false,
        format: (value) => value ? new Date(value).toLocaleDateString() : ''
    },
    sources: {
        include: false,
        format: (value) => {
            if (!value) return '';
            // Handle both array (from API) and string formats
            const urlString = Array.isArray(value) ? value.join(', ') : value;
            const urlList = formatUrls(urlString);
            return urlList ? `<ul class="list-disc pl-4">${urlList}</ul>` : '';
        }
    }
};

function enableBtn(el) {
    if (!el) return;
    el.classList.remove('disabled');
    el.removeAttribute('aria-disabled');
    el.removeAttribute('tabindex');
    if (el.title && el.title.indexOf('Select a collection') !== -1) {
        el.removeAttribute('title');
    }
}

function disableBtn(el, title) {
    if (!el) return;
    el.classList.add('disabled');
    el.setAttribute('aria-disabled', 'true');
    el.setAttribute('tabindex', '-1');
    if (title) el.setAttribute('title', title);
}

function getScope() {
    const params = new URLSearchParams(window.location.search);
    return (params.get('scope') || 'published').toLowerCase();
}

function getContextFlag(flag) {
    // Read flags rendered as data-* attributes in the template (no JS in template)
    try {
        const ctx = document.getElementById('map-context');
        if (!ctx) return null;
        const value = ctx.dataset[flag];
        if (value === undefined) return null;
        if (value === 'true') return true;
        if (value === 'false') return false;
    } catch (_) {
        return null;
    }
}

function getCurrentUserId() {
    try {
        const ctx = document.getElementById('map-context');
        if (!ctx) return null;
        const uid = ctx.dataset.userId;
        if (!uid) return null;
        const parsed = parseInt(uid, 10);
        return Number.isNaN(parsed) ? null : parsed;
    } catch (_) {
        return null;
    }
}

function hideSelectionHint() {
    const hint = document.getElementById('map-actions-hint');
    if (hint) hint.classList.add('d-none');
}

// --- Selection helpers used by featureClickHandler ---
let __wc_lastSelectedLayer = null;

function resetFeatureStyles(featureGroup) {
    try {
        if (!featureGroup) return;
        featureGroup.eachLayer(layer => {
            if (layer && typeof layer.setStyle === 'function' && typeof featuresLayerStyle === 'object') {
                layer.setStyle(featuresLayerStyle);
            }
        });
        __wc_lastSelectedLayer = null;
    } catch (_) { /* ignore styling errors */ }
}

function selectFeature(layer) {
    try {
        if (!layer) return;
        // Reset previously selected (if any)
        if (__wc_lastSelectedLayer && typeof __wc_lastSelectedLayer.setStyle === 'function' && typeof featuresLayerStyle === 'object') {
            __wc_lastSelectedLayer.setStyle(featuresLayerStyle);
        }
        __wc_lastSelectedLayer = layer;
        // Apply a highlighted style to the current selection
        if (typeof layer.setStyle === 'function') {
            const highlight = Object.assign({}, featuresLayerStyle || {}, {
                color: '#FF6600',
                weight: (featuresLayerStyle && typeof featuresLayerStyle.weight === 'number')
                    ? Math.max(2, featuresLayerStyle.weight + 3)
                    : 5,
                fillOpacity: (featuresLayerStyle && typeof featuresLayerStyle.fillOpacity === 'number')
                    ? Math.min(1, featuresLayerStyle.fillOpacity + 0.15)
                    : 0.65
            });
            layer.setStyle(highlight);
        }
        // Ensure the selected layer is drawn above overlapping polygons
        try { if (typeof layer.bringToFront === 'function') { layer.bringToFront(); } } catch (_) { }
    } catch (_) { /* ignore styling errors */ }
}

function featureClickHandler(e, featureGroup) {
    // Always compute intersecting features at the click location so overlapping polygons show a list

    const point = { type: 'Point', coordinates: [e.latlng.lng, e.latlng.lat] };
    const intersectingFeatures = new Set();

    try {
        featureGroup.eachLayer(layer => {
            try {
                if (layer && layer.toGeoJSON && layer instanceof L.Polygon) {
                    const gj = layer.toGeoJSON();
                    const poly = gj && gj.geometry ? { type: 'Feature', geometry: gj.geometry, properties: {} } : null;
                    if (poly && turf.inside(point, poly)) {
                        intersectingFeatures.add(layer);
                    }
                }
            } catch (_) { /* ignore */ }
        });
    } catch (_) { /* ignore */ }

    // If Leaflet gave us a specific layer for the click, ensure it is included
    try {
        if (e && e.layer && e.layer.feature && e.layer instanceof L.Polygon) {
            intersectingFeatures.add(e.layer);
        }
    } catch (_) { /* ignore */ }

    let catchment = "No features found";
    let html = "";

    if (intersectingFeatures.size === 0) {
        // Nothing found; keep defaults
    } else if (intersectingFeatures.size === 1) {
        // Auto-select the single item
        const layer = [...intersectingFeatures][0];
        const fid = layer.feature && layer.feature.properties ? layer.feature.properties.id : null;
        if (fid != null && typeof window.SelectionController !== 'undefined') {
            window.SelectionController.select(fid, layer);
        } else {
            selectFeature(layer);
            if (fid != null) { getFeatureDetails(fid); }
        }
        try {
            catchment = layer.feature.properties.catchment;
            const waste_category = layer.feature.properties.waste_category;
            const collection_system = layer.feature.properties.collection_system;
            const detailUrl = getDetailUrlForId(fid);
            html = `<a href="${detailUrl}">${waste_category} - ${collection_system}</a>`;
        } catch (_) { /* ignore */ }
    } else {
        // Multiple overlaps: list all choices without pre-highlighting
        try { catchment = [...intersectingFeatures][0].feature.properties.catchment; } catch (_) { }
        html = [...intersectingFeatures].map(f => {
            try {
                const fid = f.feature.properties.id;
                const waste_category = f.feature.properties.waste_category;
                const collection_system = f.feature.properties.collection_system;
                const detailUrl = getDetailUrlForId(fid);
                return `<a href="${detailUrl}" onclick="return window.__wc_selectFromPopup(${fid}, event)">${waste_category} - ${collection_system}</a>`;
            } catch (_) { return ''; }
        }).filter(Boolean).join('<br>');
    }

    try {
        map.openPopup(`<strong>${catchment}</strong><br/>${html}`, e.latlng, { offset: L.point(0, -24) });
    } catch (_) { /* ignore */ }
}

function createFeatureLayerBindings(featuresLayer) {
    featuresLayer.bindTooltip(function (layer) {
        return layer.feature.properties.catchment.toString();
    });

    featuresLayer.bindPopup(function (layer) {
        return layer.feature.properties.catchment.toString();
    });

    // Expose for cross-module helpers
    try { window.featuresLayer = featuresLayer; } catch (_) { }
    featuresLayer.on('click', e => featureClickHandler(e, featuresLayer));
}

// --- Helpers for selection and navigation from popups ---
function getDetailUrlForId(feature_id) {
    try {
        const detailBtn = document.getElementById('btn-collection-detail');
        const tmpl = detailBtn && detailBtn.dataset && detailBtn.dataset.hrefTemplate;
        if (!tmpl) return '#';
        // Build ?next=<current path with filters>
        let filter_params;
        try { filter_params = parseFilterParameters(); } catch (_) { filter_params = new URLSearchParams(window.location.search); }
        try { filter_params.set('scope', getScope()); } catch (_) { }
        filter_params.set('load_features', 'true');
        const nextTarget = window.location.pathname + '?' + filter_params.toString();
        const params = new URLSearchParams();
        params.set('next', nextTarget);
        const base = tmpl.replace('__pk__', String(feature_id));
        const sep = base.indexOf('?') === -1 ? '?' : '&';
        return base + sep + params.toString();
    } catch (_) { return '#'; }
}

function highlightFeatureById(fid, featureGroup) {
    try {
        const group = featureGroup || (typeof window.featuresLayer !== 'undefined' ? window.featuresLayer : null);
        if (!group || typeof group.eachLayer !== 'function') return;
        group.eachLayer(layer => {
            try {
                const props = layer && layer.feature && layer.feature.properties;
                if (props && String(props.id) === String(fid)) {
                    selectFeature(layer);
                }
            } catch (_) { /* ignore */ }
        });
    } catch (_) { /* ignore */ }
}

window.__wc_selectFromPopup = function (fid, event) {
    let allowDefault = false;
    try {
        if (event) {
            allowDefault = !!(event.ctrlKey || event.metaKey || event.shiftKey || event.button === 1);
        }
    } catch (_) { /* ignore */ }
    try {
        if (typeof window.SelectionController !== 'undefined') {
            window.SelectionController.select(fid);
        } else {
            highlightFeatureById(fid, (typeof window.featuresLayer !== 'undefined') ? window.featuresLayer : null);
            getFeatureDetails(fid);
        }
    } catch (_) { }
    try {
        if (event && typeof event.preventDefault === 'function' && !allowDefault) {
            event.preventDefault();
        }
    } catch (_) { /* ignore */ }
    try { if (typeof map !== 'undefined' && map && typeof map.closePopup === 'function') { map.closePopup(); } } catch (_) { }
    if (allowDefault) {
        return true;
    }
    return false;
};

// --- SelectionController: central state for current selection ---
const SelectionController = (function () {
    let currentId = null;
    function select(fid, layer) {
        try { currentId = String(fid); } catch (_) { currentId = fid; }
        try {
            if (layer) {
                selectFeature(layer);
            } else {
                highlightFeatureById(fid, (typeof window.featuresLayer !== 'undefined') ? window.featuresLayer : null);
            }
        } catch (_) { }
        try { ButtonManager.reset(); } catch (_) { }
        try { showSummaryLoading(); } catch (_) { }
        try { getFeatureDetails(fid); } catch (_) { }
        try { window.dispatchEvent(new CustomEvent('wc-selection-changed', { detail: { id: currentId } })); } catch (_) { }
    }
    function getSelectedId() { return currentId; }
    return { select, getSelectedId };
})();
try { window.SelectionController = SelectionController; } catch (_) { }

// --- Show a loading indicator while details are fetched ---
function showSummaryLoading() {
    try {
        const c = document.getElementById('summary-container');
        if (c) {
            c.innerHTML = '<div class="text-center my-3"><div class="spinner-border text-secondary" role="status" aria-label="Loading"><span class="visually-hidden">Loading...</span></div></div>';
        }
    } catch (_) { /* ignore */ }
}

function clearSummary() {
    try {
        const c = document.getElementById('summary-container');
        if (c) { c.innerHTML = '<p class="card-text">Select a collection on the map to view its details.</p>'; }
    } catch (_) { /* ignore */ }
}

(function hookGetFeatureDetailsWithSpinner() {
    const prev = typeof window.getFeatureDetails === 'function' ? window.getFeatureDetails : null;
    if (!prev) return;
    window.getFeatureDetails = async function (fid) {
        try { showSummaryLoading(); } catch (_) { }
        return await prev(fid);
    };
})();

(function hookRenderSummaries() {
    const original = typeof window.renderSummaries === 'function' ? window.renderSummaries : null;
    if (!original) return;

    window.renderSummaries = function (featureInfos) {
        try { original(featureInfos); } catch (e) { console.warn('Original renderSummaries failed:', e); }
        try {
            const container = document.getElementById('summary-container');
            if (container && (!container.textContent || container.textContent.trim() === '')) {
                clearSummary();
            }
        } catch (_) { /* ignore */ }
    };
})();

function scrollToSummaries() {
    try {
        const summaryTab = document.getElementById("summary-tab");
        if (summaryTab && typeof bootstrap !== 'undefined' && bootstrap.Tab) {
            bootstrap.Tab.getOrCreateInstance(summaryTab).show();
        }
    } catch (_) { /* ignore */ }
    const importantInfoElement = document.getElementById("filter_result_card");
    if (importantInfoElement) {
        importantInfoElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function updateUrls(feature_id) {
    // Build next URL as the current page with current filters and load_features=true
    let filter_params;
    try {
        filter_params = parseFilterParameters();
    } catch (_) {
        filter_params = new URLSearchParams(window.location.search);
    }
    filter_params.set('load_features', 'true');
    // Preserve scope from current URL so we return to the same view (published/private/review)
    try { filter_params.set('scope', getScope()); } catch (_) { }
    const nextTarget = window.location.pathname + '?' + filter_params.toString();
    const params = new URLSearchParams();
    params.set('next', nextTarget);

    try {
        const create_button = document.getElementById('btn-collection-create');
        const create_url = create_button.dataset.hrefTemplate + '?' + params.toString();
        create_button.setAttribute('href', create_url);
    } catch (error) {
        console.warn(`Create button not updated: ${error}`);
    }

    try {
        const detail_button = document.getElementById('btn-collection-detail');
        const detail_url = detail_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString());
        detail_button.setAttribute('href', detail_url);
        detail_button.classList.remove('d-none');
    } catch (error) {
        console.warn(`Detail button not updated: ${error}`);
    }

    try {
        const update_button = document.getElementById('btn-collection-update');
        const update_url = update_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
        update_button.setAttribute('href', update_url);
    } catch (error) {
        console.warn(`Update button not updated: ${error}`);
    }

    try {
        const copy_button = document.getElementById('btn-collection-copy');
        const copy_url = copy_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
        copy_button.setAttribute('href', copy_url);
    } catch (error) {
        console.warn(`Copy button not updated: ${error}`);
    }

    try {
        const delete_button = document.getElementById('btn-collection-delete');
        const delete_url = delete_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
        // Set the href so modal_links.js can read it; then rebind
        delete_button.setAttribute('href', delete_url);
        // Allow re-bind by removing the guard class
        try { delete_button.classList.remove('bmf-bound'); } catch (_) { }
        // Prefer global rewire helper; fallback to direct binding
        try {
            if (typeof window.wireModalLinks === 'function') {
                window.wireModalLinks();
            } else if (typeof window.modalForm === 'function') {
                window.modalForm(delete_button, {
                    formURL: delete_url,
                    modalID: '#modal',
                    errorClass: '.is-invalid'
                });
            }
        } catch (_) { /* ignore */ }
    } catch (error) {
        console.warn(`Delete button not updated: ${error}`);
    }

    // Selection hint off; button enablement handled by ButtonManager.apply()
    hideSelectionHint();
    try {
        const clearBtn = document.getElementById('btn-clear-selection');
        if (clearBtn) clearBtn.classList.remove('d-none');
    } catch (_) { /* ignore */ }
}

function addDetailViewButton() {

}

function clickedPrivateMapButton() {
    const privateMapLink = document.getElementById('link-map-private');
    window.location.href = privateMapLink.dataset.hrefTemplate + '?' + parseFilterParameters().toString();
}

function clickedPublicMapButton() {
    const publicMapLink = document.getElementById('link-map-public');
    console.log(publicMapLink.dataset.hrefTemplate);
    window.location.href = publicMapLink.dataset.hrefTemplate + '?' + parseFilterParameters().toString();
}

function clickedListButton() {
    const listButton = document.getElementById('btn-collections-as-list');
    window.location.href = listButton.dataset.hrefTemplate + '?' + parseFilterParameters().toString();
}

function clickedListLink() {
    const listLink = document.getElementById('link-collections-as-list');
    window.location.href = listLink.dataset.hrefTemplate + '?' + parseFilterParameters().toString();
}

function adaptMapConfig() {
    mapConfig.layerOrder = ['features', 'region', 'catchment'];
}

// --- Ensure dataset version (dv) travels with feature layer filter params ---
(function hookFeaturesLayerFilterParams() {
    function getDatasetVersion() {
        try {
            const ctx = document.getElementById('map-context');
            if (!ctx) return null;
            const dv = ctx.dataset.dv;
            return dv || null;
        } catch (_) { return null; }
    }

    const original = typeof window.getFeaturesLayerFilterParameters === 'function'
        ? window.getFeaturesLayerFilterParameters
        : null;

    window.getFeaturesLayerFilterParameters = function () {
        let params;
        try {
            params = original ? original() : new URLSearchParams(window.location.search);
        } catch (_) {
            params = new URLSearchParams(window.location.search);
        }
        try {
            const dv = getDatasetVersion();
            if (dv) params.set('dv', dv);
        } catch (_) { /* ignore */ }
        return params;
    };
})();

// --- Ensure detail fetch includes current scope so owners can retrieve private items ---
(function hookFetchFeatureDetails() {
    let __wc_currentFetchAbort = null;
    const prevFetch = typeof window.fetchFeatureDetails === 'function' ? window.fetchFeatureDetails : null;
    window.fetchFeatureDetails = async function (feature) {
        try {
            // Abort any pending request
            try { if (__wc_currentFetchAbort) { __wc_currentFetchAbort.abort(); } } catch (_) { }
            __wc_currentFetchAbort = new AbortController();

            // Try to reproduce maps.js behavior but add scope query
            let featureId = typeof feature === 'object' ? (feature.id || (feature.properties && feature.properties.id)) : feature;
            featureId = String(featureId);
            if (!Number.isInteger(parseInt(featureId))) {
                console.warn('Invalid feature id:', featureId);
                if (prevFetch) return prevFetch(feature);
                return Promise.reject(new Error('Invalid feature id'));
            }

            const base = (window.mapConfig && window.mapConfig.featuresLayerDetailsUrlTemplate) || '';
            if (!base) {
                if (prevFetch) return prevFetch(feature);
                return Promise.reject(new Error('Missing details URL template'));
            }
            let url = base + featureId + '/';
            try {
                const scope = (typeof window.getScope === 'function')
                    ? window.getScope()
                    : (new URLSearchParams(window.location.search).get('scope') || 'published');
                const sep = url.indexOf('?') === -1 ? '?' : '&';
                url = url + sep + 'scope=' + encodeURIComponent(scope);
            } catch (_) { /* ignore */ }

            const response = await fetch(url, { signal: __wc_currentFetchAbort.signal });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return await response.json();
        } catch (e) {
            if (e && e.name === 'AbortError') {
                // Silently ignore aborted requests
                return new Promise(() => { });
            }
            console.warn('fetchFeatureDetails override failed, delegating to original:', e);
            if (prevFetch) return prevFetch(feature);
            throw e;
        }
    };
})();

// --- Permission-driven enable/disable of actions on selection ---
// --- ButtonManager (Step 2): centralize enabling/disabling based on server policy when available ---
const ButtonManager = (function () {
    function buildNextParams() {
        let filter_params;
        try {
            filter_params = parseFilterParameters();
        } catch (_) {
            filter_params = new URLSearchParams(window.location.search);
        }
        try { filter_params.set('scope', getScope()); } catch (_) { }
        filter_params.set('load_features', 'true');
        const nextTarget = window.location.pathname + '?' + filter_params.toString();
        const params = new URLSearchParams();
        params.set('next', nextTarget);
        return params;
    }

    function apply(data) {
        try {
            const nextParams = buildNextParams();

            try {
                const detailBtn = document.getElementById('btn-collection-detail');
                if (detailBtn) {
                    const tmpl = detailBtn.dataset.hrefTemplate;
                    if (tmpl) {
                        const detailUrl = tmpl.replace('__pk__', data.id);
                        const sep = detailUrl.indexOf('?') === -1 ? '?' : '&';
                        detailBtn.setAttribute('href', detailUrl + sep + nextParams.toString());
                        detailBtn.classList.remove('d-none');
                    } else {
                        detailBtn.classList.add('d-none');
                    }
                }
            } catch (_) { }

            try {
                const updateBtn = document.getElementById('btn-collection-update');
                if (updateBtn) {
                    const tmpl = updateBtn.dataset.hrefTemplate;
                    if (tmpl) {
                        updateBtn.setAttribute('href', tmpl.replace('__pk__', data.id) + '?' + nextParams.toString());
                    }
                }
            } catch (_) { }

            try {
                const copyBtn = document.getElementById('btn-collection-copy');
                if (copyBtn) {
                    const tmpl = copyBtn.dataset.hrefTemplate;
                    if (tmpl) {
                        copyBtn.setAttribute('href', tmpl.replace('__pk__', data.id) + '?' + nextParams.toString());
                    }
                }
            } catch (_) { }

            try {
                const delBtn = document.getElementById('btn-collection-delete');
                if (delBtn) {
                    const tmpl = delBtn.dataset.hrefTemplate;
                    if (tmpl) {
                        const delUrl = tmpl.replace('__pk__', data.id) + '?' + nextParams.toString();
                        delBtn.setAttribute('href', delUrl);
                        try { delBtn.classList.remove('bmf-bound'); } catch (_) { }
                        try {
                            if (typeof window.wireModalLinks === 'function') {
                                window.wireModalLinks();
                            } else if (typeof window.modalForm === 'function') {
                                window.modalForm(delBtn, { formURL: delUrl, modalID: '#modal', errorClass: '.is-invalid' });
                            }
                        } catch (_) { }
                    }
                }
            } catch (_) { }

            const policy = data && data.policy ? data.policy : null;
            try { console.debug('[WC] policy from server:', policy); } catch (_) { }
            let canUpdate = false, canDelete = false, canCopy = false;
            if (policy) {
                // Align strictly with permissions.py keys
                canUpdate = !!policy.can_edit;
                canDelete = !!policy.can_delete;
                canCopy = !!policy.can_duplicate;
            } else {
                // No policy provided: keep actions disabled and warn for diagnostics
                try { console.warn('[WC] Missing policy in feature details; actions remain disabled.'); } catch (_) { }
            }

            try { console.debug('[WC] computed button perms:', { canUpdate, canDelete, canCopy }); } catch (_) { }
            const updateBtn = document.getElementById('btn-collection-update');
            const delBtn = document.getElementById('btn-collection-delete');
            const copyBtn = document.getElementById('btn-collection-copy');

            if (updateBtn) { canUpdate ? enableBtn(updateBtn) : disableBtn(updateBtn, 'You do not have permission to edit this item.'); }
            if (delBtn) { canDelete ? enableBtn(delBtn) : disableBtn(delBtn, 'You do not have permission to delete this item.'); }
            if (copyBtn) { canCopy ? enableBtn(copyBtn) : disableBtn(copyBtn, 'You do not have permission to copy this item.'); }
        } catch (e) {
            console.warn('ButtonManager.apply failed:', e);
        }
    }

    function reset() {
        try { disableBtn(document.getElementById('btn-collection-copy'), 'Select a collection on the map first'); } catch (_) { }
        try { disableBtn(document.getElementById('btn-collection-update'), 'Select a collection on the map first'); } catch (_) { }
        try { disableBtn(document.getElementById('btn-collection-delete'), 'Select a collection on the map first'); } catch (_) { }
        try { const d = document.getElementById('btn-collection-detail'); if (d) d.classList.add('d-none'); } catch (_) { }
        try { const hint = document.getElementById('map-actions-hint'); if (hint) hint.classList.remove('d-none'); } catch (_) { }
        try { const cs = document.getElementById('btn-clear-selection'); if (cs) cs.classList.add('d-none'); } catch (_) { }
    }

    return { apply, reset };
})();

(function hookRenderFeatureDetails() {
    // Keep original renderer
    const original = typeof window.renderFeatureDetails === 'function' ? window.renderFeatureDetails : null;

    window.renderFeatureDetails = function (data) {
        try { if (original) original(data); } catch (e) { console.warn('Original renderFeatureDetails failed:', e); }
        try {
            const container = document.getElementById('summary-container');
            if (container && (!container.textContent || container.textContent.trim() === '')) {
                clearSummary();
            }
        } catch (_) { /* ignore */ }
        try { ButtonManager.apply(data); } catch (e) { console.warn('ButtonManager.apply hook failed:', e); }
    };
})();

function clearSelection() {
    // Unhighlight the last selected feature
    try {
        if (__wc_lastSelectedLayer && typeof __wc_lastSelectedLayer.setStyle === 'function' && typeof featuresLayerStyle === 'object') {
            __wc_lastSelectedLayer.setStyle(featuresLayerStyle);
        }
        __wc_lastSelectedLayer = null;
    } catch (_) { /* ignore */ }

    // Reset buttons and UI state via ButtonManager
    try { ButtonManager.reset(); } catch (_) { }

    // Clear sidebar summary
    clearSummary();

    // Close any open popup
    try { if (typeof map !== 'undefined' && map && typeof map.closePopup === 'function') { map.closePopup(); } } catch (_) { }
    try { window.dispatchEvent(new CustomEvent('wc-selection-cleared')); } catch (_) { }
}

// (No duplicate SelectionController definitions)