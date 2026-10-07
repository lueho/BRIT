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

function appendContextParagraph(container, text, className = '') {
    if (typeof text !== 'string' || !text.trim()) return;
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    paragraph.className = className;
    paragraph.style.whiteSpace = 'pre-line';
    container.appendChild(paragraph);
}

function appendThemeContext(container, theme) {
    if (!theme || typeof theme.label !== 'string') return;
    const heading = document.createElement('p');
    heading.className = 'fw-semibold mb-1';
    if (isSafeLocalUrl(theme.url)) {
        const link = document.createElement('a');
        link.href = theme.url;
        link.textContent = `Theme: ${theme.label}`;
        heading.appendChild(link);
    } else {
        heading.textContent = `Theme: ${theme.label}`;
    }
    container.appendChild(heading);
    appendContextParagraph(container, theme.description, 'small text-muted');
}

function renderPilotRegions(regions) {
    const container = document.getElementById('pilot-region-context');
    if (!container) return;
    container.textContent = '';
    const pilots = new Map();
    (regions || []).forEach(region => {
        if (region && region.id !== undefined) pilots.set(region.id, region);
    });
    container.hidden = pilots.size === 0;
    pilots.forEach(pilot => {
        const section = document.createElement('section');
        section.className = 'border rounded p-3 mb-3';
        const heading = document.createElement('h5');
        heading.textContent = 'Pilot region / TBN';
        section.appendChild(heading);
        const name = document.createElement('p');
        name.className = 'fw-semibold';
        if (isSafeLocalUrl(pilot.url)) {
            const link = document.createElement('a');
            link.href = pilot.url;
            link.textContent = pilot.name;
            name.appendChild(link);
        } else {
            name.textContent = pilot.name;
        }
        section.appendChild(name);
        appendContextParagraph(section, pilot.role, 'small');
        appendContextParagraph(section, pilot.description);
        appendContextParagraph(section, pilot.boundary_note, 'small text-muted');
        if (isSafeLocalUrl(pilot.showcases_url)) {
            const link = document.createElement('a');
            link.href = pilot.showcases_url;
            link.textContent = 'Explore regional showcases';
            section.appendChild(link);
        }
        container.appendChild(section);
    });
    if (pilots.size) showShowcaseSummaryTab();
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
    appendThemeContext(summary_container, summary.theme);

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
    renderPilotRegions(summaries.map(summary => summary.pilot_region));
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

    if (summaries.length === 1) markListSelection(summaries[0].id);
    document.querySelector('#info-card-body')?.classList.add('show');
}

// Zoom level at which a showcase picked from the list is shown.
const SHOWCASE_LIST_ZOOM = 9;

function markListSelection(id) {
    document.querySelectorAll('#showcase-list [data-showcase-id]').forEach(button => {
        if (Number(button.dataset.showcaseId) === id) {
            button.setAttribute('aria-current', 'true');
        } else {
            button.removeAttribute('aria-current');
        }
    });
}

function selectShowcaseFromList(id) {
    if (typeof featuresLayer !== 'undefined' && featuresLayer) {
        resetFeatureStyles(featuresLayer);
        const markers = [];
        featuresLayer.eachLayer(layer => {
            if (isMarkerLayer(layer) && layer.feature?.id === id) markers.push(layer);
        });
        markers.forEach(layer => selectFeature(layer));
        if (markers.length) {
            map.setView(markers[0].getLatLng(), Math.max(map.getZoom(), SHOWCASE_LIST_ZOOM));
        }
    }
    markListSelection(id);
    fetchFeaturesLayerSummary({ id });
}

function initShowcaseList() {
    document.getElementById('showcase-list')?.addEventListener('click', event => {
        const button = event.target.closest('[data-showcase-id]');
        if (!button) return;
        event.preventDefault();
        selectShowcaseFromList(Number(button.dataset.showcaseId));
    });
}
document.addEventListener('DOMContentLoaded', initShowcaseList);

function bindShowcaseFeature(feature, layer) {
    bindFeaturePopup(feature, layer);
    const code = feature.properties?.code;
    if (feature.properties?.feature_type === 'showcase' && code && typeof layer.bindTooltip === 'function') {
        layer.bindTooltip(String(code), {
            permanent: true,
            direction: 'right',
            offset: [6, 0],
            className: 'csm-code-label',
        });
    }
    if (layer instanceof L.Polygon && typeof layer.on === 'function') {
        layer.on('add', () => layer.bringToBack());
    }
}

function showcaseFeatureStyle(feature) {
    const theme = feature.properties?.theme;
    if (!theme || !/^#[0-9a-f]{6}$/i.test(theme.color)) return { ...featuresLayerStyle };
    return {
        ...featuresLayerStyle,
        color: theme.color,
        fillColor: theme.color,
        fillOpacity: feature.properties.feature_type === 'pilot_region' ? 0.15 : 0.9,
    };
}

function createFeaturesLayer(geoJson, geometryType) {
    return L.geoJson(geoJson, {
        pane: 'featuresPane',
        onEachFeature: bindShowcaseFeature,
        style: showcaseFeatureStyle,
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, showcaseFeatureStyle(feature)),
    });
}

