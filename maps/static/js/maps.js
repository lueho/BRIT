"use strict";

/**
 * For rendering information about map features, the namespace featureInfos is reserved. The below structure follows
 * the for the json object that any related API should return.
 * @namespace featureInfos
 * @property featureInfos.summaries
 */

/**
 * Reserved namespace for the configuration data of a map. The below structure follows
 * the for the json object that any related API should return.
 * @namespace mapConfig
 * @property mapConfig.feature_summary_url
 * @property mapConfig.feature_url
 * @property mapConfig.region_url
 * @property mapConfig.region_id
 * @property mapConfig.catchment_url
 * @property mapConfig.load_catchment
 * @property mapConfig.catchment_id
 * @property mapConfig.markerStyle
 * @property mapConfig.adjust_bounds_to_features
 * @property mapConfig.load_region
 * @property mapConfig.load_features
 * @property mapConfig.form_fields
 */

let map;
window.addEventListener("map:init", function(event) {
    map = event.detail.map;
});

const myRenderer = L.canvas({padding: 0.5});
let region_layer;
let catchment_layer;
let feature_layer;

const region_layer_style = {
    "color": "#A1221C",
    "fillOpacity": 0.0
};

const catchment_layer_style = {
    "color": "#04555E"
};

const feature_layer_style = {
    "color": "#04555E"
};

function loadMap(mapConfig) {
    const promises = [];
    if (mapConfig.load_region === true) {
        const params = {pk: mapConfig.region_id};
        promises.push(fetchRegionGeometry(params));
    }
    if (mapConfig.load_catchment === true) {
        const params = {catchment: mapConfig.catchment_id};
        promises.push(fetchCatchmentGeometry(params));
    }
    if (mapConfig.load_features === true) {
        const params = parseFilterParameters();
        promises.push(fetchFeatureGeometries(params));
        // filterFeatures();
    }
    Promise.all(promises).then(() => {orderLayers();});

}

async function updateLayers({region_params, catchment_params, feature_params} = {}) {
    const promises = [];
    if (region_params) {
        promises.push(fetchRegionGeometry(region_params));
    }
    if (catchment_params) {
        promises.push(fetchCatchmentGeometry(catchment_params));
    }
    if (feature_params) {
        promises.push(fetchFeatureGeometries(feature_params));
    }
    Promise.all(promises).then(() => {orderLayers();});
}

function orderLayers() {
    map.invalidateSize();
    if (catchment_layer) {
        catchment_layer.bringToBack();
    }
    if (feature_layer) {
        feature_layer.bringToBack();
    }
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
    const url = mapConfig.region_url + '?' + transformSearchParams(params).toString();
    const response = await fetch(url);
    const json = await response.json();
    renderRegion(json.geoJson);
}

async function fetchCatchmentGeometry(params) {
    const url = mapConfig.catchment_url + '?' + transformSearchParams(params).toString();
    const response = await fetch(url);
    const json = await response.json();
    renderCatchment(json.geoJson);
}

async function fetchFeatureGeometries(params) {
    const url = mapConfig.feature_url + '?' + transformSearchParams(params).toString();
    const response = await fetch(url);
    const json = await response.json();
    renderFeatures(json.geoJson);
    if ('summaries' in json) {
        renderSummaries(json);
    }
}

async function fetchFeatureSummaries(feature) {

    let feature_id;
    if (typeof (feature) === 'object') {
        feature_id = feature.properties.id.toString();
    } else {
        feature_id = feature.toString();
    }

    const dataurl = mapConfig.feature_summary_url + '?' + 'pk=' + feature_id;
    const response = await fetch(dataurl);
    return await response.json();
}

function renderRegion(geoJson) {

    // Remove existing layer
    if (region_layer !== undefined) {
        map.removeLayer(region_layer);
    }

    // Render geodata on map
    region_layer = L.geoJson(geoJson, {
        style: region_layer_style,
        interactive: false
    });
    region_layer.addTo(map);
    map.fitBounds(region_layer.getBounds());
}

function renderCatchment(geoJson) {

    // Remove existing layer
    if (catchment_layer !== undefined) {
        map.removeLayer(catchment_layer);
    }

    // Render geodata on map
    catchment_layer = L.geoJson(geoJson, {
        style: catchment_layer_style,
        interactive: false
    });
    catchment_layer.addTo(map);
    map.fitBounds(catchment_layer.getBounds());
}

function renderFeatures(geoJson) {

    // Remove existing layer
    if (feature_layer !== undefined) {
        map.removeLayer(feature_layer);
    }

    const markerStyle = mapConfig.markerStyle;
    markerStyle.renderer = myRenderer;

    feature_layer = L.geoJson(geoJson, {
        pointToLayer: function(feature, latlng) {
            return L.circleMarker(latlng, markerStyle);
        },
        onEachFeature: function onEachFeature(feature, layer) {
        }
    }).addTo(map);

    feature_layer.on('click', async function(event) {
        await clickedFeature(event);
    });

    if (mapConfig.adjust_bounds_to_features === true) {
        try {
            map.fitBounds(feature_layer.getBounds());
        } catch (ex) {

        }
    }
}

try {
    document.querySelector("#summary-container").addEventListener('click', function(e) {
        if (e.target.matches('.collapse-selector')) {
            updateUrls(e.target.dataset.pk);
        }
    });
} catch (e) {
}

function clickedFilterButton() {
    const btn = document.getElementById('filter-button');
    btn.disabled = true;
    const params = parseFilterParameters();
    fetchFeatureGeometries(params).then(btn.disabled = false);
}

async function clickedFeature(event) {
    const summaries = await fetchFeatureSummaries(event.layer.feature);
    renderSummaries(summaries);
    updateUrls(event.layer.feature.properties.id);
}

function parseFilterParameters() {
    const params = new URLSearchParams();
    if ('form_fields' in mapConfig) {
        const form_fields = mapConfig.form_fields;
        Object.keys(form_fields).forEach(key => {
            switch (form_fields[key]) {
            case 'SelectMultiple':
                readSelectMultiple(key).forEach((value) => {params.append(key, value);});
                break;
            case 'RadioSelect':
                params.append(key, readRadioSelect(key));
                break;
            case 'CheckboxSelectMultiple':
                readCheckboxSelectMultiple(key).forEach((value) => {params.append(key, value);});
                break;
            case 'RangeSlider':
                const [min, max] = readRangeSlider(key);
                params.append(key + '_min', min);
                params.append(key + '_max', max);
                break;
            default:
                params.append(key, document.getElementsByName(key)[0].value);
            }
        });
    }
    return params;
}

function readSelectMultiple(name) {
    const country_codes = [];
    const inputs = document.getElementsByName(name)[0];
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].selected === true) {
            country_codes.push(inputs[i].value);
        }
    }
    return country_codes;
}

function readCheckboxSelectMultiple(name) {
    const ids = [];
    const inputs = document.getElementsByName(name);
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].checked === true) {
            ids.push(inputs[i].value);
        }
    }
    return ids;
}

function readRadioSelect(name) {
    const heatingButtons = document.getElementsByName(name);
    let heating;
    for (let i = 0; i < heatingButtons.length; i++) {
        if (heatingButtons[i].checked === true) {
            heating = heatingButtons[i].value;
        }
    }
    return heating;
}

function readRangeSlider(name) {
    const min = document.getElementById('id_' + name + '_min').value;
    const max = document.getElementById('id_' + name + '_max').value;
    return [min, max];
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
