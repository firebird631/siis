# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Range bar generators.

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass

from instrument.instrument import TickType
from instrument.bar import RangeBar
from instrument.bargeneratorbase import BarGeneratorBase

import logging
logger = logging.getLogger('siis.instrument.rangebargenerator')


class RangeBarGenerator(BarGeneratorBase):
    """
    Specialization for common range bar.
    """

    def __init__(self, size: int, tick_scale: float = 1.0):
        """
        @param size Generated tick bar tick number.
        """
        super().__init__(size, tick_scale)

    def _new_range_bar(self, tick: TickType) -> RangeBar:
        # complete the current tick-bar
        if self._current is not None:
            self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = RangeBar(tick[0], tick[3])

        return last_tickbar

    def update(self, tick: TickType) -> Optional[RangeBar]:
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        if self._current is None:
            last_tickbar = self._new_range_bar(tick)

        # is the price extend the size of the range-bar outside its allowed range
        if tick[3] > self._current._high:
            size = int((tick[3] - self._current._low) / self._tick_size)
            if size > self._size:
                last_tickbar = self._new_range_bar(tick)

        elif tick[3] < self._current._low:
            size = int((self._current._high - tick[3]) / self._tick_size)
            if size > self._size:
                last_tickbar = self._new_range_bar(tick)

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
