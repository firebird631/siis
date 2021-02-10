# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_closed_trades(strategy):
    """
    Like as get_stats but only return the array of the trade, and complete history.
    """
    results = []

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    results += strategy_trader._stats['success']
                    results += strategy_trader._stats['failed']
                    results += strategy_trader._stats['roe']

        except Exception as e:
            error_logger.error(repr(e))

    return results
