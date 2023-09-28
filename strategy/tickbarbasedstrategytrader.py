# @date 2020-09-19
# @author Frederic Scherma
# @license Copyright (c) 2020 Dream Overflow
# Tick-bar based strategy trader. 

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, List, Tuple, Any, Dict

if TYPE_CHECKING:
    from strategytradercontext import StrategyTraderContext
    from trade.strategytrade import StrategyTrade

    from .tickbarbasedsub import TickBarBasedSub

import copy

from instrument.instrument import Instrument

from monitor.streamable import Streamable, StreamMemberInt

from .strategysub import StrategySub
from .strategytrader import StrategyTrader

import logging
logger = logging.getLogger('siis.strategy.tickbarbasedstrategytrader')
error_logger = logging.getLogger('siis.error.strategy.tickbarbasedstrategytrader')
traceback_logger = logging.getLogger('siis.traceback.strategy.tickbarbasedstrategytrader')


class TickBarBasedStrategyTrader(StrategyTrader):
    """
    Tick-bar based strategy trader base class.

    There is no OHLC in this abstraction. It is tick or trade based.
    It only works with a tick or trade data flow.

    But it is possible to internally compute OHLC for some specifics needs.
    There is no support of sub per timeframe.
    
    A single configuration of tick-bar array can be generated.
    """

    _tickbars_registry: Dict[str, Any]
    tickbars: Dict[float, TickBarBasedSub]
    _tickbars_streamers: Dict[float, Streamable]

    def __init__(self, strategy, instrument, depth=50, params: dict = None):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        """
        super().__init__(strategy, instrument, params)

        self._base_timeframe = Instrument.TF_TICK

        self.tickbar_generator = None  # can be a TickBarRangeGenerator or TickBarReversalGenerator.
        self._tickbar_streamer = None

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
        timeframes = params.get('tickbars', {})

        for tf_name, tb_param in timeframes.items():
            mode = tb_param.get('mode')
            if not mode:
                logger.warning("No mode specified for tickbar sub %s" % tf_name)
                continue

            clazz_model = self._tickbars_registry.get(mode)
            if clazz_model is None:
                error_logger.error("Unable to find tickbar sub model mode %s for %s" % (mode, tf_name))
                continue

            tb = tb_param.get('tickbar')
            if tb is None:
                error_logger.error("Missing tickbar sub parameter for %s" % tf_name)
                continue

            if type(tb) is str:
                tb = int(tb)

            if tb is None:
                error_logger.error("Invalid tickbar sub parameter for %s" % tf_name)
                continue

            try:
                tb_inst = clazz_model(self, tb_param)
                self.tickbars[tb] = tb_inst
            except Exception:
                error_logger.error("Unable to instantiate tickbar sub %s" % tf_name)
                traceback_logger.error(traceback.format_exc())
                continue

            try:
                tb_inst.loads(tb_param)
                tb_inst.setup_indicators(tb_param)
            except Exception:
                error_logger.error("Unable to loads tickbar sub %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

    def update_parameters(self, params: dict):
        # reload any timeframes before contexts
        tickbar = params.get('tickbars', {})

        for tb_name, tb_param in tickbar.items():
            tb = tb_param.get('tickbar')
            if tb is None:
                error_logger.error("Missing tickbar sub parameter for %s" % tb_name)
                continue

            if type(tb) is str:
                tb = int(tb)

            if tb is None:
                error_logger.error("Invalid tickbar sub parameter for %s" % tb_name)
                continue

            tickbar = self.tickbars.get(tb)
            if tickbar is None:
                error_logger.error("Unable to retrieve tickbar sub instance %s" % tb_name)
                continue

            try:
                tickbar.loads(tb_param)
            except Exception:
                error_logger.error("Unable to load tickbar sub %s" % tb_name)
                traceback_logger.error(traceback.format_exc())

            try:
                tickbar.setup_indicators(tb_param)
            except Exception:
                error_logger.error("Unable to setup indicators from tickbar sub %s" % tb_name)
                traceback_logger.error(traceback.format_exc())

        super().update_parameters(params)

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
                self.instrument.add_tickbars(generated)

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
                self.instrument.add_tickbars(generated)

            self.instrument.add_tickbar(copy.copy(self.tickbar_generator.current), self.depth)

            # keep prev and last price at processing step
            if self.instrument.ticks():
                self.prev_price = self.last_price

                # last tick mid
                self.last_price = (self.instrument.ticks()[-1][1] + self.instrument.ticks()[-1][2]) * 0.5

            return ticks

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

    def create_chart_streamer(self, strategy_sub: StrategySub) -> Streamable:
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
            for k, tickbar in self.tickbars.items():
                result['data'] += tickbar.report_state()

        return result
