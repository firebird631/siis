# @date 2021-10-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command import active trades

import json
import time

from common.utils import timeframe_from_str, direction_from_str
from strategy.trade.strategytrade import StrategyTrade


def dehumanize_trade(trade_dump):
    trade_dump['trade'] = StrategyTrade.trade_type_from_str(trade_dump['trade'])
    trade_dump['entry-timeout'] = timeframe_from_str(trade_dump['entry-timeout'])
    # trade_dump['expiry'] = timeframe_from_str(trade_dump['expiry'])

    if 'entry-state' in trade_dump:
        trade_dump['entry-state'] = StrategyTrade.trade_state_from_str(trade_dump['entry-state'])

    if 'exit-state' in trade_dump:
        trade_dump['exit-state'] = StrategyTrade.trade_state_from_str(trade_dump['exit-state'])

    trade_dump['timeframe'] = timeframe_from_str(trade_dump['timeframe'])
    trade_dump['direction'] = direction_from_str(trade_dump['direction'])

    trade_dump['entry-open-time'] = StrategyTrade.load_timestamp(trade_dump['entry-open-time'])
    trade_dump['exit-open-time'] = StrategyTrade.load_timestamp(trade_dump['exit-open-time'])

    # if 'first-realized-entry-datetime' in trade_dump['stats']:
    #     trade_dump['stats']['first-realized-entry-datetime'] = StrategyTrade.load_timestamp(
    #         trade_dump['stats']['first-realized-entry-datetime'])
    #
    # if 'last-realized-entry-datetime' in trade_dump['stats']:
    #     trade_dump['stats']['last-realized-entry-datetime'] = StrategyTrade.load_timestamp(
    #         trade_dump['stats']['last-realized-entry-datetime'])
    #
    # if 'first-realized-exit-datetime' in trade_dump['stats']:
    #     trade_dump['stats']['first-realized-exit-datetime'] = StrategyTrade.load_timestamp(
    #         trade_dump['stats']['first-realized-exit-datetime'])
    #
    # if 'last-realized-exit-datetime' in trade_dump['stats']:
    #     trade_dump['stats']['last-realized-exit-datetime'] = StrategyTrade.load_timestamp(
    #         trade_dump['stats']['last-realized-exit-datetime'])

    return trade_dump


def dehumanize_alert(alert_dump):
    alert_dump['created'] = StrategyTrade.load_timestamp(alert_dump['created'])
    alert_dump['timeframe'] = timeframe_from_str(alert_dump['timeframe']) if alert_dump['timeframe'] else 0
    alert_dump['expiry'] = timeframe_from_str(alert_dump['expiry']) if alert_dump['expiry'] else 0

    return alert_dump


def dehumanize_region(region_dump):
    region_dump['created'] = StrategyTrade.load_timestamp(region_dump['created'])
    region_dump['timeframe'] = timeframe_from_str(region_dump['timeframe']) if region_dump['timeframe'] else 0
    region_dump['expiry'] = timeframe_from_str(region_dump['expiry']) if region_dump['expiry'] else 0

    return region_dump


