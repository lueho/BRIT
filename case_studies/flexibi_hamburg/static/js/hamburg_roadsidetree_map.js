"use strict";

async function clickedFeature(e) {
    const featureId = e.layer.feature.id;
    const url = `${mapConfig.featuresLayerDetailsUrlTemplate}${featureId}/`;
    const response = await fetch(url);
    const json = await response.json();
    const html = `
    <p>
        <strong>Tree type:</strong><br/>
        ${json.art_latein}
    </p>
    <p>
        <strong>Plantation year:</strong><br/>
        ${json.pflanzjahr}
    </p>
    <p>
        <strong>Stem circumference:</strong><br/>
        ${json.stammumfang} cm
    </p>
    <p>
        <strong>Crown diameter:</strong><br/>
        ${json.kronendurchmesser} m
    </p>
    <p>
        <strong>Address:</strong><br/>
        ${json.address}<br/>
        Hamburg, Germany
    </p>`;
    map.openPopup(html, e.latlng, { offset: L.point(0, -1) });
}