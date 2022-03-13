$(window).ready(function() {
    CURRENCIES = {
        'EUR': 2,
        'ZEUR': 2,
        'USD': 2,
        'ZUSD': 2,
        'CAD': 2,
        'ZCAD': 2,
        'JPY': 2,
        'ZJPY': 2,
        'CHF': 2,
        'ZCHF': 2,
        'XBT': 8,
        'XXBT': 8,
        'ETH': 8,
        'XETH': 8,
    };

    CURRENCIES_ALIAS = {
        'ZEUR': ['EUR', '€'],
        'ZUSD': ['USD', '$'],
        'ZCHF': ['CHF', 'CHF'],
        'ZJPY': ['JPY', '¥'],
        'ZCAD': ['CAD','$CA'],
        'XXBT': ['BTC','₿'],
        'XETH': ['ETH','Ξ'],
    };

    window.server = {
        'protocol': 'http:',
        'host': null,
        'port': null,
        'ws-port': null,
        'auth-token': null,
        'ws-auth-token': null,
        'session': "",
        'delay': 1000,
        'retry': false,
        'ws': false,
        'connected': false,
        'permissions': [
            "trader-balance-view",
            "strategy-view",
            "strategy-open-trade",
            "strategy-clean-trade",
            "strategy-close-trade",
            "strategy-modify-trade",
            "strategy-trader"
        ],
        'updates': {
            'strategy': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'trader': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'watcher1': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'watcher2': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'watcher3': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'watcher4': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0},
            'watcher5': {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0}
        }
    };

    window.ws = null;

    let searchParams = new URLSearchParams(window.location.search);

    if (searchParams.has('host')) {
        window.server['host'] = searchParams.get('host');
    }
    if (searchParams.has('port')) {
        window.server['port'] = parseInt(searchParams.get('port'));
    }
    if (searchParams.has('ws-port')) {
        window.server['ws-port'] = parseInt(searchParams.get('ws-port'));
    }

    window.broker = {
        'name': 'binancefutures.com',
    };

    // help to find the related market on trading-view
    window.broker_to_tv = {
        'binance.com': ['BINANCE', ''],
        'binancefutures.com': ['BINANCE', 'PERP'],
        'ig.com': ['OANDA' , ''],
        'kraken.com': ['KRAKEN', ''],
    };

    // map a symbol to a market on trading-view for some specials case, like indices
    window.symbol_to_tv = {
        // ig.com mapping
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

        // kraken.com mapping
        'XLTCZEUR': ['KRAKEN', 'LTCEUR'],
        'XLTCZUSD': ['KRAKEN', 'LTCUSD'],
        'XETCZEUR': ['KRAKEN', 'ETCEUR'],
        'XETCZUSD': ['KRAKEN', 'ETCUSD'],
        'XETHZEUR': ['KRAKEN', 'ETHEUR'],
        'XETHZUSD': ['KRAKEN', 'ETHUSD'],
        'XMLNZEUR': ['KRAKEN', 'MLNEUR'],
        'XMLNZUSD': ['KRAKEN', 'MLNUSD'],
        'XREPZEUR': ['KRAKEN', 'REPEUR'],
        'XREPZUSD': ['KRAKEN', 'REPUSD'],
        'XXDGZEUR': ['KRAKEN', 'XDGEUR'],
        'XXDGZUSD': ['KRAKEN', 'XDGUSD'],
        'XXLMZEUR': ['KRAKEN', 'XLMEUR'],
        'XXLMZUSD': ['KRAKEN', 'XLMUSD'],
        'XXMRZEUR': ['KRAKEN', 'XMREUR'],
        'XXMRZUSD': ['KRAKEN', 'XMRUSD'],
        'XXRPZEUR': ['KRAKEN', 'XRPEUR'],
        'XXRPZUSD': ['KRAKEN', 'XRPUSD'],
        'XZECZEUR': ['KRAKEN', 'ZECEUR'],
        'XZECZUSD': ['KRAKEN', 'ZECUSD'],
        'XXBTZEUR': ['KRAKEN', 'BTCEUR'],
        'XXBTZUSD': ['KRAKEN', 'BTCUSD'],
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
        // ask
        // spread
        // vol24 (base)
        // vol24quote
        // depth
    };

    window.strategy = {};
    window.actives_trades = {};
    window.historical_trades = {};
    window.pending_trades = [];
    window.active_alerts = {};
    window.alerts = {};
    window.signals = {};
    window.regions = {};
    window.charts = {};
    window.account_balances = {};

    window.stats = {
        'upnl': 0.0,
        'upnlpct': 0.0,
        'rpnl': 0.0,
        'rpnlpct': 0.0
    };

    window.audio = {
        'enabled': true,
        'alt': false,
    }

    window.default_profiles = {
        'price': {
            'label': 'Price',
            'take-profit': 'price',
            'stop-loss': 'price',
            'context': null,
            'timeframe': null
        },
        'invest': {
            'label': 'Invest',
            'take-profit': 'price',
            'stop-loss': 'none',
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
            'take-profit': 'percent-1.00',
            'stop-loss':'percent-1.00',
            'context': null,
            'timeframe': null
        },
        'scalp-xl': {
            'label': 'Scalp XL',
            'take-profit':'percent-1.50',
            'stop-loss':'percent-1.00',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-xs': {
            'label': 'FX Scalp XS',
            'take-profit': 'pip-5',
            'stop-loss': 'pip-5',
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
            'take-profit': 'pip-10',
            'stop-loss': 'pip-8',
            'context': null,
            'timeframe': null
        },
        'fx-scalp-lg': {
            'label': 'FX Scalp LG',
            'take-profit': 'pip-15',
            'stop-loss': 'pip-10',
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
        'none': {
            'label': 'None',
            'distance': 0.0,
            'type': 'none',
        },
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
        'percent-20.00': {
            'label': '20.00%',
            'distance': 20.0,
            'type': 'percent',
        },
        'percent-50.00': {
            'label': '50.00%',
            'distance': 50.0,
            'type': 'percent',
        },
        'percent-100.00': {
            'label': '100.00%',
            'distance': 100.0,
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
            'label': 'Market',
            'type': 'market'
        },
        'best+1': {
            'label': 'Best +1',
            'type': 'best+1'
        },
        // 'best+2': {
        //     'label': 'Best +2',
        //     'type': 'best+2'
        // },
        'best-1': {
            'label': 'Best -1',
            'type': 'best-1'
        },
        // 'best-2': {
        //     'label': 'Best -2',
        //     'type': 'best-2'
        // },
        'percent-0.05': {
            'label': '0.05%',
            'distance': 0.05,
            'type': 'limit-percent',
        },
        'percent-0.10': {
            'label': '0.10%',
            'distance': 0.10,
            'type': 'limit-percent',
        },
        'percent-0.15': {
            'label': '0.15%',
            'distance': 0.15,
            'type': 'limit-percent',
        },
        'percent-0.25': {
            'label': '0.25%',
            'distance': 0.25,
            'type': 'limit-percent',
        },
        'percent-0.35': {
            'label': '0.35%',
            'distance': 0.35,
            'type': 'limit-percent',
        },
        'percent-0.45': {
            'label': '0.45%',
            'distance': 0.45,
            'type': 'limit-percent',
        },
        'percent-0.50': {
            'label': '0.50%',
            'distance': 0.5,
            'type': 'limit-percent',
        },
        'percent-0.75': {
            'label': '0.75%',
            'distance': 0.75,
            'type': 'limit-percent',
        },
        'percent-1.00': {
            'label': '1.00%',
            'distance': 1.0,
            'type': 'limit-percent',
        },
        'percent-1.50': {
            'label': '1.50%',
            'distance': 1.5,
            'type': 'limit-percent',
        },
        'percent-2.00': {
            'label': '2.00%',
            'distance': 2.0,
            'type': 'limit-percent',
        },
        'percent-2.50': {
            'label': '2.50%',
            'distance': 2.5,
            'type': 'limit-percent',
        },
        'percent-3.00': {
            'label': '3.00%',
            'distance': 3.0,
            'type': 'limit-percent',
        },
        'percent-4.00': {
            'label': '4.00%',
            'distance': 4.0,
            'type': 'limit-percent',
        },
        'percent-5.00': {
            'label': '5.00%',
            'distance': 5.0,
            'type': 'limit-percent',
        },
        'percent-10.00': {
            'label': '10.00%',
            'distance': 10.0,
            'type': 'limit-percent',
        },
        'percent-20.00': {
            'label': '20.00%',
            'distance': 20.0,
            'type': 'limit-percent',
        },
        'percent-50.00': {
            'label': '50.00%',
            'distance': 50.0,
            'type': 'limit-percent',
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

    $('#authentication').modal({'show': true, 'backdrop': false});
    $('#list_active_trades').css('background', 'chocolate');

    $('#list_performances').on('click', function(e) {
        if (server.permissions.indexOf("trader-balance-view") != -1) {
            on_update_performances();
        }
    });

    $('#authentication').on('shown.bs.modal', function () {
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

    $('#apply_trade_add_step_stop_loss').on('click', function(e) {
        on_add_active_trade_step_stop_loss();
    });

    $('#modified_stop_loss_range').slider({
        'min': 0,
        'max': 100,
        'step': 1,
        'value': 50,
    }).on('change', function(elt) {
        on_change_stop_loss_step();
    });

    $('#modified_stop_loss_type').selectpicker({'width': '75px', 'size': '10'
    }).on('change', function(elt) {
        $('#modified_stop_loss_range').slider('setValue', 50);
        on_change_stop_loss_step(); 
    });

    $('#modified_take_profit_range').slider({
        'min': 0,
        'max': 100,
        'step': 1,
        'value': 50,
    }).on('change', function(elt) {
        on_change_take_profit_step();
    });

    $('#modified_take_profit_type').selectpicker({'width': '75px', 'size': '10'
    }).on('change', function(elt) {
        $('#modified_take_profit_range').slider('setValue', 50);
        on_change_take_profit_step(); 
    });

    $('#trade_list_sizer').dblclick(function(e) {
        let elt = $('div.trade-list');
        if (elt.attr('view-mode') == 'maximized') {
            restore_trade_list_view();
        } else {
            maximize_trade_list_view();
        }
    });

    $('#toggle_trades_status').on('click', function(elt) {
        $('#trades_status').toggle();
    });

    $('#toggle_perf_status').on('click', function(elt) {
        $('#perf_status').toggle();
    });

    //
    // session init
    //

    function setup_auth_data(data) {
        data['auth-token'] = window.server['auth-token'];
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
            contentType: 'application/json',
            headers: {
                'TWISTED_SESSION': "",
            },
        })
        .done(function(result, textStatus, xhr) {
            if (result['error'] || !result['auth-token']) {
                notify({'message': "Rejected authentication", 'type': 'error'});
                return;
            }

            window.server['auth-token'] = result['auth-token'];
            window.server['ws-auth-token'] = result['ws-auth-token'];
            window.server['session'] = result['session'];

            if (result['permissions']) {
                window.server['permissions'] = result['permissions'];
            }

            if (window.server['ws-port'] != null) {
                start_ws();
            }

            window.server['connected'] = true;
            window.server['retry'] = false;
            window.server['delay'] = 0;

            fetch_status();

            if (server.permissions.indexOf("strategy-view") != -1) {
                fetch_strategy();
            }

            $('#authentication').modal('hide');

            $("div.active-trade-list-entries ul").empty();
            $("div.historical-trade-list-entries ul").empty();

            notify({'message': "Connected", 'type': 'success'});
            set_conn_state(1);

            // store api-key into a cookie
            setCookie('identifier', api_key, 15);

            audio_notify('entry');
        })
        .fail(function() {
            window.server['connected'] = false;
            window.server['retry'] = true;

            if (window.server['delay'] == 0) {
                window.server['delay'] = 1000;
            } else if (window.server['delay'] == 1000) {
                window.server['delay'] = 5000;
            } else if (window.server['delay'] == 5000) {
                window.server['delay'] = 10000;
            } else if (window.server['delay'] == 10000) {
                window.server['delay'] = 15000;
            }

            notify({'message': "Unable to obtain an auth-token !", 'type': 'error'});
            set_conn_state(-1);

            // @todo reconnect
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
            contentType: 'application/json',
            headers: {
                'TWISTED_SESSION': "",
            },
        })
        .done(function(result) {
            if (result['error'] || !result['auth-token']) {
                notify({'message': "Rejected authentication", 'type': 'error'});
                return;
            }

            window.server['auth-token'] = result['auth-token'];
            window.server['ws-auth-token'] = result['ws-auth-token'];
            window.server['session'] = result['session'];

            if (result['permissions']) {
                window.server['permissions'] = result['permissions'];
            }

            if (window.server['ws-port'] != null) {
                start_ws();
            }

            window.server['connected'] = true;
            window.server['retry'] = false;
            window.server['delay'] = 0;

            fetch_status();

            if (server.permissions.indexOf("strategy-view") != -1) {
                fetch_strategy();
            }

            $('#authentication').modal('hide');

            $("div.active-trade-list-entries ul").empty();
            $("div.historical-trade-list-entries ul").empty();

            notify({'message': "Connected", 'type': 'success'});
            set_conn_state(1);

            // store identifier into a cookie
            setCookie('identifier', identifier, 15);

            audio_notify('entry');
        })
        .fail(function() {
            window.server['connected'] = false;
            window.server['retry'] = true;

            if (window.server['delay'] == 0) {
                window.server['delay'] = 1000;
            } else if (window.server['delay'] == 1000) {
                window.server['delay'] = 5000;
            } else if (window.server['delay'] == 5000) {
                window.server['delay'] = 10000;
            } else if (window.server['delay'] == 10000) {
                window.server['delay'] = 15000;
            }

            notify({'message': "Unable to obtain an auth-token !", 'title': 'Authentication"', 'type': 'error'});
            set_conn_state(-1);

            // @todo reconnect
        });
    };

    function start_ws() {
        if (ws != null) {
            console.log("Close previous WS");
            ws.close()
            ws = null;
        }

        ws = new WebSocket("ws://" + window.server['host'] + ":" + window.server['ws-port'] +
                "?ws-auth-token=" + window.server['ws-auth-token'] +
                '&auth-token=' + window.server['auth-token']);

        ws.onopen = function(event) {
            window.server['ws'] = true;
            console.log("WS opened");

            set_ws_ping_state(1);
        };

        ws.onclose = function(event) {
            window.server['ws'] = false;
            console.log("WS closed by peer !");

            set_ws_ping_state(-1);
            set_conn_state(-1); // @todo should try a ping but probably unreachable
            reset_states();

            // @todo reconnect if lost
        };

        ws.onmessage = function (event) {
            on_ws_message(JSON.parse(event.data));
            // rcv_ws_data();
        }
    }

    // global function to setup data and to get an initial auth-token
    siis_connect = function(api_key, host, port, ws_port=6340) {
        window.server['host'] = host;
        window.server['port'] = port;
        window.server['ws-port'] = ws_port;

        return get_auth_token(api_key);
    }

    siis_login = function(identifier, password, host, port, ws_port=6340) {
        window.server['host'] = host;
        window.server['port'] = port;
        window.server['ws-port'] = ws_port;

        return login(identifier, password);
    }

    window.server['protocol'] = window.location.protocol;

    simple_connect = function(api_key) {
        let port = parseInt(window.location.port || 80);
        return siis_connect(api_key, window.location.hostname, port, port+1);
    }

    // update ping
    function update_states() {
        let types = ['strategy', 'trader', 'watcher1', 'watcher2', 'watcher3', 'watcher4' ,'watcher5'];
        for (let type in types) {
            let id = types[type];
            let update = window.server['updates'][id];

            if (update.svc_delta > 10000) {
                set_svc_state(id, -1);
            } else if (update.svc_delta > 2000) {
                set_svc_state(id, 0);
            } else if (update.svc_delta > 0) {
                set_svc_state(id, 1);
            }

            set_svc_conn_state(id, update.conn_state)
        }

        // update status bar
        update_status_pnl();

        setTimeout(update_states, 1000);
    }

    update_states();
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

function get_local_config(cat) {
    let key = window.strategy.name + '_' + window.strategy.id + '_' + (window.strategy.backtesting ? 'backtest' : 'live') + '_' + cat;

    if (!(key in localStorage)) {
        localStorage[key] = '{}';
    }

    return JSON.parse(localStorage[key]);
}

function save_local_trader(trader_id, param, value) {
    let key = window.strategy.name + '_' + window.strategy.id + '_' + (window.strategy.backtesting ? 'backtest' : 'live') + '_' + trader_id;
    let src = get_local_config(trader_id);

    src[param] = value;
    localStorage[key] = JSON.stringify(src);
}

function save_local_option(option, value) {
    let key = window.strategy.name + '_' + window.strategy.id + '_' + (window.strategy.backtesting ? 'backtest' : 'live') + '_options';
    let src = get_local_config(options);

    src[param] = value;
    localStorage[key] = JSON.stringify(src);
}

function get_local_option(option, defval=null) {
    let src = get_local_config('options');

    return src[option] || defval;
}

function get_local_trader(trader_id) {
    let src = get_local_config(trader_id);

    return src || {
        'profile': null,
        'market-id': null,
        'entry-method': null,
        'take-profit-method': null,
        'stop-loss-method': null,
    };
}

function authenticate() {
    let identifier = $('#identifier').val();
    let password = $('#password').val();

    let port = parseInt(window.location.port || 80);

    if (identifier && password) {
        // by login and password
        siis_login(identifier, password, window.location.hostname, port, ws_port=port+1);
    } else if (identifier) {
        // by API key
        siis_connect(identifier, window.location.hostname, port, ws_port=port+1);
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

        let profile = 'price';
        let entry_method = 'last';
        let stop_loss_method = 'percent-1.00';
        let take_profit_method = 'percent-2.00';

        // load local config
        let local_trader = get_local_trader(id);
        if (local_trader && window.markets[local_trader['market-id']]) {
            if (local_trader['market-id']) {
                market_id = local_trader['market-id'];
            }

            if (local_trader['profile']) {
                profile = local_trader['profile'];
            }

            if (local_trader['entry-method']) {
                entry_method = local_trader['entry-method'];
            }

            if (local_trader['stop-loss-method']) {
                stop_loss_method = local_trader['stop-loss-method'];
            }

            if (local_trader['take-profit-method']) {
                take_profit_method = local_trader['take-profit-method'];
            }
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
        let entry_select = add_entry_price_methods(id, trader_row3);

        add_stop_loss_price(id, trader_row4);
        let stop_loss_select = add_stop_loss_methods(id, trader_row4);

        add_quantity_slider(id, trader_row5);

        add_long_short_actions(id, market_id, trader_row6);

        $(elt).append(trader_row1);
        $(elt).append(trader_row2);
        $(elt).append(trader_row3);
        $(elt).append(trader_row4);
        $(elt).append(trader_row5);
        $(elt).append(trader_row6);

        symbol_select.selectpicker('val', market_id).change();
        profile_select.selectpicker('val', profile).change();
        entry_select.selectpicker('val', entry_method).change();
        stop_loss_select.selectpicker('val', stop_loss_method).change();
        take_profit_select.selectpicker('val', take_profit_method).change();
    });
}

function base_url() {
    return server['protocol'] + "//" + server['host'] + ':' + server['port'] + "/api/v1";
};

function fetch_status() {
    let endpoint = "monitor/status";
    let url = base_url() + '/' + endpoint;

    $.ajax({
        type: "GET",
        url: url,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        // trader status
        let trader = result['data']['trader'];

        set_conn_update_state('trader', trader.name, trader.connected ? 1 : -1);

        // watchers status
        let watchers = result['data']['watchers'];

        for (let i = 0; i < watchers.length; ++i) {
            let watcher = watchers[i];
            set_conn_update_state('watcher', watcher.name, watcher.connected ? 1 : -1);
        }

        // unused watchers slots
        for (let i = 0; i < 5; ++i) {
            let update = window.server['updates']['watcher' + (i+1)];
            if (update.name == "") {
                let nid = '#watcher' + (i+1) + '_state';
                $(nid).css('display', 'none');
            }
        }
    });   
}

function fetch_strategy() {
    let endpoint = "strategy";
    let url = base_url() + '/' + endpoint;

    $.ajax({
        type: "GET",
        url: url,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.markets = {};
        window.strategy = {};
        window.broker = result['broker'];

        window.strategy = result['strategy'];

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
                'ask': market['ask'],
                'mid': market['mid'],
                'spread': market['spread'],
                'profiles': {}
            };

            // append the default profiles from contexts
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
                    } else if (profile['take-profit']['distance-type'] == 'pip') {
                        take_profit_method = 'pip-' + profile['take-profit']['distance'];
                    } else if (profile['take-profit']['distance-type'] == 'dist') {
                        take_profit_method = 'price-' + profile['take-profit']['distance'];
                    } else {
                        take_profit_method = profile['take-profit']['distance-type'];
                    }

                    if (!(take_profit_method in window.methods)) {
                        let label = ""

                        if (profile['take-profit']['distance-type'] == 'percent') {
                            label = profile['take-profit']['distance'].toFixed(2) + '%';
                        } else if (profile['take-profit']['distance-type'] == 'pip') {
                            label = profile['take-profit']['distance'] + 'pips';
                        } else if (profile['take-profit']['distance-type'] == 'dist') {
                            if (profile['take-profit']['distance'] == 0.0) {
                                continue;
                            }
                            label = profile['take-profit']['distance'] + 'price';
                        } else {
                            label = profile['take-profit']['distance-type'];
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
                    } else if (profile['stop-loss']['distance-type'] == 'pip') {
                        stop_loss_method = 'pip-' + profile['stop-loss']['distance'];
                    } else if (profile['stop-loss']['distance-type'] == 'dist') {
                        stop_loss_method = 'price-' + profile['stop-loss']['distance'];
                    } else {
                        stop_loss_method = profile['stop-loss'];
                    }

                    if (!(stop_loss_method in window.methods)) {
                        let label = "";

                        if (profile['stop-loss']['distance-type'] == 'percent') {
                            label = profile['stop-loss']['distance'].toFixed(2) + '%';
                        } else if (profile['stop-loss']['distance-type'] == 'pip') {
                            label = profile['stop-loss']['distance'] + 'pips';
                        } else if (profile['stop-loss']['distance-type'] == 'dist') {
                            if (profile['stop-loss']['distance'] == 0.0) {
                                continue;
                            }
                            label = profile['stop-loss']['distance'] + 'price';
                        } else {
                            label = profile['stop-loss']['distance-type'];
                        }

                        window.methods[stop_loss_method] = {
                            'label': label,
                            'distance': profile['stop-loss']['distance'],
                            'type': profile['stop-loss']['distance-type']
                        };
                    }
                }

                // @todo initial activity and affinity per trader
                // @todo need to be streamed in the WS in case of change from the terminal

                window.markets[market_id].profiles[profile_id] = {
                    'strategy': profile['strategy'],
                    'label': profile['profile-id'],
                    'entry': profile['profile-id'],
                    'take-profit': take_profit_method,
                    'stop-loss': stop_loss_method
                };
            }
        }

        if (server.permissions.indexOf("strategy-open-trade") != -1) {
            setup_traders();
        } else {
            // hide the traders
            maximize_trade_list_view();

            // don't allow restore
            $('#trade_list_sizer').remove();
        }

        if (server.permissions.indexOf("strategy-trader") != -1) {
            // @todo traders options
        } else {
            // @todo trader must not have play/pause, modify quantity, modify affinity
        }

        if (server.permissions.indexOf("strategy-view") != -1) {
            fetch_trades();
            fetch_history();
            fetch_alerts();
            fetch_signals();
            fetch_regions();
        } else {
            // remove menu
            $('#list_active_trades').remove();
            $('#list_historical_trades').remove();
        }

        if (server.permissions.indexOf("trader-balance-view") != -1) {
            fetch_balances();
        } else {
            // remove menu
            $('#list_performances').remove();
        }

        // @todo manage permissions
        // "debug"
        // "admin"

        // "strategy-clean-trade"
        // "strategy-close-trade"
        // "strategy-modify-trade"

        // "strategy-chart"

        // "trader-order-position-view"
        // "trader-cancel-order"
        // "trader-close-position"
    })
    .fail(function() {
        notify({'message': "Unable to obtains markets list info !", 'title': 'fetching"', 'type': 'error'});
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
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.actives_trades = {};

        let trades = result['data'];

        // sort by entry date
        trades.sort((a, b) => (a['entry-open-time'] > b['entry-open-time']) - (a['entry-open-time'] < b['entry-open-time']));

        for (let i = 0; i < trades.length; ++i) {
            let trade = trades[i];

            // initial add
            add_active_trade(trade['market-id'], trade);

            if (parseFloat(trade['filled-entry-qty']) <= 0.0) {
                let key = trade['market-id'] + ':' + trade['id'];
                window.pending_trades.push(key);
            }
        }

        update_status_trades();
    })
    .fail(function() {
        notify({'message': "Unable to obtains actives trades !", 'title': 'fetching"', 'type': 'error'});
    });
}

