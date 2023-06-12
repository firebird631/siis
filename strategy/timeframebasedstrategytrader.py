# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based strategy trader.

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Tuple, List, Dict, Union, Any

if TYPE_CHECKING:
    from .strategy import Strategy
    from instrument.instrument import Instrument
    from timeframebasedsub import TimeframeBasedSub
    from strategytradercontext import StrategyTraderContext
    from trade.strategytrade import StrategyTrade

import copy

from .strategytrader import StrategyTrader
from .strategysignal import StrategySignal

from instrument.instrument import Instrument
from common.utils import timeframe_from_str, timeframe_to_str

from monitor.streamable import Streamable, StreamMemberInt

import logging
logger = logging.getLogger('siis.strategy.timeframebasedstrategytrader')
error_logger = logging.getLogger('siis.error.strategy.timeframebasedstrategytrader')
traceback_logger = logging.getLogger('siis.traceback.strategy.timeframebasedstrategytrader')


class TimeframeBasedStrategyTrader(StrategyTrader):
    """
    Timeframe based strategy trader base class.
    Sub timeframe object must be based on TimeframeBasedSub.
    It supports the generation of the OHLCs from tick level, or from others OHLCs of a sub-multiple lower timeframe.

    But you want either process at a close of a OHLC, or at any new price (base timeframe).

    @see Strategy.base_timeframe
    """

    _timeframes_registry: Dict[str, Any]
    timeframes: Dict[float, TimeframeBasedSub]
    _timeframe_streamers: Dict[float, Streamable]

    def __init__(self, strategy: Strategy, instrument: Instrument, base_timeframe: float = Instrument.TF_TICK,
                 params: dict = None):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        @param base_timeframe Base time-frame signal accepted. Only this timeframe of incoming data serves as
            compute signal. Default is at tick level, needing a lot of CPU usage but most reactive.
        """
        super().__init__(strategy, instrument, params)

        self._base_timeframe = base_timeframe

        self._timeframes_registry = {}  # registry of timeframes models (mode:cls)
        self._timeframe_streamers = {}  # data streamers per timeframe

        self.timeframes = {}  # analyser per timeframe

        self.prev_price = 0.0
        self.last_price = 0.0

    def register_timeframe(self, mode: str, class_model: Any):
        if mode and class_model:
            self._timeframes_registry[mode] = class_model

    def setup_timeframes(self, params: dict):
        # reload any timeframes
        timeframes = params.get('timeframes', {})

        for tf_name, tf_param in timeframes.items():
            mode = tf_param.get('mode')
            if not mode:
                logger.warning("No mode specified for timeframe %s" % tf_name)
                continue

            clazz_model = self._timeframes_registry.get(mode)
            if clazz_model is None:
                error_logger.error("Unable to find timeframe model mode %s for %s" % (mode, tf_name))
                continue

            tf = tf_param.get('timeframe')
            if tf is None:
                error_logger.error("Missing timeframe parameter for %s" % tf_name)
                continue

            if type(tf) is str:
                tf = timeframe_from_str(tf)

            if tf is None:
                error_logger.error("Invalid timeframe parameter for %s" % tf_name)
                continue

            try:
                tf_inst = clazz_model(self, tf_param)
                self.timeframes[tf] = tf_inst
            except Exception:
                error_logger.error("Unable to instantiate timeframe %s" % tf_name)
                traceback_logger.error(traceback.format_exc())
                continue

            try:
                tf_inst.loads(tf_param)
                tf_inst.setup_indicators(tf_param)
            except Exception:
                error_logger.error("Unable to loads timeframe %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

    def update_parameters(self, params: dict):
        # reload any timeframes before contexts
        timeframes = params.get('timeframes', {})

        for tf_name, tf_param in timeframes.items():
            tf = tf_param.get('timeframe')
            if tf is None:
                error_logger.error("Missing timeframe parameter for %s" % tf_name)
                continue

            if type(tf) is str:
                tf = timeframe_from_str(tf)

            if tf is None:
                error_logger.error("Invalid timeframe parameter for %s" % tf_name)
                continue

            timeframe = self.timeframes.get(tf)
            if timeframe is None:
                error_logger.error("Unable to retrieve timeframe instance %s" % tf_name)
                continue

            try:
                timeframe.loads(tf_param)
            except Exception:
                error_logger.error("Unable to load timeframe %s" % tf_name)
                traceback_logger.error(traceback.format_exc())

            try:
                timeframe.setup_indicators(tf_param)
            except Exception:
                error_logger.error("Unable to setup indicators from timeframe %s" % tf_name)
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

    def on_received_initial_candles(self, timeframe: float):
        """
        Slot called once the initial bulk of candles are received for each timeframe.
        """
        sub = self.timeframes.get(timeframe)
        if sub:
            sub.init_candle_generator()

    def gen_candles_from_ticks(self, timestamp: float):
        """
        Generate the news candles from ticks.
        @note Thread-safe method.
        """
        with self._mutex:
            # at tick, we update any timeframes because we want the non consolidated candle
            ticks = self.instrument.ticks()  # self.instrument.ticks_after(sub.candles_gen.last_timestamp)

            for tf, sub in self.timeframes.items():
                # rest the previous last closed flag before update the current
                sub._last_closed = False

                generated = sub.candles_gen.generate_from_ticks(ticks)
                if generated:
                    self.instrument.add_candles(generated, sub.depth)

                    # last OHLC close
                    sub._last_closed = True

                # with the non consolidated
                self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.depth)

            # keep prev and last price at processing step
            if self.instrument.ticks():
                self.prev_price = self.last_price

                # last tick mid
                self.last_price = (self.instrument.ticks()[-1][1] + self.instrument.ticks()[-1][2]) * 0.5

            # no longer need them
            self.instrument.clear_ticks()

    def gen_candles_from_candles(self, timestamp: float):
        """
        Generate the news candles from the same base of candle.
        @note Thread-safe method.
        """
        with self._mutex:
            # at tick, we update any timeframes because we want the non consolidated candle
            for tf, sub in self.timeframes.items():
                # update at candle timeframe
                candles = self.instrument.candles_after(self._base_timeframe, sub.candles_gen.last_timestamp)

                sub._last_closed = False

                generated = sub.candles_gen.generate_from_candles(candles)
                if generated:
                    self.instrument.add_candles(generated, sub.depth)

                    # last OHLC close
                    sub._last_closed = True

                self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.depth)  # with the non consolidated

            # keep prev and last price at processing step
            if self.instrument.candles(self._base_timeframe):
                self.prev_price = self.last_price
                self.last_price = self.instrument.candles(self._base_timeframe)[-1].close  # last mid close

    def compute(self, timestamp: float) -> Tuple[List[StrategySignal], List[StrategySignal]]:
        """
        Compute the signals for the different timeframes depending on the update policy.
        """
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
            trade.timeframe = context.entry.timeframe

        trade.expiry = context.take_profit.timeout
        trade.entry_timeout = context.entry.timeout
        trade.context = context

        return True

    def check_spread(self, signal: StrategySignal) -> bool:
        """Compare spread from entry signal max allowed spread value, only if max-spread parameters is valid"""
        if not signal or not signal.context:
            return True

        if signal.context.entry.max_spread <= 0.0:
            return True

        return self.instrument.market_spread <= signal.context.entry.max_spread

    def check_min_profit(self, signal: StrategySignal) -> bool:
        """Check for a minimal profit based on context parameters"""
        if not signal or not signal.context:
            return True

        if signal.context.min_profit <= 0.0:
            return True

        return signal.profit() >= signal.context.min_profit

    #
    # streaming
    #

    def setup_streaming(self):
        super().setup_streaming()

    def stream(self):
        super().stream()

        with self._mutex:
            for k, timeframe in self.timeframes.items():
                if timeframe.tf in self._timeframe_streamers:
                    timeframe.stream(self._timeframe_streamers[timeframe.tf])

    def create_chart_streamer(self, timeframe: TimeframeBasedSub) -> Streamable:
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
        with self._mutex:
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
            for k, timeframe in self.timeframes.items():
                result['data'] += timeframe.report_state()

        return result

    #
    # alerts
    #

    def process_alerts(self, timestamp):
        # check for alert triggers
        if self.alerts:
            alerts = self.check_alerts(timestamp, self.instrument.market_bid, self.instrument.market_ask,
                                       self.timeframes)

            if alerts:
                for alert, result in alerts:
                    self.notify_alert(timestamp, alert, result)

    #
    # helpers
    #

    def timeframe_from_param(self, param: Union[str, float, int]) -> float:
        if isinstance(param, str):
            return timeframe_from_str(param)
        elif isinstance(param, float):
            return param
        elif isinstance(param, int):
            return float(param)
        else:
            return 0.0
