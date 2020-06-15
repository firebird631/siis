# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Timeframe base strategy trader. 

import copy

from terminal.terminal import Terminal

from strategy.strategy import Strategy
from strategy.strategytrader import StrategyTrader
from strategy.strategysignal import StrategySignal

from instrument.instrument import Instrument, Candle
from instrument.candlegenerator import CandleGenerator
from common.utils import timeframe_from_str

from monitor.streamable import Streamable, StreamMemberInt, StreamMemberFloatTuple, StreamMemberFloatScatter, \
                               StreamMemberTradeEntry, StreamMemberTradeUpdate, StreamMemberTradeExit, StreamMemberFloatSerie

import logging
logger = logging.getLogger('siis.strategy.trader')


class TimeframeBasedStrategyTrader(StrategyTrader):
    """
    Timeframe base strategy trader base class.
    Sub timeframe object must be based on TimeframeBasedSub.
    It support the generation of the OHLCs from tick level, or from others OHLCs of a sub-multiple lower timeframe.

    But you want either process at a close of a OHLC, or at any new price (base timeframe).

    @see Strategy.base_timeframe
    """

    def __init__(self, strategy, instrument, base_timeframe=Instrument.TF_TICK):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        @param base_tf Base time-frame signal accepted. Only this timeframe of incoming data serves as compute signal.
            Default is at tick level, needing a lot of CPU usage but most reactive.
        @param wait_next_update Or wait a condition defined by need_update(...) method override, for example the next update timestamp.
        """
        super().__init__(strategy, instrument)

        self._base_timeframe = base_timeframe

        self.timeframes = {}  # analyser per timeframe

        self.prev_price = 0.0
        self.last_price = 0.0

    @property
    def base_timeframe(self):
        return self._base_timeframe

    def on_received_initial_candles(self, timeframe):
        """
        Slot called once the initial bulk of candles are received for each timeframe.
        """
        sub = self.timeframes.get(timeframe)
        if sub:
            sub.init_candle_generator()

    def gen_candles_from_ticks(self, timestamp):
        """
        Generate the news candles from ticks.
        @note Thread-safe method.
        """
        with self._mutex:
            # at tick we update any timeframes because we want the non consolidated candle
            for tf, sub in self.timeframes.items():
                # update at tick
                ticks = self.instrument.ticks_after(sub.candles_gen.last_timestamp)

                sub._last_closed = False

                generated = sub.candles_gen.generate_from_ticks(ticks)
                if generated:
                    self.instrument.add_candle(generated, sub.depth)

                    # last OHLC close
                    sub._last_closed = True

                self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.depth)  # with the non consolidated

            # keep prev and last price at processing step
            if self.instrument._ticks:
                self.prev_price = self.last_price
                self.last_price = (self.instrument._ticks[-1][1] + self.instrument._ticks[-1][2]) * 0.5  # last tick mid

            # no longer need them
            self.instrument.clear_ticks()

    def gen_candles_from_candles(self, timestamp):
        """
        Generate the news candles from the same base of candle.
        @note Thread-safe method.
        """
        with self._mutex:
            # at tick we update any timeframes because we want the non consolidated candle
            for tf, sub in self.timeframes.items():
                # update at candle timeframe
                candles = self.instrument.candles_after(self._base_timeframe, sub.candles_gen.last_timestamp)

                sub._last_closed = False

                generated = sub.candles_gen.generate_from_candles(candles)
                if generated:
                    self.instrument.add_candle(generated, sub.depth)

                    # last OHLC close
                    sub._last_closed = True

                self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.depth)  # with tne non consolidated

            # keep prev and last price at processing step
            if self.instrument._candles.get(self._base_timeframe):
                self.prev_price = self.last_price
                self.last_price = self.instrument._candles[self._base_timeframe][-1].close  # last mid close

    def compute(self, timestamp):
        """
        Compute the signals for the differents timeframes depending of the update policy.
        """
        # split entries from exits signals
        entries = []
        exits = []

        for tf, sub in self.timeframes.items():
            if not sub.next_timestamp:
                # initial timestamp only
                sub.next_timestamp = self.strategy.timestamp

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

        # finally sort them by timeframe ascending
        entries.sort(key=lambda s: s.timeframe)
        exits.sort(key=lambda s: s.timeframe)

        return entries, exits

    def precompute(self, timestamp):
        """
        Compute the signals for the differents timeframes depending of the update policy.
        """
        # split entries from exits signals
        entries = []
        exits = []

        for tf, sub in self.timeframes.items():
            if not sub.next_timestamp:
                # initial timestamp from older candle
                candles = self.instrument.candles(tf)
                if candles:
                    sub.next_timestamp = candles[-1].timestamp
                else:
                    sub.next_timestamp = self.strategy.timestamp

            if sub.update_at_close:
                if sub.need_update(timestamp):
                    compute = True
            else:
                compute = True

            if compute:
                signal = sub.process(timestamp)
                if signal:
                    if signal.signal == StrategySignal.SIGNAL_ENTRY:
                        entries.append(signal)
                    elif signal.signal == StrategySignal.SIGNAL_EXIT:
                        exits.append(signal)

        # finally sort them by timeframe ascending
        entries.sort(key=lambda s: s.timeframe)
        exits.sort(key=lambda s: s.timeframe)

        return entries, exits

    #
    # streaming
    #

    def setup_streaming(self):
        self._global_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_INFO, self.strategy.identifier, self.instrument.market_id)
        self._global_streamer.add_member(StreamMemberFloatSerie('performance', 0))

        # trade streams
        self._trade_entry_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE, self.strategy.identifier, self.instrument.market_id)
        self._trade_entry_streamer.add_member(StreamMemberTradeEntry('trade-entry'))

        self._trade_update_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE, self.strategy.identifier, self.instrument.market_id)
        self._trade_update_streamer.add_member(StreamMemberTradeUpdate('trade-update'))

        self._trade_exit_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE, self.strategy.identifier, self.instrument.market_id)
        self._trade_exit_streamer.add_member(StreamMemberTradeExit('trade-exit'))

    def stream(self):
        # global data
        with self._mutex:
            # if self._global_streamer:
            #     self._global_streamer.publish()

            # and per timeframe
            for tf, timeframe_streamer in self._timeframe_streamers.items():
                data = self.timeframes.get(tf)
                if data:
                    self.stream_timeframe_data(timeframe_streamer, data)

    def create_chart_streamer(self, sub):
        streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_CHART, self.strategy.identifier, "%s:%i" % (self.instrument.market_id, sub.tf))
        streamer.add_member(StreamMemberInt('tf'))

        sub.setup_streamer(streamer)

        return streamer

    def stream_timeframe_data(self, streamer, sub):
        streamer.member('tf').update(sub.tf)
        streamer.publish()

        sub.stream(streamer)

    def subscribe_info(self):
        result = False

        with self._mutex:
            if not self._global_streamer:
                self.setup_streaming()

            if self._global_streamer:
                self._global_streamer.use()
                result = True

        return result

    def unsubscribe_info(self):
        result = False

        with self._mutex:
            if self._global_streamer:
                self._global_streamer.unuse()
                
                if self._global_streamer.is_free():
                    self._global_streamer = None

                result = True

        return result

    def subscribe_stream(self, timeframe):
        """
        Use or create a specific streamer.
        """
        result = False

        with self._mutex:
            if timeframe is not None and isinstance(timeframe, (float, int)):
                timeframe = self.timeframes.get(timeframe)

            if timeframe is None and self.timeframes:
                tf = sorted(list(self.timeframes.keys()))[0]
                timeframe = self.timeframes.get(tf)

            if timeframe in self._timeframe_streamers:
                self._timeframe_streamers[timeframe].use()
                result = True
            else:
                streamer = self.create_chart_streamer(timeframe)

                if streamer:
                    streamer.use()
                    self._timeframe_streamers[timeframe.tf] = streamer
                    result = True

        return False

    def unsubscribe_stream(self, timeframe):
        """
        Delete a specific streamer when no more subscribers.
        """
        result = False

        with self._mutex:
            if timeframe is not None and isinstance(timeframe, (float, int)):
                timeframe = self.timeframes.get(timeframe)

            if timeframe in self._timeframe_streamers:
                self._timeframe_streamers[timeframe].unuse()
                if self._timeframe_streamers[timeframe].is_free():
                    # delete if 0 subscribers
                    del self._timeframe_streamers[timeframe]
        
                result = True

        return result

    def report_state(self, mode=0):
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
    # helpers
    #

    def timeframe_from_param(self, param):
        if isinstance(param, str):
            return timeframe_from_str(param)
        elif isinstance(param, float):
            return param
        elif isinstance(param, int):
            return float(param)
        else:
            return 0.0