function fetch_history() {
    let endpoint = "strategy/historical";
    let url = base_url() + '/' + endpoint;

    let params = {}

    $.ajax({
        type: "GET",
        url: url,
        data: params,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.historical_trades = {};

        let trades = result['data'];

        // naturally ordered
        for (let i = 0; i < trades.length; ++i) {
            let trade = trades[i];

            window.historical_trades[trade['market-id'] + ':' + trade.id] = trade;

            // initial add
            add_historical_trade(trade['market-id'], trade);
        }

        update_status_trades();
    })
    .fail(function() {
        notify({'message': "Unable to obtains historical trades !", 'title': 'fetching"', 'type': 'error'});
    });
}

function fetch_balances() {
    let endpoint = "trader";
    let url = base_url() + '/' + endpoint;

    let params = {}

    $.ajax({
        type: "GET",
        url: url,
        data: params,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        let balances = result['data'];

        for (let asset in balances) {
            let balance = balances[asset];
            window.account_balances[asset] = balance;
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains account balances", 'title': 'fetching"', 'type': 'error'});
    });
}

function timestamp_to_time_str(timestamp) {
    if (timestamp == null || timestamp == undefined) {
        return "";
    }

    if (typeof(timestamp) === "number") {
        timestamp *= 1000.0;
    }

    let datetime = new Date(timestamp);
    return datetime.toLocaleTimeString("en-GB");
}

function timestamp_to_date_str(timestamp) {
    if (timestamp == null || timestamp == undefined) {
        return "";
    }

    if (typeof(timestamp) === "number") {
        timestamp *= 1000.0;
    }

    let datetime = new Date(timestamp);
    return datetime.toLocaleDateString("en-GB");
}

function timestamp_to_datetime_str(timestamp) {
    if (timestamp == null || timestamp == undefined) {
        return "";
    }

    if (typeof(timestamp) === "number") {
        timestamp *= 1000.0;
    }

    let datetime = new Date(timestamp);
    return datetime.toLocaleDateString("en-GB") + " " + datetime.toLocaleTimeString("fr-FR");
}

function timeframe_to_str(timeframe) {
    if (timeframe == null || timeframe == undefined) {
        return "";
    }

    if (typeof(timeframe) !== "number") {
        timestamp = parseFloat(timeframe);
    }

    if (timeframe >= 30*24*60*60*60) {
        return timeframe / (30*24*60*60) + " months"
    } else if (timeframe >= 7*24*60*60) {
        return timeframe / (7*24*60*60) + " weeks"
    } else if (timeframe >= 24*60*60) {
        return timeframe / (24*60*60) + " days"
    } else if (timeframe >= 60*60) {
        return timeframe / (60*60) + " hours"
    } else if (timeframe >= 60) {
        return timeframe / 60 + " minutes"
    } else if (timeframe > 0) {
        return timeframe + " seconds"
    } else {
        return "";
    }
}

//
// traders functions
//

function add_symbols(id, to) {
    let select = $('<select class="markets" name="market-id"></select>');
    select.attr('trader-id', id);

    for (market in markets) {
        select.append($('<option value="' + market +'">' + markets[market].symbol + '</>'));
    }

    to.append(select);

    select.selectpicker({'width': '165px', 'size': '10'});

    select.on('change', function(e) {
        on_change_symbol(e);
    });

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
    let input = $('<input type="number" class="take-profit-price" name="take-profit-price" placeholder="Take-Profit" lang="en">');
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
    let input = $('<input type="number" class="entry-price" name="entry-price" placeholder="Entry-Price" lang="en">');
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
    let input = $('<input type="number" class="stop-loss-price" name="stop-loss-price" placeholder="Stop-Loss" lang="en">');
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

    if (!trader_id) {
        trader_id = $(elt.target).parent().attr('trader-id');
    }

    return $('.markets[trader-id="' + trader_id + '"]').val();
}

function retrieve_trade_key(elt) {
    let tr = $(elt.target).parent().parent();
    if (tr.length) {
        return tr.attr('trade-key');
    }

    return "";
}

function retrieve_signal_key(elt) {
    let tr = $(elt.target).parent().parent();
    if (tr.length) {
        return tr.attr('signal-key');
    }

    return "";
}

function retrieve_alert_key(elt) {
    let tr = $(elt.target).parent().parent();
    if (tr.length) {
        return tr.attr('active-alert-key');
    }

    return "";
}

function retrieve_region_key(elt) {
    let tr = $(elt.target).parent().parent();
    if (tr.length) {
        return tr.attr('region-key');
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

function add_long_short_actions(id, market_id, to) {
    let tv_btn = $('<button class="btn btn-secondary trading-view-action" name="trading-view-action"><span class="fas fa-link"></span>&nbsp;TV</button>');
    let long_btn = $('<button class="btn btn-success long-action" name="long-action">Long</button>');
    let short_btn = $('<button class="btn btn-danger short-action" name="short-action">Short</button>');
    let auto_btn = $('<button class="btn btn-secondary siis-chart-auto" name="siis-chart-auto"><span class="fas fa-play"></span></button>');
    let chart_btn = $('<button class="btn btn-secondary siis-chart-action" name="siis-chart-action"><span class="fas fa-chart-bar"></span></button>');

    long_btn.attr('trader-id', id);
    short_btn.attr('trader-id', id);
    tv_btn.attr('trader-id', id);
    auto_btn.attr('trader-id', id).attr('market-id', market_id);
    chart_btn.attr('trader-id', id);

    to.append(tv_btn);
    to.append(long_btn);
    to.append(short_btn);
    to.append(auto_btn);
    to.append(chart_btn);

    long_btn.on('click', function(elt) {
        if (elt.ctrlKey) {
            on_order_long(elt);
        } else {
            on_open_new_trade(elt, 1);
        }
    });

    short_btn.on('click', function(elt) {
        if (elt.ctrlKey) {
            on_order_short(elt);
        } else {
            on_open_new_trade(elt, -1);
        }
    });

    tv_btn.on('click', function(elt) {
        open_trading_view(elt);
    });

    auto_btn.on('click', function(elt) {
        toggle_auto(elt);
    });

    chart_btn.on('click', function(elt) {
        notify({'message': " TODO", 'title': 'feature', 'type': 'warning'});
    });
};

function toggle_auto(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let endpoint = "strategy/instrument";
    let url = base_url() + '/' + endpoint;
    let market = window.markets[market_id];

    if (market_id && market) {
        let data = {
            'market-id': market['market-id'],
            'command': 'activity',
            'action': 'toggle'
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
        .done(function(result) {
            if (data.error) {
                for (let msg in data.messages) {
                    notify({'message': data.messages[msg], 'title': 'Toggle auto-trade"', 'type': 'error'});
                }
            } else {
                // @todo for each trader having the same market-id
                $('button[market-id="' + market_id + '"] span')
                    .removeClass('fa-play')
                    .removeClass('fa-pause')
                    .addClass(result['activity'] ? 'fa-play' : 'fa-pause');

                notify({'message': "Toggle auto-trade", 'type': 'success'});
            }
        })
        .fail(function() {
            notify({'message': "Unable toggle auto-trade status !", 'type': 'error'});
        });
    }
}

function open_trading_view(elt) {
    let market_id = retrieve_symbol(elt);

    if (window.broker['name'] in window.broker_to_tv) {
        if (market_id in window.symbol_to_tv) {
            // mapped symbol
            let stv = window.symbol_to_tv[market_id];

            window.open('https://fr.tradingview.com/chart?symbol=' + stv[0] + '%3A' + stv[1]);
        } else {
            // direct mapping with suffix
            let btv = window.broker_to_tv[window.broker['name']];

            window.open('https://fr.tradingview.com/chart?symbol=' + btv[0] + '%3A' + market_id + btv[1]);
        }
    }
};

function on_change_symbol(elt) {
    let value = $(elt.target).val();

    if (value in window.markets) {
        let trader_id = $(elt.target).attr('trader-id');

        save_local_trader(trader_id, 'market-id', value);
    };
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

        save_local_trader(trader_id, 'profile', value);
    };
};

function on_change_entry_method(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let entry_method = retrieve_entry_method(trader_id);

    if (entry_method == "limit") {
        let ep = $('input.entry-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", false);
    } else {
        let ep = $('input.entry-price[trader-id="' + trader_id +'"]');
        ep.prop("disabled", true);
    }

    save_local_trader(trader_id, 'entry-method', entry_method);
}

function on_change_entry_price(elt) {
    let market_id = retrieve_symbol(elt);

    // @todo change entry price in case of limit or trigger(limit) order
}

function on_change_stop_loss_method(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let stop_loss_method = retrieve_stop_loss_method(trader_id);

    if (stop_loss_method == "price") {
        let slp = $('input.stop-loss-price[trader-id="' + trader_id +'"]');
        slp.prop("disabled", false);
    } else {
        let slp = $('input.stop-loss-price[trader-id="' + trader_id +'"]');
        slp.prop("disabled", true);
    }

    save_local_trader(trader_id, 'stop-loss-method', stop_loss_method);
}

function on_change_take_profit_method(elt) {
    let market_id = retrieve_symbol(elt);
    let trader_id = retrieve_trader_id(elt);

    let take_profit_method = retrieve_take_profit_method(trader_id);

    if (take_profit_method == "price") {
        let tpp = $('input.take-profit-price[trader-id="' + trader_id +'"]');
        tpp.prop("disabled", false);
    } else {
        let tpp = $('input.take-profit-price[trader-id="' + trader_id +'"]');
        tpp.prop("disabled", true);
    }

    save_local_trader(trader_id, 'take-profit-method', take_profit_method);
}

function on_update_performances() {
    if ($('div.performance-list-entries').css('display') != 'none') {
        let table = $('div.performance-list-entries table.performance').find('tbody');
        table.empty();

        let active_total_sum_pct = 0.0;
        let active_total_sum = 0.0;
        
        let history_total_sum_pct = 0.0;
        let history_total_sum = 0.0;

        let success_sum = 0;
        let failed_sum = 0;
        let roe_sum = 0;

        let perfs = {};

        for (let trade in window.actives_trades) {
            let at = window.actives_trades[trade];
            let market_id = at['market-id'];

            if (!(market_id in perfs)) {
                perfs[market_id] = {
                    'success': 0,
                    'failed': 0,
                    'roe': 0,
                    'active': 0.0,
                    'history': 0.0
                }
            }

            if (!isNaN(at['profit-loss-pct'])) {
                perfs[market_id].active += at['profit-loss-pct'];
                
                active_total_sum_pct += at['profit-loss-pct'];
                active_total_sum += at.stats['profit-loss'];
            }
        }

        for (let trade in window.historical_trades) {
            let ht = window.historical_trades[trade];
            let market_id = ht['market-id'];

            if (!(market_id in perfs)) {
                perfs[market_id] = {
                    'success': 0,
                    'failed': 0,
                    'roe': 0,
                    'active': 0.0,
                    'history': 0.0
                }
            }

            if (!isNaN(ht['profit-loss-pct'])) {
                if (ht['profit-loss-pct'] > 0.0) {
                    perfs[market_id].success += 1;
                    success_sum += 1;
                } else if (ht['profit-loss-pct'] < 0.0) {
                    perfs[market_id].failed += 1;
                    failed_sum += 1;
                } else {
                    perfs[market_id].roe += 1;
                    roe_sum += 1;
                }

                perfs[market_id].history += ht['profit-loss-pct'];

                history_total_sum_pct += ht['profit-loss-pct'];
                history_total_sum += ht.stats['profit-loss']
            }
        }

        for (let perf in perfs) {
            let active_total = perfs[perf].active;
            let history_total = perfs[perf].history;
            let success = perfs[perf].success;
            let failed = perfs[perf].failed;
            let roe = perfs[perf].roe;
            let symbol = window.markets[perf] ? window.markets[perf]['symbol'] : perf;

            let row_entry = $('<tr class="performance-entry"></tr>');
            row_entry.append($('<td class="performance-symbol">' + symbol + '</td>'));
            row_entry.append($('<td class="performance-percent-active">' + active_total.toFixed(2) + '%</td>'));
            row_entry.append($('<td class="performance-percent-history">' + history_total.toFixed(2) + '%</td>'));
            row_entry.append($('<td class="performance-success">' + success + '</td>'));
            row_entry.append($('<td class="performance-failed">' + failed + '</td>'));
            row_entry.append($('<td class="performance-roe">' + roe + '</td>'));

            table.append(row_entry);
        }

        let row_entry = $('<tr class="performance-entry"></tr>');
        row_entry.append($('<td class="performance-symbol">Total</td>'));
        row_entry.append($('<td class="performance-percent-active">' + active_total_sum_pct.toFixed(2) + '%</td>'));
        row_entry.append($('<td class="performance-percent-history">' + history_total_sum_pct.toFixed(2) + '%</td>'));
        row_entry.append($('<td class="performance-success">' + success_sum + '</td>'));
        row_entry.append($('<td class="performance-failed">' + failed_sum + '</td>'));
        row_entry.append($('<td class="performance-roe">' + roe_sum + '</td>'));
        row_entry.css('border-top', '1px solid gray');

        table.append(row_entry);

        // balances
        table = $('div.performance-list-entries table.account').find('tbody');
        table.empty();

        for (let asset in window.account_balances) {
            let balance = window.account_balances[asset];

            if (balance.total <= 0.0) {
                continue;
            }

            let asset_symbol = get_currency_display(asset, false);
            let precision = balance.precision;

            let row_entry = $('<tr class="balance-entry"></tr>');
            row_entry.append($('<td class="balance-symbol">' + asset_symbol + '</td>'));

            if (balance.type == "asset") {
                if ((precision === undefined || precision === null) && (asset in CURRENCIES)) {
                    precision = CURRENCIES[asset];
                }

                row_entry.append($('<td class="balance-free">' + format_value(balance.free, precision) + '</td>'));
                row_entry.append($('<td class="balance-locked">' + format_value(balance.locked, precision) + '</td>'));
                row_entry.append($('<td class="balance-total">' + format_value(balance.total, precision) + '</td>'));
            } else if (balance.type == "margin") {
                row_entry.append($('<td class="balance-free">' + format_value(balance.free, precision) + '</td>'));
                row_entry.append($('<td class="balance-locked">' + format_value(balance.locked, precision) +
                    ' (level '+ (balance['margin-level'] * 100).toFixed(2) + '%)</td>'));
                row_entry.append($('<td class="balance-total">' + format_value(balance.total, precision) +
                    ' (upnl ' + format_value(balance.upnl, precision) + ')</td>'));
            }

            table.append(row_entry);
        }

        window.stats['upnlpct'] = active_total_sum_pct;
        window.stats['upnl'] = active_total_sum;

        window.stats['rpnlpct'] = history_total_sum_pct;
        window.stats['rpnl'] = history_total_sum;

        // update every half-second until displayed or @todo remove after using WS implementation
        if (server.permissions.indexOf("trader-balance-view") != -1) {
            setTimeout(fetch_balances, 500);
        }

        if (window.server['ws']) {
            if (server.permissions.indexOf("trader-balance-view") != -1) {
                setTimeout(on_update_performances, 500);
            }
        }
    }
}

function on_update_balances(symbol, asset, timestamp, data) {
    console.log(data)

    if ($('div.performance-list-entries').css('display') != 'none') {
        if (window.account_balances[asset]) {
            // update the related asset
            window.account_balances[asset].free = data.free;
            window.account_balances[asset].locked = data.locked;
            window.account_balances[asset].total = data.total;

            window.account_balances[asset]['margin-level'] = data['margin-level'];
            window.account_balances[asset].upnl = data.upnl;
        } else {
            // or insert
            window.account_balances[asset] = data;

            if (data.precision === undefined || data.precision === null) {
                if (asset in CURRENCIES) {
                    window.account_balances[asset].precision = CURRENCIES[asset];
                } else {
                    window.account_balances[asset].precision = 8;
                }
            }
        }

        // and redraw
        let table = $('div.performance-list-entries table.account').find('tbody');
        table.empty();

        for (let asset in window.account_balances) {
            let balance = window.account_balances[asset];

            if (balance.total <= 0.0) {
                continue;
            }

            let row_entry = $('<tr class="balance-entry"></tr>');
            row_entry.append($('<td class="balance-symbol">' + asset + '</td>'));

            let precision = balance.precision;

            if (balance.type == "asset") {
                if ((precision === undefined || precision === null) && (asset in CURRENCIES)) {
                    precision = CURRENCIES[asset];
                }

                row_entry.append($('<td class="balance-free">' + balance.free.toFixed(precision) + '</td>'));
                row_entry.append($('<td class="balance-locked">' + balance.locked.toFixed(precision) + '</td>'));
                row_entry.append($('<td class="balance-total">' + balance.total.toFixed(precision) + '</td>'));

            } else if (balance.type == "margin") {
                row_entry.append($('<td class="balance-free">' + balance.free.toFixed(precision) + '</td>'));
                row_entry.append($('<td class="balance-locked">' + balance.locked.toFixed(precision) + ' (level '+ balance['margin-level'] * 100).toFixed(2) + '%)</td>');
                row_entry.append($('<td class="balance-total">' + balance.total.toFixed(precision) + '(upnl ' + balance.upnl + ')</td>'));
            }

            table.append(row_entry);
        }
    }
}

function on_update_ticker(market_id, market_id, timestamp, ticker) {
    console.log(ticker);

    if (!(market_id in window.tickers)) {
        window.tickers[market_id] = {
            'bid': 0.0,
            'ask': 0.0,
            'vol24': 0.0,
            'vol24quote': 0.0,
            'spread': 0.0,
            'depth': []
        }
    }

    if (ticker.bid) {
       window.tickers[market_id].bid = ticker.bid;
    }

    if (ticker.ask) {
        window.tickers[market_id].ask = ticker.ask;
    }

    if (ticker.vol24) {
        window.tickers[market_id].vol24 = ticker.vol24;
    }

    if (ticker.vol24quote) {
        window.tickers[market_id].vol24quote = ticker.vol24quote;
    }

    // update spread
    window.tickers[market_id].spread = ticker.ask - ticker.bid;
}

function maximize_trade_list_view() {
    let trade_list = $('div.trade-list');
    trade_list.attr('view-mode', 'maximized')
        .css('height', 'calc(100vh - 15px)')
        .css('max-height', 'calc(100vh - 15px)');

    trade_list.children('div.trade-list-context')
        .css('height', 'calc(100%)');

    let traders = $('div.traders');
    traders.css('height', '0px');
}

function restore_trade_list_view() {
    let trade_list = $('div.trade-list');
    trade_list.attr('view-mode', 'initial')
        .css('height', 'calc(25vh - 2px - 15px)')
        .css('max-height', 'calc(25vh - 2px - 15px)');

    trade_list.children('div.trade-list-context')
        .css('height', 'calc(25vh - 2px - 15px)');

    let traders = $('div.traders');
    traders.css('height', '75vh');
}

function set_conn_state(state) {
    if (state > 0) {
        $('#conn_state').css('background', 'green');
    } else if (state < 0) {
        $('#conn_state').css('background', 'red');
    } else if (state == 0) {
        $('#conn_state').css('background', 'orange');
    }
}

function set_ws_ping_state(state) {
    if (state > 0) {
        $('#ws_state').css('background', 'green');
    } else if (state < 0) {
        $('#ws_state').css('background', 'red');
    } else if (state == 0) {
        $('#ws_state').css('background', 'orange');
    }
}

function find_watcher_slot(name) {
    for (let i = 0; i < 5; ++i) {
        let update = window.server['updates']['watcher' + (i+1)];
        if (update.name == "") {
            return 'watcher' + (i+1);
        }

        if (update.name == name) {
            return 'watcher' + (i+1);
        }
    }

    // no free slot
    return "";
}

function set_svc_update_timestamp(type, name, timestamp) {
    let now = Date.now();

    if (type == "watcher") {
        type = find_watcher_slot(name);

        if (type == "") {
            // no free slot
            return;
        }
    }

    let update = window.server['updates'][type];
    let delta = update.svc_timestamp > 0 ? now - update.svc_timestamp : 0;

    if (update.name == "") {
        update.name = name;

        let nid = '#' + type + '_state';

        $(nid).attr('title', type + ': ' + update.name);
    }

    update.svc_timestamp = timestamp;
    update.svc_delta = delta;
    update.svc_last = now;
}

function set_conn_update_state(type, name, state) {
    let now = Date.now();

    if (type == "watcher") {
        type = find_watcher_slot(name);

        if (type == "") {
            // no free slot
            return;
        }
    }

    let update = window.server['updates'][type];

    if (update.name == "") {
        update.name = name;

        let nid = '#' + type + '_state';
        $(nid).attr('title', type + ': ' + update.name);
    }

    update.conn_state = state;
    update.conn_timestamp = now;
}

function set_svc_state(type, svc_state) {
    let nid = '#' + type + '_state';

    if (svc_state > 0) {
        $(nid).css('background', 'green');
    } else if (svc_state < 0) {
        $(nid).css('background', 'red');
    } else if (svc_state == 0) {
        $(nid).css('background', 'orange');
    }
}

function set_svc_conn_state(type, conn_state) {
    let nid = '#' + type + '_state';

    if (conn_state > 0) {
        $(nid).css('border-color', 'green');
    } else if (conn_state < 0) {
        $(nid).css('border-color', 'red');
    } else if (conn_state == 0) {
        // $(nid).css('border-color', 'orange');
        $(nid).css('border-color', 'gray');
    }
}

function reset_states() {
    for (let type in window.server['updates']) {
        let update = window.server['updates'][type];

        update = {'name': "", 'svc_timestamp': 0, 'svc_delta': 0, 'svc_last': 0, 'conn_state': 0, 'conn_timestamp': 0};

        let nid = '#' + type + '_state';
        $(nid).css('background', 'gray');
        $(nid).css('border-color', 'gray');
        $(nid).attr('title', type + ': ' + update.name)
    }
}

function get_currency_display(currency, display=true) {
    if (currency in CURRENCIES_ALIAS) {
        return CURRENCIES_ALIAS[currency][display ? 1 : 0];
    }

    return currency;
}

function format_value(value, precision) {
    /**
     * Format number value as string according ot a fixed precision and remove trailing 0 and dot.
     */
     if (typeof(value) === 'string') {
        value = parseFloat(value);
     }

    return value.toFixed(precision).replace(/\.?0+$/, '');
}

// function rcv_ws_data() {
//     $('#ws_state').css('border-color', 'green');

//     setTimeout(function() {
//         $('#ws_state').css('border-color', 'gray');
//     }, 500);
// }
