# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trader base model using temporal bar

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Tuple, List, Dict, Union, Any

if TYPE_CHECKING:
    from instrument.instrument import TickType, Candle
    from .strategy import Strategy
    from .strategybaseanalyser import StrategyBaseAnalyser
    from strategytimeframeanalyser import StrategyTimeframeAnalyser
    from strategytradercontext import StrategyTraderContext
    from trade.strategytrade import StrategyTrade

import copy

from instrument.instrument import Instrument
from .strategytraderbase import StrategyTraderBase

from common.utils import timeframe_from_str

from monitor.streamable import Streamable, StreamMemberInt

import logging
logger = logging.getLogger('siis.strategy.timeframestrategytrader')
error_logger = logging.getLogger('siis.error.strategy.timeframestrategytrader')
traceback_logger = logging.getLogger('siis.traceback.strategy.timeframestrategytrader')


class TimeframeStrategyTrader(StrategyTraderBase):
    """
    Strategy trader base model using temporal bar (1m, 30m, 1d....).
    Sub timeframe object must be based on TimeframeBasedSub.
    It supports the generation of the OHLCs from tick level, or from others OHLCs of a sub-multiple lower timeframe.

    But you want either process at a close of a OHLC, or at any new price (base timeframe).

    @see Strategy.base_timeframe
    """

    timeframes: Dict[float, StrategyTimeframeAnalyser]  # @deprecated
    _timeframe_streamers: Dict[float, Streamable]  # @deprecated

    _last_ticks: List[TickType]
    _last_candles: List[Candle]

    def __init__(self, strategy: Strategy, instrument: Instrument, base_timeframe: float = Instrument.TF_TICK,
                 params: dict = None):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        @param base_timeframe Base time-frame or tick data as input for processing.
        """
        super().__init__(strategy, instrument, params)

        self._base_timeframe = base_timeframe

        self._timeframe_streamers = {}  # data streamers per timeframe
        self.timeframes = {}  # analyser per timeframe

        self.prev_price = 0.0
        self.last_price = 0.0

        self._last_ticks = []
        self._last_candles = []

    def setup_analysers(self, params: dict):
        # reload any timeframes
        timeframes = params.get('timeframes', {})

        for tf_name, tf_param in timeframes.items():
            mode = tf_param.get('mode')
            if not mode:
                logger.warning("No mode specified for analyser %s" % tf_name)
                continue

            clazz_model = self._analysers_registry.get(mode)
            if clazz_model is None:
                error_logger.error("Unable to find analyser model mode %s for %s" % (mode, tf_name))
                continue

            tf = tf_param.get('timeframe')
            if tf is None:
                error_logger.error("Missing analyser parameter for %s" % tf_name)
                continue

            if type(tf) is str:
                tf = timeframe_from_str(tf)

            if tf is None:
                error_logger.error("Invalid analyser parameter for %s" % tf_name)
                continue

            try:
                tf_inst = clazz_model(tf_name, self, tf_param)
                self._analysers[tf_name] = tf_inst
            except Exception:
                error_logger.error("Unable to instantiate analyser %s" % tf_name)
                traceback_logger.error(traceback.format_exc())
                continue

            try:
                tf_inst.loads(tf_param)
                tf_inst.setup_indicators(tf_param)
            except Exception:
                error_logger.error("Unable to loads analyser %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

    def update_parameters(self, params: dict):
        # reload any timeframes before contexts
        timeframes = params.get('timeframes', {})

        for tf_name, tf_param in timeframes.items():
            analyser = self._analysers.get(tf_name)
            if analyser is None:
                error_logger.error("Unable to retrieve analyser instance %s" % tf_name)
                continue

            try:
                analyser.loads(tf_param)
            except Exception:
                error_logger.error("Unable to load analyser %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

            try:
                analyser.setup_indicators(tf_param)
            except Exception:
                error_logger.error("Unable to setup indicators from analyser %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

        super().update_parameters(params)

    @property
    def is_timeframes_based(self) -> bool:
        return True

    @property
    def base_timeframe(self) -> float:
        return self._base_timeframe

    @property
    def timeframes_parameters(self) -> dict:
        """
        Returns the dict of timeframes with name as key and settings in value.
        """
        return self.strategy.parameters.get('timeframes', {})

    def on_received_initial_bars(self, analyser_name: str):
        """
        Slot called once the initial bulk of candles are received for each analyser.
        """
        analyser = self._analysers.get(analyser_name)
        if analyser:
            analyser.init_generator()

    def generate_bars_from_ticks(self, timestamp: float):
        """
        Generate the news candles from ticks.
        @note Thread-safe method.
        """
        with self._mutex:
            last_ticks = self.instrument.detach_ticks()

            # at tick, we update any timeframes because we want the non consolidated candle
            for k, analyser in self._analysers.items():
                # rest the previous last closed flag before update the current
                analyser._last_closed = False

                generated = analyser.bar_generator.generate_from_ticks(last_ticks)
                if generated:
                    analyser.add_bars(generated, analyser.depth)

                    # last OHLC close
                    analyser._last_closed = True

                # with the non consolidated
                analyser.add_bar(copy.copy(analyser.bar_generator.current), analyser.depth)

            # keep prev and last price at processing step
            if last_ticks:
                self.prev_price = self.last_price
                self.last_price = last_ticks[-1][3]  # last or mid (last_ticks[-1][1] + last_ticks[-1][2]) * 0.5

        self._last_ticks = last_ticks

    def generate_bars_from_candles(self, timestamp: float):
        """
        Generate the news candles from the same base of candle.
        @note Thread-safe method.
        """
        with self._mutex:
            last_candles = self.instrument.detach_candles()

            # at tick, we update any timeframes because we want the non consolidated candle
            for k, analyser in self._analysers.items():
                # update at candle timeframe
                analyser._last_closed = False

                generated = analyser.bar_generator.generate_from_candles(last_candles)
                if generated:
                    analyser.add_bars(generated, analyser.depth)

                    # last OHLC close
                    analyser._last_closed = True

                # with the non consolidated
                analyser.add_bars(copy.copy(analyser.bar_generator.current), analyser.depth)

            # keep prev and last price at processing step
            if last_candles:
                self.prev_price = self.last_price
                self.last_price = last_candles[-1].close  # last mid close

        self._last_candles = last_candles

    def compute(self, timestamp: float):
        """
        Compute the per analyser data. Compute at bar close or at each trade.
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
                analyser.process(timestamp)

    #
    # context
    #

    def apply_trade_context(self, trade: StrategyTrade, context: StrategyTraderContext) -> bool:
        if not trade or not context:
            return False

        trade.label = context.name

        if not trade.timeframe:
            trade.timeframe = context.entry.timeframe

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

        with self._mutex:
            for k, analyser in self._analysers.items():
                # @todo
                if analyser.timeframe in self._timeframe_streamers:
                    analyser.stream(self._timeframe_streamers[analyser.timeframe])

    def create_chart_streamer(self, timeframe: StrategyBaseAnalyser) -> Streamable:
        streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_CHART,
                              self.strategy.identifier, "%s:%i" % (self.instrument.market_id, timeframe.timeframe))
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
        with self._mutex:
            # @todo
            timeframe = self.timeframes.get(tf)
            if timeframe is None:
                return False

            if timeframe.tf in self._timeframe_streamers:
                self._timeframe_streamers[timeframe.tf].use()
                return True
            else:
                streamer = self.create_chart_streamer(timeframe)
                if streamer:
                    streamer.use()
                    self._timeframe_streamers[timeframe.tf] = streamer
                    return True

        return False

    def unsubscribe_stream(self, tf: float) -> bool:
        """
        Delete a specific streamer when no more subscribers.
        """
        with self._mutex:
            # @todo
            timeframe = self.timeframes.get(tf)
            if timeframe is None:
                return False

            if timeframe.tf in self._timeframe_streamers:
                self._timeframe_streamers[timeframe.tf].unuse()
                if self._timeframe_streamers[timeframe.tf].is_free():
                    # delete if 0 subscribers
                    del self._timeframe_streamers[timeframe.tf]

                return True

        return False

    def report_state(self, mode: int = 0) -> dict:
        """
        Collect the state of the strategy trader (instant) and return a dataset.
        And add the per timeframe dataset.
        """
        result = super().report_state(mode)

        if mode == 0:
            for k, analyser in self._analysers.items():
                if not result['members']:
                    # initialize from first
                    result['members'] = analyser.report_state_members()

                result['data'].append(analyser.report_state())

        elif mode == 3:
            for k, ctx in self._trade_contexts.items():
                if not result['members']:
                    # initialize from first
                    result['members'] = ctx.report_parameters_members()

                # data from any (append because it is per row)
                result['data'].append(ctx.report_parameters(self.instrument))

        elif mode == 4:
            for k, ctx in self._trade_contexts.items():
                if not result['members']:
                    # initialize from first
                    result['members'] = ctx.report_state_members()

                # data from any (append because it is per row)
                result['data'].append(ctx.report_state(self.instrument))

        return result

    #
    # helpers
    #

    @staticmethod
    def parse_timeframe(param: Union[str, float, int]) -> float:
        if isinstance(param, str):
            return timeframe_from_str(param)
        elif isinstance(param, float):
            return param
        elif isinstance(param, int):
            return float(param)
        else:
            return 0.0
