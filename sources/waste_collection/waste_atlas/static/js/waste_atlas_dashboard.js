/**
 * Waste Atlas — statistics dashboard (D3.js).
 *
 * Renders one interactive chart per map page of a region. Every chart is driven
 * by the chart config the server derived from the map's stored configuration,
 * so a chart classifies, labels and colours values exactly like its map:
 *
 *   WasteAtlasDashboard.init({
 *     country: 'DE', nutsPrefix: '', nutsLevel: '1',
 *     year: 2024, years: [2020, ..., 2024], wasteCategory: '',
 *     panels: [{
 *       theme: 'collection_system',
 *       chartId: 'dashboard-chart-collection_system',
 *       title: 'Biowaste collection systems',
 *       mapUrl: '/waste_collection/map/germany/collection-system/',
 *       dataUrl: '/waste_collection/api/waste-atlas/collection-system/',
 *       dataField: 'collection_system',
 *       transformName: 'residualCollectionAmount',   // optional
 *       categories: [{ value, label, color }, ...]
 *     }, ...]
 *   });
 *
 * Each chart offers a "Shares" view (how many catchments fall into each class
 * of the map's legend) and a "Trend" view (how those shares developed over the
 * selectable years). Clicking a class opens the map behind the chart.
 */

/* global d3, WasteAtlasChoropleth */

