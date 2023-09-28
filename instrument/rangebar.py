# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Instrument range bar models.

import logging

from common.utils import timestamp_to_str

logger = logging.getLogger('siis.instrument.rangebar')


class RangeBarBase(object):
    """
    Range bar base model for an instrument.
    """

    __slots__ = '_timestamp', '_last_timestamp', '_volume', '_ended', '_open', '_close', '_ticks', '_num_trades', \
        '_avg_size', '_num_trades', '_low', '_high', '_dir'

    def __init__(self, timestamp: float, price: float):
        """
        @param timestamp Opening timestamp in seconds.
        """
        self._timestamp = timestamp
        self._last_timestamp = timestamp

        # initial open/close
        self._open = price
        self._close = price

        # initial low/high
        self._low = price
        self._high = price

        # or in tickbar indicators (could use X=Full or X>=VolumeFilter)
        self._volume = 0.0  # total volume for any ticks of the bar

        self._avg_size = 0.0  # trade average size or aggregated trades average size ( = volume / num_trades)
        self._num_trades = 0  # num of total trades or aggregated trades ( +1 at each trade)

        self._dir = 0

        self._ended = True

    #
    # data
    #

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def last_timestamp(self) -> float:
        return self._last_timestamp

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

    @property
    def direction(self) -> int:
        return self._dir

    #
    # processing
    #

    def complete(self):
        self._ended = True

    #
    # conversion
    #

    def __str__(self):
        return "%s %s %g/%g/%g/%g %g" % (
            timestamp_to_str(self._timestamp),
            "UP" if self._dir > 0 else "DN",
            self._open, self._high, self._low, self._close,
            self._volume,
        ) + (" ENDED" if self._ended else "")


class RangeBar(RangeBarBase):
    pass
