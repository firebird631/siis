# @date 2019-04-14
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Awesome based buy/sell signal indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, crossunder, crossover

import numpy as np
from talib import EMA as ta_EMA, SMA as ta_SMA

import logging
logger = logging.getLogger('siis.strategy.indicator')


class BSAweIndicator(Indicator):
    """
    Awesome based buy/sell signal indicator.

    @ref https://www.forexstrategiesresources.com/scalping-forex-strategies-iii/337-bollinger-bands-and-chaos-awesome-scalping-system
    @ref Squeeze Momentum Indicator [LazyBear]
    """

    __slots__ = '_bb_L', '_fast_MA_L', '_awesome_fast_L', '_awesome_slow_L', '_use_EMA', '_signal'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, bb_L=20, fast_MA_L=3.0, awesome_fast_L=5, awesome_slow_L=34, use_EMA=False):
        super().__init__("bsawe", timeframe)

        self._bb_L = bb_L
        self._fast_MA_L = fast_MA_L
        self._awesome_fast_L = awesome_fast_L
        self._awesome_slow_L = awesome_slow_L
        self._use_EMA = use_EMA

        self._signal = 0  # signal direction

    def signal(self):
        return self._signal

    def compute(self, timestamp, high, low, close):
        # Breakout Indicator Inputs
        bb_basis = ta_EMA(close, self._bb_L) if self._use_EMA else ta_SMA(close, self._bb_L)
        fast_ma = ta_EMA(close, self._fast_MA_L)

        # Calculate Awesome Oscillator
        hl2 = (high + low) * 0.5

        xSMA1_hl2 = ta_SMA(hl2, self._awesome_fast_L)
        xSMA2_hl2 = ta_SMA(hl2, self._awesome_slow_L)
        xSMA1_SMA2 = xSMA1_hl2 - xSMA2_hl2

        # Calculate direction of AO
        if xSMA1_SMA2[-1] >= 0:
            if xSMA1_SMA2[-1] > xSMA1_SMA2[-2]:
                AO = 1
            else:
                AO = 2
        else:
            if xSMA1_SMA2[-1] > xSMA1_SMA2[-2]:
                AO = -1
            else:
                AO = -2

        # Calc breakouts
        break_down = crossunder(fast_ma, bb_basis) and close[-1] < bb_basis[-1] and AO<0  # abs(AO)==2
        break_up = crossover(fast_ma, bb_basis) and close[-1] > bb_basis[-1] and AO>0  # abs(AO)==1

        self._signal = 1 if break_up else -1 if break_down else 0

        self._last_timestamp = timestamp

        return self._signal
