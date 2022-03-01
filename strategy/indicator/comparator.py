# @date 2018-09-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Indicator results local storing with usual comparison/checks

import numpy as np
from strategy.indicator import utils


class Comparator(object):
    """
    Base class for indicator comparator.
    Need an update per frame to be pertinent.
    """

    def __init__(self):
        pass


class RangeComparator(Comparator):
    """
    Signal indicator comparator.
    Useful for RSI 30/70, Stochastic 20/80... or any other horizontal low&high comparisons.
    Need an update per frame to be pertinent.
    """

    __slots__ = '_indicator', '_low', '_high', '_cross', '_distance', '_data'

    def __init__(self, indicator, low=30, high=70):
        super().__init__()

        self._indicator = indicator
        self._low = low
        self._high = high
        self._cross = 0  # -1 0 or 1 (low, range, high)
        self._distance = 0.0
        self._data = []

    @property
    def data(self):
        return self._data

    @property
    def indicator(self):
        return self._indicator

    def update(self, data):
        if len(self._data) >= 1 and len(data) >= 1:
            self._distance = data[-1] - self._data[-1]

            # goes below low
            if self._data[-1] > self._low and data[-1] <= self._low:
                self._cross = -1

            # goes upper high
            elif self._data[-1] < self._high and data[-1] >= self._high:
                self._cross = 1

            # range
            else:
                self._cross = 0

        self._data = data

    def cross_low(self):
        return self._cross < 0

    def cross_high(self):
        return self._cross > 0

    @property
    def cross(self):
        return self._cross

    @property
    def distance(self):
        return self._distance


class CrossComparator(Comparator):
    """
    Dual signal indicator comparator.
    Detect trend and crossing of two signals.
    """

    __slots__ = '_ind1', '_ind2', '_cross', '_d1', '_d2', '_rd', '_data1', '_data2'

    def __init__(self, ind1, ind2):
        super().__init__()

        self._ind1 = ind1
        self._ind2 = ind2
        self._cross = 0  # -1 0 or 1 (low, range, high)
        self._d1 = 0.0   # distance from previous value of d1
        self._d2 = 0.0   # distance from previous value of d2
        self._rd = 0.0   # last relative distance d1 - d2
        self._data1 = []
        self._data2 = []

    @property
    def data1(self):
        return self._data1

    @property
    def data2(self):
        return self._data2

    @property
    def ind1(self):
        return self._ind1

    @property
    def ind2(self):
        return self._ind2

    def update(self, data1, data2):
        pass
        # @todo
        # if len(self._data) >= 1 and len(data) >= 1:
        #   self._distance = data[-1] - self._data[-1]

        #   # goes below low
        #   if self._data[-1] > self.low and data[-1] <= self.low:
        #       self._cross = -1

        #   # goes upper high
        #   elif self._data[-1] < self.high and data[-1] >= self.high:
        #       self._cross = 1

        #   # range
        #   else:
        #       self._cross = 0

        # self._data = data

    @property
    def d1(self):
        return self._d1

    @property
    def d2(self):
        return self._d2

    @property
    def rd(self):
        """
        Relative distance at latest sample.
        """
        return self._rd
