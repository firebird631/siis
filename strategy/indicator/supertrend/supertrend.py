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

    __slots__ = '_length', '_coeff', '_trends', '_ups', '_downs', '_positions', '_prev', '_last'

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
        self._ups = np.array([])
        self._downs = np.array([])
        self._positions = np.array([])

        self._last = 0.0
        self._prev = 0.0

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
        return self._positions[-1] if self._positions.size > 2 else 0

    @property
    def position_change(self):
        if self._positions.size > 2:
            return self._positions[-1] if self._positions[-1] != self._positions[-2] else 0

        return 0

    def bar_crossing(self, prices: np.array):
        """
        Crossing with the last and previous bars -> at bars.
        """
        # with up-trend
        # if prices[-2] > self._up_trends[-2] and prices[-1] < self._up_trends[-1]:
        #     return -1

        # # with dn-trend
        # if prices[-2] < self._dn_trends[-2] and prices[-1] > self.dn_trends[-1]:
        #     return 1

        return 0

    def tick_crossing(self, prev_price: float, last_price: float):
        """
        Crossing with the last and previous computed compared to last and previous price -> at ticks.
        """
        if self._trends.size < 3 or self._trends[-2] <= 0.0 or self._trends[-1] <= 0.0:
            return 0

        if last_price > self._trends[-1]:
            return 1

        if last_price < self._trends[-1]:
            return -1

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

        upper = meds - c_atrs
        lower = meds + c_atrs

        if _len != self._trends.size:
            self._trends = np.zeros(_len)
            self._ups = np.zeros(_len)
            self._downs = np.zeros(_len)
            self._positions = np.zeros(_len)

        for i in range(1, len(close)):
            # TrendUp := close[1]>TrendUp[1]? max(Up,TrendUp[1]) : Up
            # TrendDown := close[1]<TrendDown[1]? min(Dn,TrendDown[1]) : Dn
            self._ups[i] = max(upper[i], self._ups[i-1]) if close[i-1] > self._ups[i-1] else upper[i]
            self._downs[i] = min(lower[i], self._downs[i-1]) if close[i-1] < self._downs[i-1] else lower[i]

        self._positions[0] = 1  # start with 1

        for i in range(1, len(close)):
            # Trend := close > TrendDown[1] ? 1: close < TrendUp[1]? -1: nz(Trend[1],1)
            if close[i] > self._downs[i-1]:
                self._positions[i] = 1
            elif close[i] < self._ups[i-1]:
                self._positions[i] = -1
            else:
                self._positions[i] = self._positions[i-1]

            # Tsl := Trend==1? TrendUp: TrendDown
            self._trends[i] = self._ups[i] if self._positions[i] > 0 else self._downs[i]

        self._last = self._trends[-1]

        # logger.debug("%g %s %s %s %i" % (close[-1], lower[-2:], upper[-2:], self._trends[-4:], self._position))
        # logger.info("T %s" % list(self._trends))
        # logger.info("C %s" % list(close))

        self._last_timestamp = timestamp

        return self._trends
