# @date 2024-07-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Kaufman Adaptive Moving Average indicator

from strategy.indicator.indicator import Indicator
from talib import KAMA as ta_KAMA

import numpy as np


class KAMAIndicator(Indicator):
    """
    Kaufman Adaptative Moving Average indicator
    @see https://corporatefinanceinstitute.com/resources/career-map/sell-side/capital-markets/kaufmans-adaptive-moving-average-kama/

    @note Works with both temporal and non-temporal bars.
    """

    __slots__ = '_length', '_fast', '_slow', '_prev', '_last', '_kamas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self, timeframe, length=10, fast=2, slow=30):
        super().__init__("kama", timeframe)

        self._length = length   # periods number
        self._fast = fast       # EMA fast period
        self._slow = slow       # EMA slow period
        self._prev = 0.0
        self._last = 0.0

        self._kamas = np.array([])

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
    def kamas(self):
        return self._kamas

    @property
    def values(self):
        return self._kamas

    def has_values(self, min_samples=1):
        return self._kamas.size >= min_samples and not np.isnan(self._kamas[-min_samples])

    def compute(self, timestamp, prices):
        self._prev = self._last

        if np.isnan(prices[-1]):
            return self._kamas

        self._kamas = ta_KAMA(prices, timeperiod=self._length)  #, self._fast, self._slow)

        self._last = self._kamas[-1]
        self._last_timestamp = timestamp

        return self._kamas
