# @date 2018-09-28
# @author Frederic SCHERMA
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
    S3 = B - 2x (H - Pivot)
    R1 = (2 x Pivot) - B
    R2 = Pivot + (H - B)
    R3 = H + 2x (Pivot - B)

    Camarilla:
    Pivot = C
    S1 = C - (H - L) * 1.1/12
    S2 = C - (H - L) * 1.1/6
    S3 = C - (H - L) * 1.1/4
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

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, method=METHOD_CLASSICAL):
        super().__init__("pivotpoint", timeframe)

        self._method = method

        self._pivot = np.array([])
        self._supports = [np.array([]), np.array([]), np.array([])]
        self._resistances = [np.array([]), np.array([]), np.array([])]

        self._prev_supports = [0.0]*3
        self._prev_resistances = [0.0]*3
        self._prev_pivot = 0.0

        self._last_supports = [0.0]*3
        self._last_resistances = [0.0]*3
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
    
    @staticmethod
    def PivotPoint(method, _open, high, low, close):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        if method == PivotPointIndicator.METHOD_CAMARILLA:
            pivot = close

            s1 = close - (high - low)*1.1/12
            s2 = close - (high - low)*1.1/6
            s3 = close - (high - low)*1.1/4

            r1 = close + (high - low)*1.1/12
            r2 = close + (high - low)*1.1/6
            r3 = close + (high - low)*1.1/4

        elif method == PivotPointIndicator.METHOD_FIBONACCI:
            pivot = close

            s1 = close - (high - low)*0.382
            s2 = close - (high - low)*0.618
            s3 = close - (high - low)*0.764

            r1 = close + (high - low)*0.382
            r2 = close + (high - low)*0.618
            r3 = close + (high - low)*0.764

        else:  # classical or woodie
            if method == PivotPointIndicator.METHOD_CLASSICAL:
                pivot = (high + low + close) / 3.0
            elif method == PivotPointIndicator.METHOD_CLASSICAL_OHLC:
                pivot = (high + low + close + _open) / 4.0
            elif method == PivotPointIndicator.METHOD_CLASSICAL_OHL:
                pivot = (high + low + _open) / 3.0
            elif method == PivotPointIndicator.METHOD_WOODIE:
                pivot = (high + low + 2.0 * close) / 4.0

            s1 = (2.0 * pivot) - high
            s2 = pivot - (high - low)
            s3 = low - 2.0 * (high - pivot)
            
            r1 = (2.0 * pivot) - low
            r2 = pivot + (high - low)
            r3 = high + 2.0 * (pivot - low)

        return pivot, (s1, s2, s3), (r1, r2, r3)

    @staticmethod
    def PivotPoint_sf(method, _open, high, low, close, step=1, filtering=False):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        lsub_data = down_sample(low, step) if filtering else np.array(low[::step])
        hsub_data = down_sample(high, step) if filtering else np.array(high[::step])
        csub_data = down_sample(close, step) if filtering else np.array(close[::step])

        if method == PivotPointIndicator.METHOD_CLASSICAL_OHLC or method == PivotPointIndicator.METHOD_CLASSICAL_HLO:
            osub_data = down_sample(_open, step) if filtering else np.array(_open[::step])

        if method == PivotPointIndicator.METHOD_CAMARILLA:
            pivot = csub_data

            s1 = csub_data - (hsub_data - lsub_data)*1.1/12
            s2 = csub_data - (hsub_data - lsub_data)*1.1/6
            s3 = csub_data - (hsub_data - lsub_data)*1.1/4

            r1 = csub_data + (hsub_data - lsub_data)*1.1/12
            r2 = csub_data + (hsub_data - lsub_data)*1.1/6
            r3 = csub_data + (hsub_data - lsub_data)*1.1/4

        elif method == PivotPointIndicator.METHOD_FIBONACCI:
            pivot = csub_data

            s1 = csub_data - (hsub_data - lsub_data)*0.382
            s2 = csub_data - (hsub_data - lsub_data)*0.618
            s3 = csub_data - (hsub_data - lsub_data)*0.764

            r1 = csub_data + (hsub_data - lsub_data)*0.382
            r2 = csub_data + (hsub_data - lsub_data)*0.618
            r3 = csub_data + (hsub_data - lsub_data)*0.764

        else:  # classical or woodie
            if method == PivotPointIndicator.METHOD_CLASSICAL:
                pivot = (hsub_data + lsub_data + csub_data) / 3.0
            elif method == PivotPointIndicator.METHOD_CLASSICAL_OHLC:
                pivot = (hsub_data + lsub_data + csub_data + osub_data) / 4.0
            elif method == PivotPointIndicator.METHOD_CLASSICAL_OHL:
                pivot = (hsub_data + lsub_data + osub_data) / 3.0
            elif method == PivotPointIndicator.METHOD_WOODIE:
                pivot = (hsub_data + lsub_data + 2.0 * csub_data) / 4.0

            s1 = (2.0 * pivot) - hsub_data
            s2 = pivot - (hsub_data - lsub_data)
            s3 = lsub_data - 2.0 * (hsub_data - pivot)
            
            r1 = (2.0 * pivot) - lsub_data
            r2 = pivot + (hsub_data - lsub_data)
            r3 = hsub_data + 2.0 * (pivot - lsub_data)

        return pivot, (s1, s2, s3), (r1, r2, r3)

    def compute(self, timestamp, _open, high, low, close):
        self._prev_supports = copy.copy(self._last_supports)
        self._prev_resistances = copy.copy(self._last_resistances)
        self._prev_pivot = self._last_pivot

        self._pivot, self._supports, self._resistances = PivotPointIndicator.PivotPoint(self._method, _open, high, low, close)  # , self._step, self._filtering)

        self._last_supports = (self._supports[0][-1], self._supports[1][-1], self._supports[2][-1])
        self._last_resistances = (self._resistances[0][-1], self._resistances[1][-1], self._resistances[2][-1])
        self._last_pivot = self._pivot[-1]

        self._last_timestamp = timestamp

        return self._pivot, self._supports, self._resistances
