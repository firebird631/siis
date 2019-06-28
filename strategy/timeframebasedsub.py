# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based sub-strategy base class.

from instrument.candlegenerator import CandleGenerator


class TimeframeBasedSub(object):
    """
    TimeframeBasedSub sub computation base class.
    """

    def __init__(self, data, tf, parent_tf, depth, history):
        self.data = data  # parent strategy trader data object

        self.tf = tf
        self.parent_tf = parent_tf
        self.depth = depth
        self.history = history
        self.profiling = False

        self.next_timestamp = 0  # next candle timestamp

        self.candles_gen = CandleGenerator(self.data.base_timeframe, self.tf)

        # @todo distinct entry from exit signal (last)
        self.last_signal = None

    def init_candle_generator(self):
        if self.candles_gen and not self.candles_gen.current:
            last_candle = self.data.instrument.candle(self.tf)
            if last_candle:  #  and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self.candles_gen.current = last_candle

    def need_update(self, timestamp):
        return timestamp >= self.next_timestamp

    def process(self, timestamp):
        pass

    def setup_streamer(self, streamer):
        pass

    def stream(self, streamer):
        pass

    @property
    def timeframe(self):
        return self.tf

    @property
    def parent_timeframe(self):
        return self.parent_tf
