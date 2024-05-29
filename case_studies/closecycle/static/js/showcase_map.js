"use strict";

// Load 'lib/turf-inside/inside.min.js' script before this

function selectFeature(feature) {
    feature.bringToFront();
    feature.setStyle({
        "color": "#f49a33",
    });
}

function resetFeatureStyles(featureGroup) {
    featureGroup.resetStyle();
    featureGroup.bringToBack();
}

function showcaseClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

    // Find intersecting features by region
    const intersectingFeatures = new Map();
    featureGroup.eachLayer(layer => {
        if (layer instanceof L.Polygon) {
            const polygon = layer.toGeoJSON();
            const point = [e.latlng.lng, e.latlng.lat];
            if (turf.inside(point, polygon)) {
                const regionName = layer.feature.properties.region;
                if (!intersectingFeatures.has(regionName)) {
                    intersectingFeatures.set(regionName, []);
                }
                intersectingFeatures.get(regionName).push(layer);
            }
        }
    });

    // Store intersecting features globally to access in handleShowcaseClick
    window.intersectingFeatures = intersectingFeatures;
    window.featureGroup = featureGroup; // Store featureGroup globally

    // Check number of intersecting regions
    if (intersectingFeatures.size === 1) {
        // If only one region, call getShowcaseDetails directly
        const [region] = intersectingFeatures.keys();
        const features = intersectingFeatures.get(region);
        const feature = features[0];
        selectFeature(feature);
        getShowcaseDetails(feature.feature.id);
    } else {
        // Select all overlapping features
        intersectingFeatures.forEach(features => {
            features.forEach(feature => selectFeature(feature));
        });

        // Generate popup content
        let html = "";

        intersectingFeatures.forEach((features, region) => {
            html += `<strong>${region}</strong><br/>`;
            html += features.map((feature, index) => {
                const id = feature.feature.id;
                const name = feature.feature.properties.name;
                return `<a href="javascript:void(0)" onclick="handleShowcaseClick(${id}, '${region}', ${index})">${name}</a><br>`;
            }).join("");
            html += "<br>"; // Add an empty line between region groups
        });

        html = html.replace(/<br>$/, "");


        if (html === "") {
            html = "No features found";
        }

        map.openPopup(html.trim(), e.latlng, {offset: L.point(0, -24)}); // trim() to remove any trailing whitespace
    }
}

function handleShowcaseClick(id, region, featureIndex) {
    resetFeatureStyles(window.featureGroup);

    const feature = window.intersectingFeatures.get(region)[featureIndex];
    selectFeature(feature);

    getShowcaseDetails(id);

    map.closePopup();
}

async function getShowcaseDetails(fid) {
    try {
        const summaries = await fetchFeatureSummaries(fid);
        renderSummaries(summaries);
    } catch (error) {
        console.error(`Error fetching feature summaries for id ${fid}: ${error}`);
    }
}

function createFeatureLayerBindings(showcaseLayer) {
    showcaseLayer.on('click', e => showcaseClickHandler(e, showcaseLayer));
}
