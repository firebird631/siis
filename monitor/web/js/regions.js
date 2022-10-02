/**
 * @date 2020-01-24
 * @author Frederic Scherma, All rights reserved without prejudices.
 * @license Copyright (c) 2020 Dream Overflow
 * Web trader region handler.
 */

// @todo add range region dialog
// @todo add trend region dialog
// @todo remove region

function on_strategy_signal_region(market_id, region_id, timestamp, region, do_notify=true) {
    // @todo update inside status
}

function price_src_to_str(price_src) {
    switch (price_src) {
        case 0:
            return "bid";
        case 1:
            return "ask";
        case 2:
            return "mid";
        default:
            return "";
    }
}

function region_name_format(region, market_id, price_src) {
    let condition_msg = "-";

    if (region.name == "range") {
        condition_msg = `[${format_price(market_id, region.low)} - ${format_price(market_id, region.high)}]`;
    } else if (region.name == "trend") {
        condition_msg = `[${format_price(market_id, region.low_a)} - ${format_price(market_id, region.high_a)}] - ` +
                        `[${format_price(market_id, region.low_b)} - ${format_price(market_id, region.high_b)}]`;
    }

    return condition_msg;
}

function region_cancellation_format(region, market_id, price_src) {
    let cancellation_msg = "never";

    if (region.cancellation > 0) {
        if (region.direction > 0) {
            cancellation_msg = `if ${price_src} price < ${format_price(market_id, region.cancellation)}`;
        } else if (region.direction < 0) {
            cancellation_msg = `if ${price_src} price > ${format_price(market_id, region.cancellation)}`;
        }
    }

    return cancellation_msg;
}

function on_strategy_create_region(market_id, region_id, timestamp, region, do_notify=true) {
    let key = market_id + ':' + region_id;

    let region_elt = $('<tr class="region"></tr>');
    region_elt.attr('region-key', key);

    let condition_msg = "-";
    let cancellation_msg = "never";

    let price_src = price_src_to_str(region['price-src']);

    condition_msg = region_name_format(region, market_id, price_src);
    cancellation_msg = region_cancellation_format(region, market_id, price_src);

    let lregion_id = $('<span class="region-id"></span>').text(region.id);
    let region_symbol = $('<span class="region-symbol badge badge-info"></span>').text(market_id);

    let region_label = $('<span class="region-label"></span>').text(region.name);

    let region_direction = $('<span class="region-direction fa"></span>');
    if (region.direction == 0) {
        region_direction.addClass('region-both').addClass('fa-arrows-alt-v');
    } else if (region.direction < 0) {
        region_direction.addClass('region-down').addClass('fa-arrow-down');
    } else if (region.direction > 0) {
        region_direction.addClass('region-up').addClass('fa-arrow-up');
    }

    let region_stage = $('<span class="region-way fa"></span>');
    if (region.stage == 0) {
        region_stage.addClass('region-both').addClass('fa-arrows-alt-h');
    } else if (region.stage < 0) {
        region_stage.addClass('region-exit').addClass('fa-arrow-left');
    } else if (region.stage > 0) {
        region_stage.addClass('region-entry').addClass('fa-arrow-right');
    }

    // in seconds timestamp
    let region_datetime = $('<span class="region-datetime"></span>').text(timestamp_to_datetime_str(region.created));
    let region_timeframe = $('<span class="region-timeframe"></span>').text(region.timeframe || "trade");
    let region_expiry = $('<span class="region-expiry"></span>');
    if (region.expiry > 0) {
        // absolute timestamp
        region_expiry.text(timestamp_to_datetime_str(region.expiry));
    } else {
        region_expiry.text("never");
    }

    let region_condition = $('<span class="region-condition"></span>').text(condition_msg);
    let region_cancellation = $('<span class="region-cancellation"></span>').text(cancellation_msg);
    let region_inside = $('<span class="region-inside"></span>').text("");

    region_elt.append($('<td></td>').append(lregion_id));
    region_elt.append($('<td></td>').append(region_symbol));
    region_elt.append($('<td></td>').addClass('optional-info').append(region_label));
    region_elt.append($('<td></td>').append(region_direction));
    region_elt.append($('<td></td>').append(region_stage));
    region_elt.append($('<td></td>').append(region_timeframe));
    // region_elt.append($('<td></td>').append(region_datetime));
    region_elt.append($('<td></td>').addClass('optional-info').append(region_expiry));
    region_elt.append($('<td></td>').append(region_condition));
    region_elt.append($('<td></td>').addClass('optional-info').append(region_cancellation));
    region_elt.append($('<td></td>').append(region_inside));

    // actions
    let region_remove = $('<button class="region-remove btn btn-danger fas fa-window-close"></button>');

    if (server.permissions.indexOf("strategy-trader") < 0) {
        region_remove.attr("disabled", "")
    }

    region_elt.append($('<td></td>').append(region_remove));

    let region_details = $('<button class="region-details btn btn-info fas fa-info"></button>');
    region_elt.append($('<td></td>').append(region_details));

    region_details.on('click', on_details_region);

    // append
    $('div.region-list-entries tbody').prepend(region_elt);

    // actions
    if (server.permissions.indexOf("strategy-trader") != -1) {
        region_remove.on('click', on_remove_region);
    }

    if (do_notify) {
        let message = region.name + " "  + condition_msg + " " + region.symbol + " " + region.message;
        notify({'message': message, 'title': 'Strategy Region Created', 'type': 'info'});
    }

    window.regions[key] = region;
}

