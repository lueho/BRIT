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
  var BUNDESLAND_STROKE = '#000000';
  var BUNDESLAND_STROKE_WIDTH = 1.5;   // ≈ 0.4 mm at 96 DPI
  var COUNTRY_STROKE = '#000000';
  var COUNTRY_STROKE_WIDTH = 1.5;      // ≈ 0.4 mm at 96 DPI
  var CATCHMENT_STROKE = '#232323';
  var CATCHMENT_STROKE_WIDTH = 0.35;   // ≈ 0.1 mm at 96 DPI
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
  var _measureCtx = null;

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
    var catchUrl = base + 'catchment/geojson/?country=' + cfg.country + '&year=' + cfg.year + nutsSuffix;
    var allCatchUrl = base + 'catchment/geojson/?country=' + cfg.country + '&year=' + cfg.year + nutsSuffix;
    var nuts0Url = '/maps/api/nuts_region/geojson/?levl_code=0&cntr_code=' + cfg.country;
    var nutsLevel = cfg.nutsLevel || 1;
    var nutsRegionUrl = '/maps/api/nuts_region/geojson/?levl_code=' + nutsLevel + '&cntr_code=' + cfg.country;
    var dataUrl = cfg.dataUrl + '?country=' + cfg.country + '&year=' + cfg.year + nutsSuffix;
    var outlineUrl = cfg.outlineGeoJsonUrl
      ? cfg.outlineGeoJsonUrl + '?country=' + cfg.country + '&year=' + cfg.year + nutsSuffix
      : null;
    var requests = [
      _fetchJSON(catchUrl),
      _fetchJSON(dataUrl),
      _fetchJSON(nuts0Url),
      _fetchJSON(nutsRegionUrl),
      _fetchJSON(allCatchUrl)
    ];
    if (outlineUrl) requests.push(_fetchJSON(outlineUrl));

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
        allCatchments: results[4],
        acpvOutlines: outlineUrl ? results[5] : null,
      };
    });
  }

  function _configForSelection(cfg, country, year, preserveScope) {
    var loadCfg = Object.assign({}, cfg, { country: country, year: year });

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
    return String(item.label)
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
      .replace(/No Door to door bio collection/g, 'No D2D bio')
      .replace(/No door-to-door bio collection/g, 'No D2D bio')
      .replace(/No separate Biowaste collection/g, 'No separate bio')
      .replace(/No separate bio collection/g, 'No separate bio');
  }

  function _legendItems(cfg, exportMode) {
    var items = cfg.categories.map(function (item) {
      if (!exportMode) return item;
      return Object.assign({}, item, { label: _exportLegendLabel(item) });
    });
    if (cfg.noDataLabel) {
      items.push({
        label: exportMode && cfg.exportNoDataLabel ? cfg.exportNoDataLabel : cfg.noDataLabel,
        color: cfg.noDataColor || '#e0e0e0'
      });
    }
    if (cfg.overlayPatternField && cfg.overlayPatternLegendLabel) {
      items.push({
        label: exportMode && cfg.exportOverlayPatternLegendLabel
          ? cfg.exportOverlayPatternLegendLabel
          : cfg.overlayPatternLegendLabel,
        color: '#f8f9fa',
        pattern: true
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
    opts.height = opts.paddingY * 2 + opts.titleHeight + opts.titleGap
      + Math.max.apply(null, opts.columnHeights);
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
    var margin = 46;
    var titleBlock = 46;
    var gap = 46;
    var regionBorder = (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
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
        { placement: 'bottom', width: 0.88, columns: 3 }
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

  function _render(data, cfg, options) {
    options = options || {};
    // Build lookup: catchment_id -> thematic record
    var records = Array.isArray(data.thematicData) ? data.thematicData
      : (data.thematicData.results || []);
    if (typeof cfg.transformData === 'function') {
      records = cfg.transformData(records);
    }
    var lookup = {};
    records.forEach(function (r) { lookup[r.catchment_id] = r; });

    // Merge thematic data into catchment features
    if (data.catchments.features) {
      data.catchments.features.forEach(function (f) {
        var rec = lookup[f.properties.catchment_id];
        f.properties._thematic_value = rec ? rec[cfg.dataField] : null;
        f.properties._overlay_pattern = rec && cfg.overlayPatternField
          ? Boolean(rec[cfg.overlayPatternField])
          : false;
      });
    }

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
          return p.catchment_name + ' — ' + val;
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

    // Layer 4: Bundesländer borders (on top of catchments)
    if (data.bundeslaender && data.bundeslaender.features) {
      _svg.append('g').attr('class', 'layer-bundeslaender')
        .selectAll('path')
        .data(data.bundeslaender.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', BUNDESLAND_STROKE)
        .attr('stroke-width', BUNDESLAND_STROKE_WIDTH);
    }

    // Layer 5: outer border (very top) — filtered regions when nutsPrefix set, else full country
    var borderData = (cfg.nutsPrefix && data.bundeslaender && data.bundeslaender.features && data.bundeslaender.features.length)
      ? data.bundeslaender : data.countryBorder;
    if (borderData && borderData.features) {
      _svg.append('g').attr('class', 'layer-country-border')
        .selectAll('path')
        .data(borderData.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', COUNTRY_STROKE)
        .attr('stroke-width', COUNTRY_STROKE_WIDTH);
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
    if (cat.pattern) {
      g.append('rect')
        .attr('x', x).attr('y', swatchY)
        .attr('width', opts.swatchW).attr('height', opts.swatchH)
        .attr('fill', 'url(#' + _overlayPatternId(opts.cfg) + ')')
        .attr('stroke', 'none');
    }
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
    var hasOverlayLegend = cfg.overlayPatternField && cfg.overlayPatternLegendLabel;
    var legendRows = items.length + (hasOverlayLegend ? 1 : 0);

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

    items = cfg.categories.slice();
    legendRows = items.length + (hasOverlayLegend ? 1 : 0);
    if (cfg.noDataLabel) {
      items.push({ label: cfg.noDataLabel, color: cfg.noDataColor || '#e0e0e0' });
      legendRows += 1;
    }

    var g = _svg.append('g')
      .attr('class', 'atlas-legend')
      .attr('transform', 'translate(40,' + (height - 30 - legendRows * (swatchH + gap) - 20) + ')');

    var totalH = legendRows * (swatchH + gap) + gap + 20;
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

    if (hasOverlayLegend) {
      var overlayY = items.length * (swatchH + gap);
      g.append('rect')
        .attr('x', 0).attr('y', overlayY + 4)
        .attr('width', swatchW).attr('height', swatchH)
        .attr('fill', '#f8f9fa').attr('stroke', '#333');
      g.append('rect')
        .attr('x', 0).attr('y', overlayY + 4)
        .attr('width', swatchW).attr('height', swatchH)
        .attr('fill', 'url(#' + _overlayPatternId(cfg) + ')')
        .attr('stroke', 'none');
      g.append('text')
        .attr('x', swatchW + 8).attr('y', overlayY + 4 + swatchH - 3)
        .attr('font-size', 12)
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

  // ---- public API -----------------------------------------------------------

  function init(cfg) {
    _cfg = cfg;
    var loadingEl = document.getElementById(cfg.loadingId);
    var btnSVG = document.getElementById('btn-export-svg');
    var btnPNG = document.getElementById('btn-export-png');
    var btnLoad = document.getElementById('btn-load');
    var fileBase = cfg.fileBase || 'waste_atlas_map';

    function load(country, year, preserveScope) {
      _show(loadingEl);
      if (btnSVG) btnSVG.disabled = true;
      if (btnPNG) btnPNG.disabled = true;

      var loadCfg = _configForSelection(cfg, country, year, preserveScope);

      _fetchAll(loadCfg)
        .then(function (data) {
          _lastData = data;
          _lastLoadCfg = loadCfg;
          _render(data, loadCfg);
          _hide(loadingEl);
          if (btnSVG) btnSVG.disabled = false;
          if (btnPNG) btnPNG.disabled = false;
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

    if (btnLoad) {
      var countrySelect = document.getElementById('sel-country');
      function selectedRouteUrl() {
        var selectedOption = countrySelect.options[countrySelect.selectedIndex];
        return selectedOption ? selectedOption.getAttribute('data-url') : null;
      }
      function selectedYear() {
        return parseInt(document.getElementById('sel-year').value, 10) || 2022;
      }

      countrySelect.addEventListener('change', function () {
        var url = selectedRouteUrl();
        if (url && !_isCurrentPath(url)) {
          window.location.href = url + '?year=' + encodeURIComponent(selectedYear());
        }
      });

      btnLoad.addEventListener('click', function () {
        var country = countrySelect.value;
        var year = selectedYear();
        var url = selectedRouteUrl();
        if (url && !_isCurrentPath(url)) {
          window.location.href = url + '?year=' + encodeURIComponent(year);
          return;
        }
        load(country, year, false);
      });
    }

    if (btnSVG) btnSVG.addEventListener('click', function () { exportSVG(fileBase + '.svg'); });
    if (btnPNG) btnPNG.addEventListener('click', function () { exportPNG(fileBase + '.png'); });
  }

  return { init: init, exportSVG: exportSVG, exportPNG: exportPNG };
})();
