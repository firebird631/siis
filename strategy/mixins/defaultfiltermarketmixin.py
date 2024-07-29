# @date 2023-09-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Default implementation of filter_market, mixin

from typing import Tuple

from instrument.instrument import Instrument
from strategy.strategy import Strategy


class DefaultFilterMarketMixin(object):
    """
    Default implementation of filter_market, mixin.
    """
    def __init__(self, strategy: Strategy, instrument: Instrument, base_timeframe: float, params: dict):
        super().__init__(strategy, instrument, base_timeframe, params)

        self._last_filter_cache = (0, False, False)

    def filter_market(self, timestamp: float) -> Tuple[bool, bool]:
        """
        The first boolean mean accept, the second compute.
        Return True, True if the market is accepted and can be computed this time.
        """
        if timestamp - self._last_filter_cache[0] < 60 * 60:  # only once per hour
            return self._last_filter_cache[1], self._last_filter_cache[2]

        if self.instrument.market_price is not None and self.instrument.market_price < self.min_price:
            # accepted but price is very small (too binary but maybe interesting)
            self._last_filter_cache = (timestamp, True, False)
            return True, False

        if self.instrument.vol24h_quote is not None and self.instrument.vol24h_quote < self.min_vol24h:
            # accepted but 24h volume is very small (rare possibilities of exit)
            self._last_filter_cache = (timestamp, True, False)
            return True, False

        self._last_filter_cache = (timestamp, True, True)

        return True, True
