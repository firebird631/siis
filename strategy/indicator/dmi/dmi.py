# @date 2019-02-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2016 Dream Overflow
# Directional moving index indicator using close, low and high prices.

from strategy.indicator.indicator import Indicator
from talib import PLUS_DI as TA_PLUS_DI, MINUS_DI as TA_MINUS_DI

import numpy as np


class DMIIndicator(Indicator):
    """
    Directional Moving Index indicator using low and high prices.

    @note Works with both temporal and non-temporal bars.
    """

    __slots__ = '_length', '_prev_dp', '_prev_dm', '_last_dp', '_last_dm', '_dps', '_dms'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TIMEFRAME | Indicator.BASE_TICKBAR

    def __init__(self, timeframe, length=14):
        super().__init__("dmi", timeframe)

        self._length = length

        self._prev_dp = 0.0
        self._prev_dm = 0.0

        self._last_dp = 0.0
        self._last_dm = 0.0

        self._dps = np.empty(0)
        self._dms = np.empty(0)

    @property
    def prev_dp(self):
        return self._prev_dp

    @property
    def prev_dm(self):
        return self._prev_dm

    @property
    def last_dp(self):
        return self._last_dp

    @property
    def last_dm(self):
        return self._last_dm

    @property
    def dps(self):
        return self._dps

    @property
    def dms(self):
        return self._dms   

    def has_values(self, min_samples=1):
        return self._dps.size >= min_samples and not np.isnan(self._dps[-min_samples])

    def compute(self, timestamp, high, low, close):
        self._prev_dp = self._last_dp
        self._prev_dm = self._last_dm

        self._dps = TA_PLUS_DI(high, low, close, timeperiod=self._length)
        self._dms = TA_MINUS_DI(high, low, close, timeperiod=self._length)

        self._last_dp = self._dps[-1]
        self._last_dm = self._dms[-1]

        self._last_timestamp = timestamp

        return self._dps, self._dms
