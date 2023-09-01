# @date 2023-09-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Hull Moving Three Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import WMA as ta_WMA  # , SMA as ta_SMA

import numpy as np
import math


class HMA3Indicator(Indicator):
    """
    Hull Moving Three Average indicator
    https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/hull-moving-average
    It is a variation with : hma3 = wma(wma(x, len/3)*3 - wma(x, len/2) - wma(x, len), len)
    """

    __slots__ = '_length', '_prev', '_last', '_hma3s'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, length=9):
        super().__init__("hma3", timeframe)

        self._length = length  # periods number
        self._prev = 0.0
        self._last = 0.0

        self._hma3s = np.array([])

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
    def hma3s(self):
        return self._hma3s

    @property
    def values(self):
        return self._hma3s

    def has_values(self, min_samples=1):
        return self._hma3s.size >= min_samples and not np.isnan(self._hma3s[-min_samples])

    @staticmethod
    def hma3_n(n: int, data: np.array):
        n_2 = int(n / 2)
        n_3 = int(n / 3)

        # 1) calculate a WMA with period n / 3 and multiply it by 3
        hma12 = 3.0 * ta_WMA(data, n_3)

        if np.isnan(hma12[-1]):
            return np.array([0.0])

        # 2) calculate a WMA for period n / 2 and subtract if from step 1
        hma12 = hma12 - ta_WMA(data, n_2)

        if np.isnan(hma12[-1]):
            return np.array([0.0])

        # 3) calculate a WMA with period n and subtract it from previous step
        hma12 = hma12 - ta_WMA(data, n)

        if np.isnan(hma12[-1]):
            return np.array([0.0])

        # 4) calculate a WMA with period n using the data from step 3
        hma = ta_WMA(hma12, n)

        return hma

    def compute(self, timestamp, prices):
        self._prev = self._last

        if np.isnan(prices[-1]):
            return self._hma3s

        self._hma3s = HMA3Indicator.hma3_n(self._length, prices)

        self._last = self._hma3s[-1]
        self._last_timestamp = timestamp

        return self._hma3s
