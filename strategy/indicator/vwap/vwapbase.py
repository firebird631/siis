# @date 2020-06-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Volume Weighted Average indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument


# import numpy as np
# from talib import MULT as ta_MULT, STDDEV as ta_STDDEV


class VWAPBaseIndicator(Indicator):
    """
    Volume Weighted Average indicator based on timeframe.
    It's a special indicator because it need to use an intraday timeframe.

    @todo Support of evening session and overnight session.
    @todo Complete finalize and check time ranges

    @note This version works with temporal bars (timeframes OHLC).
    """

    __slots__ = '_days', '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_size', \
        '_tops', '_bottoms', '_session_offset', '_volumes_dev', '_dev2'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_AVERAGE_PRICE

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    @classmethod
    def builder(cls, base_type: int, timeframe: float, **kwargs):
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.vwap.barvwap import BarVWAPIndicator
            return BarVWAPIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.vwap.barvwap import BarVWAPIndicator
            return BarVWAPIndicator(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.vwap.vwap import VWAPIndicator
            return VWAPIndicator(timeframe, **kwargs)

        return None

    def __init__(self, name: str, timeframe: float, days=2):
        super().__init__(name, timeframe)

        self._compute_at_close = True  # only at close

        self._days = days  # number of day history

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

    def compute(self, timestamp, timestamps, highs, lows, closes, volumes):
        self._prev = self._last

        # only update at close, no overwrite
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe) + 1, len(timestamps))

        # base index
        num = len(timestamps)

        # @todo check because if not computed at close... or will not compute complete bar or will overwrite volumes

        for b in range(num - delta, num):
            # for any new candles
            if timestamps[b] > self._last_timestamp:
                if timestamps[b] >= self._open_timestamp + Instrument.TF_1D:
                    # new session (1 day based with offset)
                    self._pvs = 0.0
                    self._volumes = 0.0
                    self._volumes_dev = 0.0
                    self._dev2 = 0.0
                    self._open_timestamp = Instrument.basetime(Instrument.TF_1D, timestamps[b]) + self._session_offset

                # avg price based on HLC3
                hlc3 = (highs[b] + lows[b] + closes[b]) / 3

                # cumulative
                self._pvs += hlc3 * volumes[b]
                self._volumes += volumes[b]

                vwap = self._pvs / self._volumes

                self._vwaps.append(vwap)

                # std dev
                self._volumes_dev += hlc3 * hlc3 * volumes[b]

                self._dev2 = max(self._volumes_dev / self._volumes - vwap * vwap, self._dev2)
                dev = math.sqrt(self._dev2)

                self._tops.append(vwap + dev)
                self._bottoms.append(vwap - dev)

                # constant fixed size
                if len(self._vwaps) > self._size:
                    self._vwaps.pop(0)
                    self._tops.pop(0)
                    self._bottoms.pop(0)

        self._last = self._vwaps[-1]
        self._last_timestamp = timestamp

        return self._vwaps
