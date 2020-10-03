# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Parabolic SAR indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import numpy as np
from talib import SAR as ta_SAR


class SARIndicator(Indicator):
    """
    Parabolic SAR indicator
    """

    __slots__ = '_acceleration', '_maximum', '_prev', '_last', '_sars'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, acceleration=0, maximum=0):
        super().__init__("sar", timeframe)

        self._acceleration = acceleration
        self._maximum = maximum

        self._prev = 0.0
        self._last = 0.0

        self._sars = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def acceleration(self):
        return self._acceleration
    
    @acceleration.setter
    def acceleration(self, acceleration):
        self._acceleration = acceleration

    @property
    def maximum(self):
        return self._maximum
    
    @maximum.setter
    def maximum(self, maximum):
        self._maximum = maximum

    @property
    def sars(self):
        return self._sars

    def compute(self, timestamp, prices):
        self._prev = self._last
        self._sars = ta_SAR(high, low, acceleration=self._acceleration, maximum=self._maximum)

        self._last = self._sars[-1]
        self._last_timestamp = timestamp

        return self._sars
