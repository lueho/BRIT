let map;
let myRenderer = L.canvas({padding: 0.5});
let feature_layer;
let region_layer;

window.addEventListener("map:init", function (event) {
    map = event.detail.map;
});

document.querySelector("#summary-container").addEventListener('click', function (e) {
    if (e.target.matches('.collapse-selector')) {
        updateUrls(e.target.dataset['pk']);
    }
});

async function fetchFeatureInfos(feature, mapConfig) {
    let dataurl = mapConfig['feature_popup_url'] + '?' + 'collection_id=' + feature['properties']['id'];
    let response = await fetch(dataurl);
    return await response.json()
}

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

    feature_layer.on('click', async function (event) {
        await clickedFeature(event);
    });


    if (mapConfig['adjust_bounds_to_features'] === true) {
        try {
            map.fitBounds(feature_layer.getBounds())
        } catch (ex) {

        }
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
        style: region_layer_style,
        interactive: false
    })
    region_layer.addTo(map);
    map.fitBounds(region_layer.getBounds())

    return data
}

async function clickedFilterButton() {
    let btn = document.getElementById('filter-button')
    btn.disabled = true
    await filterFeatures();
    btn.disabled = false
}

async function clickedFeature(event){
    let feature_infos = await fetchFeatureInfos(event.layer.feature, mapConfig)
    await renderSummaryAlternative(feature_infos);
    updateUrls(event.layer.feature['properties']['id']);
}

async function filterFeatures() {

    const params = parseFilterParameters();
    let data = await fetchFeatureGeometries(params, mapConfig);
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
    $('#info-card-body').collapse('show');
    $('#filter-card-body').collapse('hide');
}


function renderSummaryContainer(summary, summary_container) {

    Object.keys(summary).forEach(key => {

        if (summary[key]) {

            let summary_item = document.createElement('div')

            let label = document.createElement('P');
            let b = document.createElement('B');
            b.innerText = key + ':';
            label.appendChild(b);
            summary_item.appendChild(label);

            let value = document.createElement('P');
            if (Array.isArray(summary[key])) {
                let ul = document.createElement('ul');
                value.appendChild(ul);
                summary[key].forEach(function (item) {
                    let li = document.createElement('li')
                    li.innerText = item.toString()
                    ul.appendChild(li)
                });
            } else {
                value.innerText = summary[key].toString();
            }
            summary_item.appendChild(value)
            if (key === 'id') {
                summary_item.className = 'd-none'
                summary_container.className += ' pk-holder'
                summary_container.setAttribute('data-pk', summary['id'])
            }

            summary_container.appendChild(summary_item);
        }
    });
}

async function renderSummaryAlternative(json) {

    // Empty summary container from previous content
    let outer_summary_container = document.getElementById('summary-container');
    outer_summary_container.textContent = ''

    if (json['summaries'].length > 1) {

        // render multiple summaries

        let message = document.createElement('P');
        message.innerText = 'Found ' + json['summaries'].length + ' items:';
        outer_summary_container.appendChild(message);

        let accordion = document.createElement('div');
        accordion.id = 'summaries_accordion'
        accordion.className = 'accordion';
        outer_summary_container.appendChild(accordion);


        json['summaries'].forEach((summary, i) => {

            let card = document.createElement('div');
            card.className = 'card';
            accordion.appendChild(card);

            let header = document.createElement('div');
            header.className = 'card-header collapse-selector';
            header.setAttribute('role', 'button');
            header.setAttribute('data-toggle', 'collapse');
            header.setAttribute('href', '#collapse' + i.toString());
            header.setAttribute('aria-expanded', 'true');
            header.setAttribute('aria-controls', 'collapse' + i.toString());
            if (summary['id']) {
                header.setAttribute('data-pk', summary['id']);
            }
            let numbering = i + 1;
            header.innerHTML = '<b>#' + numbering.toString() + '</b>';
            card.appendChild(header);

            let collapse_container = document.createElement('div');
            collapse_container.id = 'collapse' + i.toString();
            collapse_container.className = 'summary collapse';
            collapse_container.setAttribute('aria-labelledby', 'collapse' + i.toString());
            collapse_container.setAttribute('data-parent', '#summaries_accordion');
            card.appendChild(collapse_container);

            let body = document.createElement('div');
            body.className = 'card-body';

            collapse_container.appendChild(body);
            renderSummaryContainer(summary, body);
        });


    } else {
        // render one single summary
        const summary = json['summaries'][0];
        renderSummaryContainer(summary, outer_summary_container);
    }

    $('#info-card-body').collapse('show');
    $('#filter-card-body').collapse('hide');
}
