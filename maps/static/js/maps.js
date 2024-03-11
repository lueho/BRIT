"use strict";

// load filter_utils.js before this if filters are used within the map functionality

/**
 * Reserved namespace for the configuration data of a map. Each view with a map should provide a dictionary with the
 * following structure in the context. In the template, the dictionary should parse it and create a variable mapConfig
 * before running this file.
 * @namespace mapConfig
 * @property mapConfig.loadRegion
 * @property mapConfig.regionUrl
 * @property mapConfig.regionId
 * @property mapConfig.regionLayerStyle
 * @property mapConfig.loadCatchment
 * @property mapConfig.catchmentId
 * @property mapConfig.catchmentUrl
 * @property mapConfig.catchmentLayerStyle
 * @property mapConfig.loadFeatures
 * @property mapConfig.featureUrl
 * @property mapConfig.applyFilterToFeatures
 * @property mapConfig.featureLayerStyle
 * @property mapConfig.featureSummaryUrl
 * @property mapConfig.adjustBoundsToFeatures
 */

/**
 * For rendering information about map features, the namespace featureInfos is reserved.
 * @namespace featureInfos
 * @property featureInfos.summaries
 */

let map;
let contentLayerGroup;
let regionLayer;
let catchmentLayer;
let featureLayer;
const paddedRenderer = L.canvas({padding: 0.5});


function showLoadingIndicator() {
    map.spin(true);
}

function hideLoadingIndicator() {
    map.spin(false);
}

function displayErrorMessage(error) {
    console.error(`An error occurred while fetching data: ${error}`);
}

function displayTimeoutError() {
    console.error("The request has timed out. Please try reducing the size of the dataset by setting more specific filter parameters.");
}

function prepareMapRefresh() {
    try {
        lockCustomElements();
    } catch (error) {
        console.warn('Custom elements were not locked', error);
    }
    try {
        lockFilter();
    } catch (error) {
        console.warn('Filter was not locked', error);
    }
    showLoadingIndicator();
    contentLayerGroup.clearLayers();
}

function refreshMap(promises, timeLimit = 120000) {
    let promiseIsPending = true;
    Promise.all(promises)
        .then(() => {
            promiseIsPending = false;
            orderLayers();
        })
        .catch(error => {
            promiseIsPending = false;
            displayErrorMessage(error);
        })
        .finally(cleanup);
    setTimeout(() => {
        if (promiseIsPending) {
            promiseIsPending = false;
            displayTimeoutError();
            cleanup();
        }
    }, timeLimit);
}

function updateUrlSearchParams() {
    const params = parseFilterParameters();
    const url = new URL(window.location);
    url.search = params.toString();
    window.history.replaceState({}, '', url.toString());
}

function cleanup() {
    try {
        updateUrlSearchParams();
    } catch (error) {
        console.warn('URL search parameters were not updated:', error);
    }
    hideLoadingIndicator();
    try {
        unlockFilter();
    } catch (error) {
        console.warn('Filter was not unlocked', error);
    }
    try {
        unlockCustomElements();
    } catch (error) {
        console.warn('Custom elements were not unlocked', error);
    }
}

function orderLayers() {
    map.invalidateSize();

    if (contentLayerGroup.hasLayer(catchmentLayer)) {
        contentLayerGroup.removeLayer(catchmentLayer);
        contentLayerGroup.addLayer(catchmentLayer);
    }

    if (regionLayer) {
        regionLayer.bringToFront();
    }
}

function getQueryParameters() {
    // This is a hook to overwrite if this file is run for any page not containing a standard filter form.
    console.info('getQueryParameters() is not overwritten. Using default implementation.');
    return parseFilterParameters();
}


function transformSearchParams(params) {
    if (params instanceof URLSearchParams) {
        return params;
    } else {
        const result = new URLSearchParams();
        for (const [key, value] of Object.entries(params)) {
            if (Array.isArray(value)) {
                value.forEach(value_item => result.append(key, value_item));
            } else {
                result.append(key, value.toString());
            }
        }
        return result;
    }
}

async function fetchRegionGeometry(params) {
    const url = mapConfig.regionUrl + '?' + transformSearchParams(params).toString();
    const response = await fetch(url);
    const json = await response.json();
    renderRegion(json.geoJson);
}

async function fetchCatchmentGeometry(params) {
    const url = mapConfig.catchmentUrl + '?' + transformSearchParams(params).toString();

    try {
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }

        const json = await response.json();

        if ('geoJson' in json) {
            renderCatchment(json.geoJson);
        }
    } catch (error) {
        console.error('Error fetching catchment geometry:', error);
        // You can also show an error message to the user, if appropriate.
    }
}

