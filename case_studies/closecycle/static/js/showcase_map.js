"use strict";

// Load 'lib/turf-inside/inside.min.js' script before this

const fieldConfig = {
    name: {
        include: true,
        format: (value) => value || ''
    },
    description: {
        include: true,
        format: (value) => value || ''
    },
};

function featureClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

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
        getFeatureDetails(feature.feature.id);
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

async function handleShowcaseClick(id, region, featureIndex) {
    resetFeatureStyles(window.featureGroup);
    const feature = window.intersectingFeatures.get(region)[featureIndex];
    selectFeature(feature);
    await getFeatureDetails(feature.feature.id);
    map.closePopup();
}

function scrollToSummaries() {
    const importantInfoElement = document.getElementById("filter_result_card");
    if (importantInfoElement) {
        importantInfoElement.scrollIntoView({behavior: 'smooth', block: 'start'});
    }
}

function createFeatureLayerBindings(showcaseLayer) {
    showcaseLayer.on('click', e => featureClickHandler(e, showcaseLayer));
}

function uncollapseInfoCardBody() {
    const infoCardBody = document.getElementById("info-card-body");
    if (infoCardBody) {
        infoCardBody.classList.remove("collapse");
    }
}
document.addEventListener("DOMContentLoaded", uncollapseInfoCardBody);