# @date 2018-09-02
# @author Frederic SCHERMA
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Stochastic RSI indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MMexp_n, MM_n

import numpy as np
from talib import STOCHRSI as ta_STOCHRSI, STOCH as ta_STOCH, RSI as ta_RSI


class StochRSIIndicator(Indicator):
    """
    Stochastic RSI indicator
    https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/stochrsi
    """

    __slots__ = '_length', '_len_K', '_len_D', '_prev_k', '_last_k', '_prev_d', '_last_d', '_ks', '_ds'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=9, len_K=9, len_D=9):
        super().__init__("stochrsi", timeframe)
        
        self._length = length   # periods number for the RSI
        self._len_K = len_K     # periods number for the K
        self._len_D = len_D     # periods number for the D

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
    def ks(self):
        return self._ks
    
    @property
    def ds(self):
        return self._ds

    def cross(self):
        """K cross D line"""
        if (self._prev_k > self._prev_d and self._last_k < self._last_d):
            return -1
        elif (self._prev_k < self._prev_d and self._last_k > self._prev_d):
            return 1

        return 0

    @staticmethod
    def RSI_n(N, data):
        # from the RSI indicator
        variations = np.diff(data)
        #variations = np.diff(data) / data[:-1]

        # h = np.array(list(map(lambda x: max(x,0), variations)))
        # b = np.array(list(map(lambda x: abs(min(x,0)), variations)))

        # or that to avoid zeros
        h = np.array(list(map(lambda x: max(x,0.000001), variations)))
        b = np.array(list(map(lambda x: abs(min(x,-0.000001)), variations)))

        # exp or linear
        hn = MM_n(N, h)  # MMexp_n(N, h)
        bn = MM_n(N, b)  # MMexp_n(N, b

        # prefer to return in normalized 0..1
        rsi = hn/(hn+bn)
        return rsi

    @staticmethod
    def RSI_n_sf(N, data, step=1, filtering=False):
        # from the RSI indicator
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        variations = np.diff(sub_data)
        #variations = np.diff(sub_data) / sub_data[:-1]

        # h = np.array(list(map(lambda x: max(x,0), variations)))
        # b = np.array(list(map(lambda x: abs(min(x,0)), variations)))

        # or that to avoid zeros
        h = np.array(list(map(lambda x: max(x,0.000001), variations)))
        b = np.array(list(map(lambda x: abs(min(x,-0.000001)), variations)))

        # exp or linear
        # hn = np.interp(range(len(data)), t_subdata[1:], MMexp_n(N, h))
        # bn = np.interp(range(len(data)), t_subdata[1:], MMexp_n(N, b))

        hn = np.interp(range(len(data)), t_subdata[1:], MM_n(N, h))
        bn = np.interp(range(len(data)), t_subdata[1:], MM_n(N, b))

        # prefer to return in normalized 0..1
        rsi = hn/(hn+bn)
        return rsi

    @staticmethod
    def StochRSI(N, rsi, N_D=3):
        # from the Stochastic indicator
        K = np.zeros(len(rsi))

        for (j,d) in enumerate(rsi):
            i=min(j,N)
            highest = max(rsi[j-i:j+1])
            lowest = min(rsi[j-i:j+1])

            if highest == lowest:
                highest += 0.000000001

            K[j]=(d-lowest)/(highest-lowest)  # +epsilon to avoid 0

        D = MM_n(N_D, K)
        return K, D

    def compute(self, timestamp, prices):
        self._prev_k = self._last_k
        self._prev_d = self._last_d

        # k, d = StochRSIIndicator.StochRSI(
        #     self._len_K,
        #     StochRSIIndicator.RSI_n(self._length, prices),  # , self._step, self._filtering),
        #     self._len_D)

        rsis = ta_RSI(prices, self._length)
        self._ks, self._ds = ta_STOCH(rsis, rsis, rsis, fastk_period=self._length, slowk_period=self._len_K, slowk_matype=0, slowd_period=self._len_D, slowd_matype=0)

        # self._ks, self._ds = ta_STOCHRSI(prices, self._length, self._len_K, self._len_D, 0)

        self._last_k = self._ks[-1]
        self._last_d = self._ds[-1]

        self._last_timestamp = timestamp

        return self._ks, self._ds
