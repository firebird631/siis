$(window).ready(function() {
    window.server = {
        'protocol': 'http:',
        'host': null,
        'port': null,
        'ws-port': null,
        'auth-token': null,
        'ws-auth-token': null,
    };

    window.ws = null;

    let searchParams = new URLSearchParams(window.location.search);

    if (searchParams.has('host')) {
        server['host'] = searchParams.get('host');
    }
    if (searchParams.has('port')) {
        server['port'] = parseInt(searchParams.get('port'));
    }
    if (searchParams.has('ws-port')) {
        server['ws-port'] = parseInt(searchParams.get('ws-port'));
    }

    window.broker = {
        'name': 'binancefutures.com',
    };

    // help to find the related market on trading-view
    window.broker_to_tv = {
        'binance.com': ['BINANCE', ''],
        'binancefutures.com': ['BINANCE', 'PERP'],
        'ig.com': ['OANDA' , ''],
    };

    // map a symbol to a market on trading-view for some specials case, like indices
    window.symbol_to_tv = {
        'IX.D.DAX.IFMM.IP': ['OANDA', 'DE30EUR'],
        'IX.D.DOW.IFE.IP': ['OANDA', 'US30USD'],
        'IX.D.NASDAQ.IFE.IP': ['OANDA', 'NAS100USD'],
        'IX.D.SPTRD.IFE.IP': ['OANDA', 'SPX500USD'],

        'S.D.USDCHF.MINI.IP': ['OANDA', 'USDCHF'],
        'CS.D.USDJPY.MINI.IP': ['OANDA', 'USDJPY'],
        'CS.D.AUDNZD.MINI.IP': ['OANDA', 'AUDNZD'],
        'CS.D.EURCAD.MINI.IP': ['OANDA', 'EURCAD'],
        'CS.D.EURCHF.MINI.IP': ['OANDA', 'EURCHF'],
        'CS.D.EURGBP.MINI.IP': ['OANDA', 'EURGBP'],
        'CS.D.EURJPY.MINI.IP': ['OANDA', 'EURJPY'],
        'CS.D.EURUSD.MINI.IP': ['OANDA', 'EURUSD'],
        'CS.D.GBPUSD.MINI.IP': ['OANDA', 'GBPUSD'],

        'CS.D.CFEGOLD.CFE.IP': ['OANDA', 'XAUUSD'],
    };

    window.markets = {
        'BTCUSDT': {
            'market-id': 'BTCUSDT',
            'symbol': 'BTCUSDT',
            'one-pip-means': 1.0,
            'value-per-pip': 1.0,
        },
    };

    window.tickers = {
        // bid
        // ofr
        // vol24 base
        // vol24 quote
    };

    window.strategy = {};
    window.actives_trades = {};
    window.historical_trades = {};

    window.default_profiles = {
        'price': {
            'label': 'Price',
            'take-profit': 'price',
            'stop-loss': 'price',
            'context': null,
            'timeframe': null
        },
        'scalp-xs': {
            'label': 'Scalp XS',
            'take-profit': 'percent-0.15',
            'stop-loss': 'percent-0.15',
            'context': null,
            'timeframe': null
        },
        'scalp-sm': {
            'label': 'Scalp SM',
            'take-profit': 'percent-0.45',
            'stop-loss': 'percent-0.45',
            'context': null,
            'timeframe': null
        },
        'scalp-md': {
            'label': 'Scalp MD',
            'take-profit': 'percent-0.75',
            'stop-loss': 'percent-0.75',
            'context': null,
            'timeframe': null
        },
        'scalp-lg': {
            'label': 'Scalp LG',
            'take-profit': 'percent-1.0',
            'stop-loss':'percent-1.0',
            'context': null,
            'timeframe': null
        },
        'scalp-xl': {
            'label': 'Scalp XL',
            'take-profit':'percent-1.5',
            'stop-loss':'percent-1.0',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-xs': {
            'label': 'FX Scalp XS',
            'take-profit': 'pip-3',
            'stop-loss': 'pip-3',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-sm': {
            'label': 'FX Scalp SM',
            'take-profit': 'pip-7',
            'stop-loss': 'pip-5',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-md': {
            'label': 'FX Scalp MD',
            'take-profit': 'pip-12',
            'stop-loss': 'pip-6',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-lg': {
            'label': 'FX Scalp LG',
            'take-profit': 'pip-12',
            'stop-loss': 'pip-8',
            'context': null,
            'timeframe': null
        },
        'fx-Scalp-xl': {
            'label': 'FX Scalp XL',
            'take-profit': 'pip-30',
            'stop-loss': 'pip-15',
            'context': null,
            'timeframe': null
        },
    };

    window.methods = {
        'price': {
            'label': 'Price',
            'distance': 0.0,
            'type': 'price',
        },
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
        'percent-0.50': {
            'label': '0.50%',
            'distance': 0.5,
            'type': 'percent',
        },
        'percent-0.75': {
            'label': '0.75%',
            'distance': 0.75,
            'type': 'percent',
        },
        'percent-1.00': {
            'label': '1.00%',
            'distance': 1.0,
            'type': 'percent',
        },
        'percent-1.50': {
            'label': '1.50%',
            'distance': 1.5,
            'type': 'percent',
        },
        'percent-2.00': {
            'label': '2.00%',
            'distance': 2.0,
            'type': 'percent',
        },
        'percent-2.50': {
            'label': '2.50%',
            'distance': 2.5,
            'type': 'percent',
        },
        'percent-3.00': {
            'label': '3.00%',
            'distance': 3.0,
            'type': 'percent',
        },
        'percent-4.00': {
            'label': '4.00%',
            'distance': 4.0,
            'type': 'percent',
        },
        'percent-5.00': {
            'label': '5.00%',
            'distance': 5.0,
            'type': 'percent',
        },
        'percent-10.00': {
            'label': '10.00%',
            'distance': 10.0,
            'type': 'percent',
        },
        'pip-5': {
            'label': '5pips',
            'distance': 5,
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
        'pip-25': {
            'label': '25pips',
            'distance': 25,
            'type': 'pip',
        },
        'pip-30': {
            'label': '30pips',
            'distance': 30,
            'type': 'pip',
        },
        'pip-40': {
            'label': '40pips',
            'distance': 40,
            'type': 'pip',
        },
        'pip-50': {
            'label': '50pips',
            'distance': 50,
            'type': 'pip',
        },
        'pip-75': {
            'label': '75pips',
            'distance': 75,
            'type': 'pip',
        },
        'pip-100': {
            'label': '100pips',
            'distance': 100,
            'type': 'pip',
        },
    }

    window.entry_methods = {
        'limit': {
            'label': 'Limit',
            'type': 'limit'
        },
        'last': {
            'label': 'Last',
            'type': 'market'
        },
        'best1': {
            'label': 'Best 1',
            'type': 'best1'
        },
        'best2': {
            'label': 'Best 2',
            'type': 'best2'
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

    //
    // trade list
    //

    $("a.menu-btn").on('click', function(e) {
        $("div.list-entries").hide();
        $('div.' + $(this).attr('view')).show();

        $('a.menu-btn').css('background', 'initial');
        $(this).css('background', 'chocolate');
    });

    $('#authentification').modal({'show': true, 'backdrop': false});
    $('#list_active_trades').css('background', 'chocolate');

    $('#authentification').on('shown.bs.modal', function () {
        $('#identifier').focus();
        let identifier = getCookie('identifier');

        if (identifier) {
            $('#identifier').val(identifier);
        }
    })  

    $('#connect').on('click', function(e) {
        authenticate();
    });

    $('#identifier').keypress(function(e) {
        if (e.which == '13') {
            authenticate();
        }
    });

    $('#password').keypress(function(e) {
        if (e.which == '13') {
            authenticate();
        }
    });

    $('#apply_modify_trade_stop_loss').on('click', function(e) {
        on_apply_modify_active_trade_stop_loss();

        $('#apply_modify_trade_stop_loss').modal('hide');
    });

    $('#apply_modify_trade_take_profit').on('click', function(e) {
        on_apply_modify_active_trade_take_profit();

        $('#apply_modify_trade_take_profit').modal('hide');
    });

    $('#apply_trade_add_dynamic_stop_loss').on('click', function(e) {
        on_add_active_trade_dynamic_stop_loss();
    });

    //
    // session init
    //

    function setup_auth_data(data) {
        data['auth-token'] = server['auth-token'];
    }

    function get_auth_token(api_key) {
        let endpoint = "auth";
        let url = base_url() + '/' + endpoint;

        let data = {
            'api-key': api_key
        }

        $.ajax({
            type: "POST",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(result) {
            if (result['error'] || !result['auth-token']) {
                notify({'message': "Rejected authentication", 'type': 'error'});
                return;
            }

            server['auth-token'] = result['auth-token'];
            server['ws-auth-token'] = result['ws-auth-token'];

            if (server['ws-port'] != null) {
                start_ws();
            }

            fetch_strategy();

            $('#authentification').modal('hide');

            $("div.active-trade-list-entries ul").empty();
            $("div.historical-trade-list-entries ul").empty();

            notify({'message': "Connected", 'type': 'success'});

            // store api-key into a cookie
            setCookie('identifier', api_key, 15);
        })
        .fail(function() {
            notify({'message': "Unable to obtain an auth-token !", 'type': 'error'});
        });
    };

    function login(identifier, password) {
        let endpoint = "auth";
        let url = base_url() + '/' + endpoint;

        let data = {
            'identifier': identifier,
            'password': password
        }

        let res = 0;

        $.ajax({
            type: "POST",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(result) {
            server['auth-token'] = result['auth-token'];

            if (server['ws-port'] != null) {
                start_ws();
            }

            fetch_strategy();

            $('#authentification').modal('hide');

            // store identifier into a cookie
            setCookie('identifier', identifier, 15);
        })
        .fail(function() {
            alert("Unable to obtain an auth-token !");
        });
    };


    function start_ws() {
        if (ws != null) {
            console.log("Close previous WS");
            ws.close()
            ws = null;
        }

        ws = new WebSocket("ws://" + server['host'] + ":" + server['ws-port'] +
                "?ws-auth-token=" + server['ws-auth-token'] +
                '&auth-token=' + server['auth-token']);

        ws.onopen = function(event) {
            console.log("WS opened");
        };

        ws.onclose = function(event) {
            console.log("WS closed by peer !");
        };

        ws.onmessage = function (event) {
            on_ws_message(JSON.parse(event.data));
        }
    }

    // global function to setup data and to get an initial auth-token
    siis_connect = function(api_key, host, port, ws_port=6340) {
        server['host'] = host;
        server['port'] = port;
        server['ws-port'] = ws_port;

        return get_auth_token(api_key);
    }

    siis_login = function(identifier, password, host, port, ws_port=6340) {
        server['host'] = host;
        server['port'] = port;
        server['ws-port'] = ws_port;

        return login(identifier, password);
    }

    server['protocol'] = window.location.protocol;

    simple_connect = function(api_key) {
        return siis_connect(api_key, window.location.hostname, parseInt(window.location.port), ws_port=parseInt(window.location.port)+1);
    }
});

//
// global
//

function setCookie(cname, cvalue, exdays) {
    let d = new Date();
    d.setTime(d.getTime() + (exdays*24*60*60*1000));
    let expires = "expires="+ d.toUTCString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
    let name = cname + "=";
    let decodedCookie = decodeURIComponent(document.cookie);
    let ca = decodedCookie.split(';');
    for(let i = 0; i <ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

function authenticate() {
    let identifier = $('#identifier').val();
    let password = $('#password').val();

    if (identifier && password) {
        // by login and password
        siis_login(identifier, password, window.location.hostname, parseInt(window.location.port), ws_port=parseInt(window.location.port)+1);
    } else if (identifier) {
        // by API key
        siis_connect(identifier, window.location.hostname, parseInt(window.location.port), ws_port=parseInt(window.location.port)+1);
    }
}

function setup_traders() {
    $("div.trader").each(function(i, elt) {
        let trader_row1 = $('<div class="row trader-row1 trader-row"></div>');
        let trader_row2 = $('<div class="row trader-row2 trader-row"></div>');
        let trader_row3 = $('<div class="row trader-row3 trader-row"></div>');
        let trader_row4 = $('<div class="row trader-row4 trader-row"></div>');
        let trader_row5 = $('<div class="row trader-row5 trader-row"></div>');
        let trader_row6 = $('<div class="row trader-row6 trader-row"></div>');

        let id = "trader_" + i;
        let market = null;
        let profiles = window.default_profiles;
        let market_id = null;

        if (i < Object.keys(window.markets).length) {
            market_id = Object.keys(window.markets)[i];
        } else if (Object.keys(window.markets).length > 0) {
            market_id = Object.keys(window.markets)[0];
        }

        if (market_id != null) {
            market = window.markets[market_id];
            profiles = market['profiles'];
        }

        let symbol_select = add_symbols(id, trader_row1);
        let profile_select = add_profiles(id, trader_row1, profiles);

        add_take_profit_price(id, trader_row2);
        let take_profit_select = add_take_profit_methods(id, trader_row2);

        add_entry_price(id, trader_row3);
        add_entry_price_methods(id, trader_row3);

        add_stop_loss_price(id, trader_row4);
        let stop_loss_select = add_stop_loss_methods(id, trader_row4);

        add_quantity_slider(id, trader_row5);

        add_long_short_actions(id, trader_row6);

        $(elt).append(trader_row1);
        $(elt).append(trader_row2);
        $(elt).append(trader_row3);
        $(elt).append(trader_row4);
        $(elt).append(trader_row5);
        $(elt).append(trader_row6);

        symbol_select.selectpicker('change', market_id).change();
        profile_select.selectpicker('change', 'scalp-xs').change();
        stop_loss_select.selectpicker('change', stop_loss_select.val()).change();
        take_profit_select.selectpicker('change', take_profit_select.val()).change();
    });
}

function base_url() {
    return server['protocol'] + "//" + server['host'] + ':' + server['port'] + "/api/v1";
};

function fetch_strategy() {
    let endpoint = "strategy";
    let url = base_url() + '/' + endpoint;

    $.ajax({
        type: "GET",
        url: url,
        headers: {
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.markets = {};
        window.strategy = {};
        window.broker = result['broker'];

        window.strategy = {
            'name': result['strategy']
        };

        for (let market_id in result['markets']) {
            let market = result['markets'][market_id];

            window.markets[market_id] = {
                'strategy': market['strategy'],
                'market-id': market['market-id'],
                'symbol': market['symbol'],
                'market-id': market['market-id'],
                'value-per-pip': market['value-per-pip'],
                'price-limits': market['price-limits'],  // array 4 float
                'notional-limits': market['notional-limits'],  // array 4 float
                'size-limits': market['size-limits'],  // array 4 float
                'bid': market['bid'],
                'ofr': market['ofr'],
                'mid': market['mid'],
                'spread': market['spread'],
                'profiles': {}
            };

            // append the default profiles
            for (let def_profile_id in window.default_profiles) {
                window.markets[market_id].profiles[def_profile_id] = window.default_profiles[def_profile_id];
            }

            // and the strategy profiles
            for (let profile_id in market['profiles']) {
                let profile = market['profiles'][profile_id];
                let take_profit_method = null;
                let stop_loss_method = null;

                if (profile['take-profit']) {
                    take_profit_method = "";

                    if (profile['take-profit']['distance-type'] == 'percent') {
                        take_profit_method = 'percent-' + profile['take-profit']['distance'].toFixed(2);
                    } else {
                        take_profit_method = 'pip-' + profile['take-profit']['distance'];
                    }

                    if (!(take_profit_method in window.methods)) {
                        let label = ""

                        if (profile['take-profit']['distance-type'] == 'percent') {
                            label = profile['take-profit']['distance'].toFixed(2) + '%';
                        } else {
                            label = profile['take-profit']['distance'] + 'pips';
                        }

                        window.methods[take_profit_method] = {
                            'label': label,
                            'distance': profile['take-profit']['distance'],
                            'type': profile['take-profit']['distance-type']
                        };
                    }
                }

                if (profile['stop-loss']) {
                    if (profile['stop-loss']['distance-type'] == 'percent') {
                        stop_loss_method = 'percent-' + profile['stop-loss']['distance'].toFixed(2);
                    } else {
                        stop_loss_method = 'pip-' + profile['stop-loss']['distance'];
                    }

                    if (!(stop_loss_method in window.methods)) {
                        let label = "";

                        if (profile['stop-loss']['distance-type'] == 'percent') {
                            label = profile['stop-loss']['distance'].toFixed(2) + '%';
                        } else {
                            label = profile['stop-loss']['distance'] + 'pips';
                        }

                        window.methods[stop_loss_method] = {
                            'label': label,
                            'distance': profile['stop-loss']['distance'],
                            'type': profile['stop-loss']['distance-type']
                        };
                    }
                }

                window.markets[market_id].profiles[profile_id] = {
                    'label': profile['profile-id'],
                    'entry': profile['profile-id'],
                    'take-profit': take_profit_method,
                    'stop-loss': stop_loss_method
                };
            }
        }

        setup_traders();
        fetch_trades();
    })
    .fail(function() {
        alert("Unable to obtains markets list info !");
    });
}

function fetch_trades() {
    let endpoint = "strategy/trade";
    let url = base_url() + '/' + endpoint;

    let params = {}

    $.ajax({
        type: "GET",
        url: url,
        data: params,
        headers: {
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.actives_trades = {};

        let trades = result['data'];

        for (let i = 0; i < trades.length; ++i) {
            let trade = trades[i];
            window.actives_trades[trade.id] = trade;

            // initial add
            add_active_trade(trade.symbol, trade);
        }
    })
    .fail(function() {
        alert("Unable to obtains actives trades !");
    });
}

function timestamp_to_time_str(timestamp) {
    let datetime = new Date(timestamp);
    return datetime.toLocaleTimeString("en-GB");
}

function timestamp_to_date_str(timestamp) {
    let datetime = new Date(timestamp);
    return datetime.toLocaleDateString("en-GB");
}

function timestamp_to_datetime_str(timestamp) {
    let datetime = new Date(timestamp);
    return datetime.toLocaleDateString("en-GB") + " " + datetime.toLocaleTimeString("fr-FR");
}

//
// traders functions
//

function add_symbols(id, to) {
    let select = $('<select class="markets" name="market-id"></select>');
    select.attr('trader-id', id);

    for (market in markets) {
        select.append($('<option value="' + market +'">' + market + '</>'));
    }

    to.append(select);

    select.selectpicker({'width': '165px', 'size': '10'});

    return select;
};

function add_profiles(id, to, profiles) {
    let select = $('<select class="profiles" name="profile-id"></select>');
    select.attr('trader-id', id);

    for (profile_id in profiles) {
        select.append($('<option value="' + profile_id +'">' + profiles[profile_id].label + '</>'));
    }

    to.append(select);

    select.selectpicker({'width': '170px', 'size': '10'});

    select.on('change', function(e) {
        on_change_profile(e);
    });

    return select;
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

    select.selectpicker({'width': '170px', 'size': '10'});

    select.on('change', function(e) {
        on_change_take_profit_method(e);
    });

    return select;
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

    select.selectpicker({'width': '170px', 'size': '10'});

    select.on('change', function(e) {
        on_change_entry_method(e);
    });

    select.selectpicker("val", "limit");

    return select;
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

    select.selectpicker({'width': '170px', 'size': '10'});

    select.on('change', function(e) {
        on_change_stop_loss_method(e);
    });

    return select;
};

function add_quantity_slider(id, to) {
    let slider = $('<input type="range" class="quantity" name="quantity">').css('width', '200px');
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
        'min': 0,
        'max': 100,
        'step': 5,
        'value': 100,
    }).on('change', function(elt) {
        value.html($(this).val() + "%");
    });

    factor.selectpicker({'width': '75px', 'size': '10'});
};

function retrieve_symbol(elt) {
    let trader_id = $(elt.target).attr('trader-id');
    return $('.markets[trader-id="' + trader_id + '"]').val();
}

function retrieve_trade_key(elt) {
    let tr = $(elt.target).parent().parent();
    if (tr.length) {
        return tr.attr('trade-key');
    }

    return "";
}

function retrieve_trader_id(elt) {
    return $(elt.target).attr('trader-id');
}

function retrieve_profile(trader_id) {
    return $('select.profiles[trader-id="' + trader_id + '"]').val();
}

function retrieve_stop_loss_price(trader_id) {
    let val = $('input.stop-loss-price[trader-id="' + trader_id + '"]').val();
    return val ? parseFloat(val) : 0.0;
}

function retrieve_take_profit_price(trader_id) {
    let val =$('input.take-profit-price[trader-id="' + trader_id + '"]').val();
    return val ? parseFloat(val) : 0.0;
}

function retrieve_stop_loss_method(trader_id) {
    return $('select.stop-loss-method[trader-id="' + trader_id + '"]').val();
}

function retrieve_take_profit_method(trader_id) {
    return $('select.take-profit-method[trader-id="' + trader_id + '"]').val();
}

function retrieve_entry_method(trader_id) {
    return $('select.entry-price-method[trader-id="' + trader_id + '"]').val();
}

function retrieve_entry_price(trader_id) {
    let val = $('input.entry-price[trader-id="' + trader_id + '"]').val();
    return val ? parseFloat(val) : 0.0;
}

function retrieve_quantity_rate(trader_id) {
    return parseFloat($('input.quantity[trader-id="' + trader_id + '"]').val());
}

function retrieve_quantity_factor(trader_id) {
    return parseInt($('select.quantity-factor[trader-id="' + trader_id + '"]').val());
}

function retrieve_trade_id(elt) {
    let trade_id = $(elt.target).attr('active-trade-id');
    return trade_id ? parseInt(trade_id) : -1;
}

function add_long_short_actions(id, to) {
    let tv_btn = $('<button class="btn btn-secondary trading-view-action" name="trading-view-action"><span class="fa fa-link"></span>&nbsp;TV</button>');
    let long_btn = $('<button class="btn btn-success long-action" name="long-action">Long</button>');
    let short_btn = $('<button class="btn btn-danger short-action" name="short-action">Short</button>');
    let auto_btn = $('<button class="btn btn-secondary siis-chart-auto" name="siis-chart-auto"><span class="fa fa-play"></span></button>');
    let chart_btn = $('<button class="btn btn-secondary siis-chart-action" name="siis-chart-action"><span class="fa fa-bar-chart"></span></button>');

    long_btn.attr('trader-id', id);
    short_btn.attr('trader-id', id);
    tv_btn.attr('trader-id', id);
    auto_btn.attr('trader-id', id);
    chart_btn.attr('trader-id', id);

    to.append(tv_btn);
    to.append(long_btn);
    to.append(short_btn);
    to.append(auto_btn);
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

    auto_btn.on('click', function(elt) {
        toggle_auto(elt);
    });

    chart_btn.on('click', function(elt) {
        alert("TODO !:")
    });
};

function toggle_auto(elt) {
    let symbol = retrieve_symbol(elt);

    let endpoint = "strategy/trader";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[symbol];

    let data = {
        'market-id': market['market-id'],
        'activity': 'toggle',
    }

    $.ajax({
        type: "POST",
        url: url,
        data: JSON.stringify(data),
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        if (result['error'] || !result['auth-token']) {
            notify({'message': "Rejected authentication", 'type': 'error'});
            return;
        }

        $(elt).removeClass('fa-play')
            .removeClass('fa-pause')
            .addClass(result['activity'] ? 'fa-play' : 'fa-pause');

        notify({'message': "Toggle auto-trade", 'type': 'success'});
    })
    .fail(function() {
        notify({'message': "Unable toggle auto-trade status !", 'type': 'error'});
    });
}

function open_trading_view(elt) {
    let symbol = retrieve_symbol(elt);

    if (window.broker['name'] in window.broker_to_tv) {
        if (symbol in window.symbol_to_tv) {
            // mapped symbol
            let stv = window.symbol_to_tv[symbol];

            window.open('https://fr.tradingview.com/chart?symbol=' + stv[0] + '%3A' + stv[1]);
        } else {
            // direct mapping with suffix
            let btv = window.broker_to_tv[window.broker['name']];

            window.open('https://fr.tradingview.com/chart?symbol=' + btv[0] + '%3A' + symbol + btv[1]);
        }
    }
};

function on_change_profile(elt) {
    let value = $(elt.target).val();
    let market = window.markets[retrieve_symbol(elt)];

    if (value in market.profiles) {
        let profile = market.profiles[value];
        let trader_id = $(elt.target).attr('trader-id');

        let tpm = $('.take-profit-method[trader-id="' + trader_id +'"]');
        let epm = $('.entry-price-method[trader-id="' + trader_id +'"]');
        let slm = $('.stop-loss-method[trader-id="' + trader_id +'"]');

        tpm.selectpicker('val', profile['take-profit']).change();
        slm.selectpicker('val', profile['stop-loss']).change();
    };
};

function on_change_entry_method(elt) {
    let symbol = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let entry_method = retrieve_entry_method(trader_id);

    if (entry_method == "limit") {
        let ep = $('input.entry-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", false);
    } else {
        let ep = $('input.entry-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", true);
    }
}

function on_change_entry_price(elt) {
    let symbol = retrieve_symbol(elt);

    // @todo change entry price in case of limit or trigger(limit) order
}

function on_change_stop_loss_method(elt) {
    let symbol = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let entry_method = retrieve_stop_loss_method(trader_id);

    if (entry_method == "price") {
        let ep = $('input.stop-loss-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", false);
    } else {
        let ep = $('input.stop-loss-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", true);
    }
}

function on_change_stop_loss_price(elt) {
    let symbol = retrieve_symbol(elt);

    // @todo
}

function on_change_take_profit_method(elt) {
    let symbol = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let entry_method = retrieve_take_profit_method(trader_id);

    if (entry_method == "price") {
        let ep = $('input.take-profit-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", false);
    } else {
        let ep = $('input.take-profit-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", true);
    }
}

function on_change_take_profit_price(elt) {
    let symbol = retrieve_symbol(elt);

    // @todo
}
