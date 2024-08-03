# @date 2018-09-05
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# OHLC timeframe bar generator.

from datetime import datetime, timedelta
from common.utils import UTC

from instrument.instrument import Candle


class TimeframeBarGenerator(object):

    __slots__ = '_from_tf', '_to_tf', '_current_bar', '_last_timestamp', '_last_consumed', '_indicators'

    def __init__(self, from_tf: float, to_tf: float):
        """
        @param to_tf Generated candle time unit.
        """
        if from_tf and (int(to_tf) % int(from_tf) != 0):
            raise(ValueError("From timeframe %s must be an integral divider of to timeframe %s" % (from_tf, to_tf)))

        self._from_tf = float(from_tf)
        self._to_tf = float(to_tf)
        self._current_bar = None
        self._last_timestamp = 0
        self._last_consumed = 0

        self._indicators = []   # attached indicator the must be generated at the same time

    @property
    def current(self):
        """
        If exists returns the current non-closed candle.
        """
        return self._current_bar

    @current.setter
    def current(self, candle):
        self._current_bar = candle

    @property
    def last_timestamp(self):
        return self._last_timestamp

    @property
    def last_consumed(self):
        return self._last_consumed

    @property
    def from_tf(self):
        return self._from_tf
    
    @property
    def to_tf(self):
        return self._to_tf

    def attach_indicator(self, indicator):
        if indicator:
            self._indicators.append(indicator)

    def generate_from_candles(self, from_candles, ignore_non_ended=True):
        """
        Generate as many higher candles as possible from the array of candles given in parameters.
        @note Non ended candles are ignored because it will false the volume.
        """
        to_candles = []
        self._last_consumed = 0

        for from_candle in from_candles:
            to_candle = self.update_from_candle(from_candle, ignore_non_ended)
            if to_candle:
                to_candles.append(to_candle)

            # alongside generate tick based indicator, close them only if a new bar
            if self._indicators:
                for indicator in self._indicators:
                    indicator.generate(from_candle, finalize=to_candle is not None)

            self._last_consumed += 1

        return to_candles

    def generate_from_ticks(self, from_ticks):
        """
        Generate as many higher candles as possible from the array of ticks given in parameters.
        """
        to_candles = []
        self._last_consumed = 0

        for from_tick in from_ticks:
            to_candle = self.update_from_tick(from_tick)

            if to_candle:
                to_candles.append(to_candle)

            # alongside generate tick based indicator, close them only if a new bar
            if self._indicators:
                for indicator in self._indicators:
                    indicator.generate(from_tick, finalize=to_candle is not None)

            self._last_consumed += 1

        return to_candles

    def basetime(self, timestamp):
        if self._to_tf < 7*24*60*60:
            # simplest
            return int(timestamp / self._to_tf) * self._to_tf
        elif self._to_tf == 7*24*60*60:
            # must find the UTC first day of week
            dt = datetime.utcfromtimestamp(timestamp)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC()) - timedelta(days=dt.weekday())
            return dt.timestamp()
        elif self._to_tf == 30*24*60*60:
            # replace by first day of month at 00h00 UTC
            dt = datetime.utcfromtimestamp(timestamp)
            dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())
            return dt.timestamp()

    def update_from_tick(self, from_tick):
        if from_tick is None:
            return None

        if from_tick[0] <= self._last_timestamp:
            # already done (and what if two consecutive ticks have the same timestamp ?)
            return None

        # basetime can be slow, uses only to create a new candle
        # base_time = self.basetime(from_tick[0])
        ended_candle = None

        # if self._candle and self._candle.timestamp+self._to_tf <= base_time:
        if self._current_bar and from_tick[0] >= self._current_bar.timestamp+self._to_tf:
            # need to close the candle and to open a new one
            self._current_bar.set_consolidated(True)
            ended_candle = self._current_bar

            self._current_bar = None

        if self._current_bar is None:
            # open a new one
            base_time = self.basetime(from_tick[0])

            self._current_bar = Candle(base_time, self._to_tf)
            self._current_bar.set_consolidated(False)

            # all open, close, low high from the initial candle
            self._current_bar.set(from_tick[3])
            self._current_bar.set_spread(from_tick[2] - from_tick[1])

        # update volumes
        self._current_bar._volume += from_tick[4]

        # update prices

        # high/low
        self._current_bar._high = max(self._current_bar._high, from_tick[3])
        self._current_bar._low = min(self._current_bar._low, from_tick[3])

        # potential close
        self._current_bar._close = from_tick[3]

        # potential spread
        # @todo could be the max of
        self._current_bar._spread = from_tick[2] - from_tick[1]

        # keep last timestamp
        self._last_timestamp = from_tick[0]

        return ended_candle

    def update_from_candle(self, from_candle, ignore_non_ended):
        """
        From a timeframe, create/update candle to another timeframe, that must be greater and a multiple of.
        Example of creating/updating hourly candle for 1 minute candles.

        Must be called each time a new candle of the lesser timeframe is appended.
        It only creates the last or update the current candle.

        A non ended candle is ignored because it will invalid the volume.
        """
        if from_candle is None:
            return None

        if ignore_non_ended and not from_candle.ended:
            return None

        if self._from_tf != from_candle.timeframe:
            raise ValueError("From candle must be of time unit %s but %s is provided" % (
                self._from_tf, from_candle.timeframe))

        if from_candle.timestamp <= self._last_timestamp:
            # already done
            return None

        # base_time = self.basetime(from_candle.timestamp)
        ended_candle = None

        # if self._candle and self._candle.timestamp+self._to_tf <= base_time:
        if self._current_bar and from_candle.timestamp >= self._current_bar.timestamp+self._to_tf:
            # need to close the candle and to open a new one
            self._current_bar.set_consolidated(True)
            ended_candle = self._current_bar

            self._current_bar = None

        if self._current_bar is None:
            # open a new one
            base_time = self.basetime(from_candle.timestamp)

            self._current_bar = Candle(base_time, self._to_tf)
            self._current_bar.set_consolidated(False)

            # all open, close, low high from the initial candle
            self._current_bar.copy(from_candle)

        # update volumes
        self._current_bar._volume += from_candle.volume

        # update prices
        self._current_bar._high = max(self._current_bar._high, from_candle._high)
        self._current_bar._low = min(self._current_bar._low, from_candle._low)

        # potential close
        self._current_bar._close = from_candle._close

        # potential spread
        self._current_bar._spread = from_candle._spread

        # keep last timestamp
        self._last_timestamp = from_candle.timestamp

        return ended_candle
