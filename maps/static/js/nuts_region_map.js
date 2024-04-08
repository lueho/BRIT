"use strict";

async function updateLayers({region_params, catchment_params, feature_params} = {}) {
    const promises = [
        region_params && fetchRegionGeometry(region_params),
        catchment_params && fetchCatchmentGeometry(catchment_params),
        feature_params && fetchFeatureGeometries(feature_params)
    ].filter(Boolean);
    prepareMapRefresh();
    await refreshMap(promises);
}

function cleanup() {
    hideLoadingIndicator();
    unlockFilter();
    document.querySelectorAll("select").forEach(selector => selector.disabled = false);
}

async function clickedFeature(event) {
    document.querySelectorAll("select").forEach(selector => selector.disabled = true);
    const feature = event.layer.feature;
    const featureValue = feature.properties.id;
    const summary = (await fetchFeatureSummaries(feature)).summaries[0];
    const text = `${summary.Name} (${summary['Nuts id']})`;

    $(`#id_level_${feature.properties.level}`).select2("trigger", "select", {
        data: {id: featureValue, text: text}
    });

    renderSummaries(await fetchFeatureSummaries(feature));
    document.querySelectorAll("select").forEach(selector => selector.disabled = false);
}

const changedSelect = async function(e) {
    // Ensure this function is triggered only for select elements
    if (e.target.tagName === 'SELECT') {
        document.querySelectorAll("select").forEach(selector => selector.disabled = true);

        const target = e.target;
        if (!target.value) {
            // Fallback logic in case the target value is not available
            // Make sure this logic accurately finds the intended target
        }
        if (target.value) {
            await updateLayers({region_params: {pk: target.value}, feature_params: {parent_id: target.value}});
            renderSummaries(await fetchFeatureSummaries(target.value));
            await updateUrls(target.value);
        }

        document.querySelectorAll("select").forEach(selector => selector.disabled = false);
    }
};

document.querySelector('form').addEventListener("change", changedSelect, false);

$('form').on('change', 'select', changedSelect);

