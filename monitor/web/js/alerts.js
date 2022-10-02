/**
 * @date 2020-01-24
 * @author Frederic Scherma, All rights reserved without prejudices.
 * @license Copyright (c) 2020 Dream Overflow
 * Web trader alerts handler.
 */

// @todo add price cross alert dialog

function on_strategy_signal_alert(market_id, alert_id, timestamp, alert, do_notify=true) {
    let alert_elt = $('<tr class="alert"></tr>');
    let key = market_id + ':' + alert.id;
    alert_elt.attr('alert-key', key);

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    let lalert_id = $('<span class="alert-id"></span>').text(alert.id);
    let alert_symbol = $('<span class="alert-symbol badge badge-info"></span>').text(symbol).attr('title', market_id);
    let alert_direction = $('<span class="alert-direction fa"></span>')
        .addClass(alert.trigger > 0 ? 'trade-long' : 'trade-short')
        .addClass(alert.trigger > 0 ? 'fa-arrow-up' : 'fa-arrow-down');

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    // in seconds timestamp
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.timestamp));

    // timeframe is formatted
    let timeframe = alert.timeframe == 't' ? "trade/tick" : alert.timeframe;

    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(timeframe);
    let alert_lastprice = $('<span class="alert-last-price"></span>').text(alert['last-price']);
    let alert_reason = $('<span class="alert-reason"></span>').text(alert.reason);

    let alert_message = $('<span class="alert-message"></span>').text(alert.message);
    let alert_details = $('<button class="alert-details btn btn-info fas fa-info"></button>');

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_direction));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_lastprice));
    alert_elt.append($('<td></td>').append(alert_reason));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_message));
    alert_elt.append($('<td></td>').append(alert_datetime));

    alert_elt.append($('<td></td>').append(alert_details));

    // actions
    alert_details.on('click', on_details_signal_alert);

    // append
    $('div.alert-list-entries tbody').prepend(alert_elt);

    if (do_notify) {
        let message = alert.name + " "  + alert.reason + " " + alert.symbol + " " + alert.message;
        notify({'message': message, 'title': 'Strategy Alert', 'type': 'info'});
        audio_notify('alert');
    }

    window.alerts[key] = alert;

    // cleanup above 200 alerts
    if (Object.keys(window.alerts).length > 200) {
        for (alert_key in window.alerts) {
            // @todo remove and update view
        }
    }
}

function price_src_to_str(price_src) {
    switch (price_src) {
        case 0:
            return "bid";
        case 1:
            return "ask";
        case 2:
            return "mid";
        default:
            return "";
    }
}

