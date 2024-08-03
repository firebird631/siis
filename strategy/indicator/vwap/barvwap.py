# @date 2020-06-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Bar based Volume Weighted Average indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument
from strategy.indicator.vwap.vwapbase import VWAPBaseIndicator


# import numpy as np
# from talib import MULT as ta_MULT, STDDEV as ta_STDDEV


class BarVWAPIndicator(VWAPBaseIndicator):
    """
    Volume Weighted Average indicator based on bar.

    @note This version works with tick data level (TickType[]).
    """

    __slots__ = '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_tops', '_bottoms', \
        '_session_offset', '_volumes_dev', '_dev2'

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def __init__(self, timeframe: float, days=2):
        super().__init__("barvwap", 0, days)

        self._compute_at_close = False  # computed at each tick or trade

        self._prev = 0.0
        self._last = 0.0

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
    def last(self):
        return self._last

    # @todo generate
