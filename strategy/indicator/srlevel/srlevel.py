# @date 2022-10-17
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Support/resistance indicator based on OHLCs

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument


class SRLevelIndicator(Indicator):
    """
    Support/resistance indicator based on OHLCs based on timeframe.

    @todo Support of evening session and overnight session.
    @todo Complete finalize and check time ranges
    """

    __slots__ = '_history', '_currents', '_previous'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_SUPPORT_RESISTANCE

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, history=500):
        super().__init__("srlevel", timeframe)

        self._compute_at_close = True  # only at close

        self._history = history  # number of candles of history

        self._currents = []
        self._previous = []

    @property
    def currents(self):
        return self._currents

    @property
    def previous(self):
        return self._previous

    def bottoms(self, price):
        """
        Give the current and previous supports below given price.
        """
        bottoms = []

        # @todo

        return bottoms

    def tops(self, price):
        """
        Give the current and previous resistances below given price.
        """
        resistances = []

        # @todo

        return resistances

    def compute(self, timestamp, timestamps, opens, highs, lows, closes):
        # only update at close, no overwrite
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe) + 1, len(timestamps))

        # base index
        num = len(timestamps)

        for b in range(num - delta, num):
            # for any new candles
            if timestamps[b] > self._last_timestamp:
                # @todo
                pass

        # if new currents move to past @todo

        self._last_timestamp = timestamp

        return self._currents
