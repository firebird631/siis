# @date 2019-08-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# @brief MESA Adaptive Moving Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample
from talib import MAMA as ta_MAMA

import numpy as np


class MAMAIndicator(Indicator):
    """
    MESA Adaptive Moving Average indicator
    """

    __slots__ = '_fast_limit', '_slow_limit', '_prev_mama', '_prev_fama', '_last_mama', '_last_fama', '_famas', '_mamas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, fast_limit=0.5, slow_limit=0.05):
        super().__init__("mama", timeframe)

        self._fast_limit = fast_limit    # fast limit [0.01, 0.99]
        self._slow_limit = slow_limit    # slow limit [0.01, 0.99]

        self._prev_mama = 0.0
        self._prev_fama = 0.0
        self._last_mama = 0.0
        self._last_fama = 0.0

        self._famas = np.array([])
        self._mamas = np.array([])

    @property
    def prev_fama(self):
        return self._prev_fama

    @property
    def prev_mama(self):
        return self._prev_mama

    @property
    def last_fama(self):
        return self._last_fama

    @property
    def last_mama(self):
        return self._last_mama

    @property
    def fast_limit(self):
        return self._fast_limit
    
    @fast_limit.setter
    def fast_limit(self, fast_limit):
        self._fast_limit = fast_limit

    @property
    def slow_limit(self):
        return self._slow_limit
    
    @slow_limit.setter
    def slow_limit(self, slow_limit):
        self._slow_limit = slow_limit

    @property
    def famas(self):
        return self._famas

    @property
    def mamas(self):
        return self._mamas

    def cross(self):
        if (self._prev_mama > self._prev_fama and self._last_mama < self._last_fama):
            return -1
        elif (self._prev_mama < self._prev_fama and self._last_mama > self._last_fama):
            return 1

        return 0

    def trend(self):
        return 1 if self._last_mama > self._last_fama else -1 if self._last_mama < self._last_fama else 0

    def compute(self, timestamp, prices):
        self._prev_fama = self._last_fama
        self._prev_mama = self._last_mama

        self._mamas, self._famas = ta_MAMA(prices, fastlimit=self._fast_limit, slowlimit=self._slow_limit)

        self._last_fama = self._famas[-1]
        self._last_mama = self._mamas[-1]
        self._last_timestamp = timestamp

        return self._mamas, self._famas
