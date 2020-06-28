// @todo add price cross alert with popup alert on browser, popup sound alert (differents sounds)
// @todo remove alert

function on_strategy_alert(market_id, alert_id, timestamp, alert) {
    let alert_elt = $('<tr class="alert"></tr>');
    let key = market_id + ':' + alert.id;
    alert_elt.attr('alert-key', key);

    let lalert_id = $('<span class="alert-id"></span>').text(alert.id);
    let alert_symbol = $('<span class="alert-symbol"></span>').text(market_id);
    let alert_direction = $('<span class="alert-direction fa"></span>')
        .addClass(alert.trigger > 0 ? 'trade-long' : 'trade-short')
        .addClass(alert.trigger > 0 ? 'fa-arrow-up' : 'fa-arrow-down');

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.timestamp*1000));

    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(alert.timeframe || "trade");
    let alert_lastprice = $('<span class="alert-last-price"></span>').text(alert['last-price']);
    let alert_reason = $('<span class="alert-reason"></span>').text(alert.reason);

    let alert_message = $('<span class="alert-message"></span>').text(alert.message);

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_direction));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').append(alert_lastprice));
    alert_elt.append($('<td></td>').append(alert_reason));
    alert_elt.append($('<td></td>').append(alert_message));
    alert_elt.append($('<td></td>').append(alert_datetime));

    // append
    $('div.alert-list-entries tbody').prepend(alert_elt);

    let message = alert.name + " "  + alert.reason + " " + alert.symbol + " " + alert.message;
    notify({'message': message, 'title': 'Strategy Alert', 'type': 'info'});

    audio_notify('alert');
}

function on_strategy_active_alert(market_id, alert_id, timestamp, alert) {
    // @todo

    window.alerts[key] = alert;
}
