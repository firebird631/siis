# @date 2019-12-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Willy norm EMA cross indicator

from strategy.indicator.indicator import Indicator

import numpy as np
from talib import MIN as ta_MIN, MAX as ta_MAX, EMA as ta_EMA


class WillyIndicator(Indicator):
    """
    Willy norm EMA cross indicator.
    Variant of the Williams %R indicator.
    @ref https://fr.tradingview.com/script/eij9KTBO-Willy/

    Range is [0..-100], bands are -80 and -20.
    """

    __slots__ = '_length', '_len_EMA', '_prev', '_last', '_willys', '_emas'

    LOWER_BAND = -80.0
    UPPER_BAND = -20.0

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=21, len_EMA=9):
        super().__init__("willy", timeframe)

        self._length = length    # periods number
        self._len_EMA = len_EMA  # EMA periods number

        self._willys = np.array([])
        self._emas = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def len_EMA(self):
        return self._len_EMA
    
    @len_EMA.setter
    def len_EMA(self, len_EMA):
        self._len_EMA = len_EMA

    @property
    def emas(self):
        return self._emas

    @property
    def willys(self):
        return self._willys

    def cross(self):
        """Willy cross its EMA"""
        if self._willys[-2] < self._emas[-2] and self._willys[-1] > self._emas[-1]:
            return 1

        elif self._willys[-2] > self._emas[-2] and self._willys[-1] < self._emas[-1]:
            return -1

        return 0

    def cross_lb(self):
        """Willy cross the lower band"""
        if self._willys[-2] > self.LOWER_BAND and self._willys[-1] < self.LOWER_BAND:
            return -1

        elif self._willys[-2] < self.LOWER_BAND and self._willys[-1] > self.LOWER_BAND:
            return 1

        return 0

    def cross_hb(self):
        """Willy cross the upper band"""
        if self._willys[-2] > self.UPPER_BAND and self._willys[-1] < self.UPPER_BAND:
            return -1

        elif self._willys[-2] < self.UPPER_BAND and self._willys[-1] > self.UPPER_BAND:
            return 1

        return 0

    def compute(self, timestamp, high, low, close):
        upper = ta_MAX(high, self._length)
        lower = ta_MIN(low, self._length)

        with np.errstate(divide='ignore', invalid='ignore'):
            # replace by 0 when divisor is 0
            self._willys = 100.0 * (close - upper) / (upper - lower)
            self._willys[self._willys == np.inf] = 0.0

        try:
            self._emas = ta_EMA(self._willys, self._len_EMA)
        except:
            self._emas = np.array(len(close)*[np.NaN])

        self._last_timestamp = timestamp

        return self._willys, self._emas
