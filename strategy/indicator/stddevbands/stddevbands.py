# @date 2020-07-06
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Standard Deviation Bands indicator

from strategy.indicator.indicator import Indicator
from talib import STDDEV as ta_STDDEV, SMA as ta_SMA, TRANGE as ta_TRANGE

import statistics as stat
import numpy as np
import copy

import logging
logger = logging.getLogger('siis.strategy.indicator.stddevbands')


class StdDevBandsIndicator(Indicator):
    """
    Standard Deviation Bands indicator
    """

    __slots__ = '_length', '_mult',  '_prev_bottom', '_prev_ma', '_prev_top', '_last_bottom', '_last_ma', '_last_top', '_bottoms', '_tops', '_mas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLATILITY

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=20, mult=2.0):
        super().__init__("stddevbands", timeframe)
        
        self._length = length   # periods number
        self._mult = mult       # multipier coef

        self._prev_bottom = 0.0
        self._prev_ma = 0.0
        self._prev_top = 0.0

        self._last_bottom = 0.0
        self._last_ma = 0.0
        self._last_top = 0.0

        self._bottoms = np.array([])
        self._mas = np.array([])
        self._tops = np.array([])
        self._trs = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def mult(self):
        return self._mult
    
    @mult.setter
    def mult(self, mult):
        self._mult = mult

    @property
    def prev_bottom(self):
        return self._prev_bottom

    @property
    def prev_ma(self):
        return self._prev_ma

    @property
    def prev_top(self):
        return self._prev_top

    @property
    def last_bottom(self):
        return self._last_bottom

    @property
    def prev_tr(self):
        return self._prev_tr

    @property
    def last_ma(self):
        return self._last_ma

    @property
    def last_top(self):
        return self._last_top

    @property
    def last_tr(self):
        return self._last_tr

    @property
    def bottoms(self):
        return self._bottoms
    
    @property
    def tops(self):
        return self._tops
    
    @property
    def mas(self):
        return self._mas

    @property
    def trs(self):
        return self._trs

    def compute(self, timestamp, highs, lows, closes):
        self._prev_top = self._last_top
        self._prev_ma = self._last_ma
        self._prev_bottom = self._last_bottom
        self._prev_tr = self._last_tr

        basis0 = highs - lows
        basis = ta_SMA(basis0, self._length)
        basis2 = ta_TRANGE(highs, lows, closes)

        dev = self._mult * ta_STDDEV(basis, self._length)

        self._tops = basis + dev
        self._bottoms = basis - dev

        self._mas = basis
        self._tr = basis2

        self._last_top = self._tops[-1]
        self._last_ma = self._mas[-1]
        self._last_bottom = self._bottoms[-1]
        self._last_tr = self._trs[-1]

        self._last_timestamp = timestamp

        return self._tops, self._mas, self._bottoms
