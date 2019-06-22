# @date 2018-09-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Support and resistance detection using price and fibonnacci levels

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MM_n

import sys
import numpy as np


class FibonacciIndicator(Indicator):
    """
    Support and resistance detection using price and fibonnacci levels
    Works with candles and not only a price.

    @todo
    """

    PATTERN_UNKNOWN = 0
    PATTERN_PENNANT = 1
    PATTERN_FLAG = 2

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe):
        super().__init__("fibonacci", timeframe)

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
    def Fibonnacci(data):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        # @todo fast MM_n for data

        lowers = []
        highers = []

        prev_high = 0.0
        prev_low = sys.float_info.max

        for n, price in enumerate(low_prices):
            if price < prev_low:
                prev_low = price
            else:
                # store a lower
                lowers.append((n, prev_low))
                prev_low = sys.float_info.max

        for n, price in enumerate(high_prices):
            if price > prev_high:
                prev_high = price
            else:
                # store a higher
                highers.append((n, prev_high))
                prev_high = 0.0

        return highers, lowers

    @staticmethod
    def Fibonnacci_sf(data, step=1, filtering=False):
        """ 
        Retrouve les niveaux plus haut et plus bas et retrouve les niveaux fibo.
        """
        low_prices = [x.low for x in data]
        high_prices = [x.high for x in data]

        lsub_data = down_sample(low_prices, step) if filtering else low_prices [::step]
        hsub_data = down_sample(high_prices, step) if filtering else high_prices [::step]
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

    def compute(self, timestamp, candles):
        highers, lowers = FibonacciIndicator.Fibonnacci(candles)

        self._lowers = lowers
        self._highers = highers

        self._last_timestamp = timestamp

        return highers, lowers

    def fibonacci(self, lowers, highers, volatility):
        levels = []

        # @todo

        return levels
