# @date 2021-10-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command import active trades

import json

from common.utils import timeframe_from_str, direction_from_str
from strategy.strategytrade import StrategyTrade


def dehumanize(trade_dump):
    trade_dump['trade'] = StrategyTrade.trade_type_from_str(trade_dump['trade'])
    trade_dump['entry-timeout'] = timeframe_from_str(trade_dump['entry-timeout'])
    # trade_dump['expiry'] = timeframe_to_str(trade_dump['expiry'])
    trade_dump['entry-state'] = StrategyTrade.trade_state_from_str(trade_dump['entry-state'])
    trade_dump['exit-state'] = StrategyTrade.trade_state_from_str(trade_dump['exit-state'])
    trade_dump['timeframe'] = timeframe_from_str(trade_dump['timeframe'])
    trade_dump['direction'] = direction_from_str(trade_dump['direction'])
    trade_dump['entry-open-time'] = StrategyTrade.load_timestamp(trade_dump['entry-open-time'])
    trade_dump['exit-open-time'] = StrategyTrade.load_timestamp(trade_dump['exit-open-time'])
    # @todo stats

    return trade_dump


def cmd_strategy_trader_import(strategy, strategy_trader, data):
    """
    Query strategy-trader import any trade for a specific trader.
    """
    results = {
        'messages': [],
        'error': False
    }

    # filename = data.get('filename', "/tmp/siis_trades_%s.json" % strategy_trader.instrument.symbol)
    trades_dumps = data.get('trades', [])

    for trade_dump in trades_dumps:
        try:
            dehumanize(trade_dump)
            trade_id = trade_dump['id']
            trade_type = trade_dump['trade']
            operations = trade_dump.get('operations', [])

            strategy_trader.loads_trade(trade_id, trade_type, trade_dump, operations)
        except Exception as e:
            results['messages'].append("Error during import of trade %s for %s" % (
                trade_dump.get('id'), trade_dump.get('symbol')))
            results['error'] = True

    return results


def cmd_strategy_trader_import_all(strategy, data):
    """
    Query strategy-trader import any trades for any traders from a specified JSON file.
    """
    results = []

    filename = data.get('filename', "/tmp/siis_trades.json")

    try:
        with open(filename, "rt") as f:
            dataset = json.loads(f.read())
    except FileNotFoundError:
        results = {'message': "File %s not found or no permissions" % filename, 'error': True}
        return results
    except json.JSONDecodeError as e:
        results = {'message': ["Error during parsing %s" % filename, repr(e)], 'error': True}
        return results

    by_market = {}

    for trade_dump in dataset:
        # sort by market-id
        market_id = trade_dump['market-id']

        if market_id not in by_market:
            by_market[market_id] = []

        by_market[market_id].append(trade_dump)

    # process by strategy trader
    for market_id, trades_dumps in by_market.items():
        with strategy._mutex:
            strategy_trader = strategy._strategy_traders.get(market_id)
            if not strategy_trader:
                results.append({'message': "Unable to retrieved strategy-trader for %s" % market_id, 'error': True})

            sub_data = {
                'trades': trades_dumps
            }

            result = cmd_strategy_trader_import(strategy, strategy_trader, sub_data)
            results.append(result)

    return results
