
function on_strategy_signal(market_id, signal_id, timestamp, signal) {
    let signal_elt = $('<tr class="signal"></tr>');
    let key = market_id + ':' + signal.timestamp;
    signal_elt.attr('signal-key', key); // @todo how to because id is -1

    let lsignal_id = $('<span class="signal-id"></span>').text(signal.id);
    let signal_symbol = $('<span class="signal-symbol"></span>').text(market_id);
    let signal_direction = $('<span class="signal-direction fa"></span>')
        .addClass(signal.direction == "long" ? 'trade-long' : 'trade-short')
        .addClass(signal.direction == "long" ? 'fa-arrow-up' : 'fa-arrow-down');

    let signal_way = $('<span class="signal-way fa"></span>')
        .addClass(signal.way == "entry" ? 'signal-entry' : 'signal-exit')
        .addClass(signal.way == "entry" ? 'fa-arrow-right' : 'fa-arrow-left');

    let signal_datetime = $('<span class="signal-datetime"></span>').text(timestamp_to_datetime_str(signal.timestamp*1000));

    let signal_order = $('<span class="signal-order"></span>').text(signal['order-type'] + '@' + signal['order-price']);
    let signal_exit = $('<span class="signal-exit"></span>').text(signal.timeframe || "trade");

    let signal_context = $('<span class="signal-timeframe"></span>').text(signal.label + ' (' + signal.timeframe + ')');

    let signal_stop_loss = $('<span class="signal-stop-loss"></span>').text(signal['stop-loss-price']);
    let signal_take_profit = $('<span class="signal-take-profit"></span>').text(signal['take-profit-price']);

    let signal_reason = $('<span class="signal-reason"></span>').text(signal.reason);

    let pnl = compute_price_pct(signal['take-profit-price'], signal['order-price'], signal.direction == "long" ? 1 : -1);
    let signal_percent = $('<span class="signal-percent"></span>').text((pnl * 100).toFixed(2) + '%');

    let signal_copy = $('<button class="signal-copy btn btn-info fas fa-copy"></button>');

    signal_elt.append($('<td></td>').append(lsignal_id));
    signal_elt.append($('<td></td>').append(signal_symbol));
    signal_elt.append($('<td></td>').append(signal_direction));
    signal_elt.append($('<td></td>').append(signal_way));
    signal_elt.append($('<td></td>').append(signal_datetime));
    signal_elt.append($('<td></td>').append(signal_order));
    signal_elt.append($('<td></td>').append(signal_context));
    signal_elt.append($('<td></td>').append(signal_stop_loss));
    signal_elt.append($('<td></td>').append(signal_take_profit));
    signal_elt.append($('<td></td>').append(signal_reason));
    signal_elt.append($('<td></td>').append(signal_percent));
    signal_elt.append($('<td></td>').append(signal_copy));

    // append
    $('div.signal-list-entries tbody').prepend(signal_elt);

    signal_copy.on('click', on_copy_signal);

    window.signals[key] = signal;

    let message = signal.label + " "  + (signal.reason || signal.way) + " " + signal.direction + " " + signal.symbol + " @" + signal['order-price'];
    notify({'message': message, 'title': 'Trade Signal', 'type': 'info'});

    // @todo limit list and view...
    audio_notify('signal');
}

function on_copy_signal(elt) {
    alert("todo!");
}

//         'entry-timeout': timeframe_to_str(self.entry_timeout),
//         'expiry': self.expiry,
//         'is-user-trade': False,
//         'entry-open-time': self.dump_timestamp(self.ts),
//         'exit-open-time': self.dump_timestamp(self.ts),