function resetFeatureStyles(featureGroup) {
    featureGroup.resetStyle();
    featureGroup.eachLayer(layer => {
        if (layer instanceof L.Polygon && typeof layer.bringToBack === 'function') {
            layer.bringToBack();
        }
    });
}

function selectFeature(layer) {
    layer.setStyle({ "color": "#f49a33" });
    if (!(layer instanceof L.Polygon) && typeof layer.bringToFront === 'function') {
        layer.bringToFront();
    }
}

function isMarkerLayer(layer) {
    return typeof layer.getLatLng === 'function' && !(layer instanceof L.Polygon);
}

// Click tolerance in screen pixels for point (circle marker) features, which
// render smaller than a comfortable click target.
const POINT_CLICK_TOLERANCE_PX = 10;

function featureClickHandler(e, featureGroup) {
    resetFeatureStyles(featureGroup);

    const intersectingFeatures = new Map();
    const showcaseMeta = new Map();
    const clickPoint = map.latLngToLayerPoint(e.latlng);
    const markerLayers = new Map();
    const polygonLayers = [];

    featureGroup.eachLayer(layer => {
        if (layer instanceof L.Polygon) {
            polygonLayers.push(layer);
        } else if (isMarkerLayer(layer)) {
            const showcaseId = layer.feature.id;
            if (!markerLayers.has(showcaseId)) {
                markerLayers.set(showcaseId, []);
            }
            markerLayers.get(showcaseId).push(layer);
        }
    });

    const addShowcase = (id, name, region, layers) => {
        if (!intersectingFeatures.has(id)) {
            intersectingFeatures.set(id, []);
            showcaseMeta.set(id, { name, region });
        }
        const existing = intersectingFeatures.get(id);
        layers.forEach(layer => {
            if (!existing.includes(layer)) {
                existing.push(layer);
            }
        });
    };

    const markerHit = layer => {
        const markerPoint = map.latLngToLayerPoint(layer.getLatLng());
        const dx = clickPoint.x - markerPoint.x;
        const dy = clickPoint.y - markerPoint.y;
        return Math.sqrt(dx * dx + dy * dy) <= POINT_CLICK_TOLERANCE_PX;
    };

    const addHitMarkers = () => {
        markerLayers.forEach((layers, showcaseId) => {
            const hits = layers.filter(markerHit);
            if (hits.length > 0) {
                const properties = layers[0].feature.properties || {};
                addShowcase(showcaseId, properties.name, properties.region, hits);
            }
        });
    };

    const addPilotPolygon = layer => {
        const properties = layer.feature.properties || {};
        const showcases = properties.showcases;
        if (properties.feature_type === 'pilot_region' || Array.isArray(showcases)) {
            (showcases || []).forEach(entry => {
                if (entry && Number.isInteger(entry.id)) {
                    addShowcase(
                        entry.id,
                        entry.name,
                        entry.region || properties.region,
                        [layer, ...(markerLayers.get(entry.id) || [])]
                    );
                }
            });
        } else {
            addShowcase(layer.feature.id, properties.name, properties.region, [layer]);
        }
    };

    const clickedLayer = e.layer;
    if (clickedLayer && isMarkerLayer(clickedLayer)) {
        addHitMarkers();
    } else {
        const clickGeoPoint = [e.latlng.lng, e.latlng.lat];
        polygonLayers.forEach(layer => {
            if (turf.inside(clickGeoPoint, layer.toGeoJSON())) {
                addPilotPolygon(layer);
            }
        });
        if (!(clickedLayer instanceof L.Polygon)) {
            addHitMarkers();
        }
    }

    const selectedPilots = polygonLayers.filter(layer => {
        const members = layer.feature.properties?.showcases || [];
        return members.some(member => intersectingFeatures.has(member.id));
    });
    renderPilotRegions(selectedPilots.map(layer => layer.feature.properties.pilot_region));

    // Store intersecting features globally to access in handleShowcaseClick
    window.intersectingFeatures = intersectingFeatures;
    window.featureGroup = featureGroup; // Store featureGroup globally

    // Check number of intersecting regions
    if (intersectingFeatures.size === 1) {
        // If only one region, fetch and render the summary for that feature only
        const layers = intersectingFeatures.values().next().value;
        layers.forEach(layer => selectFeature(layer));
        fetchFeaturesLayerSummary({ id: intersectingFeatures.keys().next().value });
    } else {
        // Select all overlapping features
        intersectingFeatures.forEach(layers => {
            layers.forEach(layer => selectFeature(layer));
        });

        // Generate popup content
        const popupContent = document.createElement('div');
        const regionGroups = new Map();
        intersectingFeatures.forEach((layers, showcaseId) => {
            const meta = showcaseMeta.get(showcaseId) || {};
            const regionName = meta.region || 'No region';
            if (!regionGroups.has(regionName)) {
                regionGroups.set(regionName, []);
            }
            regionGroups.get(regionName).push({ id: showcaseId, name: meta.name });
        });

        regionGroups.forEach((features, regionName) => {
            const regionHeading = document.createElement('strong');
            regionHeading.textContent = regionName;
            popupContent.appendChild(regionHeading);
            popupContent.appendChild(document.createElement('br'));
            features.forEach(feature => {
                const link = document.createElement('a');
                link.href = '#';
                link.textContent = feature.name;
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
