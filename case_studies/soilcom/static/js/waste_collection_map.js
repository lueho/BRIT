"use strict";

// Load 'lib/turf-inside/inside.min.js' script before this

function selectFeature(feature) {
    feature.bringToFront();
    feature.setStyle({
        "color": "#f49a33",
    });
}

function collectionClickHandler(e, featureGroup) {
    featureGroup.resetStyle();
    featureGroup.bringToBack();

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
            return `<a href="javascript:void(0)" onclick="getCollectionDetails(${feature.feature.properties.id})">${waste_category} - ${collection_system}</a><br>`;
        }).join("");
    }

    map.openPopup(`<strong>${catchment}</strong><br/>${html}`, e.latlng, {
        offset: L.point(0, -24)
    });
}

function createFeatureLayerBindings(collectionLayer) {
    collectionLayer.bindTooltip(function(layer) {
        return layer.feature.properties.catchment.toString();
    });

    collectionLayer.bindPopup(function(layer) {
        return layer.feature.properties.catchment.toString();
    });

    collectionLayer.on('click', e => collectionClickHandler(e, collectionLayer));
}

async function getCollectionDetails(fid) {
    try {
        const summaries = await fetchFeatureSummaries(fid);
        renderSummaries(summaries);
        updateUrls(fid);
    } catch (error) {
        console.error(`Error fetching feature summaries for id ${fid}: ${error}`);
    }
}

function updateUrls(feature_id) {
    const filter_params = parseFilterParameters();
    filter_params.append('load_features', 'true')
    const params = new URLSearchParams();
    params.append('next', '/waste_collection/collections/map/?' + filter_params.toString());

    const create_button = document.getElementById('btn-collection-create');
    const create_url = create_button.dataset.hrefTemplate + '?' + params.toString();
    create_button.setAttribute('href', create_url);

    const detail_button = document.getElementById('btn-collection-detail');
    const detail_url = detail_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString());
    detail_button.setAttribute('href', detail_url);
    detail_button.classList.remove('d-none');

    const update_button = document.getElementById('btn-collection-update');
    const update_url = update_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
    update_button.setAttribute('href', update_url);

    const copy_button = document.getElementById('btn-collection-copy');
    let copy_url = copy_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
    copy_button.setAttribute('href', copy_url);

    const delete_button = document.getElementById('btn-collection-delete');
    const delete_url = delete_button.dataset.hrefTemplate.replace('__pk__', feature_id.toString()) + '?' + params.toString();
    $('#btn-collection-delete').modalForm({
        formURL: delete_url,
        errorClass: ".is-invalid"
    });
}

function clickedCreateButton() {
    const filter_params = parseFilterParameters();
    filter_params.append('load_features', 'true');
    const params = new URLSearchParams();
    params.append('next', window.location.href + '?' + filter_params.toString());
    window.location.href = "{% url 'catchment-selection' %}" + '?' + params.toString();
}

function addDetailViewButton() {

}

function clickedListLink() {
    window.location.href = "{% url 'collection-list' %}" + '?' + parseFilterParameters().toString();
}