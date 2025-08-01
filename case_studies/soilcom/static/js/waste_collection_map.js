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
    const filter_params = parseFilterParameters();
    filter_params.append('load_features', 'true');
    const params = new URLSearchParams();
    params.append('next', '/waste_collection/collections/map/?' + filter_params.toString());

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