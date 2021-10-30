# @date 2021-10-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command export active or history trades

import json
import csv

from common.utils import timeframe_to_str


def humanize(trade, trade_dump, instrument):
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

    if dataset not in ('active', 'history'):
        results['messages'].append("Unsupported export dataset")
        results['error'] = True

        return results

    if export_format not in ('csv', 'json'):
        results['messages'].append("Unsupported export format")
        results['error'] = True

        return results

    filename = ""
    filemode = "a" if merged else "w"

    trades_dumps = []

    if dataset == "history":
        if merged:
            filename = "/tmp/siis_trades_history.%s" % export_format
        else:
            filename = "/tmp/siis_trades_history_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                trades_dumps += strategy_trader._stats['success']
                trades_dumps += strategy_trader._stats['failed']
                trades_dumps += strategy_trader._stats['roe']

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        trades_dumps.sort(key=lambda x: x['stats']['last-realized-exit-datetime'])

    elif dataset == "active":
        if merged:
            filename = "/tmp/siis_trades.%s" % export_format
        else:
            filename = "/tmp/siis_trades_%s.%s" % (strategy_trader.instrument.symbol, export_format)

        try:
            with strategy_trader._mutex:
                for trade in strategy_trader.trades:
                    if trade.is_active() or (pending and trade.is_opened()):
                        trade_dump = trade.dumps()
                        if trade.has_operations():
                            trade_dump['operations'] = [operation.dumps() for operation in trade.operations]
                        else:
                            trade_dump['operations'] = []

                        trades_dumps.append(humanize(trade, trade_dump, strategy_trader.instrument))

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

        trades_dumps.sort(key=lambda x: x['entry-open-time'])

    if not trades_dumps:
        results['messages'].append("No data to export")
        return results

    results['count'] = len(trades_dumps)

    for trade in trades_dumps:
        trade['market-id'] = strategy_trader.instrument.market_id
        trade['symbol'] = strategy_trader.instrument.symbol

    if export_format == "csv":
        try:
            with open(filename, filemode, newline='') as f:
                wrt = csv.writer(f, delimiter='\t', quotechar='|', quoting=csv.QUOTE_MINIMAL)

                # header
                if header:
                    wrt.writerow(list(trades_dumps[0].keys()))

                # dataset
                for row in trades_dumps:
                    wrt.writerow([str(x) for x in row.values()])

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

    elif export_format == "json":
        try:
            with open(filename, filemode) as f:
                if merged:
                    for row in trades_dumps:
                        if not first:
                            f.write(',\n')
                        json.dump(row, f, indent=4)
                        first = False
                else:
                    json.dump(trades_dumps, f, indent=4)

        except Exception as e:
            results['messages'].append(repr(e))
            results['error'] = True

    return results


def cmd_strategy_trader_export_all(strategy, data):
    """
    Query strategy-trader export any trades for any traders.
    """
    results = []

    # clear the file
    dataset = data.get('dataset', "history")
    export_format = data.get('export-format', "csv")
    filename = ""

    if dataset not in ('active', 'history'):
        results = {}
        results['messages'].append("Unsupported export dataset")
        results['error'] = True

        return results

    if export_format not in ('csv', 'json'):
        results = {}
        results['messages'].append("Unsupported export format")
        results['error'] = True

        return results

    if dataset == "history":
        filename = "/tmp/siis_trades_history.%s" % export_format
    elif dataset == "active":
        filename = "/tmp/siis_trades.%s" % export_format

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
