# @date 2020-09-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Tick bar and reversal generators.

from datetime import datetime, timedelta
from common.utils import UTC

from instrument.tickbar import TickBarBidAsk, TickBarVolume


class TickBarBaseGenerator(object):

    __slots__ = '_size', '_last_timestamp', '_last_consumed', '_current', '_tick_size', '_price_precision', '_tick_scale'

    def __init__(self, size, tick_scale=1.0):
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
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / self._tick_size) * self._tick_size, self._price_precision)

    def generate(self, from_ticks):
        """
        Generate as many tick-bar as possible from the array of ticks or trades given in parameters.
        """
        to_tickbars = []
        self._last_consumed = 0

        for from_tick in from_ticks:
            to_tickbar = self.update(from_tick)
            if to_tickbar:
                to_tickbars.append(to_tickbar)

            self._last_consumed += 1

        return to_tickbars

    def update(self, tick):
        """
        Overrides this method to implements specifics computed tick-bar model from a single tick or trade.
        """
        pass


class TickBarRangeGenerator(TickBarBaseGenerator):

    def __init__(self, size, tick_scale=1.0):
        """
        @param size Generated tick bar tick number.
        """
        super().__init__(size, tick_scale)

    def _new_tickbar(self, tick):
        # complete the current tick-bar
        self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = TickBarBidAsk(tick[0], tick[3])

        return last_tickbar

    def update(self, tick):
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        # @todo different case

        if self._current is None:
            last_tickbar = self._new_tickbar(tick)

        elif tick[3] > self._current._high:
            # is the price extend the size of the tick-bar outside of its allowed range
            size = int((tick[3] - self._current._low) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        elif tick[3] < self._current._low:
            # is the price extend the size of the tick-bar outside of its allowed range
            size = int((self._current._high - tick[3]) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        # one more trade
        self._num_trades += 1

        # retain the last trade timestamp
        self._current._last_timestamp = tick[0]

        # last trade price as close price
        self._current._close = tick[3]

        # cumulative volume per tick-bar
        self._current._volume += tick[4]

        # cumulative volume at bid or ask
        if tick[5] < 0:
            self._current._vol_bid += tick[4]

            if tick[3] in self._current._ticks:
                pass  # @todo

        elif tick[5] > 0:
            self._current._vol_ask += tick[4]

        # retains low and high tick prices
        self._current._low = min(self._current._low, tick[3])
        self._current._high = max(self._current._high, tick[3])

        # @todo

        # return the last completed bar or None
        return last_tickbar


class TickBarReversalGenerator(TickBarBaseGenerator):

    __slots__ = '_last_price'

    def __init__(self, size, tick_scale=1.0):
        """
        @param size Generated tick bar tick number reverse at.
        """
        super().__init__(size, tick_scale)

        self._last_price = 0.0

    def _new_tickbar(self, tick):
        # complete the current tick-bar
        if self._current is not None:
            self._current._ended = True

        # return the current as last completed
        last_tickbar = self._current

        # create a new tick-bar
        self._current = TickBarBidAsk(tick[0], tick[3])

        return last_tickbar

    def update(self, tick):
        if tick[0] < self._last_timestamp:
            return None

        last_tickbar = None

        adjusted_price = self.adjust_price(tick[3])

        # @todo different case

        if self._current is None:
            # create a new tick-bar
            last_tickbar = self._new_tickbar(tick)

        elif self._current._dir == 0:
            # need to initiate in the direction of the last and previous price
            if tick[3] < self._current._open:
                pass

            elif tick[3] > self._current._open:
                pass

        elif tick[3] < self._current._open and self._current._dir > 0:
            # down-tick from open
            size = int((self._current._open - tick[3]) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        elif tick[3] > self._current._open and self._current._dir < 0:
            # up-tick from open
            size = int((tick[3] - self._current._open) / self._tick_size) + 1

            if size > self._size:
                last_tickbar = self._new_tickbar(tick)

        # elif tick[3] == 

        # one more trade
        self._num_trades += 1

        # retain the last trade timestamp
        self._current._last_timestamp = tick[0]

        # last trade price as close price
        self._current._close = tick[3]

        # cumulative volume per tick-bar
        self._current._volume += tick[4]

        # cumulative volume at bid or ask
        if tick[5] < 0:
            self._current._vol_bid += tick[4]

            if tick[3] in self._current._ticks:
                pass  # @todo

        elif tick[5] > 0:
            self._current._vol_ask += tick[4]

        # retains low and high tick prices
        self._current._low = min(self._current._low, tick[3])
        self._current._high = max(self._current._high, tick[3])

        self._last_price = adjusted_price

        # @todo

        # return the last completed bar or None
        return last_tickbar