def cmd_strategy_trader_import(strategy, strategy_trader, data):
    """
    Query strategy-trader import any trade for a specific trader.
    """
    results = {
        'messages': [],
        'error': False
    }

    data_dumps = data.get('data', [])
    dataset = data.get('dataset', "active")

    if dataset == 'active':
        trader = strategy_trader.strategy.trader()

        for trade_dump in data_dumps:
            try:
                dehumanize_trade(trade_dump)
                trade_id = trade_dump['id']
                trade_type = trade_dump['trade']
                operations = trade_dump.get('operations', [])

                strategy_trader.loads_trade(trade_id, trade_type, trade_dump, operations, check=True)
                if not trader.paper_mode:
                    time.sleep(2)

            except Exception as e:
                results['messages'].append("Error during import of trade %s for %s" % (
                    trade_dump.get('id'), strategy_trader.instrument.market_id))
                results['messages'].append(repr(e))
                results['error'] = True

    elif dataset == 'history':
        for trade_dump in data_dumps:
            try:
                with strategy_trader._mutex:
                    if round(trade_dump['profit-loss-pct'] * 10) == 0.0:
                        strategy_trader._stats['roe'].append(trade_dump)
                    elif trade_dump['profit-loss-pct'] > 0:
                        strategy_trader._stats['success'].append(trade_dump)
                    elif trade_dump['profit-loss-pct'] < 0:
                        strategy_trader._stats['failed'].append(trade_dump)
                    else:
                        strategy_trader._stats['roe'].append(trade_dump)

            except Exception as e:
                results['messages'].append("Error during import of trade history %s for %s" % (
                    trade_dump.get('id'), strategy_trader.instrument.market_id))
                results['messages'].append(repr(e))
                results['error'] = True

    elif dataset == 'alert':
        for alert_dump in data_dumps:
            try:
                dehumanize_alert(alert_dump)
                alert_id = alert_dump['id']
                alert_type = alert_dump['alert']

                strategy_trader.loads_alert(alert_id, alert_type, alert_dump)
            except Exception as e:
                results['messages'].append("Error during import of alert %s for %s" % (
                    alert_dump.get('id'), strategy_trader.instrument.market_id))
                results['messages'].append(repr(e))
                results['error'] = True

    elif dataset == 'region':
        for region_dump in data_dumps:
            try:
                dehumanize_region(region_dump)
                region_id = region_dump['id']
                region_type = region_dump['region']

                strategy_trader.loads_region(region_id, region_type, region_dump)
            except Exception as e:
                results['messages'].append("Error during import of region %s for %s" % (
                    region_dump.get('id'), strategy_trader.instrument.market_id))
                results['messages'].append(repr(e))
                results['error'] = True

    elif dataset == 'strategy':
        for strategy_dump in data_dumps:
            trader_dump = strategy_dump.get('trader', {})
            trades_dump = strategy_dump.get('trades', [])
            alerts_dump = strategy_dump.get('alerts', [])
            regions_dump = strategy_dump.get('regions', [])

            trader = strategy_trader.strategy.trader()

            for trade_dump in trades_dump:
                try:
                    # dehumanize_trade(trade_dump)
                    trade_id = trade_dump['id']
                    trade_type = trade_dump['trade']
                    operations = trade_dump.get('operations', [])

                    strategy_trader.loads_trade(trade_id, trade_type, trade_dump,
                                                operations, check=True, force_id=True)
                    if not trader.paper_mode:
                        time.sleep(2)

                except Exception as e:
                    results['messages'].append("Error during import of trade %s for %s" % (
                        trade_dump.get('id'), strategy_trader.instrument.market_id))
                    results['messages'].append(repr(e))
                    results['error'] = True

            try:
                strategy_trader.loads(trader_dump, regions_dump, alerts_dump, force_id=True)
            except Exception as e:
                results['messages'].append("Error during import of strategy-trader for %s" %
                                           strategy_trader.instrument.market_id)
                results['messages'].append(repr(e))
                results['error'] = True

    return results


def cmd_strategy_trader_import_all(strategy, data):
    """
    Query strategy-trader import any trades for any traders from a specified JSON file.
    """
    results = []

    filename = data.get('filename', "")
    dataset = data.get('dataset', "active")

    if dataset not in ('active', 'history', 'alert', 'region', 'strategy'):
        results = {'message': "Unsupported import dataset", 'error': True}
        return results

    if not filename:
        if dataset == 'active':
            filename = "siis_trades.json"
        elif dataset == 'history':
            filename = "siis_history.json"
        elif dataset == 'alert':
            filename = "siis_alerts.json"
        if dataset == 'region':
            filename = "siis_regions.json"
        if dataset == 'strategy':
            filename = "siis_strategy.json"

    try:
        with open(filename, "rt") as f:
            data_dumps = json.loads(f.read())
    except FileNotFoundError:
        results = {'message': "File %s not found or no permissions" % filename, 'error': True}
        return results
    except json.JSONDecodeError as e:
        results = {'message': ["Error during parsing %s" % filename, repr(e)], 'error': True}
        return results

    by_market = {}

    for data_dump in data_dumps:
        # organize by market-id
        market_id = data_dump['market-id']

        if market_id not in by_market:
            by_market[market_id] = []

        by_market[market_id].append(data_dump)

    # process by strategy trader
    for market_id, data_dumps in by_market.items():
        with strategy._mutex:
            strategy_trader = strategy._strategy_traders.get(market_id)
            if not strategy_trader:
                results.append({'message': "Unable to retrieved strategy-trader for %s" % market_id, 'error': True})

            sub_data = {
                'dataset': dataset,
                'data': data_dumps
            }

            result = cmd_strategy_trader_import(strategy, strategy_trader, sub_data)
            results.append(result)

    return results
