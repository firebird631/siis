# @date 2020-09-19
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Tick-bar based strategy trader. 

from __future__ import annotations

from typing import List, Tuple

import copy

from instrument.instrument import Instrument

from monitor.streamable import Streamable, StreamMemberInt

from .strategytrader import StrategyTrader

import logging
logger = logging.getLogger('siis.strategy.tickbarbasedstrategytrader')


class TickBarBasedStrategyTrader(StrategyTrader):
    """
    Tick-bar based strategy trader base class.

    There is no OHLC in this abstraction. It is tick or trade based.
    It only works with a tick or trade data flow.

    But it is possible to internally compute OHLC for some specifics needs.
    There is no support of sub per timeframe.
    
    A single configuration of tick-bar array can be generated.
    """

    def __init__(self, strategy, instrument, depth=50):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        """
        super().__init__(strategy, instrument)

        self._base_timeframe = Instrument.TF_TICK

        self.tickbar_generator = None  # can be a TickBarRangeGenerator or TickBarReversalGenerator.
        self._tickbar_streamer = None

        self.depth = depth

        self.prev_price = 0.0
        self.last_price = 0.0

        self.last_timestamp = 0.0

    @property
    def is_tickbars_based(self):
        return True

    def update_tickbar(self, timestamp: float):
        """
        Update the current tickbar according to the last trade and timestamp or create a new tickbar.
        @note Thread-safe method.
        """       
        with self._mutex:
            # update at tick or trade
            ticks = self.instrument.ticks()  # self.instrument.ticks_after(self.last_timestamp)

            generated = self.tickbar_generator.generate(ticks)
            if generated:
                self.instrument.add_tickbar(generated)

            self.instrument.add_tickbar(copy.copy(self.tickbar_generator.current), self.depth)

            # keep prev and last price at processing step
            if self.instrument.ticks():
                self.prev_price = self.last_price

                # last tick mid
                self.last_price = (self.instrument.ticks()[-1][1] + self.instrument.ticks()[-1][2]) * 0.5

            # no longer need them
            self.instrument.clear_ticks()

    def update_tickbar_ext(self, timestamp: float) -> List[Tuple]:
        # update data at tick level
        with self._mutex:
            # update at tick or trade
            ticks = self.instrument.detach_ticks()

            generated = self.tickbar_generator.generate(ticks)
            if generated:
                self.instrument.add_tickbar(generated)

            self.instrument.add_tickbar(copy.copy(self.tickbar_generator.current), self.depth)

            # keep prev and last price at processing step
            if self.instrument.ticks():
                self.prev_price = self.last_price

                # last tick mid
                self.last_price = (self.instrument.ticks()[-1][1] + self.instrument.ticks()[-1][2]) * 0.5

            return ticks

    #
    # streaming
    #

    def setup_streaming(self):
        super().setup_streaming()

    def stream(self):
        super().stream()

    def create_chart_streamer(self, timeframe) -> Streamable:
        streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_CHART,
                              self.strategy.identifier, "%s:%i" % (self.instrument.market_id, timeframe.tf))
        streamer.add_member(StreamMemberInt('tf'))

        timeframe.setup_streamer(streamer)

        return streamer

    def subscribe_info(self) -> bool:
        result = False

        with self._mutex:
            if not self._global_streamer:
                self.setup_streaming()

            if self._global_streamer:
                self._global_streamer.use()
                result = True

        return result

    def unsubscribe_info(self) -> bool:
        result = False

        with self._mutex:
            if self._global_streamer:
                self._global_streamer.unuse()

                if self._global_streamer.is_free():
                    self._global_streamer = None

                result = True

        return result

    def subscribe_stream(self, tf: float) -> bool:
        """
        Use or create a specific streamer.
        @param 
        """
        result = False

        with self._mutex:
            pass  # @todo

        return False

    def unsubscribe_stream(self, tf: float) -> bool:
        """
        Delete a specific streamer when no more subscribers.
        """
        result = False

        with self._mutex:
            pass  # @todo

        return result

    def report_state(self, mode: int = 0) -> dict:
        """
        Collect the state of the strategy trader (instant) and return a dataset.
        And add the per timeframe dataset.
        """
        result = super().report_state(mode)

        if mode == 0:
            result['data'] += self.report_tickbar_state()

        return result

    def report_tickbar_state(self):
        """
        Report the properties of the state of the tickbar, according to what is computed and what is implemented.
        To be overloaded.
        """
        return []
