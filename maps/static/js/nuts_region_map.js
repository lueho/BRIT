"use strict";

let isProgrammaticChange = false;

const fieldConfig = {
    nuts_id: {
        include: true, format: (value) => value || ''
    },
    name: {
        include: true, format: (value) => value || ''
    },
    population: {
        include: true, format: (value) => value || ''
    },
    population_density: {
        include: true, format: (value) => value || ''
    },
    urban_rural_remoteness: {
        include: true, format: (value) => value || ''
    },
};

function lockForm() {
    document.querySelectorAll("select")
        .forEach(selector => {
            selector.disabled = true;
            if (selector.tomselect) {
                selector.tomselect.disable();
            }
        });
}

function unlockForm() {
    document.querySelectorAll("select")
        .forEach(selector => {
            selector.disabled = false;
            if (selector.tomselect) {
                selector.tomselect.enable();
            }
        });
}

/**
 * The NUTS vintage selected in the filter form, e.g. '2021'.
 * Codes repeat across vintages, so every feature query must name one.
 */
function selectedVintage() {
    const field = document.getElementById('id_version');
    return field ? field.value : '';
}

const AUTOCOMPLETE_PATH = '/maps/nutsregions/autocomplete/';

/**
 * Add the selected vintage and the nearest selected ancestor to a NUTS
 * autocomplete request.
 *
 * Done at the fetch layer rather than by patching TomSelect's ``firstUrl``:
 * django-tomselect restores its own URL builder whenever it resets a widget
 * (which clearing a field does), so an override there silently disappears and
 * the picker starts offering another vintage's regions.
 */
function withAutocompleteParams(input) {
    const url = new URL(input, window.location.origin);
    if (!url.pathname.startsWith(AUTOCOMPLETE_PATH)) {
        return input;
    }
    const vintage = selectedVintage();
    if (vintage) {
        url.searchParams.set('version', vintage);
    }
    const level = url.pathname.match(/level(\d)\/$/);
    if (level) {
        const ancestor = getAncestorNutsId(Number(level[1]));
        if (ancestor) {
            url.searchParams.set('ancestor', ancestor);
        }
    }
    return url.pathname + url.search;
}

function patchAutocompleteFetch() {
    const originalFetch = window.fetch;
    window.fetch = function (resource, ...rest) {
        if (typeof resource === 'string') {
            resource = withAutocompleteParams(resource);
        } else if (resource instanceof Request) {
            const rewritten = withAutocompleteParams(resource.url);
            if (rewritten !== resource.url) {
                resource = new Request(rewritten, resource);
            }
        }
        return originalFetch.call(this, resource, ...rest);
    };
}

// Installed at parse time so no widget can load before the wrapper is in place.
patchAutocompleteFetch();

function withVintage(params) {
    const vintage = selectedVintage();
    return vintage ? { ...params, version: vintage } : params;
}

async function updateLayers({ region_params, catchment_params, feature_params } = {}) {
    if (feature_params) {
        feature_params = withVintage(feature_params);
    }
    if (!catchment_params && catchmentLayer) {
        // The highlight of a region that is no longer selected would otherwise
        // stay on the map, showing a shape from the vintage just left behind.
        removeExistingLayer(catchmentLayer);
        catchmentLayer = null;
    }
    const promises = [
        region_params && fetchRegionGeometry(region_params),
        catchment_params && fetchCatchmentGeometry(catchment_params),
        feature_params && fetchFeatureGeometries(feature_params)
    ].filter(Boolean);
    prepareMapRefresh();
    await refreshMap(promises);
}

function cleanup() {
    hideLoadingIndicator();
    unlockForm();
    unlockFilter();
}

function adaptMapConfig() {
    mapConfig.layerOrder = ['features', 'region', 'catchment'];
}

function loadAndSelect(selectSelector, id, name) {
    const ts = document.querySelector(selectSelector)?.tomselect;
    if (!ts) return;
    return new Promise(res => {
        const once = () => {
            if (ts.options[id]) {
                ts.setValue(id);
                ts.off('load', once);
                res();
            }
        };
        ts.on('load', once);
        ts.load(id);
    });
}

async function clickedFeature(event) {
    lockForm();
    const feature = event.layer.feature;
    const featureId = feature.properties.id;
    const featureDetails = await fetchFeatureDetails(featureId);
    renderFeatureDetails(featureDetails);
    await loadAndSelect(
        `#id_level_${feature.properties.level}`,
        featureId,
        `${featureDetails.name} (${featureDetails.nuts_id})`
    );
}

/**
 * Ensures the initial query parameter `levl_code=0` is set on a fresh page load.
 */
function getQueryParameters() {
    const params = new URLSearchParams(window.location.search);

    if ([...params.keys()].length === 0) {
        params.append('levl_code', '0');

        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.history.replaceState({}, '', newUrl);
    }
    if (!params.has('version')) {
        const vintage = selectedVintage();
        if (vintage) {
            params.set('version', vintage);
        }
    }
    return params;
}

function setTomSelectValue(selectSelector, id, name) {
    const select = document.querySelector(selectSelector);
    if (!select) {
        console.warn(`Select element not found: ${selectSelector}`);
        return;
    }

    if (!select.tomselect) {
        console.warn(`TomSelect not initialized for: ${selectSelector}`);
        return;
    }

    // Check if option with this value already exists in TomSelect
    const existingOption = select.tomselect.options[id];

    setProgrammaticChange(() => {
        if (!existingOption) {
            // Add the option to TomSelect
            console.log("Adding option to TomSelect")
            console.log(id)
            console.log(name)
            select.tomselect.load(id);
            select.tomselect.setValue(id);
        }
    });
}

