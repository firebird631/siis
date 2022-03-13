# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# Relative Strength Index indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n  # , MMexp_n

import numpy as np
from talib import RSI as ta_RSI


class RSIIndicator(Indicator):
    """
    Relative Strength Index indicator
    """

    __slots__ = '_length', '_prev', '_last', '_rsis'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=14):
        super().__init__("rsi", timeframe)

        self._length = length   # periods number
        self._prev = 0.0
        self._last = 0.0

        self._rsis = np.array([])

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
    def rsis(self):
        return self._rsis

    @staticmethod
    def RSI_n(N, data):
        """ 
        Calcule le RSI sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        variations = np.diff(data)
        #variations = np.diff(data) / data[:-1]

        # h = np.array(list(map(lambda x: max(x,0), variations)))
        # b = np.array(list(map(lambda x: abs(min(x,0)), variations)))

        # or that to avoid zeros
        h = np.array(list(map(lambda x: max(x,0.000000001), variations)))
        b = np.array(list(map(lambda x: abs(min(x,-0.000000001)), variations)))

        # exp or linear
        hn = MM_n(N, h)  # MMexp_n(N, h)
        bn = MM_n(N, b)  # MMexp_n(N, b)

        # prefer to return in normalized 0..1
        rsi = hn/(hn+bn) * 100

        return rsi

    @staticmethod
    def RSI_n_sf(N, data, step=1, filtering=False):
        """
        Calcule le RSI sur N periodes en prenant un echantillon tous les step avec ou sans filtrage prealable
        Retourne un array de la même taille que data. Lorsque step > 1, les valeurs sont interpolees lineairement.
        """
        # have a difference with others algo, it seems doubling N make the deals... but what's the problem
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        variations = np.diff(sub_data)
        #variations = np.diff(sub_data) / sub_data[:-1]

        # h = np.array(list(map(lambda x: max(x,0), variations)))
        # b = np.array(list(map(lambda x: abs(min(x,0)), variations)))

        # or that to avoid zeros
        h = np.array(list(map(lambda x: max(x,0.000000001), variations)))
        b = np.array(list(map(lambda x: abs(min(x,-0.000000001)), variations)))

        # exp or linear
        # hn = np.interp(range(len(data)), t_subdata[1:], MMexp_n(N, h))
        # bn = np.interp(range(len(data)), t_subdata[1:], MMexp_n(N, b))

        hn = np.interp(range(len(data)), t_subdata[1:], MM_n(N, h))
        bn = np.interp(range(len(data)), t_subdata[1:], MM_n(N, b))

        # prefer to return in normalized 0..1
        rsi = hn/(hn+bn) * 100

        return rsi

    def compute(self, timestamp, prices):
        self._prev = self._last
        # self._rsis = RSIIndicator.RSI_n_sf(self._length, prices)  # , self._step, self._filtering)
        self._rsis = ta_RSI(prices, self._length)

        self._last = self._rsis[-1]
        self._last_timestamp = timestamp

        return self._rsis
