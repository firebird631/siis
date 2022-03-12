// @todo add range region
// @todo add trend region
// @todo remove region

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
/*
    let condition_msg = "-";
    let cancellation_msg = "never";

    let price_src = price_src_to_str(region['price-src']);

    if (region.name == "range-region") {
        if (region.direction > 0) {
            condition_msg = `if ${price_src} price goes above ${format_price(market_id, region.price)}`;
            if (region['cancellation-price'] > 0) {
                cancellation_msg = `if ${price_src} price < ${format_price(market_id, region['cancellation-price'])}`;
            }
        } else if (region.direction < 0) {
            condition_msg = `if ${price_src} price goes below ${format_price(market_id, region.price)}`;
            if (region['cancellation-price'] > 0) {
                cancellation_msg = `if ${price_src} price > ${format_price(market_id, region['cancellation-price'])}`;
            }
        }
    } else if (region.name == "trend-region") {
    }

    let lregion_id = $('<span class="region-id"></span>').text(region.id);
    let region_symbol = $('<span class="region-symbol"></span>').text(market_id);

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.created*1000));

    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(alert.timeframe || "trade");
    let alert_expiry = $('<span class="alert-datetime"></span>');
    if (alert.expiry > 0) {
        alert_expiry.text(timestamp_to_datetime_str(alert.created+alert.expiry*1000));
    } else {
        alert_expiry.text("never");
    }

    let region_condition = $('<span class="alert-condition"></span>').text(condition_msg);
    let region_cancellation = $('<span class="alert-cancellation"></span>').text(cancellation_msg);

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').append(alert_expiry));
    alert_elt.append($('<td></td>').append(alert_condition));
    alert_elt.append($('<td></td>').append(alert_cancellation));

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
*/
    window.regions[key] = region;
}

function on_strategy_remove_region(market_id, timestamp, region_id) {
    let key = market_id + ':' + region_id;
    //let container = $('div.region-list-entries tbody');

    //container.find('tr.region[region-key="' + key + '"]').remove();
    if (key in window.regions) {
        delete window.regions[key];
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

            window.regions[region['market-id'] + ':' + region.id] = alert;

            // initial add
            on_strategy_create_region(alert['market-id'], region.id, region.timestamp, region, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains regions !", 'title': 'fetching"', 'type': 'error'});
    });
};
