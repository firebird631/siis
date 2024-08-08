# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Backtesting strategy data feeder/promise
from datetime import datetime
from typing import List, Optional, Dict, TYPE_CHECKING

from database.economiceventstorage import EconomicEventStreamer
from database.tickstorage import TickStreamer
from instrument.instrument import Instrument
from database.ohlcstorage import OhlcStreamer

from database.database import Database

import logging

logger = logging.getLogger('siis.strategy.datafeeder')


class StrategyDataFeeder(object):
    """
    Ticks and candles data feeder for strategy backtesting. It read data from specific streamer.
    """

    _instrument: Optional[Instrument]
    _candle_streamer: Dict[float, Optional[OhlcStreamer]]
    _tick_streamer: Optional[TickStreamer]
    _economic_events_streamer: Optional[EconomicEventStreamer]

    def __init__(self, strategy, market_id: str, timeframes: List[float], ticks: bool,
                 country: str = None, currency: str = None, min_level: int = 1):
        """
        For backtesting only fetch data from database and stream them according the timestamp.
        """
        self._strategy = strategy
        self._initialized = False

        self._market_id = market_id
        self._instrument = None

        self._timeframes = timeframes
        self._candle_streamer = {tf: None for tf in timeframes}

        self._fetch_ticks = ticks
        self._tick_streamer = None

        self._country = country
        self._currency = currency
        self._min_level = min_level
        self._economic_events_streamer = None

        self._finished = False

    @property
    def strategy(self):
        return self._strategy

    @property
    def market_id(self) -> str:
        return self._market_id
    
    @property
    def instrument(self) -> Instrument:
        return self._instrument

    @property
    def has_economic_events(self) -> bool:
        return self._economic_events_streamer is not None

    def initialize(self, watcher_name, from_date: datetime, to_date: datetime):
        """
        Initialize data streamer.
        """
        for tf in self._timeframes:
            self._candle_streamer[tf] = Database.inst().create_ohlc_streamer(watcher_name, self._market_id, tf,
                                                                             from_date=from_date, to_date=to_date)

        if self._fetch_ticks:
            self._tick_streamer = Database.inst().create_tick_streamer(watcher_name, self._market_id,
                                                                       from_date=from_date, to_date=to_date)

        self._economic_events_streamer = Database.inst().create_economic_event_streamer(
            self._country, self._currency, self._min_level, from_date=from_date, to_date=to_date)

        if self._country or self._currency:
            self._economic_events_streamer = Database.inst().create_economic_event_streamer(
                watcher_name, self._country, self._currency, self._min_level, from_date=from_date, to_date=to_date)

        self._initialized = True

    def ready(self) -> bool:
        """Once initialized and received the instrument."""
        return self._initialized and self._instrument is not None

    def set_instrument(self, instrument):
        """Once the instrument is retrieved set it"""
        self._instrument = instrument

    def finished(self) -> bool:
        """Returns True if there is no more data for any timeframes."""
        return self._finished

    def feed(self, timestamp: float):
        """
        Feed the next candles to fill the passed timestamp, for the predefined timeframes and instrument.
        If one or more data are feds then returns the list of updated units of time.

        @return list of updated timeframe sorted from lesser to higher.
        """
        updated = []
        finished = True

        # need instrument be ready
        if self._instrument is None:
            return []

        for tf, streamer in self._candle_streamer.items():
            # candles must be ready
            if streamer is None or streamer.finished():
                continue

            # buffer
            candles = streamer.next(timestamp)

            if candles:
                self._instrument.add_candles(candles)
                updated.append(tf)

                # defines the last market price
                self.instrument.market_bid = candles[-1].close - candles[-1].spread * 0.5
                self.instrument.market_ask = candles[-1].close + candles[-1].spread * 0.5

            finished = streamer.finished() and not candles

        # ticks must be ready
        if self._tick_streamer and not self._tick_streamer.finished():
            # ticks = self._tick_streamer.next(timestamp)
            # if ticks:
            #   self._instrument.add_ticks(ticks)
            #   updated.append(0)

            # speedup version, direct fill the instrument array
            if self._tick_streamer.next_to(timestamp, self._instrument.ticks()):
                updated.append(0)

                last_tick = self._instrument.ticks()[-1]

                # defines the last market price (prefer at tick if we have candles and ticks)
                self.instrument.last_update_time = last_tick[0]

                # set bid/ask from tick, but on trade data we don't have it
                self.instrument.market_bid = last_tick[1]
                self.instrument.market_ask = last_tick[2]

            finished = self._tick_streamer.finished()

        if finished:
            # fed all data
            self._finished = True

        # lesser to higher
        return sorted(updated)

    def feed_economic_events(self, timestamp: float):
        """
        Feed the next economic events.
        """
        if self._economic_events_streamer and not self._finished:
            streamer = self._economic_events_streamer
            # candles must be ready
            if not streamer.finished():
                # buffer
                economic_events = streamer.next(timestamp)

                return economic_events

        return []
