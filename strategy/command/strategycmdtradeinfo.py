# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trade info

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytrader import StrategyTrader


def cmd_trade_info(strategy: Strategy, strategy_trader: StrategyTrader, data: dict) -> dict:
    """
    Get trade info according data on given strategy_trader.

    @note If trade-id is -1 assume the last trade.
    """        
    results = {
        'messages': [],
        'error': False
    }

    trade_id = -1

    try:
        trade_id = int(data.get('trade-id'))
    except Exception:
        results['error'] = True
        results['messages'].append("Invalid trade identifier")

    if results['error']:
        return results

    trade = None

    with strategy_trader._mutex:
        if trade_id == -1 and strategy_trader.trades:
            trade = strategy_trader.trades[-1]
        else:
            for t in strategy_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            # info
            results['messages'] += trade.info_report(strategy_trader)

            # operations
            if trade.operations:
                results['messages'].append("-----")
                results['messages'].append("Operations %i :" % len(trade.operations))

                for operation in trade.operations:
                    results['messages'].append(" - #%i: %s" % (operation.id, operation.str_info()))
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

    return results
