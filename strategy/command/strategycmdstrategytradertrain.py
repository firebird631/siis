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

    parameters = {}

    result = Trainer.caller(strategy.service.identity, strategy.service.profile, strategy.service.learning_path,
                            strategy_trader, strategy.service.profile_config)

    if not result:
        results['error'] = True

    return results
