# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Super Trend indicator

from strategy.indicator.indicator import Indicator
from talib import ATR as ta_ATR

import numpy as np


import logging
logger = logging.getLogger('siis.strategy.supertrend')


class SuperTrendIndicator(Indicator):
    """
    Super Trend indicator
    Based on ATR and high/low.
    """

    __slots__ = '_length', '_coeff', '_up_trends', '_dn_trends', '_last_up', '_prev_up', '_last_dn', '_prev_dn', \
        '_trends', '_prev', '_last', '_position'

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
        self._trends = np.array([])

        self._last_up = 0.0
        self._prev_up = 0.0

        self._last_dn = 0.0
        self._prev_dn = 0.0

        self._last = 0.0
        self._prev = 0.0

        self._position = 0

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
    def prev(self):
        return self._prev

    @property
    def prev_dn(self):
        return self._prev_dn

    @property
    def prev_up(self):
        return self._prev_up

    @property
    def last(self):
        return self._last

    @property
    def last_dn(self):
        return self._last_dn

    @property
    def last_up(self):
        return self._last_up

    @property
    def trends(self):
        return self.trends

    @property
    def dn_trends(self):
        return self._dn_trends

    @property
    def up_trends(self):
        return self._up_trends

    @property
    def position(self):
        return self._position

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
        # if self._last_dn <= 0 or self._last_up <= 0 or prev_price <= 0 or last_price <= 0:
        #     return 0

        # marche mieux sur DAX mais pas conforme avec l'indic
        # # with up-trend
        # if prev_price > self._last_up and last_price < self._last_up:
        #     return -1
        #
        # # with dn-trend
        # if prev_price < self._last_dn and last_price > self._last_dn:
        #     return 1

        # # conforme et marche mieux sur NAS
        # if prev_price > self._last_dn and last_price < self._last_dn:
        #     return -1
        #
        # if prev_price < self._last_up and last_price > self._last_up:
        #     return 1

        if prev_price > self._last and last_price < self._last:
            return -1

        if prev_price < self._last and last_price > self._last:
            return 1

        return 0

    def compute(self, timestamp, high, low, close):
        self._prev_up = self._last_up
        self._prev_dn = self._last_dn
        self._prev = self._last

        c_atrs = self._coeff * ta_ATR(high, low, close, timeperiod=self._length)
        atrs = ta_ATR(high, low, close, timeperiod=self._length)
        meds = (high + low) * 0.5

        _len = close.size

        c_atrs[np.isnan(c_atrs)] = 0.0

        # for i in range(0, _len):
        #     if np.isnan(c_atrs[i]):
        #         c_atrs[i] = 0.0

        upper = meds + c_atrs
        lower = meds - c_atrs

        if _len != self._up_trends.size:
            self._up_trends = np.zeros(_len)
            self._dn_trends = np.zeros(_len)
            self._trends = np.zeros(_len)

        # for i in range(1, _len):
        #     _high = high[i]
        #     _low = low[i]
        #     _close = close[i-1]
        #
        #     self._up_trends[i] = (_high + _low) / 2 + self._coeff * atrs[i]
        #     self._dn_trends[i] = (_high + _low) / 2 - self._coeff * atrs[i]
        #
        #     if _close <= self._up_trends[i-1]:
        #         self._trends[i] = self._up_trends[i]
        #     else:
        #         self._trends[i] = self._dn_trends[i]

        # self._trends[0] = (high[0] + low[0]) / 2
        #
        # for i in range(1, _len):
        #     if close[i-1] <= self._trends[i-1]:
        #         self._trends[i] = max(upper[i], close[i-1])
        #     else:
        #         self._trends[i] = min(lower[i], close[i-1])

        in_long_position = False  # Indique si vous êtes en position longue

        # first trend
        if close[0] <= upper[0]:
            self._trends[0] = upper[0]
            in_long_position = True
        else:
            self._trends[0] = lower[0]
            in_long_position = False

        for i in range(1, len(close)):
            if close[i] <= self._trends[i - 1] and not in_long_position:
                self._trends[i] = max(upper[i], close[i])
                in_long_position = True
            elif close[i] >= self._trends[i - 1] and in_long_position:
                self._trends[i] = min(lower[i], close[i])
                in_long_position = False
            else:
                self._trends[i] = self._trends[i - 1]

        # for i in range(1, _len):
        #     if upper[i] < self._up_trends[i-1] and close[i-1] < self._up_trends[i-1]:
        #         self._up_trends[i] = upper[i]
        #     else:
        #         self._up_trends[i] = self._up_trends[i-1]
        #
        #     if lower[i] > self._dn_trends[i-1] and close[i-1] > self._dn_trends[i-1]:
        #         self._dn_trends[i] = lower[i]
        #     else:
        #         self._dn_trends[i] = self._dn_trends[i-1]

        self._last_up = self._up_trends[-1]
        self._last_dn = self._dn_trends[-1]
        self._last = self._trends[-1]

        # if close[-1] > self._last:
        #     self._position = 1
        # elif close[-1] < self._last:
        #     self._position = -1
        # else:
        #     self._position = 0

        # logger.debug("%g %g %g %g %i" % (close[-1], self._last_dn, self._last_up, self._last, self._position))

        self._last_timestamp = timestamp

        return self._dn_trends, self._up_trends
