# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_strategy_trader_state(strategy, market_id):
    """
    Generate and return an array of all the actives trades :
        symbol: str market identifier
    """
    results = []
    trader = strategy.trader()

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    pass

        except Exception as e:
            error_logger.error(repr(e))

    return results
