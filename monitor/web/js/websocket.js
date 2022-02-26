const STREAM_UNDEFINED = 0;
const STREAM_GENERAL = 1;
const STREAM_TRADER = 2;
const STREAM_STRATEGY = 3;
const STREAM_STRATEGY_CHART = 4;
const STREAM_STRATEGY_INFO = 5;
const STREAM_STRATEGY_TRADE = 6;
const STREAM_STRATEGY_ALERT = 7;
const STREAM_STRATEGY_SIGNAL = 8;
const STREAM_WATCHER = 9;
const STREAM_STRATEGY_REGION = 10;

function read_value(data) {
    if (data.t == "b") {
        return read_bool(data);
    } else if (data.t == "i") {
        return read_int(data);
    } else if (data.t == "il") {
        return read_int_list(data);
    } else if (data.t == "f") {
        return read_float(data);
    } else if (data.t == "ft") {
        return read_float_tuple(data);
    } else if (data.t == "fs") {
        return read_float_serie(data);
    } else if (data.t == "fbs") {
        return read_float_bar_serie(data);
    } else if (data.t == "sl") {
        return read_str_lst(data);
    } else if (data.t == "to") {
        return read_trade_entry(data);
    } else if (data.t == "tu") {
        return read_trade_update(data);
    } else if (data.t == "tx") {
        return read_trade_exit(data);
    } else if (data.t == "ht") {
        return read_trade_history(data);
    } else if (data.t == "se") {
        return read_serie(data);
    } else if (data.t == "fsc") {
        return read_float_scatter(data);
    } else if (data.t == "os") {
        return read_ohlc_serie(data);
    } else if (data.t == "tk") {
        return read_ticker(data);
    } else if (data.t == "ts") {
        return read_signal(data);
    } else if (data.t == "sa") {
        return read_signal_alert(data);
    } else if (data.t == "ca") {
        return read_alert(data);
    } else if (data.t == "ra") {
        return read_alert(data);
    } else if (data.t == "sr") {
        return read_signal_region(data);
    } else if (data.t == "cr") {
        return read_region(data);
    } else if (data.t == "rr") {
        return read_region(data);
    } else if (data.t == "ab") {
        return read_account_balance(data);
    } else {
        return None;
    }
}

function read_bool(data) {
    return data.v;
}

function read_int(data) {
    return data.v;
}

function read_int_list(data) {
    return data.v;   
}

function read_float(data) {
    return data.v;
}

function read_float_tuple(data) {
    return data.v;
}

function read_float_serie(data) {
    return data.v;
}

function read_float_bar_serie(data) {
    return data.v;
}

function read_str_lst(data) {
    return data.v;
}

function read_trade_entry(data) {
    return data.v;
}

function read_trade_update(data) {
    return data.v;
}

function read_trade_exit(data) {
    return data.v;
}

function read_serie(data) {
    return data.v;
}

function read_float_scatter(data) {
    return data.v;
}

function read_ohlc_serie(data) {
    return data.v;
}

function read_ticker(data) {
    return data.v;
}

function read_signal(data) {
    return data.v;
}

function read_signal_alert(data) {
    return data.v;
}

function read_alert(data) {
    return data.v;
}

function read_signal_region(data) {
    return data.v;
}

function read_region(data) {
    return data.v;
}

function read_account_balance(data) {
    return data.v;
}

function on_ws_message(data) {
    // n i o g c v b s t
    // c category, g group, s name
    let component = data.g;

    if (data.c == STREAM_GENERAL) {
        // global status
        // nothing for now

    } else if (data.c == STREAM_TRADER) {
        // trader status
        let value = read_value(data);

        if (value && data.g == 'status' && data.n == 'ping') {
            set_svc_update_timestamp('trader', data.s, value);

        } else if (value && data.g == 'status' && data.n == 'conn') {
            set_conn_update_state('trader', data.s, value);

        } else if (value && data.t == 'tk') {
            // update ticker
            on_update_ticker(data.s, value.id, data.b*1000, value);

        } else if (value && data.t == 'ab') {
            // update ticker
            on_update_balances(data.s, value.asset, data.b*1000, value);
        }

    } else if (data.c == STREAM_WATCHER) {
        // strategy info
        let value = read_value(data);

        if (value && data.g == 'status' && data.n == 'ping') {
            set_svc_update_timestamp('watcher', data.s, value);

        } else if (value && data.g == 'status' && data.n == 'conn') {
            set_conn_update_state('watcher', data.s, value);
        }

    } else if (data.c == STREAM_STRATEGY) {
        // strategy info
        let value = read_value(data);

        if (value && data.g == 'status' && data.n == 'ping') {
            set_svc_update_timestamp('strategy', data.s, value);
        }

    } else if (data.c == STREAM_STRATEGY_CHART) {
        // strategy trader chart data
        // @todo

    } else if (data.c == STREAM_STRATEGY_INFO) {
        // strategy trader performance
        // @todo

    } else if (data.c == STREAM_STRATEGY_TRADE) {
        // strategy trader trade
        let value = read_value(data);

        if (value && data.t == 'to') {
            // active trade insert
            on_active_trade_entry_message(data.s, value.id, data.b*1000, value);
        } else if (value && data.t == 'tu') {
            // active trade update
            on_active_trade_update_message(data.s, value.id, data.b*1000, value);
        } else if (value && data.t == 'tx') {
            // active trade delete
            on_active_trade_exit_message(data.s, value.id, data.b*1000, value);
        }

    } else if (data.c == STREAM_STRATEGY_ALERT) {
        // strategy trader alert
        let value = read_value(data);

        if (value && data.t == 'sa') {
            on_strategy_signal_alert(data.s, value.id, data.b*1000, value);
        } else if (value && data.t == 'ca') {
            on_strategy_create_alert(data.s, value.id, data.b*1000, value);
        } else if (value && data.t == 'ra') {
            on_strategy_remove_alert(data.s, value.id, data.b*1000, value);
        }

    } else if (data.c == STREAM_STRATEGY_REGION) {
        // strategy trader region
        let value = read_value(data);

        if (value && data.t == 'sr') {
            // @todo signal region
        } else if (value && data.t == 'cr') {
           // @todo create region
        } else if (value && data.t == 'rr') {
            // @todo remove region
        }

    } else if (data.c == STREAM_STRATEGY_SIGNAL) {
        // strategy trader signal
        let value = read_value(data);

        if (value && data.t == 'ts') {
            on_strategy_signal(data.s, value.id, data.b*1000, value);
        }
    }
}
