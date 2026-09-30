"use strict";

function geoDatasetFilterSelectOptions(select, fetchImpl) {
    const options = {
        plugins: ['remove_button'],
        maxOptions: 100,
        placeholder: select.dataset.placeholder || 'Any',
        hidePlaceholder: true,
    };
    if (select.dataset.geodatasetFilter !== 'autocomplete') {
        return options;
    }
    const url = select.dataset.autocompleteUrl;
    return Object.assign(options, {
        valueField: 'value',
        labelField: 'text',
        searchField: ['text'],
        loadThrottle: 250,
        shouldLoad: query => query.length > 0,
        load(query, callback) {
            fetchImpl(`${url}?q=${encodeURIComponent(query)}`, {
                headers: { Accept: 'application/json' },
            })
                .then(response => (response.ok ? response.json() : { results: [] }))
                .then(data => callback(data.results || []))
                .catch(() => callback());
        },
    });
}

function initGeoDatasetFilterSelects(root) {
    if (typeof TomSelect === 'undefined') {
        return;
    }
    root.querySelectorAll('select[data-geodataset-filter]').forEach(select => {
        if (!select.tomselect) {
            new TomSelect(select, geoDatasetFilterSelectOptions(select, fetch));
        }
    });
}

document.addEventListener('DOMContentLoaded', () => initGeoDatasetFilterSelects(document));
