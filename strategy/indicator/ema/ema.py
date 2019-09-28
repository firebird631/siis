# @date 2018-09-02
# @author Frederic SCHERMA
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Simple Exponential Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MMexp_n

import numpy as np
from talib import EMA as ta_EMA


class EMAIndicator(Indicator):
    """
    Exponential Moving Average indicator
    """

    __slots__ = '_length', '_prev', '_last', '_emas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=9):
        super().__init__("ema", timeframe)
        
        # self._step = step       # sample step
        # self._filtering = filtering
        
        self._length = length   # periods number

        self._prev = 0.0
        self._last = 0.0

        self._emas = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def emas(self):
        return self._emas

    @staticmethod
    def EMA_n_sf(N, data, step=1, filtering=False):
        """ 
        Calcule une EMA sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        ema = MMexp_n(N, sub_data)

        return ema

    def compute(self, timestamp, prices):
        self._prev = self._last

        # self._emas = EMAIndicator.EMA_n_sf(self._length, prices)
        # self._emas = MMexp_n(self._length, prices)
        self._emas = ta_EMA(prices, self._length)

        self._last = self._emas[-1]

        self._last_timestamp = timestamp

        return self._emas