function on_strategy_create_alert(market_id, alert_id, timestamp, alert, do_notify=true) {
    let key = market_id + ':' + alert_id;

    let alert_elt = $('<tr class="active-alert"></tr>');
    alert_elt.attr('active-alert-key', key);

    let condition_msg = "-";
    let cancellation_msg = "never";

    let price_src = price_src_to_str(alert['price-src']);

    if (alert.name == "price-cross") {
        if (alert.direction > 0) {
            condition_msg = `if ${price_src} price goes above ${format_price(market_id, alert.price)}`;
        } else if (alert.direction < 0) {
            condition_msg = `if ${price_src} price goes below ${format_price(market_id, alert.price)}`;
        }
    }

    if (alert.cancellation > 0) {
        if (alert.direction > 0) {
            cancellation_msg = `if ${price_src} price < ${format_price(market_id, alert.cancellation)}`;
        } else if (alert.direction < 0) {
            cancellation_msg = `if ${price_src} price > ${format_price(market_id, alert.cancellation)}`;
        }
    }

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    let lalert_id = $('<span class="alert-id"></span>').text(alert.id);
    let alert_symbol = $('<span class="alert-symbol badge badge-info"></span>').text(symbol).attr('title', market_id);

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.created));

    // timeframe is not formatted
    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(alert.timeframe || "trade/tick");
    let alert_expiry = $('<span class="alert-expiry"></span>');
    if (alert.expiry > 0) {
        // absolute timestamp
        alert_expiry.text(timestamp_to_datetime_str(alert.expiry));
    } else {
        alert_expiry.text("never");
    }

    let alert_condition = $('<span class="alert-condition"></span>').text(condition_msg);
    let alert_countdown = $('<span class="alert-countdown"></span>').text(alert.countdown);
    let alert_cancellation = $('<span class="alert-cancellation"></span>').text(cancellation_msg);
    let alert_message = $('<span class="alert-message"></span>').text(alert.message);

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_expiry));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_countdown));
    alert_elt.append($('<td></td>').append(alert_condition));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_cancellation));
    alert_elt.append($('<td></td>').append(alert_message));

    // actions
    let alert_remove = $('<button class="alert-remove btn btn-danger fas fa-window-close"></button>');

    if (server.permissions.indexOf("strategy-trader") < 0) {
        alert_remove.attr("disabled", "")
    }

    alert_elt.append($('<td></td>').append(alert_remove));

    let alert_details = $('<button class="alert-details btn btn-info fas fa-info"></button>');
    alert_elt.append($('<td></td>').append(alert_details));

    alert_details.on('click', on_details_alert);

    // append
    $('div.active-alert-list-entries tbody').prepend(alert_elt);

    // actions
    if (server.permissions.indexOf("strategy-trader") != -1) {
        alert_remove.on('click', on_remove_alert);
    }

    if (do_notify) {
        let message = alert.name + " "  + condition_msg + " " + alert.symbol + " " + alert.message;
        notify({'message': message, 'title': 'Strategy Alert Created', 'type': 'info'});
    }

    window.active_alerts[key] = alert;
}

function on_remove_alert(elt) {
    let key = retrieve_alert_key(elt);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let alert_id = parseInt(parts[1]);

    let endpoint = "strategy/alert";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];

    if (market_id && market && alert_id) {
        let data = {
            'market-id': market['market-id'],
            'alert-id': alert_id,
            'action': "del-alert"
        };

        $.ajax({
            type: "DELETE",
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
                    notify({'message': data.messages[msg], 'title': 'Remove Alert', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Remove Alert', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Remove Alert', 'type': 'error'});
            }
        });
    }
}

function on_strategy_remove_alert(market_id, timestamp, alert_id) {
    let key = market_id + ':' + alert_id;
    let container = $('div.active-alert-list-entries tbody');

    container.find('tr.active-alert[active-alert-key="' + key + '"]').remove();
    if (key in window.active_alerts) {
        delete window.active_alerts[key];
    }
}

window.fetch_alerts = function() {
    // fetch actives alerts
    let endpoint1 = "strategy/alert";
    let url1 = base_url() + '/' + endpoint1;

    let params1 = {}

    $.ajax({
        type: "GET",
        url: url1,
        data: params1,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.active_alerts = {};

        let alerts = result['data'];
        if (!alerts) {
            return;
        }

        // naturally ordered
        for (let i = 0; i < alerts.length; ++i) {
            let alert = alerts[i];

            window.active_alerts[alert['market-id'] + ':' + alert.id] = alert;

            // initial add
            on_strategy_create_alert(alert['market-id'], alert.id, alert.timestamp, alert, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains actives alerts !", 'title': 'fetching"', 'type': 'error'});
    });

    // fetch last history of alerts
    let endpoint2 = "strategy/historical-alert";
    let url2 = base_url() + '/' + endpoint2;

    let params2 = {}

    $.ajax({
        type: "GET",
        url: url2,
        data: params2,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.alerts = {};

        let alerts = result['data'];
        if (!alerts) {
            return;
        }

        // naturally ordered
        for (let i = 0; i < alerts.length; ++i) {
            let alert = alerts[i];

            window.alerts[alert['market-id'] + ':' + alert.id] = alert;

            // initial add
            on_strategy_signal_alert(alert['market-id'], alert.id, alert.timestamp, alert, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains historical alerts !", 'title': 'fetching"', 'type': 'error'});
    });
};

function on_add_price_cross_alert(elt) {
    alert("TODO");
}

function on_details_signal_alert(elt) {
    alert("TODO");
}

function on_details_alert(elt) {
    alert("TODO");
}