function on_strategy_remove_region(market_id, timestamp, region_id) {
    let key = market_id + ':' + region_id;
    let container = $('div.region-list-entries tbody');

    container.find('tr.region[region-key="' + key + '"]').remove();
    if (key in window.regions) {
        delete window.regions[key];
    }
}

function on_remove_region(elt) {
    let key = retrieve_region_key(elt);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let region_id = parseInt(parts[1]);

    let endpoint = "strategy/region";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];

    if (market_id && market && region_id) {
        let data = {
            'market-id': market['market-id'],
            'region-id': region_id,
            'action': "del-region"
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
                    notify({'message': data.messages[msg], 'title': 'Remove Region', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Remove Region', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Remove Region', 'type': 'error'});
            }
        });
    }
}

window.fetch_regions = function() {
    // fetch actives regions
    let endpoint = "strategy/region";
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
        window.regions = {};

        let regions = result['data'];
        if (!regions) {
            return;
        }

        // naturally ordered
        for (let i = 0; i < regions.length; ++i) {
            let region = regions[i];

            window.regions[region['market-id'] + ':' + region.id] = region;

            // initial add
            on_strategy_create_region(region['market-id'], region.id, region.timestamp, region, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains regions !", 'title': 'fetching"', 'type': 'error'});
    });
};

function on_add_range_region(elt) {
    alert("TODO");
}

function on_add_trend_region(elt) {
    alert("TODO");
}

function on_details_signal_region(elt) {
    alert("TODO");
}

