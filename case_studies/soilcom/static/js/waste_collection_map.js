"use strict";

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