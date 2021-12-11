# @date 2021-10-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command export active or history trades

import json
import csv

from common.utils import timeframe_to_str


def humanize_trade(trade, trade_dump, instrument):
    trade_dump['market-id'] = instrument.market_id
    trade_dump['symbol'] = instrument.symbol

    trade_dump['trade'] = trade.trade_type_to_str()
    trade_dump['entry-timeout'] = timeframe_to_str(trade.entry_timeout)
    # trade_dump['expiry'] = timeframe_to_str(trade.expiry)
    trade_dump['entry-state'] = trade.trade_state_to_str(trade.entry_state)
    trade_dump['exit-state'] = trade.trade_state_to_str(trade.exit_state)
    trade_dump['timeframe'] = trade.timeframe_to_str()
    trade_dump['direction'] = trade.direction_to_str()
    trade_dump['entry-open-time'] = trade.dump_timestamp(trade.eot)
    trade_dump['exit-open-time'] = trade.dump_timestamp(trade.xot)

    # @todo stats

    return trade_dump


def humanize_alert(alert, alert_dump, instrument):
    alert_dump['market-id'] = instrument.market_id
    alert_dump['symbol'] = instrument.symbol

    alert_dump['created'] = alert.dump_timestamp(alert.created)
    alert_dump['timeframe'] = alert.timeframe_to_str()
    alert_dump['expiry'] = alert.expiry_to_str()

    return alert_dump


def humanize_region(region, region_dump, instrument):
    region_dump['market-id'] = instrument.market_id
    region_dump['symbol'] = instrument.symbol

    region_dump['created'] = region.dump_timestamp(region.created)
    region_dump['timeframe'] = region.timeframe_to_str()
    region_dump['expiry'] = region.expiry_to_str()

    return region_dump


def cmd_strategy_trader_export(strategy, strategy_trader, data):
    """
    Query strategy-trader export any trade for a specific trader.
    """
    results = {
        'messages': [],
        'error': False
    }

    dataset = data.get('dataset', "history")
    pending = data.get('pending', False)
    export_format = data.get('export-format', "csv")
    merged = data.get('merged', False)
    header = data.get('header', True)
    first = data.get('first', True)
    filename = data.get('filename', "")

    if dataset not in ('active', 'history', 'alert', 'region'):
        results = {'message': "Unsupported export dataset", 'error': True}
        return results

    if export_format not in ('csv', 'json'):
        results = {'message': "Unsupported export format", 'error': True}
        return results

    filemode = "a" if merged else "w"

    data_dumps = []

    if dataset == "history":
        if not filename:
            if merged:
                filename = "siis_history.%s" % export_format
            else:
                filename = "siis_history_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                data_dumps += strategy_trader._stats['success']
                data_dumps += strategy_trader._stats['failed']
                data_dumps += strategy_trader._stats['roe']

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        data_dumps.sort(key=lambda x: x['stats']['last-realized-exit-datetime'])

    elif dataset == "active":
        if not filename:
            if merged:
                filename = "siis_trades.%s" % export_format
            else:
                filename = "siis_trades_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                for trade in strategy_trader.trades:
                    if trade.is_active() or (pending and trade.is_opened()):
                        data_dump = trade.dumps()

                        if trade.has_operations():
                            data_dump['operations'] = [operation.dumps() for operation in trade.operations]
                        else:
                            data_dump['operations'] = []

                        data_dumps.append(humanize_trade(trade, data_dump, strategy_trader.instrument))

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        data_dumps.sort(key=lambda x: x['entry-open-time'])

    elif dataset == "alert":
        if not filename:
            if merged:
                filename = "siis_alerts.%s" % export_format
            else:
                filename = "siis_alerts_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                for alert in strategy_trader.alerts:
                    data_dump = alert.dumps()
                    data_dumps.append(humanize_alert(alert, data_dump, strategy_trader.instrument))

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        data_dumps.sort(key=lambda x: x['created'])

    elif dataset == "region":
        if not filename:
            if merged:
                filename = "siis_regions.%s" % export_format
            else:
                filename = "siis_regions_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                for region in strategy_trader.regions:
                    data_dump = region.dumps()
                    data_dumps.append(humanize_region(region, data_dump, strategy_trader.instrument))

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        data_dumps.sort(key=lambda x: x['created'])

    if not data_dumps:
        results['messages'].append("No data to export")
        return results

    results['count'] = len(data_dumps)

    for element in data_dumps:
        element['market-id'] = strategy_trader.instrument.market_id
        element['symbol'] = strategy_trader.instrument.symbol

    if export_format == "csv":
        try:
            with open(filename, filemode, newline='') as f:
                wrt = csv.writer(f, delimiter='\t', quotechar='|', quoting=csv.QUOTE_MINIMAL)

                # header
                if header:
                    wrt.writerow(list(data_dumps[0].keys()))

                # dataset
                for row in data_dumps:
                    wrt.writerow([str(x) for x in row.values()])

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

    elif export_format == "json":
        try:
            with open(filename, filemode) as f:
                if merged:
                    for row in data_dumps:
                        if not first:
                            f.write(',\n')
                        json.dump(row, f, indent=4)
                        first = False
                else:
                    json.dump(data_dumps, f, indent=4)

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

    return results


def cmd_strategy_trader_export_all(strategy, data):
    """
    Query strategy-trader export any trades for any traders, or alerts or regions data.
    """
    results = []

    # clear the file
    dataset = data.get('dataset', "history")
    export_format = data.get('export-format', "csv")
    filename = data.get('filename', "")

    if dataset not in ('active', 'history', 'alert', 'region'):
        results = {'message': "Unsupported export dataset", 'error': True}
        return results

    if export_format not in ('csv', 'json'):
        results = {'message': "Unsupported export format", 'error': True}
        return results

    if not filename:
        if dataset == "history":
            filename = "siis_history.%s" % export_format
        elif dataset == "active":
            filename = "siis_trades.%s" % export_format
        elif dataset == "alert":
            filename = "siis_alerts.%s" % export_format
        elif dataset == "region":
            filename = "siis_regions.%s" % export_format

    with open(filename, "w") as f:
        if export_format == "json":
            f.write('[\n')

    data['merged'] = True
    data['header'] = True
    data['first'] = True

    last_count = 0

    with strategy._mutex:
        for k, strategy_trader in strategy._strategy_traders.items():
            if export_format == "json":
                if last_count > 0:
                    data['first'] = False

            result = cmd_strategy_trader_export(strategy, strategy_trader, data)
            last_count = result.get('count', 0)

            results.append(result)

            # only for the first
            data['header'] = False

    # final closure ] for json only
    if export_format == "json":
        with open(filename, "a") as f:
            f.write('\n]')

    return results
