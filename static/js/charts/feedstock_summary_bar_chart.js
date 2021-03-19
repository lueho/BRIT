// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily =
    'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

function number_format(number, decimals, dec_point, thousands_sep) {
    // *     example: number_format(1234.56, 2, ',', ' ');
    // *     return: '1 234,56'
    number = (number + '').replace(',', '').replace(' ', '');
    let n = !isFinite(+number) ? 0 : +number;
    let prec = !isFinite(+decimals) ? 0 : Math.abs(decimals);
    let sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep;
    let dec = (typeof dec_point === 'undefined') ? '.' : dec_point;
    let s;
    let toFixedFix = function (n, prec) {
        let k = Math.pow(10, prec);
        return '' + Math.round(n * k) / k;
    };
    // Fix for IE parseFloat(0.55).toFixed(0) = 0;
    s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
    if (s[0].length > 3) {
        s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
    }
    if ((s[1] || '').length < prec) {
        s[1] = s[1] || '';
        s[1] += new Array(prec - s[1].length + 1).join('0');
    }
    return s.join(dec);
}

function chartDefinition(type, labels, values, unit, show_legend) {

    console.log(values)

    switch (type) {
        case 'barchart':
            return barChartDefinition(labels, values, unit, show_legend);
        case 'stacked_barchart':
            return barChartDefinition(labels, values, unit, show_legend);
    }

}


function barChartDefinition(xlabels, data, unit, show_legend) {

    const bg_colors = [
        "#04555e",
        "#943329",
        "#63a33c",
        "#f49a33",
        "#826937",
        "#fcc767"
    ]

    for (let i = 0; i < data.length; i++) {
        data[i]['backgroundColor'] = bg_colors[i]
        data[i]['backgroundColor'] = bg_colors[i]
        // data[i]['hoverBackgroundColor'] = TODO
        // data[i]['borderColor'] = TODO
    }

    return {
        type: 'bar',
        data: {
            labels: xlabels,
            datasets: data,
        },
        options: {
            layout: {
                padding: {
                    left: 10,
                    right: 25,
                    top: 25,
                    bottom: 0
                }
            },
            legend: {
                display: show_legend
            },
            maintainAspectRatio: false,
            scales: {
                yAxes: [{
                    gridLines: {
                        color: "rgb(234, 236, 244)",
                        zeroLineColor: "rgb(234, 236, 244)",
                        drawBorder: true,
                        borderDash: [2],
                        zeroLineBorderDash: [2]
                    },
                    scaleLabel: {
                        display: true,
                        labelString: unit
                    },
                    stacked: true,
                    ticks: {
                        beginAtZero: true,
                        padding: 10
                    }
                }],
                xAxes: [{
                    gridLines: {
                        display: false,
                        drawBorder: true
                    },
                    maxBarThickness: 100,
                    stacked: true,
                    ticks: {
                        beginAtZero: true,
                        maxTicksLimit: 12
                    }
                }]

            },
            tooltips: {
                titleMarginBottom: 10,
                titleFontColor: '#6e707e',
                titleFontSize: 14,
                backgroundColor: "rgb(255,255,255)",
                bodyFontColor: "#858796",
                borderColor: '#dddfeb',
                borderWidth: 1,
                xPadding: 15,
                yPadding: 15,
                displayColors: false,
                caretPadding: 10,
                callbacks: {
                    label: function (tooltipItem, chart) {
                        const datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
                        return datasetLabel + ': ' + number_format(tooltipItem.yLabel) + ' ' + unit;
                    }
                }
            },
        }
    }
}
