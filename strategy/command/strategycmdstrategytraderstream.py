# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader stream

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytrader import StrategyTrader

from common.utils import timeframe_from_str


def cmd_strategy_trader_stream(strategy: Strategy, strategy_trader: StrategyTrader, data: dict):
    """
    Stream subscribe/unsubscribe to a market.
    """
    results = {
        'messages': [],
        'error': False
    }      

    timeframe = data.get('timeframe', None)
    action = data.get('action', "")
    typename = data.get('type', "")

    if action == "subscribe":
        if typename == "chart":
            strategy_trader.subscribe_stream(timeframe_from_str(timeframe))
            results['messages'].append("Subscribed for stream %s %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id, timeframe or "default"))
        elif typename == "info":
            strategy_trader.subscribe_info()
            results['messages'].append("Subscribed for stream info %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id))
        else:
            # unsupported type
            results['error'] = True
            results['messages'].append("Unsupported stream %s for trader %s" % (
                typename, strategy_trader.instrument.market_id))

    elif action == "unsubscribe":
        if typename == "chart":            
            strategy_trader.unsubscribe_stream(timeframe_from_str(timeframe))
            results['messages'].append("Unsubscribed from stream %s %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id, timeframe or "any"))
        elif typename == "info":
            strategy_trader.unsubscribe_info()
            results['messages'].append("Unsubscribed from stream info %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id))
        else:
            # unsupported type
            results['error'] = True
            results['messages'].append("Unsupported stream %s for trader %s" % (
                typename, strategy_trader.instrument.market_id))

    else:
        # unsupported action
        results['error'] = True
        results['messages'].append("Unsupported stream action %s for trader %s" % (
            action, strategy_trader.instrument.market_id))

    return results
