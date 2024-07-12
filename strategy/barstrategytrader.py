# @date 2020-09-19
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Strategy trader base model using non-temporal bar

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, List, Tuple, Any, Dict

from .strategysignal import StrategySignal

if TYPE_CHECKING:
    from strategytradercontext import StrategyTraderContext
    from trade.strategytrade import StrategyTrade

    from .strategyrangebaranalyser import StrategyRangeBarAnalyser

import copy

from instrument.instrument import Instrument

from monitor.streamable import Streamable, StreamMemberInt

from .strategybaseanalyser import StrategyBaseAnalyser
from .strategytrader import StrategyTrader

import logging
logger = logging.getLogger('siis.strategy.barstrategytrader')
error_logger = logging.getLogger('siis.error.strategy.barstrategytrader')
traceback_logger = logging.getLogger('siis.traceback.strategy.barstrategytrader')


class BarStrategyTrader(StrategyTrader):
    """
    Strategy trader base model using non-temporal bar (range-bar, reversal-bar, volume-bar, renko).
    @note Currently support only range-bars.

    There is no OHLC in this abstraction. It is tick or trade based.
    It only works with a tick or trade data flow.

    But it is possible to internally compute OHLC for some specifics needs.
    There is no support of sub per timeframe.
    
    A single configuration of tick-bar array can be generated.
    """

    _tickbars_registry: Dict[str, Any]
    tickbars: Dict[int, StrategyRangeBarAnalyser]
    _tickbars_streamers: Dict[int, Streamable]

    def __init__(self, strategy, instrument, depth=50, params: dict = None):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        """
        super().__init__(strategy, instrument, params)

        self._base_timeframe = Instrument.TF_TICK

        self.depth = depth

        self.prev_price = 0.0
        self.last_price = 0.0

        self.last_timestamp = 0.0

        self._tickbars_registry = {}
        self.tickbars = {}
        self._tickbars_streamers = {}

    def register_tickbar(self, mode: str, class_model: Any):
        if mode and class_model:
            self._tickbars_registry[mode] = class_model

    def setup_tickbars(self, params: dict):
        # reload any tickbars
        tickbars = params.get('tickbars', {})

        for tickbar_id, tickbar_params in tickbars.items():
            mode = tickbar_params.get('mode')
            if not mode:
                logger.warning("No mode specified for tickbar analyser %s" % tickbar_id)
                continue

            clazz_model = self._tickbars_registry.get(mode)
            if clazz_model is None:
                error_logger.error("Unable to find tickbar analyser model mode %s for %s" % (mode, tickbar_id))
                continue

            tickbar_size = tickbar_params.get('tickbar')
            if tickbar_size is None:
                error_logger.error("Missing tickbar analyser parameter for %s" % tickbar_id)
                continue

            if type(tickbar_size) is str:
                tickbar_size = int(tickbar_size)

            if tickbar_size is None:
                error_logger.error("Invalid tickbar analyser parameter for %s" % tickbar_id)
                continue

            try:
                tickbar_inst = clazz_model(self, tickbar_params)
                self.tickbars[tickbar_size] = tickbar_inst
            except Exception:
                error_logger.error("Unable to instantiate tickbar analyser %s" % tickbar_id)
                traceback_logger.error(traceback.format_exc())
                continue

            try:
                tickbar_inst.loads(tickbar_params)
                tickbar_inst.setup_indicators(tickbar_params)
            except Exception:
                error_logger.error("Unable to loads tickbar analyser %s" % tickbar_id)
                traceback_logger.error(traceback.format_exc())

    def update_parameters(self, params: dict):
        # reload any timeframes before contexts
        tickbars = params.get('tickbars', {})

        for tickbar_id, tickbar_params in tickbars.items():
            tb = tickbar_params.get('tickbar')
            if tb is None:
                error_logger.error("Missing tickbar analyser parameter for %s" % tickbar_id)
                continue

            if type(tb) is str:
                tb = int(tb)

            if tb is None:
                error_logger.error("Invalid tickbar analyser parameter for %s" % tickbar_id)
                continue

            tickbars = self.tickbars.get(tb)
            if tickbars is None:
                error_logger.error("Unable to retrieve tickbar analyser instance %s" % tickbar_id)
                continue

            try:
                tickbars.loads(tickbar_params)
            except Exception:
                error_logger.error("Unable to load tickbar analyser %s" % tickbar_id)
                traceback_logger.error(traceback.format_exc())

            try:
                tickbars.setup_indicators(tickbar_params)
            except Exception:
                error_logger.error("Unable to setup indicators from tickbar analyser %s" % tickbar_id)
                traceback_logger.error(traceback.format_exc())

        super().update_parameters(params)

    @property
    def is_tickbars_based(self):
        return True

    def setup_tickbar_gen(self):
        """
        Call it on receive instrument/market data.
        """
        for tb, tickbar in self.tickbars.items():
            tickbar.setup_generator(self.instrument)

    def update_tickbar(self, timestamp: float):
        """
        Update the current tickbar according to the last trade and timestamp or create a new tickbar.
        @note Thread-safe method.
        """       
        with self._mutex:
            # update at tick or trade
            ticks = self.instrument.ticks()  # self.instrument.ticks_after(self.last_timestamp)

            for tickbar_id, tickbar in self.tickbars.items():
                # rest the previous last closed flag before update the current
                tickbar._last_closed = False

                generated = tickbar.range_bar_gen.generate(ticks)
                if generated:
                    self.instrument.add_range_bars(tickbar_id, generated, tickbar.depth)

                    # last tick bar close
                    tickbar._last_closed = True

                # with the non consolidated
                self.instrument.add_range_bar(tickbar_id, copy.copy(tickbar.range_bar_gen.current), tickbar.depth)

            # keep prev and last price at processing step
            if self.instrument.ticks():
                self.prev_price = self.last_price

                # last close price
                self.last_price = self.instrument.ticks()[-1][3]

            # no longer need them
            self.instrument.clear_ticks()

    def update_tickbar_ext(self, timestamp: float) -> List[Tuple]:
        """
        Similar as @see update_tickbar but in detach ticks array in place of taking the array and after cleaning it.
        This method could be faster.
        @param timestamp:
        @return:
        """
        # update data at tick level
        with self._mutex:
            # update at tick or trade
            ticks = self.instrument.detach_ticks()

            for tickbar_id, tickbar in self.tickbars.items():
                # rest the previous last closed flag before update the current
                tickbar._last_closed = False

                generated = tickbar.range_bar_gen.generate(ticks)
                if generated:
                    self.instrument.add_range_bars(tickbar_id, generated, tickbar.depth)

                    # last tick bar close
                    tickbar._last_closed = True

                # with the non consolidated
                self.instrument.add_range_bar(tickbar_id, copy.copy(tickbar.range_bar_gen.current), tickbar.depth)

            # keep prev and last price at processing step
            if ticks:
                self.prev_price = self.last_price

                # last close price
                self.last_price = ticks[-1][3]

            return ticks

    def compute(self, timestamp: float) -> Tuple[List[StrategySignal], List[StrategySignal]]:
        """
        Compute the signals for the different tickbars depending on the update policy.
        """
        # split entries from exits signals
        entries = []
        exits = []

        for tickbar_id, tickbar in self.tickbars.items():
            if tickbar.update_at_close:
                if tickbar.need_update(timestamp):
                    compute = True
                else:
                    compute = False
            else:
                compute = True

            if compute:
                signal = tickbar.process(timestamp)
                if signal:
                    if signal.signal == StrategySignal.SIGNAL_ENTRY:
                        entries.append(signal)
                    elif signal.signal == StrategySignal.SIGNAL_EXIT:
                        exits.append(signal)

        # finally, sort them by timeframe ascending
        entries.sort(key=lambda s: s.timeframe)
        exits.sort(key=lambda s: s.timeframe)

        return entries, exits

    #
    # context
    #

    def apply_trade_context(self, trade: StrategyTrade, context: StrategyTraderContext) -> bool:
        if not trade or not context:
            return False

        trade.label = context.name

        if not trade.timeframe:
            trade.timeframe = Instrument.TF_TRADE

        trade.expiry = context.take_profit.timeout
        trade.entry_timeout = context.entry.timeout
        trade.context = context

        return True

    #
    # streaming
    #

    def setup_streaming(self):
        super().setup_streaming()

    def stream(self):
        super().stream()

    def create_chart_streamer(self, strategy_sub: StrategyBaseAnalyser) -> Streamable:
        streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_CHART,
                              self.strategy.identifier, "%s:%i" % (self.instrument.market_id, strategy_sub.timeframe))
        streamer.add_member(StreamMemberInt('tf'))

        strategy_sub.setup_streamer(streamer)

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
            # data-series values
            for k, tickbar in self.tickbars.items():
                if not result['members']:
                    # initialize from first
                    if not tickbar.report_state_members():
                        break

                    result['members'] = tickbar.report_state_members()

                result['data'].append(tickbar.report_state())

        elif mode == 3:
            # context parameters
            for k, ctx in self._trade_contexts.items():
                if not result['members']:
                    # initialize from first
                    if not ctx.report_parameters_members():
                        break

                    result['members'] = ctx.report_parameters_members()

                # data from any
                result['data'].append(ctx.report_parameters(self.instrument))

        elif mode == 4:
            # context computing states
            for k, ctx in self._trade_contexts.items():
                if not result['members']:
                    # initialize from first
                    if not ctx.report_state_members():
                        break

                    result['members'] = ctx.report_state_members()

                # data from any
                result['data'].append(ctx.report_state(self.instrument))

        return result
