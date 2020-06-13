function on_order_long(elt) {
    let symbol = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[symbol];

    if (symbol && market) {
        // how to retrieve the context name; timeframe and expiry ?
        let profile = market.profiles[retrieve_profile(trader_id)];

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
        } else {
            stop_loss = window.methods[retrieve_stop_loss_method(trader_id)].distance;
        }

        if (take_profit_price_mode == "price") {
            take_profit = retrieve_take_profit_price(trader_id);
        } else {
            take_profit = window.methods[retrieve_take_profit_method(trader_id)].distance;
        }
        
        let entry_price_mode = window.entry_methods[retrieve_entry_method(trader_id)].type;

        if (entry_price_mode == "limit") {
            limit_price = retrieve_entry_price(trader_id);
            method = "limit"
        } else if (entry_price_mode == "market") {
            method = "market"
        } else if (entry_price_mode == "best1") {
            // @todo
        } else if (entry_price_mode == "best2") {
            // @todo
        } else if (entry_price_mode == "bid1") {
            // @todo
        } else if (entry_price_mode == "bid2") {
            // @todo
        } else if (entry_price_mode == "ask1") {
            // @todo
        } else if (entry_price_mode == "ask2") {
            // @todo
        }

        quantity_rate = retrieve_quantity_rate(trader_id) * 0.01 * retrieve_quantity_factor(trader_id);

        let timeframe = profile['timeframe'];
        let entry_timeout = null;  // @todo
        let leverage = 1;
        let context = profile['context'];

        let data = {
            'command': 'trade-entry',
            'appliance': market['appliance'],
            'market-id': market['market-id'],
            'direction': 1,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'entry-timeout': entry_timeout,
            'leverage': leverage
        };

        if (context) {
            data['context'] = context;
        }

        if (timeframe) {
            data['timeframe'] = timeframe;
        }

        $.ajax({
            type: "POST",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            // console.log(data);
            notify({'message': "Success", 'title': 'Order Long', 'type': 'success'});
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Order Long', 'type': 'error'});
            }
        });
    }
};

