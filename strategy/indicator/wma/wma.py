# @date 2018-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Weighted Moving Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import WMA as ta_WMA

import numpy as np


class WMAIndicator(Indicator):
    """
    Weighted Moving Average indicator
    """

    __slots__ = '_length', '_prev', '_last', '_wmas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, length=9):
        super().__init__("wma", timeframe)

        self._length = length   # periods number
        self._prev = 0.0
        self._last = 0.0

        self._wmas = np.array([])

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
    def wmas(self):
        return self._wmas

    @staticmethod
    def WMA_n(N, prices):
        weights = np.array([x for x in range(1, len(prices)+1)])
        wma = MM_n(N, prices*weights) / weights

        return wma

    @staticmethod
    def WMA_n_sf(N, prices, step=1, filtering=False):
        """ 
        Calcule une WMA sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        sub_data = down_sample(prices, step) if filtering else np.array(prices) [::step]
        t_subdata = range(0,len(prices),step)

        weights = np.array([x for x in range(1, len(sub_data)+1)])
        wma = MM_n(N, sub_data*weights) / weights

        return wma

    def compute(self, timestamp, prices):
        self._prev = self._last

        # self._wmas = WMAIndicator.WMA_n(self._length, prices)  # , self._step, self._filtering)
        self._wmas = ta_WMA(prices, self._length)

        self._last = self._wmas[-1]
        self._last_timestamp = timestamp

        return self._wmas
