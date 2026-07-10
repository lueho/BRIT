/**
 * Waste Atlas — Reusable classified choropleth renderer (D3.js, print-quality SVG).
 *
 * Usage:
 *   WasteAtlasChoropleth.init({
 *     svgId:        'atlas-svg',
 *     containerId:  'map-container',
 *     loadingId:    'loading-overlay',
 *     country:      'DE',
 *     year:         2022,
 *     title:        'Map title',
 *     subtitle:     '',                   // optional
 *     dataUrl:      '/waste_collection/api/waste-atlas/orga-level/',
 *     dataField:    'orga_level',         // field in the data JSON to classify on
 *     categories:   [                     // ordered; first match wins
 *       { value: 'nuts', label: 'Landkreise', color: '#93d163' },
 *       ...
 *     ],
 *     noDataColor:  '#e0e0e0',            // optional, default grey
 *     noDataLabel:  'Keine Daten',        // optional
 *     legendTitle:  'Legend',              // optional
 *   });
 */

/* global d3 */

var WasteAtlasChoropleth = (function () {
  'use strict';

  var COUNTRY_FILL = '#f0f0f0';
  var BUNDESLAND_STROKE = '#666666';
  var BUNDESLAND_STROKE_WIDTH = 1.0;   // Thinner than country border
  var COUNTRY_STROKE = '#000000';
  var COUNTRY_STROKE_WIDTH = 1.5;      // Thicker than Bundesläender border
  var CATCHMENT_STROKE = '#232323';
  var CATCHMENT_STROKE_WIDTH = 0.35;   // ≈ 0.1 mm at 96 DPI
  // Maintainer aid: outline style for catchments with conflicting collections.
  var CONFLICT_STROKE = '#d7263d';
  var CONFLICT_STROKE_WIDTH = 1.6;
  var CONFLICT_STROKE_DASHARRAY = '3 2';
  var EXPORT_DPI = 300;
  var EXPORT_WIDTH_MM = 160;
  var EXPORT_HEIGHT_MM = 110;
  var EXPORT_MAX_HEIGHT_MM = 180;
  var EXPORT_WIDTH = Math.round(EXPORT_WIDTH_MM / 25.4 * EXPORT_DPI);
  var EXPORT_HEIGHT = Math.round(EXPORT_HEIGHT_MM / 25.4 * EXPORT_DPI);
  var EXPORT_LEGEND_FONT_SIZE = 11 / 72 * EXPORT_DPI;
  var EXPORT_LEGEND_FONT_FAMILY = "'Calibri', 'Carlito', Arial, sans-serif";

  var _cfg = {};
  var _svg;
  var _lastData = null;
  var _lastLoadCfg = null;
  var _baseLoadCfg = null;
  var _measureCtx = null;
  // Maintainer conflict aid: catchment ids with conflicting theme values,
  // plus per-catchment detail for tooltips. Populated on demand by the
  // "Highlight conflicting catchments" toggle.
  var _conflictCatchments = null;
  var _conflictDetails = null;
  var _conflictEnabled = false;

  // ---- helpers --------------------------------------------------------------

  function _show(el) { if (el) el.style.display = ''; }
  function _hide(el) { if (el) el.style.display = 'none'; }

  function _fetchJSON(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status + ' ' + r.statusText + ' — ' + url);
        return r.json();
      });
  }

  /**
   * Build the conflict-aid API URL for the current selection/theme.
   * Returns null when the map config does not opt into the conflict aid.
   */
  function _conflictUrlFor(cfg, country, year, fromYear) {
    if (!cfg.conflictUrl || !cfg.conflictTheme) return null;
    if (cfg.changeMode || fromYear) return null; // not meaningful for diffs
    var params = [
      'theme=' + encodeURIComponent(cfg.conflictTheme),
      'country=' + encodeURIComponent(country || cfg.country || 'DE'),
      'year=' + encodeURIComponent(year || cfg.year)
    ];
    if (cfg.nutsPrefix) {
      params.push('nuts_prefix=' + encodeURIComponent(cfg.nutsPrefix));
    }
    return cfg.conflictUrl + '?' + params.join('&');
  }

  /**
   * Fetch conflict rows for the current selection and store them as a
   * catchment-id set + detail map.  Resolves with the populated set (or an
   * empty set when the aid is disabled/unsupported for this theme).
   */
  function _loadConflicts(cfg, country, year, fromYear) {
    var url = _conflictUrlFor(cfg, country, year, fromYear);
    if (!url) {
      _conflictCatchments = null;
      _conflictDetails = null;
      return Promise.resolve(null);
    }
    return _fetchJSON(url).then(function (rows) {
      var ids = new Set();
      var details = {};
      (rows || []).forEach(function (row) {
        ids.add(row.catchment_id);
        details[row.catchment_id] = row;
      });
      _conflictCatchments = ids;
      _conflictDetails = details;
      return ids;
    });
  }

  function _isNoDataValue(value, categories) {
    if (value == null) return true;
    for (var i = 0; i < categories.length; i++) {
      var cat = categories[i];
      if (typeof cat.test === 'function') {
        if (cat.test(value)) return false;
      } else if (cat.value === value) {
        return false;
      }
    }
    return true;
  }

  function _colorFor(value, categories, noDataColor) {
    if (value == null) return noDataColor || '#e0e0e0';
    for (var i = 0; i < categories.length; i++) {
      var cat = categories[i];
      if (typeof cat.test === 'function') {
        if (cat.test(value)) return cat.color;
      } else if (cat.value === value) {
        return cat.color;
      }
    }
    return noDataColor || '#e0e0e0';
  }

  /**
   * Merge thematic records into the catchment features and flag on the
   * config whether any rendered feature falls back to the no-data color.
   * Idempotent; used by both the screen render and the export layout so
   * the "No data" legend entry is only drawn when such features exist.
   */
  function _annotateFeatures(data, cfg) {
    var records = Array.isArray(data.thematicData) ? data.thematicData
      : (data.thematicData.results || []);
    if (typeof cfg.transformData === 'function') {
      records = cfg.transformData(records);
    } else if (cfg.transformName && transforms[cfg.transformName]) {
      records = transforms[cfg.transformName](records);
    }
    var lookup = {};
    records.forEach(function (r) { lookup[r.catchment_id] = r; });

    var hasNoData = false;
    var hasOverlayPattern = false;
    if (data.catchments.features) {
      data.catchments.features.forEach(function (f) {
        var rec = lookup[f.properties.catchment_id];
        f.properties._thematic_value = rec ? rec[cfg.dataField] : null;
        f.properties._thematic_record = rec || null;
        f.properties._overlay_pattern = rec && cfg.overlayPatternField
          ? Boolean(rec[cfg.overlayPatternField])
          : false;
        if (f.properties._overlay_pattern) {
          hasOverlayPattern = true;
        }
        if (_isNoDataValue(f.properties._thematic_value, cfg.categories)) {
          hasNoData = true;
        }
      });
    }
    cfg._hasNoData = hasNoData;
    cfg._hasOverlayPattern = hasOverlayPattern;
  }

  function _overlayPatternId(cfg) {
    return (cfg.svgId || 'atlas-svg') + '-overlay-pattern';
  }

  function _defineOverlayPattern(cfg) {
    if (!cfg.overlayPatternField) return;

    var pattern = _svg.append('defs')
      .append('pattern')
      .attr('id', _overlayPatternId(cfg))
      .attr('patternUnits', 'userSpaceOnUse')
      .attr('width', 6)
      .attr('height', 6)
      .attr('patternTransform', 'rotate(45)');

    pattern.append('line')
      .attr('x1', 0)
      .attr('y1', 0)
      .attr('x2', 0)
      .attr('y2', 6)
      .attr('stroke', '#ffffff')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2);
  }

  // ---- data fetching --------------------------------------------------------

  function _fetchAll(cfg) {
    var base = '/waste_collection/api/waste-atlas/';
    var nutsSuffix = cfg.nutsPrefix ? '&nuts_prefix=' + encodeURIComponent(cfg.nutsPrefix) : '';
    var collectionYear = cfg.collectionYear || cfg.year;
    var collectionYearSuffix = cfg.collectionYear ? '&collection_year=' + encodeURIComponent(cfg.collectionYear) : '';
    var catchmentDataUrl = cfg.catchmentDataUrl || (base + 'catchment/geojson/');
    var catchUrl = catchmentDataUrl + '?country=' + cfg.country + '&year=' + collectionYear + nutsSuffix;
    var nuts0Url = '/maps/api/nuts_region/geojson/?levl_code=0&cntr_code=' + cfg.country;
    var nutsLevel = cfg.nutsLevel || 1;
    var nutsRegionUrl = '/maps/api/nuts_region/geojson/?levl_code=' + nutsLevel + '&cntr_code=' + cfg.country;
    var dataUrl = cfg.dataUrl + '?country=' + cfg.country + '&year=' + cfg.year + nutsSuffix + collectionYearSuffix;
    var outlineUrl = cfg.outlineGeoJsonUrl
      ? cfg.outlineGeoJsonUrl + '?country=' + cfg.country + '&year=' + collectionYear + nutsSuffix
      : null;
    var fromDataUrl = cfg.changeMode
      ? cfg.dataUrl + '?country=' + cfg.country + '&year=' + cfg.fromYear + nutsSuffix
      : null;
    var requests = [
      _fetchJSON(catchUrl),
      _fetchJSON(dataUrl),
      _fetchJSON(nuts0Url),
      _fetchJSON(nutsRegionUrl)
    ];
    if (outlineUrl) requests.push(_fetchJSON(outlineUrl));
    if (fromDataUrl) requests.push(_fetchJSON(fromDataUrl));

    return Promise.all(requests).then(function (results) {
      var bundeslaender = results[3];
      if (cfg.nutsPrefix && bundeslaender && bundeslaender.features) {
        var prefixes = cfg.nutsPrefix
          .split(',')
          .map(function (p) { return p.trim(); })
          .filter(function (p) { return p.length > 0; });
        bundeslaender = Object.assign({}, bundeslaender, {
          features: bundeslaender.features.filter(function (f) {
            var nutsId = f.properties && (f.properties.nuts_id || f.properties.NUTS_ID || '');
            return prefixes.some(function (p) { return nutsId.indexOf(p) === 0; });
          }),
        });
      }
      return {
        catchments: results[0],
        thematicData: results[1],
        countryBorder: results[2],
        bundeslaender: bundeslaender,
        allCatchments: results[0],
        acpvOutlines: outlineUrl ? results[4] : null,
        fromThematicData: fromDataUrl ? results[outlineUrl ? 5 : 4] : null,
      };
    });
  }

  // ---- change maps (two-year diff) ------------------------------------------

  function _changeCategories(toYear) {
    return [
      { value: 'no_change', label: 'No change', color: '#c8e6c9' },
      { value: 'changed', label: 'Category changed', color: '#ffb74d' },
      { value: 'new', label: 'New in ' + toYear, color: '#64b5f6' },
      { value: 'removed', label: 'Removed in ' + toYear, color: '#bdbdbd' }
    ];
  }

  function _numericChangeCategories(toYear) {
    return [
      { value: 'decrease', label: 'Decrease', color: '#d73027' },
      { value: 'no_change', label: 'No numeric change', color: '#c8e6c9' },
      { value: 'increase', label: 'Increase', color: '#1a9850' },
      { value: 'changed', label: 'Category changed', color: '#ffb74d' },
      { value: 'new', label: 'New value in ' + toYear, color: '#64b5f6' },
      { value: 'removed', label: 'Value removed in ' + toYear, color: '#bdbdbd' }
    ];
  }

  function _recordList(raw) {
    if (Array.isArray(raw)) return raw;
    return (raw && raw.results) || [];
  }

  function _classifyRecords(cfg, raw) {
    var records = _recordList(raw);
    if (typeof cfg.transformData === 'function') {
      records = cfg.transformData(records);
    } else if (cfg.transformName && transforms[cfg.transformName]) {
      records = transforms[cfg.transformName](records);
    }
    var classes = {};
    records.forEach(function (r) {
      var value = r[cfg.dataField];
      classes[r.catchment_id] = value == null ? null : value;
    });
    return classes;
  }

  function _recordLookup(raw) {
    var lookup = {};
    _recordList(raw).forEach(function (r) {
      lookup[r.catchment_id] = r;
    });
    return lookup;
  }

  function _numericValue(record, field) {
    if (!record) return null;
    var value = record[field];
    if (value === null || value === undefined || value === '') return null;
    var number = Number(value);
    return isNaN(number) ? null : number;
  }

  function _changeRecords(cfg, fromRaw, toRaw) {
    if (cfg.numericField) {
      return _numericChangeRecords(cfg, fromRaw, toRaw);
    }
    var fromClasses = _classifyRecords(cfg, fromRaw);
    var toClasses = _classifyRecords(cfg, toRaw);
    var ids = {};
    Object.keys(fromClasses).forEach(function (id) { ids[id] = true; });
    Object.keys(toClasses).forEach(function (id) { ids[id] = true; });
    return Object.keys(ids).map(function (id) {
      var from = fromClasses[id];
      var to = toClasses[id];
      var change = null;
      if (from != null && to != null) change = from === to ? 'no_change' : 'changed';
      else if (to != null) change = 'new';
      else if (from != null) change = 'removed';
      return { catchment_id: parseInt(id, 10) || id, change_type: change };
    });
  }

  function _numericChangeRecords(cfg, fromRaw, toRaw) {
    var fromRecords = _recordLookup(fromRaw);
    var toRecords = _recordLookup(toRaw);
    var fromClasses = _classifyRecords(cfg, fromRaw);
    var toClasses = _classifyRecords(cfg, toRaw);
    var ids = {};
    Object.keys(fromRecords).forEach(function (id) { ids[id] = true; });
    Object.keys(toRecords).forEach(function (id) { ids[id] = true; });
    Object.keys(fromClasses).forEach(function (id) { ids[id] = true; });
    Object.keys(toClasses).forEach(function (id) { ids[id] = true; });

    return Object.keys(ids).map(function (id) {
      var fromValue = _numericValue(fromRecords[id], cfg.numericField);
      var toValue = _numericValue(toRecords[id], cfg.numericField);
      var difference = null;
      var change = null;

      if (fromValue != null && toValue != null) {
        difference = toValue - fromValue;
        if (Math.abs(difference) < 1e-9) {
          change = 'no_change';
        } else {
          change = difference > 0 ? 'increase' : 'decrease';
        }
      } else if (toValue != null) {
        change = 'new';
      } else if (fromValue != null) {
        change = 'removed';
      } else if (fromClasses[id] != null && toClasses[id] != null) {
        change = fromClasses[id] === toClasses[id] ? 'no_change' : 'changed';
      } else if (toClasses[id] != null) {
        change = 'new';
      } else if (fromClasses[id] != null) {
        change = 'removed';
      }

      return {
        catchment_id: parseInt(id, 10) || id,
        change_type: change,
        from_value: fromValue,
        to_value: toValue,
        difference: difference
      };
    });
  }

  function _changeRenderConfig(loadCfg, baseTitle) {
    var isNumericChange = Boolean(loadCfg.numericField);
    var renderCfg = Object.assign({}, loadCfg, {
      dataField: 'change_type',
      transformName: null,
      transformData: null,
      categories: isNumericChange
        ? _numericChangeCategories(loadCfg.year)
        : _changeCategories(loadCfg.year),
      legendTitle: isNumericChange ? 'Difference' : 'Change',
      noDataLabel: 'No data',
      title: (baseTitle || '') + ' — changes (' + loadCfg.fromYear + ' → ' + loadCfg.year + ')'
    });
    if (isNumericChange) {
      renderCfg.tooltipFields = [
        { field: 'from_value', label: String(loadCfg.fromYear) },
        { field: 'to_value', label: String(loadCfg.year) },
        { field: 'difference', label: 'Difference' }
      ];
    }
    return renderCfg;
  }

  function _regionCountry(region) {
    return region && typeof region === 'object' ? region.country : region;
  }

  function _regionNutsPrefix(region) {
    return region && typeof region === 'object' ? region.nutsPrefix : '';
  }

  function _regionNutsLevel(region) {
    return region && typeof region === 'object' ? region.nutsLevel : '';
  }

  function _configForSelection(cfg, region, year, preserveScope) {
    var country = _regionCountry(region);
    var loadCfg = Object.assign({}, cfg, { country: country, year: year });
    var nutsPrefix = _regionNutsPrefix(region);
    var nutsLevel = _regionNutsLevel(region);

    if (region && typeof region === 'object') {
      if (nutsPrefix) {
        loadCfg.nutsPrefix = nutsPrefix;
        if (nutsLevel) loadCfg.nutsLevel = parseInt(nutsLevel, 10);
        else delete loadCfg.nutsLevel;
      } else {
        delete loadCfg.nutsPrefix;
        delete loadCfg.nutsLevel;
      }
      return loadCfg;
    }

    if (country === 'IT-ST') {
      return Object.assign(loadCfg, {
        country: 'IT',
        nutsPrefix: 'ITH10',
        nutsLevel: 3
      });
    }

    if (!preserveScope) {
      delete loadCfg.nutsPrefix;
      delete loadCfg.nutsLevel;
    }
    return loadCfg;
  }

  function _isCurrentPath(path) {
    return window.location.pathname.replace(/\/$/, '') === path.replace(/\/$/, '');
  }

  function _selectorNavigationTarget(url, year, fromYear, region) {
    if (!url || _isCurrentPath(url)) return null;
    return url + '?' + _selectorQueryString(year, fromYear, region);
  }

  function _selectorQueryString(year, fromYear, region) {
    var params = fromYear
      ? 'from_year=' + encodeURIComponent(fromYear) + '&to_year=' + encodeURIComponent(year)
      : 'year=' + encodeURIComponent(year);
    var country = _regionCountry(region);
    var nutsPrefix = _regionNutsPrefix(region);
    var nutsLevel = _regionNutsLevel(region);
    if (country) params += '&country=' + encodeURIComponent(country);
    if (nutsPrefix) params += '&nuts_prefix=' + encodeURIComponent(nutsPrefix);
    if (nutsLevel) params += '&nuts_level=' + encodeURIComponent(nutsLevel);
    return params;
  }

  function _replaceSelectorUrl(url, year, fromYear, region) {
    if (!window.history || !window.history.replaceState) return;
    var path = url || window.location.pathname;
    window.history.replaceState(null, '', path + '?' + _selectorQueryString(year, fromYear, region));
  }

  function _debounce(fn, delay) {
    var timer = null;
    return function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(fn, delay);
    };
  }

  function initSelectorControls(loadCurrent, options) {
    options = options || {};
    var disableNavigation = options.disableNavigation || false;
    var countrySelect = document.getElementById('sel-country');
    var wasteCategorySelect = document.getElementById('sel-waste-category');
    var themeSearchInput = document.getElementById('sel-theme-search');
    var themeSelect = document.getElementById('sel-theme');
    var yearSelect = document.getElementById('sel-year');
    var fromYearSelect = document.getElementById('sel-from-year');
    var toYearSelect = document.getElementById('sel-to-year');
    var btnLoad = document.getElementById('btn-load');
    var btnToggleChange = document.getElementById('btn-toggle-change');
    var form = document.getElementById('atlas-selection-form');
    var statusEl = document.getElementById('atlas-selector-status');

    var yearSelectEl = toYearSelect || yearSelect;
    if (!countrySelect || !themeSelect || !yearSelectEl || !btnLoad) return null;

    var themeOptions = Array.prototype.slice.call(themeSelect.options);
    var visibleThemeCount = 0;

    function selectedYear() {
      return parseInt(yearSelectEl.value, 10) || 2024;
    }

    function selectedFromYear() {
      return fromYearSelect ? parseInt(fromYearSelect.value, 10) || 2023 : null;
    }

    function previousChangeYear(year) {
      var value = String(year);
      if (yearSelect) {
        for (var i = 0; i < yearSelect.options.length; i++) {
          if (yearSelect.options[i].value === value) {
            return i > 0 ? yearSelect.options[i - 1].value : value;
          }
        }
      }
      var numericYear = parseInt(value, 10);
      return numericYear ? String(numericYear - 1) : value;
    }

    function selectedRegion() {
      var selectedOption = countrySelect.options[countrySelect.selectedIndex];
      return {
        country: selectedOption ? selectedOption.getAttribute('data-country') || countrySelect.value : countrySelect.value,
        nutsPrefix: selectedOption ? selectedOption.getAttribute('data-nuts-prefix') || '' : '',
        nutsLevel: selectedOption ? selectedOption.getAttribute('data-nuts-level') || '' : ''
      };
    }

    function selectedCountryCode() {
      return selectedRegion().country;
    }

    function selectedRouteUrl() {
      var selectedOption = themeSelect.options[themeSelect.selectedIndex];
      if (!selectedOption) return null;
      var attr = options.useChangeUrls ? 'data-change-url' : 'data-url';
      return selectedOption.getAttribute(attr);
    }

    function selectedCrossLinkUrl() {
      var selectedOption = themeSelect.options[themeSelect.selectedIndex];
      if (!selectedOption) return null;
      var attr = options.useChangeUrls ? 'data-url' : 'data-change-url';
      return selectedOption.getAttribute(attr);
    }

    function selectedThemeGroup() {
      var selectedOption = themeSelect.options[themeSelect.selectedIndex];
      return selectedOption ? selectedOption.getAttribute('data-theme-group') : null;
    }

    function searchQuery() {
      return themeSearchInput ? themeSearchInput.value.trim().toLowerCase() : '';
    }

    function optionMatchesSearch(option, query) {
      if (!query) return true;
      var haystack = option.getAttribute('data-search') || option.textContent || '';
      return haystack.toLowerCase().indexOf(query) !== -1;
    }

    function updateThemeVisibility(selectedMapSet, selectedWasteCategory) {
      var firstVisibleOption = null;
      var query = searchQuery();
      visibleThemeCount = 0;
      themeOptions.forEach(function (option) {
        var isVisible = option.getAttribute('data-map-set') === selectedMapSet
          && (!selectedWasteCategory || option.getAttribute('data-waste-category') === selectedWasteCategory)
          && optionMatchesSearch(option, query);
        option.hidden = !isVisible;
        option.disabled = !isVisible;
        if (isVisible) {
          visibleThemeCount += 1;
          if (!firstVisibleOption) firstVisibleOption = option;
        }
      });
      return firstVisibleOption;
    }

    function findThemeOption(selectedMapSet, selectedWasteCategory, selectedThemeGroup) {
      var fallbackOption = null;
      for (var i = 0; i < themeOptions.length; i++) {
        var option = themeOptions[i];
        if (option.disabled || option.getAttribute('data-map-set') !== selectedMapSet) continue;
        if (selectedWasteCategory && option.getAttribute('data-waste-category') !== selectedWasteCategory) continue;
        if (!fallbackOption) fallbackOption = option;
        if (selectedThemeGroup && option.getAttribute('data-theme-group') === selectedThemeGroup) {
          return option;
        }
      }
      return fallbackOption;
    }

    function selectedText(selectEl) {
      var selectedOption = selectEl && selectEl.options[selectEl.selectedIndex];
      return selectedOption ? selectedOption.textContent.trim() : '';
    }

    function updateSelectorStatus() {
      var hasMatches = visibleThemeCount > 0;
      var message = '';
      if (hasMatches) {
        message = visibleThemeCount + ' ' + (
          visibleThemeCount === 1
            ? (form && form.dataset.countSingular || 'map available')
            : (form && form.dataset.countPlural || 'maps available')
        );
        message += ' for ' + selectedText(countrySelect);
        if (wasteCategorySelect) message += ' · ' + selectedText(wasteCategorySelect);
      } else {
        message = form && form.dataset.emptyMessage || 'No maps match these filters.';
      }
      if (statusEl) statusEl.textContent = message;
      if (form) form.classList.toggle('atlas-selector-empty', !hasMatches);
      themeSelect.disabled = !hasMatches;
      btnLoad.disabled = !hasMatches;
    }

    function updateToggleChangeLink() {
      if (!btnToggleChange) return;
      var url = selectedCrossLinkUrl();
      if (!url) {
        btnToggleChange.style.display = 'none';
        btnToggleChange.removeAttribute('href');
        return;
      }
      var year = selectedYear();
      var fromYear = selectedFromYear();
      var params = options.useChangeUrls
        ? 'year=' + encodeURIComponent(year)
        : 'from_year=' + encodeURIComponent(fromYear || previousChangeYear(year)) + '&to_year=' + encodeURIComponent(year);
      btnToggleChange.href = url + '?' + params;
      btnToggleChange.style.display = '';
    }

    function ensureVisibleSelection() {
      var currentThemeGroup = selectedThemeGroup();
      var selectedMapSet = countrySelect.value;
      var selectedWasteCategory = wasteCategorySelect ? wasteCategorySelect.value : null;
      var firstVisibleOption = updateThemeVisibility(selectedMapSet, selectedWasteCategory);
      var usingCategoryFallback = false;
      if (!firstVisibleOption && selectedWasteCategory) {
        // Some generic maps are valid for regions that do not have that
        // theme in the route selector; keep the dropdown populated but
        // avoid silently selecting an unrelated route.
        firstVisibleOption = updateThemeVisibility(selectedMapSet, null);
        usingCategoryFallback = true;
      }
      if (!(themeSelect.selectedOptions.length && !themeSelect.selectedOptions[0].disabled)) {
        var nextOption = null;
        if (firstVisibleOption && !usingCategoryFallback) {
          nextOption = findThemeOption(selectedMapSet, selectedWasteCategory, currentThemeGroup);
        }
        if (nextOption) {
          themeSelect.selectedIndex = nextOption.index;
        } else if (firstVisibleOption) {
          themeSelect.selectedIndex = firstVisibleOption.index;
        } else {
          themeSelect.selectedIndex = -1;
        }
      }
      updateSelectorStatus();
      updateToggleChangeLink();
    }

    function navigateOrLoad(event) {
      if (event && event.preventDefault) event.preventDefault();
      ensureVisibleSelection();
      var url = selectedRouteUrl();
      var year = selectedYear();
      var fromYear = selectedFromYear();
      var country = selectedRegion();
      var navigationTarget = _selectorNavigationTarget(url, year, fromYear, country);
      if (navigationTarget && !disableNavigation) {
        window.location.href = navigationTarget;
        return;
      }
      if (loadCurrent) loadCurrent(country, year, false, fromYear, !disableNavigation, url);
    }

    var debouncedNavigateOrLoad = _debounce(navigateOrLoad, options.yearReloadDelay || 250);
    function autoReloadYear() {
      updateToggleChangeLink();
      debouncedNavigateOrLoad();
    }

    countrySelect.addEventListener('change', ensureVisibleSelection);
    if (wasteCategorySelect) wasteCategorySelect.addEventListener('change', ensureVisibleSelection);
    if (themeSearchInput) themeSearchInput.addEventListener('input', ensureVisibleSelection);
    themeSelect.addEventListener('change', ensureVisibleSelection);
    if (yearSelect) yearSelect.addEventListener('change', autoReloadYear);
    if (fromYearSelect) fromYearSelect.addEventListener('change', autoReloadYear);
    if (toYearSelect) toYearSelect.addEventListener('change', autoReloadYear);
    if (form) {
      form.addEventListener('submit', navigateOrLoad);
    } else {
      btnLoad.addEventListener('click', navigateOrLoad);
    }
    ensureVisibleSelection();

    return {
      selectedYear: selectedYear,
      selectedFromYear: selectedFromYear,
      selectedRouteUrl: selectedRouteUrl,
      updateToggleChangeLink: updateToggleChangeLink
    };
  }

  // ---- rendering ------------------------------------------------------------

  function _screenLayout(container) {
    var width = container.clientWidth || 900;
    var height = Math.round(width * 1.17);
    return {
      exportMode: false,
      width: width,
      height: height,
      mapExtent: [[40, 40], [width - 40, height - 100]],
      showHeader: false,
      titleY: 30,
      subtitleY: 50,
      titleFontSize: 18,
      subtitleFontSize: 13
    };
  }

  function _measureTextWidth(text, fontSize, fontWeight) {
    if (!_measureCtx && typeof document !== 'undefined') {
      _measureCtx = document.createElement('canvas').getContext('2d');
    }
    if (!_measureCtx) return String(text).length * fontSize * 0.52;
    _measureCtx.font = (fontWeight ? fontWeight + ' ' : '') + fontSize + 'px ' + EXPORT_LEGEND_FONT_FAMILY;
    return _measureCtx.measureText(text).width;
  }

  function _wrapTextToWidth(label, maxWidth, fontSize) {
    var words = String(label)
      .replace(/\s*\/\s*/g, ' / ')
      .replace(/\s*[–—]\s*/g, ' – ')
      .split(/\s+/)
      .filter(function (word) { return word.length > 0; });
    var lines = [];
    var current = '';
    words.forEach(function (word) {
      var next = current ? current + ' ' + word : word;
      if (_measureTextWidth(next, fontSize) <= maxWidth || !current) {
        current = next;
        if (_measureTextWidth(current, fontSize) <= maxWidth || current.length <= 1) return;
      }
      if (current !== word) {
        lines.push(current);
        current = word;
      }
      while (_measureTextWidth(current, fontSize) > maxWidth && current.length > 1) {
        var part = current;
        while (_measureTextWidth(part, fontSize) > maxWidth && part.length > 1) {
          part = part.slice(0, -1);
        }
        lines.push(part);
        current = current.slice(part.length);
      }
    });
    if (current) lines.push(current);
    return lines;
  }

  function _exportLegendLabel(item) {
    if (item.exportLabel) return item.exportLabel;
    var label = String(item.label);
    if (label.indexOf('No separate biowaste collection') !== -1 ||
      label.indexOf('No separate door-to-door collection') !== -1) {
      return label;
    }
    return label
      .replace(/Biowaste/g, 'Bio')
      .replace(/biowaste/g, 'bio')
      .replace(/Residual waste/g, 'residual')
      .replace(/residual waste/g, 'residual')
      .replace(/every two weeks/g, '2 weeks')
      .replace(/more often/g, 'more')
      .replace(/less frequent/g, 'less')
      .replace(/collected equally often/g, 'equal')
      .replace(/collected more/g, 'more')
      .replace(/collected less/g, 'less')
      .replace(/No door to door biowaste collection/g, 'No separate door-to-door collection')
      .replace(/No door-to-door bio collection/g, 'No separate door-to-door collection')
      .replace(/No separate biowaste collection/g, 'No separate biowaste collection')
      .replace(/No separate bio collection/g, 'No separate biowaste collection');
  }

  function _isNoCollectionCategory(item) {
    var label = String(item.label || '');
    return (
      label.indexOf('No separate biowaste collection') !== -1 ||
      label.indexOf('No separate door-to-door collection') !== -1 ||
      label.indexOf('No separate collection') !== -1 ||
      label.indexOf('No separate green waste collection') !== -1 ||
      label.indexOf('No door-to-door') !== -1
    );
  }

  function _legendItems(cfg, exportMode) {
    var normal = [];
    var noCollection = [];
    cfg.categories.forEach(function (item) {
      if (_isNoCollectionCategory(item)) {
        noCollection.push(item);
      } else {
        normal.push(item);
      }
    });
    var items = [];
    normal.forEach(function (item) {
      items.push(exportMode ? Object.assign({}, item, { label: _exportLegendLabel(item) }) : item);
    });
    noCollection.forEach(function (item) {
      items.push(exportMode ? Object.assign({}, item, { label: _exportLegendLabel(item) }) : item);
    });
    if (cfg.noDataLabel && cfg._hasNoData !== false) {
      items.push({
        label: exportMode && cfg.exportNoDataLabel ? cfg.exportNoDataLabel : cfg.noDataLabel,
        color: cfg.noDataColor || '#e0e0e0'
      });
    }
    return items;
  }

  function _measureExportLegend(cfg, width, columnCount) {
    var swatchSize = Math.round(EXPORT_LEGEND_FONT_SIZE * 0.72);
    var opts = {
      paddingX: 20,
      paddingY: 18,
      swatchW: swatchSize,
      swatchH: swatchSize,
      labelGap: 10,
      rowGap: 8,
      titleGap: 14,
      columnGap: 34,
      columnCount: columnCount || 1,
      fontSize: EXPORT_LEGEND_FONT_SIZE,
      titleFontSize: EXPORT_LEGEND_FONT_SIZE,
      fontFamily: EXPORT_LEGEND_FONT_FAMILY
    };
    opts.lineHeight = Math.round(opts.fontSize * 1.12);
    opts.width = width;
    opts.columnWidth = (
      width - opts.paddingX * 2 - (opts.columnCount - 1) * opts.columnGap
    ) / opts.columnCount;
    opts.textWidth = opts.columnWidth - opts.swatchW - opts.labelGap;
    opts.titleLines = _wrapTextToWidth(
      cfg.exportLegendTitle || cfg.legendTitle || '',
      width - opts.paddingX * 2,
      opts.titleFontSize
    );
    opts.titleHeight = Math.max(opts.titleFontSize, opts.titleLines.length * opts.lineHeight);
    opts.items = _legendItems(cfg, true).map(function (item) {
      var lines = _wrapTextToWidth(item.label, opts.textWidth, opts.fontSize);
      return Object.assign({}, item, {
        lines: lines,
        height: Math.max(opts.swatchH, lines.length * opts.lineHeight)
      });
    });
    opts.columns = [];
    for (var i = 0; i < opts.columnCount; i++) opts.columns.push([]);
    opts.items.forEach(function (item) {
      var shortestIndex = 0;
      opts.columns.forEach(function (column, index) {
        var columnHeight = column.reduce(function (total, columnItem, itemIndex) {
          return total + columnItem.height + (itemIndex ? opts.rowGap : 0);
        }, 0);
        var shortestHeight = opts.columns[shortestIndex].reduce(function (total, columnItem, itemIndex) {
          return total + columnItem.height + (itemIndex ? opts.rowGap : 0);
        }, 0);
        if (columnHeight < shortestHeight) shortestIndex = index;
      });
      opts.columns[shortestIndex].push(item);
    });
    opts.columnHeights = opts.columns.map(function (column) {
      return column.reduce(function (total, item, index) {
        return total + item.height + (index ? opts.rowGap : 0);
      }, 0);
    });
    // Footnote for overlay pattern hint (rendered separately, not as a category)
    opts.footnote = null;
    if (cfg.overlayPatternField && cfg.overlayPatternLegendLabel && cfg._hasOverlayPattern) {
      var footnoteLabel = cfg.exportOverlayPatternLegendLabel || cfg.overlayPatternLegendLabel;
      var footnoteFontSize = Math.round(opts.fontSize * 0.82);
      opts.footnote = {
        lines: _wrapTextToWidth(footnoteLabel, width - opts.paddingX * 2, footnoteFontSize),
        fontSize: footnoteFontSize
      };
      opts.footnoteHeight = opts.footnote.lines.length * Math.round(footnoteFontSize * 1.12)
        + Math.round(opts.fontSize * 0.6);
    } else {
      opts.footnoteHeight = 0;
    }
    opts.height = opts.paddingY * 2 + opts.titleHeight + opts.titleGap
      + Math.max.apply(null, opts.columnHeights) + opts.footnoteHeight;
    return opts;
  }

  function _rectIntersectionArea(a, b) {
    var x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
    var y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
    return x * y;
  }

  function _mapBoundsForExtent(fitData, extent) {
    var projection = d3.geoMercator().fitExtent(extent, fitData);
    var bounds = d3.geoPath().projection(projection).bounds(fitData);
    return {
      x: bounds[0][0],
      y: bounds[0][1],
      width: bounds[1][0] - bounds[0][0],
      height: bounds[1][1] - bounds[0][1],
      scale: projection.scale()
    };
  }

  function _exportLayout(data, cfg) {
    // Ensure cfg._hasNoData is up to date before measuring the legend.
    _annotateFeatures(data, cfg);
    var margin = 46;
    var titleBlock = 46;
    var gap = 46;
    // Use the same logic as main rendering: country border for full maps, Bundesläender for regional maps
    var regionBorder = data.countryBorder;
    if (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length) {
      regionBorder = data.bundeslaender;
    }
    var fitData = (regionBorder && regionBorder.features && regionBorder.features.length)
      ? regionBorder : data.catchments;
    var candidates = [];
    [EXPORT_HEIGHT_MM, 130, 150, 170, EXPORT_MAX_HEIGHT_MM].forEach(function (heightMm) {
      var exportHeight = Math.round(heightMm / 25.4 * EXPORT_DPI);
      [
        { placement: 'right', width: 0.32, columns: 1 },
        { placement: 'right', width: 0.40, columns: 1 },
        { placement: 'left', width: 0.32, columns: 1 },
        { placement: 'left', width: 0.40, columns: 1 },
        { placement: 'bottom-right', width: 0.52, columns: 2, overlay: true },
        { placement: 'bottom-left', width: 0.52, columns: 2, overlay: true },
        { placement: 'top-right', width: 0.52, columns: 2, overlay: true },
        { placement: 'top-left', width: 0.52, columns: 2, overlay: true },
        { placement: 'bottom', width: 0.88, columns: cfg.exportLegendBottomColumns || 3 }
      ].forEach(function (spec) {
        var legend = _measureExportLegend(cfg, Math.round(EXPORT_WIDTH * spec.width), spec.columns);
        var x = margin;
        var y = titleBlock;
        var mapExtent = [[margin, titleBlock], [EXPORT_WIDTH - margin, exportHeight - margin]];
        if (spec.placement === 'right') {
          x = EXPORT_WIDTH - margin - legend.width;
          mapExtent = [[margin, titleBlock], [x - gap, exportHeight - margin]];
        } else if (spec.placement === 'left') {
          x = margin;
          mapExtent = [[x + legend.width + gap, titleBlock], [EXPORT_WIDTH - margin, exportHeight - margin]];
        } else if (spec.placement === 'bottom-right') {
          x = EXPORT_WIDTH - margin - legend.width;
          y = exportHeight - margin - legend.height;
        } else if (spec.placement === 'bottom-left') {
          x = margin;
          y = exportHeight - margin - legend.height;
        } else if (spec.placement === 'top-right') {
          x = EXPORT_WIDTH - margin - legend.width;
          y = titleBlock;
        } else if (spec.placement === 'top-left') {
          x = margin;
          y = titleBlock;
        } else if (spec.placement === 'bottom') {
          x = Math.round((EXPORT_WIDTH - legend.width) / 2);
          y = exportHeight - margin - legend.height;
          mapExtent = [[margin, titleBlock], [EXPORT_WIDTH - margin, y - gap]];
        }
        legend = Object.assign({}, legend, { x: x, y: y });
        candidates.push({
          name: spec.placement,
          heightMm: heightMm,
          height: exportHeight,
          legend: legend,
          mapExtent: mapExtent,
          overlay: Boolean(spec.overlay)
        });
      });
    });
    var best = candidates.reduce(function (selected, candidate) {
      var legendOverflow = Math.max(0, margin - candidate.legend.y)
        + Math.max(0, candidate.legend.y + candidate.legend.height - (candidate.height - margin))
        + Math.max(0, margin - candidate.legend.x)
        + Math.max(0, candidate.legend.x + candidate.legend.width - (EXPORT_WIDTH - margin));
      var mapW = candidate.mapExtent[1][0] - candidate.mapExtent[0][0];
      var mapH = candidate.mapExtent[1][1] - candidate.mapExtent[0][1];
      var invalidMap = mapW <= 0 || mapH <= 0;
      var mapBounds = invalidMap
        ? { x: 0, y: 0, width: 0, height: 0, scale: 0 }
        : _mapBoundsForExtent(fitData, candidate.mapExtent);
      var legendRect = {
        x: candidate.legend.x,
        y: candidate.legend.y,
        width: candidate.legend.width,
        height: candidate.legend.height
      };
      var overlap = _rectIntersectionArea(mapBounds, legendRect);
      var legendArea = candidate.legend.width * candidate.legend.height;
      var invalidOverlay = candidate.overlay && overlap > legendArea * 0.02;
      var mapArea = mapBounds.width * mapBounds.height;
      var usedArea = mapArea + legendArea - overlap;
      candidate.score = mapBounds.scale * 100000 + usedArea / 1000
        - (candidate.heightMm - EXPORT_HEIGHT_MM) * 120000
        - legendOverflow * 1000000
        - overlap * 1000
        - (invalidOverlay ? 1000000000 : 0)
        - (invalidMap ? 1000000000 : 0);
      if (!selected || candidate.score > selected.score) return candidate;
      return selected;
    }, null);
    return {
      exportMode: true,
      width: EXPORT_WIDTH,
      height: best.height,
      widthMm: EXPORT_WIDTH_MM,
      heightMm: best.heightMm,
      mapExtent: best.mapExtent,
      showHeader: false,
      titleY: 50,
      subtitleY: 82,
      titleFontSize: 38,
      subtitleFontSize: 22,
      legend: best.legend
    };
  }

  // ---- quartile helpers -----------------------------------------------------

  function _computeQuartileCategories(values, colors) {
    var valid = values.filter(function (v) { return v != null && !isNaN(v); });
    if (valid.length < 4) return null;
    var sorted = valid.slice().sort(function (a, b) { return a - b; });
    var q1 = d3.quantile(sorted, 0.25);
    var q2 = d3.quantile(sorted, 0.50);
    var q3 = d3.quantile(sorted, 0.75);
    var min = sorted[0];
    var max = sorted[sorted.length - 1];
    colors = colors || ['#d9f0d3', '#a6d96a', '#66bd63', '#1a9850'];

    function fmt(v) {
      if (v == null) return '';
      return Math.round(v).toString();
    }

    return [
      { value: 'q1', label: fmt(min) + ' – ' + fmt(q1) + ' (Q1)', color: colors[0], threshold: q1 },
      { value: 'q2', label: fmt(q1) + ' – ' + fmt(q2) + ' (Q2)', color: colors[1], threshold: q2 },
      { value: 'q3', label: fmt(q2) + ' – ' + fmt(q3) + ' (Q3)', color: colors[2], threshold: q3 },
      { value: 'q4', label: fmt(q3) + ' – ' + fmt(max) + ' (Q4)', color: colors[3], threshold: Infinity }
    ];
  }

  function _quartileClassify(value, categories) {
    if (value == null || isNaN(value)) return null;
    if (value <= categories[0].threshold) return 'q1';
    if (value <= categories[1].threshold) return 'q2';
    if (value <= categories[2].threshold) return 'q3';
    return 'q4';
  }

  function _isQuartileEnabled(cfg) {
    return cfg.numericField && cfg.quartileColors && cfg.enableQuartiles !== false;
  }

  function _legacyRecordLookup(baseCfg, records) {
    var legacyRecords = records;
    if (typeof baseCfg.transformData === 'function') {
      legacyRecords = baseCfg.transformData(records);
    } else if (baseCfg.transformName && transforms[baseCfg.transformName]) {
      legacyRecords = transforms[baseCfg.transformName](records);
    }
    var lookup = {};
    legacyRecords.forEach(function (r) { lookup[r.catchment_id] = r; });
    return lookup;
  }

  function _applyQuartiles(baseCfg, records) {
    if (!_isQuartileEnabled(baseCfg)) return baseCfg;
    var specialCases = baseCfg.quartileSpecialCases || [];
    var preserveClasses = baseCfg.quartilePreserveClasses || [];
    var preserveClassLookup = {};
    preserveClasses.forEach(function (value) { preserveClassLookup[value] = true; });
    var preservedCategories = baseCfg.categories.filter(function (cat) {
      return preserveClassLookup[cat.value];
    });
    var legacyLookup = preserveClasses.length ? _legacyRecordLookup(baseCfg, records) : {};

    function isPreservedRecord(r) {
      var legacy = legacyLookup[r.catchment_id];
      var legacyClass = legacy ? legacy[baseCfg.dataField] : null;
      return Boolean(legacyClass && preserveClassLookup[legacyClass]);
    }

    function isSpecialCaseRecord(r) {
      return specialCases.some(function (sc) { return Boolean(r[sc.field]); });
    }

    var values = records
      .filter(function (r) { return !isPreservedRecord(r) && !isSpecialCaseRecord(r); })
      .map(function (r) { return r[baseCfg.numericField]; });
    var categories = _computeQuartileCategories(values, baseCfg.quartileColors);
    if (!categories) return baseCfg;

    var allCategories = preservedCategories.concat(specialCases.map(function (sc) {
      return { value: sc.classValue, label: sc.label, color: sc.color };
    })).filter(function (cat, index, items) {
      return items.findIndex(function (item) { return item.value === cat.value; }) === index;
    }).concat(categories);

    return Object.assign({}, baseCfg, {
      categories: allCategories,
      transformName: null,
      transformData: function (records) {
        return records.map(function (r) {
          var result = Object.assign({}, r);
          // Preserve ACPV overlay metadata used by the renderer
          if (r.value_source !== undefined) {
            result._has_acpv_overlay = r.value_source === 'acpv';
          }
          if (r.acpv_group_key !== undefined) {
            result._acpv_group_key = r.acpv_group_key;
          }
          var cls = null;
          var legacy = legacyLookup[r.catchment_id];
          var legacyClass = legacy ? legacy[baseCfg.dataField] : null;
          if (legacyClass && preserveClassLookup[legacyClass]) {
            cls = legacyClass;
          }
          for (var i = 0; i < specialCases.length; i++) {
            var sc = specialCases[i];
            if (cls === null && r[sc.field]) {
              cls = sc.classValue;
              break;
            }
          }
          if (cls === null) {
            var v = r[baseCfg.numericField];
            cls = _quartileClassify(v, categories);
          }
          result._classified = cls;
          return result;
        });
      }
    });
  }

  // ---- named transform registry -------------------------------------------
  var transforms = {
    biowasteCollectionAmount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.no_collection) {
          cls = 'no_bio';
        } else if (r.amount === null) {
          cls = null;
        } else if (r.amount > 150) {
          cls = 'very_high';
        } else if (r.amount > 100) {
          cls = 'high';
        } else if (r.amount > 50) {
          cls = 'medium';
        } else {
          cls = 'low';
        }
        return {
          catchment_id: r.catchment_id,
          _classified: cls,
          _has_acpv_overlay: r.value_source === 'acpv',
          _acpv_group_key: r.acpv_group_key
        };
      });
    },
    biowasteCollectionCount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.is_door_to_door === false) {
          cls = 'no_door_to_door';
        } else if (r.collection_count === null) {
          cls = null;
        } else if (r.has_seasonal_variation) {
          cls = 'seasonal';
        } else if (r.collection_count >= 104) {
          cls = 'twice_weekly';
        } else if (r.collection_count >= 52) {
          cls = 'weekly';
        } else if (r.collection_count >= 26) {
          cls = 'biweekly';
        } else {
          cls = 'less_frequent';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    biowasteCollectionPointCount: function (records) {
      return records.map(function (r) {
        var value = r.collection_point_count;
        var cls;
        if (value === null || value === undefined) {
          cls = r.is_door_to_door ? 'full_dtd' : null;
        } else if (value >= 59) {
          cls = 'very_high';
        } else if (value >= 10) {
          cls = 'high';
        } else if (value >= 2) {
          cls = 'medium';
        } else {
          cls = 'very_low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    biowasteFrequency: function (records) {
      var NO_BIO = ['No separate collection', 'Bring point', 'Recycling centre',
        'On demand kerbside collection', 'Home-composting'];
      return records.map(function (r) {
        var cls = NO_BIO.indexOf(r.frequency_type) !== -1
          ? 'no_bio_collection'
          : r.frequency_type;
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    biowasteImpurity: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.no_collection) {
          cls = 'no_collection';
        } else if (r.impurity_rate === null) {
          cls = null;
        } else if (r.impurity_rate <= 5) {
          cls = 'very_low';
        } else if (r.impurity_rate <= 10) {
          cls = 'low';
        } else if (r.impurity_rate <= 20) {
          cls = 'medium';
        } else if (r.impurity_rate <= 40) {
          cls = 'high';
        } else {
          cls = 'very_high';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    biowasteMinBinSize: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.is_door_to_door === false) {
          cls = 'no_door_to_door';
        } else if (r.min_bin_size === null) {
          cls = null;
        } else if (r.min_bin_size <= 26.5) {
          cls = 'xs';
        } else if (r.min_bin_size <= 60) {
          cls = 'small';
        } else if (r.min_bin_size <= 120) {
          cls = 'medium';
        } else {
          cls = 'large';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    biowasteRequiredBinCapacity: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.is_door_to_door === false) {
          cls = 'no_door_to_door';
        } else if (r.required_bin_capacity === null) {
          cls = null;
        } else if (r.required_bin_capacity <= 5) {
          cls = 'very_low';
        } else if (r.required_bin_capacity <= 10) {
          cls = 'low';
        } else if (r.required_bin_capacity <= 20) {
          cls = 'medium';
        } else if (r.required_bin_capacity <= 60) {
          cls = 'high';
        } else {
          cls = 'very_high';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    collectionCountRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.bio_is_door_to_door === false ||
          (r.bio_is_door_to_door == null && r.residual_count != null)) {
          cls = 'no_bio';
        } else if (r.bio_has_seasonal_variation) {
          cls = 'seasonal';
        } else if (r.bio_count === null || r.bio_count === undefined) {
          cls = null;
        } else if (r.ratio === null || r.ratio === undefined) {
          cls = null;
        } else if (r.ratio > 1.5) {
          cls = 'bio_2x';
        } else if (r.ratio < 0.67) {
          cls = 'bio_half';
        } else {
          cls = 'same';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    collectionPointCount: function (records) {
      return records.map(function (r) {
        var value = r.collection_point_count;
        var cls;
        if (value === null || value === undefined) {
          cls = r.is_door_to_door ? 'full_dtd' : null;
        } else if (value > 10) {
          cls = 'high';
        } else if (value > 5) {
          cls = 'medium';
        } else if (value > 1) {
          cls = 'low';
        } else {
          cls = 'very_low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    collectionPointCountRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.bio_is_door_to_door === false ||
          (r.bio_is_door_to_door == null && r.residual_count != null)) {
          cls = 'no_bio';
        } else if (r.bio_count === null || r.bio_count === undefined) {
          cls = null;
        } else if (r.ratio === null || r.ratio === undefined) {
          cls = null;
        } else if (r.ratio > 1.05) {
          cls = 'bio_more';
        } else if (r.ratio < 0.95) {
          cls = 'bio_less';
        } else {
          cls = 'same';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    collectionSupport: function (records) {
      var KEY_MAP = {
        'allowed': 'a',
        'forbidden': 'f',
        'no_data': 'n'
      };
      return records.map(function (r) {
        var cls;
        if (r.paper_bags === 'no_collection') {
          cls = 'no_collection';
        } else {
          var p = KEY_MAP[r.paper_bags] || 'n';
          var b = KEY_MAP[r.plastic_bags] || 'n';
          cls = 'paper_' + p + '_plastic_' + b;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    combinedCollectionCount: function (records) {
      function bucket(count) {
        if (count === null || count === undefined) return null;
        if (count > 26) return 'more';
        if (count >= 24) return 'bi';
        return 'less';
      }
      return records.map(function (r) {
        var b = bucket(r.bio_count);
        var re = bucket(r.residual_count);
        var cls;
        if (r.bio_is_door_to_door === false ||
          (r.bio_is_door_to_door == null && r.residual_count != null)) {
          cls = 'no_bio';
        } else if (b === null) {
          cls = null;
        } else if (re === null) {
          cls = null;
        } else {
          cls = 'bio_' + b + '_res_' + re;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    combinedCollectionSystem: function (records) {
      return records.map(function (r) {
        var bio = r.bio_collection_system;
        var residual = r.residual_collection_system;
        return {
          catchment_id: r.catchment_id,
          _classified: bio && residual ? bio + ' / ' + residual : null
        };
      });
    },
    combinedFeeSystem: function (records) {
      return records.map(function (r) {
        var cls;
        var noSep = ['No separate collection', 'Recycling centre', 'Bring point'];
        if (noSep.indexOf(r.bio_fee) !== -1) {
          cls = 'no_bio';
        } else if (r.bio_fee === 'Flexible' && r.residual_fee === 'Flexible') {
          cls = 'flex_flex';
        } else if (r.bio_fee === 'No fee' && r.residual_fee === 'Flexible') {
          cls = 'no_fee_flex';
        } else if (r.bio_fee === 'No fee' && r.residual_fee === 'Pay as you throw (PAYT)') {
          cls = 'no_fee_payt';
        } else if (r.bio_fee === 'Pay as you throw (PAYT)' && r.residual_fee === 'Pay as you throw (PAYT)') {
          cls = 'payt_payt';
        } else if (r.bio_fee === 'Flexible' && r.residual_fee === 'Pay as you throw (PAYT)') {
          cls = 'flex_payt';
        } else if (r.bio_fee === 'Flexible' && r.residual_fee === 'Flexible+') {
          cls = 'flex_flex_plus';
        } else if (r.bio_fee && r.residual_fee && r.bio_fee !== 'no_data' && r.residual_fee !== 'no_data') {
          cls = 'other_combined';
        } else {
          cls = null;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    combinedFrequency: function (records) {
      var TYPE_KEY = {
        'Fixed': 'fixed',
        'Fixed-Flexible': 'flexible',
        'Fixed-Seasonal': 'seasonal'
      };
      var NO_BIO = ['No separate collection', 'Bring point', 'Recycling centre',
        'On demand kerbside collection', 'Home-composting'];
      return records.map(function (r) {
        var cls;
        if (NO_BIO.indexOf(r.bio_frequency) !== -1) {
          cls = 'no_bio_collection';
        } else {
          var b = TYPE_KEY[r.bio_frequency] || 'unknown';
          var re = TYPE_KEY[r.residual_frequency] || 'unknown';
          cls = 'bio_' + b + '_res_' + re;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    connectionRate: function (records) {
      return records.map(function (r) {
        var cls;
        if (!r.is_door_to_door) {
          cls = 'no_d2d';
        } else if (r.connection_rate == null) {
          cls = null;
        } else if (r.connection_rate >= 0.75) {
          cls = '75-100';
        } else if (r.connection_rate >= 0.50) {
          cls = '50-74';
        } else if (r.connection_rate >= 0.25) {
          cls = '25-49';
        } else {
          cls = '0-24';
        }
        return Object.assign({}, r, { _classified: cls });
      });
    },
    denmarkCollectionSupport: function (records) {
      var KEY_MAP = {
        'allowed': 'a',
        'forbidden': 'f',
        'no_data': 'n'
      };
      return records.map(function (r) {
        var cls;
        if (r.paper_bags === 'no_collection') {
          cls = 'no_collection';
        } else {
          var p = KEY_MAP[r.paper_bags] || 'n';
          var b = KEY_MAP[r.plastic_bags] || 'n';
          cls = 'paper_' + p + '_plastic_' + b;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    greenWasteCollectionAmount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.no_collection) {
          cls = 'no_green';
        } else if (r.amount === null) {
          cls = null;
        } else if (r.amount > 150) {
          cls = 'very_high';
        } else if (r.amount > 100) {
          cls = 'high';
        } else if (r.amount > 50) {
          cls = 'medium';
        } else {
          cls = 'low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    minBinSizeRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.bio_is_door_to_door === false ||
          (r.bio_is_door_to_door == null && r.residual_min_bin_size != null)) {
          cls = 'no_bio';
        } else if (r.bio_min_bin_size === null || r.bio_min_bin_size === undefined) {
          cls = null;
        } else if (r.ratio === null || r.ratio === undefined) {
          cls = null;
        } else if (r.ratio > 1.05) {
          cls = 'bio_larger';
        } else if (r.ratio < 0.95) {
          cls = 'bio_smaller';
        } else {
          cls = 'same';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    organicCollectionAmount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.amount === null) {
          cls = null;
        } else if (r.amount > 300) {
          cls = 'very_high';
        } else if (r.amount > 200) {
          cls = 'high';
        } else if (r.amount > 100) {
          cls = 'medium';
        } else if (r.amount > 50) {
          cls = 'low';
        } else {
          cls = 'very_low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    organicWasteRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.ratio === null) {
          cls = null;
        } else if (r.ratio > 0.66) {
          cls = 'very_high';
        } else if (r.ratio > 0.50) {
          cls = 'high';
        } else if (r.ratio > 0.33) {
          cls = 'medium';
        } else {
          cls = 'low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    residualCollectionAmount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.amount === null) {
          cls = null;
        } else if (r.amount > 225) {
          cls = 'high';
        } else if (r.amount > 150) {
          cls = 'medium';
        } else if (r.amount > 75) {
          cls = 'low';
        } else {
          cls = 'very_low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    residualCollectionCount: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.has_seasonal_variation) {
          cls = 'seasonal';
        } else if (r.collection_count >= 104) {
          cls = 'twice_weekly';
        } else if (r.collection_count >= 52) {
          cls = 'weekly';
        } else if (r.collection_count >= 26) {
          cls = 'biweekly';
        } else {
          cls = 'less_frequent';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    residualCollectionPointCount: function (records) {
      return records.map(function (r) {
        var value = r.collection_point_count;
        var cls;
        if (value === null || value === undefined) {
          cls = r.is_door_to_door ? 'full_dtd' : null;
        } else if (value >= 121) {
          cls = 'very_high';
        } else if (value >= 59) {
          cls = 'high';
        } else if (value >= 8) {
          cls = 'medium';
        } else {
          cls = 'low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    residualMinBinSize: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.min_bin_size === null) {
          cls = null;
        } else if (r.min_bin_size <= 30) {
          cls = 'xs';
        } else if (r.min_bin_size <= 60) {
          cls = 'small';
        } else if (r.min_bin_size <= 120) {
          cls = 'medium';
        } else {
          cls = 'large';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    residualRequiredBinCapacity: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.required_bin_capacity === null) {
          cls = null;
        } else if (r.required_bin_capacity <= 10) {
          cls = 'very_low';
        } else if (r.required_bin_capacity <= 20) {
          cls = 'low';
        } else if (r.required_bin_capacity <= 40) {
          cls = 'medium';
        } else if (r.required_bin_capacity <= 80) {
          cls = 'high';
        } else {
          cls = 'very_high';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    wasteRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.ratio === null) {
          if (r.bio_amount === null && r.residual_amount !== null) {
            cls = 'no_bio';
          } else {
            cls = null;
          }
        } else if (r.ratio > 0.66) {
          cls = 'very_high';
        } else if (r.ratio > 0.50) {
          cls = 'high';
        } else if (r.ratio > 0.33) {
          cls = 'low';
        } else {
          cls = 'very_low';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    weeklyBpAccessDays: function (records) {
      return records.map(function (r) {
        var cls;
        if (!r.has_bring_point) {
          cls = 'no_bp';
        } else if (r.weekly_access_days === null) {
          cls = null;
        } else if (r.weekly_access_days >= 7) {
          cls = '7';
        } else if (r.weekly_access_days >= 5) {
          cls = '5_6';
        } else if (r.weekly_access_days >= 3) {
          cls = '3_4';
        } else {
          cls = '1_2';
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    greenWasteCollectionSystemCount: function (records) {
      return records.map(function (r) {
        var v = r.collection_system_count;
        var cls = null;
        if (v != null) {
          if (v >= 3) { cls = '3plus'; }
          else if (v === 2) { cls = '2'; }
          else if (v === 1) { cls = '1'; }
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    populationDensity: function (records) {
      return records.map(function (r) {
        var v = r.population_density;
        var cls = null;
        if (v != null) {
          if (v > 1500) { cls = 'urban'; }
          else if (v >= 300) { cls = 'suburban'; }
          else { cls = 'rural'; }
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
  };

  function _render(data, cfg, options) {
    options = options || {};
    // Merge thematic data into catchment features
    _annotateFeatures(data, cfg);

    // SVG dimensions
    var container = document.getElementById(cfg.containerId);
    var layout = options.layout || _screenLayout(container);
    var width = layout.width;
    var height = layout.height;

    _svg = options.svgSelection || d3.select('#' + cfg.svgId);
    _svg
      .attr('xmlns', 'http://www.w3.org/2000/svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', '0 0 ' + width + ' ' + height)
      .style('background', '#fff');

    _svg.selectAll('*').remove();
    _defineOverlayPattern(cfg);

    // Projection — fit to country border (or filtered regions when nutsPrefix is set)
    var regionBorder = (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
    var fitData = (regionBorder && regionBorder.features && regionBorder.features.length)
      ? regionBorder : data.catchments;
    var projection = d3.geoMercator()
      .fitExtent(layout.mapExtent, fitData);
    var path = d3.geoPath().projection(projection);

    // Layer 1: background fill (filtered NUTS1 regions when nutsPrefix set, else full country)
    var fillData = (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
    if (fillData && fillData.features) {
      _svg.append('g').attr('class', 'layer-country-fill')
        .selectAll('path')
        .data(fillData.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', COUNTRY_FILL)
        .attr('stroke', 'none');
    }

    // Layer 2: all catchments (border-only background for those without data this year)
    if (data.allCatchments && data.allCatchments.features) {
      _svg.append('g').attr('class', 'layer-catchments-all')
        .selectAll('path')
        .data(data.allCatchments.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', CATCHMENT_STROKE)
        .attr('stroke-width', CATCHMENT_STROKE_WIDTH);
    }

    // Layer 3: catchments with data (thin borders)
    if (data.catchments.features) {
      _svg.append('g').attr('class', 'layer-catchments')
        .selectAll('path')
        .data(data.catchments.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', function (d) {
          return _colorFor(d.properties._thematic_value, cfg.categories, cfg.noDataColor);
        })
        .attr('stroke', CATCHMENT_STROKE)
        .attr('stroke-width', CATCHMENT_STROKE_WIDTH)
        .append('title')
        .text(function (d) {
          var p = d.properties;
          var val = p._thematic_value != null ? String(p._thematic_value) : 'no data';
          var tooltip = p.catchment_name + ' — ' + val;
          if (Array.isArray(cfg.tooltipFields) && p._thematic_record) {
            cfg.tooltipFields.forEach(function (field) {
              var fieldValue = p._thematic_record[field.field];
              if (fieldValue != null && fieldValue !== '') {
                tooltip += '\n' + field.label + ': ' + fieldValue;
              }
            });
          }
          if (_conflictEnabled && !layout.exportMode && _conflictDetails && _conflictDetails[p.catchment_id]) {
            var detail = _conflictDetails[p.catchment_id];
            tooltip += '\n⚠ Conflicting collections (' + detail.distinct_count + '): '
              + detail.distinct_values.join(', ');
          }
          return tooltip;
        });
    }

    if (cfg.overlayPatternField && data.catchments.features) {
      _svg.append('g').attr('class', 'layer-catchments-overlay')
        .selectAll('path')
        .data(data.catchments.features.filter(function (d) {
          return d.properties._overlay_pattern && d.properties._thematic_value != null;
        }))
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'url(#' + _overlayPatternId(cfg) + ')')
        .attr('stroke', 'none')
        .style('pointer-events', 'none');
    }

    if (data.acpvOutlines && data.acpvOutlines.features) {
      _svg.append('g').attr('class', 'layer-acpv-outlines')
        .selectAll('path')
        .data(data.acpvOutlines.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', cfg.outlineStrokeColor || '#ffffff')
        .attr('stroke-opacity', cfg.outlineStrokeOpacity == null ? 0.95 : cfg.outlineStrokeOpacity)
        .attr('stroke-width', cfg.outlineStrokeWidth || 1.35)
        .attr('stroke-linejoin', 'round')
        .attr('stroke-linecap', 'round')
        .style('pointer-events', 'none');
    }

    // Maintainer aid: outline catchments whose theme value is ambiguous
    // (more than one collection competes for the single displayed slot).
    // Screen-only: the export legend carries no conflict entry, so drawing
    // the outlines in exports would leave them unexplained.
    if (_conflictEnabled && !layout.exportMode && _conflictCatchments && _conflictCatchments.size && data.catchments.features) {
      _svg.append('g').attr('class', 'layer-catchments-conflict')
        .selectAll('path')
        .data(data.catchments.features.filter(function (d) {
          return _conflictCatchments.has(d.properties.catchment_id);
        }))
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', CONFLICT_STROKE)
        .attr('stroke-width', CONFLICT_STROKE_WIDTH)
        .attr('stroke-dasharray', CONFLICT_STROKE_DASHARRAY)
        .attr('stroke-linejoin', 'round')
        .style('pointer-events', 'none');
    }

    var hasRegionalBorder = cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features
      && data.bundeslaender.features.length;

    // Layer 4: Bundesländer borders (on top of catchments)
    if (!hasRegionalBorder && data.bundeslaender && data.bundeslaender.features) {
      _svg.append('g').attr('class', 'layer-bundeslaender')
        .selectAll('path')
        .data(data.bundeslaender.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', BUNDESLAND_STROKE)
        .attr('stroke-width', BUNDESLAND_STROKE_WIDTH);
    }

    // Layer 5: outer border (very top) — always show country border for full maps,
    // but show Bundesläender borders as outer border for regional maps (when nutsPrefix is set)
    var borderData = data.countryBorder;
    var borderStroke = COUNTRY_STROKE;
    var borderWidth = COUNTRY_STROKE_WIDTH;

    if (hasRegionalBorder) {
      // For regional maps (with nutsPrefix), use Bundesläender as outer border instead of country border
      borderData = data.bundeslaender;
      // Don't draw Bundesläender borders in layer 4 since we're drawing them as outer border
    }

    if (borderData && borderData.features) {
      _svg.append('g').attr('class', 'layer-country-border')
        .selectAll('path')
        .data(borderData.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', borderStroke)
        .attr('stroke-width', borderWidth);
    }

    if (layout.showHeader !== false) {
      // Title
      _svg.append('text')
        .attr('x', width / 2).attr('y', layout.titleY)
        .attr('text-anchor', 'middle')
        .attr('font-family', "'Nunito', sans-serif")
        .attr('font-size', layout.titleFontSize).attr('font-weight', 'bold')
        .text(cfg.title);

      // Subtitle / count
      var count = data.catchments.features ? data.catchments.features.length : 0;
      var subtitle = cfg.subtitle || (count + ' catchments');
      _svg.append('text')
        .attr('x', width / 2).attr('y', layout.subtitleY)
        .attr('text-anchor', 'middle')
        .attr('font-family', "'Nunito', sans-serif")
        .attr('font-size', layout.subtitleFontSize).attr('fill', '#666')
        .text(subtitle);
    }

    // Legend
    _drawLegend(width, height, cfg, layout);
  }

  function _drawExportLegendItem(g, cat, x, y, opts) {
    var itemHeight = Math.max(opts.swatchH, cat.lines.length * opts.lineHeight);
    var textBaselineY = y + opts.fontSize;
    var capCenterY = textBaselineY - Math.round(opts.fontSize * 0.36);
    var swatchY = capCenterY - Math.round(opts.swatchH / 2);
    g.append('rect')
      .attr('x', x).attr('y', swatchY)
      .attr('width', opts.swatchW).attr('height', opts.swatchH)
      .attr('fill', cat.color).attr('stroke', '#333');
    var textX = x + opts.swatchW + opts.labelGap;
    var text = g.append('text')
      .attr('x', textX).attr('y', textBaselineY)
      .attr('font-size', opts.fontSize)
      .attr('font-family', opts.fontFamily);
    cat.lines.forEach(function (line, index) {
      text.append('tspan')
        .attr('x', textX)
        .attr('dy', index === 0 ? 0 : opts.lineHeight)
        .text(line);
    });
    return itemHeight + opts.rowGap;
  }

  function _drawLegend(width, height, cfg, layout) {
    var swatchW = 22, swatchH = 16, gap = 6;
    var items = _legendItems(cfg);
    var hasOverlayLegend = cfg.overlayPatternField && cfg.overlayPatternLegendLabel && cfg._hasOverlayPattern;
    var hasConflictLegend = !!(_conflictEnabled && cfg.conflictOverlayLabel
      && _conflictCatchments && _conflictCatchments.size);
    var legendRows = items.length + (hasOverlayLegend ? 1 : 0)
      + (hasConflictLegend ? 1 : 0);

    if (layout.exportMode) {
      var opts = layout.legend;
      opts.cfg = cfg;
      var gExport = _svg.append('g')
        .attr('class', 'atlas-legend')
        .attr('transform', 'translate(' + opts.x + ',' + opts.y + ')');
      var columnStartY = opts.paddingY + opts.titleHeight + opts.titleGap;
      opts.columns.forEach(function (column, columnIndex) {
        var x = opts.paddingX + columnIndex * (opts.columnWidth + opts.columnGap);
        var y = columnStartY;
        column.forEach(function (cat, itemIndex) {
          if (itemIndex) y += opts.rowGap;
          y += _drawExportLegendItem(gExport, cat, x, y, opts) - opts.rowGap;
        });
      });
      // Footnote: overlay pattern hint (separate from legend categories)
      if (opts.footnote) {
        var footnoteY = columnStartY + Math.max.apply(null, opts.columnHeights)
          + Math.round(opts.fontSize * 0.3);
        gExport.append('line')
          .attr('x1', opts.paddingX).attr('y1', footnoteY)
          .attr('x2', opts.width - opts.paddingX).attr('y2', footnoteY)
          .attr('stroke', '#d0d4da').attr('stroke-width', 1);
        var footnoteText = gExport.append('text')
          .attr('x', opts.paddingX)
          .attr('y', footnoteY + Math.round(opts.footnote.fontSize * 1.12))
          .attr('font-size', opts.footnote.fontSize)
          .attr('font-style', 'italic')
          .attr('fill', '#6c757d')
          .attr('font-family', opts.fontFamily);
        opts.footnote.lines.forEach(function (line, index) {
          footnoteText.append('tspan')
            .attr('x', opts.paddingX)
            .attr('dy', index === 0 ? 0 : Math.round(opts.footnote.fontSize * 1.12))
            .text(line);
        });
      }
      gExport.insert('rect', ':first-child')
        .attr('x', 0).attr('y', 0)
        .attr('width', opts.width).attr('height', opts.height)
        .attr('fill', 'white').attr('fill-opacity', 0.94)
        .attr('stroke', '#c9ced6').attr('rx', 8);
      var titleText = gExport.insert('text', ':nth-child(2)')
        .attr('x', opts.paddingX).attr('y', opts.paddingY + opts.titleFontSize - 4)
        .attr('font-weight', 'bold').attr('font-size', opts.titleFontSize)
        .attr('font-family', opts.fontFamily);
      opts.titleLines.forEach(function (line, index) {
        titleText.append('tspan')
          .attr('x', opts.paddingX)
          .attr('dy', index === 0 ? 0 : opts.lineHeight)
          .text(line);
      });
      return;
    }

    var normalCats = [];
    var noCollectionCats = [];
    cfg.categories.forEach(function (item) {
      if (_isNoCollectionCategory(item)) {
        noCollectionCats.push(item);
      } else {
        normalCats.push(item);
      }
    });
    items = normalCats.concat(noCollectionCats);
    legendRows = items.length + (hasConflictLegend ? 1 : 0);

    if (cfg.noDataLabel && cfg._hasNoData !== false) {
      legendRows += 1;
    }

    // Overlay footnote takes less space than a full legend row
    var overlayFootnoteH = hasOverlayLegend ? 28 : 0;

    var g = _svg.append('g')
      .attr('class', 'atlas-legend')
      .attr('transform', 'translate(40,' + (height - 30 - legendRows * (swatchH + gap) - overlayFootnoteH - 20) + ')');

    var totalH = legendRows * (swatchH + gap) + overlayFootnoteH + gap + 20;
    g.append('rect')
      .attr('x', -8).attr('y', -20)
      .attr('width', 300).attr('height', totalH)
      .attr('fill', 'white').attr('fill-opacity', 0.9)
      .attr('stroke', '#ccc').attr('rx', 4);

    g.append('text')
      .attr('x', 0).attr('y', -4)
      .attr('font-weight', 'bold').attr('font-size', 12)
      .attr('font-family', "'Nunito', sans-serif")
      .text(cfg.legendTitle || '');

    items.forEach(function (cat, i) {
      var y = i * (swatchH + gap);
      g.append('rect')
        .attr('x', 0).attr('y', y + 4)
        .attr('width', swatchW).attr('height', swatchH)
        .attr('fill', cat.color).attr('stroke', '#333');
      g.append('text')
        .attr('x', swatchW + 8).attr('y', y + 4 + swatchH - 3)
        .attr('font-size', 12)
        .attr('font-family', "'Nunito', sans-serif")
        .text(cat.label);
    });

    var currentY = items.length * (swatchH + gap);

    if (hasConflictLegend) {
      g.append('rect')
        .attr('x', 0).attr('y', currentY + 4)
        .attr('width', swatchW).attr('height', swatchH)
        .attr('fill', '#ffffff')
        .attr('stroke', CONFLICT_STROKE)
        .attr('stroke-width', 1.4)
        .attr('stroke-dasharray', CONFLICT_STROKE_DASHARRAY);
      g.append('text')
        .attr('x', swatchW + 8).attr('y', currentY + 4 + swatchH - 3)
        .attr('font-size', 12)
        .attr('font-family', "'Nunito', sans-serif")
        .text(cfg.conflictOverlayLabel);
      currentY += swatchH + gap;
    }

    if (cfg.noDataLabel && cfg._hasNoData !== false) {
      g.append('rect')
        .attr('x', 0).attr('y', currentY + 4)
        .attr('width', swatchW).attr('height', swatchH)
        .attr('fill', cfg.noDataColor || '#e0e0e0').attr('stroke', '#333');
      g.append('text')
        .attr('x', swatchW + 8).attr('y', currentY + 4 + swatchH - 3)
        .attr('font-size', 12)
        .attr('font-family', "'Nunito', sans-serif")
        .text(cfg.noDataLabel);
      currentY += swatchH + gap;
    }

    if (hasOverlayLegend) {
      // Footnote: thin separator + small italic text (not a legend category)
      var footnoteLineY = currentY + 6;
      g.append('line')
        .attr('x1', 0).attr('y1', footnoteLineY)
        .attr('x2', 280).attr('y2', footnoteLineY)
        .attr('stroke', '#d0d4da').attr('stroke-width', 1);
      g.append('text')
        .attr('x', 0).attr('y', footnoteLineY + 14)
        .attr('font-size', 10)
        .attr('font-style', 'italic')
        .attr('fill', '#6c757d')
        .attr('font-family', "'Nunito', sans-serif")
        .text(cfg.overlayPatternLegendLabel);
    }
  }

  // ---- export ---------------------------------------------------------------

  function _svgSource(svgEl) {
    svgEl = svgEl || document.getElementById(_cfg.svgId);
    var serializer = new XMLSerializer();
    var source = serializer.serializeToString(svgEl);
    if (!source.match(/^<svg[^>]+xmlns/)) {
      source = source.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    if (source.indexOf('data-waste-atlas-export-font') === -1) {
      source = source.replace(
        /<svg([^>]*)>/,
        '<svg$1><style data-waste-atlas-export-font="true">text{font-family:Nunito,Calibri,Carlito,Arial,sans-serif;}</style>'
      );
    }
    return '<?xml version="1.0" standalone="no"?>\r\n' + source;
  }

  function _buildExportSVGElement() {
    if (!_lastData || !_lastLoadCfg) return document.getElementById(_cfg.svgId);
    var node = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    var layout = _exportLayout(_lastData, _lastLoadCfg);
    node.__wasteAtlasExportLayout = layout;
    _render(_lastData, _lastLoadCfg, {
      layout: layout,
      svgSelection: d3.select(node)
    });
    d3.select(node)
      .attr('width', node.__wasteAtlasExportLayout.widthMm + 'mm')
      .attr('height', node.__wasteAtlasExportLayout.heightMm + 'mm')
      .attr(
        'viewBox',
        '0 0 ' + node.__wasteAtlasExportLayout.width + ' ' + node.__wasteAtlasExportLayout.height
      );
    _svg = d3.select('#' + _cfg.svgId);
    return node;
  }

  function _downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function exportSVG(filename) {
    var source = _svgSource(_buildExportSVGElement());
    var blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    _downloadBlob(blob, filename || 'waste_atlas_map.svg');
  }

  function _crc32(bytes) {
    var table = _crc32.table;
    if (!table) {
      table = [];
      for (var n = 0; n < 256; n++) {
        var c = n;
        for (var k = 0; k < 8; k++) {
          c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
        }
        table[n] = c >>> 0;
      }
      _crc32.table = table;
    }
    var crc = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) {
      crc = table[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function _pngChunk(type, data) {
    var typeBytes = new TextEncoder().encode(type);
    var chunk = new Uint8Array(12 + data.length);
    var view = new DataView(chunk.buffer);
    view.setUint32(0, data.length);
    chunk.set(typeBytes, 4);
    chunk.set(data, 8);
    var crcInput = new Uint8Array(typeBytes.length + data.length);
    crcInput.set(typeBytes, 0);
    crcInput.set(data, typeBytes.length);
    view.setUint32(8 + data.length, _crc32(crcInput));
    return chunk;
  }

  function _pngWithDpi(blob, dpi) {
    return blob.arrayBuffer().then(function (buffer) {
      var input = new Uint8Array(buffer);
      var ppm = Math.round(dpi / 0.0254);
      var phys = new Uint8Array(9);
      var physView = new DataView(phys.buffer);
      physView.setUint32(0, ppm);
      physView.setUint32(4, ppm);
      phys[8] = 1;
      var physChunk = _pngChunk('pHYs', phys);
      var chunks = [input.slice(0, 8)];
      var offset = 8;
      while (offset < input.length) {
        var length = new DataView(input.buffer, input.byteOffset + offset, 4).getUint32(0);
        var type = String.fromCharCode(
          input[offset + 4],
          input[offset + 5],
          input[offset + 6],
          input[offset + 7]
        );
        var end = offset + 12 + length;
        var chunk = input.slice(offset, end);
        if (type !== 'pHYs') {
          chunks.push(chunk);
        }
        if (type === 'IHDR') {
          chunks.push(physChunk);
        }
        offset = end;
      }
      var total = chunks.reduce(function (sum, chunk) { return sum + chunk.length; }, 0);
      var output = new Uint8Array(total);
      var cursor = 0;
      chunks.forEach(function (chunk) {
        output.set(chunk, cursor);
        cursor += chunk.length;
      });
      return new Blob([output], { type: 'image/png' });
    });
  }

  function exportPNG(filename) {
    var svgEl = _buildExportSVGElement();
    var layout = svgEl.__wasteAtlasExportLayout || { width: EXPORT_WIDTH, height: EXPORT_HEIGHT };
    var w = layout.width;
    var h = layout.height;
    var canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    var ctx = canvas.getContext('2d');

    var img = new Image();
    var source = _svgSource(svgEl);
    var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
    img.onload = function () {
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob(function (blob) {
        _pngWithDpi(blob, EXPORT_DPI).then(function (pngBlob) {
          _downloadBlob(pngBlob, filename || 'waste_atlas_map.png');
        });
      }, 'image/png');
    };
    img.src = url;
  }

  function exportElementSVG(svgEl, filename) {
    var source = _svgSource(svgEl);
    var blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    _downloadBlob(blob, filename || 'waste_atlas_map.svg');
  }

  function exportElementPNG(svgEl, filename, dpi) {
    var width = parseInt(svgEl.getAttribute('width'), 10) || svgEl.viewBox.baseVal.width || EXPORT_WIDTH;
    var height = parseInt(svgEl.getAttribute('height'), 10) || svgEl.viewBox.baseVal.height || EXPORT_HEIGHT;
    var canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext('2d');
    var img = new Image();
    var source = _svgSource(svgEl);
    var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
    img.onload = function () {
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob(function (blob) {
        _pngWithDpi(blob, dpi || EXPORT_DPI).then(function (pngBlob) {
          _downloadBlob(pngBlob, filename || 'waste_atlas_map.png');
        });
      }, 'image/png');
    };
    img.src = url;
  }

  // ---- public API -----------------------------------------------------------

  function init(cfg) {
    _cfg = cfg;
    var loadingEl = document.getElementById(cfg.loadingId);
    var btnSVG = document.getElementById('btn-export-svg');
    var btnPNG = document.getElementById('btn-export-png');
    var fileBase = cfg.fileBase || 'waste_atlas_map';
    var isQuartileMode = _isQuartileEnabled(cfg) && !cfg.changeMode;

    function _exportFileBase() {
      if (cfg.changeMode && _lastLoadCfg) {
        return fileBase + '_change_' + _lastLoadCfg.fromYear + '_' + _lastLoadCfg.year;
      }
      return fileBase;
    }

    function load(country, year, preserveScope, fromYear, replaceUrl, selectorUrl) {
      if (replaceUrl) _replaceSelectorUrl(selectorUrl, year, fromYear, country);
      _show(loadingEl);
      if (btnSVG) btnSVG.disabled = true;
      if (btnPNG) btnPNG.disabled = true;

      var isConfiguredMultiRegion = cfg.nutsPrefix && cfg.nutsPrefix.indexOf(',') !== -1
        && country === cfg.country;
      var loadCfg = _configForSelection(cfg, country, year, preserveScope || isConfiguredMultiRegion);
      if (fromYear) loadCfg.fromYear = fromYear;
      if (loadCfg.changeMode) {
        // ACPV overlays/outlines are not meaningful for two-year diffs.
        delete loadCfg.outlineGeoJsonUrl;
        delete loadCfg.overlayPatternField;
        delete loadCfg.overlayPatternLegendLabel;
        delete loadCfg.exportOverlayPatternLegendLabel;
      }

      _fetchAll(loadCfg)
        .then(function (data) {
          var renderCfg = loadCfg;
          if (loadCfg.changeMode) {
            data = Object.assign({}, data, {
              thematicData: _changeRecords(loadCfg, data.fromThematicData, data.thematicData)
            });
            renderCfg = _changeRenderConfig(loadCfg, cfg.title);
          }
          _baseLoadCfg = renderCfg;
          if (isQuartileMode) {
            var records = _recordList(data.thematicData);
            renderCfg = _applyQuartiles(renderCfg, records);
          }
          _lastData = data;
          _lastLoadCfg = renderCfg;
          var conflictPromise = _conflictEnabled
            ? _loadConflicts(loadCfg, loadCfg.country, loadCfg.year, fromYear)
            : Promise.resolve(null);
          conflictPromise
            .then(function () {
              _render(data, renderCfg);
              _hide(loadingEl);
              if (btnSVG) btnSVG.disabled = false;
              if (btnPNG) btnPNG.disabled = false;
            })
            .catch(function (conflictErr) {
              // Conflict aid is best-effort; never block the map render.
              console.warn('Waste Atlas conflict aid failed:', conflictErr);
              _conflictCatchments = null;
              _conflictDetails = null;
              _render(data, renderCfg);
              _hide(loadingEl);
              if (btnSVG) btnSVG.disabled = false;
              if (btnPNG) btnPNG.disabled = false;
            });
        })
        .catch(function (err) {
          _hide(loadingEl);
          console.error('Waste Atlas load error:', err);
          var container = document.getElementById(cfg.containerId);
          container.innerHTML = '<div class="alert alert-danger m-3">'
            + '<strong>Error loading map data:</strong> ' + err.message
            + '</div>';
        });
    }

    load(cfg.country, cfg.year, true);

    initSelectorControls(function (country, year, _preserveScope, fromYear, replaceUrl, selectorUrl) {
      load(country, year, true, fromYear, replaceUrl, selectorUrl);
    }, { useChangeUrls: !!cfg.changeMode });

    var atlasControls = document.getElementById('atlas-controls');
    if (atlasControls && _isQuartileEnabled(cfg) && !cfg.changeMode) {
      var toggleWrap = document.createElement('label');
      toggleWrap.style.display = 'inline-flex';
      toggleWrap.style.alignItems = 'center';
      toggleWrap.style.gap = '0.4rem';
      toggleWrap.style.fontWeight = '600';
      toggleWrap.style.cursor = 'pointer';
      toggleWrap.style.fontSize = '0.875rem';

      var toggleCheckbox = document.createElement('input');
      toggleCheckbox.type = 'checkbox';
      toggleCheckbox.checked = true;
      toggleCheckbox.addEventListener('change', function () {
        isQuartileMode = toggleCheckbox.checked;
        if (_lastData && _baseLoadCfg) {
          if (isQuartileMode) {
            var records = _recordList(_lastData.thematicData);
            _lastLoadCfg = _applyQuartiles(_baseLoadCfg, records);
          } else {
            _lastLoadCfg = _baseLoadCfg;
          }
          _render(_lastData, _lastLoadCfg);
        }
      });

      toggleWrap.appendChild(toggleCheckbox);
      toggleWrap.appendChild(document.createTextNode('Quartile boundaries'));
      atlasControls.appendChild(toggleWrap);
    }

    // Maintainer aid: highlight catchments where the dataset holds more than
    // one collection competing for the single displayed theme value.
    if (atlasControls && cfg.conflictUrl && cfg.conflictTheme && !cfg.changeMode) {
      var conflictWrap = document.createElement('label');
      conflictWrap.style.display = 'inline-flex';
      conflictWrap.style.alignItems = 'center';
      conflictWrap.style.gap = '0.4rem';
      conflictWrap.style.fontWeight = '600';
      conflictWrap.style.cursor = 'pointer';
      conflictWrap.style.fontSize = '0.875rem';
      conflictWrap.style.color = CONFLICT_STROKE;

      var conflictCheckbox = document.createElement('input');
      conflictCheckbox.type = 'checkbox';
      conflictCheckbox.checked = false;
      conflictCheckbox.addEventListener('change', function () {
        _conflictEnabled = conflictCheckbox.checked;
        if (!_conflictEnabled) {
          _conflictCatchments = null;
          _conflictDetails = null;
          if (_lastData && _lastLoadCfg) _render(_lastData, _lastLoadCfg);
          return;
        }
        // Fetch conflicts for the current selection, then re-render.
        if (_lastData && _lastLoadCfg) {
          _loadConflicts(_lastLoadCfg, _lastLoadCfg.country, _lastLoadCfg.year, _lastLoadCfg.fromYear)
            .then(function () { _render(_lastData, _lastLoadCfg); })
            .catch(function (err) {
              console.warn('Waste Atlas conflict aid failed:', err);
              _conflictCatchments = null;
              _conflictDetails = null;
              _render(_lastData, _lastLoadCfg);
            });
        }
      });

      conflictWrap.appendChild(conflictCheckbox);
      conflictWrap.appendChild(document.createTextNode('Highlight conflicting catchments'));
      atlasControls.appendChild(conflictWrap);
    }

    if (btnSVG) btnSVG.addEventListener('click', function () { exportSVG(_exportFileBase() + '.svg'); });
    if (btnPNG) btnPNG.addEventListener('click', function () { exportPNG(_exportFileBase() + '.png'); });
  }

  function initOverviewDirectory() {
    var tabList = document.getElementById('atlas-region-tabs');
    var categorySelect = document.getElementById('atlas-directory-category');
    var searchInput = document.getElementById('atlas-directory-search');
    if (!tabList && !categorySelect && !searchInput) return null;

    var params = new URLSearchParams(window.location.search);

    function activeRegion() {
      var activeTab = tabList && tabList.querySelector('.nav-link.active');
      return activeTab ? activeTab.getAttribute('data-region') : '';
    }

    function updateUrl() {
      if (!window.history || !window.history.replaceState) return;
      var next = new URLSearchParams();
      var region = activeRegion();
      var category = categorySelect ? categorySelect.value : '';
      var query = searchInput ? searchInput.value.trim() : '';
      if (region) next.set('region', region);
      if (category) next.set('category', category);
      if (query) next.set('q', query);
      var qs = next.toString();
      window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }

    function applyFilters() {
      var category = categorySelect ? categorySelect.value : '';
      var query = searchInput ? searchInput.value.trim().toLowerCase() : '';
      var panes = document.querySelectorAll('#atlas-region-tab-content .atlas-region-pane');
      panes.forEach(function (pane) {
        var visibleInPane = 0;
        pane.querySelectorAll('.atlas-map-link').forEach(function (link) {
          var linkCategory = link.getAttribute('data-category') || '';
          var haystack = link.getAttribute('data-search') || link.textContent || '';
          var matches = (!category || linkCategory === '' || linkCategory === category)
            && (!query || haystack.toLowerCase().indexOf(query) !== -1);
          link.hidden = !matches;
          if (matches) visibleInPane += 1;
        });
        pane.querySelectorAll('.atlas-link-group').forEach(function (group) {
          var anyVisible = Array.prototype.some.call(
            group.querySelectorAll('.atlas-map-link'),
            function (link) { return !link.hidden; }
          );
          group.hidden = !anyVisible;
        });
        pane.querySelectorAll('.atlas-directory-region').forEach(function (region) {
          var anyVisible = Array.prototype.some.call(
            region.querySelectorAll('.atlas-map-link'),
            function (link) { return !link.hidden; }
          );
          region.hidden = !anyVisible;
        });
        var emptyEl = pane.querySelector('.atlas-directory-empty');
        if (emptyEl) emptyEl.hidden = visibleInPane !== 0;
      });
    }

    if (categorySelect && params.has('category')) categorySelect.value = params.get('category');
    if (searchInput && params.has('q')) searchInput.value = params.get('q');

    if (tabList) {
      tabList.addEventListener('shown.bs.tab', function () {
        applyFilters();
        updateUrl();
      });
    }
    if (categorySelect) {
      categorySelect.addEventListener('change', function () {
        applyFilters();
        updateUrl();
      });
    }
    if (searchInput) {
      searchInput.addEventListener('input', _debounce(function () {
        applyFilters();
        updateUrl();
      }, 150));
    }

    applyFilters();
    return { applyFilters: applyFilters };
  }

  return {
    init: init,
    initSelectorControls: initSelectorControls,
    initOverviewDirectory: initOverviewDirectory,
    selectorNavigationTarget: _selectorNavigationTarget,
    exportSVG: exportSVG,
    exportPNG: exportPNG,
    exportElementSVG: exportElementSVG,
    exportElementPNG: exportElementPNG,
    transforms: transforms
  };
})();
