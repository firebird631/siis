function on_chart_data_serie(market_id, timestamp, value) {
    console.log(value);
}

function subscribe_chart(market_id, timeframe) {
    let key = market_id + ':' + timeframe;

    if (!window.charts.get(key) || !window.charts[key].subscribed) {
        let endpoint = "strategy/chart";
        let url = base_url() + '/' + endpoint;

        let data = {
            'command': 'subscribe-chart',
            'action': 'subscribe',
            'type': 'chart',
            'market-id': market_id,
            'timeframe': timeframe,
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

function unsubscribe_chart(market_id, timeframe) {
    let key = market_id + ':' + timeframe;

    if (window.charts.get(key) && window.charts[key].subscribed) {
        // unsubscribe
        let endpoint = "strategy/chart";
        let url = base_url() + '/' + endpoint;

        let data = {
            'command': 'unsubscribe-chart',
            'action': 'unsubscribe',
            'type': 'chart',
            'market-id': market_id,
            'timeframe': timeframe,
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
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Unsubscribe Chart', 'type': 'error'});
            }
        });
    }
}