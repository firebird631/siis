# @date 2019-07-09
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# ZigZag indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample

import sys
import numpy as np


class ZigZagIndicator(Indicator):
    """
    ZigZag indicator

    @todo

    Choose a starting point (swing high or swing low).
    Choose % price movement.
    Identify next swing high or swing low that differs from the starting point = > % price movement.
    Draw trendline from starting point to new point.
    Identify next swing high or swing low that differs from the new point = > % price movement.
    Draw trendline.
    Repeat to most recent swing high or swing low.

    ZigZag(HL,%change=X,retrace=FALSE,LastExtreme=TRUE)
    If %change>=X,plot ZigZag
    where =
    HL=High-Low price series or Closing price series.
    %change=Minimum price movement, in percentage.
    Retrace=Is change a retracement of the previous move, or an absolute change from peak to trough?
    LastExtreme=If the extreme price is the same over multiple periods, is the extreme price the first or last observation?
    """

    __slots__ = '_threshold', '_lowers', '_highers', '_pattern'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, threshold=0.05):
        super().__init__("zigzag", timeframe)

        self._threshold = threshold

        self._lowers = []
        self._highers = []

    @property
    def threshold(self):
        return self._threshold

    @property
    def lowers(self):
        return self._lowers
    
    @property
    def highers(self):
        return self._highers

    def compute(self, timestamp, open, high, low, close):
        highers, lowers = [], []

        # @todo

        self._lowers = lowers
        self._highers = highers

        self._last_timestamp = timestamp

        return highers, lowers
