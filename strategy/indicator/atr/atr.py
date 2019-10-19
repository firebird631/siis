# @date 2019-02-13
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Average True Range indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n
from talib import ATR as ta_ATR, SMA as ta_SMA

import numpy as np


class ATRIndicator(Indicator):
    """
    Average True Range indicator
    Also update the last ATR stop-loss for the two directions.
    Compute need at least N candles plus one.

        - distance entre le haut du jour et le bas du jour.
        - distance entre la clôture de la veille et le haut du jour
        - distance entre la clôture de la veille et le bas du jour
        - ATR est une moyenne mobile (habituellement a 14 jours) de ces True Ranges
    """

    __slots__ = '_length', '_coeff', '_atrs', '_last', '_prev', '_long_sl', '_short_sl'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, length=9, coeff=3):
        super().__init__("atr", timeframe)
        
        # self._step = step       # sample step
        # self._filtering = filtering
        
        self._length = length   # MA periods number
        self._coeff = coeff

        self._atrs = np.array([])

        self._last = 0.0
        self._prev = 0.0

        self._long_sl = 0
        self._short_sl = 0

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
    def atrs(self):
        return self._atrs

    def stop_loss(self, direction):
        if direction > 0:
            return self._long_sl
        elif direction < 0:
            return self._short_sl
        return 0

    def _update_stop_loss(self, last_price, coeff=None):
        """
        Compute an ATR stop-loss price depending on the direction.
        """
        coeff = coeff or self._coeff

        # long
        # ATRTS(t) = Close(t) - (Coeff * ATR(t))
        # et si ATRTS(t) < ATRTS(t-1) : ATRTS(t)=ATRTS(t-1)
        prev = self._long_sl
        self._long_sl = last_price - (coeff * self._last)
        # if self._long_sl < prev:
        #     self._long_sl = prev

        # short
        # ATRTS(t) = Close(t) + (Coeff * ATR(t))
        # Et si ATRTS(t) > ATRTS(t-1) : ATRTS(t)=ATRTS(t-1)
        prev = self._short_sl
        self._short_sl = last_price + (coeff * self._last)
        # if self._short_sl > prev:
        #     self._short_sl = prev

    # def compute(self, timestamp, candles, high=None, low=None, close=None):
    def compute(self, timestamp, high, low, close):
        self._prev = self._last

        # n = len(candles)
        # atr = np.array([0.0]*n)

        # # find a source saying its
        # # true_high = np.array([max(candles[n-1].close, candles[n].high) for n in range(1, n)])
        # # true_low = np.array([min(candles[n-1].close, candles[n].low) for n in range(1, n)])
        # # atr = MM_n(N, true_high - true_low)

        # # these version appear most often, so its probably the good one
        # for i in range(1, n):
        #     atr[i] = max(max(
        #                 candles[i].high - candles[i].low,
        #                 abs(candles[i].high - candles[i-1].close)),
        #                 abs(candles[i].low - candles[i-1].close))

        # # first value must, last previous or duplicate the first we have
        # if len(self._atr):
        #     atr[0] = self._atr[-1]
        # else:
        #     atr[0] = atr[1]

        # self._last = ta_SMA(atr, self._length)

        self._atrs = ta_ATR(high, low, close, timeperiod=self._length)
        self._last = self._atrs[-1]

        # update the last ATR stop-loss for long and short directions
        # self._update_stop_loss(candles[-1].close)
        self._update_stop_loss(close[-1])

        self._last_timestamp = timestamp

        return self._atrs
