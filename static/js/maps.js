let map;
let myRenderer = L.canvas({padding: 0.5});
let feature_layer;
let region_layer;

window.addEventListener("map:init", function (event) {
    map = event.detail.map;
});

async function fetchFeatureGeometries(base_url, params, mapConfig) {

    let dataurl = base_url + $.param(params);

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

    // Fill "Results" section with analysis data from the analysis dict
    return data['analysis'];
}

async function fetchRegionGeometry(region_base_url, region_id) {

    // Define query string for REST API
    let params = L.Util.extend({
        region_id: region_id
    });

    let url = region_base_url + L.Util.getParamString(params);

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
}

function loadMap(config) {
    fetchRegionGeometry(config['base_url'], config['region_id']);
    if (config['load_features'] === true) {
        filterFeatures();
    }
    map.invalidateSize();
}

function readMultiChoiceCheckboxes(name) {
    let ids = []
    let inputs = document.getElementsByName(name)
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].checked === true) {
            ids.push(inputs[i].value)
        }
    }
    return ids
}

function readSingleChoiceCheckbox(name) {
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
}