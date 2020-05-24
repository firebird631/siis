$(window).ready(function() {
    let appliance = {
        'name': null,
        'protocol': 'http://',
        'host': '127.0.0.1',
        'port': 6339,
        'api-key': null,
        'auth-token': null
    }

    // how to input the api-key ?

    let searchParams = new URLSearchParams(window.location.search);
    if (searchParams.has('appliance')) {
        appliance['name'] = searchParams.get('appliance');
    }
    if (searchParams.has('host')) {
        appliance['host'] = searchParams.get('host');
    }
    if (searchParams.has('port')) {
        appliance['port'] = parseInt(searchParams.get('port'));
    }

    function base_url() {
        return appliance['protocol'] + appliance['host'] + ':' + appliance['port'];
    };

    let broker = {
        'name': 'binancefutures.com',
    }

    // help to find the related market on trading-view
    let broker_to_tv = {
        'binance.com': ['BINANCE', ''],
        'binancefutures.com': ['BINANCE', 'PERP'],
        'ig.com': ['FXCM' , ''],
    }

    // map a symbol to a market on trading-view for some specials case, like indices
    let symbol_to_tv = {
        // @todo fill DAX, SPX, DJI, NAS100, NAS500, EUROSTOCK, LSE, NIKKEY, HK30, HK50, CAC40, FTSE, BE30
    }

    let markets = {
        'BTCUSDT': {
            'market-id': 'BTCUSDT',
            'symbol': 'BTCUSDT',
            'one-pip-means': 1.0,
            'value-per-pip': 1.0,
        },
        'ETHUSDT': {

        },
        'BNBUSDT': {

        },
    };

    let profiles = {
        'Scalp XS': {
            'take-profit': 'percent-0.15',
            'stop-loss': 'percent-0.15',
        },
        'Scalp SM': {
            'take-profit': 'percent-0.45',
            'stop-loss': 'percent-0.45',
        },
        'Scalp MD': {
            'take-profit': 'percent-0.75',
            'stop-loss': 'percent-0.75',
        },
        'Scalp LG': {
            'take-profit': 'percent-1.0',
            'stop-loss':'percent-1.0',
        },
        'Scalp XL': {
            'take-profit':'percent-1.5',
            'stop-loss':'percent-1.0',
        },
        'FX Scalp XS': {
            'take-profit': 'pip-3',
            'stop-loss': 'pip-3',
        },
        'FX Scalp SM': {
            'take-profit': 'pip-7',
            'stop-loss': 'pip-5',
        },
        'FX Scalp MD': {
            'take-profit': 'pip-12',
            'stop-loss': 'pip-6',
        },
        'FX Scalp LG': {
            'take-profit': 'pip-12',
            'stop-loss': 'pip-8',
        },
        'FX Scalp XL': {
            'take-profit': 'pip-30',
            'stop-loss': 'pip-15',
        },
    };

    let methods = {
        'percent-0.05': {
            'label': '0.05%',
            'distance': 0.05,
            'type': 'percent',
        },
        'percent-0.10': {
            'label': '0.10%',
            'distance': 0.10,
            'type': 'percent',
        },
        'percent-0.15': {
            'label': '0.15%',
            'distance': 0.15,
            'type': 'percent',
        },
        'percent-0.25': {
            'label': '0.25%',
            'distance': 0.25,
            'type': 'percent',
        },
        'percent-0.35': {
            'label': '0.35%',
            'distance': 0.35,
            'type': 'percent',
        },
        'percent-0.45': {
            'label': '0.45%',
            'distance': 0.45,
            'type': 'percent',
        },
        'percent-0.5': {
            'label': '0.5%',
            'distance': 0.5,
            'type': 'percent',
        },
        'percent-0.75': {
            'label': '0.75%',
            'distance': 0.75,
            'type': 'percent',
        },
        'percent-1.0': {
            'label': '1.0%',
            'distance': 1.0,
            'type': 'percent',
        },
        'percent-1.5': {
            'label': '1.5%',
            'distance': 1.5,
            'type': 'percent',
        },
        'pip-3': {
            'label': '3pips',
            'distance': 3,
            'type': 'pip',
        },
        'pip-5': {
            'label': '5pips',
            'distance': 5,
            'type': 'pip',
        },
        'pip-6': {
            'label': '6pips',
            'distance': 6,
            'type': 'pip',
        },
        'pip-7': {
            'label': '7pips',
            'distance': 7,
            'type': 'pip',
        },
        'pip-8': {
            'label': '8pips',
            'distance': 8,
            'type': 'pip',
        },
        'pip-10': {
            'label': '10pips',
            'distance': 10,
            'type': 'pip',
        },
        'pip-12': {
            'label': '12pips',
            'distance': 12,
            'type': 'pip',
        },
        'pip-15': {
            'label': '15pips',
            'distance': 15,
            'type': 'pip',
        },
        'pip-20': {
            'label': '20pips',
            'distance': 20,
            'type': 'pip',
        },
        'pip-30': {
            'label': '30pips',
            'distance': 30,
            'type': 'pip',
        }
    }

    let entry_methods = {
        'market': {
            'label': 'Market',
            'type': 'market'
        },
        'last': {
            'label': 'Last',
            'type': 'last'
        },
        'bid1': {
            'label': 'Bid 1',
            'type': 'bid1'
        },
        'ask1': {
            'label': 'Ask 1',
            'type': 'ask1'
        },
        'bid2': {
            'label': 'Bid 2',
            'type': 'bid2'
        },
        'ask2': {
            'label': 'Ask 2',
            'type': 'ask2'
        },
    }

    // @todo fetch markets
    // @todo fetch details
    // @todo fetch options

    // @todo regular curr trades and trades history (later WS)
    // @todo chart view

    function add_symbols(id, to) {
        let select = $('<select class="markets" name="market-id"></select>');
        select.attr('trader-id', id);

        for (market in markets) {
            select.append($('<option value="' + market +'">' + market + '</>'));
        }

        to.append(select);

        select.selectpicker({'width': '150px'});
    };

    function add_profiles(id, to) {
        let select = $('<select class="profiles" name="profile-id"></select>');
        select.attr('trader-id', id);

        for (profile in profiles) {
            select.append($('<option value="' + profile +'">' + profile + '</>'));
        }

        to.append(select);

        select.selectpicker({'width': '150px'});

        select.on('change', function(e) {
            on_change_profile(e);
        });
    };

    function add_take_profit_price(id, to) {
        let input = $('<input type="number" class="take-profit-price" name="take-profit-price" placeholder="Take-Profit">');
        input.attr('trader-id', id);

        to.append(input);
    };

    function add_take_profit_methods(id, to) {
        let select = $('<select class="take-profit-method" name="take-profit-method"></select>');
        select.attr('trader-id', id);

        for (method in methods) {
            select.append($('<option value="' + method +'">' + methods[method].label + '</>'));
        }

        to.append(select);

        select.selectpicker({'width': '150px'});
    };

    function add_entry_price(id, to) {
        let input = $('<input type="number" class="entry-price" name="entry-price" placeholder="Entry-Price">');
        input.attr('trader-id', id);

        to.append(input);
    };

    function add_entry_price_methods(id, to) {
        let select = $('<select class="entry-price-method" name="entry-price-method"></select>');
        select.attr('trader-id', id);

        for (method in entry_methods) {
            select.append($('<option value="' + method +'">' + entry_methods[method].label + '</>'));
        }

        to.append(select);

        select.selectpicker({'width': '150px'});
    };

    function add_stop_loss_price(id, to) {
        let input = $('<input type="number" class="stop-loss-price" name="stop-loss-price" placeholder="Stop-Loss">');
        input.attr('trader-id', id);

        to.append(input);
    };

    function add_stop_loss_methods(id, to) {
        let select = $('<select class="stop-loss-method" name="stop-loss-method"></select>');
        select.attr('trader-id', id);

        for (method in methods) {
            select.append($('<option value="' + method +'">' + methods[method].label + '</>'));
        }

        to.append(select);

        select.selectpicker({'width': '150px'});
    };

    function add_quantity_slider(id, to) {
        let slider = $('<input type="range" class="quantity" name="quantity">').css('width', '165px');
        let factor = $('<select class="quantity-factor" name="quantity-factor"></select>');
        let value = $('<span class="quantity-value" name="quantity-value">100%</span>');

        slider.attr('trader-id', id);
        factor.attr('trader-id', id);

        for (let i = 1; i <= 5; ++i) {
            factor.append($('<option value="' + i +'">x' + i + '</>'));
        }

        to.append(slider);
        to.append(value);
        to.append(factor);

        slider.slider({
            'min': 1,
            'max': 4,
            'step': 1,
        }).on('change', function(elt) {
            value.html($(this).val() * 25.0 + "%");
        });

        factor.selectpicker({'width': '75px'});
    };

    function retrieve_symbol(elt) {
        let trader_id = $(elt.target).attr('trader-id');
        return $('.markets[trader-id="' + trader_id + '"]').val();
    }

    function add_long_short_actions(id, to) {
        let tv_btn = $('<button class="btn btn-secondary trading-view-action" name="trading-view-action"><span class="fa fa-link"></span>&nbsp;TV</button>');
        let long_btn = $('<button class="btn btn-success long-action" name="long-action">Long</button>');
        let short_btn = $('<button class="btn btn-danger short-action" name="short-action">Short</button>');
        let chart_btn = $('<button class="btn btn-secondary siis-chart-action" name="siis-chart-action"><span class="fa fa-bar-chart"></span></button>');

        long_btn.attr('trader-id', id);
        short_btn.attr('trader-id', id);
        tv_btn.attr('trader-id', id);
        chart_btn.attr('trader-id', id);

        to.append(tv_btn);
        to.append(long_btn);
        to.append(short_btn);
        to.append(chart_btn);

        long_btn.on('click', function(elt) {
            on_order_long(elt);
        });

        short_btn.on('click', function(elt) {
            on_order_short(elt);
        });

        tv_btn.on('click', function(elt) {
            open_trading_view(elt);
        });

        chart_btn.on('click', function(elt) {
            alert("TODO !:")
        });
    };

    $("div.trader").each(function(i, elt) {
        let trader_row1 = $('<div class="row trader-row1 trader-row"></div>');
        let trader_row2 = $('<div class="row trader-row2 trader-row"></div>');
        let trader_row3 = $('<div class="row trader-row3 trader-row"></div>');
        let trader_row4 = $('<div class="row trader-row4 trader-row"></div>');
        let trader_row5 = $('<div class="row trader-row5 trader-row"></div>');
        let trader_row6 = $('<div class="row trader-row6 trader-row"></div>');

        let id = "trader_" + i;

        add_symbols(id, trader_row1);
        add_profiles(id, trader_row1);

        add_take_profit_price(id, trader_row2);
        add_take_profit_methods(id, trader_row2);

        add_entry_price(id, trader_row3);
        add_entry_price_methods(id, trader_row3);

        add_stop_loss_price(id, trader_row4);
        add_stop_loss_methods(id, trader_row4);

        add_quantity_slider(id, trader_row5);

        add_long_short_actions(id, trader_row6);

        $(elt).append(trader_row1);
        $(elt).append(trader_row2);
        $(elt).append(trader_row3);
        $(elt).append(trader_row4);
        $(elt).append(trader_row5);
        $(elt).append(trader_row6);
    });

    function add_active_trade(appliance_id, market_id, trade) {
        // @todo
    };

    function remove_active_trade(appliance_id, market_id, local_id) {
        // @todo
    };

    function add_historical_trade(appliance_id, market_id, trade) {
        // @todo
    };

    function open_trading_view(elt) {
        let symbol = retrieve_symbol(elt);

        if (broker['name'] in broker_to_tv) {
            if (symbol in symbol_to_tv) {
                symbol = symbol_to_tv[symbol];
            }

            window.open('https://fr.tradingview.com/chart?symbol=' + broker_to_tv[broker['name']][0] + '%3A' + symbol + broker_to_tv[broker['name']][1]);
        }
    };

    function on_change_profile(elt) {
        let value = $(elt.target).val();

        if (value in profiles) {
            let profile = profiles[value];
            let trader_id = $(elt.target).attr('trader-id');

            let tpm = $('.take-profit-method[trader-id="' + trader_id +'"]');
            let epm = $('.entry-price-method[trader-id="' + trader_id +'"]');
            let slm = $('.stop-loss-method[trader-id="' + trader_id +'"]');

            tpm.selectpicker('val', profile['take-profit']);
            slm.selectpicker('val', profile['stop-loss']);
        };
    };

    function on_order_long(elt) {
        let symbol = retrieve_symbol(elt);
        let endpoint = "trade/create";
        let url = base_url() + '/' + endpoint;

        if (symbol) {
            let data = {}

            $.ajax({
                type: "POST",
                url: url,
                data: JSON.stringify(data),
                dataType: 'json',
                contentType: 'application/json'
            })
            .done(function() {
                alert( "second success" );
            })
            .fail(function() {
                alert( "error" );
            });
        }
    };

    function on_order_short(elt) {
        let symbol = retrieve_symbol(elt);
        let endpoint = "trade/create";
        let url = base_url() + '/' + endpoint;

        if (symbol) {
            let data = {}

            $.ajax({
                type: "POST",
                url: url,
                data: JSON.stringify(data),
                dataType: 'json',
                contentType: 'application/json'
            })
            .done(function() {
                alert( "second success" );
            })
            .fail(function() {
                alert( "error" );
            });
        }
    };

    function on_change_entry_price(elt) {
        let symbol = retrieve_symbol(elt);

        // @todo
    }

    function on_change_stop_loss_price(elt) {
        let symbol = retrieve_symbol(elt);

        // @todo
    }

    function on_change_take_profit_price(elt) {
        let symbol = retrieve_symbol(elt);

        // @todo
    }

    function setup_auth_data(data) {
        data['auth-token'] = appliance['auth-token'];
    }

    function get_auth_token() {
        let endpoint = "auth";
        let url = base_url() + '/' + endpoint;

        let data = {
            'api-key': appliance['api-key'],
        }

        $.ajax({
            type: "POST",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(result) {
            appliance['auth-token'] = result['auth-token'];
        })
        .fail(function() {
            alert("Unable to obtain an auth-token !");
        });
    };

    // get an initial auth-token
    get_auth_token();
});
