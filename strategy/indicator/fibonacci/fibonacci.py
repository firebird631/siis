# @date 2018-09-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Support and resistance detection using price and fibonacci levels

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import sys
import numpy as np


class FibonacciIndicator(Indicator):
    """
    Support and resistance detection using price and fibonacci levels
    Works with candles and not only a price.

    @todo
    """

    __slots__ = '_threshold', '_lowers', '_highers', '_pattern'

    PATTERN_UNKNOWN = 0
    PATTERN_PENNANT = 1
    PATTERN_FLAG = 2

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe):
        super().__init__("fibonacci", timeframe)

        self._compute_at_close = True  # only at close
        self._threshold = 0.0001   # mostly a factor of the pip meaning

        self._lowers = []
        self._highers = []

        self._pattern = FibonacciIndicator.PATTERN_UNKNOWN

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def lowers(self):
        return self._lowers
    
    @property
    def highers(self):
        return self._highers

    @staticmethod
    def Fibonnacci(open, high, low, close):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        # @todo fast MM_n for data

        lowers = []
        highers = []

        prev_high = 0.0
        prev_low = sys.float_info.max

        for n, price in enumerate(low):
            if price < prev_low:
                prev_low = price
            else:
                # store a lower
                lowers.append((n, prev_low))
                prev_low = sys.float_info.max

        for n, price in enumerate(high):
            if price > prev_high:
                prev_high = price
            else:
                # store a higher
                highers.append((n, prev_high))
                prev_high = 0.0

        return highers, lowers

    @staticmethod
    def Fibonnacci_sf(open, high, low, close, step=1, filtering=False):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        lsub_data = down_sample(low, step) if filtering else low [::step]
        hsub_data = down_sample(high, step) if filtering else high [::step]
        t_subdata = range(0,len(data),step)

        # @todo fast MM_n for data

        lowers = []
        highers = []

        prev_high = 0.0
        prev_low = sys.float_info.max

        for n, price in enumerate(lsub_data):
            if price < prev_low:
                prev_low = price
            else:
                # store a lower
                lowers.append((n*step, prev_low))
                prev_low = sys.float_info.max

        for n, price in enumerate(hsub_data):
            if price > prev_high:
                prev_high = price
            else:
                # store a higher
                highers.append((n*step, prev_high))
                prev_high = 0.0

        return highers, lowers

    def compute(self, timestamp, open, high, low, close):
        highers, lowers = FibonacciIndicator.Fibonnacci(open, high, low, close)

        self._lowers = lowers
        self._highers = highers

        self._last_timestamp = timestamp

        return highers, lowers

    def fibonacci(self, lowers, highers, volatility):
        levels = []

        # @todo

        return levels
