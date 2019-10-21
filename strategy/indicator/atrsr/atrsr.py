# @date 2019-10-18
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Average True Range support and resistance indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import MM_n, down_sample
from talib import ATR as ta_ATR, EMA as ta_EMA, MAX as ta_MAX, MIN as ta_MIN, SMA as ta_SMA

import numpy as np


class ATRSRIndicator(Indicator):
    """
    Average True Range Support and Resistance indicator
    """

    __slots__ = '_length', '_coeff', '_length_MA', '_support', '_resistance', '_last_support', '_prev_support', '_last_resistance', '_prev_resistance'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=14, coeff=2, length_MA=7):
        super().__init__("atrsr", timeframe)

        self._compute_at_close = True  # only at close

        self._length = length   # MA periods number
        self._coeff = coeff
        self._length_MA = length_MA

        self._support = np.array([])
        self._resistance = np.array([])

        self._last_support = 0.0
        self._prev_support = 0.0

        self._last_resistance = 0.0
        self._prev_resistance = 0.0

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def prev_support(self):
        return self._prev_support

    @property
    def last_support(self):
        return self._last_support

    @property
    def prev_resistance(self):
        return self._prev_resistance

    @property
    def last_resistance(self):
        return self._last_resistance

    def stop_loss(self, direction, last_price):
        if direction > 0:
            stop_loss = 0.0

            for x in self._support:
                if last_price > x:
                    stop_loss = x

            return x

        elif direction < 0:
            stop_loss = 0.0

            for x in self._resistance:
                if last_price < x:
                    stop_loss = x

            return x

        return 0.0

    def compute(self, timestamp, high, low, close):
        self._prev_resistance = self._last_resistance
        self._prev_support = self._last_support

        # @todo
        # basis = ta_SMA(close, self._length)
        # atrs = ta_ATR(high, low, close, timeperiod=self._length)
        
        # dev = atrs * self._coeff
        # upper = basis + dev
        # lower = basis - dev
        
        # bbr = (close - lower) / (upper - lower)
        # bbe = ta_EMA(bbr, self._length_MA)

        # up = bbe if bbe[-2] > bbe[-1] and bbe[-3] < bbe[-2] else np.NaN
        # bt = bbe if bbe[-2] > bbe[-1] and bbe[-3] > bbe[-2] else np.NaN

        # topH = ta_MAX(high, 3) if not np.isnan(up) else np.NaN
        # bottomL = ta_MIN(low, 3) if not np.isnan(bt) else np.NaN

        # # ...

        # self._last_support = self._support[-1]
        # self._last_resistance = self._resistance[-1]

        self._last_timestamp = timestamp

        return self._atrs
