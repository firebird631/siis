# @date 2023-04-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Strategy command trader restart

from strategy.learning.trainer import Trainer


def cmd_strategy_trader_train(strategy, strategy_trader, data):
    """
    Query strategy-trader train for specific trader/market
    """
    results = {
        'messages': [],
        'error': False
    }

    if strategy_trader.has_trainer:
        result = strategy_trader.trainer.start()
        if not result:
            results['error'] = True
            results['messages'].append("Unable to start trainer for %s" % strategy_trader.instrument.market_id)
    else:
        results['error'] = True
        results['messages'].append("Missing trainer config for %s" % strategy_trader.instrument.market_id)

    return results
