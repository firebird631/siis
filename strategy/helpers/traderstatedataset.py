# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_strategy_trader_state(strategy, market_id, report_mode=0):
    """
    Generate and return an array of all the actives trades :
        symbol: str market identifier
    """
    results = {
        'market-id': market_id,
        'activity': False,
        'bootstraping': False,
        'ready': False,
        'members': [],
        'data': [],
        'num-modes': 1
    }

    trader = strategy.trader()

    with strategy._mutex:
        try:
            strategy_trader = strategy._strategy_traders.get(market_id)
            with strategy_trader._mutex:
                results = strategy_trader.report_state(report_mode)

        except Exception as e:
            error_logger.error(repr(e))

    return results
