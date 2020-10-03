# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Stochastique indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MMexp_n, MM_n

import numpy as np
from talib import STOCH as ta_STOCH, STOCHF as to_STOCHF


class StochasticIndicator(Indicator):
    """
    Stochastique indicator.
    https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/slow-stochastic
    """

    __slots__ = '_length', '_len_K', '_len_D', '_prev_k', '_last_k', '_prev_d', '_last_d', '_ks', '_ds'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=9, len_K=3, len_D=3):
        super().__init__("stochastic", timeframe)

        self._length = length   # periods number for the K
        self._len_K = len_K     # periods number for the K smooth
        self._len_D = len_D     # periods number for the D smooth

        self._prev_k = 0.0
        self._last_k = 0.0

        self._prev_d = 0.0
        self._last_d = 0.0

        self._ks = np.array([])
        self._ds = np.array([])

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def prev_k(self):
        return self._prev_k

    @property
    def last_k(self):
        return self._last_k

    @property
    def prev_d(self):
        return self._prev_d

    @property
    def last_d(self):
        return self._last_d

    @property
    def len_K(self):
        return self._len_K
    
    @len_K.setter
    def len_K(self, len_K):
        self._len_K = len_K

    @property
    def len_D(self):
        return self._len_D
    
    @len_D.setter
    def len_D(self, len_D):
        self._len_D = len_D

    @property
    def ks(self):
        return self._ks
    
    @property
    def ds(self):
        return self._ds

    def cross(self):
        if (self._prev_k > self._prev_d and self._last_k < self._last_d):
            return -1
        elif (self._prev_k < self._prev_d and self._last_k > self._last_d):
            return 1

        return 0

    @staticmethod
    def Stochastic(N, data, N_D=3):
        K = np.zeros(len(data))

        for (j,d) in enumerate(data):
            i=min(j,N)
            highest = max(data[j-i:j+1])
            lowest = min(data[j-i:j+1])

            if highest == lowest:
                highest += 0.000000001

            K[j]=(d-lowest)/(highest-lowest)  # +epsilon to avoid 0

        D = MM_n(N_D, K)
    
        return (K, D)

    @staticmethod
    def Stochastic_sf(N, data, N_D=3, step=1, filtering=False):
        """ 
        Calcul des stochastiques.
        N est le nombre de periodes a observer pour repérer le min et le max du cours.
        N_D est le nombre d'echantillons de K a utiliser pour le calcul de D
        step permet de ne selectionner qu'un echantillon sur step dans data.
        filtering permet de filtrer ou non les donnees avant d'appliquer la selection.

        Retourne les stochastiques K, D interpolees lineairement ; meme taille que data.
        """
        sub_data = down_sample(data, step) if filtering else data [::step]

        K = np.zeros(len(sub_data))
        t_subdata = range(0,len(data),step)

        for (j,d) in enumerate(sub_data):
            i=min(j,N)
            highest = max(sub_data[j-i:j+1])
            lowest = min(sub_data[j-i:j+1])

            if highest == lowest:
                highest += 0.000000001

            K[j]=(d-lowest)/(highest-lowest)  # +epsilon to avoid 0

        D = MM_n(N_D, K)
    
        return np.interp(range(len(data)), t_subdata, K), np.interp(range(len(data)), t_subdata, D)

    def compute(self, timestamp, high, low, close):
        self._prev_k = self._last_k
        self._prev_d = self._last_d

        # self._ks, self._ds = StochasticIndicator.Stochastic_sf(self._len_K, close, self._len_D)  # , self._step, self._filtering)
        self._ks, self._ds = ta_STOCH(high, low, close, fastk_period=self._length, slowk_period=self._len_K, slowk_matype=0, slowd_period=self._len_D, slowd_matype=0)
        # self._ks, self._ds = to_STOCHF(high, low, close, fastk_period=self._len_K, fastd_period=self._len_D, fastd_matype=0)

        self._last_k = self._ks[-1]
        self._last_d = self._ds[-1]

        self._last_timestamp = timestamp

        return self._ks, self._ds
