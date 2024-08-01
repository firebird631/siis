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


class TickVWAPIndicator(VWAPBaseIndicator):
    """
    Volume Weighted Average indicator based on tick or trade and only keep the current and previous vwap.

    @note This version works with tick data level (TickType[]).
    """

    __slots__ = '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_tops', '_bottoms', \
        '_last_top', '_last_bottom', '_session_offset', '_prev_top', '_prev_bottom', '_volumes_dev', '_dev2'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_AVERAGE_PRICE

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def __init__(self, timeframe: float, days=2):
        super().__init__("tickvwap", 0, days)

        self._compute_at_close = False  # computed at each tick or trade

        self._prev = 0.0
        self._prev_top = 0.0
        self._prev_bottom = 0.0

        self._last = 0.0
        self._last_top = 0.0
        self._last_bottom = 0.0

        self._session_offset = 0.0

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
    def prev_top(self, scale=1.0):
        return self._prev_top * scale

    @property
    def prev_bottom(self, scale=1.0):
        return self._prev_bottom * scale

    @property
    def last(self):
        return self._last

    @property
    def last_top(self, scale=1.0):
        return self._last_top * scale

    @property
    def last_bottom(self, scale=1.0):
        return self._last_bottom * scale

    def compute(self, timestamp, tick):
        self._prev = self._last
        self._prev_top = self._last_top
        self._prev_bottom = self._last_bottom

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

        self._last = vwap

        # std dev
        self._volumes_dev += (tick[3] * tick[3]) * tick[4]  # price^2 * volume

        self._dev2 = max(self._volumes_dev / self._volumes - vwap * vwap, self._dev2)
        dev = math.sqrt(self._dev2)

        self._last = vwap
        self._last_top = vwap + dev
        self._last_bottom = vwap - dev

        self._last_timestamp = timestamp

        return vwap
