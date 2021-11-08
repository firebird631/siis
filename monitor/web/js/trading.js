function on_order_long(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[market_id];

    if (market_id && market) {
        let profile_name = retrieve_profile(trader_id);
        let profile = market.profiles[profile_name];

        let limit_price = 0.0;
        let trigger_price = 0.0;
        let method = "";
        let quantity_rate = 1;

        let stop_loss = 0.0;
        let take_profit = 0.0;

        let stop_loss_price_mode = window.methods[retrieve_stop_loss_method(trader_id)].type;
        let take_profit_price_mode = window.methods[retrieve_take_profit_method(trader_id)].type;

        if (stop_loss_price_mode == "price") {
            stop_loss = retrieve_stop_loss_price(trader_id);
        } else if (stop_loss_price_mode != "none") {
            stop_loss = window.methods[retrieve_stop_loss_method(trader_id)].distance;
        }

        if (take_profit_price_mode == "price") {
            take_profit = retrieve_take_profit_price(trader_id);
        } else if (take_profit_price_mode != "none") {
            take_profit = window.methods[retrieve_take_profit_method(trader_id)].distance;
        }
        
        let entry_price_mode = window.entry_methods[retrieve_entry_method(trader_id)].type;

        if (entry_price_mode == "limit") {
            limit_price = retrieve_entry_price(trader_id);
            method = "limit";
        } else if (entry_price_mode == "limit-percent") {
            limit_price = window.entry_methods[retrieve_entry_method(trader_id)].distance;
            method = "limit-percent";
        } else if (entry_price_mode == "market") {
            method = "market";
        } else if (entry_price_mode == "best-1") {
            method = "best-1";
        } else if (entry_price_mode == "best-2") {
            method = "best-2";
        } else if (entry_price_mode == "best+1") {
            method = "best+1";
        } else if (entry_price_mode == "best+2") {
            method = "best+2";
        }

        quantity_rate = retrieve_quantity_rate(trader_id) * 0.01 * retrieve_quantity_factor(trader_id);

        let timeframe = profile ? profile['timeframe'] : null;
        let entry_timeout = null;  // @todo
        let leverage = 1;
        let context = profile_name;

        let data = {
            'command': 'trade-entry',
            'market-id': market['market-id'],
            'direction': 1,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'entry-timeout': entry_timeout,
            'leverage': leverage
        };

        if (stop_loss_price_mode != "none") {
            data['stop-loss'] = stop_loss;
            data['stop-loss-price-mode'] = stop_loss_price_mode;
        }

        if (take_profit_price_mode != "none") {
            data['take-profit'] = take_profit;
            data['take-profit-price-mode'] = take_profit_price_mode;
        }

        if (context && profile && ('strategy' in profile)) {
            data['context'] = context;
        } else if (timeframe) {
            data['timeframe'] = timeframe;
        }

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
                    notify({'message': data.messages[msg], 'title': 'Order Long', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Order Long', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Order Long', 'type': 'error'});
            }
        });
    }
};

function on_order_short(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[market_id];

    if (market_id && market) {
        let profile_name = retrieve_profile(trader_id);
        let profile = market.profiles[profile_name];

        let limit_price = 0.0;
        let trigger_price = 0.0;
        let method = "";
        let quantity_rate = 1;

        let stop_loss = 0.0;
        let take_profit = 0.0;

        let stop_loss_price_mode = window.methods[retrieve_stop_loss_method(trader_id)].type;
        let take_profit_price_mode = window.methods[retrieve_take_profit_method(trader_id)].type;

        if (stop_loss_price_mode == "price") {
            stop_loss = retrieve_stop_loss_price(trader_id);
        } else if (stop_loss_price_mode != "none") {
            stop_loss = window.methods[retrieve_stop_loss_method(trader_id)].distance;
        }

        if (take_profit_price_mode == "price") {
            take_profit = retrieve_take_profit_price(trader_id);
        } else if (take_profit_price_mode != "none") {
            take_profit = window.methods[retrieve_take_profit_method(trader_id)].distance;
        }
        
        let entry_price_mode = window.entry_methods[retrieve_entry_method(trader_id)].type;

        if (entry_price_mode == "limit") {
            limit_price = retrieve_entry_price(trader_id);
            method = "limit";
        } else if (entry_price_mode == "limit-percent") {
            limit_price = window.entry_methods[retrieve_entry_method(trader_id)].distance;;
            method = "limit-percent";
        } else if (entry_price_mode == "market") {
            method = "market";
        } else if (entry_price_mode == "best-1") {
            method = "best-1";
        } else if (entry_price_mode == "best-2") {
            method = "best-2";
        } else if (entry_price_mode == "best+1") {
            method = "best+1";
        } else if (entry_price_mode == "best+2") {
            method = "best+2";
        }

        quantity_rate = retrieve_quantity_rate(trader_id) * 0.01 * retrieve_quantity_factor(trader_id);

        let timeframe = profile ? profile['timeframe'] : null;
        let entry_timeout = null;  // @todo
        let leverage = 1;
        let context = profile_name;

        let data = {
            'command': 'trade-entry',
            'market-id': market['market-id'],
            'direction': -1,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'entry-timeout': entry_timeout,
            'leverage': leverage
        };

        if (stop_loss_price_mode != "none") {
            data['stop-loss'] = stop_loss;
            data['stop-loss-price-mode'] = stop_loss_price_mode;
        }

        if (take_profit_price_mode != "none") {
            data['take-profit'] = take_profit;
            data['take-profit-price-mode'] = take_profit_price_mode;
        }

        if (context && profile && ('strategy' in profile)) {
            data['context'] = context;
        } else if (timeframe) {
            data['timeframe'] = timeframe;
        }

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
                    notify({'message': data.messages[msg], 'title': 'Order Short', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Order Short', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Order Short', 'type': 'error'});
            }
        });
    }
};

function on_close_trade(elt) {
    let key = retrieve_trade_key(elt);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let trade_id = parseInt(parts[1]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];

    if (market_id && market && trade_id) {
        let data = {
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'action': "close"
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
                    notify({'message': data.messages[msg], 'title': 'Order Close', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Order Close', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Order Close', 'type': 'error'});
            }
        });
    }
};

function on_breakeven_trade(elt) {
    let key = retrieve_trade_key(elt);

    let trade = window.actives_trades[key];

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let trade_id = parseInt(parts[1]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];
    let stop_loss_price = parseFloat(trade['avg-entry-price'] || trade['order-price']);

    let pnl_pct = trade['profit-loss-pct'];

    if (pnl_pct <= 0.0) {
        let msg = "It is not allowed to break-even a non profit trade. On market " + market['symbol'] + ".";
        notify({'message': msg, 'title': 'Break-even Stop-Loss', 'type': 'info'});
        return false;
    }

    if (market_id && market && trade_id) {
        let data = {
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'command': "trade-modify",
            'action': "stop-loss",
            'stop-loss': stop_loss_price,
            'force': false
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
                    notify({'message': data.messages[msg], 'title': 'Break-even Stop-Loss', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Break-even Stop-Loss', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Break-even Stop-Loss', 'type': 'error'});
            }
        });
    }
}

let on_active_trade_entry_message = function(market_id, trade_id, timestamp, value) {
    // insert into active trades
    add_active_trade(market_id, value);

    if (parseFloat(value['filled-entry-qty']) <= 0.0) {
        let key = market_id + ':' + trade_id;
        window.pending_trades.push(key);
    }

    // update global counters
    update_status_trades();
};

