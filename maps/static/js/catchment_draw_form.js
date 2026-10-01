"use strict";

// Shows the boundary of the region selected in the parent region field on the
// draw map of the "draw custom borders" catchment form, and zooms to it. The
// layer is kept out of the geometry field's FeatureGroup so it is never
// serialized into the form or grabbed by the draw control's edit handlers.

const PARENT_REGION_STYLE = {
    color: '#e6550d',
    weight: 2,
    opacity: 0.9,
    dashArray: '6 4',
    fillColor: '#e6550d',
    fillOpacity: 0.05
};

let parentRegionLayer = null;
// Bumped per selection so an out-of-order response from a superseded request
// cannot overwrite the boundary of the region picked last.
let parentRegionRequest = 0;

function parentRegionConfig() {
    const el = document.getElementById('parent-region-preview');
    if (!el) return null;
    return {
        geojsonUrl: el.dataset.geojsonUrl,
        regionFieldId: el.dataset.regionFieldId,
        mapId: el.dataset.mapId
    };
}

// django-leaflet publishes each form map under window['leafletmap<mapId>'] and
// fires map:init on window; both paths are covered because script load order
// relative to the inline widget map setup is not guaranteed.
function withDrawMap(mapId, callback) {
    const existing = window['leafletmap' + mapId];
    if (existing) {
        callback(existing);
        return;
    }
    const handler = function (e) {
        if (e.detail && e.detail.id === mapId) {
            window.removeEventListener('map:init', handler);
            callback(e.detail.map);
        }
    };
    window.addEventListener('map:init', handler);
}

function removeParentRegionLayer(map) {
    if (parentRegionLayer) {
        map.removeLayer(parentRegionLayer);
        parentRegionLayer = null;
    }
}

async function showParentRegion(map, regionId, geojsonUrl) {
    const generation = ++parentRegionRequest;
    const url = new URL(geojsonUrl, window.location.origin);
    url.searchParams.set('id', regionId);
    let data;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }
        data = await response.json();
    } catch (error) {
        console.error('Could not load the parent region boundary:', error);
        return;
    }
    if (generation !== parentRegionRequest) {
        return;
    }
    removeParentRegionLayer(map);
    const layer = L.geoJSON(data, {
        style: PARENT_REGION_STYLE,
        // The boundary must not swallow the clicks used to draw the catchment.
        interactive: false,
        bubblingMouseEvents: false
    });
    if (layer.getLayers().length === 0) {
        // Region without borders: nothing to show, keep the current view.
        return;
    }
    parentRegionLayer = layer;
    layer.addTo(map);
    if (layer.bringToBack) {
        layer.bringToBack();
    }
    map.fitBounds(layer.getBounds());
}

function initParentRegionPreview() {
    const config = parentRegionConfig();
    if (!config || !config.geojsonUrl) return;
    const field = document.getElementById(config.regionFieldId);
    if (!field) return;

    withDrawMap(config.mapId, (map) => {
        // TomSelect propagates change events to the underlying select element.
        field.addEventListener('change', () => {
            if (field.value) {
                showParentRegion(map, field.value, config.geojsonUrl);
            } else {
                parentRegionRequest++;
                removeParentRegionLayer(map);
            }
        });
        // A region may already be selected, e.g. when the form re-renders
        // after a validation error.
        if (field.value) {
            showParentRegion(map, field.value, config.geojsonUrl);
        }
    });
}

initParentRegionPreview();