function convertToFeatureCollection(data) {
    // This function is necessary for compatibility with early versions of the API.
    // Once all endpoints for geometry data return a FeatureCollection, this function can be removed.

    if ('geoJson' in data) {
        data = {...data.geoJson, summaries: data.summaries || null};
    }

    if (data.type !== 'FeatureCollection') {
        data = {type: 'FeatureCollection', features: data.features, summaries: data.summaries};
    }

    return data;
}

async function fetchFeatureGeometries(params) {
    const url = new URL(window.location.origin + mapConfig.featureUrl);
    url.search = transformSearchParams(params).toString();
    const response = await fetch(url);
    const geoJson = await response.json();
    renderFeatures(convertToFeatureCollection(geoJson));
    if ('summaries' in geoJson) {
        renderSummaries(geoJson);
    }
}

async function fetchFeatureSummaries(feature) {
    let featureId;
    if (typeof (feature) === 'object') {
        try {
            featureId = feature.properties.id.toString();
        } catch (error) {
            console.warn('The provided feature does not contain an id property:', error);
            return;
        }
    } else {
        featureId = feature.toString();
    }
    const dataurl = mapConfig.featureSummaryUrl + '?' + 'id=' + featureId;
    const response = await fetch(dataurl);
    return await response.json();
}

function renderRegion(geoJson) {

    // Remove existing layer
    if (regionLayer !== undefined) {
        map.removeLayer(regionLayer);
    }

    // Render geodata on map
    regionLayer = L.geoJson(geoJson, {
        style: mapConfig.regionLayerStyle, interactive: false,
    });
    regionLayer.addTo(map);
    map.fitBounds(regionLayer.getBounds());
}

function renderCatchment(geoJson) {

    // Remove existing layer
    if (catchmentLayer !== undefined) {
        map.removeLayer(catchmentLayer);
    }

    const catchmentLayerStyle = mapConfig.catchmentLayerStyle;
    catchmentLayerStyle.renderer = paddedRenderer;

    // Render geodata on map
    catchmentLayer = L.geoJson(geoJson, {
        style: catchmentLayerStyle, interactive: false,
    });

    catchmentLayer.addTo(contentLayerGroup);
    map.fitBounds(catchmentLayer.getBounds());
}

function createFeatureLayerBindings(layer) {
    layer.on('click', async function(event) {
        await clickedFeature(event);
    });
}

function renderFeatures(geoJson) {

    if (!geoJson || !geoJson.features || geoJson.features.length === 0) {
        console.warn('The provided GeoJSON object is empty or does not contain any features.');
        return;
    }

    const featureLayerStyle = mapConfig.featureLayerStyle;
    featureLayerStyle.renderer = paddedRenderer;

    const geometryType = geoJson.features[0].geometry.type;
    if (geometryType === "Polygon" || geometryType === "MultiPolygon") {
        featureLayer = L.geoJson(geoJson, {
            style: featureLayerStyle
        });
    } else if (geometryType === "Point") {
        featureLayer = L.geoJson(geoJson, {
            pointToLayer: (feature, latlng) => {
                return L.circleMarker(latlng, featureLayerStyle);
            }
        });
    }

    createFeatureLayerBindings(featureLayer);
    featureLayer.addTo(contentLayerGroup);

    if (mapConfig.adjustBoundsToFeatures) {
        try {
            map.fitBounds(featureLayer.getBounds());
        } catch (error) {
            console.error(`An error occurred while adjusting the map bounds to the feature layer: ${error}`);
        }
    }
}


function isEmptyArray(el) {

    return Array.isArray(el) && el.length === 0;
}

function isValidHttpUrl(string) {
    let url;

    try {
        url = new URL(string);
    } catch (_) {
        return false;
    }

    return url.protocol === "http:" || url.protocol === "https:";
}