async function populateParents(regionId) {
    try {
        const response = await fetch(`/maps/api/nutsregion/${regionId}/parents/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        for (const [key, value] of Object.entries(data)) {
            const level = key.split('_')[1];

            if (value) {
                setTomSelectValue(`#id_level_${level}`, value.id, value.name);
            }
        }
    } catch (error) {
        console.error('Error fetching parent regions:', error);
    }
}

function setProgrammaticChange(callback) {
    isProgrammaticChange = true;
    callback();
    isProgrammaticChange = false;
}

async function updateMapAccordingToSelection() {
    console.log("Updating map according to selection")
    const level0 = document.getElementById('id_level_0').value;
    console.log(level0)
    const level1 = document.getElementById('id_level_1').value;
    console.log(level1)
    const level2 = document.getElementById('id_level_2').value;
    console.log(level2)
    const level3 = document.getElementById('id_level_3').value;
    console.log(level3)

    const selectedLevel = level3 || level2 || level1 || level0;
    console.log(selectedLevel)

    if (selectedLevel) {
        mapConfig.adjustBoundsToLayer = 'catchment';
        setLayerOrder(['region', 'features', 'catchment']);
        if (level3) {
            console.log("Updating map according to selection level 3")
            await updateLayers({
                catchment_params: { id: selectedLevel },
                feature_params: { id: selectedLevel }
            });
        } else {
            console.log("Updating map according to selection")
            await updateLayers({
                catchment_params: { id: selectedLevel },
                feature_params: { parent_id: selectedLevel }
            });
        }
    } else {
        mapConfig.adjustBoundsToLayer = 'region';
        setLayerOrder(['features', 'region']);

        await updateLayers({
            feature_params: { levl_code: 0 }
        });
    }
}

/**
 * Empty one region picker and make it fetch its options again.
 *
 * Emptying alone is not enough: TomSelect skips a query it has already loaded
 * and virtual_scroll skips one it has already paged, so a picker whose options
 * were dropped would stay empty forever. The reload has to bypass
 * ``shouldLoad``, which django-tomselect uses to refuse the empty query.
 */
function resetPicker(ts) {
    ts.clear(true);
    if (ts.clearPagination) {
        ts.clearPagination();
    }
    ts.clearOptions();
    ts.loadedSearches = {};
    ts.lastQuery = null;
    ts.settings.pagination = {};

    const shouldLoad = ts.settings.shouldLoad;
    ts.settings.shouldLoad = () => true;
    try {
        ts.load('');
    } finally {
        setTimeout(() => {
            ts.settings.shouldLoad = shouldLoad;
        }, 0);
    }
}

function clearFields(fields) {
    setProgrammaticChange(() => {
        fields.forEach(function (field) {
            const element = document.getElementById(`id_${field}`);
            if (element) {
                if (element.tomselect) {
                    resetPicker(element.tomselect);
                }
                element.value = null;
                const event = new Event('change', { bubbles: true });
                element.dispatchEvent(event);
            }

        });
    });
}

function resetFeatureDetails() {
    setLayerOrder(defaultLayerOrder);
    renderFeatureDetails({});
}

const changedSelect = async function (e) {
    if (isProgrammaticChange || e.target.tagName !== 'SELECT') {
        return;
    }
    lockForm();

    const changedField = e.target.id;
    let regionId = e.target.value;

    if (changedField === 'id_version') {
        // Region ids belong to one vintage, so no selection survives a switch.
        clearFields(['level_0', 'level_1', 'level_2', 'level_3']);
        resetFeatureDetails();
        await updateMapAccordingToSelection();
        return;
    }

    if (regionId) {
        // await populateParents(regionId);
        // clearLowerFields(changedField);
    } else {
        // clearLowerFields(changedField);
        if (changedField === 'id_level_0') {
            resetFeatureDetails();
        }

        const parentFieldMap = {
            'id_level_1': 'id_level_0',
            'id_level_2': 'id_level_1',
            'id_level_3': 'id_level_2'
        };
        if (parentFieldMap[changedField]) {
            regionId = document.getElementById(parentFieldMap[changedField]).value;
        }
    }

    await updateMapAccordingToSelection();

    if (regionId) {
        const details = await fetchFeatureDetails(regionId);
        await renderFeatureDetails(details);
    }
};

function clearLowerFields(level) {
    const fieldMap = {
        id_level_0: ['level_1', 'level_2', 'level_3'],
        id_level_1: ['level_2', 'level_3'],
        id_level_2: ['level_3'],
        id_level_3: []
    };
    if (fieldMap[level]) {
        // clearFields(fieldMap[level]);
    }
}

/**
 * Get the nuts_id of the most specific selected ancestor for a given level.
 * For example, if level 3 is being loaded and level 0 is selected, return level 0's nuts_id.
 */
function getAncestorNutsId(targetLevel) {
    // Check ancestor levels from most specific to least specific
    for (let level = targetLevel - 1; level >= 0; level--) {
        const field = document.getElementById(`id_level_${level}`);
        if (field && field.value && field.tomselect) {
            const selectedOption = field.tomselect.options[field.value];
            if (selectedOption && selectedOption.nuts_id) {
                return selectedOption.nuts_id;
            }
        }
    }
    return null;
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('change', (event) => {
            if (event.target.tagName === 'SELECT') {
                changedSelect(event);
            }
        });
    }
});