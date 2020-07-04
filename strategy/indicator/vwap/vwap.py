7# @date 2020-06-30
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Volume Weighted Average indicator

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument

import numpy as np
from talib import MULT as ta_MULT


class VWAPIndicator(Indicator):
    """
    Volume Weighted Average indicator.
    It's a special indicator because it need to use an intraday timeframe.

    @todo test and validation, but how to optimize the array
    """

    __slots__ = '_days', '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_size'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_MOMENTUM_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, days=2):
        super().__init__("vwap", timeframe)

        self._compute_at_close = True  # only at close

        self._days = days   # number of day history

        self._prev = 0.0
        self._last = 0.0

        self._size = days * (Instrument.TF_1D // timeframe)
        self._vwaps = [0.0] * self._size

        self._open_timestamp = 0.0
        self._pvs = 0.0
        self._volumes = 0.0

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

    def compute(self, timestamp, timestamps, highs, lows, closes, volumes):
        self._prev = self._last

        # only update at close, no overwrite
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe) + 1, len(timestamps))

        # base index
        num = len(timestamps)

        for b in range(num-delta, num):
            # for any new candles
            if timestamps[b] > self._last_timestamp:
                if timestamps[b] >= self._open_timestamp + Instrument.TF_1D:
                    # next daily candle
                    self._pvs = 0.0
                    self._volumes = 0.0
                    self._open_timestamp = Instrument.basetime(Instrument.TF_1D, timestamps[b])

                hlc3 = (highs[b] + lows[b] + closes[b]) / 3

                self._pvs += hlc3 * volumes[b]
                self._volumes += volumes[b]

                self._vwaps.append(self._pvs / self._volumes)

                # constant fixed size
                if len(self._vwaps) > self._size:
                    self._vwaps.pop(0)

        self._last = self._vwaps[-1]
        self._last_timestamp = timestamp

        return self._vwaps
