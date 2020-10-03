# @date 2018-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Supports and resistances detection using pivot point method.

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import copy
import sys
import numpy as np


class PivotPointIndicator(Indicator):
    """
    Supports and resistances detection using pivot point method.

    @ref https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/pivot-points-resistance-support
    @ref https://www.andlil.com/les-points-pivots-dans-le-trading-430.html
    @ref https://www.andlil.com/points-pivots-de-camarilla-440.html
    @ref https://www.andlil.com/point-pivot-de-woodie-445.html

    Classical:
    Pivot = (H + B + C) / 3
    S1 = (2 x Pivot) - H
    S2 = Pivot - (H - B)
    S3 = B - 2 x (H - Pivot)
    ...
    R1 = (2 x Pivot) - B
    R2 = Pivot + (H - B)
    R3 = H + 2x (Pivot - B)

    Camarilla:
    Pivot = C
    S1 = C - (H - L) * 1.1/12
    S2 = C - (H - L) * 1.1/6
    S3 = C - (H - L) * 1.1/4
    S4 = C - (H - L) * 1.1/2
    R4 = C + (H - L) * 1.1/2
    R3 = C + (H - L) * 1.1/4
    R2 = C + (H - L) * 1.1/6
    R1 = C + (H - L) * 1.1/12

    Woodie:
    Pivot = (H + L + 2 x C) / 4
    Like as classicial
    """

    METHOD_CLASSICAL = 0
    METHOD_CLASSICAL_OHLC = 1
    METHOD_CLASSICAL_OHL = 2
    METHOD_CAMARILLA = 3
    METHOD_WOODIE = 4
    METHOD_FIBONACCI = 5

    __slots__ = '_method', '_pivot', '_supports', '_resistances', '_last_supports', '_last_resistances', '_last_pivot', '_num'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, method=METHOD_CLASSICAL, num=6):
        super().__init__("pivotpoint", timeframe)

        self._compute_at_close = True  # only at close

        if method == self.METHOD_CAMARILLA:
            num = 4
        elif method == self.METHOD_FIBONACCI:
            num = 4
        else:
            num = min(max(3, num), 10)  # at least 3 supports/resistances

        self._method = method
        self._num = num

        self._pivot = np.array([])
        self._supports = [None]*num
        self._resistances = [None]*num

        for n in range(0, num):
            self._supports[n] = np.array([])
            self._resistances[n] = np.array([])

        self._last_supports = [0.0]*num
        self._last_resistances = [0.0]*num
        self._last_pivot = 0.0

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def method(self):
        return self._method
    
    @property
    def price_mode(self):
        return self._price_mode
    
    @property
    def last_supports(self):
        return self._last_supports
    
    @property
    def last_resistances(self):
        return self._last_resistances

    @property
    def last_pivot(self):
        return self._last_pivot

    @property
    def prev_supports(self):
        return self._prev_supports
    
    @property
    def prev_resistances(self):
        return self._prev_resistances

    @property
    def prev_pivot(self):
        return self._prev_pivot

    @property
    def pivot(self):
        return self._pivot

    @property
    def supports(self):
        return self._supports

    @property
    def resistances(self):
        return self._resistances

    @property
    def num(self):
        return self._num
    
    # @staticmethod
    # def PivotPoint(method, _open, high, low, close):
    #     """ 
    #     Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
    #     """
    #     if method == PivotPointIndicator.METHOD_CAMARILLA:
    #         pivot = close

    #         s1 = close - (high - low)*1.1/12
    #         s2 = close - (high - low)*1.1/6
    #         s3 = close - (high - low)*1.1/4

    #         r1 = close + (high - low)*1.1/12
    #         r2 = close + (high - low)*1.1/6
    #         r3 = close + (high - low)*1.1/4

    #     elif method == PivotPointIndicator.METHOD_FIBONACCI:
    #         pivot = close

    #         s1 = close - (high - low)*0.382
    #         s2 = close - (high - low)*0.618
    #         s3 = close - (high - low)*0.764

    #         r1 = close + (high - low)*0.382
    #         r2 = close + (high - low)*0.618
    #         r3 = close + (high - low)*0.764

    #     else:  # classical or woodie
    #         if method == PivotPointIndicator.METHOD_CLASSICAL:
    #             pivot = (high + low + close) / 3.0
    #         elif method == PivotPointIndicator.METHOD_CLASSICAL_OHLC:
    #             pivot = (high + low + close + _open) / 4.0
    #         elif method == PivotPointIndicator.METHOD_CLASSICAL_OHL:
    #             pivot = (high + low + _open) / 3.0
    #         elif method == PivotPointIndicator.METHOD_WOODIE:
    #             pivot = (high + low + 2.0 * close) / 4.0

    #         s1 = (2.0 * pivot) - high
    #         s2 = pivot - (high - low)
    #         s3 = low - 2.0 * (high - pivot)
            
    #         r1 = (2.0 * pivot) - low
    #         r2 = pivot + (high - low)
    #         r3 = high + 2.0 * (pivot - low)

    #     return pivot, (s1, s2, s3), (r1, r2, r3)

    def _pivotpoint3(self, _open, high, low, close):
        """ 
        Compute pivot, 3 supports and 3 resistances
        """
        size = len(close)

        if len(self._pivot) != size:
            self._pivot = np.zeros(size)

            for i in range(0, self._num):
                self._supports[i] = np.zeros(size)
                self._resistances[i] = np.zeros(size)

        if self._method == PivotPointIndicator.METHOD_CAMARILLA:
            for i in range(0, size-1):
                self._pivot[i+1] = close[i]

                self._supports[0][i+1] = close[i] - (high[i] - low[i])*1.1/12
                self._supports[1][i+1] = close[i] - (high[i] - low[i])*1.1/6
                self._supports[2][i+1] = close[i] - (high[i] - low[i])*1.1/4
                self._supports[3][i+1] = close[i] - (high[i] - low[i])*1.1/2

                self._resistances[0][i+1] = close[i] + (high[i] - low[i])*1.1/12
                self._resistances[1][i+1] = close[i] + (high[i] - low[i])*1.1/6
                self._resistances[2][i+1] = close[i] + (high[i] - low[i])*1.1/4
                self._resistances[3][i+1] = close[i] + (high[i] - low[i])*1.1/2

        elif self._method == PivotPointIndicator.METHOD_FIBONACCI:
            for i in range(0, size-1):
                self._pivot[i+1] = close[i]

                # or 100 618 382
                self._supports[0][i+1] = close[i] - (high[i] - low[i])*0.382
                self._supports[1][i+1] = close[i] - (high[i] - low[i])*0.618
                self._supports[2][i+1] = close[i] - (high[i] - low[i])*0.764
                self._supports[3][i+1] = close[i] - (high[i] - low[i])  # 100%

                self._resistances[0][i+1] = close[i] + (high[i] - low[i])*0.382
                self._resistances[1][i+1] = close[i] + (high[i] - low[i])*0.618
                self._resistances[2][i+1] = close[i] + (high[i] - low[i])*0.764
                self._resistances[3][i+1] = close[i] + (high[i] - low[i])  # 100%

        else:  # classical or woodie
            if self._method == PivotPointIndicator.METHOD_CLASSICAL:
                for i in range(0, size-1):
                    self._pivot[i+1] = (high[i] + low[i] + close[i]) / 3.0

                    self._supports[0][i+1] = (2.0 * self._pivot[i+1]) - high[i]
                    self._supports[1][i+1] = self._pivot[i+1] - (high[i] - low[i])
                    # self._supports[2][i+1] = low[i] - 2.0 * (high[i] - self._pivot[i+1])

                    self._resistances[0][i+1] = (2.0 * self._pivot[i+1]) - low[i]
                    self._resistances[1][i+1] = self._pivot[i+1] + (high[i] - low[i])
                    # self._resistances[2][i+1] = high[i] + 2.0 * (self._pivot[i+1] - low[i])

                for n in range(2, self._num):
                    for i in range(0, size-1):
                        self._supports[n][i+1] = low[i] - n * (high[i] - self._pivot[i+1])
                        self._resistances[n][i+1] = high[i] + n * (self._pivot[i+1] - low[i])

            elif self._method == PivotPointIndicator.METHOD_CLASSICAL_OHLC:
                for i in range(0, size-1):
                    self._pivot[i+1] = (high[i] + low[i] + close[i] + _open[i]) / 4.0

                    self._supports[0][i+1] = (2.0 * self._pivot[i+1]) - high[i]
                    self._supports[1][i+1] = self._pivot[i+1] - (high[i] - low[i])
                    # self._supports[2][i+1] = low[i] - 2.0 * (high[i] - self._pivot[i+1])

                    self._resistances[0][i+1] = (2.0 * self._pivot[i+1]) - low[i]
                    self._resistances[1][i+1] = self._pivot[i+1] + (high[i] - low[i])
                    # self._resistances[2][i+1] = high[i] + 2.0 * (self._pivot[i+1] - low[i])

                for n in range(2, self._num):
                    for i in range(0, size-1):
                        self._supports[n][i+1] = low[i] - n * (high[i] - self._pivot[i+1])
                        self._resistances[n][i+1] = high[i] + n * (self._pivot[i+1] - low[i])

            elif self._method == PivotPointIndicator.METHOD_CLASSICAL_OHL:
                for i in range(0, size-1):
                    self._pivot[i+1] = (high[i] + low[i] + _open[i]) / 3.0

                    self._supports[0][i+1] = (2.0 * self._pivot[i+1]) - high[i]
                    self._supports[1][i+1] = self._pivot[i+1] - (high[i] - low[i])
                    # self._supports[2][i+1] = low[i] - 2.0 * (high[i] - self._pivot[i+1])

                    self._resistances[0][i+1] = (2.0 * self._pivot[i+1]) - low[i]
                    self._resistances[1][i+1] = self._pivot[i+1] + (high[i] - low[i])
                    # self._resistances[2][i+1] = high[i] + 2.0 * (self._pivot[i+1] - low[i])

                for n in range(2, self._num):
                    for i in range(0, size-1):
                        self._supports[n][i+1] = low[i] - n * (high[i] - self._pivot[i+1])
                        self._resistances[n][i+1] = high[i] + n * (self._pivot[i+1] - low[i])

            elif self._method == PivotPointIndicator.METHOD_WOODIE:
                for i in range(0, size-1):
                    self._pivot[i+1] = (high[i] + low[i] + 2.0 * close[i]) / 4.0

                    self._supports[0][i+1] = (2.0 * self._pivot[i+1]) - high[i]
                    self._supports[1][i+1] = self._pivot[i+1] - (high[i] - low[i])
                    # self._supports[2][i+1] = low[i] - 2.0 * (high[i] - self._pivot[i+1])

                    self._resistances[0][i+1] = (2.0 * self._pivot[i+1]) - low[i]
                    self._resistances[1][i+1] = self._pivot[i+1] + (high[i] - low[i])
                    # self._resistances[2][i+1] = high[i] + 2.0 * (self._pivot[i+1] - low[i])

                for n in range(2, self._num):
                    for i in range(0, size-1):
                        self._supports[n][i+1] = low[i] - n * (high[i] - self._pivot[i+1])
                        self._resistances[n][i+1] = high[i] + n * (self._pivot[i+1] - low[i])

    def compute(self, timestamp, _open, high, low, close):
        if len(_open) < 2:
            # at least 2 entries (previous + current)
            return self._pivot, self._supports, self._resistances

        self._pivotpoint3(_open, high, low, close)

        self._last_supports = [self._supports[n][-1] for n in range(0, self._num)]  # (self._supports[0][-1], self._supports[1][-1], self._supports[2][-1])
        self._last_resistances = [self._resistances[n][-1] for n in range(0, self._num)]  # (self._resistances[0][-1], self._resistances[1][-1], self._resistances[2][-1])
        self._last_pivot = self._pivot[-1]

        self._last_timestamp = timestamp

        return self._pivot, self._supports, self._resistances
