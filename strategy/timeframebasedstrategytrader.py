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

from monitor.streamable import Streamable, StreamMemberInt, StreamMemberFloatTuple, StreamMemberTradeList, StreamMemberFloatScatter

import logging
logger = logging.getLogger('siis.strategy')


class TimeframeBasedStrategyTrader(StrategyTrader):
    """
    Timeframe base strategy trader base class.
    Sub timeframe object must be based on TimeframeBasedSub.
    It support the generation of the OHLCs from tick level, or from others OHLCs of a sub-multiple lower timeframe.

    But you want either process at a close of a OHLC, or at any new price (base timeframe).

    @see Strategy.base_timeframe
    """

    def __init__(self, strategy, instrument, base_timeframe=Instrument.TF_TICK, wait_next_update=False):
        """
        @param strategy Parent strategy (mandatory)
        @param instrument Related unique instance of instrument (mandatory)
        @param base_tf Base time-frame signal accepted. Only this timeframe of incoming data serves as compute signal.
            Default is at tick level, needing a lot of CPU usage but most reactive.
        @param wait_next_update Or wait a condition defined by need_update(...) method override, for example the next update timestamp.
        """
        super().__init__(strategy, instrument)

        self._base_timeframe = base_timeframe
        self._wait_next_update = wait_next_update

        self.timeframes = {}  # analyser per timeframe

    @property
    def base_timeframe(self):
        return self._base_timeframe

    @property
    def wait_next_update(self):
        return self._wait_next_update

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
        """
        self.lock()

        # at tick we update any timeframes because we want the non consolidated candle
        for tf, sub in self.timeframes.items():
            # update at tick
            ticks = self.instrument.ticks_after(sub.candles_gen.last_timestamp)

            generated = sub.candles_gen.generate_from_ticks(ticks)
            if generated:
                self.instrument.add_candle(generated, sub.history)

            self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.history)  # with the non consolidated

        # no longer need them
        self.instrument.clear_ticks()

        self.unlock()

    def gen_candles_from_candles(self, timestamp):
        """
        Generate the news candles from the same base of candle.
        """
        self.lock()

        # at tick we update any timeframes because we want the non consolidated candle
        for tf, sub in self.timeframes.items():
            # update at candle timeframe
            candles = self.instrument.candles_after(sub.sub_tf, sub.candles_gen.last_timestamp)

            generated = sub.candles_gen.generate_from_candles(candles)
            if generated:
                self.instrument.add_candle(generated, sub.history)

            self.instrument.add_candle(copy.copy(sub.candles_gen.current), sub.history)  # with the non consolidated

        self.unlock()

    def compute(self, timeframe, timestamp):
        """
        Compute the signals for the differents timeframes depending of the update policy.

        If wait_next_update is set then it will only compute signal for a particular timeframe
        when the need_update method return True. The standard implementation is to compute signal at a candle close.
        """
        # split entries from exits signals
        entries = []
        exits = []

        if self.wait_next_update:
            # process sub computations only when condition
            for tf, sub in self.timeframes.items():
                if sub.need_update(timestamp):
                    print(tf, self.instrument.market_id)
                    # only if need_update return true
                    signal = sub.process(timestamp)
                    if signal:
                        if signal.signal == StrategySignal.SIGNAL_ENTRY:
                            entries.append(signal)
                        elif signal.signal == StrategySignal.SIGNAL_EXIT:
                            exits.append(signal)

        elif self.base_timeframe == timeframe:
            # or at min timeframe level (default behavior, and at tick level)
            for tf, sub in self.timeframes.items():
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

    def higher_timeframe_low_high_trend(self, tf, upper_tf):
        # how to do if the previous candles are very smalls or very big ?
        height = max(self.instrument.height(tf, -1), self.instrument.height(tf, -2))  # * 2.0

        last_price = 0
        slow_ema = 0
        price_above_slow_ema = 0
        slow_rsi = 0

        if len(self.timeframes[upper_tf].price.price):
            last_price = self.timeframes[upper_tf].price.price[-1]

        if len(self.timeframes[upper_tf].ema.ema):
            slow_ema = self.timeframes[upper_tf].ema.ema[-1]

        if len(self.timeframes[upper_tf].rsi.rsi):
            slow_rsi = self.timeframes[upper_tf].rsi.rsi[-1]

        if last_price > slow_ema:
            price_above_slow_ema = 1
        elif last_price < slow_ema:
            price_above_slow_ema = -1

        low = self.instrument.candle(upper_tf).low
        high = self.instrument.candle(upper_tf).high

        return upper_tf, low, high, price_above_slow_ema

    #
    # streaming
    #

    def setup_streaming(self):
        self._global_streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_INFO, self.strategy.identifier, self.instrument.market_id)
        self._global_streamer.add_member(StreamMemberFloatTuple('tfs'))
        self._global_streamer.add_member(StreamMemberTradeList('trades'))

        # merged on the price
        self._global_streamer.add_member(StreamMemberFloatScatter('buy-entry', 0, 'g^'))
        self._global_streamer.add_member(StreamMemberFloatScatter('sell-entry', 0, 'r^'))
        self._global_streamer.add_member(StreamMemberFloatScatter('buy-exit', 0, 'r^'))
        self._global_streamer.add_member(StreamMemberFloatScatter('sell-exit', 0, 'g^'))

    def stream(self):
        # global data
        self.lock()

        if self._global_streamer:
            self._global_streamer.push()

        # and per timeframe
        for tf, timeframe_streamer in self._timeframe_streamers.items():
            data = self.timeframes.get(tf)
            if data:
                self.stream_timeframe_data(timeframe_streamer, data)

        self.unlock()

    def stream_call(self):
        # timeframes list
        if self._global_streamer:
            self._global_streamer.member('tfs').update(list(self.timeframes.keys()))
            self._global_streamer.push()

    def create_chart_streamer(self, sub):
        streamer = Streamable(self.strategy.service.monitor_service, Streamable.STREAM_STRATEGY_CHART, self.strategy.identifier, "%s:%i" % (self.instrument.market_id, sub.tf))
        streamer.add_member(StreamMemberInt('tf'))

        sub.setup_streamer(streamer)

        return streamer

    def stream_timeframe_data(self, streamer, sub):
        streamer.member('tf').update(sub.tf)
        streamer.push()

        sub.stream(streamer)

    def subscribe_info(self):
        result = False

        self.lock()

        if not self._global_streamer:
            self.setup_streaming()

        if self._global_streamer:
            self._global_streamer.use()
            result = True

        self.unlock()
        return result

    def unsubscribe_info(self):
        result = False

        self.lock()

        if self._global_streamer:
            self._global_streamer.unuse()
            
            if self._global_streamer.is_free():
                self._global_streamer = None

            result = True

        self.unlock()
        return result

    def subscribe(self, timeframe):
        """
        Use or create a specific streamer.
        """
        result = False

        self.lock()

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

        self.unlock()
        return False

    def unsubscribe(self, timeframe):
        """
        Delete a specific streamer when no more subscribers.
        """
        result = False

        self.lock()

        if timeframe is not None and isinstance(timeframe, (float, int)):
            timeframe = self.timeframes.get(timeframe)

        if timeframe in self._timeframe_streamers:
            self._timeframe_streamers[timeframe].unuse()
            if self._timeframe_streamers[timeframe].is_free():
                # delete if 0 subscribers
                del self._timeframe_streamers[timeframe]
    
            self.unlock()
            result = True

        self.unlock()
        return result
