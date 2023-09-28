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

    __slots__ = '_length', '_coeff', '_trends', '_prev', '_last', '_position'

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

        self._trends = np.array([])

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
    def last(self):
        return self._last

    @property
    def trends(self):
        return self.trends

    @property
    def position(self):
        return self._position

    def bar_crossing(self, prices: np.array):
        """
        Crossing with the last and previous bars -> at bars.
        """
        # with up-trend
        # if prices[-2] > self._up_trends[-2] and prices[-1] < self._up_trends[-1]:
        #     return -1
        #
        # # with dn-trend
        # if prices[-2] < self._dn_trends[-2] and prices[-1] > self.dn_trends[-1]:
        #     return 1

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

        if self._trends.size < 2:
            return 0

        if prev_price < self._trends[-2] and last_price > self._trends[-1]:
            return 1

        elif prev_price > self._trends[-2] and last_price < self._trends[-1]:
            return -1

        return 0

    def compute(self, timestamp, high, low, close):
        self._prev = self._last

        c_atrs = self._coeff * ta_ATR(high, low, close, timeperiod=self._length)
        # atrs = ta_ATR(high, low, close, timeperiod=self._length)
        meds = (high + low) * 0.5

        _len = close.size

        c_atrs[np.isnan(c_atrs)] = 0.0

        upper = meds + c_atrs
        lower = meds - c_atrs

        if _len != self._trends.size:
            self._trends = np.zeros(_len)

        # first trend
        if close[0] <= upper[0]:
            self._trends[0] = upper[0]
            is_long = True
        else:
            self._trends[0] = lower[0]
            is_long = False

        for i in range(1, len(close)):
            if close[i] <= self._trends[i-1] and not is_long:
                self._trends[i] = max(upper[i], close[i])
                is_long = True

            elif close[i] >= self._trends[i-1] and is_long:
                self._trends[i] = min(lower[i], close[i])
                is_long = False
            else:
                self._trends[i] = self._trends[i-1]

        self._last = self._trends[-1]

        # logger.debug("%g %s %s %s %i" % (close[-1], lower[-2:], upper[-2:], self._trends[-4:], self._position))
        # logger.info("T %s" % list(self._trends))
        # logger.info("C %s" % list(close))

        self._last_timestamp = timestamp

        return self._trends
