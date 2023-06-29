# @date 2023-04-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Average Directional Index ADX

from strategy.indicator.indicator import Indicator
from talib import ADX as TA_ADX

import numpy as np


class ADXIndicator(Indicator):
    """
    Average Directional Index indicator using low and high prices.
    """

    __slots__ = '_length', '_prev', '_last', '_adxs'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=14):
        super().__init__("adx", timeframe)

        self._length = length

        self._prev = 0.0
        self._last = 0.0

        self._adxs = np.empty(0)

    @property
    def length(self) -> int:
        return self._length

    @property
    def prev(self) -> float:
        return self._prev

    @property
    def last(self) -> float:
        return self._last

    @property
    def adxs(self) -> np.array:
        return self._adxs

    @property
    def values(self) -> np.array:
        return self._adxs

    def has_values(self, min_samples=1) -> bool:
        return self._adxs.size >= min_samples and not np.isnan(self._adxs[-min_samples])

    def compute(self, timestamp, high, low, close):
        self._prev = self._last

        self._adxs = TA_ADX(high, low, close, timeperiod=self._length)

        self._last = self._adxs[-1]

        self._last_timestamp = timestamp

        return self._adxs
