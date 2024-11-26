"use strict";

// load filter_utils.js before this if filters are used within the map functionality

/**
 * Reserved namespace for the configuration data of a map. Each view with a map should provide a dictionary with the
 * following structure in the context. In the template, the dictionary should parse it and create a variable mapConfig
 * before running this file.
 * @namespace mapConfig
 * @property mapConfig.loadRegion // Can be used to prevent excessive traffic on first page load
 * @property mapConfig.regionLayerGeometriesUrl // Endpoint for fetching region geometries. Append query parameters as needed.
 * @property mapConfig.regionLayerDetailsUrlTemplate // Endpoint for fetching feature details. Append feature id before using.
 * @property mapConfig.regionId // If set, specific region is loaded
 * @property mapConfig.regionLayerStyle // Dictionary with Leaflet compatible style settings
 * @property mapConfig.loadCatchment // Can be used to prevent excessive traffic on first page load
 * @property mapConfig.catchmentId // If set, specific catchment is loaded
 * @property mapConfig.catchmentLayerGeometriesUrl // Endpoint for fetching catchment geometries. Append query parameters as needed.
 * @property mapConfig.catchmentLayerDetailsUrlTemplate // Endpoint for fetching feature details. Append feature id before using.
 * @property mapConfig.catchmentLayerStyle // Dictionary with Leaflet compatible style settings
 * @property mapConfig.loadFeatures // Can be used to prevent excessive traffic on first page load
 * @property mapConfig.featuresId // If set, specific feature is loaded
 * @property mapConfig.featuresLayerGeometriesUrl // Endpoint for fetching feature geometries. Append query parameters as needed.
 * @property mapConfig.featuresLayerDetailsUrlTemplate // Endpoint for fetching feature details. Append feature id before using.
 * @property mapConfig.featuresLayerSummariesUrl // Endpoint for fetching feature summaries. Append query parameters as needed.
 * @property mapConfig.featuresLayerStyle // Dictionary with Leaflet compatible style settings
 * @property mapConfig.loadFeaturesLayerSummary // If true, summary of all features are loaded on first page load.
 * @property mapConfig.applyFilterToFeatures // true: filter is parsed / false: query parameters from URL are used
 * @property mapConfig.adjustBoundsToLayer // Possible values: 'region', 'catchment', 'features'
 * @property mapConfig.layerOrder // Array defining the order of layers from bottom to top
 */

/**
 * For rendering information about map features, the namespace featureInfos is reserved.
 * @namespace featureInfos
 * @property featureInfos.summaries
 */

let map;
let regionLayer;
let catchmentLayer;
let featuresLayer;
let regionLayerStyle;
let catchmentLayerStyle;
let featuresLayerStyle;
const defaultLayerOrder = ['region', 'catchment', 'features'];


function showLoadingIndicator() {
    map.spin(true);
}

function hideLoadingIndicator() {
    map.spin(false);
}

function showMapOverlay() {
    try {
        const overlay = document.getElementById('map-overlay');
        overlay.style.display = 'flex';
    } catch (error) {
        console.warn('Map overlay could not be shown:', error);
    }
}

function hideMapOverlay() {
    try {
        const overlay = document.getElementById('map-overlay');
        overlay.style.display = 'none';
    } catch (error) {
        console.warn('Map overlay could not be hidden:', error);
    }
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
}

function clearMap() {
    map.eachLayer(layer => {
        if (layer instanceof L.GeoJSON) {
            map.removeLayer(layer);
        }
    });
}

