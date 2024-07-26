/**
 * @date 2020-01-24
 * @author Frederic Scherma, All rights reserved without prejudices.
 * @license Copyright (c) 2020 Dream Overflow
 * Web trader charting module.
 */

function on_chart_data_serie(market_id, timestamp, value) {
    console.log(value);
}

function subscribe_chart(market_id, analyser_name) {
    let key = market_id + ':' + analyser_name;

    if (!(key in window.charts) || !window.charts[key].subscribed) {
        let endpoint = "strategy/chart";
        let url = base_url() + '/' + endpoint;

        let data = {
            'command': 'subscribe-chart',
            'action': 'subscribe',
            'type': 'chart',
            'market-id': market_id,
            'analyser': analyser_name,
        };

        $.ajax({
            type: "POST",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
                'TWISTED_SESSION': server.session,
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            if (data.error) {
                for (let msg in data.messages) {
                    notify({'message': data.messages[msg], 'title': 'Subscribe Chart', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Subscribe Chart', 'type': 'success'});

                window.charts[key]= {
                    'subscribed': true,
                    'serie': []
                };
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Subscribe Chart', 'type': 'error'});
            }
        });
    }
}

function unsubscribe_chart(market_id, analyser_name) {
    let key = market_id + ':' + analyser_name;

    if (window.charts.get(key) && window.charts[key].subscribed) {
        // unsubscribe
        let endpoint = "strategy/chart";
        let url = base_url() + '/' + endpoint;

        let data = {
            'command': 'unsubscribe-chart',
            'action': 'unsubscribe',
            'type': 'chart',
            'market-id': market_id,
            'analyser': analyser_name,
        };

        $.ajax({
            type: "POST",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
                'TWISTED_SESSION': server.session,
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            if (data.error) {
                for (let msg in data.messages) {
                    notify({'message': data.messages[msg], 'title': 'Unsubscribe Chart', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Unsubscribe Chart', 'type': 'success'});
                delete(window.charts[key]);
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Unsubscribe Chart', 'type': 'error'});
            }
        });
    }
}

function setup_charting(elt, market_id, analyser_name) {
    if (window.charts.mode) {
        // remove current and replace
        remove_charting();
    }

    subscribe_chart(market_id, analyser_name);

    let canvas = $('<canvas id="chart1" class="chart"></canvas>');
    $(elt).children('div.chart').append(canvas);

    let label = market_id; // @todo
    let timeframeUnit = "minute";

    create_chart(canvas, label, timeframeUnit);
}

function remove_charting() {
    // remove charting configuration
    if (!window.charts) {
        return;
    }

    let subs = [];

    for (let key in window.charts) {
        let v = window.charts[key];
        const [market_id, analyser_name] = key.split(':');
        subs.push([market_id, analyser_name]);
    }

    for (let i = 0; i < subs.length; ++i) {
        unsubscribe_chart(subs[i][0], subs[i][1]);
    }

    $("canvas.chart").remove();
}

function create_chart(canvas, label, timeframeUnit) {
    let candleData = [];

    let ctx = canvas[0].getContext('2d');
    let chart = new Chart(ctx, {
      type: 'candlestick',
      data: {
        datasets: [{
          label: label,
          data: candleData,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'time',
            time: {
              parser: 'luxon',
              tooltipFormat: 'yyyy-MM-dd HH:mm:ss',
              unit: timeframeUnit,
              displayFormats: {
                second: 'HH:mm:ss',
              },
              adapter: {
                date: luxon.DateTime,
                formats: {
                  datetime: 'yyyy-MM-dd HH:mm:ss',
                },
              },
            },
          },
        },
        plugins: {
          annotation: {
            annotations: []
          },
          legend: {
              display: false
          },
          zoom: {
            pan: {
              rangeMin: {
                  x: null,
                  y: null,
              },
              rangeMax: {
                  x: null,
                  y: null,
              },
              enabled: true,
              mode: 'xy',
            },
            zoom: {
              wheel: {
                enabled: true,
              },
              pinch: {
                enabled: true
              },
              mode: 'xy',
           },
        }
      },
      },
    });
}