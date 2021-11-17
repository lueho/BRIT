let map;
let myRenderer = L.canvas({padding: 0.5});
let feature_layer;
let region_layer;

window.addEventListener("map:init", function (event) {
    map = event.detail.map;
});

async function fetchFeatureGeometries(params, mapConfig) {

    let dataurl = mapConfig['feature_url'] + '?' + $.param(params);

    // Remove existing layer
    if (feature_layer !== undefined) {
        map.removeLayer(feature_layer);
    }

    // Fetch data from REST API
    let response = await fetch(dataurl);
    let data = await response.json();

    let markerStyle = mapConfig['markerStyle']
    markerStyle['renderer'] = myRenderer

    // Render geodata on map
    let geodata = data['geoJson'];
    feature_layer = L.geoJson(geodata, {
        pointToLayer: function (feature, latlng) {
            return L.circleMarker(latlng, markerStyle)
        },
        onEachFeature: function onEachFeature(feature, layer) {
        }
    }).addTo(map);

    if (mapConfig['adjust_bounds_to_features'] === true) {
        map.fitBounds(feature_layer.getBounds())
    }
    return data;
}

async function fetchRegionGeometry(region_url, region_id) {

    // Define query string for REST API
    let params = L.Util.extend({
        region_id: region_id
    });

    let url = region_url + L.Util.getParamString(params);

    // Remove existing layer
    if (region_layer !== undefined) {
        map.removeLayer(region_layer);
    }

    // Fetch data from REST API
    let response = await fetch(url);
    let data = await response.json();

    // Render geodata on map
    let geodata;
    geodata = data['geoJson'];
    region_layer = L.geoJson(geodata, {
        style: region_layer_style
    })
    region_layer.addTo(map);
    map.fitBounds(region_layer.getBounds())

    return data
}

async function filterFeatures() {
    const params = parseFilterParameters();
    let data = await fetchFeatureGeometries(params, mapConfig);
    if ('info' in data) {
        await renderInfo(data['info'])
    }
    if ('analysis' in data) {
        await renderSummary(data['analysis'])
    }
}

function loadMap(config) {
    if (config['load_region'] === true) {
        fetchRegionGeometry(config['region_url'], config['region_id']);
    }
    if (config['load_features'] === true) {
        filterFeatures();
    }
    map.invalidateSize();
}

function parseFilterParameters() {
    const form_fields = mapConfig['form_fields']
    let params = {}
    Object.keys(form_fields).forEach(key => {
        switch (form_fields[key]) {
            case 'SelectMultiple':
                params[key] = readSelectMultiple(key);
                break;
            case 'RadioSelect':
                params[key] = readRadioSelect(key);
                break;
            case 'CheckboxSelectMultiple':
                params[key] = readCheckboxSelectMultipe(key);
                break;
            default:
                params[key] = document.getElementsByName(key)[0].value;
        }
    });
    return params
}

function readSelectMultiple(name) {
    let country_codes = []
    let inputs = document.getElementsByName(name)[0]
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].selected === true) {
            country_codes.push(inputs[i].value)
        }
    }
    return country_codes
}

function readCheckboxSelectMultipe(name) {
    let ids = []
    let inputs = document.getElementsByName(name)
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].checked === true) {
            ids.push(inputs[i].value)
        }
    }
    return ids
}

function readRadioSelect(name) {
    const heatingButtons = document.getElementsByName(name);
    let heating;
    for (let i = 0; i < heatingButtons.length; i++) {
        if (heatingButtons[i].checked === true) {
            heating = heatingButtons[i].value;
        }
    }
    return heating
}

async function renderSummary(summary) {
    let summary_container = document.getElementById('summary-container');
    summary_container.textContent = ''
    Object.keys(summary).forEach(key => {
        let label = document.createElement('P');
        let value = document.createElement('P');
        label.innerText = summary[key]['label'] + ':';
        value.innerText = summary[key]['value'].toString();
        summary_container.appendChild(label);
        summary_container.appendChild(value);
    });
    $('#summary-container').collapse('show');
}

async function renderInfo(info) {
    let info_container = document.getElementById('info-container');
    info_container.textContent = ''
    Object.keys(info).forEach(key => {
        let label = document.createElement('P');
        let value = document.createElement('P');
        label.innerText = info[key]['label'].toString() + ':';
        value.innerText = info[key]['value'].toString();
        info_container.appendChild(label);
        info_container.appendChild(value);
    });
    $('#info-container').collapse('show');
}