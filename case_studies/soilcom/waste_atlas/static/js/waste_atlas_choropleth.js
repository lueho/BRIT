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

  var _cfg = {};
  var _svg;

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

  // ---- data fetching --------------------------------------------------------

  function _fetchAll(cfg) {
    var base = '/waste_collection/api/waste-atlas/';
    var catchUrl = base + 'catchment/geojson/?country=' + cfg.country + '&year=' + cfg.year;
    var allCatchUrl = base + 'catchment/geojson/?country=' + cfg.country + '&year=2022';
    var nuts0Url = '/maps/api/nuts_region/geojson/?levl_code=0&cntr_code=' + cfg.country;
    var nuts1Url = '/maps/api/nuts_region/geojson/?levl_code=1&cntr_code=' + cfg.country;
    var dataUrl = cfg.dataUrl + '?country=' + cfg.country + '&year=' + cfg.year;

    return Promise.all([
      _fetchJSON(catchUrl),
      _fetchJSON(dataUrl),
      _fetchJSON(nuts0Url),
      _fetchJSON(nuts1Url),
      _fetchJSON(allCatchUrl),
    ]).then(function (results) {
      return {
        catchments: results[0],
        thematicData: results[1],
        countryBorder: results[2],
        bundeslaender: results[3],
        allCatchments: results[4],
      };
    });
  }

  // ---- rendering ------------------------------------------------------------

  function _render(data, cfg) {
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
      });
    }

    // SVG dimensions
    var container = document.getElementById(cfg.containerId);
    var width = container.clientWidth || 900;
    var height = Math.round(width * 1.17);

    _svg = d3.select('#' + cfg.svgId)
      .attr('xmlns', 'http://www.w3.org/2000/svg')
      .attr('width', width)
      .attr('height', height)
      .style('background', '#fff');

    _svg.selectAll('*').remove();

    // Projection — fit to country border so the extent is identical across years
    var fitData = (data.countryBorder && data.countryBorder.features && data.countryBorder.features.length)
      ? data.countryBorder : data.catchments;
    var projection = d3.geoMercator()
      .fitExtent([[40, 60], [width - 40, height - 100]], fitData);
    var path = d3.geoPath().projection(projection);

    // Layer 1: country background fill (no stroke — border drawn on top)
    if (data.countryBorder && data.countryBorder.features) {
      _svg.append('g').attr('class', 'layer-country-fill')
        .selectAll('path')
        .data(data.countryBorder.features)
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

    // Layer 5: country border (very top)
    if (data.countryBorder && data.countryBorder.features) {
      _svg.append('g').attr('class', 'layer-country-border')
        .selectAll('path')
        .data(data.countryBorder.features)
        .enter().append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', COUNTRY_STROKE)
        .attr('stroke-width', COUNTRY_STROKE_WIDTH);
    }

    // Title
    _svg.append('text')
      .attr('x', width / 2).attr('y', 30)
      .attr('text-anchor', 'middle')
      .attr('font-family', "'Nunito', sans-serif")
      .attr('font-size', 18).attr('font-weight', 'bold')
      .text(cfg.title);

    // Subtitle / count
    var count = data.catchments.features ? data.catchments.features.length : 0;
    var subtitle = cfg.subtitle || (count + ' catchments');
    _svg.append('text')
      .attr('x', width / 2).attr('y', 50)
      .attr('text-anchor', 'middle')
      .attr('font-family', "'Nunito', sans-serif")
      .attr('font-size', 13).attr('fill', '#666')
      .text(subtitle);

    // Legend
    _drawLegend(width, height, cfg);
  }

  function _drawLegend(width, height, cfg) {
    var swatchW = 22, swatchH = 16, gap = 6;
    var items = cfg.categories.slice();
    if (cfg.noDataLabel) {
      items.push({ label: cfg.noDataLabel, color: cfg.noDataColor || '#e0e0e0' });
    }

    var g = _svg.append('g')
      .attr('class', 'atlas-legend')
      .attr('transform', 'translate(40,' + (height - 30 - items.length * (swatchH + gap) - 20) + ')');

    var totalH = items.length * (swatchH + gap) + gap + 20;
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
  }

  // ---- export ---------------------------------------------------------------

  function _svgSource() {
    var svgEl = document.getElementById(_cfg.svgId);
    var serializer = new XMLSerializer();
    var source = serializer.serializeToString(svgEl);
    if (!source.match(/^<svg[^>]+xmlns/)) {
      source = source.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    return '<?xml version="1.0" standalone="no"?>\r\n' + source;
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
    var source = _svgSource();
    var blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    _downloadBlob(blob, filename || 'waste_atlas_map.svg');
  }

  function exportPNG(filename) {
    var svgEl = document.getElementById(_cfg.svgId);
    var w = parseInt(svgEl.getAttribute('width'), 10);
    var h = parseInt(svgEl.getAttribute('height'), 10);
    var scale = EXPORT_DPI / 96;
    var canvas = document.createElement('canvas');
    canvas.width = w * scale;
    canvas.height = h * scale;
    var ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);

    var img = new Image();
    var source = _svgSource();
    var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(source);
    img.onload = function () {
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob(function (blob) {
        _downloadBlob(blob, filename || 'waste_atlas_map.png');
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

    function load(country, year) {
      _show(loadingEl);
      if (btnSVG) btnSVG.disabled = true;
      if (btnPNG) btnPNG.disabled = true;

      var loadCfg = Object.assign({}, cfg, { country: country, year: year });

      _fetchAll(loadCfg)
        .then(function (data) {
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

    load(cfg.country, cfg.year);

    if (btnLoad) {
      btnLoad.addEventListener('click', function () {
        var country = document.getElementById('sel-country').value;
        var year = parseInt(document.getElementById('sel-year').value, 10) || 2022;
        load(country, year);
      });
    }

    if (btnSVG) btnSVG.addEventListener('click', function () { exportSVG(fileBase + '.svg'); });
    if (btnPNG) btnPNG.addEventListener('click', function () { exportPNG(fileBase + '.png'); });
  }

  return { init: init, exportSVG: exportSVG, exportPNG: exportPNG };
})();
