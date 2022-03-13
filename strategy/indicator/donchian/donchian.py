# @date 2019-02-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2016 Dream Overflow
# Donchian channel indicator using low and high prices.

from strategy.indicator.indicator import Indicator
# from strategy.indicator.utils import down_sample
from talib import MIN as ta_MIN, MAX as ta_MAX

import numpy as np


class DonchianIndicator(Indicator):
    """
    Donchian channel indicator using low and high prices.
    """

    __slots__ = '_length', '_prev_low', '_prev_high', '_last_low', '_last_high', '_highs', '_lows'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=30):
        super().__init__("donchian", timeframe)

        self._length = length

        self._prev_low = 0.0
        self._prev_high = 0.0

        self._last_low = 0.0
        self._last_high = 0.0

        self._highs = np.empty(0)
        self._lows = np.empty(0)

    @property
    def prev_low(self):
        return self._prev_low

    @property
    def prev_high(self):
        return self._prev_high

    @property
    def last_low(self):
        return self._last_low

    @property
    def last_high(self):
        return self._last_high

    @property
    def highs(self):
        return self._highs
        
    @property
    def lows(self):
        return self._lows   

    def compute(self, timestamp, high, low):
        self._prev_low = self._last_low
        self._prev_high = self._last_high

        self._lows = ta_MIN(low, self._length)
        self._highs = ta_MAX(high, self._length)

        self._last_low = self._lows[-1]
        self._last_high = self._highs[-1]

        self._last_timestamp = timestamp

        return self._highs, self._lows   
