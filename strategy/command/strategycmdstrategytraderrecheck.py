# @date 2021-08-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy command trader recheck

def cmd_strategy_trader_recheck(strategy, strategy_trader, data):
    """
    Query strategy-trader recheck any trade for a specific trader.
    """
    results = {
        'messages': [],
        'error': False
    }

    strategy_trader.recheck()
    strategy.send_update_strategy_trader(strategy_trader.instrument.market_id)

    return results


def cmd_strategy_trader_recheck_all(strategy, data):
    """
    Query strategy-trader recheck any trades for any traders.
    """
    results = []

    with strategy._mutex:
        for k, strategy_trader in strategy._strategy_traders.items():
            results.append(cmd_strategy_trader_recheck(strategy, strategy_trader, data))

    return results