let on_active_trade_update_message = function(market_id, trade_id, timestamp, value) {
    // update into active trades
    update_active_trade(market_id, value);

    // remove from pending trades once the entry quantity is filled
    let idx = window.pending_trades.indexOf(trade_id);
    if (idx >= 0 && parseFloat(value['filled-entry-qty']) > 0.0) {
        window.pending_trades = window.pending_trades.splice(idx, 1);

        // and update global counters
        update_status_trades();
    }
};

let on_active_trade_exit_message = function(market_id, trade_id, timestamp, value) {
    // remove from active trades
    remove_active_trade(market_id, trade_id, value);

    // insert to historical trades
    if (value['state'] == "closed") {
        add_historical_trade(market_id, value);
    }

    // remove from pending trades
    let idx = window.pending_trades.indexOf(trade_id);
    if (idx >= 0) {
        window.pending_trades = window.pending_trades.splice(idx, 1);
    }

    // update global counters
    update_status_trades();
};

function update_status_trades() {
    let total_trades = Object.keys(window.actives_trades).length;
    let historical = Object.keys(window.historical_trades).length;
    let pending = window.pending_trades.length;

    $('#total_trades').text(total_trades);
    $('#closed_trades').text(historical);
    $('#pending_trades').text(pending);
    $('#active_trades').text(total_trades - pending);
}

function update_status_pnl() {
    // @todo value / base exchange rate
    let rpnl_pct = 0.0;
    let rpnl_v = 0.0;
    let upnl_pct = 0.0;
    let upnl_v = 0.0;

    let currency = "";

    for (let trade_id in actives_trades) {
        let trade = actives_trades[trade_id];

        upnl_pct += trade['profit-loss-pct'];
        upnl_v += trade.stats['profit-loss'];

        if (!currency) {
            currency = trade.stats['profit-loss-currency'];
        }
    }

    for (let trade_id in historical_trades) {
        let trade = historical_trades[trade_id];

        rpnl_pct += trade['profit-loss-pct'];
        rpnl_v += trade.stats['profit-loss'];

        if (!currency) {
            currency = trade.stats['profit-loss-currency'];
        }
    }

    window.stats['upnlpct'] = upnl_pct;
    window.stats['upnl'] = upnl_v;
    
    window.stats['rpnlpct'] = rpnl_pct;
    window.stats['rpnl'] = rpnl_v;

    $('#upln_pct').text(upnl_pct.toFixed(2) + "%");
    $('#upln_value').text(upnl_v + currency);

    $('#rpln_pct').text(rpnl_pct.toFixed(2) + "%");
    $('#rpln_value').text(rpnl_v + currency);
}

//
// trades list functions
//

function on_close_all_active_trade(elt) {
    notify({'message': "todo!", 'type': "error"});
}

function compute_price_pct(target, base, direction) {
    if (typeof(target) === "string") {
        target = parseFloat(target);
    }

    if (typeof(base) === "string") {
        base = parseFloat(base);
    }

    if (direction > 0) {
        return (target - base) / base;
    } else if (direction < 0) {
        return (base - target) / base;
    }

    return 0.0;
}

function normalized_profit_loss_distance(entry, close, stop_loss_rate, take_profit_rate, direction) {
    // -1 .. 0 .. 1 distance
    if (typeof(entry) === "string") {
        entry = parseFloat(entry);
    }

    if (typeof(close) === "string") {
        close = parseFloat(close);
    }

    if (typeof(stop_loss_rate) === "string") {
        stop_loss_rate = parseFloat(stop_loss_rate);
    }

    if (typeof(take_profit_rate) === "string") {
        take_profit_rate = parseFloat(take_profit_rate);
    }

    if (direction > 0) {
        // current pnl rate
        let pnl_rate = (close - entry) / entry;

        if (pnl_rate > 0.0) {
            return Math.min(1.0, 1.0 - (take_profit_rate - pnl_rate) / take_profit_rate);
        } else if (pnl_rate < 0.0) {
            return Math.max(-1.0, (stop_loss_rate - pnl_rate) / stop_loss_rate - 1.0);
        } else {
            return 0.0
        }
    } else if (direction < 0) {
        // current pnl rate
        let pnl_rate = (entry - close) / entry;

        if (pnl_rate > 0.0) {
            return Math.min(1.0, 1.0 - (take_profit_rate - pnl_rate) / take_profit_rate);
        } else if (pnl_rate < 0.0) {
            return Math.max(-1.0, (stop_loss_rate - pnl_rate) / stop_loss_rate - 1.0);
        } else {
            return 0.0
        }
    }

    return 0.0;    
}

