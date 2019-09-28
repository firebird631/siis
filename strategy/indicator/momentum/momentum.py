# @date 2018-09-02
# @author Frederic SCHERMA
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Momentum indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample
from talib import MOM as ta_MOM

import numpy as np


class MomentumIndicator(Indicator):
    """
    Momentum indicator
    """

    __slots__ = '_length', '_prev', '_last', '_mmts'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=7):
        super().__init__("momentum", timeframe)
        
        self._length = length   # periods number
        self._prev = 0.0
        self._last = 0.0

        self._mmts = np.array([])

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
    def mmts(self):
        return self._mmts

    @staticmethod
    def MMT_n(N, data):
        """ 
        Calcule un momentum sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        # rajoute les N premieres valeures manquantes
        return np.array([x-data[0] for x in data[:N]] + list(np.array(data[N:]) - np.array(data[0:-1-N+1])))
    
    @staticmethod
    def MMT_n_sf(N, data, step=1, filtering=False):
        """ 
        Calcule un momentum sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)
        
        # rajoute les N premieres valeures manquantes
        mmt = np.array([x-sub_data[0] for x in sub_data[:N]] + list(np.array(sub_data[N:]) - np.array(sub_data[0:-1-N+1])))
        return mmt  # interp

    def compute(self, timestamp, prices):
        self._prev = self._last

        # self._mmts = MomentumIndicator.MMT_n(self._length, prices)
        self._mmts = ta_MOM(prices, self._length)

        self._last = self._mmts[-1]
        self._last_timestamp = timestamp

        return self._mmts
