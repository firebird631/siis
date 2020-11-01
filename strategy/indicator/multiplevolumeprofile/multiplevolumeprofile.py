# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Multiple Volume Profile indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument

from common.utils import truncate

import numpy as np

# @todo Support of evening session and overnight session.


class MultipleVolumeProfileIndicator(Indicator):
    """
    Multiple Volume Profile indicator based on timeframe.
    """

    __slots__ = '_days', '_prev', '_last', '_volumes', '_open_timestamp', '_size', '_poc', '_valleys', '_peaks', \
        '_session_offset', '_price_precision', '_tick_size'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, days=2, stddev_len=5):
        super().__init__("multiplevolumeprofile", timeframe)

        self._compute_at_close = True  # only at close

        self._days = days   # number of day history

        self._prev = 0.0
        self._last = 0.0
        self._last_top = 0.0
        self._last_bottom = 0.0

        self._session_offset = 0.0

        self._price_precision = 1
        self._tick_size = 1.0

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

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001

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

    def adjust_price(self, price):
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or 8
        tick_size = self._price_limits[2] or 0.00000001

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / tick_size) * tick_size, precision)

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
                    # new session (1 day based with offset)
                    self._pvs = 0.0
                    self._volumes = 0.0
                    self._volumes_dev = 0.0
                    self._dev2 = 0.0
                    self._open_timestamp = Instrument.basetime(Instrument.TF_1D, timestamps[b]) + self._session_offset

                # avg price based on HLC3
                hlc3 = (highs[b] + lows[b] + closes[b]) / 3

                # cumulatives
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
        self._last_top = self._tops[-1]
        self._last_bottom = self._bottoms[-1]
        self._last_timestamp = timestamp

        return self._vwaps


class TickMultipleVolumeProfileIndicator(Indicator):
    """
    Multiple Volume Profile indicator based on tick or trade.
    """

    __slots__ = '_prev', '_last', '_vwaps', '_open_timestamp', '_pvs', '_volumes', '_size', '_tops', '_bottoms', \
        '_last_top', '_last_bottom', '_session_offset', '_price_precision', '_tick_size'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, tickbar=50, stddev_len=5, session_offset=0.0):
        super().__init__("tickbar-multiplevolumeprofile", timeframe)

        self._compute_at_close = False  # computed at each tick or trade

        self._prev = 0.0
        self._last = 0.0
        self._last_top = 0.0
        self._last_bottom = 0.0

        self._price_precision = 1
        self._tick_size = 1.0

        self._session_offset = session_offset

        self._size = tickbar
        self._vwaps = [0.0] * self._size

        self._tops = [0.0] * self._size
        self._bottoms = [0.0] * self._size

        self._open_timestamp = self._session_offset
        self._pvs = 0.0
        self._volumes = 0.0
        self._volumes_dev = 0.0
        self._dev2 = 0.0

    def setup(self, instrument):
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001

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

    def compute(self, timestamp, price, volume):
        self._prev = self._last

        if timestamp >= self._open_timestamp + Instrument.TF_1D:
            # new session (1 day based with offset)
            self._pvs = 0.0
            self._volumes = 0.0
            self._volumes_dev = 0.0
            self._dev2 = 0.0
            self._open_timestamp = Instrument.basetime(Instrument.TF_1D, timestamp) + self._session_offset

        # cumulatives
        self._pvs += price * volume
        self._volumes += volume              

        vwap = self._pvs / self._volumes

        self._vwaps[-1] = vwap

        # std dev
        self._volumes_dev += price * price * volume

        self._dev2 = max(self._volumes_dev / self._volumes - vwap * vwap, self._dev2)
        dev = math.sqrt(self._dev2)

        self._tops[-1] = vwap + dev
        self._bottoms[-1] = vwap - dev

        self._last = self._vwaps[-1]
        self._last_top = self._tops[-1]
        self._last_bottom = self._bottoms[-1]
        self._last_timestamp = timestamp

        return self._vwaps

    def push(self):
        self._vwaps.append(self._vwaps[-1])
        self._tops.append(self._tops[-1])
        self._bottoms.append(self._bottoms[-1])

        # constant fixed size
        if len(self._vwaps) > self._size:
            self._vwaps.pop(0)
            self._tops.pop(0)
            self._bottoms.pop(0)