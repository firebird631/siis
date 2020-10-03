# @date 2018-09-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Volume Weighted Moving Average indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import SMA as ta_SMA

import numpy as np


class VWMAIndicator(Indicator):
    """
    Volume Weighted Moving Average indicator
    """

    __slots__ = '_length', '_prev', '_last', '_vwmas'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, length=9):
        super().__init__("vwma", timeframe)
    
        self._length = length   # periods number
        self._prev = 0.0
        self._last = 0.0

        self._vwmas = np.array([])

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
    def vwmas(self):
        return self._vwmas

    @staticmethod
    def VWMA_n(N, prices, volumes):
        # cannot deal with zero volume, then set it to 1 will have no effect on the result, juste give a price
        for i, v in enumerate(volumes):
            if v <= 0:
                volumes[i] = 1.0

        # pvs = MM_n(N, np.array(prices)*np.array(volumes))
        pvs = ta_SMA(np.array(prices)*np.array(volumes), N)
        # vs = MM_n(N, volumes)
        vs = ta_SMA(volumes, N)

        return pvs / vs

    @staticmethod
    def VWMA_n_sf(N, prices, volumes, step=1, filtering=False):
        """ 
        Calcule une VWMA sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la meme taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        p_sub_data = down_sample(prices, step) if filtering else np.array(prices) [::step]
        v_sub_data = down_sample(volumes, step) if filtering else np.array(volumes) [::step]
        t_subdata = range(0,len(prices),step)

        # cannot deal with zero volume, then set it to 1 will have no effect on the result, juste give a price
        for i, v in enumerate(v_sub_data):
            if v <= 0:
                v_sub_data[i] = 1.0

        pvs = MM_n(N, p_sub_data*v_sub_data)
        vs = MM_n(N, v_sub_data)

        return pvs / vs

    def compute(self, timestamp, prices, volumes):
        self._prev = self._last
        
        self._vwmas = VWMAIndicator.VWMA_n(self._length, prices, volumes)  # , self._step, self._filtering)

        self._last = self._vwmas[-1]
        self._last_timestamp = timestamp

        return self._vwmas
