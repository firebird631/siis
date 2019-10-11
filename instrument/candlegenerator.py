# @date 2018-09-05
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Higher candle generator.

from datetime import datetime, timedelta
from common.utils import UTC

from instrument.instrument import Candle


class CandleGenerator(object):

    __slots__ = '_from_tf', '_to_tf', '_candle', '_last_timestamp', '_last_consumed'

    def __init__(self, from_tf, to_tf):
        """
        @param to_tf Generated candle time unit.
        """
        if from_tf and (int(to_tf) % int(from_tf) != 0):
            raise(ValueError("From timeframe %s must be an integral divider of to timeframe %s" % (from_tf, to_tf)))

        self._from_tf = float(from_tf)
        self._to_tf = float(to_tf)
        self._candle = None
        self._last_timestamp = 0
        self._last_consumed = 0

    @property
    def current(self):
        """
        If exists returns the current non closed candle.
        """
        return self._candle

    @current.setter
    def current(self, candle):
        self._candle = candle

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
            # already done (and what if two consecutives ticks have the same timestamp ?)
            return None

        # basetime can be slow, uses only to create a new candle
        # base_time = self.basetime(from_tick[0])
        ended_candle = None

        # if self._candle and self._candle.timestamp+self._to_tf <= base_time:
        if self._candle and from_tick[0] >= self._candle.timestamp+self._to_tf:
            # need to close the candle and to open a new one
            self._candle.set_consolidated(True)
            ended_candle = self._candle

            self._candle = None

        if self._candle is None:
            # open a new one
            base_time = self.basetime(from_tick[0])

            self._candle = Candle(base_time, self._to_tf)
            self._candle.set_consolidated(False)

            # all open, close, low high from the initial candle
            self._candle.set_bid(from_tick[1])
            self._candle.set_ofr(from_tick[2])

        # update volumes
        self._candle._volume += from_tick[3]

        # update bid prices

        # bid high/low
        self._candle._bid_high = max(self._candle._bid_high, from_tick[1])
        self._candle._bid_low = min(self._candle._bid_low, from_tick[1])

        # potential close
        self._candle._bid_close = from_tick[1]

        # update ofr prices

        # ofr high/low
        self._candle._ofr_high = max(self._candle._ofr_high, from_tick[2])
        self._candle._ofr_low = min(self._candle._ofr_low, from_tick[2])

        # potential close
        self._candle._ofr_close = from_tick[2]

        # keep last timestamp
        self._last_timestamp = from_tick[0]

        return ended_candle


    def update_from_candle(self, from_candle, ignore_non_ended):
        """
        From a timeframe, create/update candle to another timeframe, that must be greater and a multiple of.
        Example of creating/updating hourly candle for 1 minute candles.

        Must be called each time a new candle of the lesser timeframe is append.
        It only create the last or update the current candle.

        A non ended candle is ignored because it will false the volume.
        """
        if from_candle is None:
            return None

        if ignore_non_ended and not from_candle.ended:
            return None

        if self._from_tf != from_candle.timeframe:
            raise ValueError("From candle must be of time unit %s but %s is provided" % (self._from_tf, from_candle.timeframe))

        if from_candle.timestamp <= self._last_timestamp:
            # already done
            return None

        # base_time = self.basetime(from_candle.timestamp)
        ended_candle = None

        # if self._candle and self._candle.timestamp+self._to_tf <= base_time:
        if self._candle and from_candle.timestamp >= self._candle.timestamp+self._to_tf:
            # need to close the candle and to open a new one
            self._candle.set_consolidated(True)
            ended_candle = self._candle

            self._candle = None

        if self._candle is None:
            # open a new one
            base_time = self.basetime(from_candle.timestamp)

            self._candle = Candle(base_time, self._to_tf)
            self._candle.set_consolidated(False)

            # all open, close, low high from the initial candle
            self._candle.copy_bid(from_candle)
            self._candle.copy_ofr(from_candle)

        # update volumes
        self._candle._volume += from_candle.volume

        # update bid prices
        self._candle._bid_high = max(self._candle._bid_high, from_candle._bid_high)
        self._candle._bid_low = min(self._candle._bid_low, from_candle._bid_low)

        # potential close
        self._candle._bid_close = from_candle._bid_close

        # update ofr prices
        self._candle._ofr_high = max(self._candle._ofr_high, from_candle._ofr_high)
        self._candle._ofr_low = min(self._candle._ofr_low, from_candle._ofr_low)

        # potential close
        self._candle._ofr_close = from_candle._ofr_close

        # keep last timestamp
        self._last_timestamp = from_candle.timestamp

        return ended_candle
