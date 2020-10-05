# @date 2020-10-03
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Volume Composite Volume Profile indicator

import math

from strategy.indicator.indicator import Indicator
from instrument.instrument import Instrument

from common.utils import truncate

import numpy as np


class CompositeVolumeProfileIndicator(Indicator):
    """
    Composite Volume Profile indicator based on timeframe.
    It is prefered to use the TickCompositeVolumeProfileIndicator version because this timeframe based version
    will reduce the precision, better using lower timeframe, but best is still per tick or trade update.
    """

    __slots__ = '_volumes', '_open_timestamp', '_poc', '_valleys', '_peaks', '_sensibility', '_price_precision', '_tick_size'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, sensibility=10.0, session_offset=0.0):
        super().__init__("compositevolumeprofile", timeframe)

        self._compute_at_close = True  # only at close

        self._sensibility = sensibility

        self._price_precision = 8
        self._tick_size = 1.0

        self._session_offset = session_offset

        self._volumes = {}
        self._peaks = []
        self._valleys = []

        self._open_timestamp = self._session_offset

        self._poc = 0.0

    def setup(self, instrument):
        if instrument is None:
            return

        self._precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001

    @property
    def sensibility(self):
        return self._sensibility

    @property
    def poc(self):
        """
        POC price level.
        """
        return self._poc

    @property
    def volumes(self):
        """
        Returns a dict of price and volume.
        """
        return self._volumes

    @property
    def peaks(self):
        """
        Returns an array of the prices for the detected peaks.
        """
        return self._peaks
    
    @property
    def valleys(self):
        """
        Returns an array of the prices for the detected valleys.
        """
        return self._valleys

    def compute(self, timestamp, timestamps, highs, lows, closes, volumes):
        self._prev = self._last

        # only update at close, no overwrite
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe) + 1, len(timestamps))

        # base index
        num = len(timestamps)

        for b in range(num-delta, num):
            # for any new candles
            if timestamps[b] > self._last_timestamp:
                if timestamps[b] >= self._open_timestamp + self._timeframe:
                    # new session (timeframe based session with offset)
                    self._volumes = {}
                    self._peaks = []
                    self._valleys = []
                    self._poc = 0.0
                    self._open_timestamp = Instrument.basetime(self._timeframe, timestamps[b]) + self._session_offset

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


class TickCompositeVolumeProfileIndicator(Indicator):
    """
    Composite Volume Profile indicator base on tick or trade.
    """

    __slots__ = '_volumes', '_open_timestamp', '_poc', '_valleys', '_peaks', '_sensibility'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, sensibility=10.0, session_offset=0.0):
        super().__init__("compositevolumeprofile", timeframe)

        self._compute_at_close = False  # at each trade

        self._sensibility = sensibility
        self._session_offset = session_offset

        self._volumes = {}
        self._peaks = []
        self._valleys = []

        self._open_timestamp = self._session_offset

        self._poc = 0.0

    @property
    def sensibility(self):
        return self._sensibility

    @property
    def poc(self):
        """
        POC price level.
        """
        return self._poc

    @property
    def volumes(self):
        """
        Returns a dict of price and volume.
        """
        return self._volumes

    @property
    def peaks(self):
        """
        Returns an array of the prices for the detected peaks.
        """
        return self._peaks
    
    @property
    def valleys(self):
        """
        Returns an array of the prices for the detected valleys.
        """
        return self._valleys

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
