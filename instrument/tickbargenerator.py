# @date 2020-09-16
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Tick bar and reversal generators.

from datetime import datetime, timedelta
from common.utils import UTC

# from instrument.instrument import TickBar


class TickBarBaseGenerator(object):

    __slots__ = '_size', '_last_timestamp', '_last_consumed'

    def __init__(self, size):
        """
        @param size Generated tick bar tick number.
        """
        self._size = size if size > 0 else 1
        self._last_consumed = 0
        self._last_timestamp = 0.0

    def generate_from_ticks(self, from_ticks):
        """
        Generate as many tick-bar as possible from the array of ticks given in parameters.
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
        pass


class TickBarRangeGenerator(TickBarBaseGenerator):

    def __init__(self, size):
        """
        @param size Generated tick bar tick number.
        """
        super().__init(size)

    def update_from_tick(self, tick):
        pass


class TickBarReversalGenerator(TickBarBaseGenerator):

    def __init__(self, size):
        """
        @param size Generated tick bar tick number reverse at.
        """
        super().__init(size)

    def update_from_tick(self, tick):
        pass