var WasteAtlasDashboard = (function () {
  'use strict';

  var NO_DATA_LABEL = 'No data';
  var NO_DATA_COLOR = '#e5e7eb';
  var TREND_HEIGHT = 200;
  var BAR_HEIGHT = 22;
  var BAR_GAP = 6;
  var MARGIN = { top: 8, right: 44, bottom: 24, left: 132 };

  /**
   * Build the API URL for one panel, scoped to the dashboard region and a year.
   */
  function chartDataUrl(panel, scope, year) {
    var params = ['country=' + encodeURIComponent(scope.country), 'year=' + year];
    if (scope.nutsPrefix) {
      params.push('nuts_prefix=' + encodeURIComponent(scope.nutsPrefix));
    }
    var separator = panel.dataUrl.indexOf('?') === -1 ? '?' : '&';
    return panel.dataUrl + separator + params.join('&');
  }

  /** Apply the map's client-side classification transform, when it has one. */
  function classify(panel, records) {
    var transforms =
      typeof WasteAtlasChoropleth !== 'undefined'
        ? WasteAtlasChoropleth.transforms
        : null;
    if (panel.transformName && transforms && transforms[panel.transformName]) {
      return transforms[panel.transformName](records);
    }
    return records;
  }

  /**
   * Count how many records fall into each legend class of a panel.
   *
   * Returns the classes in legend order plus a trailing no-data class, each
   * with its absolute count and its share of all records.
   */
  function summarise(panel, records) {
    var classified = classify(panel, records || []);
    var counts = {};
    classified.forEach(function (record) {
      var value = record[panel.dataField];
      if (value === null || value === undefined || value === '') return;
      counts[value] = (counts[value] || 0) + 1;
    });
    var total = classified.length;
    var bars = (panel.categories || []).map(function (category) {
      return {
        value: category.value,
        label: category.label || category.value,
        color: category.color,
        count: counts[category.value] || 0
      };
    });
    var known = bars.reduce(function (sum, bar) {
      return sum + bar.count;
    }, 0);
    // Records without a value, and values outside the legend, are reported as
    // no data so that no record silently disappears from the chart.
    var noData = total - known;
    if (noData > 0) {
      bars.push({
        value: null,
        label: panel.noDataLabel || NO_DATA_LABEL,
        color: panel.noDataColor || NO_DATA_COLOR,
        count: noData
      });
    }
    bars.forEach(function (bar) {
      bar.share = total ? bar.count / total : 0;
    });
    return { total: total, withData: total - noData, noData: noData, bars: bars };
  }

  /** Turn per-year record lists into one row per year with class shares. */
  function trendRows(panel, recordsByYear) {
    return Object.keys(recordsByYear)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      })
      .map(function (year) {
        var summary = summarise(panel, recordsByYear[year]);
        return { year: year, total: summary.total, bars: summary.bars };
      });
  }

  /** Aggregate the loaded panel summaries into the dashboard headline figures. */
  function kpisFrom(summaries) {
    var withData = summaries.filter(function (summary) {
      return summary && summary.withData > 0;
    });
    return {
      charts: withData.length,
      chartsTotal: summaries.length,
      catchments: summaries.reduce(function (max, summary) {
        return summary && summary.total > max ? summary.total : max;
      }, 0),
      values: withData.reduce(function (sum, summary) {
        return sum + summary.withData;
      }, 0)
    };
  }

  function _fetchJSON(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (response) {
      if (!response.ok) {
        throw new Error(response.status + ' ' + response.statusText + ' — ' + url);
      }
      return response.json();
    });
  }

  function _formatShare(share) {
    return (share * 100).toFixed(share < 0.1 ? 1 : 0) + '%';
  }

  function _tooltip() {
    return d3.select('#dashboard-tooltip');
  }

  function _showTooltip(event, html) {
    _tooltip()
      .attr('hidden', null)
      .html(html)
      .style('left', event.pageX + 12 + 'px')
      .style('top', event.pageY + 12 + 'px');
  }

  function _hideTooltip() {
    _tooltip().attr('hidden', 'hidden');
  }

  function _clear(container) {
    container.selectAll('*').remove();
  }

  function _status(container, message) {
    _clear(container);
    container.append('p').attr('class', 'dashboard-chart-status').text(message);
  }

  function _width(node) {
    return Math.max(240, node.clientWidth || 320);
  }

  function _mapHref(panel, state) {
    return panel.mapUrl + '?year=' + state.year;
  }

  /** Draw the "Shares" view: one horizontal bar per legend class. */
  function renderShares(container, panel, summary, state) {
    _clear(container);
    if (!summary.total) {
      _status(container, 'No data for ' + state.year + '.');
      return;
    }
    var bars = summary.bars;
    var height = MARGIN.top + MARGIN.bottom + bars.length * (BAR_HEIGHT + BAR_GAP);
    var width = _width(container.node());
    var innerWidth = width - MARGIN.left - MARGIN.right;
    var x = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(bars, function (bar) {
          return bar.count;
        }) || 1
      ])
      .range([0, innerWidth]);
    var y = d3
      .scaleBand()
      .domain(
        bars.map(function (bar) {
          return bar.label;
        })
      )
      .range([0, bars.length * (BAR_HEIGHT + BAR_GAP)])
      .padding(0.2);

    var svg = container
      .append('svg')
      .attr('class', 'dashboard-chart-svg')
      .attr('viewBox', '0 0 ' + width + ' ' + height)
      .attr('role', 'img')
      .attr('aria-label', panel.title + ' — catchments per class');
    var plot = svg
      .append('g')
      .attr('transform', 'translate(' + MARGIN.left + ',' + MARGIN.top + ')');

    plot
      .append('g')
      .attr('class', 'dashboard-axis dashboard-axis--y')
      .call(d3.axisLeft(y).tickSize(0));
    plot
      .append('g')
      .attr('class', 'dashboard-axis dashboard-axis--x')
      .attr('transform', 'translate(0,' + bars.length * (BAR_HEIGHT + BAR_GAP) + ')')
      .call(d3.axisBottom(x).ticks(4).tickSizeOuter(0));

    plot
      .selectAll('rect.dashboard-bar')
      .data(bars)
      .enter()
      .append('rect')
      .attr('class', 'dashboard-bar')
      .attr('x', 0)
      .attr('y', function (bar) {
        return y(bar.label);
      })
      .attr('height', y.bandwidth())
      .attr('width', function (bar) {
        return x(bar.count);
      })
      .attr('fill', function (bar) {
        return bar.color;
      })
      .attr('tabindex', 0)
      .attr('role', 'link')
      .attr('aria-label', function (bar) {
        return bar.label + ': ' + bar.count + ' catchments — open map';
      })
      .on('mousemove', function (event, bar) {
        _showTooltip(
          event,
          '<strong>' +
            bar.label +
            '</strong><br>' +
            bar.count +
            ' of ' +
            summary.total +
            ' catchments (' +
            _formatShare(bar.share) +
            ')'
        );
      })
      .on('mouseleave', _hideTooltip)
      .on('click', function () {
        window.location.href = _mapHref(panel, state);
      })
      .on('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          window.location.href = _mapHref(panel, state);
        }
      });

    plot
      .selectAll('text.dashboard-bar-value')
      .data(bars)
      .enter()
      .append('text')
      .attr('class', 'dashboard-bar-value')
      .attr('x', function (bar) {
        return x(bar.count) + 6;
      })
      .attr('y', function (bar) {
        return y(bar.label) + y.bandwidth() / 2;
      })
      .attr('dy', '0.35em')
      .text(function (bar) {
        return bar.count;
      });
  }

  /** Draw the "Trend" view: one line per legend class over the atlas years. */
  function renderTrend(container, panel, rows) {
    _clear(container);
    var labels = (panel.categories || []).map(function (category) {
      return category.label || category.value;
    });
    var series = labels
      .map(function (label) {
        var color = null;
        var points = rows.map(function (row) {
          var bar =
            row.bars.filter(function (candidate) {
              return candidate.label === label;
            })[0] || {};
          color = bar.color || color;
          return { year: row.year, share: bar.share || 0 };
        });
        return { label: label, color: color || NO_DATA_COLOR, points: points };
      })
      .filter(function (line) {
        return line.points.some(function (point) {
          return point.share > 0;
        });
      });
    if (!series.length) {
      _status(container, 'No data for the selectable years.');
      return;
    }

    var width = _width(container.node());
    var height = TREND_HEIGHT;
    var margin = { top: 10, right: 16, bottom: 26, left: 44 };
    var innerWidth = width - margin.left - margin.right;
    var innerHeight = height - margin.top - margin.bottom;
    var x = d3
      .scalePoint()
      .domain(
        rows.map(function (row) {
          return String(row.year);
        })
      )
      .range([0, innerWidth]);
    var y = d3.scaleLinear().domain([0, 1]).range([innerHeight, 0]);
    var line = d3
      .line()
      .x(function (point) {
        return x(String(point.year));
      })
      .y(function (point) {
        return y(point.share);
      });

    var svg = container
      .append('svg')
      .attr('class', 'dashboard-chart-svg')
      .attr('viewBox', '0 0 ' + width + ' ' + height)
      .attr('role', 'img')
      .attr('aria-label', panel.title + ' — share per class and year');
    var plot = svg
      .append('g')
      .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
    plot
      .append('g')
      .attr('class', 'dashboard-axis dashboard-axis--x')
      .attr('transform', 'translate(0,' + innerHeight + ')')
      .call(d3.axisBottom(x).tickSizeOuter(0));
    plot
      .append('g')
      .attr('class', 'dashboard-axis dashboard-axis--y')
      .call(
        d3
          .axisLeft(y)
          .ticks(4)
          .tickFormat(function (value) {
            return value * 100 + '%';
          })
      );

    plot
      .selectAll('path.dashboard-line')
      .data(series)
      .enter()
      .append('path')
      .attr('class', 'dashboard-line')
      .attr('fill', 'none')
      .attr('stroke-width', 2)
      .attr('stroke', function (item) {
        return item.color;
      })
      .attr('d', function (item) {
        return line(item.points);
      });

    series.forEach(function (item) {
      plot
        .selectAll('circle.dashboard-point-' + labels.indexOf(item.label))
        .data(item.points)
        .enter()
        .append('circle')
        .attr('class', 'dashboard-point')
        .attr('r', 3.5)
        .attr('fill', item.color)
        .attr('cx', function (point) {
          return x(String(point.year));
        })
        .attr('cy', function (point) {
          return y(point.share);
        })
        .on('mousemove', function (event, point) {
          _showTooltip(
            event,
            '<strong>' +
              item.label +
              '</strong><br>' +
              point.year +
              ': ' +
              _formatShare(point.share)
          );
        })
        .on('mouseleave', _hideTooltip);
    });
  }

  function _card(panel) {
    return document.querySelector('.dashboard-card[data-theme="' + panel.theme + '"]');
  }

  function _applyCategoryFilter(panels, category) {
    panels.forEach(function (panel) {
      var card = _card(panel);
      if (!card) return;
      card.hidden = Boolean(category) && panel.wasteCategory !== category;
    });
    document.querySelectorAll('.dashboard-section').forEach(function (section) {
      var visible = section.querySelectorAll('.dashboard-card:not([hidden])');
      section.hidden = visible.length === 0;
    });
  }

  function _renderKpis(kpis) {
    var catchments = document.getElementById('dashboard-kpi-catchments');
    var charts = document.getElementById('dashboard-kpi-charts');
    var values = document.getElementById('dashboard-kpi-values');
    if (catchments) catchments.textContent = String(kpis.catchments);
    if (charts) charts.textContent = kpis.charts + ' / ' + kpis.chartsTotal;
    if (values) values.textContent = String(kpis.values);
  }

  function init(cfg) {
    var state = {
      country: cfg.country,
      nutsPrefix: cfg.nutsPrefix,
      nutsLevel: cfg.nutsLevel,
      year: cfg.year
    };
    var summaries = [];
    var recordCache = {};

    function load(panel, year) {
      var key = panel.theme + ':' + year;
      if (!recordCache[key]) {
        recordCache[key] = _fetchJSON(chartDataUrl(panel, state, year));
      }
      return recordCache[key];
    }

    function showShares(panel) {
      var container = d3.select('#' + panel.chartId);
      _status(container, 'Loading…');
      return load(panel, state.year)
        .then(function (records) {
          var summary = summarise(panel, records);
          renderShares(container, panel, summary, state);
          return summary;
        })
        .catch(function (error) {
          _status(container, 'Could not load this chart.');
          if (window.console) window.console.error(error);
          return null;
        });
    }

    function showTrend(panel) {
      var container = d3.select('#' + panel.chartId);
      _status(container, 'Loading trend…');
      return Promise.all(
        cfg.years.map(function (year) {
          return load(panel, year).then(function (records) {
            return { year: year, records: records };
          });
        })
      )
        .then(function (loaded) {
          var recordsByYear = {};
          loaded.forEach(function (entry) {
            recordsByYear[entry.year] = entry.records;
          });
          renderTrend(container, panel, trendRows(panel, recordsByYear));
        })
        .catch(function (error) {
          _status(container, 'Could not load this trend.');
          if (window.console) window.console.error(error);
        });
    }

    document.querySelectorAll('.dashboard-mode').forEach(function (button) {
      button.addEventListener('click', function () {
        var panel = cfg.panels.filter(function (candidate) {
          return candidate.theme === button.dataset.theme;
        })[0];
        if (!panel) return;
        var card = _card(panel);
        card.querySelectorAll('.dashboard-mode').forEach(function (sibling) {
          sibling.classList.toggle(
            'dashboard-mode--active',
            sibling === button
          );
        });
        if (button.dataset.mode === 'trend') showTrend(panel);
        else showShares(panel);
      });
    });

    var filters = document.getElementById('dashboard-filters');
    if (filters) {
      ['dashboard-region', 'dashboard-year'].forEach(function (id) {
        var select = document.getElementById(id);
        if (select) {
          select.addEventListener('change', function () {
            filters.submit();
          });
        }
      });
      var category = document.getElementById('dashboard-category');
      if (category) {
        category.addEventListener('change', function () {
          _applyCategoryFilter(cfg.panels, category.value);
        });
      }
    }
    _applyCategoryFilter(cfg.panels, cfg.wasteCategory || '');

    Promise.all(cfg.panels.map(showShares)).then(function (loaded) {
      summaries = loaded;
      _renderKpis(kpisFrom(summaries));
    });

    window.addEventListener(
      'resize',
      (function () {
        var timer = null;
        return function () {
          if (timer) window.clearTimeout(timer);
          timer = window.setTimeout(function () {
            cfg.panels.forEach(function (panel, index) {
              var card = _card(panel);
              var active = card && card.querySelector('.dashboard-mode--active');
              if (active && active.dataset.mode === 'trend') return;
              if (summaries[index]) {
                renderShares(
                  d3.select('#' + panel.chartId),
                  panel,
                  summaries[index],
                  state
                );
              }
            });
          }, 150);
        };
      })()
    );
  }

  return {
    init: init,
    // Pure helpers, exposed for unit tests.
    chartDataUrl: chartDataUrl,
    summarise: summarise,
    trendRows: trendRows,
    kpisFrom: kpisFrom
  };
})();
