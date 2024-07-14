# @date 2020-09-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Footprint bar and generator.

import logging

from common.utils import timestamp_to_str

logger = logging.getLogger('siis.instrument.footprint')


class FootPrintBase(object):
    """
    Foot-print generator base model.
    It must use the ticks data and work for a specified bar (timeframe or non-temporal).
    """

    __slots__ = ('_timestamp', '_last_timestamp', '_volume', '_ended', '_open', '_close', '_low', '_high', '_ticks',
                 '_pov', '_pov_bid', '_pov_ask', '_vol_bid', '_vol_ask', '_avg_size', '_num_trades', '_dir')

    def __init__(self, timestamp: float, price: float):
        """
        @param timestamp Opening timestamp in seconds.
        """
        self._timestamp = timestamp
        self._last_timestamp = timestamp

        self._ticks = {}  # map of ticks : volume [merged volume, (bid volume, ask volume) ...]

        # initial open/close
        self._open = price
        self._close = price

        # initial low/high
        self._low = price
        self._high = price

        # or in tickbar indicators (could use X=Full or X>=VolumeFilter)
        self._volume = 0.0  # total volume for any ticks of the bar

        self._vol_bid = 0.0
        self._vol_ask = 0.0

        self._avg_size = 0.0  # trade average size or aggregated trades average size ( = volume / num_trades)
        self._num_trades = 0  # num of total trades or aggregated trades ( +1 at each trade)

        self._pov = 0.0
        self._pov_bid = 0.0
        self._pov_ask = 0.0

        self._dir = 1

        # volume delta from prev
        # volume change from prev
        # average size

        self._ended = False

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
    def ticks(self):
        return self._ticks

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

    @property
    def height(self) -> float:
        """
        Height in ticks from low to high, always positive.
        """
        return self._high - self._low

    @property
    def pov(self) -> float:
        """
        Returns the price where the bid+ask volume is the max.
        """
        return self._pov

    @property
    def pov_bid(self) -> float:
        return self._pov_bid
    
    @property
    def pov_ask(self) -> float:
        return self._pov_ask

    @property
    def direction(self) -> int:
        return self._dir

    #
    # processing
    #

    def complete(self):
        self._ended = True
        self._update_pov()

    def add_tick(self, price, volume):
        pass
        # if price in self._ticks:
        #     # @todo not index
        #     pos = self._ticks.index(price)
        #     self._ticks[pos] += volume
        # else:
        #     self._ticks.append()

    #
    # conversion
    #

    def __str__(self):
        return "%s %s %g/%g/%g/%g %g (%g/%g)" % (
            timestamp_to_str(self._timestamp),
            "UP" if self._dir > 0 else "DN",
            self._open, self._high, self._low, self._close,
            self._volume, self._vol_bid, self._vol_ask
        ) + (" ENDED" if self._ended else "")

    #
    # protected
    #

    def _update_pov(self):
        pg = 0.0
        vg = 0.0

        pb = 0.0
        vb = 0.0

        po = 0.0
        vo = 0.0

        for p, vs in self._ticks.items():
            # max volume, at price...
            if vs[0]+vs[1] == vg:
                # only if price is greater
                if p > pg:
                    vg = vs[0]+vs[1]
                    pg = p

            elif vs[0]+vs[1] > vg:
                vg = vs[0]+vs[1]
                pg = p

            # similar for bid but for the lower price
            if vs[0] == vb:
                # only if price is lower
                if p < pb:
                    vb = vs[0]
                    pb = p

            elif vs[0] > vb:
                vb = vs[0]
                pb = p

            # similar for ask but for the higher price
            if vs[1] == vo:
                # only if price is higher
                if p > po:
                    vo = vs[1]
                    po = p

            elif vs[1] > vo:
                vo = vs[1]
                po = p

        self._pov = pg  # retains the price of the higher merged volume
        self._pov_bid = pb  # and for the bid volume, the lower price
        self._pov_ask = po  # and for the ask volume, the higher price


class FootPrintBidAsk(FootPrintBase):
    """
    Tick-bar instance for an instrument with distinct bid/ask volume.
    """

    def __init__(self, timestamp: float, price: float):
        super().__init__(timestamp, price)

    def bid_vol(self, price: float) -> float:
        if price in self._ticks:
            return self._ticks[price][0]

        return 0.0

    def ask_vol(self, price: float) -> float:
        if price in self._ticks:
            return self._ticks[price][1]

        return 0.0


class FootPrintVolume(FootPrintBase):
    """
    Tick-bar instance for an instrument with merged volume.
    """

    def __init__(self, timestamp: float, price: float):
        super().__init__(timestamp, price)

    def vol(self, price: float) -> float:
        if price in self._ticks:
            return self._ticks[price]

        return 0.0


class TickBarBaseGenerator(object):
    """
    Base model for tick bar specialized generators.
    """

    __slots__ = '_size', '_last_timestamp', '_last_consumed', '_current', '_tick_size', \
        '_price_precision', '_tick_scale', '_num_trades'

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
        self._num_trades = 0

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


