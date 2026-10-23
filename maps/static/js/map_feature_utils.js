"use strict";

// Shared Leaflet feature highlighting helpers. Loaded site-wide by the base
// templates ahead of maps.js and page-specific map scripts, so each map only
// configures the style/promotion behaviour instead of reimplementing it.

const MAP_FEATURE_HIGHLIGHT_STYLE = { color: '#f49a33' };

/**
 * Apply a highlight style to a feature layer and optionally promote it above
 * overlapping layers.
 * @param {L.Layer} layer - The layer to highlight.
 * @param {Object} [options]
 * @param {Object} [options.style] - Leaflet style applied via setStyle().
 * @param {boolean|function(L.Layer): boolean} [options.promote] - Whether to
 *   bring the layer to front. A function receives the layer and returns a
 *   boolean (e.g. to keep markers above polygons).
 */
function selectMapFeature(layer, { style = MAP_FEATURE_HIGHLIGHT_STYLE, promote = true } = {}) {
    if (!layer) return;
    try {
        if (typeof layer.setStyle === 'function') {
            layer.setStyle(style);
        }
    } catch (_) { /* ignore styling errors */ }
    const shouldPromote = typeof promote === 'function' ? promote(layer) : promote !== false;
    if (shouldPromote && typeof layer.bringToFront === 'function') {
        try { layer.bringToFront(); } catch (_) { /* ignore */ }
    }
}

/**
 * Reset the styles of every layer in a feature group and optionally demote
 * layers underneath others.
 * @param {L.LayerGroup} featureGroup - The group to reset.
 * @param {Object} [options]
 * @param {Object} [options.style] - Style applied to each layer via setStyle().
 *   When omitted, featureGroup.resetStyle() is used instead.
 * @param {string} [options.demote] - 'group' calls bringToBack() on the whole
 *   group, 'polygons' calls bringToBack() on each L.Polygon layer only,
 *   'none' leaves z-order untouched.
 */
function resetMapFeatureStyles(featureGroup, { style = null, demote = 'group' } = {}) {
    if (!featureGroup) return;
    if (style && typeof featureGroup.eachLayer === 'function') {
        featureGroup.eachLayer(layer => {
            try {
                if (layer && typeof layer.setStyle === 'function') {
                    layer.setStyle(style);
                }
            } catch (_) { /* ignore styling errors */ }
        });
    } else if (typeof featureGroup.resetStyle === 'function') {
        try { featureGroup.resetStyle(); } catch (_) { /* ignore */ }
    }
    if (demote === 'group' && typeof featureGroup.bringToBack === 'function') {
        try { featureGroup.bringToBack(); } catch (_) { /* ignore */ }
    } else if (demote === 'polygons' && typeof featureGroup.eachLayer === 'function') {
        featureGroup.eachLayer(layer => {
            try {
                if (typeof L !== 'undefined' && layer instanceof L.Polygon
                    && typeof layer.bringToBack === 'function') {
                    layer.bringToBack();
                }
            } catch (_) { /* ignore */ }
        });
    }
}
