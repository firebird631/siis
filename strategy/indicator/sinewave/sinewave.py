# @date 2019-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# SineWave Hilbert transform indicator

from strategy.indicator.indicator import Indicator
# from strategy.indicator.utils import down_sample, cross

import numpy as np
from talib import HT_SINE as ta_HT_SINE


class SineWaveIndicator(Indicator):
    """
    SineWave Hilbert transform indicator
    """

    __slots__ = '_prev_sine', '_last_sine',  '_prev_lead_sine', '_last_lead_sine', '_sines', '_lead_sines'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_CYCLE

    def __init__(self, timeframe):
        super().__init__("sineware", timeframe)

        self._prev_sine = 0.0
        self._last_sine = 0.0

        self._prev_lead_sine = 0.0
        self._last_lead_sine = 0.0

        self._sines = np.array([])
        self._lead_sines = np.array([])

    @property
    def prev_sine(self):
        return self._prev_sine

    @property
    def last_sine(self):
        return self._last_sine

    @property
    def prev_lead_sine(self):
        return self._prev_lead_sine
    
    @property
    def last_lead_sine(self):
        return self._last_lead_sine

    @property
    def sines(self):
        return self._sines
    
    @property
    def lead_sines(self):
        return self._lead_sines

    def cross(self):
        if (self._prev_sine > self._prev_lead_sine and self._last_sine < self._last_lead_sine):
            return -1
        elif (self._prev_sine < self._prev_lead_sine and self._last_sine > self._prev_lead_sine):
            return 1

        return 0

    def trend(self):
        return 1 if self._last_sine > self._last_lead_sine else -1 if self._last_sine < self._last_lead_sine else 0

    def compute(self, timestamp, close):
        self._prev_sine = self._last_sine
        self._prev_lead_sine = self._last_lead_sine

        self._sines, self._lead_sines = ta_HT_SINE(close)

        self._last_sine = self._sines[-1]
        self._last_lead_sine = self._lead_sines[-1]

        self._last_timestamp = timestamp

        return self._sines, self._lead_sines
