# @date 2018-09-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# IndiceAlpha strategy

import time
import copy

import numpy as np

from terminal.terminal import Terminal
from trader.position import Position
from trader.order import Order

from config import config
from strategy.strategy import Strategy

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from instrument.instrument import Instrument, Candle
from watcher.watcher import Watcher

from charting.charting import Charting
from database.database import Database

from strategy.indicator import utils
from strategy.indicator.score import Score, Scorify
from strategy.strategydatafeeder import StrategyDataFeeder


import logging
logger = logging.getLogger('siis.strategy.indicealpha')


class IndiceAlphaStrategy(Strategy):
    """
    Indice Alpha strategy. Does not use volume information because we don't have them.
    """

    def __init__(self, strategy_service, watcher_service, trader_service, options):
        super().__init__("indicealpha", strategy_service, watcher_service, trader_service, options)

        self.reset()