function on_details_region(elt) {
    let key = retrieve_region_key(elt);
    let table = $('#region_details_table');
    let tbody = table.find('tbody').empty();

    let region = window.regions[key];
    if (!region) {
        return;
    }

    let market_id = region['market-id'];

    let price_src = price_src_to_str(region['price-src']);

    let condition_msg = region_name_format(region, market_id, price_src);
    let cancellation_msg = region_cancellation_format(region, market_id, price_src);

    let id = $('<tr></tr>').append($('<td class="data-name">Identifier</td>')).append(
        $('<td class="data-value">' + region.id + '</td>'));
    let lmarket_id = $('<tr></tr>').append($('<td class="data-name">Market</td>')).append(
        $('<td class="data-value"><span class="badge badge-info">' + region['market-id'] + '</span></td>'));
    let symbol = $('<tr></tr>').append($('<td class="data-name">Symbol</td>')).append(
        $('<td class="data-value"><span class="badge badge-info">' + region.symbol + '</span></td>'));
    let version = $('<tr></tr>').append($('<td class="data-name">Version</td>')).append(
        $('<td class="data-value">' + region.version + '</td>'));
    let timestamp = $('<tr></tr>').append($('<td class="data-name">Created</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(region.created) + '</td>'));
    let timeframe = $('<tr></tr>').append($('<td class="data-name">Timeframe</td>')).append(
        $('<td class="data-value">' + (timeframe_to_str(region.timeframe) || "trade/tick") + '</td>'));
    let expiry = $('<tr></tr>').append($('<td class="data-name">Expiry</td>')).append(
        $('<td class="data-value">' + (timeframe_to_str(region.expiry) || "never") + '</td>'));

    let label = $('<tr></tr>').append($('<td class="data-name">Label</td>')).append(
        $('<td class="data-value">' + region.name + '</td>'));

    let spacer1 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

//high: 20000
//low: 19000

    let condition = $('<tr></tr>').append($('<td class="data-name">Trigger condition</td>')).append(
        $('<td class="data-value">' + condition_msg + '</td>'));

    let spacer2 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value">-</td>'));
    if (region.direction == "long" || region.direction == 1) {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="region-direction fas region-up fa-arrow-up"></span></td>'));
    } else if (region.direction == "short" || region.direction == -1) {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="region-direction fas region-down fa-arrow-dn"></span></td>'));
    }

    let stage = $('<tr></tr>').append($('<td class="data-name">Stage</td>')).append(
        $('<td class="data-value">-</td>'));
    if (region.stage == "long" || region.stage == 1) {
        stage = $('<tr></tr>').append($('<td class="data-name">Stage</td>')).append(
        $('<td class="data-value"><span class="region-direction fas region-up fa-arrow-up"></span></td>'));
    } else if (region.stage == "short" || region.stage == -1) {
        stage = $('<tr></tr>').append($('<td class="data-name">Stage</td>')).append(
        $('<td class="data-value"><span class="region-direction fas region-down fa-arrow-dn"></span></td>'));
    }

    let region_price = 0.0;
    let region_dir = 0;
    if (region.name == "range") {
        if (region.cancellation <= region['low']) {
            region_price = region['low'];
            region_dir = 1;
        } else if (region.cancellation >= region['high']) {
            region_price = region['high'];
            region_dir = -1;
        }
    } else if (region.name == "trend") {
        let min_low = math.min(region['low-a'], region['low-b']);
        let max_high = math.max(region['high-a'], region['high-b']);

        if (region.cancellation <= min_low) {
            region_price = min_low;
            region_dir = 1;
        } else if (region.cancellation >= max_high) {
            region_price = max_high;
            region_dir = -1;
        }
    }

    let cancellation_price_rate = compute_price_pct(region['cancellation'], region_price, region_dir);
    let cancellation_price_pct = (cancellation_price_rate * 100).toFixed(2) + '%';
    let cancellation_price = $('<tr></tr>').append($('<td class="data-name">Cancellation-Price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, region['cancellation']) + ' (' +
        cancellation_price_pct + ')</td>'));

    let spacer3 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let cancellation_condition = $('<tr></tr>').append($('<td class="data-name">Cancellation condition</td>')).append(
        $('<td class="data-value">' + cancellation_msg + '</td>'));

    let spacer4 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    tbody.append(id);
    tbody.append(lmarket_id);
    tbody.append(symbol);
    tbody.append(version);
    tbody.append(timestamp);
    tbody.append(timeframe);
    tbody.append(expiry);
    tbody.append(direction);
    tbody.append(stage);
    tbody.append(label);
    tbody.append(spacer1);
    tbody.append(condition);
    tbody.append(spacer2);
    tbody.append(cancellation_price);
    tbody.append(spacer3);
    tbody.append(cancellation_condition);
    tbody.append(spacer4);

    // specific
    if (region.name == "range") {
       let low_price = $('<tr></tr>').append($('<td class="data-name">Low-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['low']) + '</td>'));

       let high_price = $('<tr></tr>').append($('<td class="data-name">High-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['high']) + '</td>'));

       tbody.append(low_price);
       tbody.append(high_price);

    } else if (region.name == "trend") {
       let low_a_price = $('<tr></tr>').append($('<td class="data-name">Low-A-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['low_a']) + '</td>'));
       let high_a_price = $('<tr></tr>').append($('<td class="data-name">High-A-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['high_a']) + '</td>'));

       let low_b_price = $('<tr></tr>').append($('<td class="data-name">Low-B-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['low_b']) + '</td>'));
       let high_b_price = $('<tr></tr>').append($('<td class="data-name">High-B-Price</td>')).append(
           $('<td class="data-value">' + format_price(market_id, region['high_b']) + '</td>'));

       tbody.append(low_a_price);
       tbody.append(high_a_price);
       tbody.append(low_b_price);
       tbody.append(high_b_price);
    }

    $('#region_details').modal({'show': true, 'backdrop': true});
}
