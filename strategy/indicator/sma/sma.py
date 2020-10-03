7# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Simple Moving Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import numpy as np
from talib import SMA as ta_SMA


class SMAIndicator(Indicator):
    """
    Simple Moving Average indicator
    """

    __slots__ = '_length', '_prev', '_last', '_smas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=9):
        super().__init__("sma", timeframe)

        self._length = length   # periods number

        self._prev = 0.0
        self._last = 0.0

        self._smas = np.array([])

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
    def smas(self):
        return self._smas

    @staticmethod
    def SMA_n_sf(N, data, step=1, filtering=False):
        """ 
        Calcule une SMA sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        sma = MM_n(N, data)

        return sma

    def compute(self, timestamp, prices):
        self._prev = self._last

        # self._smas = SMAIndicator.SMA_n_sf(self._length, prices)  # , self._step, self._filtering)
        # self._smas = MM_n(self._length, prices)
        self._smas = ta_SMA(prices, self._length)
        self._last = self._smas[-1]

        self._last_timestamp = timestamp

        return self._smas
