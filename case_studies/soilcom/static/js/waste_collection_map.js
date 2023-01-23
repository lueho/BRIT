function collectionClickHandler(e) {
    const intersectingFeatures = new Set();
    Object.values(map._layers)
        .filter(overlay => overlay._layers)
        .flatMap(overlay => Object.values(overlay._layers))
        .filter(feature => {
            if (feature instanceof L.Polygon) {
                const polygon = feature.toGeoJSON();
                const point = turf.point([e.latlng.lng, e.latlng.lat]);
                if (turf.inside(point, polygon)) {
                    intersectingFeatures.add(feature);
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
            return `<a href="javascript:void(0)" onclick="getCollectionDetails(${feature.feature.properties.id})">${waste_category} - ${collection_system}</a><br>`;
        }).join("");
    }
    map.openPopup(`<strong>${catchment}</strong><br/>${html}`, e.latlng, {
        offset: L.point(0, -24)
    });
}

function createFeatureLayerBindings(feature_layer) {
    feature_layer.bindTooltip(function(layer) {
        return layer.feature.properties.catchment.toString();
    });

    feature_layer.bindPopup(function(layer) {
        return layer.feature.properties.catchment.toString();
    });

    feature_layer.on('click', collectionClickHandler);
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