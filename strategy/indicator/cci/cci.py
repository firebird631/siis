# @date 2022-10-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Commodity Channel Index

from strategy.indicator.indicator import Indicator
from talib import CCI as TA_CCI

import numpy as np


class CCIIndicator(Indicator):
    """
    Commodity Channel Index indicator using low and high prices.
    """

    __slots__ = '_length', '_prev', '_last', '_ccis'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=20):
        super().__init__("cci", timeframe)

        self._length = length

        self._prev = 0.0
        self._last = 0.0

        self._ccis = np.empty(0)

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def ccis(self):
        return self._ccis

    def compute(self, timestamp, high, low, close):
        self._prev = self._last

        self._ccis = TA_CCI(high, low, close, timeperiod=self._length)

        self._last = self._ccis[-1]

        self._last_timestamp = timestamp

        return self._ccis
