# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal Ball indicator strategy trader.

from typing import Tuple

from strategy.timeframestrategytrader import TimeframeStrategyTrader

from instrument.instrument import Instrument

from .cbaanalyser import CrystalBallAAnalyser

import logging
logger = logging.getLogger('siis.strategy.crystalball')


class CrystalBallStrategyTrader(TimeframeStrategyTrader):
    """
    Crystal Ball indicator strategy trader.
    """

    def __init__(self, strategy, instrument, params):
        super().__init__(strategy, instrument, Instrument.TF_TICK, params)

        self.register_analyser('A', CrystalBallAAnalyser)

        self.setup_analysers(params)

        self._last_filter_cache = (0, False, False)

        self.setup_streaming()

    def filter_market(self, timestamp: float) -> Tuple[bool, bool]:
        """
        The first boolean mean accept, the second compute.
        Return True, True if the market is accepted and can be computed this time.
        """
        if timestamp - self._last_filter_cache[0] < 60*60:  # only once per hour
            return self._last_filter_cache[1], self._last_filter_cache[2]

        # if there is no actives trades we can avoid computation on some uninteresting markets
        if self.trades:
            if self.instrument.vol24h_quote is not None and self.instrument.vol24h_quote < self.min_vol24h:
                # accepted but 24h volume is very small (rare possibilities of exit)
                self._last_filter_cache = (timestamp, True, False)
                return True, False

        self._last_filter_cache = (timestamp, True, True)
        return True, True

    def compute(self, timestamp: float):
        # split entries from exits signals
        entries = []
        exits = []

        for tf, sub in self.timeframes.items():
            if sub.update_at_close:
                if sub.need_update(timestamp):
                    compute = True
                else:
                    compute = False
            else:
                compute = True

            if compute:
                signal = sub.process(timestamp)
                if signal:
                    if signal.signal == signal.SIGNAL_ENTRY:
                        entries.append(signal)
                    elif signal.signal == signal.SIGNAL_EXIT:
                        exits.append(signal)

        # finally, sort them by timeframe ascending
        entries.sort(key=lambda s: s.timeframe)
        exits.sort(key=lambda s: s.timeframe)

        return entries, exits

    def process(self, timestamp):
        # update data at tick level
        self.generate_bars_from_ticks(timestamp)

        accept, compute = self.filter_market(timestamp)
        if not accept:
            return

        # and compute
        entries = []
        exits = []

        if compute:
            entries, exits = self.compute(timestamp)

        trader = self.strategy.trader()

        if not trader:
            self._last_filter_cache = (timestamp, False, False)
            return False, False

        for _entry in entries:
            self.notify_signal(timestamp, _entry)

        for _exit in exits:
            self.notify_signal(timestamp, _exit)

        # update user managed actives trades
        self.update_trades(timestamp)