function renderSummaryContainer(summary, summary_container) {

    Object.keys(summary).forEach(key => {

        if (!isEmptyArray(summary[key]) && summary[key] !== null) {
            const summaryElement = document.createElement('div');
            const labelElement = document.createElement('P');
            const boldLabelElement = document.createElement('B');
            boldLabelElement.innerText = key;
            let value = summary[key];
            if (typeof summary[key] === 'object') {
                if ('label' in summary[key]) {
                    boldLabelElement.innerText = summary[key].label;
                }
                if ('value' in summary[key]) {
                    value = summary[key].value;
                }
            }
            boldLabelElement.innerText += ':';
            labelElement.appendChild(boldLabelElement);
            summaryElement.appendChild(labelElement);

            const summaryValueElement = document.createElement('P');
            if (Array.isArray(value)) {
                const ul = document.createElement('ul');
                summaryValueElement.appendChild(ul);
                value.forEach(function(item) {
                    const li = document.createElement('li');
                    if (isValidHttpUrl(item.toString())) {
                        const a = document.createElement('a');
                        a.href = item.toString();
                        a.innerText = item.toString();
                        a.setAttribute('target', '_blank');
                        li.appendChild(a);
                    } else {
                        li.innerText = item.toString();
                    }
                    ul.appendChild(li);
                });
            } else {
                summaryValueElement.innerText = value.toString();
            }
            summaryElement.appendChild(summaryValueElement);
            if (key === 'id') {
                summaryElement.className = 'd-none';
                summary_container.className += ' pk-holder';
                summary_container.setAttribute('data-pk', summary.id);
            }

            summary_container.appendChild(summaryElement);
        }
    });
}

function renderSummaries(featureInfos) {
    // Empty summary container from previous content
    const outer_summary_container = document.getElementById('summary-container');
    outer_summary_container.textContent = '';

    if ('summaries' in featureInfos) {
        if (featureInfos.summaries.length > 1) {

            // render multiple summaries
            const message = document.createElement('P');
            message.innerText = 'Found ' + featureInfos.summaries.length + ' items:';
            outer_summary_container.appendChild(message);

            const accordion = document.createElement('div');
            accordion.id = 'summaries_accordion';
            accordion.className = 'accordion';
            outer_summary_container.appendChild(accordion);

            featureInfos.summaries.forEach((summary, i) => {

                const card = document.createElement('div');
                card.className = 'card';
                accordion.appendChild(card);

                const header = document.createElement('div');
                header.className = 'card-header collapse-selector';
                header.setAttribute('role', 'button');
                header.setAttribute('data-toggle', 'collapse');
                header.setAttribute('href', '#collapse' + i.toString());
                header.setAttribute('aria-expanded', 'true');
                header.setAttribute('aria-controls', 'collapse' + i.toString());
                if (summary.id) {
                    header.setAttribute('data-pk', summary.id);
                }
                const numbering = i + 1;
                header.innerHTML = '<b>#' + numbering.toString() + '</b>';
                card.appendChild(header);

                const collapse_container = document.createElement('div');
                collapse_container.id = 'collapse' + i.toString();
                collapse_container.className = 'summary collapse';
                collapse_container.setAttribute('aria-labelledby', 'collapse' + i.toString());
                collapse_container.setAttribute('data-parent', '#summaries_accordion');
                card.appendChild(collapse_container);

                const body = document.createElement('div');
                body.className = 'card-body';

                collapse_container.appendChild(body);
                renderSummaryContainer(summary, body);
            });


        } else if (featureInfos.summaries.length === 1) {
            // render one single summary
            const summary = featureInfos.summaries[0];
            renderSummaryContainer(summary, outer_summary_container);
        }

        $('#info-card-body').collapse('show');
    }
}

function updateUrls(feature_id) {
    // This is a hook to overwrite if this file is run for any page not containing a standard filter form.
}

async function clickedFeature(event) {
    const summaries = await fetchFeatureSummaries(event.layer.feature);
    if (summaries) {
        renderSummaries(summaries);
        updateUrls(event.layer.feature.properties.id);
    }
}

function clickedFilterButton() {
    prepareMapRefresh();
    const params = parseFilterParameters();
    const promises = [fetchCatchmentGeometry(params), fetchFeatureGeometries(params)];
    refreshMap(promises);
}

function loadMap(mapConfig) {
    prepareMapRefresh();

    let params;
    try {
        if (mapConfig.applyFilterToFeatures) {
            params = parseFilterParameters();
        } else {
            params = getQueryParameters();
        }
    } catch (error) {
        console.warn('Filter parameters could not be parsed:', error);
    }

    const promises = [];
    if (mapConfig.loadRegion === true) {
        promises.push(fetchRegionGeometry({pk: mapConfig.regionId}));
    }
    if (params && params.has("catchment") && params.get("catchment") !== "") {
        promises.push(fetchCatchmentGeometry(params));
    } else if (mapConfig.loadCatchment === true && 'catchmentId' in mapConfig && mapConfig.catchmentId !== null) {
        promises.push(fetchCatchmentGeometry({catchment: mapConfig.catchmentId}));
    }
    if (mapConfig.loadFeatures === true) {
        promises.push(fetchFeatureGeometries(params));
    }
    refreshMap(promises);
}

window.addEventListener("map:init", function(event) {
    map = event.detail.map;
    contentLayerGroup = L.layerGroup().addTo(map);
});