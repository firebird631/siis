# @date 2020-09-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Tick bar and reversal generators.

from datetime import datetime, timedelta
from common.utils import UTC

from instrument.instrument import TickBar


class TickBarBaseGenerator(object):

    __slots__ = '_size', '_last_timestamp', '_last_consumed'

    def __init__(self, size, tick_size=1.0):
        """
        @param size Generated tick bar tick number.
        @param tick_size Size of the tick in price (default 1.0)
        """
        self._size = size if size > 0 else 1
        self._tick_size = tick_size

        self._last_consumed = 0
        self._last_timestamp = 0.0

    def generate_from_ticks(self, from_ticks):
        """
        Generate as many tick-bar as possible from the array of ticks or trades given in parameters.
        """
        to_tickbars = []
        self._last_consumed = 0

        for from_tick in from_ticks:
            to_tickbar = self.update_from_tick(from_tick)
            if to_tickbar:
                to_tickbars.append(to_tickbar)

            self._last_consumed += 1

        return to_tickbars

    def update_from_tick(self, tick):
        """
        Overrides this method to implements specifics computed tick-bar model from a single tick or trade.
        """
        pass


class TickBarRangeGenerator(TickBarBaseGenerator):

    def __init__(self, size):
        """
        @param size Generated tick bar tick number.
        """
        super().__init(size)

        self._current = None

    def _new_tickbar(self, tick):
        # complete the current tick-bar
        self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = TickBar(tick[0], tick[1])

        return last_tickbar

    def update_from_tick(self, tick):
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        if self._current is None:
            last_tickbar = self._new_tickbar(tick)

        elif tick[1] > self._current._high:
            # is the price extend the size of the tick-bar outside of its allowed range
            size = int((tick[1] - self._current._low) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        elif tick[1] < self._current._low:
            # is the price extend the size of the tick-bar outside of its allowed range
            size = int((self._current._high - tick[1]) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        # one more trade
        self._num_trades += 1

        # retain the last trade timestamp
        self._current._last_timestamp = tick[0]

        # last trade price as close price
        self._current._close = tick[1]

        # cumulative volume per tick-bar
        self._current._volume += tick[3]

        # cumulative volume at bid or ask
        if tick[4] < 0:
            self._current._vol_bid += tick[3]

            if tick[1] in self._current._ticks:

        elif tick[4] > 0:
            self._current._vol_ofr += tick[3]

        # retains low and high tick prices
        self._current._low = min(self._current._low, tick[1])
        self._current._high = max(self._current._high, tick[1])

        # @todo

        # return the last completed bar or None
        return last_tickbar


class TickBarReversalGenerator(TickBarBaseGenerator):

    def __init__(self, size):
        """
        @param size Generated tick bar tick number reverse at.
        """
        super().__init(size)

    def _new_tickbar(self, tick):
        # complete the current tick-bar
        self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = TickBar(tick[0], tick[1])

        # opposite direction tick-bar
        self._current._dir = -last_tickbar._dir

        return last_tickbar

    def update_from_tick(self, tick):
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        if self._current is None:
            # complete the current tick-bar
            self._current._ended = True

            # return the current as last completed
            last_tickbar = self._current

            # create a new tick-bar
            self._current = TickBar(tick[0], tick[1])

        elif tick[1] < self._current._open and self._current._dir > 0:
            # down-tick from open
            size = int((self._current._open - tick[1]) / self._tick_size) + 1:

            if size > self._size:
                self._current = TickBar(tick[0], tick[1])

        elif tick[1] > self._current._open and self._current._dir < 0:
            # up-tick from open
            size = int((tick[1] - self._current._open) / self._tick_size) + 1:

            if size > self._size:
                self._current = TickBar(tick[0], tick[1])

        # one more trade
        self._num_trades += 1

        # retain the last trade timestamp
        self._current._last_timestamp = tick[0]

        # last trade price as close price
        self._current._close = tick[1]

        # cumulative volume per tick-bar
        self._current._volume += tick[3]

        # cumulative volume at bid or ask
        if tick[4] < 0:
            self._current._vol_bid += tick[3]
            
            if tick[1] in self._current._ticks:

        elif tick[4] > 0:
            self._current._vol_ofr += tick[3]

        # retains low and high tick prices
        self._current._low = min(self._current._low, tick[1])
        self._current._high = max(self._current._high, tick[1])

        # @todo

        # return the last completed bar or None
        return last_tickbar
