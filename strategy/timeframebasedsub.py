# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based sub-strategy base class.

from instrument.candlegenerator import CandleGenerator


class TimeframeBasedSub(object):
    """
    TimeframeBasedSub sub computation base class.
    """

    def __init__(self, strategy_trader, timeframe, parent_timeframe, depth, history):
        self.strategy_trader = strategy_trader  # parent strategy-trader object

        self.tf = timeframe
        self.parent_tf = parent_timeframe
        self.depth = depth       # min samples size needed for processing
        self.history = history   # sample history size
        self.profiling = False   # profiling mean store the states of the indicators for any signals
        self.next_timestamp = 0  # next waiting, to be processed ohlc timestamp

        self.candles_gen = CandleGenerator(self.strategy_trader.base_timeframe, self.tf)

        # @todo do we distinct entry from exit signal (last) ?
        self.last_signal = None

        self.trend = 0

        self.can_long = False
        self.can_short = False        

    def init_candle_generator(self):
        """
        Setup the ohlc generator for this sub unit using the configured timeframe
        and the current opened ohlc.
        This method is called once the initial ohlc are fetched from the strategy setup process.
        """
        if self.candles_gen and not self.candles_gen.current:
            last_candle = self.strategy_trader.instrument.candle(self.tf)
            if last_candle:  #  and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self.candles_gen.current = last_candle

    def need_update(self, timestamp):
        """
        An update is needed if the timestamp is greater than the next waited timestamp.
        next_timestamp must be updated during the processing.
        """
        return timestamp >= self.next_timestamp

    def process(self, timestamp):
        """
        Process the computation here.
        """
        pass

    @property
    def timeframe(self):
        """
        Timeframe of this strategy-trader in second.
        """
        return self.tf

    @property
    def parent_timeframe(self):
        """
        If a parent timeframe is defined, then it refers to its timeframe.
        """
        return self.parent_tf

    @property
    def samples_depth_size(self):
        """
        Number of Ohlc to have at least to process the computation.
        """
        return self.depth

    @property
    def samples_history_size(self):
        """
        Number of Ohlc used for inititalization on kept in memory.
        """
        return self.history

    #
    # data streaming (@deprecated way)
    #

    def setup_streamer(self, streamer):
        pass

    def stream(self, streamer):
        pass
