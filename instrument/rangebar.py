# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Instrument range bar models.

import logging

from common.utils import timestamp_to_str

logger = logging.getLogger('siis.instrument.rangebar')


class RangeBase(object):
    """
    Non-temporal bar model for an instrument.
    Support range-bar, reversal-bar, volume-bar, renko.
    """

    __slots__ = ('_timestamp', '_duration', '_open', '_close', '_low', '_high', '_volume', '_ended')

    def __init__(self, timestamp: float, price: float = 0.0):
        """
        @param timestamp Opening timestamp in seconds.
        """
        self._timestamp = timestamp
        self._duration = 0.0

        # initial open/close
        self._open = price
        self._close = price

        # initial low/high
        self._low = price
        self._high = price

        self._volume = 0.0    # total volume for any ticks of the bar

        self._ended = False

    #
    # data
    #

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def ended(self) -> bool:
        return self._ended

    @property
    def open(self) -> float:
        return self._open

    @property
    def close(self) -> float:
        return self._close

    @property
    def high(self) -> float:
        return self._high

    @property
    def low(self) -> float:
        return self._low

    @property
    def volume(self) -> float:
        return self._volume

    def set_ohlc(self, o: float, h: float, l: float, c: float):
        self._open = o
        self._high = h
        self._low = l
        self._close = c

    def set_volume(self, ltv: float):
        self._volume = ltv

    def set_duration(self, duration: float):
        self._duration = duration

    def set_consolidated(self, cons: bool):
        self._ended = cons

    @property
    def abs_height(self) -> float:
        """
        Height in ticks from open to close, always absolute.
        """
        return self._close - self._open if self._close > self._open else self._open - self._close

    @property
    def height(self) -> float:
        """
        Height in ticks from open to close, always relative.
        """
        return self._close - self._open

    #
    # processing
    #

    def complete(self):
        self._ended = True

    #
    # conversion
    #

    def __str__(self):
        return "%s %gs %s %g/%g/%g/%g %g (h=%g)" % (
            timestamp_to_str(self._timestamp),
            self._duration,
            "UP" if self._close > self._open else "DN",
            self._open, self._high, self._low, self._close,
            self._volume,
            self.height,
        ) + (" ENDED" if self._ended else "")


class RangeBar(RangeBase):
    pass
