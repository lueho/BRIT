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

function isSafeLocalUrl(url) {
    return typeof url === 'string'
        && url.startsWith('/')
        && !url.startsWith('//')
        && !url.split('').some(ch => ch === '\\' || ch.charCodeAt(0) <= 0x20 || ch.charCodeAt(0) === 0x7f);
}

function appendLinkItem(list, item) {
    if (!item || typeof item !== 'object') {
        return;
    }
    const li = document.createElement('li');
    if (isSafeLocalUrl(item.url)) {
        const a = document.createElement('a');
        a.href = item.url;
        a.textContent = item.name;
        li.appendChild(a);
    } else {
        li.textContent = item.name;
    }
    list.appendChild(li);
}

function appendListSection(container, heading, items, ordered) {
    if (!Array.isArray(items) || items.length === 0) {
        return;
    }
    const headingElement = document.createElement('h6');
    headingElement.textContent = heading;
    container.appendChild(headingElement);
    const list = document.createElement(ordered ? 'ol' : 'ul');
    items.forEach(item => appendLinkItem(list, item));
    container.appendChild(list);
}

function showShowcaseSummaryTab() {
    const tab = document.getElementById('summary-tab');
    if (tab && typeof bootstrap !== 'undefined' && bootstrap.Tab) {
        bootstrap.Tab.getOrCreateInstance(tab).show();
    }
}

function renderSummaryContainer(summary, summary_container) {
    showShowcaseSummaryTab();
    summary_container.className += ' pk-holder';
    summary_container.setAttribute('data-pk', summary.id);

    const heading = document.createElement('h5');
    heading.textContent = summary.name;
    summary_container.appendChild(heading);

    if (summary.region) {
        const region = document.createElement('p');
        region.textContent = summary.region;
        summary_container.appendChild(region);
    }

    if (summary.description) {
        const description = document.createElement('p');
        description.className = 'text-break';
        description.style.whiteSpace = 'pre-line';
        description.textContent = summary.description;
        summary_container.appendChild(description);
    }

    appendListSection(summary_container, 'Input bioresources', summary.input_materials, false);
    appendListSection(summary_container, 'Processing chain', summary.involved_processes, true);
    appendListSection(summary_container, 'Intermediates', summary.intermediate_materials, false);
    appendListSection(summary_container, 'Products', summary.products, false);

    if (isSafeLocalUrl(summary.url)) {
        const detailsLink = document.createElement('a');
        detailsLink.href = summary.url;
        detailsLink.textContent = 'View showcase details';
        summary_container.appendChild(detailsLink);
    }
}

function renderSummaries(featureInfos) {
    const outer_summary_container = document.getElementById('summary-container');
    if (!outer_summary_container) {
        return;
    }
    outer_summary_container.textContent = '';

    if (!('summaries' in featureInfos)) {
        return;
    }

    const summaries = featureInfos.summaries;
    if (summaries.length === 0) {
        const message = document.createElement('p');
        message.textContent = 'No showcases found.';
        outer_summary_container.appendChild(message);
    } else if (summaries.length === 1) {
        renderSummaryContainer(summaries[0], outer_summary_container);
    } else {
        summaries.forEach((summary, index) => {
            const details = document.createElement('details');
            details.className = 'card mb-2';
            if (index === 0) {
                details.open = true;
            }
            const heading = document.createElement('summary');
            heading.className = 'card-header';
            heading.textContent = summary.name;
            details.appendChild(heading);
            const body = document.createElement('div');
            body.className = 'card-body';
            details.appendChild(body);
            renderSummaryContainer(summary, body);
            outer_summary_container.appendChild(details);
        });
    }

    document.querySelector('#info-card-body')?.classList.add('show');
}

// Click tolerance in screen pixels for point (circle marker) features, which
// render smaller than a comfortable click target.
const POINT_CLICK_TOLERANCE_PX = 10;

function featureClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

    const intersectingFeatures = new Map();
    const clickPoint = map.latLngToLayerPoint(e.latlng);

    featureGroup.eachLayer(layer => {
        let hit = false;
        if (layer instanceof L.Polygon) {
            const polygon = layer.toGeoJSON();
            const point = [e.latlng.lng, e.latlng.lat];
            hit = turf.inside(point, polygon);
        } else if (typeof layer.getLatLng === 'function') {
            const markerPoint = map.latLngToLayerPoint(layer.getLatLng());
            const dx = clickPoint.x - markerPoint.x;
            const dy = clickPoint.y - markerPoint.y;
            hit = Math.sqrt(dx * dx + dy * dy) <= POINT_CLICK_TOLERANCE_PX;
        }
        if (hit) {
            const showcaseId = layer.feature.id;
            if (!intersectingFeatures.has(showcaseId)) {
                intersectingFeatures.set(showcaseId, []);
            }
            intersectingFeatures.get(showcaseId).push(layer);
        }
    });

    // Store intersecting features globally to access in handleShowcaseClick
    window.intersectingFeatures = intersectingFeatures;
    window.featureGroup = featureGroup; // Store featureGroup globally

    // Check number of intersecting regions
    if (intersectingFeatures.size === 1) {
        // If only one region, fetch and render the summary for that feature only
        const layers = intersectingFeatures.values().next().value;
        layers.forEach(layer => selectFeature(layer));
        fetchFeaturesLayerSummary({ id: layers[0].feature.id });
    } else {
        // Select all overlapping features
        intersectingFeatures.forEach(layers => {
            layers.forEach(layer => selectFeature(layer));
        });

        // Generate popup content
        const popupContent = document.createElement('div');
        const regionGroups = new Map();
        intersectingFeatures.forEach(layers => {
            const regionName = layers[0].feature.properties.region;
            if (!regionGroups.has(regionName)) {
                regionGroups.set(regionName, []);
            }
            regionGroups.get(regionName).push(layers[0].feature);
        });

        regionGroups.forEach((features, regionName) => {
            const regionHeading = document.createElement('strong');
            regionHeading.textContent = regionName;
            popupContent.appendChild(regionHeading);
            popupContent.appendChild(document.createElement('br'));
            features.forEach(feature => {
                const link = document.createElement('a');
                link.href = '#';
                link.textContent = feature.properties.name;
                link.addEventListener('click', (event) => {
                    event.preventDefault();
                    handleShowcaseClick(feature.id);
                });
                popupContent.appendChild(link);
                popupContent.appendChild(document.createElement('br'));
            });
            // Add an empty line between region groups
            popupContent.appendChild(document.createElement('br'));
        });

        if (!popupContent.hasChildNodes()) {
            popupContent.textContent = 'No features found';
        }

        map.openPopup(popupContent, e.latlng, {offset: L.point(0, -24)}); // trim() to remove any trailing whitespace
    }
}

async function handleShowcaseClick(id) {
    resetFeatureStyles(window.featureGroup);
    const layers = window.intersectingFeatures.get(id) || [];
    layers.forEach(layer => selectFeature(layer));
    fetchFeaturesLayerSummary({ id: id });
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
    showShowcaseSummaryTab();
}
document.addEventListener("DOMContentLoaded", uncollapseInfoCardBody);