function refreshMap(promises, timeLimit = 120000) {
    let promiseIsPending = true;
    Promise.all(promises)
        .then(() => {
            promiseIsPending = false;
            orderLayers();
            adjustMapBounds();
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

function orderLayers(layerOrder = mapConfig.layerOrder || defaultLayerOrder) {
    if (!Array.isArray(layerOrder)) {
        console.error('Invalid layerOrder. Expected an array.');
        return;
    }

    const validKeys = ['region', 'catchment', 'features']; // Define valid layer keys
    const invalidKeys = layerOrder.filter(key => !validKeys.includes(key));
    if (invalidKeys.length > 0) {
        console.warn(`Unknown layer keys found: ${invalidKeys.join(', ')}`);
    }

    const validLayerOrder = layerOrder.filter(key => validKeys.includes(key));

    validLayerOrder.forEach((key, index) => {
        if (key === 'region') {
            regionLayer?.bringToFront();
        } else if (key === 'catchment') {
            catchmentLayer?.bringToFront();
        } else if (key === 'features') {
            featuresLayer?.bringToFront();
        }
    });
}


function setLayerOrder(layerOrder) {

    // If layerOrder is not a valid array, reset to default
    if (!Array.isArray(layerOrder) || layerOrder.length === 0) {
        console.warn('Invalid or empty layerOrder. Resetting to default.');
        mapConfig.layerOrder = defaultLayerOrder;
        return;
    }

    const validKeys = ['region', 'catchment', 'features'];
    const filteredLayerOrder = layerOrder.filter(key => validKeys.includes(key));

    if (filteredLayerOrder.length === 0) {
        console.warn('No valid keys in layerOrder. Resetting to default.');
        mapConfig.layerOrder = defaultLayerOrder;
        return;
    }

    mapConfig.layerOrder = filteredLayerOrder;
}

function getQueryParameters() {
    // This is a hook to overwrite if this file is run for any page not containing a standard filter form.
    // Must return a URLSearchParams object.
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

async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching data from ${url}:`, error);
        throw error;
    }
}

function validateParams(params, requiredKeys) {
    for (const key of requiredKeys) {
        if (!params || !(key in params)) {
            throw new Error(`Missing required parameter: ${key}`);
        }
    }
}

function buildUrl(base, params) {
    const url = new URL(base, window.location.origin);
    url.search = transformSearchParams(params).toString();
    return url.toString();
}

async function fetchRegionGeometry(params) {
    validateParams(params, ['id']);
    const url = buildUrl(mapConfig.regionLayerGeometriesUrl, {id: params.id});
    const geoJson = await fetchData(url);
    renderRegion(geoJson);
}

async function fetchCatchmentGeometry(params) {
    validateParams(params, ['id']);
    const url = buildUrl(mapConfig.catchmentLayerGeometriesUrl, {id: params.id});
    const geoJson = await fetchData(url);
    renderCatchment(geoJson);
}

async function fetchFeatureGeometries(params) {
    hideMapOverlay();
    const finalParams = mapConfig.featuresId ? {id: mapConfig.featuresId} : params;
    const url = buildUrl(mapConfig.featuresLayerGeometriesUrl, finalParams);
    const geoJson = await fetchData(url);
    renderFeatures(geoJson);
}

/**
 * Asynchronously fetches feature summaries from a server.
 *
 * @async
 * @function fetchFeatureDetails
 * @param {(Object|string)} feature - The feature for which to fetch summaries.
 * If an object is provided, it should have an 'id' property or a 'properties.id' property.
 * If a string is provided, it should represent the feature id.
 * @returns {Promise<Object>} A promise that resolves to the JSON response from the server.
 * @throws Will log a warning if the provided feature id is not a valid integer number.
 */
async function fetchFeatureDetails(feature) {
    let featureId = typeof feature === 'object' ? feature.id || feature.properties.id : feature;
    featureId = featureId.toString();

    if (Number.isInteger(parseInt(featureId))) {
        const dataurl = `${mapConfig.featuresLayerDetailsUrlTemplate}${featureId}/`;
        const response = await fetch(dataurl);
        const json = await response.json();
        return json;
    } else {
        console.warn('The provided feature id is not a valid integer number:', featureId);
    }
}

async function fetchFeaturesLayerSummary(params) {
    const url = mapConfig.featuresLayerSummariesUrl + '?' + transformSearchParams(params).toString();
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }

        const summaries = await response.json();
        renderSummaries(summaries);

    } catch (error) {
        console.error('Error fetching layer summary:', error);
    }
}

function removeExistingLayer(layer) {
    if (layer) {
        map.removeLayer(layer);
    }
}

function initializeRenderers() {
    const paddedRenderer = L.canvas({padding: 0.5});

    regionLayerStyle = mapConfig.regionLayerStyle;
    regionLayerStyle.renderer = paddedRenderer;

    catchmentLayerStyle = mapConfig.catchmentLayerStyle;
    catchmentLayerStyle.renderer = paddedRenderer;

    featuresLayerStyle = mapConfig.featuresLayerStyle;
    featuresLayerStyle.renderer = paddedRenderer;
}


function renderRegion(geoJson) {

    removeExistingLayer(regionLayer);

    // Render geodata on map
    regionLayer = L.geoJson(geoJson, {
        style: regionLayerStyle,
        interactive: false,
        pane: 'regionPane',
    });

    regionLayer.addTo(map);
}


function renderCatchment(geoJson) {

    removeExistingLayer(catchmentLayer);


    // Render geodata on map
    catchmentLayer = L.geoJson(geoJson, {
        style: catchmentLayerStyle,
        interactive: false,
        pane: 'catchmentPane',
    });

    catchmentLayer.addTo(map);
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

    removeExistingLayer(featuresLayer);

    const geometryType = geoJson.features[0].geometry.type;
    if (geometryType === "Polygon" || geometryType === "MultiPolygon") {
        featuresLayer = L.geoJson(geoJson, {
            style: featuresLayerStyle,
            pane: 'featuresPane',
        });
    } else if (geometryType === "Point") {
        featuresLayer = L.geoJson(geoJson, {
            pointToLayer: (feature, latlng) => L.circleMarker(latlng, featuresLayerStyle),
            pane: 'featuresPane',
        });
    }

    createFeatureLayerBindings(featuresLayer);
    featuresLayer.addTo(map);
}

function adjustMapBounds() {
    const layerPriorities = [
        {key: 'region', layer: regionLayer},
        {key: 'catchment', layer: catchmentLayer},
        {key: 'features', layer: featuresLayer}
    ];

    const preferredIndex = layerPriorities.findIndex(item => item.key === mapConfig.adjustBoundsToLayer);
    if (preferredIndex === -1) {
        console.warn(`Invalid preferred layer: ${mapConfig.adjustBoundsToLayer}`);
        return false;
    }

    const orderedPriorities = [
        ...layerPriorities.slice(preferredIndex),
        ...layerPriorities.slice(0, preferredIndex)
    ];

    for (const {key, layer} of orderedPriorities) {
        if (layer && layer.getBounds) {
            try {
                const bounds = layer.getBounds();
                if (bounds.isValid()) {
                    map.fitBounds(bounds);
                    return true;
                }
            } catch (error) {
                console.warn(`Failed to adjust bounds to ${key} layer:`, error);
            }
        }
    }

    console.warn('No valid layers found for bounds adjustment');
    return false;
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

function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

function renderSummaryContainer(summary, summary_container) {

    Object.keys(summary).forEach(key => {

        if (!isEmptyArray(summary[key]) && summary[key] !== null) {
            const summaryElement = document.createElement('div');
            const labelElement = document.createElement('P');
            const boldLabelElement = document.createElement('B');
            boldLabelElement.innerText = capitalizeFirstLetter(key);
            let value = summary[key];
            if (typeof summary[key] === 'object') {
                if ('label' in summary[key]) {
                    boldLabelElement.innerText = capitalizeFirstLetter(summary[key].label);
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

        document.querySelector('#info-card-body').classList.add('show');
    }
}

async function getFeatureDetails(fid) {
    try {
        const details = await fetchFeatureDetails(fid);
        renderFeatureDetails(details);
        scrollToSummaries();
        updateUrls(fid);
    } catch (error) {
        console.error(`Error fetching feature details for id ${fid}: ${error}`);
    }
}

function formatHeader(key) {
    return key
        .replace(/([A-Z])/g, ' $1')
        .replace(/_/g, ' ')
        .replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase())
        .trim();
}

function formatList(value, separator) {
    if (!value) {
        return '';
    }
    const items = value.split(separator).filter(item => item.trim());
    if (items.length === 0) {
        return '';
    }

    return `<ul class="list-disc pl-4">
        ${items.map(item => `<li>${item.trim()}</li>`).join('')}
    </ul>`;
}

function truncateUrl(url, maxLength = 40) {
    return url.length > maxLength ? url.substring(0, maxLength) + '...' : url;
}

function formatUrls(urlString) {
    if (!urlString) {
        return '';
    }
    const urls = urlString.split(', ').filter(Boolean);
    if (urls.length === 0) {
        return '';
    }

    return urls
        .map(url => `<li>
            <a href="${url}" 
               title="${url}"
               target="_blank" 
               rel="noopener noreferrer"
               class="url-link hover:text-blue-600">
                ${truncateUrl(url)}
            </a>
        </li>`)
        .join('');
}

function renderFeatureDetails(data) {
    const container = document.getElementById('summary-container');

    container.innerHTML = '';

    const fragment = document.createDocumentFragment();

    Object.entries(data)
        .filter(([key]) => fieldConfig[key]?.include)
        .forEach(([key, value]) => {
            const formatted = fieldConfig[key].format(value);
            if (formatted) {
                const header = formatHeader(key);

                const p = document.createElement('p');

                const strong = document.createElement('strong');
                strong.textContent = `${header}:`;

                p.appendChild(strong);
                p.appendChild(document.createElement('br'));
                p.innerHTML += formatted;

                fragment.appendChild(p);
            }
        });

    container.appendChild(fragment);
    document.querySelector('#info-card-body').classList.add('show');

}

function scrollToSummaries() {
    // This is a hook for implementing behaviour when a feature details are rendered.
}

function updateUrls(feature_id) {
    // This is a hook to overwrite if this file is run for any page not containing a standard filter form.
}

async function clickedFeature(event) {
    // This is a hook for implementing behaviour when a feature is clicked.
}

function clickedFilterButton() {
    prepareMapRefresh();
    let params;
    try {
        params = parseFilterParameters();
    } catch (error) {
        console.warn('Filter parameters could not be parsed:', error);
    }
    mapConfig.loadFeatures = true;
    loadLayers(params);
}

function adaptMapConfig() {
    // This is a hook to adapt the mapConfig object before loading the map.
}

function loadMap(mapConfig) {
    if (!mapConfig) {
        console.error('mapConfig is not defined or invalid.');
        return;
    }

    adaptMapConfig();
    initializeRenderers();
    prepareMapRefresh();

    try {
        loadLayers();
    } catch (error) {
        console.error('Failed to load layers:', error);
    }
}

function getFeaturesLayerFilterParameters() {
    let params;
    try {
        params = mapConfig.applyFilterToFeatures
            ? parseFilterParameters()
            : getQueryParameters();
        if (!params) {
            console.warn('Parameters are undefined. Using default configuration.');
            return new URLSearchParams();
        }
        return params;
    } catch (error) {
        console.warn('Filter parameters could not be parsed:', error);
        return new URLSearchParams();
    }
}

function loadLayers() {
    const filterParameters = getFeaturesLayerFilterParameters();
    const promises = [];

    const region_id = filterParameters.get('region') || (mapConfig.loadRegion ? mapConfig.regionId : null);
    if (region_id) {
        promises.push(fetchRegionGeometry({id: region_id}));
    }

    const catchment_id = filterParameters.get('catchment') || (mapConfig.loadCatchment ? mapConfig.catchmentId : null);
    if (catchment_id) {
        promises.push(fetchCatchmentGeometry({id: catchment_id}));
    }

    if (mapConfig.loadFeatures === true) {
        promises.push(fetchFeatureGeometries(filterParameters));
        promises.push(fetchFeaturesLayerSummary(filterParameters));
    } else {
        try {
            showMapOverlay();
        } catch (error) {
            console.warn('Map overlay could not be shown:', error);
        }
    }

    if (promises.length > 0) {
        Promise.all(promises)
            .then(() => {
                return refreshMap(promises);
            })
            .catch(error => console.error('Error loading layers or refreshing map:', error));
    } else {
        console.warn('No layers to load.');
    }
}

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

window.addEventListener("map:init", function(event) {
    map = event.detail.map;
});