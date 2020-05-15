# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy display table formatter helpers for views or notifiers

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

from strategy.strategy import Strategy

from strategy.helpers.traderstatedataset import get_strategy_trader_state


import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def trader_state_table(strategy, style='', offset=None, limit=None, col_ofs=None, summ=True):
    pass
