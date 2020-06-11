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
            notify({'message': data.reason, 'title': 'Order Long', 'type': 'error'});
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
            notify({'message': "Success", 'title': 'Order Long', 'type': 'success'});
        })
        .fail(function(data) {
            notify({'message': data.reason, 'title': 'Order Long', 'type': 'error'});
        });
    }
};

function on_close_trade(elt) {
    let symbol = retrieve_symbol(elt);
    let trade_id = retrieve_trade_id(elt);
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[symbol];

    if (symbol && market && trader_id) {
        let data = {
            'appliance': market['appliance'],
            'market-id': market['market-id'],
            'trade-id': trade_id,
            'action': "close"
        };

        $.ajax({
            type: "DELETE",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            notify({'message': "Success", 'title': 'Order Close', 'type': 'success'});
        })
        .fail(function(data) {
            notify({'message': data.reason, 'title': 'Order Close', 'type': 'error'});
        });
    }
};

let on_trade_entry_message = function(appliance, market_id, trade_id, timestamp, value) {

};

let on_trade_update_message = function(appliance, market_id, trade_id, timestamp, value) {

};

let on_trade_exit_message = function(appliance, market_id, trade_id, timestamp, value) {

};