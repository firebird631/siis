# @date 2020-06-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Volume Weighted Average indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument
from strategy.indicator.vwap.vwapbase import VWAPBaseIndicator


# import numpy as np
# from talib import MULT as ta_MULT, STDDEV as ta_STDDEV


class TickBarVWAPIndicator(VWAPBaseIndicator):
    """
    Volume Weighted Average indicator based on tick or trade and relate to tickbars.

    The history depends on the length parameters. It is related the number of tickbars history needed.

    @note This version works with non-temporal bars (range, reversal, tick, volume, renko OHLC).
    """

    __slots__ = '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_size', '_tops', '_bottoms', \
        '_last_top', '_last_bottom', '_session_offset', '_volumes_dev', '_dev2'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_AVERAGE_PRICE

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICKBAR

    def __init__(self, timeframe: float, days=2, tickbar=50):
        super().__init__("vwap", timeframe, days)

        self._compute_at_close = False  # computed at each tick or trade

        self._prev = 0.0
        self._last = 0.0
        self._last_top = 0.0
        self._last_bottom = 0.0

        self._session_offset = 0.0

        self._size = tickbar
        self._vwaps = [0.0] * self._size

        self._tops = [0.0] * self._size
        self._bottoms = [0.0] * self._size

        self._open_timestamp = 0.0
        self._pvs = 0.0
        self._volumes = 0.0
        self._volumes_dev = 0.0
        self._dev2 = 0.0

    def setup(self, instrument):
        if instrument is None:
            return

        self._session_offset = instrument.session_offset
        self._open_timestamp = self._session_offset

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

    @property
    def last_top(self, scale=1.0):
        return self._last_top * scale

    @property
    def last_bottom(self, scale=1.0):
        return self._last_bottom * scale

    @property
    def vwaps(self):
        return self._vwaps

    @property
    def bottoms(self):
        """
        StdDev-.
        """
        return self._bottoms

    @property
    def tops(self):
        """
        StdDev+.
        """
        return self._tops

    def compute(self, timestamp, tick):
        self._prev = self._last

        if tick[0] >= self._open_timestamp + Instrument.TF_1D:
            # new session (1 day based with offset)
            self._pvs = 0.0
            self._volumes = 0.0
            self._volumes_dev = 0.0
            self._dev2 = 0.0
            self._open_timestamp = Instrument.basetime(Instrument.TF_1D, timestamp) + self._session_offset

        # cumulative
        self._pvs += tick[3] * tick[4]  # price * volume
        self._volumes += tick[4]

        vwap = self._pvs / self._volumes

        self._vwaps[-1] = vwap

        # std dev
        self._volumes_dev += tick[3] * tick[3] * tick[4]  # price^2 * volume

        self._dev2 = max(self._volumes_dev / self._volumes - vwap * vwap, self._dev2)
        dev = math.sqrt(self._dev2)

        self._tops[-1] = vwap + dev
        self._bottoms[-1] = vwap - dev

        self._last = self._vwaps[-1]
        self._last_top = self._tops[-1]
        self._last_bottom = self._bottoms[-1]
        self._last_timestamp = timestamp

        return self._vwaps

    def pushbar(self):
        self._vwaps.append(self._vwaps[-1])
        self._tops.append(self._tops[-1])
        self._bottoms.append(self._bottoms[-1])

        # constant fixed size
        if len(self._vwaps) > self._size:
            self._vwaps.pop(0)
            self._tops.pop(0)
            self._bottoms.pop(0)
