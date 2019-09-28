# @date 2019-04-14
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Bollinger band + Awesome indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, crossunder, crossover

import numpy as np
from talib import EMA as ta_EMA, SMA as ta_SMA, BBANDS as ta_BBANDS, STDDEV as ta_STDDEV

import numpy as np

import logging
logger = logging.getLogger('siis.strategy.indicator')


class BBAweIndicator(Indicator):
    """
    Bollinger band + Awesome indicator

    @ref https://www.forexstrategiesresources.com/scalping-forex-strategies-iii/337-bollinger-bands-and-chaos-awesome-scalping-system
    @ref Squeeze Momentum Indicator [LazyBear]
    """

    __slots__ = '_bb_L', '_base_multiplier', '_fast_MA_L', '_awesome_fast_L', '_awesome_slow_L', '_use_EMA', '_signal'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, bb_L=20, base_multiplier=2.0, fast_MA_L=3.0, awesome_fast_L=5, awesome_slow_L=34, use_EMA=False):
        super().__init__("bbawe", timeframe)

        self._bb_L = bb_L
        self._base_multiplier = base_multiplier
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

        # Deviation (a simple BBAND)
        # dev = ta_STDDEV(close, self._bb_L)
        # bb_dev_inner = self._base_multiplier * dev

        # Upper bands
        # inner_high = bb_basis + bb_dev_inner
        # Lower Bands
        # inner_low = bb_basis - bb_dev_inner

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
        break_down = crossunder(fast_ma, bb_basis) and close[-1] < bb_basis[-1] and abs(AO)==2
        break_up = crossover(fast_ma, bb_basis) and close[-1] > bb_basis[-1] and abs(AO)==1

        self._signal = 1 if break_up else -1 if break_down else 0

        self._last_timestamp = timestamp

        return self._signal
