"use strict";

// Shared formatting helpers for feature detail and summary rendering.
// Loaded site-wide by the base templates ahead of dependent scripts, so map
// modules can call these without relying on implicit script order.

function formatHeader(key) {
    return key
        .replace(/([A-Z])/g, ' $1')
        .replace(/_/g, ' ')
        .replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase())
        .trim();
}

function formatList(value, separator) {
    if (!value) {
        return '';
    }
    const items = value.split(separator).filter(item => item.trim());
    if (items.length === 0) {
        return '';
    }

    return `<ul class="list-disc pl-4">
        ${items.map(item => `<li>${item.trim()}</li>`).join('')}
    </ul>`;
}

function truncateUrl(url, maxLength = 40) {
    return url.length > maxLength ? url.substring(0, maxLength) + '...' : url;
}

function formatUrls(urlString) {
    if (!urlString) {
        return '';
    }
    const urls = urlString.split(', ').filter(Boolean);
    if (urls.length === 0) {
        return '';
    }

    return urls
        .map(url => `<li>
            <a href="${url}"
               title="${url}"
               target="_blank" 
               rel="noopener noreferrer"
               class="url-link hover:text-blue-600">
                ${truncateUrl(url)}
            </a>
        </li>`)
        .join('');
}

const DEFAULT_FIELD_FORMAT = (value) => value || '';

/**
 * Build a fieldConfig object for renderFeatureDetails-style renderers.
 * Accepts shorthand booleans (include flag with the default format) or
 * { include, format } entries; omitted keys default to include: true and the
 * default format.
 */
function createFieldConfig(fields) {
    const config = {};
    Object.entries(fields).forEach(([key, def]) => {
        config[key] = typeof def === 'boolean'
            ? { include: def, format: DEFAULT_FIELD_FORMAT }
            : { include: def.include !== false, format: def.format || DEFAULT_FIELD_FORMAT };
    });
    return config;
}
