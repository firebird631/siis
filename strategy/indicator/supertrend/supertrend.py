# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Super Trend indicator
from instrument.instrument import Instrument
from strategy.indicator.indicator import Indicator
from talib import ATR as ta_ATR

import numpy as np


class SuperTrendIndicator(Indicator):
    """
    Super Trend indicator
    Based on ATR and high/low.
    """

    __slots__ = '_length', '_coeff', '_up_trends', '_dn_trends', '_last_up', '_prev_up', '_last_dn', '_prev_dn'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=14, coeff=3):
        super().__init__("supertrend", timeframe)

        self._length = length  # ATR periods number
        self._coeff = coeff

        self._up_trends = np.array([])
        self._dn_trends = np.array([])

        self._last_up = 0.0
        self._prev_up = 0.0

        self._last_dn = 0.0
        self._prev_dn = 0.0

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, length):
        self._length = length

    @property
    def coeff(self):
        return self._coeff

    @coeff.setter
    def coeff(self, coeff):
        self._coeff = coeff

    @property
    def prev_dn(self):
        return self._prev_dn

    @property
    def prev_up(self):
        return self._prev_up

    @property
    def last_dn(self):
        return self._last_dn

    @property
    def last_up(self):
        return self._last_up

    @property
    def dn_trends(self):
        return self._dn_trends

    @property
    def up_trends(self):
        return self._up_trends

    def trend(self, last_close: float):
        # superTrend = trendDirection == isUpTrend ? lowerBand : upperBand
        if not last_close or self._last_up <= 0 or self._last_dn <= 0:
            return 0

        if last_close > self._last_up:
            return 1
        elif last_close < self._last_dn:
            return -1

        return 0

    def bar_crossing(self, prices: np.array):
        """
        Crossing with the last and previous bars -> at bars.
        """
        # with up-trend
        if prices[-2] > self._up_trends[-2] and prices[-1] < self._up_trends[-1]:
            return -1

        # with dn-trend
        if prices[-2] < self._dn_trends[-2] and prices[-1] > self.dn_trends[-1]:
            return 1

        return 0

    def tick_crossing(self, prev_price: float, last_price: float):
        """
        Crossing with the last and previous computed compared to last and previous price -> at ticks.
        """
        if self._last_dn <= 0 or self._last_up <= 0 or prev_price <= 0 or last_price <= 0:
            return 0

        # marche mieux sur DAX mais pas conforme avec l'indic
        # # with up-trend
        # if prev_price > self._last_up and last_price < self._last_up:
        #     return -1
        #
        # # with dn-trend
        # if prev_price < self._last_dn and last_price > self._last_dn:
        #     return 1

        # conforme et marche mieux sur NAS
        if prev_price > self._last_dn and last_price < self._last_dn:
            return -1

        if prev_price < self._last_up and last_price > self._last_up:
            return 1

        return 0

    def compute(self, timestamp, high, low, close):
        self._prev_up = self._last_up
        self._prev_dn = self._last_dn

        c_atrs = self._coeff * ta_ATR(high, low, close, timeperiod=self._length)
        meds = (high + low) * 0.5

        upper = meds + c_atrs
        lower = meds - c_atrs

        _len = c_atrs.size

        if _len != self._up_trends.size:
            self._up_trends = np.zeros(_len)
            self._dn_trends = np.zeros(_len)

        self._up_trends[0] = upper[0]
        self._dn_trends[0] = lower[0]

        for i in range(1, _len):
            if upper[i] < self._up_trends[i-1] or close[i-1] > self._up_trends[i-1]:
                self._up_trends[i] = upper[i]
            else:
                self._up_trends[i] = upper[i-1]

            if lower[i] > self._dn_trends[i-1] or close[i-1] < self._dn_trends[i-1]:
                self._dn_trends[i] = lower[i]
            else:
                self._dn_trends[i] = lower[i-1]

        self._last_up = self._up_trends[-1]
        self._last_dn = self._dn_trends[-1]

        self._last_timestamp = timestamp

        return self._dn_trends, self._up_trends