# class FootPrintGenerator(object):
#     """
#     Specialization for common tick bar.
#     @todo to be tested, uses RangeBarGenerator and RangeBar for the moment.
#     """
#
#     def __init__(self, size, tick_scale=1.0):
#         """
#         @param size Generated tick bar tick number.
#         """
#         super().__init__(size, tick_scale)
#
#     def _new_tickbar(self, tick):
#         # complete the current tick-bar
#         if self._current is not None:
#             self._current._ended = True
#
#         # return the current as last completed
#         last_tickbar = self._current
#
#         # create a new tick-bar
#         self._current = FootPrintBidAsk(tick[0], tick[3])
#
#         return last_tickbar
#
#     def update(self, tick):
#         if tick[0] < self._last_timestamp:
#             return None
#
#         last_tickbar = None
#
#         # @todo different case
#
#         if self._current is None:
#             last_tickbar = self._new_tickbar(tick)
#
#         elif tick[3] > self._current._high:
#             # is the price extend the size of the tick-bar outside its allowed range
#             size = int((tick[3] - self._current._low) / self._tick_size) + 1
#             if size > self._size:
#                 last_tickbar = self._new_tickbar(tick)
#
#         elif tick[3] < self._current._low:
#             # is the price extend the size of the tick-bar outside its allowed range
#             size = int((self._current._high - tick[3]) / self._tick_size) + 1
#             if size > self._size:
#                 last_tickbar = self._new_tickbar(tick)
#
#         # one more trade
#         self._num_trades += 1
#
#         # retain the last trade timestamp
#         self._current._last_timestamp = tick[0]
#
#         # last trade price as close price
#         self._current._close = tick[3]
#
#         # cumulative volume per tick-bar
#         self._current._volume += tick[4]
#
#         # cumulative volume at bid or ask
#         if tick[5] < 0:
#             self._current._vol_bid += tick[4]
#
#             if tick[3] in self._current._ticks:
#                 pass  # @todo
#
#         elif tick[5] > 0:
#             self._current._vol_ask += tick[4]
#
#         # retains low and high tick prices
#         self._current._low = min(self._current._low, tick[3])
#         self._current._high = max(self._current._high, tick[3])
#
#         # @todo
#
#         # return the last completed bar or None
#         return last_tickbar


# class TickBarReversalGenerator(TickBarBaseGenerator):
#     """
#     Variant of the tick bar generator with a reversal price.
#     """
#
#     __slots__ = '_last_price'
#
#     def __init__(self, size, tick_scale=1.0):
#         """
#         @param size Generated tick bar tick number reverse at.
#         """
#         super().__init__(size, tick_scale)
#
#         self._last_price = 0.0
#
#     def _new_tickbar(self, tick):
#         # complete the current tick-bar
#         if self._current is not None:
#             self._current._ended = True
#
#         # return the current as last completed
#         last_tickbar = self._current
#
#         # create a new tick-bar
#         self._current = FootPrintBidAsk(tick[0], tick[3])
#
#         return last_tickbar
#
#     def update(self, tick):
#         if tick[0] < self._last_timestamp:
#             return None
#
#         last_tickbar = None
#
#         adjusted_price = self.adjust_price(tick[3])
#
#         # @todo different case
#
#         if self._current is None:
#             # create a new tick-bar
#             last_tickbar = self._new_tickbar(tick)
#
#         elif self._current._dir == 0:
#             # need to initiate in the direction of the last and previous price
#             if tick[3] < self._current._open:
#                 pass
#
#             elif tick[3] > self._current._open:
#                 pass
#
#         elif tick[3] < self._current._open and self._current._dir > 0:
#             # down-tick from open
#             size = int((self._current._open - tick[3]) / self._tick_size) + 1
#             if size > self._size:
#                 last_tickbar = self._new_tickbar(tick)
#
#         elif tick[3] > self._current._open and self._current._dir < 0:
#             # up-tick from open
#             size = int((tick[3] - self._current._open) / self._tick_size) + 1
#             if size > self._size:
#                 last_tickbar = self._new_tickbar(tick)
#
#         # elif tick[3] ==
#
#         # one more trade
#         self._num_trades += 1
#
#         # retain the last trade timestamp
#         self._current._last_timestamp = tick[0]
#
#         # last trade price as close price
#         self._current._close = tick[3]
#
#         # cumulative volume per tick-bar
#         self._current._volume += tick[4]
#
#         # cumulative volume at bid or ask
#         if tick[5] < 0:
#             self._current._vol_bid += tick[4]
#
#             if tick[3] in self._current._ticks:
#                 pass  # @todo
#
#         elif tick[5] > 0:
#             self._current._vol_ask += tick[4]
#
#         # retains low and high tick prices
#         self._current._low = min(self._current._low, tick[3])
#         self._current._high = max(self._current._high, tick[3])
#
#         self._last_price = adjusted_price
#
#         # @todo
#
#         # return the last completed bar or None
#         return last_tickbar
