# @date 2023-09-27
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Range bar generators.

import logging
from typing import Union

from common.utils import truncate

from instrument.rangebar import RangeBar

logger = logging.getLogger('siis.instrument.rangebar')


class BarGeneratorBase(object):
    """
    Base model for non temporal bar specialized generators.
    """

    __slots__ = '_size', '_last_timestamp', '_last_consumed', '_current', '_tick_size', '_last_price', \
        '_price_precision', '_tick_scale'

    _size: int
    _tick_scale: float
    _price_precision: int
    _tick_size: float
    _last_consumed: int
    _last_timestamp: float
    _last_price: float
    _current: Union[RangeBar, None]

    def __init__(self, size: int, tick_scale: float = 1.0):
        """
        @param size Generated tick bar tick number.
        @param tick_scale Regroup ticks by a scalar (default 1.0 for non grouping).
        """
        self._size = size if size > 0 else 1

        self._tick_scale = tick_scale

        self._price_precision = 1
        self._tick_size = 1.0

        self._last_consumed = 0
        self._last_timestamp = 0.0

        self._last_price = 0.0

        self._current = None

    @property
    def size(self):
        return self._size

    @property
    def tick_scale(self):
        return self._tick_scale

    @property
    def tick_size(self):
        return self._tick_size

    @property
    def price_precision(self):
        return self._price_precision

    @property
    def current(self):
        return self._current

    def setup(self, instrument):
        """
        Setup some constant from instrument.
        The tick size is scaled by the tick_scale factor.
        """
        if instrument is None:
            return

        self._price_precision = instrument.price_precision or 8
        self._tick_size = instrument.tick_price or 0.00000001 * self._tick_scale

    def adjust_price(self, price):
        """
        Adjust the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    def generate(self, from_ticks):
        """
        Generate as many range-bar as possible from the array of ticks or trades given in parameters.
        """
        to_tickbars = []
        self._last_consumed = 0

        for from_tick in from_ticks:
            to_tickbar = self.update(from_tick)
            if to_tickbar:
                # if self.size == 16:
                #     logger.debug(str(to_tickbar))
                to_tickbars.append(to_tickbar)

            self._last_consumed += 1

        return to_tickbars

    def update(self, tick):
        """
        Overrides this method to implements specifics computed tick-bar model from a single tick or trade.
        """
        pass


class RangeBarGenerator(BarGeneratorBase):
    """
    Specialization for common range bar.
    """

    def __init__(self, size: int, tick_scale: float = 1.0):
        """
        @param size Generated tick bar tick number.
        """
        super().__init__(size, tick_scale)

    def _new_range_bar(self, tick):
        # complete the current tick-bar
        if self._current is not None:
            self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = RangeBar(tick[0], tick[3])

        return last_tickbar

    def update(self, tick):
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

    def _new_range_bar(self, tick):
        # complete the current tick-bar
        if self._current is not None:
            self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = RangeBar(tick[0], tick[3])

        # reset reversing state
        self._reversing = 0

        return last_tickbar

    def update(self, tick):
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
