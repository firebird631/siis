# @date 2023-05-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Strategy command trader set news parameters and apply

import copy

from config import utils

import logging
logger = logging.getLogger('siis.strategy.strategycmdstrategytraderparams')


def cmd_strategy_trader_params(strategy, strategy_trader, data):
    """
    Query strategy-trader modify parameters for specific trader/market
    """
    results = {
        'messages': [],
        'error': False
    }

    new_parameters = copy.deepcopy(strategy_trader._initials_parameters)

    learning_config = {
        "strategy": {
            "parameters": data['parameters']
        }
    }

    # merge new parameters
    utils.merge_learning_config(new_parameters, learning_config)

    # display news values
    for n, v in learning_config.get('strategy', {}).get('parameters', {}).items():
        logger.info("-- %s = %s" % (n, v))

    # update strategy trader with new parameters
    try:
        strategy_trader.update_parameters(new_parameters)
    except Exception as e:
        results['error'] = True
        results['messages'].append(str(e))

    return results