function add_active_trade(market_id, trade) {
    let trade_elt = $('<tr class="active-trade"></tr>');
    let key = market_id + ':' + trade.id;
    trade_elt.attr('trade-key', key);

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    // info
    let trade_id = $('<span class="trade-id"></span>').text(trade.id);
    let trade_symbol = $('<span class="trade-symbol badge"></span>').text(symbol);
    if (trade['filled-entry-qty'] > 0.0) {
        trade_symbol.addClass("badge-info");
    } else {
        trade_symbol.addClass("badge-secondary");
    }
    let trade_direction = $('<span class="trade-direction fa"></span>')
        .addClass(trade.direction == "long" ? 'trade-long' : 'trade-short')
        .addClass(trade.direction == "long" ? 'fa-arrow-up' : 'fa-arrow-down');

    // order date, first trade date
    let trade_datetime = $('<span class="trade-datetime"></span>').text(
        timestamp_to_datetime_str(trade['entry-open-time']));
    trade_datetime.attr('data-toggle', "tooltip");
    trade_datetime.attr('data-placement', "top");
    trade_datetime.attr('title', timestamp_to_datetime_str(trade['stats']['first-realized-entry-datetime']));

    let trade_order = $('<span class="trade-order"></span>').text(
        trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');
 
    // entry
    let trade_entry = $('<span class="trade-entry"></span>').text(
        trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    trade_entry.attr('data-toggle', "tooltip");
    trade_entry.attr('data-placement', "top");

    let entry_price_rate = compute_price_pct(trade['avg-entry-price'],
        trade.stats['close-exec-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    trade_entry.attr('title', (entry_price_rate * 100).toFixed(2) + '%');

    // exit
    let trade_exit = $('<span class="trade-exit"></span>').text('-')
    trade_exit.attr('data-toggle', "tooltip");
    trade_exit.attr('data-placement', "top");
    trade_exit.attr('title', '-');

    // context
    let trade_context = $('<span class="trade-context"></span>')
        .text(trade['label'] ? trade['label'] + ' (' + trade['timeframe'] + ')' : trade['timeframe']);

    // status
    let trade_auto = $('<span class="trade-auto fa"></span>')
        .addClass(trade['is-user-trade'] ? 'trade-auto-no' : 'trade-auto-yes')
        .addClass(trade['is-user-trade'] ? 'fa-pause' : 'fa-play');

    // pnl
    let trade_percent = $('<span class="trade-percent"></span>');
    let trade_upnl = $('<span class="trade-upnl"></span>');

    if (parseFloat(trade['filled-entry-qty']) > 0.0) {
        trade_percent.text(trade['profit-loss-pct'] + '%');
        trade_upnl.text(format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency']);
    } else {
        trade_percent.text("-");
        trade_upnl.text("-");
    }

    // fees
    let fees = trade.stats['entry-fees'] == undefined || trade.stats['exit-fees'] == undefined ? 0.0 : format_quote_price(
        market_id, trade.stats['entry-fees'] + trade.stats['exit-fees']);
    let trade_fees = $('<span class="trade-fees"></span>').text(fees);
    trade_fees.attr('title', (trade.stats['fees-pct'] == undefined ? 0.0 : trade.stats['fees-pct']).toFixed(2) + '%');

    // stop-loss
    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);  // + UP/DN buttons
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'],
        trade['avg-entry-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    let trade_stop_loss_chg = $('<button class="btn btn-light trade-modify-stop-loss fa fa-pencil"></button>');

    // take-profit
    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);  // + UP/DN buttons
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");
    
    let trade_take_profit_chg = $('<button class="btn btn-light trade-modify-take-profit fa fa-pencil"></button>');

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'],
        trade['avg-entry-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    trade_take_profit.attr('title', (take_profit_price_rate * 100).toFixed(2) + '%');

    // actions
    let trade_close = $('<button class="trade-close btn btn-danger fa fa-close"></button>');
    let trade_breakeven = $('<button class="trade-be btn btn-light fa fa-random"></button>');
    let trade_details = $('<button class="trade-details btn btn-info fa fa-info"></button>');

    trade_elt.append($('<td></td>').append(trade_id));
    trade_elt.append($('<td></td>').append(trade_symbol));
    trade_elt.append($('<td></td>').append(trade_direction));
    trade_elt.append($('<td></td>').append(trade_datetime));
    
    trade_elt.append($('<td></td>').append(trade_order));
    trade_elt.append($('<td></td>').append(trade_entry));
    trade_elt.append($('<td></td>').append(trade_exit));
    
    trade_elt.append($('<td></td>').append(trade_auto));
    trade_elt.append($('<td></td>').append(trade_context));

    trade_elt.append($('<td></td>').append(trade_percent));
    trade_elt.append($('<td></td>').append(trade_upnl));
    trade_elt.append($('<td></td>').append(trade_fees));

    if (server.permissions.indexOf("strategy-modify-trade") != -1) {
        trade_elt.append($('<td></td>').append(trade_stop_loss).append(trade_stop_loss_chg));
        trade_elt.append($('<td></td>').append(trade_take_profit).append(trade_take_profit_chg));
    } else {
        trade_elt.append($('<td></td>').append(trade_stop_loss));
        trade_elt.append($('<td></td>').append(trade_take_profit));
    }

    if (server.permissions.indexOf("strategy-close-trade") < 0) {
        trade_close.attr("disabled", "")
    }

    if (server.permissions.indexOf("strategy-modify-trade") < 0) {
        trade_breakeven.attr("disabled", "")
    }

    trade_elt.append($('<td></td>').append(trade_close));
    trade_elt.append($('<td></td>').append(trade_breakeven));
    trade_elt.append($('<td></td>').append(trade_details));

    // append
    $('div.active-trade-list-entries tbody').append(trade_elt);

    // actions
    if (server.permissions.indexOf("strategy-close-trade") != -1) {
        trade_close.on('click', on_close_trade);
        trade_breakeven.on('click', on_breakeven_trade);
    }

    if (server.permissions.indexOf("strategy-modify-trade") != -1) {
        trade_stop_loss_chg.on('click', on_modify_active_trade_stop_loss);
        trade_take_profit_chg.on('click', on_modify_active_trade_take_profit);
    }

    trade_details.on('click', on_details_active_trade);

    window.actives_trades[key] = trade;

    audio_notify('entry');
};

function update_active_trade(market_id, trade) {
    let key = market_id + ':' + trade.id;
    let container = $('div.active-trade-list-entries tbody');
    let trade_elt = container.find('tr.active-trade[trade-key="' + key + '"]')

    let trade_symbol = $('<span class="trade-symbol badge"></span>').text(trade.symbol);
    if (trade['filled-entry-qty'] > 0.0) {
        trade_symbol.addClass("badge-info");
    } else {
        trade_symbol.addClass("badge-secondary");
    }

    let trade_order = $('<span class="trade-order"></span>').text(
        trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');

    // order date, first trade date
    let trade_datetime = $('<span class="trade-datetime"></span>').text(
        timestamp_to_datetime_str(trade['entry-open-time']));
    trade_datetime.attr('data-toggle', "tooltip");
    trade_datetime.attr('data-placement', "top");
    trade_datetime.attr('title', timestamp_to_datetime_str(trade['stats']['first-realized-entry-datetime']));

    // entry
    let trade_entry = $('<span class="trade-entry"></span>').text(
        trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    trade_entry.attr('data-toggle', "tooltip");
    trade_entry.attr('data-placement', "top");

    let entry_price_rate = compute_price_pct(trade['avg-entry-price'],
        trade.stats['close-exec-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    trade_entry.attr('title', (entry_price_rate * 100).toFixed(2) + '%');

    // exit
    let trade_exit = $('<span class="trade-exit"></span>').text(
        trade['avg-exit-price'] + ' (' + trade['filled-exit-qty'] + ')');
    trade_exit.attr('data-toggle', "tooltip");
    trade_exit.attr('data-placement', "top");

    let exit_price_rate = compute_price_pct(trade['avg-exit-price'],
        trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_exit.attr('title', (exit_price_rate * 100).toFixed(2) + '%');

    // pnl
    let trade_percent = $('<span class="trade-percent"></span>');
    let trade_upnl = $('<span class="trade-upnl"></span>');

    if (parseFloat(trade['filled-entry-qty']) > 0.0) {
        trade_percent.text(trade['profit-loss-pct'] + '%');
        trade_upnl.text(format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency']);
    } else {
        trade_percent.text("-");
        trade_upnl.text("-");
    }

    // fees
    let fees = trade.stats['entry-fees'] == undefined || trade.stats['exit-fees'] == undefined ? 0.0 : format_quote_price(
        market_id, trade.stats['entry-fees'] + trade.stats['exit-fees']);
    let trade_fees = $('<span class="trade-fees"></span>').text(fees);
    trade_fees.attr('title', (trade.stats['fees-pct'] == undefined ? 0.0 : trade.stats['fees-pct']).toFixed(2) + '%');

    // stop-loss
    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);  // + UP/DN buttons
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'],
        trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    // take-profit + UP/DN buttons
    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'],
        trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_take_profit.attr('title', (take_profit_price_rate * 100).toFixed(2) + '%');

    // colorized upnl % background
    let upnl_bg_color = 'initial';
    let upnl_border_color = 'initial';
    let upnl_color = 'white';

    let upnl_bg = normalized_profit_loss_distance(
            trade['avg-entry-price'],
            trade.stats['close-exec-price'],
            stop_loss_price_rate,
            take_profit_price_rate,
            trade.direction == "long" ? 1 : -1);

    if (upnl_bg < 0.0) {
        upnl_bg_color = 'rgba(255, 0, 0, ' + (-upnl_bg * 0.9).toFixed(1) + ')';
        upnl_border_color = 'rgba(255, 0, 0, 0)';
    } else if (upnl_bg > 0.0) {
        upnl_bg_color = 'rgba(0, 255, 0, ' + (upnl_bg * 0.9).toFixed(1) + ')';
        upnl_border_color = 'rgba(0, 255, 0, 0)';
    }

    trade_percent.css('background', upnl_bg_color)
        .css('color', upnl_color)
        .css('border', 'solid 1px ' + upnl_border_color)
        .css('border-radius', '3px')
        .css('width', '100%');

    // update
    trade_elt.find('span.trade-symbol').replaceWith(trade_symbol);
    trade_elt.find('span.trade-datetime').replaceWith(trade_datetime);
    trade_elt.find('span.trade-order').replaceWith(trade_order);
    trade_elt.find('span.trade-entry').replaceWith(trade_entry);
    trade_elt.find('span.trade-exit').replaceWith(trade_exit);
    trade_elt.find('span.trade-percent').replaceWith(trade_percent);
    trade_elt.find('span.trade-upnl').replaceWith(trade_upnl);
    trade_elt.find('span.trade-fees').replaceWith(trade_fees);
    trade_elt.find('span.trade-stop-loss').replaceWith(trade_stop_loss);
    trade_elt.find('span.trade-take-profit').replaceWith(trade_take_profit);

    window.actives_trades[key] = trade;
};

function remove_active_trade(market_id, trade_id, trade) {
    let key = market_id + ':' + trade_id;
    let container = $('div.active-trade-list-entries tbody');

    container.find('tr.active-trade[trade-key="' + key + '"]').remove();
    if (key in window.actives_trades) {
        delete window.actives_trades[key];
    }

    if (trade['profit-loss-pct'] > 0.0) {
        audio_notify('win');
    } else {
        if (parseFloat(trade['filled-entry-qty']) <= 0) {
            audio_notify('timeout');
        } else {
            audio_notify('loose');
        }
    }
};

function format_price(market_id, price) {
    let market = window.markets[market_id];
    if (market) {
        if (typeof(price) === "string") {
            price = parseFloat(price);
        }

        return price.toFixed(market['price-limits'][3] || 2);
    }

    return "0.0";
}

function format_quote_price(market_id, price) {
    let market = window.markets[market_id];
    if (market) {
        if (typeof(price) === "string") {
            price = parseFloat(price);
        }

        return price.toFixed(market['notional-limits'][3] || 2);
    }

    return "0.0";
}

function add_historical_trade(market_id, trade) {
    let trade_elt = $('<tr class="historical-trade"></tr>');
    let key = market_id + ':' + trade.id;
    trade_elt.attr('trade-key', key);

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    let trade_id = $('<span class="trade-id"></span>').text(trade.id);
    let trade_symbol = $('<span class="trade-symbol badge badge-info"></span>').text(symbol);
    let trade_direction = $('<span class="trade-direction fa"></span>')
        .addClass(trade.direction == "long" ? 'trade-long' : 'trade-short')
        .addClass(trade.direction == "long" ? 'fa-arrow-up' : 'fa-arrow-down');

    let trade_datetime = $('<span class="trade-datetime"></span>').text(
        timestamp_to_datetime_str(trade['entry-open-time']));
    trade_datetime.attr('data-toggle', "tooltip");
    trade_datetime.attr('data-placement', "top");
    trade_datetime.attr('title', timestamp_to_datetime_str(trade['stats']['last-realized-exit-datetime']));

    let trade_order = $('<span class="trade-order"></span>').text(
        trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');
 
    let trade_entry = $('<span class="trade-entry"></span>').text(
        trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    let trade_exit = $('<span class="trade-entry"></span>').text(
        trade['avg-exit-price'] + ' (' + trade['filled-exit-qty'] + ')');

    let trade_context = $('<span class="trade-context"></span>')
        .text(trade['label'] ? trade['label'] + ' (' + trade['timeframe'] + ')' : trade['timeframe']);

    let trade_percent = $('<span class="trade-percent"></span>').text(trade['profit-loss-pct'] +'%');   
    let trade_pnl = $('<span class="trade-pnl"></span>').text(format_quote_price(market_id,
        trade.stats['profit-loss']) + trade.stats['profit-loss-currency']);

    let fees = format_quote_price(market_id, trade.stats['entry-fees'] + trade.stats['exit-fees']);
    let trade_fees = $('<span class="trade-fees"></span>').text(fees);
    trade_fees.attr('title', (trade.stats['fees-pct'] || 0.0).toFixed(2) + '%');

    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'],
        trade['avg-entry-price'], trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'],
        trade['avg-entry-price'], trade.direction == "long" ? 1 : -1);
    trade_take_profit.attr('title', (take_profit_price_rate * 100).toFixed(2) + '%');

    let trade_details = $('<button class="trade-details btn btn-info fa fa-info"></button>');

    trade_elt.append($('<td></td>').append(trade_id));
    trade_elt.append($('<td></td>').append(trade_symbol));
    trade_elt.append($('<td></td>').append(trade_direction));
    trade_elt.append($('<td></td>').append(trade_datetime));
    
    trade_elt.append($('<td></td>').append(trade_order));
    trade_elt.append($('<td></td>').append(trade_entry));
    trade_elt.append($('<td></td>').append(trade_exit));
    
    trade_elt.append($('<td></td>').append(trade_context));

    trade_elt.append($('<td></td>').append(trade_percent));
    trade_elt.append($('<td></td>').append(trade_pnl));
    trade_elt.append($('<td></td>').append(trade_fees));
    
    trade_elt.append($('<td></td>').append(trade_stop_loss));
    trade_elt.append($('<td></td>').append(trade_take_profit));
    
    trade_elt.append($('<td></td>').append(trade_details));

    // actions
    trade_details.on('click', on_details_historical_trade);

    // most recent
    $('div.historical-trade-list-entries tbody').prepend(trade_elt);

    window.historical_trades[key] = trade;

    // global stats
    window.stats['rpnlpct'] += trade['profit-loss-pct'];
    window.stats['rpnl'] += trade.stats['profit-loss'];
};

function on_modify_active_trade_stop_loss(elt) {
    let key = retrieve_trade_key(elt);
    $('#modify_trade_stop_loss').attr('trade-key', key);

    let trade = window.actives_trades[key];
    $('#modified_stop_loss_price').val(trade['stop-loss-price']);
    $('#modified_stop_loss_range').slider('setValue', 50);

    $('#modify_trade_stop_loss').modal({'show': true, 'backdrop': true});
}

function on_modify_active_trade_take_profit(elt) {
    let key = retrieve_trade_key(elt);
    $('#modify_trade_take_profit').attr('trade-key', key);

    let trade = window.actives_trades[key];
    $('#modified_take_profit_price').val(trade['take-profit-price']);
    $('#modified_take_profit_range').slider('setValue', 50);

    $('#modify_trade_take_profit').modal({'show': true, 'backdrop': true});
}

function on_change_take_profit_step() {
    let key = $('#modify_trade_take_profit').attr('trade-key');

    let trade = window.actives_trades[key];
    let take_profit_price = $('#modified_take_profit_price').val();

    let mode = $('#modified_take_profit_type').val();
    let range = parseFloat($('#modified_take_profit_range').val());

    if (mode == 'percent') {
        range = (range - 50) * 0.001;

        take_profit_price = format_price(trade['market-id'],
            parseFloat(trade['take-profit-price']) * (1.0 + range));

        $('#modified_take_profit_range_relative').text((range*100).toFixed(2) + "%");
    } else if (mode == 'pip') {
        range = (range - 50);
        let value_per_pip = window.markets[trade['market-id']]['value-per-pip'];

        take_profit_price = format_price(trade['market-id'],
            parseFloat(trade['take-profit-price']) + value_per_pip * range);

        $('#modified_take_profit_range_relative').text(range + "pips");
    }

    $('#modified_take_profit_price').val(take_profit_price);
}

function on_change_stop_loss_step() {
    let key = $('#modify_trade_stop_loss').attr('trade-key');

    let trade = window.actives_trades[key];
    let stop_loss_price = $('#modified_stop_loss_price').val();

    let mode = $('#modified_stop_loss_type').val();
    let range = parseFloat($('#modified_stop_loss_range').val());

    if (mode == 'percent') {
        range = (range - 50) * 0.001;

        stop_loss_price = format_price(trade['market-id'],
            parseFloat(trade['stop-loss-price']) * (1.0 + range));

        $('#modified_stop_loss_range_relative').text((range*100).toFixed(2) + "%");
    } else if (mode == 'pip') {
        range = (range - 50);
        let value_per_pip = window.markets[trade['market-id']]['value-per-pip'];

        stop_loss_price = format_price(trade['market-id'],
            parseFloat(trade['stop-loss-price']) + value_per_pip * range);

        $('#modified_stop_loss_range_relative').text(range + "pips");
    }

    $('#modified_stop_loss_price').val(stop_loss_price);
}

function on_apply_modify_active_trade_take_profit() {
    let key = $('#modify_trade_take_profit').attr('trade-key');

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let trade_id = parseInt(parts[1]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];
    let take_profit_price = parseFloat($('#modified_take_profit_price').val());

    if (market_id && market && trade_id) {
        let data = {
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'command': "trade-modify",
            'action': "take-profit",
            'take-profit': take_profit_price,
            'force': true
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
                    notify({'message': data.messages[msg], 'title': 'Modify Take-Profit', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Modify Take-Profit', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Modify Take-Profit', 'type': 'error'});
            }
        });
    }
}

function on_apply_modify_active_trade_stop_loss() {
    let key = $('#modify_trade_stop_loss').attr('trade-key',);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let trade_id = parseInt(parts[1]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];
    let stop_loss_price = parseFloat($('#modified_stop_loss_price').val());

    if (market_id && market && trade_id) {
        let data = {
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'command': "trade-modify",
            'action': "stop-loss",
            'stop-loss': stop_loss_price,
            'force': true
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
                    notify({'message': data.messages[msg], 'title': 'Modify Stop-Loss', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Modify Stop-Loss', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Modify Stop-Loss', 'type': 'error'});
            }
        });
    }
}

function on_add_active_trade_step_stop_loss() {
    let key = $('#modify_trade_stop_loss').attr('trade-key', key);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let trade_id = parseInt(parts[1]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];

    let step_stop_loss_price = parseFloat($('#step_stop_loss_price').val());
    let trigger_price = parseFloat($('#step_stop_loss_trigger_price').val());

    if (market_id && market && trade_id) {
        let data = {
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'command': "trade-modify",
            'action': "step-stop-loss",
            'stop-loss': step_stop_loss_price,
            'trigger': trigger_price
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
                    notify({'message': data.messages[msg], 'title': 'Add Step Stop-Loss', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Add Step Stop-Loss', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Add Step Stop-Loss', 'type': 'error'});
            }
        });
    }
}

function on_details_active_trade(elt) {
    let key = retrieve_trade_key(elt);
    let table = $('#trade_details_table');
    let tbody = table.find('tbody').empty();

    let trade = window.actives_trades[key];
    if (!trade) {
        return;
    }

    let market_id = trade['market-id'];

    let app = $('<tr></tr>').append($('<td class="data-name">Strategy</td>')).append(
        $('<td class="data-value">' + trade['app-name'] + ' / ' + trade['app-id'] + '</td>'));
    let id = $('<tr></tr>').append($('<td class="data-name">Identifier</td>')).append(
        $('<td class="data-value">' + trade.id + '</td>'));
    let lmarket_id = $('<tr></tr>').append($('<td class="data-name">Market</td>')).append(
        $('<td class="data-value"><span class="badge">' + trade['market-id'] + '</span></td>'));
    let symbol = $('<tr></tr>').append($('<td class="data-name">Symbol</td>')).append(
        $('<td class="data-value"><span class="badge">' + trade.symbol + '</span></td>'));
    let version = $('<tr></tr>').append($('<td class="data-name">Version</td>')).append(
        $('<td class="data-value">' + trade.version + '</td>'));
    let trade_type = $('<tr></tr>').append($('<td class="data-name">Type</td>')).append(
        $('<td class="data-value">' + trade.trade + '</td>'));
    let timestamp = $('<tr></tr>').append($('<td class="data-name">Last update</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.timestamp) + '</td>'));
    let timeframe = $('<tr></tr>').append($('<td class="data-name">Timeframe</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade.timeframe) + '</td>'));
    let entry_timeout = $('<tr></tr>').append($('<td class="data-name">Entry timeout</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade['entry-timeout']) + '</td>'));
    let expiry = $('<tr></tr>').append($('<td class="data-name">Expiry</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade.expiry) + '</td>'));
    let user_trade = $('<tr></tr>').append($('<td class="data-name">User trade</td>')).append(
        $('<td class="data-value">' + trade['is-user-trade'] + '</td>'));

    let direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value">' + trade.direction + '</td>'));

    if (trade.direction == "long") {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="trade-direction fa trade-long fa-arrow-up"></span></td>'));
    } else if (trade.direction == "short") {
       direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="trade-direction fa trade-short fa-arrow-dn"></span></td>'));
    }

    let state = $('<tr></tr>').append($('<td class="data-name">State</td>')).append(
        $('<td class="data-value">' + trade.state + '</td>'));
    let label = $('<tr></tr>').append($('<td class="data-name">Label</td>')).append(
        $('<td class="data-value">' + trade.label + '</td>'));
    let order_price = $('<tr></tr>').append($('<td class="data-name">Order price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['order-price']) + '</td>'));
    let order_qty = $('<tr></tr>').append($('<td class="data-name">Order qty</td>')).append(
        $('<td class="data-value">' + trade['order-qty'] + '</td>'));

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'],
        trade['avg-entry-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    let trade_stop_loss_pct = (stop_loss_price_rate * 100).toFixed(2) + '%';
    let stop_loss_price = $('<tr></tr>').append($('<td class="data-name">Stop-Loss</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['stop-loss-price']) + ' (' +
        trade_stop_loss_pct + ')</td>'));

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'],
        trade['avg-entry-price'] || trade['order-price'],
        trade.direction == "long" ? 1 : -1);
    let trade_take_profit_pct = (take_profit_price_rate * 100).toFixed(2) + '%';
    let take_profit_price = $('<tr></tr>').append($('<td class="data-name">Take-Profit</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['take-profit-price']) + ' (' +
        trade_take_profit_pct + ')</td>'));

    let avg_entry_price = $('<tr></tr>').append($('<td class="data-name">Avg entry price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['avg-entry-price']) + '</td>'));
    let avg_exit_price = $('<tr></tr>').append($('<td class="data-name">Avg exit price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['avg-exit-price']) + '</td>'));

    let entry_open_time = $('<tr></tr>').append($('<td class="data-name">Entry open at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade['entry-open-time']) + '</td>'));
    let exit_open_time = $('<tr></tr>').append($('<td class="data-name">Exit open at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade['exit-open-time']) + '</td>'));

    let filled_entry_qty = $('<tr></tr>').append($('<td class="data-name">Filled entry qty</td>')).append(
        $('<td class="data-value">' + trade['filled-entry-qty'] + '</td>'));
    let filled_exit_qty = $('<tr></tr>').append($('<td class="data-name">Filled exit qty</td>')).append(
        $('<td class="data-value">' + trade['filled-exit-qty'] + '</td>'));

    let profit_loss_pct_text = '-';
    let trade_upnl_text= '-';
    let entry_fees_text = '-';
    let exit_fees_text = '-';
    let total_fees_text = '-';
    if (parseFloat(trade['filled-entry-qty']) > 0.0) {
        profit_loss_pct_text = trade['profit-loss-pct'] + '%';
        trade_upnl_text = format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency'];
        entry_fees_text = format_quote_price(market_id, trade.stats['entry-fees']) + trade.stats['profit-loss-currency'];
        total_fees_text = format_quote_price(market_id, trade.stats['entry-fees'] + trade.stats['exit-fees']) +
            trade.stats['profit-loss-currency'] + ' (' + trade.stats['fees-pct'] + '%)';
        symbol.find('span').addClass('badge-info');
        lmarket_id.find('span').addClass('badge-info');
    } else {
        symbol.find('span').addClass('badge-secondary');
        lmarket_id.find('span').addClass('badge-secondary');
    }

    if (parseFloat(trade['filled-exit-qty']) > 0.0) {
        exit_fees_text = format_quote_price(market_id, trade.stats['exit-fees']) + trade.stats['profit-loss-currency'];
    }

    let profit_loss_pct = $('<tr></tr>').append($('<td class="data-name">Profit/Loss</td>')).append(
        $('<td class="data-value">' + profit_loss_pct_text + '</td>'));

    let trade_upnl = $('<tr></tr>').append($('<td class="data-name">UPNL</td>')).append(
        $('<td class="data-value">' + trade_upnl_text + '</td>'));

    if (trade.stats['profit-loss'] > 0.0) {
        profit_loss_pct.find('td:last').css('color', 'green');
        trade_upnl.find('td:last').css('color', 'green');
    } else if (trade.stats['profit-loss'] < 0.0) {
       profit_loss_pct.find('td:last').css('color', 'red');
       trade_upnl.find('td:last').css('color', 'red');
    }

    tbody.append(app);
    tbody.append(id);
    tbody.append(lmarket_id);
    tbody.append(symbol);
    tbody.append(version);
    tbody.append(trade_type);
    tbody.append(timestamp);
    tbody.append(entry_timeout);
    tbody.append(expiry);
    tbody.append(user_trade);
    tbody.append(direction);
    tbody.append(state);
    tbody.append(label);
    tbody.append(order_price);
    tbody.append(order_qty);
    tbody.append(stop_loss_price);
    tbody.append(take_profit_price);
    tbody.append(avg_entry_price);
    tbody.append(avg_exit_price);
    tbody.append(entry_open_time);
    tbody.append(exit_open_time);
    tbody.append(filled_entry_qty);
    tbody.append(filled_exit_qty);
    tbody.append(profit_loss_pct);
    tbody.append(trade_upnl);

    let best_price_text = '-';
    let worst_price_text = '-';

    if (trade.stats['best-datetime']) {
        best_price_text = format_price(market_id, trade.stats['best-price']) + ' on ' +
            timestamp_to_datetime_str(trade.stats['best-datetime']);
        worst_price_text = format_price(market_id, trade.stats['worst-price']) + ' on ' +
            timestamp_to_datetime_str(trade.stats['worst-datetime']);
    }

    let best_price = $('<tr></tr>').append($('<td class="data-name">Best price</td>')).append(
        $('<td class="data-value">' + best_price_text + '</td>'));
    let worst_price = $('<tr></tr>').append($('<td class="data-name">Worst price</td>')).append(
        $('<td class="data-value">' + worst_price_text + '</td>'));

    let entry_order_type = $('<tr></tr>').append($('<td class="data-name">Entry order type</td>')).append(
        $('<td class="data-value">' + trade.stats['entry-order-type'] + '</td>'));

    let first_realized_entry_dt = $('<tr></tr>').append($('<td class="data-name">First realized entry at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['first-realized-entry-datetime']) + '</td>'));
    let first_realized_exit_dt = $('<tr></tr>').append($('<td class="data-name">First realized exit at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['first-realized-exit-datetime']) + '</td>'));

    let last_realized_entry_dt = $('<tr></tr>').append($('<td class="data-name">Last realized entry at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['last-realized-entry-datetime']) + '</td>'));
    let last_realized_exit_dt = $('<tr></tr>').append($('<td class="data-name">Last realized exit at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['last-realized-exit-datetime']) + '</td>'));

    let entry_fees = $('<tr></tr>').append($('<td class="data-name">Entry fees</td>')).append(
        $('<td class="data-value">' + entry_fees_text + '</td>'));
    let exit_fees = $('<tr></tr>').append($('<td class="data-name">Exit fees</td>')).append(
        $('<td class="data-value">' + exit_fees_text + '</td>'));
    let total_fees = $('<tr></tr>').append($('<td class="data-name">Total fees</td>')).append(
        $('<td class="data-value">' + total_fees_text + '</td>'));

    let close_exec_price = $('<tr></tr>').append($('<td class="data-name">Last close exec price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade.stats['close-exec-price']) + '</td>'));

    tbody.append(best_price);
    tbody.append(worst_price);

    tbody.append(entry_order_type);
    tbody.append(first_realized_entry_dt);
    tbody.append(first_realized_exit_dt);
    tbody.append(last_realized_entry_dt);
    tbody.append(last_realized_exit_dt);

    tbody.append(entry_fees);
    tbody.append(exit_fees);
    tbody.append(total_fees);

    tbody.append(close_exec_price);

    $('#trade_details').modal({'show': true, 'backdrop': true});
}

function on_details_historical_trade(elt) {
    let key = retrieve_trade_key(elt);
    let table = $('#trade_details_table');
    let tbody = table.find('tbody').empty();

    let trade = window.historical_trades[key];
    if (!trade) {
        return;
    }

    let market_id = trade['market-id'];

    let app = $('<tr></tr>').append($('<td class="data-name">Strategy</td>')).append(
        $('<td class="data-value">' + trade['app-name'] + ' / ' + trade['app-id'] + '</td>'));
    let id = $('<tr></tr>').append($('<td class="data-name">Identifier</td>')).append(
        $('<td class="data-value">' + trade.id + '</td>'));
    let lmarket_id = $('<tr></tr>').append($('<td class="data-name">Market</td>')).append(
        $('<td class="data-value"><span class="badge">' + trade['market-id'] + '</span></td>'));
    let symbol = $('<tr></tr>').append($('<td class="data-name">Symbol</td>')).append(
        $('<td class="data-value"><span class="badge">' + trade.symbol + '</span></td>'));
    let version = $('<tr></tr>').append($('<td class="data-name">Version</td>')).append(
        $('<td class="data-value">' + trade.version + '</td>'));
    let trade_type = $('<tr></tr>').append($('<td class="data-name">Type</td>')).append(
        $('<td class="data-value">' + trade.trade + '</td>'));
    let timestamp = $('<tr></tr>').append($('<td class="data-name">Last update</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.timestamp) + '</td>'));
    let timeframe = $('<tr></tr>').append($('<td class="data-name">Timeframe</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade.timeframe) + '</td>'));
    let entry_timeout = $('<tr></tr>').append($('<td class="data-name">Entry timeout</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade['entry-timeout']) + '</td>'));
    let expiry = $('<tr></tr>').append($('<td class="data-name">Expiry</td>')).append(
        $('<td class="data-value">' + timeframe_to_str(trade.expiry) + '</td>'));
    let user_trade = $('<tr></tr>').append($('<td class="data-name">User trade</td>')).append(
        $('<td class="data-value">' + trade['is-user-trade'] + '</td>'));

    let direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value">' + trade.direction + '</td>'));

    if (trade.direction == "long") {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="trade-direction fa trade-long fa-arrow-up"></span></td>'));
    } else if (trade.direction == "short") {
       direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="trade-direction fa trade-short fa-arrow-dn"></span></td>'));
    }

    let state = $('<tr></tr>').append($('<td class="data-name">State</td>')).append(
        $('<td class="data-value">' + trade.state + '</td>'));
    let label = $('<tr></tr>').append($('<td class="data-name">Label</td>')).append(
        $('<td class="data-value">' + trade.label + '</td>'));
    let order_price = $('<tr></tr>').append($('<td class="data-name">Order price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['order-price']) + '</td>'));
    let order_qty = $('<tr></tr>').append($('<td class="data-name">Order qty</td>')).append(
        $('<td class="data-value">' + trade['order-qty'] + '</td>'));
    let stop_loss_price = $('<tr></tr>').append($('<td class="data-name">Take-Profit</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['stop-loss-price']) + '</td>'));
    let take_profit_price = $('<tr></tr>').append($('<td class="data-name">Stop-Loss</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['take-profit-price']) + '</td>'));

    let avg_entry_price = $('<tr></tr>').append($('<td class="data-name">Avg entry price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['avg-entry-price']) + '</td>'));
    let avg_exit_price = $('<tr></tr>').append($('<td class="data-name">Avg exit price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, trade['avg-exit-price']) + '</td>'));

    let entry_open_time = $('<tr></tr>').append($('<td class="data-name">Entry open at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade['entry-open-time']) + '</td>'));
    let exit_open_time = $('<tr></tr>').append($('<td class="data-name">Exit open at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade['exit-open-time']) + '</td>'));

    let filled_entry_qty = $('<tr></tr>').append($('<td class="data-name">Filled entry qty</td>')).append(
        $('<td class="data-value">' + trade['filled-entry-qty'] + '</td>'));
    let filled_exit_qty = $('<tr></tr>').append($('<td class="data-name">Filled exit qty</td>')).append(
        $('<td class="data-value">' + trade['filled-exit-qty'] + '</td>'));

    let profit_loss_pct_text = '-';
    let trade_pnl_text= '-';
    let entry_fees_text = '-';
    let exit_fees_text = '-';
    let total_fees_text = '-';
    if (parseFloat(trade['filled-entry-qty']) > 0.0) {
        profit_loss_pct_text = trade['profit-loss-pct'] + '%';
        trade_pnl_text = format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency'];
        entry_fees_text = format_quote_price(market_id, trade.stats['entry-fees']) + trade.stats['profit-loss-currency'];
        total_fees_text = format_quote_price(market_id, trade.stats['entry-fees'] + trade.stats['exit-fees']) +
            trade.stats['profit-loss-currency'] + ' (' + trade.stats['fees-pct'] + '%)';
        symbol.find('span').addClass('badge-info');
        lmarket_id.find('span').addClass('badge-info');
    } else {
        symbol.find('span').addClass('badge-secondary');
        lmarket_id.find('span').addClass('badge-secondary');
    }

    if (parseFloat(trade['filled-exit-qty']) > 0.0) {
        exit_fees_text = format_quote_price(market_id, trade.stats['exit-fees']) + trade.stats['profit-loss-currency'];
    }

    let profit_loss_pct = $('<tr></tr>').append($('<td class="data-name">Profit/Loss</td>')).append(
        $('<td class="data-value">' + profit_loss_pct_text + '</td>'));

    let trade_pnl = $('<tr></tr>').append($('<td class="data-name">Realized PNL</td>')).append(
        $('<td class="data-value">' + trade_pnl_text + '</td>'));

    if (trade.stats['profit-loss'] > 0.0) {
        profit_loss_pct.find('td:last').css('color', 'green');
        trade_pnl.find('td:last').css('color', 'green');
    } else if (trade.stats['profit-loss'] < 0.0) {
       profit_loss_pct.find('td:last').css('color', 'red');
       trade_pnl.find('td:last').css('color', 'red');
    }

    tbody.append(app);
    tbody.append(id);
    tbody.append(lmarket_id);
    tbody.append(symbol);
    tbody.append(version);
    tbody.append(trade_type);
    tbody.append(timestamp);
    tbody.append(entry_timeout);
    tbody.append(expiry);
    tbody.append(user_trade);
    tbody.append(direction);
    tbody.append(state);
    tbody.append(label);
    tbody.append(order_price);
    tbody.append(order_qty);
    tbody.append(stop_loss_price);
    tbody.append(take_profit_price);
    tbody.append(avg_entry_price);
    tbody.append(avg_exit_price);
    tbody.append(entry_open_time);
    tbody.append(exit_open_time);
    tbody.append(filled_entry_qty);
    tbody.append(filled_exit_qty);
    tbody.append(profit_loss_pct);
    tbody.append(trade_pnl);

    let best_price_text = '-';
    let worst_price_text = '-';

    if (trade.stats['best-datetime']) {
        best_price_text = format_price(market_id, trade.stats['best-price']) + ' on ' +
            timestamp_to_datetime_str(trade.stats['best-datetime']);
        worst_price_text = format_price(market_id, trade.stats['worst-price']) + ' on ' +
            timestamp_to_datetime_str(trade.stats['worst-datetime']);
    }

    let best_price = $('<tr></tr>').append($('<td class="data-name">Best price</td>')).append(
        $('<td class="data-value">' + best_price_text + '</td>'));
    let worst_price = $('<tr></tr>').append($('<td class="data-name">Worst price</td>')).append(
        $('<td class="data-value">' + worst_price_text + '</td>'));

    let entry_order_type = $('<tr></tr>').append($('<td class="data-name">Entry order type</td>')).append(
        $('<td class="data-value">' + trade.stats['entry-order-type'] + '</td>'));

    let first_realized_entry_dt = $('<tr></tr>').append($('<td class="data-name">First realized entry at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['first-realized-entry-datetime']) + '</td>'));
    let first_realized_exit_dt = $('<tr></tr>').append($('<td class="data-name">First realized exit at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['first-realized-exit-datetime']) + '</td>'));

    let last_realized_entry_dt = $('<tr></tr>').append($('<td class="data-name">Last realized entry at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['last-realized-entry-datetime']) + '</td>'));
    let last_realized_exit_dt = $('<tr></tr>').append($('<td class="data-name">Last realized exit at</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(trade.stats['last-realized-exit-datetime']) + '</td>'));

    let entry_fees = $('<tr></tr>').append($('<td class="data-name">Entry fees</td>')).append(
        $('<td class="data-value">' + entry_fees_text + '</td>'));
    let exit_fees = $('<tr></tr>').append($('<td class="data-name">Exit fees</td>')).append(
        $('<td class="data-value">' + exit_fees_text + '</td>'));
    let total_fees = $('<tr></tr>').append($('<td class="data-name">Total fees</td>')).append(
        $('<td class="data-value">' + total_fees_text + '</td>'));

    let exit_reason = $('<tr></tr>').append($('<td class="data-name">Exit reason</td>')).append(
        $('<td class="data-value">' + trade.stats['exit-reason'] + '</td>'));

    tbody.append(best_price);
    tbody.append(worst_price);

    tbody.append(entry_order_type);
    tbody.append(first_realized_entry_dt);
    tbody.append(first_realized_exit_dt);
    tbody.append(last_realized_entry_dt);
    tbody.append(last_realized_exit_dt);

    tbody.append(entry_fees);
    tbody.append(exit_fees);
    tbody.append(total_fees);

    tbody.append(exit_reason);

    $('#trade_details').modal({'show': true, 'backdrop': true});
}

/////////////////////
// Helpers Scripts //
/////////////////////

/**
 * Check any trades and match with assets quantities
 * If some asset quantity remains then try to detect the average entry price and number of missing slot
 * using an average slot size based on last data.
 * Report console log analysis results.
 * @param currency str Currency asset to use.
 * @param currency_prefix str In some case an additional currency prefix to match between asset symbol and market ids.
 * @return object Per asset an object with details.
 */
function check_trades(currency="EUR", currency_prefix="Z", asset_prefix="X") {
    let diffs = {};
    let totals = {};
    let avg_slot_size = 0;
    let avg_slot_count = 0;

    for (let trade in window.actives_trades) {
        let at = window.actives_trades[trade];
        let market_id = at['market-id'];

        if (!market_id.endsWith(currency)) {
            continue
        };

        let asset_name = market_id.slice(0, -currency.length);

        if (asset_name.length > 3 && asset_name[asset_name.length-1] == currency_prefix) {
            asset_name = asset_name.slice(0, -1);
        }

        if (!(asset_name in window.account_balances)) {
            if ((asset_prefix + asset_name) in window.account_balances) {
                asset_name = asset_prefix + asset_name;
            }
        }

        if (!(asset_name in totals)) {
            totals[asset_name] = {'ids': [], 'actives': 0, 'quantity': 0.0};
        }

        totals[asset_name].ids.push(at.id);
        totals[asset_name].quantity += parseFloat(at['filled-entry-qty']) - parseFloat(at['filled-exit-qty']);

        if (parseFloat(at['avg-entry-price']) > 0) {
            avg_slot_size += parseFloat(at['order-qty']) * parseFloat(at['avg-entry-price']);
            avg_slot_count += 1;

            totals[asset_name].actives += 1;
        }
    }

    if (avg_slot_count > 0) {
       avg_slot_size /= avg_slot_count;
    }

    let total_missing_trades = 0;

    // make diff
    for (let asset_name in window.account_balances) {
        let asset = window.account_balances[asset_name];

        if (asset.type == 'asset') {
            if (asset_name in totals) {
                let total = totals[asset_name];
                let diff = asset.total - total.quantity;
                let avg_qty = total.quantity / total.actives;
                let threshold = avg_qty * 0.1;

                if (diff > 0 && total.quantity > 0.0) {
                    if (diff > threshold) {
                        let count = diff / avg_qty;
                        let est_ep = (Math.round(count) * avg_slot_size) / diff;

                        diffs[asset_name] = {
                            'asset-quantity': asset.total,
                            'trades-quantity': total.quantity,
                            'trades-count': total.ids.length,
                            'active-trades-count': total.actives,
                            'pending-trades-count': total.ids.length - total.actives,
                            'quantity-diff': diff,
                            'num-missing-slots': Math.round(count),
                            'approximation': count - Math.round(count),
                            'approximation-pct': ((count - Math.round(count)) * 100).toFixed(2),
                            'estimated-entry-price': est_ep
                        };

                        total_missing_trades += Math.round(count)
                    }
                }
            } else if (CURRENCIES.indexOf(asset_name) < 0) {
                // not a currency 
                let diff = asset.total;
                let market = null;

                if ((asset_name + currency) in window.markets) {
                    market = window.markets[asset_name + currency];
                } else if ((asset_prefix+asset_name + currency_prefix+currency) in window.markets) {
                    market = window.markets[asset_prefix+asset_name + currency_prefix+currency];
                }

                let avg_qty =  avg_slot_size / (market ? market.mid : 1.0);
                let threshold = avg_qty * 0.1;

                if (diff > 0) {
                    if (diff > threshold) {
                        let count = diff / avg_qty;
                        let est_ep = (Math.round(count) * avg_slot_size) / diff;

                        diffs[asset_name] = {
                            'asset-quantity': asset.total,
                            'trades-quantity': 0,
                            'trades-count': 0,
                            'active-trades-count': 0,
                            'pending-trades-count': 0,
                            'quantity-diff': diff,
                            'num-missing-slots': Math.round(count),
                            'approximation': count - Math.round(count),
                            'approximation-pct': ((count - Math.round(count)) * 100).toFixed(2),
                            'estimated-entry-price': est_ep
                        };

                        total_missing_trades += Math.round(count)
                    }
                }
            }
        }
    }

    console.log(diffs);
    console.log("Total missing actives trades (approximation) : " + total_missing_trades);
    console.log("Average trade size : " + avg_slot_size);
    console.log("Approximating notional of missing trades : " + total_missing_trades * avg_slot_size);

    return diffs;
}

/**
 *
 */
function compute_all_avg_entry_price() {
    for (let mid in window.markets) {
        let market = window.markets[mid];

        let qty = 0.0;
        let price = 0.0;
        let tp_price = 0.0;
        let tp_pct = 0.0;

        for (let t in actives_trades) {
            let trade = actives_trades[t];

            if (trade['market-id'] != mid) {
                continue;
            }

            let trade_qty = parseFloat(trade['filled-entry-qty']);

            if (trade_qty <= 0) {
                continue;
            }

            qty += trade_qty;
            price += parseFloat(trade['avg-entry-price']) * trade_qty;
            tp_price += parseFloat(trade['take-profit-price']) * trade_qty;
        }

        if (qty > 0 && price > 0) {
            price /= qty;
            tp_price /= qty;
            tp_pct = (tp_price - price) / price * 100;
            price_pct = (market['mid'] - price) / price * 100;

            console.log(market['symbol'] + ' / avg-entry-price=' + format_quote_price(mid, price) +
                '(' + price_pct.toFixed(2) + '%) / qty=' + qty + ' / tp=' + format_quote_price(mid, tp_price) +
                '(' + tp_pct.toFixed(2) + '%)');
        }
    }
}

/**
 *
 */
function trade_validation(asset, currency, zero_count) {
    let qty = 0.0;
    zero_count = zero_count || false;

    for (var t in window.actives_trades) {
        let trade = window.actives_trades[t];
        let trade_qty = parseFloat(trade['filled-entry-qty']);

        if (!zero_count && trade_qty <= 0) {
            continue;
        }

        if (trade['market-id'] == asset+currency) {
            console.log(trade['id'] + ' EP@' + trade['avg-entry-price'] + ' date=' + trade['stats']['first-realized-entry-datetime'],
                ' TP@' + trade['take-profit-price']);
            // console.log(trade)
            qty += trade_qty;
        }
    }

    console.log('qty=' + qty + ' / asset=' + window.account_balances[asset]['total']);
}
