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
        .forEach(selector => selector.disabled = true);
}

function unlockForm() {
    document.querySelectorAll("select")
        .forEach(selector => selector.disabled = false);
}

async function updateLayers({ region_params, catchment_params, feature_params } = {}) {
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

async function clickedFeature(event) {
    lockForm();
    const feature = event.layer.feature;
    const featureId = feature.properties.id;
    const featureDetails = await fetchFeatureDetails(featureId);
    renderFeatureDetails(featureDetails);
    setSelect2Value(
        `#id_level_${feature.properties.level}`,
        featureId,
        `${featureDetails.name} (${featureDetails.nuts_id})`
    );
    await updateMapAccordingToSelection();
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
    return params;
}

function setSelect2Value(selectSelector, id, name) {
    const select = document.querySelector(selectSelector);
    if (!select) {
        console.warn(`Select element not found: ${selectSelector}`);
        return;
    }

    // Check if option with this value already exists
    const existingOption = select.querySelector(`option[value="${id}"]`);

    if (!existingOption) {
        // Create a new option element
        const option = document.createElement('option');
        option.value = id;
        option.text = name;
        option.selected = true;

        setProgrammaticChange(() => {
            select.appendChild(option);
            // Dispatch change event
            const event = new Event('change', { bubbles: true });
            select.dispatchEvent(event);
        });
    } else {
        setProgrammaticChange(() => {
            select.value = id;
            // Dispatch change event
            const event = new Event('change', { bubbles: true });
            select.dispatchEvent(event);
        });
    }
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
                setSelect2Value(`#id_level_${level}`, value.id, value.name);
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
    const level0 = document.getElementById('id_level_0').value;
    const level1 = document.getElementById('id_level_1').value;
    const level2 = document.getElementById('id_level_2').value;
    const level3 = document.getElementById('id_level_3').value;

    const selectedLevel = level3 || level2 || level1 || level0;

    if (selectedLevel) {
        mapConfig.adjustBoundsToLayer = 'catchment';
        setLayerOrder(['region', 'features', 'catchment']);
        if (level3) {
            await updateLayers({
                catchment_params: { id: selectedLevel },
                feature_params: { id: selectedLevel }
            });
        } else {
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

function clearFields(fields) {
    setProgrammaticChange(() => {
        fields.forEach(function (field) {
            const element = document.getElementById(`id_${field}`);
            if (element) {
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

    if (regionId) {
        await populateParents(regionId);
        clearLowerFields(changedField);
    } else {
        clearLowerFields(changedField);
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
        clearFields(fieldMap[level]);
    }
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