const STREAM_UNDEFINED = 0;
const STREAM_GENERAL = 1;
const STREAM_TRADER = 2;
const STREAM_STRATEGY = 3;
const STREAM_STRATEGY_CHART = 4;
const STREAM_STRATEGY_INFO = 5;
const STREAM_STRATEGY_TRADE = 6;
const STREAM_STRATEGY_ALERT = 7;
const STREAM_STRATEGY_SIGNAL = 8;

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
    } else if (data.t == "se") {
        return read_serie(data);
    } else if (data.t == "fsc") {
        return read_float_scatter(data);
    } else if (data.t == "os") {
        return read_ohlc_serie(data);
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

function on_ws_message(data) {
    // n i o g c v b s t
    // c categorie, g groupe, s name
    let component = data.g;

    if (data.c == STREAM_GENERAL) {
        //  global status

    } else if (data.c == STREAM_TRADER) {
        // strategy trader status
        // @todo 'cpu-load'

    } else if (data.c == STREAM_STRATEGY) {
        // strategy info
        let appliance = data.g;
        let symbol = data.s;

    } else if (data.c == STREAM_STRATEGY_CHART) {
        // strategy trader chart data
        let appliance = data.g;
        let symbol = data.s;

    } else if (data.c == STREAM_STRATEGY_INFO) {
        // strategy trader performance
        let appliance = data.g;
        let symbol = data.s;

    } else if (data.c == STREAM_STRATEGY_TRADE) {
        // strategy trader trade
        let appliance = data.g;
        let symbol = data.s;

        let value = read_value(data);
        if (value && data.t == 'to') {
            on_trade_entry_message(appliance, market_id, trade_id, data.b*1000, value);
        } else if (value && data.t == 'tu') {
            on_trade_update_message(appliance, market_id, trade_id, data.b*1000, value);
        } else if (value && data.t == 'tx') {
            on_trade_exit_message(appliance, market_id, trade_id, data.b*1000, value);
        }

    } else if (data.c == STREAM_STRATEGY_ALERT) {
        // strategy trader alert
        let appliance = data.g;
        let symbol = data.s;

    } else if (data.c == STREAM_STRATEGY_SIGNAL) {
        // strategy trader signal
        let appliance = data.g;
        let symbol = data.s;

    }
}