# @date 2023-09-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Kahlman Filter implementation.

import math
import numpy as np

import logging
logger = logging.getLogger('siis.strategy.kahlman')


class KahlmanFilter(object):
    """
    Kahlman Filter implementation working with indicators.
    It is not directly based on Indicator model.

    @note Works with both temporal and non-temporal bars.
    """

    def __init__(self, _len: int, gain: float = 0.7):
        self.len = _len
        self.gain = gain

        self.g2sqrt = math.sqrt(gain * 2.0)

        self.kf = np.zeros(_len)
        self.dk = np.zeros(_len)
        self.smooth = np.zeros(_len)
        self.velo = np.zeros(_len)

        self.prev = 0.0
        self.last = 0.0

        self._last_timestamp = 0  # last compute timestamp

    def resize(self, _len: int):
        self.len = _len

        self.kf = np.zeros(_len)
        self.dk = np.zeros(_len)
        self.smooth = np.zeros(_len)
        self.velo = np.zeros(_len)

    def compute(self, timestamp: float, price: np.array):
        self.prev = self.last

        if price.size != self.len:
            self.resize(price.size)

        # kahlman(x, g) =>
        #    kf = 0.0
        #    dk = x - nz(kf[1], x)
        #    smooth = nz(kf[1],x)+dk*sqrt(g*2)
        #    velo = 0.0
        #    velo := nz(velo[1],0) + (g*dk)
        #    kf := smooth+velo

        for i in range(0, self.len):
            self.dk[i] = price[i] - (price[i] if i == 0 or np.isnan(self.kf[i-1]) else self.kf[i-1])
            self.smooth[i] = (price[i] if i == 0 or np.isnan(self.kf[i-1]) else self.kf[i-1]) + self.dk[i] * self.g2sqrt
            self.velo[i] = (0.0 if i == 0 or np.isnan(self.velo[i-1]) else self.velo[i-1]) + (self.gain * self.dk[i])
            self.kf[i] = self.smooth[i] + self.velo[i]

        self.last = self.kf[-1]
        self._last_timestamp = timestamp
