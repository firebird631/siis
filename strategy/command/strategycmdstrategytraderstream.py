# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader stream

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytraderbase import StrategyTraderBase


def cmd_strategy_trader_stream(strategy: Strategy, strategy_trader: StrategyTraderBase, data: dict):
    """
    Stream subscribe/unsubscribe to a market.
    """
    results = {
        'messages': [],
        'error': False
    }      

    analyser_name = data.get('analyser', None)
    action = data.get('action', "")
    typename = data.get('type', "")

    if action == "subscribe":
        if typename == "chart":
            strategy_trader.subscribe_stream(analyser_name)
            results['messages'].append("Subscribed for stream %s %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id, analyser_name or "default"))
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
            strategy_trader.unsubscribe_stream(analyser_name)
            results['messages'].append("Unsubscribed from stream %s %s %s" % (
                strategy.identifier, strategy_trader.instrument.market_id, analyser_name or "any"))
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
