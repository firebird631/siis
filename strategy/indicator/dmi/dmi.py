# @date 2019-02-16
# @author Frederic SCHERMA
# @license Copyright (c) 2016 Dream Overflow
# Directionnal moving index indicator using close, low and high prices.

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample
from talib import PLUS_DI as ta_PLUS_DI, MINUS_DI as ta_MINUS_DI

import numpy as np


class DMIIndicator(Indicator):
    """
    Directionnal Moving Index indicator using low and high prices.
    """

    __slots__ = '_length', '_prev_dp', '_prev_dm', '_last_dp', '_last_dm', '_dps', '_dms'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

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
    def prev_da(self):
        return self._prev_da

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

    def compute(self, timestamp, high, low, close):
        self._prev_dp = self._last_dp
        self._prev_dm = self._last_dm

        self._dps = ta_PLUS_DI(high, low, close, timeperiod=14)
        self._dms = ta_MINUS_DI(high, low, close, timeperiod=14)

        self._last_dp = self._dps[-1]
        self._last_dm = self._dms[-1]

        self._last_timestamp = timestamp

        return self._dps, self._dms
