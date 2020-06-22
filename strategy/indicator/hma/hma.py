# @date 2018-09-02
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Hull Moving Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import SMA as ta_SMA

import numpy as np
import math


class HMAIndicator(Indicator):
    """
    Hull Moving Average indicator
    https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/hull-moving-average
    """

    __slots__ = '_length', '_prev', '_last', '_hmas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, length=9):
        super().__init__("hma", timeframe)

        self._length = length   # periods number
        self._prev = 0.0
        self._last = 0.0

        self._hmas = np.array([])

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
    def step(self):
        return self._step
    
    @step.setter
    def step(self, step):
        self._step = step

    @property
    def filtering(self):
        return self._filtering

    @filtering.setter
    def filtering(self, filtering):
        self._filtering = filtering

    @property
    def hmas(self):
        return self._hmas

    @staticmethod
    def HMA_n(N, data):
        N_2 = int(N / 2)
        N_sqrt = int(math.sqrt(N))

        weights = np.array([float(x) for x in range(1, len(data)+1)])

        # 1) calculate a WMA with period n / 2 and multiply it by 2
        # hma12 = 2 * MM_n(N_2, data*weights) / MM_n(N_2, weights)
        hma12 = 2.0 * ta_SMA(data*weights, N_2) / ta_SMA(weights, N_2)

        # 2) calculate a WMA for period n and subtract if from step 1
        # hma12 = hma12 - (MM_n(N, data*weights) / MM_n(N, weights))
        hma12 = hma12 - (ta_SMA(data*weights, N) / ta_SMA(weights, N))

        # 3) calculate a WMA with period sqrt(n) using the data from step 2
        # hma = (MM_n(N_sqrt, hma12*weights) / MM_n(N_sqrt, weights))
        hma = (ta_SMA(hma12*weights, N_sqrt) / ta_SMA(weights, N_sqrt))

        return hma

    @staticmethod
    def HMA_n_sf(N, data, step=1, filtering=False):
        """ 
        Calcule un HMA sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        N_2 = int(N / 2)
        N_sqrt = int(math.sqrt(N))

        weights = np.array([x for x in range(1, len(sub_data)+1)])

        # 1) calculate a WMA with period n / 2 and multiply it by 2
        hma12 = 2 * MM_n(N_2, sub_data*weights) / MM_n(N_2, weights)

        # 2) calculate a WMA for period n and subtract if from step 1
        hma12 = hma12 - (MM_n(N, sub_data*weights) / MM_n(N, weights))

        # 3) calculate a WMA with period sqrt(n) using the data from step 2
        hma = (MM_n(N_sqrt, hma12*weights) / MM_n(N_sqrt, weights))

        return hma

    def compute(self, timestamp, prices):
        self._prev = self._last
        self._hmas = HMAIndicator.HMA_n(self._length, prices)

        self._last = self._hmas[-1]
        self._last_timestamp = timestamp

        return self._hmas
