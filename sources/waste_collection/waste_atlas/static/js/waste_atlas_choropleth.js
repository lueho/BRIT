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
 *     noDataLabel:  'Keine Daten',        // optional
 *     legendTitle:  'Legend',              // optional
 *   });
 *
 * Atlas-wide values (palette, legend defaults, export page geometry) are not
 * hard-coded here: they are read from the JSON script element
 * ``#waste-atlas-render-defaults`` that the ``atlas_render_defaults`` template
 * tag renders from the database, or from ``cfg.renderDefaults``.
 */

/* global d3 */

var WasteAtlasChoropleth = (function () {
  'use strict';

  var RENDER_DEFAULTS_ELEMENT_ID = 'waste-atlas-render-defaults';
  // The width of the drawn map the ACPV marker geometry is dimensioned for.
  // Scaling follows the projected geography rather than the canvas, because an
  // export page has its own aspect ratio and reserves room for the legend: only
  // the map's own size tells how dense the hatching has to be to look the same.
  var ACPV_REFERENCE_MAP_WIDTH = 900;
  var ACPV_HATCH_SPACING = 6;
  var ACPV_HATCH_STROKE_WIDTH = 2;
  var ACPV_HATCH_ANGLE = 45;
  // Aggregated values are derived centrally from the raw record, not copied
  // along by every transform; a map opts in by naming this field.
  var ACPV_OVERLAY_FIELD = '_has_acpv_overlay';
  var _renderDefaults = null;

  /**
   * Return the database-backed atlas defaults.
   *
   * Reads the JSON script element rendered by the ``atlas_render_defaults``
   * template tag once and caches it. ``setRenderDefaults`` lets callers (the
   * page config injected into ``init``) supply the same payload directly.
   */
  function _defaults() {
    if (_renderDefaults) return _renderDefaults;
    var el = document.getElementById(RENDER_DEFAULTS_ELEMENT_ID);
    if (el) {
      try {
        _renderDefaults = JSON.parse(el.textContent);
      } catch (error) {
        _renderDefaults = null;
      }
    }
    if (!_renderDefaults) {
      throw new Error(
        'Waste Atlas rendering defaults are missing: render the '
        + 'atlas_render_defaults template tag on this page.'
      );
    }
    return _renderDefaults;
  }

  function setRenderDefaults(defaults) {
    if (defaults) _renderDefaults = defaults;
  }

  function _exportDefaults() {
    return _defaults().export;
  }

  function _exportPx(millimetres) {
    return Math.round(millimetres / 25.4 * _exportDefaults().dpi);
  }

  function _exportWidth() {
    return _exportPx(_exportDefaults().widthMm);
  }

  function _exportHeight() {
    return _exportPx(_exportDefaults().heightMm);
  }

  function _exportLegendFontSize() {
    return _exportDefaults().legendFontSizePt / 72 * _exportDefaults().dpi;
  }

  function _defaultFileBase() {
    return _defaults().exportFileNamePrefix + '_map';
  }

  function _exportLegendFontFamily() {
    return _exportDefaults().legendFontFamily;
  }

  // The face the on-screen map and legend are drawn in; text is measured in it
  // so wrapping matches what the browser renders.
  var SCREEN_FONT_FAMILY = "'Nunito', sans-serif";
  var SCREEN_LABEL_FONT = { family: SCREEN_FONT_FAMILY };
  var SCREEN_TITLE_FONT = { family: SCREEN_FONT_FAMILY, weight: 'bold' };
  // The export legend title is printed bold in the export face.
  var EXPORT_TITLE_FONT = { weight: 'bold' };

  /**
   * Page heights the export layout may choose from, in millimetres.
   *
   * The preferred height comes first so it wins on equal score; taller pages
   * are tried in ~20 mm steps up to the configured maximum.
   */
  function _exportHeightCandidatesMm() {
    var preferred = _exportDefaults().heightMm;
    var maximum = _exportDefaults().maxHeightMm;
    var candidates = [preferred];
    var step = 20;
    for (var height = preferred + step; height < maximum; height += step) {
      candidates.push(height);
    }
    if (maximum > preferred) candidates.push(maximum);
    return candidates;
  }
  // On-screen canvas: the SVG always spans the container width, the height
  // follows the projected geometry so DE, EU and single-region maps each get
  // sensible proportions instead of one hard-coded aspect ratio.
  var SCREEN_PADDING_X = 40;
  // The canvas is taller than the viewport, so the legend is anchored to the
  // top where it is visible on load; this band reserves room for it.
  var SCREEN_PADDING_TOP = 100;
  var SCREEN_PADDING_BOTTOM = 40;
  var SCREEN_FALLBACK_ASPECT = 1.11; // Used until the geometry is known.
  var SCREEN_MIN_ASPECT = 0.4;
  var SCREEN_MAX_ASPECT = 1.7;
  var SCREEN_MIN_HEIGHT = 320;
  var MERCATOR_MAX_LATITUDE = 89.5;
  // Below 1 the map shrinks inside the canvas, which is how a reader gets a
  // tall map back onto one screen without resizing the window.
  var ZOOM_MIN = 0.2;
  var ZOOM_MAX = 12;
  var ZOOM_STEP = 1.5;
  // d3-zoom treats any movement beyond this as a drag and cancels the trailing
  // click. Its default of 0 makes ordinary mouse jitter swallow catchment
  // clicks, so allow a few pixels of slop.
  var ZOOM_CLICK_DISTANCE = 4;

  var _cfg = {};
  var _svg;
  // Root group holding every geographic layer; the zoom transform is applied
  // here so the title and legend stay put and readable.
  var _mapRoot = null;
  var _zoomBehavior = null;
  var _zoomTarget = null;
  var _zoomTransform = null;
  // Open choice popover for a catchment whose value comes from several
  // collections; only one can be open at a time.
  var _collectionPicker = null;
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

  function _show(el) { if (el) el.classList.remove('d-none'); }
  function _hide(el) { if (el) el.classList.add('d-none'); }

  function _collectionDetailUrl(feature) {
    var properties = feature && feature.properties;
    return properties && properties.collection_detail_url
      ? properties.collection_detail_url
      : null;
  }

  function _openCollectionDetail(feature) {
    var detailUrl = _collectionDetailUrl(feature);
    if (detailUrl) window.location.assign(detailUrl);
  }

  /**
   * Every collection a click on *feature* may open.
   *
   * Composite themes (waste ratio, combined frequency, …) derive one value from
   * a biowaste and a residual collection, so the API sends both and the reader
   * chooses. Falls back to the single-collection field for cached responses
   * that predate the list.
   */
  function _collectionOptions(feature) {
    var properties = feature && feature.properties;
    if (!properties) return [];
    if (Array.isArray(properties.collection_details)) {
      return properties.collection_details.filter(function (option) {
        return option && option.url;
      });
    }
    var detailUrl = properties.collection_detail_url;
    if (!detailUrl) return [];
    return [{ url: detailUrl, label: properties.catchment_name || 'Collection' }];
  }

  function _openCollectionChoice(event, feature) {
    var options = _collectionOptions(feature);
    if (options.length > 1) {
      _openCollectionPicker(event, feature, options);
      return;
    }
    _openCollectionDetail(feature);
  }

  /**
   * Middle-click means "open in a new tab" everywhere else, but the browser's
   * default action for it is autoscroll, which is useless on a map that pans by
   * dragging. Suppressing it needs preventDefault on the *mousedown*.
   */
  function _suppressAutoscroll(event) {
    if (event.button === 1) event.preventDefault();
  }

  function _openCollectionInNewTab(feature) {
    var options = _collectionOptions(feature);
    if (options.length !== 1) return false;
    var opened = window.open(options[0].url, '_blank');
    // Keep the new tab from reaching back into this one.
    if (opened) opened.opener = null;
    return true;
  }

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

  function _matchesCategory(value, category) {
    return typeof category.test === 'function'
      ? category.test(value)
      : category.value === value;
  }

  function _isNoDataValue(value, categories) {
    if (value == null) return true;
    return !categories.some(function (category) {
      return _matchesCategory(value, category);
    });
  }

  function _isNoDataCategory(item) {
    return item.value === 'no_data'
      || String(item.label || '').toLowerCase().indexOf('no data') !== -1;
  }

  function _colorFor(value, categories, noDataColor) {
    if (value == null) return noDataColor || _defaults().noDataColor;
    for (var i = 0; i < categories.length; i++) {
      var cat = categories[i];
      if (typeof cat.test === 'function') {
        if (cat.test(value)) return cat.color;
      } else if (cat.value === value) {
        return cat.color;
      }
    }
    return noDataColor || _defaults().noDataColor;
  }

  /**
   * Merge thematic records into the catchment features and flag on the
   * config whether any rendered feature falls back to the no-data color.
   * Idempotent; used by both the screen render and the export layout so
   * the "No data" legend entry is only drawn when such features exist.
   */
  function _annotateFeatures(data, cfg) {
    var rawRecords = Array.isArray(data.thematicData) ? data.thematicData
      : (data.thematicData.results || []);
    var records = rawRecords;
    if (typeof cfg.transformData === 'function') {
      records = cfg.transformData(rawRecords);
    } else if (cfg.transformName && transforms[cfg.transformName]) {
      records = transforms[cfg.transformName](rawRecords);
    }
    var lookup = {};
    var presentCategoryValues = {};
    records.forEach(function (r) {
      lookup[r.catchment_id] = r;
      if (r[cfg.dataField] != null) presentCategoryValues[r[cfg.dataField]] = true;
    });
    cfg._presentCategoryValues = presentCategoryValues;
    var rawLookup = {};
    rawRecords.forEach(function (r) { rawLookup[r.catchment_id] = r; });

    var hasFallbackNoData = false;
    var hasNoDataCategory = false;
    var hasOverlayPattern = false;
    if (data.catchments.features) {
      data.catchments.features.forEach(function (f) {
        var rec = lookup[f.properties.catchment_id];
        f.properties._thematic_value = rec ? rec[cfg.dataField] : null;
        f.properties._thematic_record = rec || null;
        f.properties._overlay_pattern = _acpvOverlayFlag(
          cfg, rec, rawLookup[f.properties.catchment_id]
        );
        if (f.properties._overlay_pattern) {
          hasOverlayPattern = true;
        }
        var matchesNoDataCategory = f.properties._thematic_value != null
          && cfg.categories.some(function (category) {
            return _isNoDataCategory(category)
              && _matchesCategory(f.properties._thematic_value, category);
          });
        if (matchesNoDataCategory) {
          hasNoDataCategory = true;
        } else if (_isNoDataValue(f.properties._thematic_value, cfg.categories)) {
          hasFallbackNoData = true;
        }
      });
    }
    cfg._hasNoData = hasFallbackNoData || hasNoDataCategory;
    cfg._hasFallbackNoData = hasFallbackNoData;
    cfg._hasNoDataCategory = hasNoDataCategory;
    cfg._hasOverlayPattern = hasOverlayPattern;
  }

  /**
   * Whether a catchment shows the aggregated-value hatching.
   *
   * For the canonical ACPV field the flag is derived here from the raw API
   * record, so no transform has to carry it along. A map naming any other
   * field reads it from the transformed record, falling back to the raw one.
   */
  function _acpvOverlayFlag(cfg, record, rawRecord) {
    if (!cfg.overlayPatternField) return false;
    if (cfg.overlayPatternField === ACPV_OVERLAY_FIELD) {
      return Boolean(rawRecord && rawRecord.value_source === 'acpv');
    }
    if (record && record[cfg.overlayPatternField] != null) {
      return Boolean(record[cfg.overlayPatternField]);
    }
    return Boolean(rawRecord && rawRecord[cfg.overlayPatternField]);
  }

  function _firstDefined(a, b) {
    return a == null ? b : a;
  }

  /**
   * Resolve the appearance of the ACPV markers for a map drawn ``mapWidth``
   * wide.
   *
   * Colors and opacities come from the atlas-wide defaults, overridable per
   * map with the ``acpv*`` config keys. Everything geometric is expressed for
   * the reference map width and scaled with the projected geography, so the
   * hatching and the group outline look the same on screen and in an export.
   */
  function _acpvStyle(cfg, mapWidth) {
    cfg = cfg || {};
    var defaults = _defaults().acpv || {};
    var scale = (mapWidth || ACPV_REFERENCE_MAP_WIDTH) / ACPV_REFERENCE_MAP_WIDTH;
    return {
      hatchColor: _firstDefined(cfg.acpvHatchColor, defaults.hatchColor),
      hatchOpacity: _firstDefined(cfg.acpvHatchOpacity, defaults.hatchOpacity),
      hatchSpacing: ACPV_HATCH_SPACING * scale,
      hatchStrokeWidth: ACPV_HATCH_STROKE_WIDTH * scale,
      hatchAngle: ACPV_HATCH_ANGLE,
      outlineColor: _firstDefined(cfg.acpvOutlineColor, defaults.outlineColor),
      outlineOpacity: _firstDefined(cfg.acpvOutlineOpacity, defaults.outlineOpacity),
      outlineWidth: _firstDefined(cfg.acpvOutlineWidth, defaults.outlineWidth) * scale
    };
  }

  function _overlayPatternId(cfg) {
    return (cfg.svgId || 'atlas-svg') + '-overlay-pattern';
  }

  function _defineOverlayPattern(cfg, mapWidth) {
    if (!cfg.overlayPatternField) return;

    var style = _acpvStyle(cfg, mapWidth);
    var pattern = _svg.append('defs')
      .append('pattern')
      .attr('id', _overlayPatternId(cfg))
      .attr('patternUnits', 'userSpaceOnUse')
      .attr('width', style.hatchSpacing)
      .attr('height', style.hatchSpacing)
      .attr('patternTransform', 'rotate(' + style.hatchAngle + ')');

    pattern.append('line')
      .attr('x1', 0)
      .attr('y1', 0)
      .attr('x2', 0)
      .attr('y2', style.hatchSpacing)
      .attr('stroke', style.hatchColor)
      .attr('stroke-opacity', style.hatchOpacity)
      .attr('stroke-width', style.hatchStrokeWidth);
  }

  // ---- data fetching --------------------------------------------------------

  function _changeCatchmentUrl(catchmentDataUrl) {
    if (catchmentDataUrl.indexOf('collector-geojson') !== -1) {
      return catchmentDataUrl.replace('collector-geojson', 'collector-change-geojson');
    }
    if (catchmentDataUrl.indexOf('collection-geojson') !== -1) {
      return catchmentDataUrl.replace('collection-geojson', 'collection-change-geojson');
    }
    if (catchmentDataUrl.indexOf('geojson') !== -1) {
      return catchmentDataUrl.replace('geojson', 'collection-change-geojson');
    }
    return '/waste_collection/api/waste-atlas/catchment/collection-change-geojson/';
  }

  function _fetchAll(cfg) {
    var base = '/waste_collection/api/waste-atlas/';
    var nutsSuffix = cfg.nutsPrefix ? '&nuts_prefix=' + encodeURIComponent(cfg.nutsPrefix) : '';
    var collectionYear = cfg.collectionYear || cfg.year;
    var collectionYearSuffix = cfg.collectionYear ? '&collection_year=' + encodeURIComponent(cfg.collectionYear) : '';
    var catchmentDataUrl = cfg.catchmentDataUrl || (base + 'catchment/geojson/');
    var collectionDetailSuffix = cfg.collectionDetailCategory
      ? '&collection_detail_category=' + encodeURIComponent(cfg.collectionDetailCategory)
      : '';
    var catchUrl = cfg.changeMode
      ? _changeCatchmentUrl(catchmentDataUrl) + '?country=' + cfg.country
      + '&from_year=' + cfg.fromYear + '&to_year=' + cfg.year + nutsSuffix
      : catchmentDataUrl + '?country=' + cfg.country + '&year=' + collectionYear
      + nutsSuffix + collectionDetailSuffix;
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
    var colors = _defaults().changeColors;
    return [
      { value: 'no_change', label: 'No change', color: colors.noChange },
      { value: 'changed', label: 'Category changed', color: colors.changed },
      { value: 'boundary_changed', label: 'Catchment reassigned', color: colors.boundaryChanged },
      { value: 'new', label: 'New in ' + toYear, color: colors['new'] },
      { value: 'removed', label: 'Removed in ' + toYear, color: colors.removed }
    ];
  }

  function _numericChangeCategories(toYear) {
    var colors = _defaults().changeColors;
    return [
      { value: 'decrease', label: 'Decrease', color: colors.decrease },
      { value: 'no_change', label: 'No numeric change', color: colors.noChange },
      { value: 'increase', label: 'Increase', color: colors.increase },
      { value: 'changed', label: 'Category changed', color: colors.changed },
      { value: 'boundary_changed', label: 'Catchment reassigned', color: colors.boundaryChanged },
      { value: 'new', label: 'New value in ' + toYear, color: colors['new'] },
      { value: 'removed', label: 'Value removed in ' + toYear, color: colors.removed }
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

  function _changeRecords(cfg, fromRaw, toRaw, changeFeatures) {
    if (changeFeatures) {
      return _spatialChangeRecords(cfg, fromRaw, toRaw, changeFeatures);
    }
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

  function _spatialChangeRecords(cfg, fromRaw, toRaw, changeFeatures) {
    var fromRecords = _recordLookup(fromRaw);
    var toRecords = _recordLookup(toRaw);
    var fromClasses = _classifyRecords(cfg, fromRaw);
    var toClasses = _classifyRecords(cfg, toRaw);

    return changeFeatures.map(function (feature) {
      var properties = feature.properties || {};
      var fromId = properties.from_catchment_id;
      var toId = properties.to_catchment_id;
      var spatialChange = properties.spatial_change;
      var fromClass = fromId == null ? null : fromClasses[fromId];
      var toClass = toId == null ? null : toClasses[toId];
      var fromValue = cfg.numericField && fromId != null
        ? _numericValue(fromRecords[fromId], cfg.numericField)
        : null;
      var toValue = cfg.numericField && toId != null
        ? _numericValue(toRecords[toId], cfg.numericField)
        : null;
      var difference = null;
      var change = null;

      if (spatialChange === 'added') {
        change = 'new';
      } else if (spatialChange === 'removed') {
        change = 'removed';
      } else if (spatialChange === 'transferred') {
        change = 'boundary_changed';
      } else if (cfg.numericField && fromValue != null && toValue != null) {
        difference = toValue - fromValue;
        if (Math.abs(difference) < 1e-9) {
          change = 'no_change';
        } else {
          change = difference > 0 ? 'increase' : 'decrease';
        }
      } else if (fromClass != null && toClass != null) {
        change = fromClass === toClass ? 'no_change' : 'changed';
      } else if (toClass != null || toValue != null) {
        change = 'new';
      } else if (fromClass != null || fromValue != null) {
        change = 'removed';
      }

      return {
        catchment_id: properties.change_feature_id || properties.catchment_id,
        change_type: change,
        spatial_change: spatialChange,
        from_catchment_id: fromId,
        to_catchment_id: toId,
        from_value: fromValue,
        to_value: toValue,
        difference: difference
      };
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
    renderCfg.tooltipFields = [
      { field: 'spatial_change', label: 'Boundary' }
    ];
    if (isNumericChange) {
      renderCfg.tooltipFields = renderCfg.tooltipFields.concat([
        { field: 'from_value', label: String(loadCfg.fromYear) },
        { field: 'to_value', label: String(loadCfg.year) },
        { field: 'difference', label: 'Difference' }
      ]);
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

  function _regionFromSelect(select) {
    var selectedOption = select.options[select.selectedIndex];
    return {
      country: selectedOption ? selectedOption.getAttribute('data-country') || select.value : select.value,
      nutsPrefix: selectedOption ? selectedOption.getAttribute('data-nuts-prefix') || '' : '',
      nutsLevel: selectedOption ? selectedOption.getAttribute('data-nuts-level') || '' : ''
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
      return _regionFromSelect(countrySelect);
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
        btnToggleChange.classList.add('d-none');
        btnToggleChange.removeAttribute('href');
        return;
      }
      var year = selectedYear();
      var fromYear = selectedFromYear();
      var params = options.useChangeUrls
        ? 'year=' + encodeURIComponent(year)
        : 'from_year=' + encodeURIComponent(fromYear || previousChangeYear(year)) + '&to_year=' + encodeURIComponent(year);
      btnToggleChange.href = url + '?' + params;
      btnToggleChange.classList.remove('d-none');
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

  /** Geometry the projection is fitted to: region border, else country, else catchments. */
  function _fitGeometry(data, cfg) {
    if (!data) return null;
    var regionBorder = (cfg && cfg.nutsPrefix && data.bundeslaender
      && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
    return (regionBorder && regionBorder.features && regionBorder.features.length)
      ? regionBorder : data.catchments;
  }

  /** Geographic bounding box of any GeoJSON node, independent of ring winding. */
  function _geographicBounds(geojson) {
    var west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;

    function visitPosition(position) {
      var lon = position[0];
      var lat = position[1];
      if (typeof lon !== 'number' || typeof lat !== 'number') return;
      if (lon < west) west = lon;
      if (lon > east) east = lon;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }

    function visitCoordinates(coordinates) {
      if (!Array.isArray(coordinates)) return;
      if (typeof coordinates[0] === 'number') return visitPosition(coordinates);
      coordinates.forEach(visitCoordinates);
    }

    function visit(node) {
      if (!node) return;
      if (node.type === 'FeatureCollection') (node.features || []).forEach(visit);
      else if (node.type === 'Feature') visit(node.geometry);
      else if (node.type === 'GeometryCollection') (node.geometries || []).forEach(visit);
      else visitCoordinates(node.coordinates);
    }

    visit(geojson);
    if (west > east || south > north) return null;
    return { west: west, east: east, south: south, north: north };
  }

  function _mercatorY(latitude) {
    var clamped = Math.max(-MERCATOR_MAX_LATITUDE, Math.min(MERCATOR_MAX_LATITUDE, latitude));
    return Math.log(Math.tan(Math.PI / 4 + clamped * Math.PI / 360));
  }

  /**
   * Projected height/width ratio of the fitted geometry, or null when unknown.
   *
   * Measured from the geographic bounding box and the Mercator y transform
   * rather than from a probe projection: d3's spherical polygon clipping is
   * winding-sensitive, so `geoMercator().fitWidth(…)` + `geoPath().bounds(…)`
   * reports the whole (square) world for rings wound the GeoJSON way.
   */
  function _geometryAspect(fitData) {
    var bounds = _geographicBounds(fitData);
    if (!bounds) return null;
    var lonSpan = (bounds.east - bounds.west) * Math.PI / 180;
    var latSpan = _mercatorY(bounds.north) - _mercatorY(bounds.south);
    if (!isFinite(lonSpan) || !isFinite(latSpan)) return null;
    if (lonSpan <= 0 || latSpan <= 0) return null;
    return latSpan / lonSpan;
  }

  function _screenLayout(container, fitData) {
    var width = (container && container.clientWidth) || 900;
    var innerWidth = Math.max(120, width - SCREEN_PADDING_X * 2);
    var aspect = _geometryAspect(fitData);
    if (aspect == null) aspect = SCREEN_FALLBACK_ASPECT;
    aspect = Math.min(SCREEN_MAX_ASPECT, Math.max(SCREEN_MIN_ASPECT, aspect));

    // The map fills the canvas width; the canvas grows vertically to match the
    // geometry and the page scrolls if that is taller than the viewport.
    var chrome = SCREEN_PADDING_TOP + SCREEN_PADDING_BOTTOM;
    var height = Math.max(SCREEN_MIN_HEIGHT, Math.round(innerWidth * aspect) + chrome);

    return {
      exportMode: false,
      width: width,
      height: height,
      mapExtent: [
        [SCREEN_PADDING_X, SCREEN_PADDING_TOP],
        [width - SCREEN_PADDING_X, height - SCREEN_PADDING_BOTTOM]
      ],
      legendAtTop: true,
      showHeader: false,
      titleY: 30,
      subtitleY: 50,
      titleFontSize: 18,
      subtitleFontSize: 13
    };
  }

  // Text is measured in the face it is rendered in: ``font`` = { family, weight }
  // defaulting to the export legend face, so a bold or non-export label is not
  // underestimated and then drawn wider than the box it was wrapped for.
  function _measureTextWidth(text, fontSize, font) {
    font = font || {};
    if (!_measureCtx && typeof document !== 'undefined') {
      _measureCtx = document.createElement('canvas').getContext('2d');
    }
    if (!_measureCtx) {
      return String(text).length * fontSize * (font.weight === 'bold' ? 0.56 : 0.52);
    }
    _measureCtx.font = (font.weight ? font.weight + ' ' : '')
      + fontSize + 'px ' + (font.family || _exportLegendFontFamily());
    return _measureCtx.measureText(text).width;
  }

  function _wrapTextToWidth(label, maxWidth, fontSize, font) {
    var lines = [];
    String(label).split(/\r?\n/).forEach(function (segment) {
      var words = segment
        .replace(/\s*\/\s*/g, ' / ')
        .replace(/\s*[–—]\s*/g, ' – ')
        .split(/\s+/)
        .filter(function (word) { return word.length > 0; });
      var current = '';
      words.forEach(function (word) {
        var next = current ? current + ' ' + word : word;
        if (_measureTextWidth(next, fontSize, font) <= maxWidth || !current) {
          current = next;
          if (
            _measureTextWidth(current, fontSize, font) <= maxWidth
            || current.length <= 1
          ) return;
        }
        if (current !== word) {
          lines.push(current);
          current = word;
        }
        while (_measureTextWidth(current, fontSize, font) > maxWidth && current.length > 1) {
          var part = current;
          while (_measureTextWidth(part, fontSize, font) > maxWidth && part.length > 1) {
            part = part.slice(0, -1);
          }
          lines.push(part);
          current = current.slice(part.length);
        }
      });
      if (current) lines.push(current);
    });
    return lines;
  }

  function _exportLegendLabel(item) {
    return item.exportLabel || item.label;
  }

  function _legendFootnoteLabel(cfg, exportMode) {
    var labels = [];
    if (cfg.legendNote) labels.push(cfg.legendNote);
    if (cfg.overlayPatternField && cfg.overlayPatternLegendLabel && cfg._hasOverlayPattern) {
      labels.push(
        exportMode && cfg.exportOverlayPatternLegendLabel
          ? cfg.exportOverlayPatternLegendLabel
          : cfg.overlayPatternLegendLabel
      );
    }
    return labels.join('\n');
  }

  function _visibleLegendCategories(cfg) {
    return cfg.categories.filter(function (item) {
      if (_isNoDataCategory(item) && !cfg._hasNoDataCategory) return false;
      if (!cfg.showOnlyPresentCategories) return true;
      return Boolean(cfg._presentCategoryValues && cfg._presentCategoryValues[item.value]);
    });
  }

  function _defaultLegendCategories(cfg) {
    return _visibleLegendCategories(cfg);
  }

  /**
   * Apply the saved legend order (``legendCategoryOrder``) to the categories the
   * legend shows, on screen and in the export alike.
   *
   * An entry the saved order does not mention keeps its position relative to the
   * mentioned ones: it stays directly behind the last mentioned entry preceding
   * it in the default order, and in front of everything when none does. Quartile
   * classification swaps the stored classes for data-derived ones, so a saved
   * order predating that swap still places the entries it does know without
   * scattering the rest.
   */
  function _orderedLegendCategories(cfg) {
    var order = Array.isArray(cfg.legendCategoryOrder) ? cfg.legendCategoryOrder : [];
    var keyed = [];
    var rank = -1;
    var offset = 0;
    _defaultLegendCategories(cfg).forEach(function (item) {
      var saved = order.indexOf(item.value);
      if (saved === -1) {
        offset += 1;
      } else {
        rank = saved;
        offset = 0;
      }
      keyed.push({ rank: rank, offset: offset, item: item });
    });
    return keyed.sort(function (left, right) {
      return left.rank - right.rank || left.offset - right.offset;
    }).map(function (entry) {
      return entry.item;
    });
  }

  function _legendItems(cfg, exportMode) {
    var items = [];
    _orderedLegendCategories(cfg).forEach(function (item) {
      items.push(Object.assign({}, item, {
        label: exportMode ? _exportLegendLabel(item) : item.label
      }));
    });
    if (cfg.noDataLabel && cfg._hasFallbackNoData) {
      items.push({
        label: exportMode && cfg.exportNoDataLabel ? cfg.exportNoDataLabel : cfg.noDataLabel,
        color: cfg.noDataColor || _defaults().noDataColor
      });
    }
    return _markTrailingLegendStatuses(cfg, items);
  }

  // Computed value ranges have thresholds; preserved classes, conflict aids
  // and fallback no-data entries are statuses. When the statuses form one
  // trailing group, expose that natural boundary to the column distributor.
  // A map may instead declare explicit category-value boundaries when its
  // semantic groups are not inferred from numeric ranges.
  function _markTrailingLegendStatuses(cfg, items) {
    var columnBreakBefore = Array.isArray(cfg.legendColumnBreakBefore)
      ? cfg.legendColumnBreakBefore
      : [];
    var lastValueRange = -1;
    items.forEach(function (item, index) {
      if (item.threshold != null) lastValueRange = index;
      delete item.breakBefore;
    });
    items.forEach(function (item) {
      if (columnBreakBefore.indexOf(item.value) !== -1) item.breakBefore = true;
    });
    if (columnBreakBefore.length) return items;
    if (lastValueRange < 0 || lastValueRange === items.length - 1) return items;
    var trailingItemsAreStatuses = items.slice(lastValueRange + 1).every(function (item) {
      return item.threshold == null;
    });
    if (trailingItemsAreStatuses) items[lastValueRange + 1].breakBefore = true;
    return items;
  }

  // Smallest width (<= maxWidth) that fits the measured content for the given
  // column count. Applied to every legend: the engine never uses more width
  // than the content needs, whether the legend has one column or several.
  function _fitExportLegendWidth(cfg, maxWidth, opts) {
    var titleWidth = String(cfg.exportLegendTitle || cfg.legendTitle || '')
      .split(/\r?\n/)
      .reduce(function (widest, line) {
        return Math.max(
          widest,
          _measureTextWidth(line, opts.titleFontSize, EXPORT_TITLE_FONT)
        );
      }, 0);
    var labelWidth = _legendItems(cfg, true).reduce(function (widest, item) {
      return Math.max(widest, _measureTextWidth(item.label, opts.fontSize));
    }, 0);
    var footnoteWidth = _legendFootnoteLabel(cfg, true).split(/\r?\n/)
      .reduce(function (widest, line) {
        return Math.max(widest, _measureTextWidth(line, Math.round(opts.fontSize * 0.82)));
      }, 0);
    var columnContent = opts.swatchW + opts.labelGap + labelWidth;
    var columnsWidth = opts.columnCount * columnContent
      + (opts.columnCount - 1) * opts.columnGap;
    var contentWidth = Math.max(titleWidth, columnsWidth, footnoteWidth);
    return Math.min(maxWidth, Math.ceil(contentWidth + opts.paddingX * 2 + 2));
  }

  // Arrange the measured items into ``columnCount`` columns.
  //
  // ``column`` flow fills one column after another: the entries keep their
  // order down the first column before the next one starts, and a remainder
  // that does not divide evenly lengthens the leading columns. ``row`` flow
  // reads across the columns instead, so entry order runs left to right; every
  // entry of a row then gets the row's tallest height as its ``slotHeight`` so
  // the rows line up across columns.
  function _distributeLegendItems(items, columnCount, itemFlow, rowGap) {
    var columns = [];
    for (var i = 0; i < columnCount; i++) columns.push([]);
    if (itemFlow === 'row') {
      var rowHeights = [];
      items.forEach(function (item, index) {
        var row = Math.floor(index / columnCount);
        rowHeights[row] = Math.max(rowHeights[row] || 0, item.height);
      });
      items.forEach(function (item, index) {
        item.slotHeight = rowHeights[Math.floor(index / columnCount)];
        columns[index % columnCount].push(item);
      });
      return columns;
    }
    var groups = [[]];
    items.forEach(function (item) {
      if (item.breakBefore && groups[groups.length - 1].length) groups.push([]);
      groups[groups.length - 1].push(item);
    });
    if (groups.length === columnCount) {
      groups.forEach(function (group, columnIndex) {
        group.forEach(function (item) {
          item.slotHeight = null;
          columns[columnIndex].push(item);
        });
      });
      return columns;
    }
    var perColumn = Math.floor(items.length / columnCount);
    var remainder = items.length % columnCount;
    var index = 0;
    columns.forEach(function (column, columnIndex) {
      var count = perColumn + (columnIndex < remainder ? 1 : 0);
      for (var taken = 0; taken < count; taken++) {
        items[index].slotHeight = null;
        column.push(items[index]);
        index += 1;
      }
    });
    return columns;
  }

  function _legendSlotHeight(item) {
    return item.slotHeight == null ? item.height : item.slotHeight;
  }

  // Height of one laid-out column, measured on the slot heights so that the
  // rows of a row-flow legend line up across the columns.
  function _legendColumnHeight(column, rowGap) {
    return column.reduce(function (total, item, index) {
      return total + _legendSlotHeight(item) + (index ? rowGap : 0);
    }, 0);
  }

  function _measureExportLegend(cfg, width, columnCount, itemFlow) {
    var swatchSize = Math.round(_exportLegendFontSize() * 0.72);
    var opts = {
      paddingX: 20,
      paddingY: 18,
      swatchW: swatchSize,
      swatchH: swatchSize,
      labelGap: 10,
      rowGap: 8,
      titleGap: 14,
      columnGap: 20,
      columnCount: columnCount || 1,
      itemFlow: itemFlow === 'row' ? 'row' : 'column',
      fontSize: _exportLegendFontSize(),
      titleFontSize: _exportLegendFontSize(),
      fontFamily: _exportLegendFontFamily()
    };
    opts.lineHeight = Math.round(opts.fontSize * 1.12);
    // Always fit width to content (no user opt-in); the caller passes the hard
    // maximum and the legend shrinks to what its content needs.
    width = _fitExportLegendWidth(cfg, width, opts);
    opts.width = width;
    opts.columnWidth = (
      width - opts.paddingX * 2 - (opts.columnCount - 1) * opts.columnGap
    ) / opts.columnCount;
    opts.textWidth = opts.columnWidth - opts.swatchW - opts.labelGap;
    opts.titleLines = _wrapTextToWidth(
      cfg.exportLegendTitle || cfg.legendTitle || '',
      width - opts.paddingX * 2,
      opts.titleFontSize,
      EXPORT_TITLE_FONT
    );
    opts.titleHeight = Math.max(opts.titleFontSize, opts.titleLines.length * opts.lineHeight);
    opts.items = _legendItems(cfg, true).map(function (item) {
      var lines = _wrapTextToWidth(item.label, opts.textWidth, opts.fontSize);
      return Object.assign({}, item, {
        lines: lines,
        height: Math.max(opts.swatchH, lines.length * opts.lineHeight)
      });
    });
    opts.itemCount = opts.items.length;
    // Extra label lines beyond one per item — a readability cost the scorer
    // uses to prefer layouts that wrap labels less.
    opts.wrappedLines = opts.items.reduce(function (total, item) {
      return total + Math.max(0, item.lines.length - 1);
    }, 0);
    opts.columns = _distributeLegendItems(
      opts.items, opts.columnCount, opts.itemFlow, opts.rowGap
    );
    opts.columnHeights = opts.columns.map(function (column) {
      return _legendColumnHeight(column, opts.rowGap);
    });
    // Configured legend notes and pattern hints are rendered below the categories.
    opts.footnote = null;
    var footnoteLabel = _legendFootnoteLabel(cfg, true);
    if (footnoteLabel) {
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

  function _offsetProjection(projection, offsetX, offsetY) {
    if (!offsetX && !offsetY) return projection;
    var translation = projection.translate();
    return projection.translate([
      translation[0] + (offsetX || 0),
      translation[1] + (offsetY || 0)
    ]);
  }

  function _mapBoundsForExtent(fitData, extent, offsetX, offsetY) {
    var projection = _offsetProjection(
      d3.geoMercator().fitExtent(extent, fitData), offsetX, offsetY
    );
    var bounds = d3.geoPath().projection(projection).bounds(fitData);
    return {
      x: bounds[0][0],
      y: bounds[0][1],
      width: bounds[1][0] - bounds[0][0],
      height: bounds[1][1] - bounds[0][1],
      scale: projection.scale()
    };
  }

  // Find the projected geometry range within a band on the other axis. Boundary
  // crossings are interpolated so sparse polygon vertices do not hide overlap.
  function _projectedRangeInBand(
    geometryData, fitData, extent, bandAxis, minBand, maxBand, offsetX, offsetY
  ) {
    var projection = _offsetProjection(
      d3.geoMercator().fitExtent(extent, fitData), offsetX, offsetY
    );
    var minEdge = Infinity;
    var maxEdge = -Infinity;
    var previous = null;
    var inLine = false;
    function pointValues(x, y) {
      return bandAxis === 'x'
        ? { band: x, edge: y }
        : { band: y, edge: x };
    }
    function record(point) {
      if (point.band >= minBand && point.band <= maxBand) {
        minEdge = Math.min(minEdge, point.edge);
        maxEdge = Math.max(maxEdge, point.edge);
      }
    }
    var stream = {
      point: function (x, y) {
        var current = pointValues(x, y);
        record(current);
        if (inLine && previous && current.band !== previous.band) {
          [minBand, maxBand].forEach(function (boundary) {
            var crossesBoundary = (previous.band < boundary && current.band > boundary)
              || (previous.band > boundary && current.band < boundary);
            if (crossesBoundary) {
              var ratio = (boundary - previous.band) / (current.band - previous.band);
              var crossing = previous.edge + (current.edge - previous.edge) * ratio;
              minEdge = Math.min(minEdge, crossing);
              maxEdge = Math.max(maxEdge, crossing);
            }
          });
        }
        if (inLine) previous = current;
      },
      lineStart: function () {
        inLine = true;
        previous = null;
      },
      lineEnd: function () {
        inLine = false;
        previous = null;
      },
      polygonStart: function () { },
      polygonEnd: function () { },
      sphere: function () { }
    };
    d3.geoStream(geometryData, projection.stream(stream));
    return { min: minEdge, max: maxEdge };
  }

  function _projectedEdgesInBand(
    geometryData, fitData, extent, minY, maxY, offsetX, offsetY
  ) {
    var range = _projectedRangeInBand(
      geometryData, fitData, extent, 'y', minY, maxY, offsetX, offsetY
    );
    return { left: range.min, right: range.max };
  }

  function _projectedVerticalEdgesInBand(
    geometryData, fitData, extent, minX, maxX, offsetX, offsetY
  ) {
    var range = _projectedRangeInBand(
      geometryData, fitData, extent, 'x', minX, maxX, offsetX, offsetY
    );
    return { top: range.min, bottom: range.max };
  }

  function _horizontalCornerOffset(position, edges, legend, gap) {
    if (position.indexOf('right') !== -1) {
      if (edges.right === -Infinity) return 0;
      return Math.min(0, legend.x - gap - edges.right);
    }
    if (edges.left === Infinity) return 0;
    return Math.max(0, legend.x + legend.width + gap - edges.left);
  }

  function _verticalCornerOffset(position, edges, legend, gap) {
    if (position.indexOf('bottom') !== -1) {
      if (edges.bottom === -Infinity) return 0;
      return Math.min(0, legend.y - gap - edges.bottom);
    }
    if (edges.top === Infinity) return 0;
    return Math.max(0, legend.y + legend.height + gap - edges.top);
  }

  // ---- export legend layout (constraint-driven) ----------------------------
  // The renderer consumes one resolved config, ``cfg.exportLegend`` =
  // { placement, mapLayout, columns, itemFlow, maxWidthFraction } with explicit
  // auto/fixed values.
  // From it we generate candidate layouts, reject any that violate a hard
  // invariant (clipping, empty map, unreadable text, or disallowed overlap),
  // then score the survivors deterministically.

  var EXPORT_LEGEND_MARGIN = 46;
  var EXPORT_LEGEND_TITLE_BLOCK = 46;
  var EXPORT_LEGEND_GAP = 24;
  // The eight compass positions are independent from whether the map is fitted
  // around the legend or the legend overlays the full map area.
  var EXPORT_LEGEND_POSITIONS = [
    'top-left', 'top', 'top-right', 'right',
    'bottom-right', 'bottom', 'bottom-left', 'left'
  ];
  var EXPORT_LEGEND_FIT_SIDES = {
    'top-left': ['left', 'top'],
    'top': ['top'],
    'top-right': ['right', 'top'],
    'right': ['right'],
    'bottom-right': ['right', 'bottom'],
    'bottom': ['bottom'],
    'bottom-left': ['left', 'bottom'],
    'left': ['left']
  };
  // When no candidate is fully valid, the least-bad one is chosen by summed
  // violation cost first: clipping the legend or destroying the map area are
  // far worse than an over-wide column count or slightly tight text.
  var EXPORT_LEGEND_VIOLATION_COST = {
    'clipped': 1000000,
    'invalid-map': 1000000,
    'overlap': 100000,
    'readability': 1000,
    'columns': 100
  };

  function _exportCandidateViolationCost(candidate) {
    return candidate.violations.reduce(function (total, violation) {
      return total + (EXPORT_LEGEND_VIOLATION_COST[violation] || 1);
    }, 0);
  }

  // Choose the least-bad candidate: lowest summed violation cost wins, and the
  // normal score breaks ties. Deterministic given the fixed generation order.
  function _pickLeastBadExportCandidate(pool) {
    return pool.reduce(function (selected, candidate) {
      if (!selected) return candidate;
      if (candidate.violationCost < selected.violationCost) return candidate;
      if (
        candidate.violationCost === selected.violationCost
        && candidate.score > selected.score
      ) {
        return candidate;
      }
      return selected;
    }, null);
  }

  function _resolvedExportLegend(cfg) {
    var resolved = cfg && cfg.exportLegend;
    var defaults = _exportDefaults();
    var atlasLegend = _defaults().exportLegend || {};
    var fallbackWidth = defaults.legendMaxWidthFraction || 0.52;
    var fallbackItemFlow = atlasLegend.itemFlow === 'row' ? 'row' : 'column';
    if (!resolved) {
      // Backward compatibility for any caller that still passes flat keys.
      resolved = {
        placement: cfg && cfg.exportLegendPlacement,
        mapLayout: cfg && cfg.exportLegendMapLayout,
        columns: cfg && cfg.exportLegendColumns,
        itemFlow: cfg && cfg.exportLegendItemFlow,
        maxWidthFraction: cfg && cfg.exportLegendWidth
      };
    }
    var placement = resolved.placement || 'auto';
    var mapLayout = resolved.mapLayout || atlasLegend.mapLayout || 'auto';
    var columns = resolved.columns == null ? 'auto' : resolved.columns;
    var maxWidthFraction = Number(resolved.maxWidthFraction) || fallbackWidth;
    var itemFlow = resolved.itemFlow;
    if (mapLayout !== 'fit' && mapLayout !== 'overlay') mapLayout = 'auto';
    if (itemFlow !== 'row' && itemFlow !== 'column') itemFlow = fallbackItemFlow;
    return {
      placement: placement,
      mapLayout: mapLayout,
      columns: columns,
      itemFlow: itemFlow,
      maxWidthFraction: maxWidthFraction
    };
  }

  // The arrangement of legend entries across the legend columns, shared by the
  // screen legend and the export so a configured arrangement is honoured in
  // both. The screen legend has its own column count (``legendColumns``).
  function _legendItemFlow(cfg) {
    return _resolvedExportLegend(cfg).itemFlow;
  }

  function _exportLegendPlacementCandidates(placement) {
    if (placement && placement !== 'auto') return [placement];
    return EXPORT_LEGEND_POSITIONS.slice();
  }

  function _exportLegendLayoutCandidates(placement, mapLayout) {
    var candidates = [];
    _exportLegendPlacementCandidates(placement).forEach(function (position) {
      if (mapLayout === 'fit') {
        if (position.indexOf('-') !== -1) {
          candidates.push({ position: position, mapLayout: 'fit', fitSide: 'shape-x' });
          candidates.push({ position: position, mapLayout: 'fit', fitSide: 'shape-y' });
        }
        EXPORT_LEGEND_FIT_SIDES[position].forEach(function (fitSide) {
          candidates.push({ position: position, mapLayout: 'fit', fitSide: fitSide });
        });
      } else if (mapLayout === 'overlay') {
        candidates.push({ position: position, mapLayout: 'overlay', fitSide: null });
      } else if (position.indexOf('-') === -1) {
        candidates.push({ position: position, mapLayout: 'fit', fitSide: position });
      } else {
        candidates.push({ position: position, mapLayout: 'auto', fitSide: null });
      }
    });
    return candidates;
  }

  function _exportLegendColumnCandidates(columns) {
    if (columns && columns !== 'auto') return [Number(columns)];
    return [1, 2, 3, 4];
  }

  function _exportCandidateViolations(candidate) {
    var violations = [];
    var right = _exportWidth() - EXPORT_LEGEND_MARGIN;
    var bottom = candidate.height - EXPORT_LEGEND_MARGIN;
    var l = candidate.legend;
    if (
      l.x < EXPORT_LEGEND_MARGIN - 0.5
      || l.y < EXPORT_LEGEND_MARGIN - 0.5
      || l.x + l.width > right + 0.5
      || l.y + l.height > bottom + 0.5
    ) {
      violations.push('clipped');
    }
    if (candidate.mapWidth <= 0 || candidate.mapHeight <= 0 || candidate.mapClipped) {
      violations.push('invalid-map');
    }
    if (candidate.textWidth < candidate.minTextWidth) {
      violations.push('readability');
    }
    if (candidate.columns > candidate.itemCount) {
      violations.push('columns');
    }
    if (candidate.overlay && !candidate.allowOverlap && candidate.overlapsShapes) {
      violations.push('overlap');
    }
    return violations;
  }

  function _scoreExportCandidate(candidate, preferredHeightMm) {
    var pageArea = _exportWidth() * candidate.height;
    var usedAreaRatio = pageArea > 0
      ? (candidate.mapArea + candidate.legendArea) / pageArea
      : 0;
    return candidate.mapScale * 100000
      - (candidate.heightMm - preferredHeightMm) * 120000
      - candidate.wrappedLines * 4000
      - (Math.abs(candidate.mapOffsetX || 0) + Math.abs(candidate.mapOffsetY || 0))
      + usedAreaRatio * 500;
  }

  function _positionExportLegend(position, legend, exportWidth, exportHeight) {
    var left = EXPORT_LEGEND_MARGIN;
    var right = exportWidth - EXPORT_LEGEND_MARGIN - legend.width;
    var top = EXPORT_LEGEND_TITLE_BLOCK;
    var bottom = exportHeight - EXPORT_LEGEND_MARGIN - legend.height;
    var centerX = Math.round((exportWidth - legend.width) / 2);
    var centerY = Math.round((top + exportHeight - EXPORT_LEGEND_MARGIN - legend.height) / 2);
    return {
      x: position.indexOf('left') !== -1 ? left
        : (position.indexOf('right') !== -1 ? right : centerX),
      y: position.indexOf('top') !== -1 ? top
        : (position.indexOf('bottom') !== -1 ? bottom : centerY)
    };
  }

  function _fitMapExtent(fitSide, legend, exportWidth, exportHeight) {
    var extent = [
      [EXPORT_LEGEND_MARGIN, EXPORT_LEGEND_TITLE_BLOCK],
      [exportWidth - EXPORT_LEGEND_MARGIN, exportHeight - EXPORT_LEGEND_MARGIN]
    ];
    if (fitSide === 'right') {
      extent[1][0] = legend.x - EXPORT_LEGEND_GAP;
    } else if (fitSide === 'left') {
      extent[0][0] = legend.x + legend.width + EXPORT_LEGEND_GAP;
    } else if (fitSide === 'top') {
      extent[0][1] = legend.y + legend.height + EXPORT_LEGEND_GAP;
    } else if (fitSide === 'bottom') {
      extent[1][1] = legend.y - EXPORT_LEGEND_GAP;
    }
    return extent;
  }

  function _exportLayout(data, cfg) {
    // Ensure cfg._hasNoData is up to date before measuring the legend.
    _annotateFeatures(data, cfg);
    var gap = EXPORT_LEGEND_GAP;
    var exportWidth = _exportWidth();
    var preferredHeightMm = _exportDefaults().heightMm;
    // Country border for full maps, subdivisions for regional maps.
    var fitData = _fitGeometry(data, cfg);
    var resolved = _resolvedExportLegend(cfg);
    var layoutOptions = _exportLegendLayoutCandidates(
      resolved.placement, resolved.mapLayout
    );
    var columnOptions = _exportLegendColumnCandidates(resolved.columns);
    var maxLegendWidth = Math.round(exportWidth * resolved.maxWidthFraction);
    var minTextWidth = Math.max(40, Math.round(_exportLegendFontSize() * 2));
    var order = 0;
    var candidates = [];

    // Within one layout pass cfg and the maximum width are constant, so a
    // measured legend depends only on the column count. Memoising it avoids
    // re-measuring the same legend for every page-height/placement combination.
    var measureCache = {};
    function measureLegend(columnCount) {
      var key = maxLegendWidth + ':' + columnCount;
      if (!(key in measureCache)) {
        measureCache[key] = _measureExportLegend(
          cfg, maxLegendWidth, columnCount, resolved.itemFlow
        );
      }
      return measureCache[key];
    }
    // A projected-edge scan is a full d3.geoStream pass; cache it by the exact
    // inputs that change the result (map extent, axis, band and offset).
    var edgesCache = {};
    function projectedEdgesInBand(extent, minY, maxY, offsetX, offsetY) {
      var key = 'y:' + extent[0][0] + ',' + extent[0][1] + ','
        + extent[1][0] + ',' + extent[1][1] + ':' + minY + ',' + maxY
        + ':' + (offsetX || 0) + ',' + (offsetY || 0);
      if (!(key in edgesCache)) {
        edgesCache[key] = _projectedEdgesInBand(
          fitData, fitData, extent, minY, maxY, offsetX, offsetY
        );
      }
      return edgesCache[key];
    }
    function projectedVerticalEdgesInBand(extent, minX, maxX, offsetX, offsetY) {
      var key = 'x:' + extent[0][0] + ',' + extent[0][1] + ','
        + extent[1][0] + ',' + extent[1][1] + ':' + minX + ',' + maxX
        + ':' + (offsetX || 0) + ',' + (offsetY || 0);
      if (!(key in edgesCache)) {
        edgesCache[key] = _projectedVerticalEdgesInBand(
          fitData, fitData, extent, minX, maxX, offsetX, offsetY
        );
      }
      return edgesCache[key];
    }

    _exportHeightCandidatesMm().forEach(function (heightMm) {
      var exportHeight = Math.round(heightMm / 25.4 * _exportDefaults().dpi);
      layoutOptions.forEach(function (layoutOption) {
        var overlay = layoutOption.fitSide === null;
        var allowOverlap = layoutOption.mapLayout === 'overlay';
        columnOptions.forEach(function (columnCount) {
          var measuredLegend = measureLegend(columnCount);
          var position = _positionExportLegend(
            layoutOption.position, measuredLegend, exportWidth, exportHeight
          );
          var legend = Object.assign({}, measuredLegend, position);
          var mapExtent = _fitMapExtent(
            layoutOption.fitSide, legend, exportWidth, exportHeight
          );
          var mapWidth = mapExtent[1][0] - mapExtent[0][0];
          var mapHeight = mapExtent[1][1] - mapExtent[0][1];
          var invalidMap = mapWidth <= 0 || mapHeight <= 0;
          var mapOffsetX = 0;
          var mapOffsetY = 0;
          var shapeEdges = null;
          var shapeEdgesMissing = false;
          if (layoutOption.fitSide === 'shape-x' && !invalidMap) {
            shapeEdges = projectedEdgesInBand(
              mapExtent, legend.y, legend.y + legend.height
            );
            shapeEdgesMissing = shapeEdges.left === Infinity
              || shapeEdges.right === -Infinity;
            mapOffsetX = _horizontalCornerOffset(
              layoutOption.position, shapeEdges, legend, gap
            );
          } else if (layoutOption.fitSide === 'shape-y' && !invalidMap) {
            shapeEdges = projectedVerticalEdgesInBand(
              mapExtent, legend.x, legend.x + legend.width
            );
            shapeEdgesMissing = shapeEdges.top === Infinity
              || shapeEdges.bottom === -Infinity;
            mapOffsetY = _verticalCornerOffset(
              layoutOption.position, shapeEdges, legend, gap
            );
          }
          var mapBounds = invalidMap
            ? { x: 0, y: 0, width: 0, height: 0, scale: 0 }
            : _mapBoundsForExtent(fitData, mapExtent, mapOffsetX, mapOffsetY);
          var shapeFit = layoutOption.fitSide === 'shape-x'
            || layoutOption.fitSide === 'shape-y';
          var mapClipped = shapeFit && (
            !shapeEdges
            || shapeEdgesMissing
            || mapBounds.x < EXPORT_LEGEND_MARGIN - 0.5
            || mapBounds.x + mapBounds.width > exportWidth - EXPORT_LEGEND_MARGIN + 0.5
            || mapBounds.y < EXPORT_LEGEND_TITLE_BLOCK - 0.5
            || mapBounds.y + mapBounds.height > exportHeight - EXPORT_LEGEND_MARGIN + 0.5
          );

          // Automatic overlays remain valid only over genuinely empty space;
          // an explicit overlay layout deliberately permits covering shapes.
          var overlapsShapes = false;
          if (overlay && !allowOverlap && !invalidMap) {
            var edges = projectedEdgesInBand(
              mapExtent, legend.y, legend.y + legend.height
            );
            overlapsShapes = edges.right !== -Infinity
              && edges.left !== Infinity
              && legend.x < edges.right + gap
              && legend.x + legend.width > edges.left - gap;
          }

          candidates.push({
            order: order++,
            name: layoutOption.position,
            mapLayout: layoutOption.mapLayout,
            overlay: overlay,
            allowOverlap: allowOverlap,
            columns: columnCount,
            heightMm: heightMm,
            height: exportHeight,
            legend: legend,
            mapExtent: mapExtent,
            mapOffsetX: mapOffsetX,
            mapOffsetY: mapOffsetY,
            mapWidth: mapWidth,
            mapHeight: mapHeight,
            mapClipped: mapClipped,
            mapScale: mapBounds.scale,
            mapArea: mapBounds.width * mapBounds.height,
            legendArea: legend.width * legend.height,
            textWidth: legend.textWidth,
            minTextWidth: minTextWidth,
            itemCount: legend.itemCount,
            wrappedLines: legend.wrappedLines,
            overlapsShapes: overlapsShapes
          });
        });
      });
    });

    candidates.forEach(function (candidate) {
      candidate.violations = _exportCandidateViolations(candidate);
      candidate.valid = candidate.violations.length === 0;
      candidate.violationCost = _exportCandidateViolationCost(candidate);
      candidate.score = _scoreExportCandidate(candidate, preferredHeightMm);
    });

    function pickBest(pool) {
      return pool.reduce(function (selected, candidate) {
        // Strict ``>`` keeps the first candidate on ties, so selection is
        // deterministic given the fixed generation order.
        if (!selected || candidate.score > selected.score) return candidate;
        return selected;
      }, null);
    }

    var valid = candidates.filter(function (c) { return c.valid; });
    var warning = null;
    var best = pickBest(valid);
    if (!best) {
      // No layout satisfies the constraints; surface an actionable warning
      // instead of silently ignoring a setting, but still render the least-bad
      // option so the export is inspectable. Rank by summed violation severity
      // first (clipping/invalid map dominate), then by the normal score.
      best = _pickLeastBadExportCandidate(candidates);
      warning = 'No export legend layout satisfies the configured constraints'
        + ' (' + (best ? best.violations.join(', ') : 'none') + ').'
        + ' Adjust placement, columns or maximum width.';
    }

    return {
      exportMode: true,
      width: exportWidth,
      height: best.height,
      widthMm: _exportDefaults().widthMm,
      heightMm: best.heightMm,
      mapExtent: best.mapExtent,
      mapOffsetX: best.mapOffsetX,
      mapOffsetY: best.mapOffsetY,
      showHeader: false,
      titleY: 50,
      subtitleY: 82,
      titleFontSize: 38,
      subtitleFontSize: 22,
      legend: best.legend,
      legendPlacement: best.name,
      legendColumns: best.columns,
      legendItemFlow: resolved.itemFlow,
      warning: warning
    };
  }

  // ---- quartile helpers -----------------------------------------------------

  function _computeQuartileCategories(values, colors, displayMultiplier) {
    var valid = values.filter(function (v) { return v != null && !isNaN(v); });
    if (valid.length < 4) return null;
    var sorted = valid.slice().sort(function (a, b) { return a - b; });
    var q1 = d3.quantile(sorted, 0.25);
    var q2 = d3.quantile(sorted, 0.50);
    var q3 = d3.quantile(sorted, 0.75);
    var min = sorted[0];
    var max = sorted[sorted.length - 1];
    colors = colors || _defaults().quartileColors;
    displayMultiplier = displayMultiplier || 1;

    function fmt(v) {
      if (v == null) return '';
      var scaled = v * displayMultiplier;
      var epsilon = Number.EPSILON * Math.max(1, Math.abs(scaled));
      return Math.round(scaled + epsilon).toString();
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

  function _matchesQuartileSpecialCase(record, specialCase) {
    var value = record[specialCase.field];
    if (Object.prototype.hasOwnProperty.call(specialCase, 'equals')) {
      return value === specialCase.equals;
    }
    return Boolean(value);
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
      return specialCases.some(function (sc) {
        return _matchesQuartileSpecialCase(r, sc);
      });
    }

    var values = records
      .filter(function (r) { return !isPreservedRecord(r) && !isSpecialCaseRecord(r); })
      .map(function (r) { return r[baseCfg.numericField]; });
    var categories = _computeQuartileCategories(
      values,
      baseCfg.quartileColors,
      baseCfg.quartileDisplayMultiplier
    );
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
          var cls = null;
          var legacy = legacyLookup[r.catchment_id];
          var legacyClass = legacy ? legacy[baseCfg.dataField] : null;
          if (legacyClass && preserveClassLookup[legacyClass]) {
            cls = legacyClass;
          }
          for (var i = 0; i < specialCases.length; i++) {
            var sc = specialCases[i];
            if (cls === null && _matchesQuartileSpecialCase(r, sc)) {
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

  var NON_DOOR_TO_DOOR_COLLECTION_SYSTEMS = [
    'No separate collection',
    'Bring point',
    'Recycling centre',
    'On demand kerbside collection',
    'Home-composting'
  ];

  function _isNonDoorToDoorCollectionSystem(value) {
    return NON_DOOR_TO_DOOR_COLLECTION_SYSTEMS.indexOf(value) !== -1;
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
        return { catchment_id: r.catchment_id, _classified: cls };
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
    biowasteFeeSystem: function (records) {
      return records.map(function (r) {
        return {
          catchment_id: r.catchment_id,
          _classified: _isNonDoorToDoorCollectionSystem(r.fee_system)
            ? 'no_door_to_door'
            : r.fee_system
        };
      });
    },
    rpBiowasteCollectionCount: function (records) {
      return records.map(function (r) {
        var count = r.collection_count;
        var cls;
        if (r.is_door_to_door === false) {
          cls = 'no_door_to_door';
        } else if (count === 13) {
          cls = '13';
        } else if (count >= 14 && count <= 25) {
          cls = '14_25';
        } else if (count === 26) {
          cls = '26';
        } else if (count >= 27 && count <= 39) {
          cls = '27_39';
        } else if (count >= 40 && count <= 51) {
          cls = '40_51';
        } else if (count === 52) {
          cls = '52';
        } else if (count > 52) {
          cls = 'over_52';
        } else if (count != null) {
          cls = 'under_13';
        } else {
          cls = null;
        }
        return { catchment_id: r.catchment_id, _classified: cls };
      });
    },
    rpResidualCollectionCount: function (records) {
      return records.map(function (r) {
        var count = r.collection_count;
        var cls;
        if (count === 13) {
          cls = '13';
        } else if (count >= 14 && count <= 25) {
          cls = '14_25';
        } else if (count === 26) {
          cls = '26';
        } else if (count >= 27 && count <= 39) {
          cls = '27_39';
        } else if (count >= 40 && count <= 51) {
          cls = '40_51';
        } else if (count === 52) {
          cls = '52';
        } else if (count > 52) {
          cls = 'over_52';
        } else if (count != null) {
          cls = 'under_13';
        } else {
          cls = null;
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
      return records.map(function (r) {
        var cls = _isNonDoorToDoorCollectionSystem(r.frequency_type)
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
        } else if (r.min_bin_size < 40) {
          cls = 'under_40';
        } else if (r.min_bin_size === 40) {
          cls = 'exactly_40';
        } else if (r.min_bin_size < 60) {
          cls = 'between_40_and_60';
        } else if (r.min_bin_size === 60) {
          cls = 'exactly_60';
        } else if (r.min_bin_size < 80) {
          cls = 'between_60_and_80';
        } else if (r.min_bin_size === 80) {
          cls = 'exactly_80';
        } else if (r.min_bin_size < 120) {
          cls = 'between_80_and_120';
        } else if (r.min_bin_size === 120) {
          cls = 'exactly_120';
        } else {
          cls = 'over_120';
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
    rpCollectionCountRatio: function (records) {
      return records.map(function (r) {
        var cls;
        if (r.bio_is_door_to_door === false ||
          (r.bio_is_door_to_door == null && r.residual_count != null)) {
          cls = 'no_bio';
        } else if (r.ratio >= 2) {
          cls = 'two_to_one';
        } else if (r.ratio > 1 && r.ratio < 2) {
          cls = 'between_two_and_one';
        } else if (r.ratio === 1) {
          cls = 'one_to_one';
        } else if (r.ratio != null) {
          cls = 'below_one_to_one';
        } else {
          cls = null;
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
        if (_isNonDoorToDoorCollectionSystem(r.bio_fee)) {
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
      return records.map(function (r) {
        var cls;
        if (_isNonDoorToDoorCollectionSystem(r.bio_frequency)) {
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
        } else if (r.connection_rate === 1) {
          cls = 'full_connection';
        } else if (r.connection_rate >= 0.75) {
          cls = '75-99';
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
        if (r.no_collection) {
          cls = 'no_collection';
        } else if (r.amount === null) {
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
        } else if (r.min_bin_size < 40) {
          cls = 'under_40';
        } else if (r.min_bin_size === 40) {
          cls = 'exactly_40';
        } else if (r.min_bin_size < 60) {
          cls = 'between_40_and_60';
        } else if (r.min_bin_size === 60) {
          cls = 'exactly_60';
        } else if (r.min_bin_size < 80) {
          cls = 'between_60_and_80';
        } else if (r.min_bin_size === 80) {
          cls = 'exactly_80';
        } else if (r.min_bin_size < 120) {
          cls = 'between_80_and_120';
        } else if (r.min_bin_size === 120) {
          cls = 'exactly_120';
        } else {
          cls = 'over_120';
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
    // Projection — fit to country border (or filtered regions when nutsPrefix is set)
    var fitData = _fitGeometry(data, cfg);
    var layout = options.layout || _screenLayout(container, fitData);
    var width = layout.width;
    var height = layout.height;
    // A new render replaces the geography a picker was anchored to.
    if (!layout.exportMode) _closeCollectionPicker();

    _svg = options.svgSelection || d3.select('#' + cfg.svgId);
    _svg
      .attr('xmlns', 'http://www.w3.org/2000/svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', '0 0 ' + width + ' ' + height)
      .attr('class', 'waste-atlas-export-svg');

    _svg.selectAll('*').remove();

    // Geographic layers live in one group so the screen zoom transform can move
    // and scale them without touching the title or the legend.
    var mapRoot = _svg.append('g').attr('class', 'layer-map-root');
    if (!layout.exportMode) _mapRoot = mapRoot;

    var projection = _offsetProjection(
      d3.geoMercator().fitExtent(layout.mapExtent, fitData),
      layout.mapOffsetX,
      layout.mapOffsetY
    );
    var path = d3.geoPath().projection(projection);

    // The ACPV markers are sized against the drawn map, not the canvas.
    var projectedBounds = path.bounds(fitData);
    var acpvStyle = _acpvStyle(cfg, projectedBounds[1][0] - projectedBounds[0][0]);
    _defineOverlayPattern(cfg, projectedBounds[1][0] - projectedBounds[0][0]);

    // Layer 1: background fill (filtered NUTS1 regions when nutsPrefix set, else full country)
    var fillData = (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
    if (fillData && fillData.features) {
      mapRoot.append('g').attr('class', 'layer-country-fill')
        .selectAll('path')
        .data(fillData.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', _defaults().countryFill)
        .attr('stroke', 'none');
    }

    // Layer 2: all catchments (border-only background for those without data this year)
    if (data.allCatchments && data.allCatchments.features) {
      mapRoot.append('g').attr('class', 'layer-catchments-all')
        .selectAll('path')
        .data(data.allCatchments.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', _defaults().catchmentStroke)
        .attr('stroke-width', _defaults().catchmentStrokeWidth);
    }

    // Layer 3: catchments with data (thin borders)
    if (data.catchments.features) {
      var catchmentPaths = mapRoot.append('g').attr('class', 'layer-catchments')
        .selectAll('path')
        .data(data.catchments.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', function (d) {
          return _colorFor(d.properties._thematic_value, cfg.categories, cfg.noDataColor);
        })
        .attr('stroke', _defaults().catchmentStroke)
        .attr('stroke-width', _defaults().catchmentStrokeWidth);

      if (!layout.exportMode) {
        catchmentPaths
          .attr('tabindex', function (d) {
            return _collectionDetailUrl(d) ? 0 : null;
          })
          .attr('role', function (d) {
            return _collectionDetailUrl(d) ? 'link' : null;
          })
          .attr('aria-label', function (d) {
            var options = _collectionOptions(d);
            if (!options.length) return null;
            if (options.length > 1) {
              return 'Choose a collection for ' + d.properties.catchment_name;
            }
            return 'Open collection for ' + d.properties.catchment_name;
          })
          .style('cursor', function (d) {
            return _collectionDetailUrl(d) ? 'pointer' : null;
          })
          .on('click', function (event, d) {
            event.stopPropagation();
            // d3-zoom itself cancels the click that terminates a real drag.
            _openCollectionChoice(event, d);
          })
          .on('auxclick', function (event, d) {
            if (event.button !== 1) return;
            event.preventDefault();
            event.stopPropagation();
            // One collection goes straight to a new tab; several have no single
            // destination, so offer the choice as a left click would.
            if (!_openCollectionInNewTab(d)) _openCollectionChoice(event, d);
          })
          .on('keydown', function (event, d) {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            event.stopPropagation();
            _openCollectionChoice(event, d);
          });
      }

      catchmentPaths.append('title')
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
          if (_collectionDetailUrl(d)) tooltip += '\nClick to open collection';
          return tooltip;
        });
    }

    if (cfg.overlayPatternField && data.catchments.features) {
      mapRoot.append('g').attr('class', 'layer-catchments-overlay')
        .selectAll('path')
        .data(data.catchments.features.filter(function (d) {
          return d.properties._overlay_pattern && d.properties._thematic_value != null;
        }))
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'url(#' + _overlayPatternId(cfg) + ')')
        .attr('stroke', 'none')
        .attr('pointer-events', 'none');
    }

    if (data.acpvOutlines && data.acpvOutlines.features) {
      mapRoot.append('g').attr('class', 'layer-acpv-outlines')
        .selectAll('path')
        .data(data.acpvOutlines.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', acpvStyle.outlineColor)
        .attr('stroke-opacity', acpvStyle.outlineOpacity)
        .attr('stroke-width', acpvStyle.outlineWidth)
        .attr('stroke-linejoin', 'round')
        .attr('stroke-linecap', 'round')
        .attr('pointer-events', 'none');
    }

    // Maintainer aid: outline catchments whose theme value is ambiguous
    // (more than one collection competes for the single displayed slot).
    // Screen-only: the export legend carries no conflict entry, so drawing
    // the outlines in exports would leave them unexplained.
    if (_conflictEnabled && !layout.exportMode && _conflictCatchments && _conflictCatchments.size && data.catchments.features) {
      mapRoot.append('g').attr('class', 'layer-catchments-conflict')
        .selectAll('path')
        .data(data.catchments.features.filter(function (d) {
          return _conflictCatchments.has(d.properties.catchment_id);
        }))
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', _defaults().conflictStroke)
        .attr('stroke-width', _defaults().conflictStrokeWidth)
        .attr('stroke-dasharray', _defaults().conflictStrokeDasharray)
        .attr('stroke-linejoin', 'round')
        .attr('pointer-events', 'none');
    }

    var hasRegionalBorder = cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features
      && data.bundeslaender.features.length;

    // Layer 4: Bundesländer borders (on top of catchments)
    if (!hasRegionalBorder && data.bundeslaender && data.bundeslaender.features) {
      mapRoot.append('g').attr('class', 'layer-bundeslaender')
        .selectAll('path')
        .data(data.bundeslaender.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', _defaults().subdivisionStroke)
        .attr('stroke-width', _defaults().subdivisionStrokeWidth);
    }

    // Layer 5: outer border (very top) — always show country border for full maps,
    // but show Bundesläender borders as outer border for regional maps (when nutsPrefix is set)
    var borderData = data.countryBorder;
    var borderStroke = _defaults().countryStroke;
    var borderWidth = _defaults().countryStrokeWidth;

    if (hasRegionalBorder) {
      // For regional maps (with nutsPrefix), use Bundesläender as outer border instead of country border
      borderData = data.bundeslaender;
      // Don't draw Bundesläender borders in layer 4 since we're drawing them as outer border
    }

    if (borderData && borderData.features) {
      mapRoot.append('g').attr('class', 'layer-country-border')
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

    // Re-apply the manual zoom/pan the user had set before this re-render
    // (window resize, toggles, …). Exports always render unzoomed.
    if (!layout.exportMode) {
      if (_zoomTransform) mapRoot.attr('transform', _zoomTransform);
      _updateZoomReadout();
    }
  }

  function _drawExportLegendItem(g, cat, x, y, opts) {
    var itemHeight = Math.max(
      _legendSlotHeight(cat) || 0,
      Math.max(opts.swatchH, cat.lines.length * opts.lineHeight)
    );
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
    var hasLegendFootnote = Boolean(_legendFootnoteLabel(cfg, false));
    var hasConflictLegend = !!(_conflictEnabled && cfg.conflictOverlayLabel
      && _conflictCatchments && _conflictCatchments.size);

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
      // Configured notes and pattern hints are separate from legend categories.
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

    var fontSize = Math.max(8, Math.min(24, Number(cfg.legendFontSize) || _defaults().legend.fontSize));
    var lineHeight = Math.round(fontSize * 1.18);
    var swatchH = Math.max(12, Math.round(fontSize * 1.3));
    var swatchW = Math.round(swatchH * 1.375);
    var gap = Math.max(5, Math.round(fontSize * 0.5));
    var paddingX = 10;
    var paddingY = 12;
    var labelGap = 8;
    var requestedWidth = Number(cfg.legendWidth) || _defaults().legend.width;
    var legendWidth = Math.max(120, Math.min(requestedWidth, width - 32));
    var legendColumns = Math.max(1, Math.floor(Number(cfg.legendColumns) || 1));
    var columnGap = gap * 2;
    var columnWidth = (legendWidth - paddingX * 2 - columnGap * (legendColumns - 1)) / legendColumns;
    var textWidth = columnWidth - swatchW - labelGap;
    var screenItems = _orderedLegendCategories(cfg).map(function (item) {
      return {
        color: item.color,
        lines: _wrapTextToWidth(item.label, textWidth, fontSize, SCREEN_LABEL_FONT),
        kind: 'category',
        threshold: item.threshold
      };
    });
    if (hasConflictLegend) {
      screenItems.push({
        color: '#ffffff',
        lines: _wrapTextToWidth(
          cfg.conflictOverlayLabel,
          textWidth,
          fontSize,
          SCREEN_LABEL_FONT
        ),
        kind: 'conflict'
      });
    }
    if (cfg.noDataLabel && cfg._hasFallbackNoData) {
      screenItems.push({
        color: cfg.noDataColor || _defaults().noDataColor,
        lines: _wrapTextToWidth(cfg.noDataLabel, textWidth, fontSize, SCREEN_LABEL_FONT),
        kind: 'no-data'
      });
    }
    _markTrailingLegendStatuses(cfg, screenItems);

    screenItems.forEach(function (item) {
      item.height = Math.max(swatchH, item.lines.length * lineHeight);
    });
    var titleLines = _wrapTextToWidth(
      cfg.legendTitle || '',
      legendWidth - paddingX * 2,
      fontSize,
      SCREEN_TITLE_FONT
    );
    var titleHeight = Math.max(fontSize, titleLines.length * lineHeight) + 10;
    var screenColumns = _distributeLegendItems(
      screenItems, legendColumns, _legendItemFlow(cfg), gap
    );
    var itemsHeight = Math.max.apply(null, screenColumns.map(function (column) {
      return _legendColumnHeight(column, gap);
    }));
    var footnoteLines = hasLegendFootnote
      ? _wrapTextToWidth(
        _legendFootnoteLabel(cfg, false),
        legendWidth - paddingX * 2,
        Math.max(8, fontSize - 2),
        SCREEN_LABEL_FONT
      )
      : [];
    var footnoteHeight = footnoteLines.length
      ? gap + 7 + footnoteLines.length * Math.max(10, lineHeight - 2)
      : 0;
    var totalH = paddingY * 2 + titleHeight + itemsHeight + footnoteHeight;
    var placement = cfg.legendPlacement || _defaults().legend.placement;
    var margin = 32;
    // Honour the configured side, but keep the vertical anchor at the top on
    // screen: the canvas is taller than the viewport, so a bottom legend would
    // sit below the fold on load. The configured side still wins for exports,
    // which never reach this code.
    var anchorTop = layout.legendAtTop || placement.indexOf('top') === 0;
    var legendX = placement.indexOf('right') !== -1
      ? width - margin - legendWidth
      : margin;
    var legendY = anchorTop
      ? margin
      : height - margin - totalH;
    legendX = Math.max(16, legendX);
    legendY = Math.max(16, legendY);

    var g = _svg.append('g')
      .attr('class', 'atlas-legend')
      .attr('transform', 'translate(' + legendX + ',' + legendY + ')');
    g.append('rect')
      .attr('width', legendWidth).attr('height', totalH)
      .attr('fill', 'white').attr('fill-opacity', 0.9)
      .attr('stroke', '#ccc').attr('rx', 4);
    var title = g.append('text')
      .attr('x', paddingX).attr('y', paddingY + fontSize)
      .attr('font-weight', 'bold').attr('font-size', fontSize)
      .attr('font-family', "'Nunito', sans-serif");
    titleLines.forEach(function (line, index) {
      title.append('tspan')
        .attr('x', paddingX)
        .attr('dy', index === 0 ? 0 : lineHeight)
        .text(line);
    });

    var currentY = paddingY + titleHeight;
    screenColumns.forEach(function (column, columnIndex) {
      var columnY = currentY;
      var columnX = paddingX + columnIndex * (columnWidth + columnGap);
      column.forEach(function (item, index) {
        if (index) columnY += gap;
        var swatchY = columnY + Math.round((item.height - swatchH) / 2);
        var slotHeight = _legendSlotHeight(item);
        var swatch = g.append('rect')
          .attr('x', columnX).attr('y', swatchY)
          .attr('width', swatchW).attr('height', swatchH)
          .attr('fill', item.color).attr('stroke', '#333');
        if (item.kind === 'conflict') {
          swatch
            .attr('stroke', _defaults().conflictStroke)
            .attr('stroke-width', 1.4)
            .attr('stroke-dasharray', _defaults().conflictStrokeDasharray);
        }
        var textX = columnX + swatchW + labelGap;
        var label = g.append('text')
          .attr('x', textX).attr('y', columnY + fontSize)
          .attr('font-size', fontSize)
          .attr('font-family', "'Nunito', sans-serif");
        item.lines.forEach(function (line, lineIndex) {
          label.append('tspan')
            .attr('x', textX)
            .attr('dy', lineIndex === 0 ? 0 : lineHeight)
            .text(line);
        });
        columnY += slotHeight;
      });
    });
    currentY += itemsHeight;

    if (hasLegendFootnote) {
      var footnoteLineY = currentY + gap;
      g.append('line')
        .attr('x1', paddingX).attr('y1', footnoteLineY)
        .attr('x2', legendWidth - paddingX).attr('y2', footnoteLineY)
        .attr('stroke', '#d0d4da').attr('stroke-width', 1);
      var footnoteFontSize = Math.max(8, fontSize - 2);
      var footnote = g.append('text')
        .attr('x', paddingX).attr('y', footnoteLineY + footnoteFontSize + 6)
        .attr('font-size', footnoteFontSize)
        .attr('font-style', 'italic')
        .attr('fill', '#6c757d')
        .attr('font-family', "'Nunito', sans-serif");
      footnoteLines.forEach(function (line, index) {
        footnote.append('tspan')
          .attr('x', paddingX)
          .attr('dy', index === 0 ? 0 : Math.max(10, lineHeight - 2))
          .text(line);
      });
    }
  }

  // ---- collection picker ------------------------------------------------------

  function _closeCollectionPicker() {
    if (!_collectionPicker) return;
    document.removeEventListener('keydown', _collectionPickerKeydown, true);
    document.removeEventListener('mousedown', _collectionPickerOutside, true);
    if (_collectionPicker.parentNode) {
      _collectionPicker.parentNode.removeChild(_collectionPicker);
    }
    _collectionPicker = null;
  }

  function _collectionPickerKeydown(event) {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    _closeCollectionPicker();
  }

  function _collectionPickerOutside(event) {
    if (_collectionPicker && !_collectionPicker.contains(event.target)) {
      _closeCollectionPicker();
    }
  }

  /**
   * Offer every collection behind an aggregated value, anchored at the click.
   *
   * Dismissed with Escape, by pressing outside, or as soon as the map moves
   * underneath it (zoom, pan, re-render).
   */
  function _openCollectionPicker(event, feature, options) {
    _closeCollectionPicker();
    var container = document.getElementById(_cfg.containerId);
    if (!container) return;

    var name = (feature && feature.properties && feature.properties.catchment_name) || '';
    var picker = document.createElement('div');
    picker.className = 'atlas-collection-picker';
    picker.setAttribute('role', 'group');
    picker.setAttribute('aria-label', 'Collections for ' + name);

    var title = document.createElement('p');
    title.className = 'atlas-collection-picker-title';
    title.textContent = name;
    picker.appendChild(title);

    options.forEach(function (option) {
      var link = document.createElement('a');
      link.className = 'atlas-collection-picker-link';
      link.href = option.url;
      link.textContent = option.label || option.url;
      picker.appendChild(link);
    });
    container.appendChild(picker);

    // Anchor at the pointer, clamped so the whole picker stays on the canvas.
    // Keyboard activation has no coordinates, so fall back to the centre.
    var rect = container.getBoundingClientRect();
    var hasPointer = event && event.clientX != null && event.clientY != null;
    var x = hasPointer ? event.clientX - rect.left : container.clientWidth / 2;
    var y = hasPointer ? event.clientY - rect.top : Math.min(container.clientHeight / 2, 320);
    picker.style.left = Math.max(
      8, Math.min(x + 8, Math.max(8, container.clientWidth - picker.offsetWidth - 8))
    ) + 'px';
    picker.style.top = Math.max(
      8, Math.min(y + 8, Math.max(8, container.clientHeight - picker.offsetHeight - 8))
    ) + 'px';

    _collectionPicker = picker;
    var firstLink = picker.querySelector('a');
    if (firstLink) firstLink.focus();
    document.addEventListener('keydown', _collectionPickerKeydown, true);
    document.addEventListener('mousedown', _collectionPickerOutside, true);
  }

  // ---- responsive canvas & manual zoom ---------------------------------------

  function _updateZoomReadout() {
    var readout = document.getElementById('atlas-map-zoom-level');
    if (!readout) return;
    var scale = _zoomTransform ? _zoomTransform.k : 1;
    readout.textContent = Math.round(scale * 100) + '%';
  }

  function _applyZoomTransform(transform) {
    // The picker is anchored to a screen position, not to the map.
    _closeCollectionPicker();
    _zoomTransform = transform;
    if (_mapRoot) _mapRoot.attr('transform', transform);
    _updateZoomReadout();
  }

  /** Scale around the canvas centre, as the +/- handles are not pointer events. */
  function _zoomBy(factor) {
    if (!_zoomBehavior || !_zoomTarget) return;
    var node = _zoomTarget.node();
    var box = node.viewBox.baseVal;
    var center = [(box.width || node.clientWidth) / 2, (box.height || node.clientHeight) / 2];
    _zoomTarget.transition().duration(180).call(_zoomBehavior.scaleBy, factor, center);
  }

  function _resetZoom() {
    _zoomTransform = null;
    if (_mapRoot) _mapRoot.attr('transform', null);
    if (_zoomBehavior && _zoomTarget) {
      _zoomTarget.call(_zoomBehavior.transform, d3.zoomIdentity);
    }
    _updateZoomReadout();
  }

  function _setupZoom(cfg) {
    var svgNode = document.getElementById(cfg.svgId);
    if (!svgNode || typeof d3.zoom !== 'function') return;

    _zoomTarget = d3.select(svgNode);
    _zoomBehavior = d3.zoom()
      .scaleExtent([ZOOM_MIN, ZOOM_MAX])
      .clickDistance(ZOOM_CLICK_DISTANCE)
      // Plain wheel keeps scrolling the page — the map is taller than the
      // viewport, so hijacking the wheel would trap the reader.
      .filter(function (event) {
        if (event.type === 'wheel') return event.ctrlKey || event.metaKey;
        return !event.button;
      })
      .on('zoom', function (event) {
        _applyZoomTransform(event.transform);
      });
    _zoomTarget
      .call(_zoomBehavior)
      .on('dblclick.zoom', null)
      // Canvas-wide, so a middle click never starts autoscroll, whether or not
      // it lands on a catchment.
      .on('mousedown.atlasautoscroll', _suppressAutoscroll);

    var bindings = [
      ['btn-map-zoom-in', function () { _zoomBy(ZOOM_STEP); }],
      ['btn-map-zoom-out', function () { _zoomBy(1 / ZOOM_STEP); }],
      ['btn-map-zoom-reset', _resetZoom]
    ];
    bindings.forEach(function (binding) {
      var button = document.getElementById(binding[0]);
      if (button) button.addEventListener('click', binding[1]);
    });
    _updateZoomReadout();
  }

  /** Re-render at the new canvas width so labels and strokes keep their size. */
  function _observeContainerResize(cfg) {
    var container = document.getElementById(cfg.containerId);
    if (!container) return;
    var lastWidth = container.clientWidth;
    var rerender = _debounce(function () {
      if (_lastData && _lastLoadCfg) _render(_lastData, _lastLoadCfg);
    }, 150);

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', rerender);
      return;
    }
    new ResizeObserver(function (entries) {
      var width = Math.round(entries[0].contentRect.width);
      if (!width || width === lastWidth) return;
      lastWidth = width;
      rerender();
    }).observe(container);
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
    if (layout.warning && typeof console !== 'undefined' && console.warn) {
      console.warn('Waste Atlas export: ' + layout.warning);
    }
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
    _downloadBlob(blob, filename || _defaultFileBase() + '.svg');
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
    var layout = svgEl.__wasteAtlasExportLayout || { width: _exportWidth(), height: _exportHeight() };
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
        _pngWithDpi(blob, _exportDefaults().dpi).then(function (pngBlob) {
          _downloadBlob(pngBlob, filename || _defaultFileBase() + '.png');
        });
      }, 'image/png');
    };
    img.src = url;
  }

  function exportElementSVG(svgEl, filename) {
    var source = _svgSource(svgEl);
    var blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    _downloadBlob(blob, filename || _defaultFileBase() + '.svg');
  }

  function exportElementPNG(svgEl, filename, dpi) {
    var width = parseInt(svgEl.getAttribute('width'), 10) || svgEl.viewBox.baseVal.width || _exportWidth();
    var height = parseInt(svgEl.getAttribute('height'), 10) || svgEl.viewBox.baseVal.height || _exportHeight();
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
        _pngWithDpi(blob, dpi || _exportDefaults().dpi).then(function (pngBlob) {
          _downloadBlob(pngBlob, filename || _defaultFileBase() + '.png');
        });
      }, 'image/png');
    };
    img.src = url;
  }

  // ---- public API -----------------------------------------------------------

  function init(cfg) {
    _cfg = cfg;
    setRenderDefaults(cfg.renderDefaults);
    var loadingEl = document.getElementById(cfg.loadingId);
    var btnSVG = document.getElementById('btn-export-svg');
    var btnPNG = document.getElementById('btn-export-png');
    var fileBase = cfg.fileBase || _defaultFileBase();
    var isQuartileMode = _isQuartileEnabled(cfg)
      && cfg.quartileDefaultEnabled !== false
      && !cfg.changeMode;

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
              thematicData: _changeRecords(
                loadCfg,
                data.fromThematicData,
                data.thematicData,
                data.catchments.features
              )
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
          // A new selection means a new extent; keep the manual zoom out of it.
          _resetZoom();
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

    _setupZoom(cfg);
    _observeContainerResize(cfg);

    load(cfg.country, cfg.year, true);

    initSelectorControls(function (country, year, _preserveScope, fromYear, replaceUrl, selectorUrl) {
      load(country, year, true, fromYear, replaceUrl, selectorUrl);
    }, { useChangeUrls: !!cfg.changeMode });

    var atlasControls = document.getElementById('atlas-controls');
    var atlasToggleMount = document.getElementById('atlas-map-tools') || atlasControls;
    var _atlasToggleBar = null;
    function _atlasToggleContainer() {
      if (!_atlasToggleBar) {
        _atlasToggleBar = document.createElement('div');
        _atlasToggleBar.className = 'atlas-map-toggles';
        atlasToggleMount.appendChild(_atlasToggleBar);
      }
      return _atlasToggleBar;
    }
    if (atlasControls && _isQuartileEnabled(cfg) && !cfg.changeMode) {
      var toggleWrap = document.createElement('label');
      toggleWrap.className = 'atlas-map-toggle';

      var toggleCheckbox = document.createElement('input');
      toggleCheckbox.type = 'checkbox';
      toggleCheckbox.checked = isQuartileMode;
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
      _atlasToggleContainer().appendChild(toggleWrap);
    }

    // Maintainer aid: highlight catchments where the dataset holds more than
    // one collection competing for the single displayed theme value.
    if (atlasControls && cfg.conflictUrl && cfg.conflictTheme && !cfg.changeMode) {
      var conflictWrap = document.createElement('label');
      conflictWrap.className = 'atlas-map-toggle';

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
      _atlasToggleContainer().appendChild(conflictWrap);
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

  function initShell() {
    var shell = document.getElementById('atlas-shell');
    if (!shell) return null;
    var tree = document.getElementById('atlas-tree');
    var toggle = document.getElementById('atlas-tree-toggle');
    var scrim = document.getElementById('atlas-tree-scrim');

    function setTreeOpen(open) {
      shell.classList.toggle('atlas-shell--tree-open', open);
      if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (toggle) {
      toggle.addEventListener('click', function () {
        setTreeOpen(!shell.classList.contains('atlas-shell--tree-open'));
      });
    }
    if (scrim) scrim.addEventListener('click', function () { setTreeOpen(false); });

    var filter = document.getElementById('atlas-tree-filter');
    if (filter && tree) {
      var links = Array.prototype.slice.call(tree.querySelectorAll('.atlas-tree-link'));
      var regions = Array.prototype.slice.call(tree.querySelectorAll('.atlas-tree-region'));
      var savedOpenStates = null;

      filter.addEventListener('input', _debounce(function () {
        var query = filter.value.trim().toLowerCase();
        if (query && savedOpenStates === null) {
          savedOpenStates = regions.map(function (region) { return region.open; });
        }
        links.forEach(function (link) {
          var haystack = link.getAttribute('data-search') || link.textContent || '';
          link.hidden = !!query && haystack.toLowerCase().indexOf(query) === -1;
        });
        tree.querySelectorAll('.atlas-tree-section').forEach(function (section) {
          section.hidden = !section.querySelector('.atlas-tree-link:not([hidden])');
        });
        tree.querySelectorAll('.atlas-tree-region-block').forEach(function (block) {
          block.hidden = !block.querySelector('.atlas-tree-link:not([hidden])');
        });
        regions.forEach(function (region, index) {
          var anyVisible = !!region.querySelector('.atlas-tree-link:not([hidden])');
          region.hidden = !!query && !anyVisible;
          if (query) {
            region.open = anyVisible;
          } else if (savedOpenStates) {
            region.open = savedOpenStates[index];
          }
        });
        if (!query) savedOpenStates = null;
      }, 120));
    }

    var activeLink = tree && tree.querySelector('.atlas-tree-link--active');
    if (activeLink && activeLink.scrollIntoView) {
      activeLink.scrollIntoView({ block: 'nearest' });
    }
    return { setTreeOpen: setTreeOpen };
  }

  return {
    init: init,
    setRenderDefaults: setRenderDefaults,
    initSelectorControls: initSelectorControls,
    initOverviewDirectory: initOverviewDirectory,
    initShell: initShell,
    selectorNavigationTarget: _selectorNavigationTarget,
    exportSVG: exportSVG,
    exportPNG: exportPNG,
    exportElementSVG: exportElementSVG,
    exportElementPNG: exportElementPNG,
    transforms: transforms,
    changes: {
      numericRecords: _numericChangeRecords,
      renderConfig: _changeRenderConfig
    },
    collections: {
      detailUrl: _collectionDetailUrl,
      openChoice: _openCollectionChoice
    },
    quartiles: {
      apply: _applyQuartiles,
      categories: _computeQuartileCategories
    },
    selection: {
      configForSelection: _configForSelection,
      queryString: _selectorQueryString,
      regionFromSelect: _regionFromSelect
    },
    // Appearance of the aggregated-value markers, shared by the screen and the
    // export; exposed for tests and callers that draw their own legend swatch.
    acpv: {
      style: _acpvStyle
    },
    // Legend entry order, shared by the screen legend and the export.
    legend: {
      annotateFeatures: _annotateFeatures,
      footnote: _legendFootnoteLabel,
      items: _legendItems,
      orderedCategories: _orderedLegendCategories,
      screenFontFamily: SCREEN_FONT_FAMILY
    },
    // Pure helpers for the export legend layout engine, exposed for tests and
    // for a future export preview that must share this exact layout path.
    layout: {
      resolveExportLegend: _resolvedExportLegend,
      exportLegendLabel: _exportLegendLabel,
      legendItemFlow: _legendItemFlow,
      placementCandidates: _exportLegendPlacementCandidates,
      layoutCandidates: _exportLegendLayoutCandidates,
      horizontalCornerOffset: _horizontalCornerOffset,
      verticalCornerOffset: _verticalCornerOffset,
      columnCandidates: _exportLegendColumnCandidates,
      distributeLegendItems: _distributeLegendItems,
      wrapTextToWidth: _wrapTextToWidth,
      fitExportLegendWidth: _fitExportLegendWidth,
      measureExportLegend: _measureExportLegend,
      legendColumnHeight: _legendColumnHeight,
      candidateViolations: _exportCandidateViolations,
      candidateViolationCost: _exportCandidateViolationCost,
      pickLeastBad: _pickLeastBadExportCandidate,
      scoreCandidate: _scoreExportCandidate,
      exportLayout: _exportLayout
    }
  };
})();
