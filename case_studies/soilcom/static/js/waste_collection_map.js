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
        include: true,
        format: (value) => {
            if (!value) return '';
            const str = Array.isArray(value) ? value.join(', ') : value;
            return formatList(str, ', ');
        }
    },
    forbidden_materials: {
        include: true,
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
        include: true,
        format: (value) => {
            const urlList = formatUrls(value);
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
        return value;
    } catch (_) {
        return null;
    }
}

function isStaffUser() {
    const flag = getContextFlag('isStaff');
    return flag === true; // default to false if not provided
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
                    ? Math.max(1, featuresLayerStyle.weight + 2)
                    : 4,
                fillOpacity: (featuresLayerStyle && typeof featuresLayerStyle.fillOpacity === 'number')
                    ? Math.min(1, featuresLayerStyle.fillOpacity + 0.1)
                    : 0.6
            });
            layer.setStyle(highlight);
        }
    } catch (_) { /* ignore styling errors */ }
}

function featureClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

    // Prefer the exact clicked layer if Leaflet provides it
    if (e && e.layer && e.layer.feature) {
        const layer = e.layer;
        selectFeature(layer);
        const props = layer.feature.properties || {};
        if (props.id != null) {
            getFeatureDetails(props.id);
        }
        try {
            const catchment = props.catchment;
            const waste_category = props.waste_category;
            const collection_system = props.collection_system;
            const html = `<a href="javascript:void(0)" onclick="getFeatureDetails(${props.id})">${waste_category} - ${collection_system}</a>`;
            map.openPopup(`<strong>${catchment}</strong><br/>${html}`, e.latlng, { offset: L.point(0, -24) });
        } catch (_) { /* ignore */ }
        return;
    }

    // Fallback: detect polygons under the click
    const intersectingFeatures = new Set();

    featureGroup.eachLayer(layer => {
        if (layer instanceof L.Polygon) {
            const polygon = layer.toGeoJSON();
            const point = [e.latlng.lng, e.latlng.lat];
            if (turf.inside(point, polygon)) {
                intersectingFeatures.add(layer);
            }
        }
    });

    let catchment = "No features found";
    let html = "";

    if (intersectingFeatures.size === 1) {
        const layer = [...intersectingFeatures][0];
        selectFeature(layer);
        const fid = layer.feature.properties.id;
        if (fid != null) {
            getFeatureDetails(fid);
        }
        catchment = layer.feature.properties.catchment;
        const waste_category = layer.feature.properties.waste_category;
        const collection_system = layer.feature.properties.collection_system;
        html = `<a href="javascript:void(0)" onclick="getFeatureDetails(${fid})">${waste_category} - ${collection_system}</a>`;
    } else if (intersectingFeatures.size > 1) {
        catchment = [...intersectingFeatures][0].feature.properties.catchment;
        html = [...intersectingFeatures].map(feature => {
            const waste_category = feature.feature.properties.waste_category;
            const collection_system = feature.feature.properties.collection_system;
            selectFeature(feature);
            return `<a href="javascript:void(0)" onclick="getFeatureDetails(${feature.feature.properties.id})">${waste_category} - ${collection_system}</a><br>`;
        }).join("");
    }

    map.openPopup(`<strong>${catchment}</strong><br/>${html}`, e.latlng, {
        offset: L.point(0, -24)
    });
}

function createFeatureLayerBindings(featuresLayer) {
    featuresLayer.bindTooltip(function (layer) {
        return layer.feature.properties.catchment.toString();
    });

    featuresLayer.bindPopup(function (layer) {
        return layer.feature.properties.catchment.toString();
    });

    featuresLayer.on('click', e => featureClickHandler(e, featuresLayer));
}

function scrollToSummaries() {
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

    // Always enable Copy once a feature is selected
    try { enableBtn(document.getElementById('btn-collection-copy')); } catch (_) { }
    hideSelectionHint();
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
    const prevFetch = typeof window.fetchFeatureDetails === 'function' ? window.fetchFeatureDetails : null;
    window.fetchFeatureDetails = async function (feature) {
        try {
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

            const response = await fetch(url);
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return await response.json();
        } catch (e) {
            console.warn('fetchFeatureDetails override failed, delegating to original:', e);
            if (prevFetch) return prevFetch(feature);
            throw e;
        }
    };
})();

// --- Permission-driven enable/disable of actions on selection ---
(function hookRenderFeatureDetails() {
    // Keep original renderer
    const original = typeof window.renderFeatureDetails === 'function' ? window.renderFeatureDetails : null;

    window.renderFeatureDetails = function (data) {
        try { if (original) original(data); } catch (e) { console.warn('Original renderFeatureDetails failed:', e); }

        try {
            const status = String(data && data.publication_status || '').toLowerCase();
            const staff = isStaffUser();
            const ownerId = (data && data.owner_id != null) ? String(data.owner_id) : null;
            const currentUserId = getCurrentUserId();
            const isOwner = !!(ownerId && currentUserId != null && String(currentUserId) === ownerId);

            const isPublished = status === 'published';
            const isArchived = status === 'archived';

            // Align with utils/object_management/permissions.get_object_policy
            const canEdit = !isArchived && (staff || (isOwner && !isPublished));
            const canDelete = (isArchived && staff) || (!isArchived && ((isPublished && staff) || (!isPublished && (isOwner || staff))));

            const updateBtn = document.getElementById('btn-collection-update');
            const delBtn = document.getElementById('btn-collection-delete');

            if (updateBtn) {
                if (canEdit) { enableBtn(updateBtn); }
                else { disableBtn(updateBtn, 'You do not have permission to edit this item.'); }
            }
            if (delBtn) {
                if (canDelete) { enableBtn(delBtn); }
                else { disableBtn(delBtn, 'You do not have permission to delete this item.'); }
            }
        } catch (e) {
            console.warn('Failed to toggle Edit/Delete availability:', e);
        }
    };
})();