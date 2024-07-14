# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Reversal bar generator.

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass

from instrument.instrument import TickType
from instrument.bar import ReversalBar
from instrument.rangebargenerator import BarGeneratorBase

import logging
logger = logging.getLogger('siis.instrument.reversalbargenerator')


class ReversalBarGenerator(BarGeneratorBase):
    """
    Specialization for reversal bar.
    """

    __slots__ = '_reversal', '_reversing'

    _reversal: int
    _reversing: int

    def __init__(self, size: int, reversal: int, tick_scale=1.0):
        """
        @param size Generated tick bar tick number.
        """
        super().__init__(size, tick_scale)

        self._reversal = reversal
        self._reversing = 0

    def _new_range_bar(self, tick: TickType) -> ReversalBar:
        # complete the current tick-bar
        if self._current is not None:
            self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = ReversalBar(tick[0], tick[3])

        # reset reversing state
        self._reversing = 0

        return last_tickbar

    def update(self, tick: TickType) -> Optional[ReversalBar]:
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        if self._current is None:
            last_tickbar = self._new_range_bar(tick)

        # close at reversal size
        if self._reversing > 0:
            size = int((tick[3] - self._current._low) / self._tick_size)
            if size > self._reversal:
                last_tickbar = self._new_range_bar(tick)

        elif self._reversing < 0:
            size = int((self._current._high - tick[3]) / self._tick_size)
            if size > self._reversal:
                last_tickbar = self._new_range_bar(tick)

        # lookup for reversal size
        if tick[3] > self._current._high:
            size = int((tick[3] - self._current._low) / self._tick_size)
            if size >= self._size:
                self._reversing = -1

        elif tick[3] < self._current._low:
            size = int((self._current._high - tick[3]) / self._tick_size)
            if size > self._size:
                self._reversing = 1

        # update the current bar

        # duration of the bar in seconds
        self._current._duration = tick[0] - self._current._timestamp

        # last trade price as close price
        self._current._close = tick[3]

        # cumulative volume per tick-bar
        self._current._volume += tick[4]

        # retains low and high tick prices
        self._current._low = min(self._current._low, tick[3])
        self._current._high = max(self._current._high, tick[3])

        # return the last completed bar or None
        return last_tickbar
