# @date 2020-09-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Instrument tickbar models.

import logging

from common.utils import timestamp_to_str

logger = logging.getLogger('siis.instrument.tickbar')


class TickBarBase(object):
    """
    Tick-bar base model for an instrument.
    It is mostly for futures market where tick step are fixed by instrument but the generator can use a specific
    range of price to make aggregates.
    This is a more complex object than RangeBar. Tick-bar is similar to what is found with foot-print.
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


class TickBarBidAsk(TickBarBase):
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


class TickBarVolume(TickBarBase):
    """
    Tick-bar instance for an instrument with merged volume.
    """

    def __init__(self, timestamp: float, price: float):
        super().__init__(timestamp, price)

    def vol(self, price: float) -> float:
        if price in self._ticks:
            return self._ticks[price]

        return 0.0
