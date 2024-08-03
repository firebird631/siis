# @date 2020-06-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Per tick Volume Weighted Average indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument, TickType
from strategy.indicator.vwap.vwapbase import VWAPBaseIndicator


# import numpy as np
# from talib import MULT as ta_MULT, STDDEV as ta_STDDEV


class VWAPIndicator(VWAPBaseIndicator):
    """
    Per tick Volume Weighted Average indicator based on timeframe.
    It's a special indicator because it need to use an intraday timeframe.

    @todo Support of evening session and overnight session.
    @todo Complete finalize and check time ranges

    @note This version works with temporal bars (timeframes OHLC).
    """

    __slots__ = '_days', '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_size', \
                '_tops', '_bottoms', '_session_offset', '_volumes_dev', '_dev2'

    @classmethod
    def indicator_base(cls):
        return Indicator.BASE_TICK

    def __init__(self, timeframe:float, days=2):
        super().__init__("vwap", timeframe, days)

        self._compute_at_close = True  # only at close

        self._days = days   # number of day history

        self._prev = 0.0
        self._last = 0.0

        self._session_offset = 0.0

        self._size = days * (Instrument.TF_1D // timeframe)
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
    def days(self):
        return self._days
    
    @days.setter
    def days(self, days):
        self._days = days

    @property
    def prev(self):
        return self._prev

    @property
    def last(self):
        return self._last

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

    def generate(self, tick: TickType, finalize: bool):
        self._prev = self._last

        if tick[0] >= self._open_timestamp + Instrument.TF_1D:
            # new session (1 day based with offset)
            self._pvs = 0.0
            self._volumes = 0.0
            self._volumes_dev = 0.0
            self._dev2 = 0.0
            self._open_timestamp = Instrument.basetime(Instrument.TF_1D, tick[0]) + self._session_offset

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

        self._last_timestamp = tick[0]

        return vwap
