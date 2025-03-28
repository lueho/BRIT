"use strict";

async function queryDatasets() {
    const dataurl = "{% url 'data.result_layer' layer.table_name %}";

    // Fetch data from REST API
    const response = await fetch(dataurl);
    const data = await response.json();

    // Render geodata on map
    const geodata = data.geoJson;
    const region_id = data.region_id;
    await fetchRegionGeometry(region_id);
    const catchment_id = data.catchment_id;
    await fetchCatchmentGeometry(catchment_id);

    L.geoJson(geodata, {
        pointToLayer: function(feature, latlng) {
            return L.circleMarker(latlng, {
                renderer: resultRenderer,
                color: '#63c36c',
                fillOpacity: 1,
                radius: 5,
                stroke: false
            });
        },
        onEachFeature: function onEachFeature(feature, layer) {
        }
    }).addTo(map);

}