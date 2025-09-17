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
        format: (value) => formatList(value, ', ')
    },
    forbidden_materials: {
        include: true,
        format: (value) => formatList(value, ', ')
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

// --- UI helpers ---
function britEnableBtn(el) {
    if (!el) return;
    el.classList.remove('disabled');
    el.removeAttribute('aria-disabled');
    el.removeAttribute('tabindex');
    if (el.title && el.title.indexOf('Select a collection') !== -1) {
        el.removeAttribute('title');
    }
}

function britDisableBtn(el, title) {
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

function hideSelectionHint() {
    const hint = document.getElementById('map-actions-hint');
    if (hint) hint.classList.add('d-none');
}

function featureClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

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

    if (intersectingFeatures.size) {
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
        modalForm(delete_button, {
            formURL: delete_url,
            errorClass: ".is-invalid"
        });
    } catch (error) {
        console.warn(`Delete button not updated: ${error}`);
    }

    // Always enable Copy once a feature is selected
    try { britEnableBtn(document.getElementById('btn-collection-copy')); } catch (_) { }
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

// --- Permission-driven enable/disable of actions on selection ---
(function hookRenderFeatureDetails() {
    // Keep original renderer
    const original = typeof window.renderFeatureDetails === 'function' ? window.renderFeatureDetails : null;

    window.renderFeatureDetails = function (data) {
        try { if (original) original(data); } catch (e) { console.warn('Original renderFeatureDetails failed:', e); }

        try {
            const status = String(data && data.publication_status || '').toLowerCase();
            const scope = getScope();
            const staff = isStaffUser();

            // Rules:
            // - Staff: can edit/delete any
            // - Non-staff: only when in private scope (owner-only dataset) AND item is not published
            const canModify = staff || (scope === 'private' && status !== 'published');

            const updateBtn = document.getElementById('btn-collection-update');
            const delBtn = document.getElementById('btn-collection-delete');

            if (canModify) {
                britEnableBtn(updateBtn);
                britEnableBtn(delBtn);
            } else {
                britDisableBtn(updateBtn, 'Select a permitted collection (private/review) or be staff');
                britDisableBtn(delBtn, 'Select a permitted collection (private/review) or be staff');
            }
        } catch (e) {
            console.warn('Failed to toggle Edit/Delete availability:', e);
        }
    };
})();