function on_order_short(elt) {
    let symbol = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[symbol];

    if (symbol && market) {
        // how to retrieve the context name; timeframe and expiry ?
        let profile = market.profiles[retrieve_profile(trader_id)];

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
        } else {
            stop_loss = window.methods[retrieve_stop_loss_method(trader_id)].distance;
        }

        if (take_profit_price_mode == "price") {
            take_profit = retrieve_take_profit_price(trader_id);
        } else {
            take_profit = window.methods[retrieve_take_profit_method(trader_id)].distance;
        }
        
        let entry_price_mode = window.entry_methods[retrieve_entry_method(trader_id)].type;

        if (entry_price_mode == "limit") {
            limit_price = retrieve_entry_price(trader_id);
            method = "limit"
        } else if (entry_price_mode == "market") {
            method = "market"
        } else if (entry_price_mode == "best1") {
            // @todo
        } else if (entry_price_mode == "best2") {
            // @todo
        } else if (entry_price_mode == "bid1") {
            // @todo
        } else if (entry_price_mode == "bid2") {
            // @todo
        } else if (entry_price_mode == "ask1") {
            // @todo
        } else if (entry_price_mode == "ask2") {
            // @todo
        }

        quantity_rate = retrieve_quantity_rate(trader_id) * 0.01 * retrieve_quantity_factor(trader_id);

        let timeframe = profile['timeframe'];
        let entry_timeout = null;  // @todo
        let leverage = 1;
        let context = profile['context'];

        let data = {
            'command': 'trade-entry',
            'appliance': market['appliance'],
            'market-id': market['market-id'],
            'direction': -1,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'entry-timeout': entry_timeout,
            'leverage': leverage
        };

        if (context) {
            data['context'] = context;
        }

        if (timeframe) {
            data['timeframe'] = timeframe;
        }

        $.ajax({
            type: "POST",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            notify({'message': "Success", 'title': 'Order Short', 'type': 'success'});
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
    if (parts.length != 3) {
        return false;
    }

    let appliance = parts[0];
    let symbol = parts[1];
    let trade_id = parseInt(parts[2]);

    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[symbol];

    if (symbol && market && trade_id) {
        let data = {
            'appliance': market['appliance'],
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'action': "close"
        };

        $.ajax({
            type: "DELETE",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            notify({'message': "Success", 'title': 'Order Close', 'type': 'success'});
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Order Close', 'type': 'error'});
            }
        });
    }
};

function on_reverse_trade(elt) {
    alert("todo!");
}

let on_active_trade_entry_message = function(appliance, market_id, trade_id, timestamp, value) {
    // insert into active trades
    add_active_trade(appliance, market_id, value);
};

let on_active_trade_update_message = function(appliance, market_id, trade_id, timestamp, value) {
    // update into active trades
    update_active_trade(appliance, market_id, value);
};

let on_active_trade_exit_message = function(appliance, market_id, trade_id, timestamp, value) {
    // remove from active trades
    remove_active_trade(appliance, market_id, trade_id);

    // insert to historical trades
    add_historical_trade(appliance, market_id, value);
};

//
// trades list functions
//

function on_close_all_active_trade(elt) {
    // @todo
}

function compute_price_pct(price, close, direction) {
    if (typeof(price) === "string") {
        price = parseFloat(price);
    }

    if (typeof(close) === "string") {
        close = parseFloat(close);
    }

    if (direction > 0) {
        return (close - price) / price;
    } else if (direction < 0) {
        return (price - close) / price;
    }

    return 0.0;
}

function add_active_trade(appliance_id, market_id, trade) {
    let trade_elt = $('<tr class="active-trade"></tr>');
    let key = appliance_id + ':' + market_id + ':' + trade.id;
    trade_elt.attr('trade-key', key);

    let trade_id = $('<span class="trade-id"></span>').text(trade.id);
    let trade_symbol = $('<span class="trade-symbol"></span>').text(market_id);
    let trade_direction = $('<span class="trade-direction fa"></span>')
        .addClass(trade.direction == "long" ? 'trade-long' : 'trade-short')
        .addClass(trade.direction == "long" ? 'fa-arrow-up' : 'fa-arrow-down');

    let trade_datetime = $('<span class="trade-datetime"></span>').text(timestamp_to_datetime_str(trade.timestamp*1000));
    let trade_order = $('<span class="trade-order"></span>').text(trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');
 
    let trade_entry = $('<span class="trade-entry"></span>').text(trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    trade_entry.attr('data-toggle', "tooltip");
    trade_entry.attr('data-placement', "top");

    let entry_price_rate = compute_price_pct(trade['avg-entry-price'], trade.stats['close-exec-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_entry.attr('title', (entry_price_rate * 100).toFixed(2) + '%');

    let trade_exit = $('<span class="trade-exit"></span>').text('-')
    trade_exit.attr('data-toggle', "tooltip");
    trade_exit.attr('data-placement', "top");
    trade_exit.attr('title', '-');

    let trade_context = $('<span class="trade-context"></span>')
        .text(trade['label'] ? trade['label'] + ' (' + trade['timeframe'] + ')' : trade['timeframe']);

    let trade_auto = $('<span class="trade-auto fa"></span>')
        .addClass(trade['is-user-trade'] ? 'trade-auto-no' : 'trade-auto-yes')
        .addClass(trade['is-user-trade'] ? 'fa-pause' : 'fa-play');

    let trade_percent = $('<span class="trade-percent"></span>').text("-");
    let trade_upnl = $('<span class="trade-upnl"></span>').text("-");
    let trade_fees = $('<span class="trade-fees"></span>').text("-");

    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);  // + UP/DN buttons
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'], trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);  // + UP/DN buttons
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'], trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_take_profit.attr('title', (take_profit_price_rate * 100).toFixed(2) + '%');

    let trade_close = $('<button class="trade-close btn btn-danger fa fa-close"></button>');
    let trade_reverse = $('<button class="trade-reverse btn btn-light fa fa-random"></button>');
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
    
    trade_elt.append($('<td></td>').append(trade_stop_loss));
    trade_elt.append($('<td></td>').append(trade_take_profit));
    
    trade_elt.append($('<td></td>').append(trade_close));  
    trade_elt.append($('<td></td>').append(trade_reverse));
    trade_elt.append($('<td></td>').append(trade_details));

    // append
    $('div.active-trade-list-entries tbody').append(trade_elt);

    // actions
    trade_close.on('click', on_close_trade);
    trade_details.on('click', on_details_active_trade);
    trade_reverse.on('click', on_reverse_trade);

    window.actives_trades[key] = trade;
};

function update_active_trade(appliance_id, market_id, trade) {
    let key = appliance_id + ':' + market_id + ':' + trade.id;
    let container = $('div.active-trade-list-entries tbody');
    let trade_elt = container.find('tr.active-trade[trade-key="' + key + '"]')

    let trade_order = $('<span class="trade-order"></span>').text(trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');

    let trade_entry = $('<span class="trade-entry"></span>').text(trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    trade_entry.attr('data-toggle', "tooltip");
    trade_entry.attr('data-placement', "top");

    let entry_price_rate = compute_price_pct(trade['avg-entry-price'], trade.stats['close-exec-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_entry.attr('title', (entry_price_rate * 100).toFixed(2) + '%');

    let trade_exit = $('<span class="trade-exit"></span>').text(trade['avg-exit-price'] + ' (' + trade['filled-exit-qty'] + ')');
    trade_exit.attr('data-toggle', "tooltip");
    trade_exit.attr('data-placement', "top");

    let exit_price_rate = compute_price_pct(trade['avg-exit-price'], trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_exit.attr('title', (exit_price_rate * 100).toFixed(2) + '%');

    let trade_percent = $('<span class="trade-percent"></span>').text(trade['profit-loss-pct'] +'%');   
    let trade_upnl = $('<span class="trade-upnl"></span>').text(format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency']);
    let trade_fees = $('<span class="trade-fees"></span>').text(trade.stats['entry-fees'] + trade.stats['exit-fees']);

    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);  // + UP/DN buttons
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'], trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);  // + UP/DN buttons
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'], trade['avg-entry-price'] || trade['order-price'], trade.direction == "long" ? 1 : -1);
    trade_take_profit.attr('title', (take_profit_price_rate * 100).toFixed(2) + '%');

    trade_elt.find('span.trade-order').replaceWith(trade_order);
    trade_elt.find('span.trade-entry').replaceWith(trade_entry);
    trade_elt.find('span.trade-exit').replaceWith(trade_exit);
    trade_elt.find('span.trade-percent').replaceWith(trade_percent);
    trade_elt.find('span.trade-upnl').replaceWith(trade_upnl);
    trade_elt.find('span.trade-fees').replaceWith(trade_fees);
    trade_elt.find('span.trade-stop-loss').replaceWith(trade_stop_loss);
    trade_elt.find('span.trade-take-profit').replaceWith(trade_take_profit);

    window.history[key] = trade;
};

function remove_active_trade(appliance_id, market_id, trade_id) {
    let key = appliance_id + ':' + market_id + ':' + trade_id;
    let container = $('div.active-trade-list-entries tbody');

    container.find('tr.active-trade[trade-key="' + key + '"]').remove();
    delete window.actives_trades[key];
};

function format_quote_price(symbol, price) {
    let market = window.markets[symbol];
    if (market) {
        return price.toFixed(market['notional-limits'][3] || 2);
    }

    return 0.0;
}

function add_historical_trade(appliance_id, market_id, trade) {
    let trade_elt = $('<tr class="historical-trade"></tr>');
    let key = appliance_id + ':' + market_id + ':' + trade.id;
    trade_elt.attr('trade-key', key);

    let trade_id = $('<span class="trade-id"></span>').text(trade.id);
    let trade_symbol = $('<span class="trade-symbol"></span>').text(market_id);
    let trade_direction = $('<span class="trade-direction fa"></span>')
        .addClass(trade.direction == "long" ? 'trade-long' : 'trade-short')
        .addClass(trade.direction == "long" ? 'fa-arrow-up' : 'fa-arrow-down');

    let trade_datetime = $('<span class="trade-datetime"></span>').text(timestamp_to_datetime_str(trade.timestamp*1000));
    let trade_order = $('<span class="trade-order"></span>').text(trade['stats']['entry-order-type'] + ' @' + trade['order-price'] + ' (' + trade['order-qty'] + ')');
 
    let trade_entry = $('<span class="trade-entry"></span>').text(trade['avg-entry-price'] + ' (' + trade['filled-entry-qty'] + ')');
    let trade_exit = $('<span class="trade-entry"></span>').text(trade['avg-exit-price'] + ' (' + trade['filled-exit-qty'] + ')');

    let trade_context = $('<span class="trade-context"></span>')
        .text(trade['label'] ? trade['label'] + ' (' + trade['timeframe'] + ')' : trade['timeframe']);

    let trade_percent = $('<span class="trade-percent"></span>').text(trade['profit-loss-pct'] +'%');   
    let trade_pnl = $('<span class="trade-pnl"></span>').text(format_quote_price(market_id, trade.stats['profit-loss']) + trade.stats['profit-loss-currency']);
    let trade_fees = $('<span class="trade-fees"></span>').text(trade.stats['entry-fees'] + trade.stats['exit-fees']);

    let trade_stop_loss = $('<span class="trade-stop-loss"></span>').text(trade['stop-loss-price']);
    trade_stop_loss.attr('data-toggle', "tooltip");
    trade_stop_loss.attr('data-placement', "top");

    let stop_loss_price_rate = compute_price_pct(trade['stop-loss-price'], trade['avg-entry-price'], trade.direction == "long" ? 1 : -1);
    trade_stop_loss.attr('title', (stop_loss_price_rate * 100).toFixed(2) + '%');

    let trade_take_profit = $('<span class="trade-take-profit"></span>').text(trade['take-profit-price']);
    trade_take_profit.attr('data-toggle', "tooltip");
    trade_take_profit.attr('data-placement', "top");

    let take_profit_price_rate = compute_price_pct(trade['take-profit-price'], trade['avg-entry-price'], trade.direction == "long" ? 1 : -1);
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
};

function on_close_active_trade(elt) {
    // @todo
}

function on_reduce_active_trade_stop_loss(elt) {
    // @todo
}

function on_increase_active_trade_stop_loss(elt) {
    // @todo
}

function on_reduce_active_trade_take_profit(elt) {
    // @todo
}

function on_increase_active_trade_take_profit(elt) {
    // @todo
}

function on_modify_active_trade_take_profit(elt) {
    // @todo
}

function on_modify_active_trade_take_profit(elt) {
    // @todo
}

function on_add_active_trade_dynamic_stop_loss(elt) {
    // @todo
}

function on_details_historical_trade(elt) {
    // @todo
}

function on_details_active_trade(elt) {
    // @todo
}
