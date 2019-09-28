# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Timeframe based sub-strategy base class.

from instrument.candlegenerator import CandleGenerator


class TimeframeBasedSub(object):
    """
    TimeframeBasedSub sub computation base class.
    """

    def __init__(self, strategy_trader, timeframe, depth, history, params=None):
        self.strategy_trader = strategy_trader  # parent strategy-trader object

        params = params or {}

        self.tf = timeframe
        self.depth = depth       # min samples size needed for processing
        self.history = history   # sample history size
        self.next_timestamp = 0  # next waiting, to be processed ohlc timestamp

        self._update_at_close = params.get('update-at-close', False)
        self._signal_at_close = params.get('signal-at-close', False)

        self.candles_gen = CandleGenerator(self.strategy_trader.base_timeframe, self.tf)
        self._last_closed = False  # last generated candle closed

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
            if last_candle and not last_candle.ended:
                # the last candle is not ended, we have to continue it
                self.candles_gen.current = last_candle

    def need_update(self, timestamp):
        """
        Return True if the compute must be done.
        If update at close then wait for the last OHLC close, else always returns true.
        """
        if self._update_at_close:
            return self._last_closed

        return True

    def need_signal(self, timestamp):
        """
        Return True if the signal can be generated and returned at this processing.
        If signal at close than wait for the last candle close, else always returns true.
        """
        if self._signal_at_close:
            return self._last_closed

        return True

    def process(self, timestamp):
        """
        Process the computation here.
        """
        pass

    def complete(self, candles):
        """
        Must be called at the end of the process method.
        """
        if candles:
            # last processed candle timestamp (from last candle if non consolidated else from the next one)
            self.next_timestamp = candles[-1].timestamp if not candles[-1].ended else candles[-1].timestamp + self.tf

        # last closed candle processed
        self._last_closed = False

    #
    # properties
    #

    @property
    def timeframe(self):
        """
        Timeframe of this strategy-trader in second.
        """
        return self.tf

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

    @property
    def update_at_close(self):
        return self._update_at_close

    @property
    def signal_at_close(self):
        return self._signal_at_close

    @property
    def last_closed(self):
        return self._last_closed

    #
    # data streaming (@deprecated way)
    #

    def setup_streamer(self, streamer):
        pass

    def stream(self, streamer):
        pass
