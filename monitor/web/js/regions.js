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
    // @todo
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

function on_strategy_create_region(market_id, region_id, timestamp, region, do_notify=true) {
    let key = market_id + ':' + region_id;

    let region_elt = $('<tr class="region"></tr>');
    region_elt.attr('region-key', key);

    let condition_msg = "-";
    let cancellation_msg = "never";

    let price_src = price_src_to_str(region['price-src']);

    if (region.name == "range") {
        condition_msg = `[${format_price(market_id, region.low)} - ${format_price(market_id, region.high)}]`;
    } else if (region.name == "trend") {
        condition_msg = `[${format_price(market_id, region.low_a)} - ${format_price(market_id, region.high_a)}] - ` +
                        `[${format_price(market_id, region.low_b)} - ${format_price(market_id, region.high_b)}]`;
    }

    if (region.cancellation > 0) {
        if (region.direction > 0) {
            cancellation_msg = `if ${price_src} price < ${format_price(market_id, region.cancellation)}`;
        } else if (region.direction < 0) {
            cancellation_msg = `if ${price_src} price > ${format_price(market_id, region.cancellation)}`;
        }
    }

    let lregion_id = $('<span class="region-id"></span>').text(region.id);
    let region_symbol = $('<span class="region-symbol"></span>').text(market_id);

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
    let region_inside = $('<span class="region-cancellation"></span>').text("");

    region_elt.append($('<td></td>').append(lregion_id));
    region_elt.append($('<td></td>').append(region_symbol));
    region_elt.append($('<td></td>').append(region_label));
    region_elt.append($('<td></td>').append(region_direction));
    region_elt.append($('<td></td>').append(region_stage));
    region_elt.append($('<td></td>').append(region_timeframe));
    // region_elt.append($('<td></td>').append(region_datetime));
    region_elt.append($('<td></td>').append(region_expiry));
    region_elt.append($('<td></td>').append(region_condition));
    region_elt.append($('<td></td>').append(region_cancellation));
    region_elt.append($('<td></td>').append(region_inside));

//    expiry: 0
//    high: 0.5
//    id: 1
//    low: 0.3
//    region: 1
//    stage: 0

    // actions
    let region_remove = $('<button class="region-remove btn btn-danger fas fa-window-close"></button>');

    if (server.permissions.indexOf("strategy-trader") < 0) {
        region_remove.attr("disabled", "")
    }

    region_elt.append($('<td></td>').append(region_remove));

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
