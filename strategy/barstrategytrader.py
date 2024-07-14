# @date 2020-09-19
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Strategy trader base model using non-temporal bar

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, List, Tuple, Any, Dict

if TYPE_CHECKING:
    from .strategy import Strategy
    from strategytradercontext import StrategyTraderContext
    from trade.strategytrade import StrategyTrade
    from instrument.instrument import TickType
    # from .strategyrangebaranalyser import StrategyRangeBarAnalyser

import copy

from instrument.instrument import Instrument
from monitor.streamable import Streamable, StreamMemberInt

from .strategybaseanalyser import StrategyBaseAnalyser
from .strategytraderbase import StrategyTraderBase

import logging
logger = logging.getLogger('siis.strategy.barstrategytrader')
error_logger = logging.getLogger('siis.error.strategy.barstrategytrader')
traceback_logger = logging.getLogger('siis.traceback.strategy.barstrategytrader')


class BarStrategyTrader(StrategyTraderBase):
    """
    Strategy trader base model using non-temporal bar (range-bar, reversal-bar, volume-bar, renko).
    @note Currently support only range-bars.

    There is no OHLC in this abstraction. It is tick or trade based.
    It only works with a tick or trade data flow.

    But it is possible to internally compute OHLC for some specifics needs.
    There is no support of sub per timeframe.
    
    A single configuration of tick-bar array can be generated.
    """

    _last_ticks: List[TickType]

    def __init__(self, strategy: Strategy, instrument: Instrument, depth=50, params: dict = None):
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

        self._last_ticks = []  # retains the last updated ticks

    def setup_analysers(self, params: dict):
        # reload any tickbars
        tickbars = params.get('tickbars', {})

        for analyser_name, analyser_params in tickbars.items():
            mode = analyser_params.get('mode')
            if not mode:
                logger.warning("No mode specified for analyser %s" % analyser_name)
                continue

            clazz_model = self._analysers_registry.get(mode)
            if clazz_model is None:
                error_logger.error("Unable to find analyser model %s for %s" % (mode, analyser_name))
                continue

            bar_size = analyser_params.get('size')
            if bar_size is None:
                error_logger.error("Missing analyser parameter size for %s" % analyser_name)
                continue

            if type(bar_size) is str:
                bar_size = int(bar_size)

            if bar_size is None:
                error_logger.error("Invalid analyser parameter tickbar for %s" % analyser_name)
                continue

            try:
                analyser_inst = clazz_model(analyser_name, self, analyser_params)
                self._analysers[analyser_name] = analyser_inst
            except Exception:
                error_logger.error("Unable to instantiate analyser %s" % analyser_name)
                traceback_logger.error(traceback.format_exc())
                continue

            try:
                analyser_inst.loads(analyser_params)
                analyser_inst.setup_indicators(analyser_params)
            except Exception:
                error_logger.error("Unable to loads analyser %s" % analyser_name)
                traceback_logger.error(traceback.format_exc())

    def update_parameters(self, params: dict):
        # reload any timeframes before contexts
        tickbars = params.get('tickbars', {})

        for analyser_name, analyser_params in tickbars.items():
            analyser = self._analysers.get(analyser_name)
            if analyser is None:
                error_logger.error("Unable to retrieve analyser instance %s" % analyser_name)
                continue

            try:
                analyser.loads(analyser_params)
            except Exception:
                error_logger.error("Unable to load analyser %s" % analyser_name)
                traceback_logger.error(traceback.format_exc())

            try:
                analyser.setup_indicators(analyser_params)
            except Exception:
                error_logger.error("Unable to setup indicators from analyser %s" % analyser_name)
                traceback_logger.error(traceback.format_exc())

        super().update_parameters(params)

    @property
    def is_tickbars_based(self):
        return True

    @property
    def base_timeframe(self) -> float:
        return 0.0

    def setup_generators(self):
        """
        Call it on receive instrument/market data.
        """
        for k, analyser in self._analysers.items():
            analyser.setup_generator(self.instrument)

    def generate_bars_from_ticks(self, timestamp: float):
        """
        Compute range-bar using the last received ticks.
        @param timestamp:
        @return:
        """
        # update data at tick level
        with self._mutex:
            # update at tick or trade
            last_ticks = self.instrument.detach_ticks()

            for k, analyser in self._analysers.items():
                # rest the previous last closed flag before update the current
                analyser._last_closed = False

                # @todo move to RangeBarAnalyser
                generated = analyser.bar_generator.generate(last_ticks)
                if generated:
                    analyser.add_bars(generated, analyser.depth)

                    # last tick bar close
                    analyser._last_closed = True

                # with the non consolidated
                analyser.add_bar(copy.copy(analyser.bar_generator.current), analyser.depth)

            # keep prev and last price at processing step
            if last_ticks:
                # always keep previous and last tick price
                self.prev_price = self.last_price
                self.last_price = last_ticks[-1][3]  # last exec price

            # keep for computing some ticks based indicators
            self._last_ticks = last_ticks

    def compute(self, timestamp: float):
        """
        Compute the indicators for the different tickbars depending on the update policy.
        """
        for k, analyser in self._analysers.items():
            if analyser.update_at_close:
                if analyser.need_update(timestamp):
                    compute = True
                else:
                    compute = False
            else:
                compute = True

            if compute:
                analyser.process(timestamp, self._last_ticks)

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
            for k, analyser in self._analysers.items():
                if not result['members']:
                    # initialize from first
                    if not analyser.report_state_members():
                        break

                    result['members'] = analyser.report_state_members()

                result['data'].append(analyser.report_state())

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
