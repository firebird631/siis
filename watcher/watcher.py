# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# watcher interface

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Dict, Tuple, Set

if TYPE_CHECKING:
    from .service import WatcherService
    from .author import Author
    from .position import Position
    from trader.market import Market
    from instrument.instrument import TickType, OHLCType

import time
import collections

from datetime import datetime, timedelta

from common.runnable import Runnable
from common.utils import matching_symbols_set, UTC
from terminal.terminal import Terminal

from common.signal import Signal
from database.database import Database

from instrument.instrument import Instrument, Candle
from instrument.candlegenerator import CandleGenerator

from monitor.streamable import Streamable, StreamMemberInt

import logging
logger = logging.getLogger('siis.watcher')
error_logger = logging.getLogger('siis.error.watcher')


class Watcher(Runnable):
    """
    Watcher base class.

    In specialisation, use the pre_update to manage the connection state.
    """

    COMMAND_INFO = 1

    COMMAND_SUBSCRIBE = 2
    COMMAND_UNSUBSCRIBE = 3

    UPDATE_MARKET_INFO_DELAY = 4*60*60  # 4h between each market data info fetch

    WATCHER_UNDEFINED = 0
    WATCHER_PRICE_AND_VOLUME = 1
    WATCHER_BUY_SELL_SIGNAL = 2
    WATCHER_ALL = 1 | 2

    DEFAULT_PREFETCH_SIZE = 100  # by default prefetch 100 OHLCs for each stored timeframe

    TICK_STORAGE_DELAY = 0.05  # 50ms
    MAX_PENDING_TICK = 10000

    # stored OHLC timeframes
    STORED_TIMEFRAMES = (
        Instrument.TF_MIN,
        Instrument.TF_3MIN,
        Instrument.TF_5MIN,
        Instrument.TF_15MIN,
        Instrument.TF_30MIN,
        Instrument.TF_HOUR,
        Instrument.TF_2HOUR,
        Instrument.TF_4HOUR,
        Instrument.TF_DAY,
        Instrument.TF_WEEK)

    # generated OHLC timeframes
    GENERATED_TF = (
        Instrument.TF_MIN,
        Instrument.TF_3MIN,
        Instrument.TF_5MIN,
        Instrument.TF_15MIN,
        Instrument.TF_30MIN,
        Instrument.TF_HOUR,
        Instrument.TF_2HOUR,
        Instrument.TF_4HOUR,
        Instrument.TF_DAY,
        Instrument.TF_WEEK)

    _authors: Dict[str, Author]
    _positions: Dict[str, Position]

    _last_ohlc: Dict[str, Dict[float, Union[Candle, None]]]
    _last_update_times: Dict[float, float]

    def __init__(self, name: str, service: WatcherService, watcher_type: int):
        super().__init__("wt-%s" % (name,))

        self._name = name
        self._service = service
        self._authors = {}
        self._positions = {}
        self._watcher_type = watcher_type

        self._ready = False
        self._connecting = False
        self._retry = 0
        self._last_retry = 0

        self._signals = collections.deque()

        self._available_instruments = set()  # all available instruments
        self._watched_instruments = set()    # watched instruments

        self._data_streams = {}

        self._streamable = None
        self._heartbeat = 0

        self._store_ohlc = service.store_ohlc        # default never store OHLC to DB storage
        self._store_trade = service.store_trade      # default never store trade/tick/quote during watching
        self._initial_fetch = service.initial_fetch  # default never fetch history of OHLC at connection

        self._last_ohlc = {}  # last OHLC per market id and then per timeframe
        self._last_update_times = {tf: 0.0 for tf in self.GENERATED_TF}

        self._last_market_update = time.time()

        # listen to its service
        self.service.add_listener(self)

        # streaming
        self.setup_streaming()

    def setup_streaming(self):
        self._streamable = Streamable(self.service.monitor_service, Streamable.STREAM_WATCHER, "status", self.name)
        self._streamable.add_member(StreamMemberInt('ping'))
        self._streamable.add_member(StreamMemberInt('conn'))

    def stream(self):
        if self._streamable:
            self._streamable.publish()

    @property
    def watcher_type(self) -> int:
        """
        Type of watched data
        """
        return self._watcher_type

    @property
    def has_prices_and_volumes(self) -> bool:
        """
        This watchers looks for price and volumes data.
        """
        return self._watcher_type & Watcher.WATCHER_PRICE_AND_VOLUME == Watcher.WATCHER_PRICE_AND_VOLUME

    @property
    def has_buy_sell_signals(self) -> bool:
        """
        This watcher looks for buy/sell signals data.
        """
        return self._watcher_type & Watcher.WATCHER_BUY_SELL_SIGNAL == Watcher.WATCHER_BUY_SELL_SIGNAL

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self) -> bool:
        return False

    @property
    def connector(self):
        return None

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def initial_fetch(self) -> bool:
        return self._initial_fetch
    
    @initial_fetch.setter
    def initial_fetch(self, value):
        self._initial_fetch = value

    def stream_connection_status(self, status: bool):
        if self._streamable:
            self._streamable.member('conn').update(1 if status else -1)

    #
    # instruments
    #

    def insert_watched_instrument(self, market_id: str, timeframes: Union[Tuple[float], List[float]]):
        """
        Must be called for each subscribed market to initialize the last price data structure.

        @warning Non thread safe method.
        """
        if market_id not in self._watched_instruments:
            self._watched_instruments.add(market_id)

        _timeframes = set.union(set(Watcher.STORED_TIMEFRAMES), set(timeframes))

        for timeframe in _timeframes:
            if timeframe != Instrument.TF_TICK:
                if market_id not in self._last_ohlc:
                    self._last_ohlc[market_id] = {}

                if timeframe not in self._last_ohlc[market_id]:
                    self._last_ohlc[market_id][timeframe] = None

    def configured_symbols(self) -> Set[str]:
        """
        Configured instruments symbols from config of the watcher.
        @return A set of symbol, can contains '*' or any symbols prefixed by a '*'.
        """
        watcher_config = self.service.watcher_config(self._name)
        if watcher_config:
            configured_symbols = watcher_config.get('symbols', [])
        else:
            configured_symbols = []

        return set(configured_symbols)

    def matching_symbols_set(self, configured_symbols: Union[Tuple[str], List[str], Set[str]],
                             available_symbols: Union[Tuple[str], List[str], Set[str]]) -> Set[str]:
        """
        Special '*' symbol mean every symbol.
        Starting with '!' mean except this symbol.
        Starting with '*' mean every wildcard before the suffix.

        @param configured_symbols:
        @param available_symbols List containing any supported markets symbol of the broker. Used when a
               wildcard is defined.
        """
        return matching_symbols_set(configured_symbols, available_symbols)

    def has_instrument(self, instrument: str) -> bool:
        return instrument in self._available_instruments

    def is_watched_instrument(self, instrument: str) -> bool:
        return instrument in self._watched_instruments

    def available_instruments(self) -> Set[str]:
        """
        All available instruments.
        """
        return self._available_instruments

    def watched_instruments(self) -> Set[str]:
        """
        Watched instruments.
        """
        return self._watched_instruments

    def subscribe(self, market_id: str, ohlc_depths: Optional[dict[float]] = None,
                  tick_depth: Optional[int] = None, order_book_depth: Optional[int] = None):
        """
        Subscribes for receiving data from price source for a market and a timeframe.

        @param market_id str Valid market identifier
        @param ohlc_depths A dict of timeframe with an integer value depth of history or -1 for full update from
            last stored point
        @param tick_depth An integer of depth value of ticks/trader or -1 for full update from last stored point
        @param order_book_depth An integer of order book size
        """
        return False

    def unsubscribe(self, market_id: str, timeframe: float) -> bool:
        """
        Unsubscribes from receiving data for a market and a timeframe or any timeframe.

        @param market_id str Valid market identifier
        @param timeframe int TF_xxx or -1 for any
        """
        return False

    def current_ohlc(self, market_id: str, timeframe: float) -> Union[Candle, None]:
        """
        Return current OHLC for a specific market-id and timeframe or None.
        """
        if market_id in self._last_ohlc:
            return self._last_ohlc[market_id].get(timeframe)

        return None

    #
    # processing
    #

    def receiver(self, signal: Signal):
        if signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name != self._name:
                # only interested by the watcher of the same name
                return

            elif signal.signal_type not in (Signal.SIGNAL_MARKET_LIST_DATA,):
                return

            # signal of interest
            self._signals.append(signal)

    def pre_run(self):
        Terminal.inst().message("Running watcher %s..." % self._name)
        self.connect()

    def post_run(self):
        Terminal.inst().message("Joining watcher %s..." % self._name)
        self.disconnect()
        Terminal.inst().message("Watcher %s stopped." % self._name)

    def update(self):
        """
        Nothing by default but must return True.
        """
        return True

    def post_update(self):
        # streaming
        try:
            now = time.time()
            if now - self._heartbeat >= 1.0:
                if self._streamable:
                    self._streamable.member('ping').update(int(now*1000))

                self._heartbeat = now
        except Exception as e:
            error_logger.error(repr(e))

        self.stream()

    @property
    def name(self) -> str:
        return self._name

    def find_author(self, author_id: str) -> Union[Author, None]:
        return self._authors.get(str(author_id))

    @property
    def service(self) -> WatcherService:
        return self._service

    def command(self, command_type: int, data: dict) -> Union[dict, None]:
        # @todo info, subscribe, unsubscribe commands
        return None

    def pong(self, timestamp: float, pid: int, watchdog_service, msg: str):
        if msg:
            # display watcher activity
            if self.connected:
                Terminal.inst().action("Watcher worker %s is alive %s" % (self._name, msg), view='content')
            else:
                Terminal.inst().action("Watcher worker %s is alive but waiting for (re)connection %s" % (self._name, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    def fetch_market(self, market_id: str) -> Union[Market, None]:
        """
        Retrieve market details for a specific market id and return a new Market instance if found.
        You should cache it to avoid multiple request.
        """
        return None

    def update_markets_info(self):
        """
        Update the market info from the API, for any of the followed markets.
        @note Could cost some REST API credits, don't need to call it often, once per 4h, or per day is sufficient.
        """
        pass

    def historical_data(self, market_id: str, timeframe: float, from_date: Optional[datetime] = None,
                        to_date: Optional[datetime] = None, n_last: Optional[int] = None):
        """
        Async fetch the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Non zero time unit in second
        @param from_date date object
        @param to_date date object
        @param n_last Last n data
        """
        if timeframe <= 0:
            return

        if n_last:
            Database.inst().load_market_ohlc_last_n(self.service, self.name, market_id, timeframe, n_last)
        else:
            Database.inst().load_market_ohlc(self.service, self.name, market_id, timeframe, from_date, to_date)       

    def price_history(self, market_id: str, timestamp: float) -> Union[float, None]:
        """
        Retrieve the historical price for a specific market id.
        """
        return None

    #
    # utils
    #

    def update_ohlc(self, market_id: str, tf: float, ts: float, last: float, spread: float, volume: float):
        """
        Update the current OHLC or create a new one, and save them.

        @param market_id: str Unique market identifier
        @param tf: float Timeframe (normalized timeframe at second)
        @param ts: float Timestamp of the update or of the tick/trade
        @param last: float Last price.
        @param spread: float Spread.
        @param volume float Volume transacted or 0 if unspecified.
        """
        ended_ohlc = None
        ohlc = None

        # last ohlc per market id
        last_ohlc_by_timeframe = self._last_ohlc.get(market_id)
        if last_ohlc_by_timeframe is None:
            # not found for this market insert it
            self._last_ohlc[market_id] = {tf: None}
            last_ohlc_by_timeframe = self._last_ohlc[market_id]

        if tf not in last_ohlc_by_timeframe:
            last_ohlc_by_timeframe[tf] = None
        else:
            ohlc = last_ohlc_by_timeframe[tf]

        if ohlc and ts >= ohlc.timestamp + tf:
            # need to close the current ohlc
            ohlc.set_consolidated(True)
            ended_ohlc = ohlc

            last_ohlc_by_timeframe[tf] = None
            ohlc = None

        if ohlc is None:
            # open a new one if necessary
            base_time = Instrument.basetime(tf, ts)
            ohlc = Candle(base_time, tf)

            ohlc.set_consolidated(False)

            if last:
                ohlc.set(last)

            if spread:
                ohlc.set_spread(spread)

            last_ohlc_by_timeframe[tf] = ohlc

        if ts >= ohlc.timestamp:
            # update the current OHLC
            if volume:
                ohlc._volume += volume

            if last:
                if not ohlc._open:
                    ohlc.set(last)

                # update prices
                ohlc._high = max(ohlc._high, last)
                ohlc._low = min(ohlc._low, last)

                # potential close
                ohlc._close = last

            if spread:
                # potential spread
                ohlc._spread = spread

        # stored timeframes only
        if self._store_ohlc and ended_ohlc and (tf in self.STORED_TIMEFRAMES):
            Database.inst().store_market_ohlc((
                self.name, market_id, int(ended_ohlc.timestamp*1000), tf,
                ended_ohlc._open, ended_ohlc._high, ended_ohlc._low, ended_ohlc._close,
                ended_ohlc._spread,
                ended_ohlc._volume))

        return ohlc

    def close_ohlc(self, market_id: str, last_ohlc_by_timeframe: Dict[float, Union[Candle, None]],
                   tf: float, ts: float) -> Union[Candle, None]:
        ohlc = last_ohlc_by_timeframe.get(tf)
        ended_ohlc = None

        if ohlc and ts >= ohlc.timestamp + tf:
            # need to close the current ohlc
            ohlc.set_consolidated(True)
            ended_ohlc = ohlc

            last_ohlc_by_timeframe[tf] = None

        # stored timeframes only
        if self._store_ohlc and ended_ohlc and (tf in self.STORED_TIMEFRAMES):
            Database.inst().store_market_ohlc((
                self.name, market_id, int(ended_ohlc.timestamp*1000), tf,
                ended_ohlc._open, ended_ohlc._high, ended_ohlc._low, ended_ohlc._close,
                ended_ohlc._spread,
                ended_ohlc._volume))

        return ended_ohlc

    def update_from_tick(self):
        """
        During update processing, close OHLCs if not tick data arrive before.
        Then notify a signal if a ohlc is generated (and closed).
        """
        now = time.time()

        for tf in self.GENERATED_TF:
            # only if current base time is greater than the previous
            base_time = Instrument.basetime(tf, now)
            if base_time > self._last_update_times[tf]:
                self._last_update_times[tf] = base_time

                for market_id, last_ohlc_by_timeframe in self._last_ohlc.items():
                    if last_ohlc_by_timeframe:
                        ohlc = self.close_ohlc(market_id, last_ohlc_by_timeframe, tf, now)
                        if ohlc:
                            self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, ohlc))

    def fetch_and_generate(self, market_id: str, timeframe: float, n_last: int = 1, cascaded: Optional[float] = None):
        """
        For initial fetching of the last OHLCs.
        """
        if timeframe < Instrument.TF_1M or timeframe not in self.GENERATED_TF:
            error_logger.error("Timeframe %i is not allowed !" % (timeframe,))
            return

        generators = []
        from_tf = timeframe

        # compute a from date
        today = datetime.now().astimezone(UTC())
        from_date = today

        # for n last, minus a delta time
        if timeframe == Instrument.TF_MONTH:
            # ohlc based
            if n_last < 0:
                # get last datetime from OHLCs DB, and always overwrite it because if it was not closed
                last_ohlc = Database.inst().get_last_ohlc(self.name, market_id, timeframe)

                if last_ohlc:
                    last_timestamp = last_ohlc.timestamp

                    last_date = datetime.fromtimestamp(last_timestamp, tz=UTC())
                    from_date = last_date
                else:
                    # no previous then query all necessary
                    from_date = today - timedelta(days=30*n_last)
            else:
                from_date = today - timedelta(days=30*n_last)

        else:
            # ohlc based
            if n_last < 0:
                # get last datetime from OHLCs DB, and always overwrite it because if it was not closed
                last_ohlc = Database.inst().get_last_ohlc(self.name, market_id, timeframe)

                if last_ohlc:
                    # if cascaded is defined, then we need more past data to have a full range
                    # (until 7x1d for the week, until 4x1h for the 4h...)
                    if cascaded:
                        last_timestamp = Instrument.basetime(cascaded, last_ohlc.timestamp)
                    else:
                        last_timestamp = last_ohlc.timestamp

                    last_date = datetime.fromtimestamp(last_timestamp, tz=UTC())
                    from_date = last_date
                else:
                    # no previous then query all necessary
                    from_date = today - timedelta(seconds=int(timeframe)*n_last)
            else:
                from_date = today - timedelta(seconds=int(timeframe)*n_last)

        to_date = today

        last_ohlcs = {}
        current_ohlc = {}

        # cascaded generation of candles
        if cascaded:
            for tf in Watcher.GENERATED_TF:
                if tf > timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded:
                        # until max cascaded timeframe
                        generators.append(CandleGenerator(from_tf, tf))
                        from_tf = tf

                        # store for generation
                        last_ohlcs[tf] = []
                else:
                    from_tf = tf

        if timeframe > 0:
            last_ohlcs[timeframe] = []

        n = 0

        # fetch OHLC history
        for data in self.fetch_candles(market_id, timeframe, from_date, to_date, None):
            # store (int timestamp ms, str open, high, low, close, spread, volume)
            Database.inst().store_market_ohlc((
                self.name, market_id, data[0], int(timeframe),
                data[1], data[2], data[3], data[4],  # OHLC
                data[5],  # spread
                data[6]))  # volume

            candle = Candle(float(data[0]) * 0.001, timeframe)

            candle.set_ohlc(float(data[1]), float(data[2]), float(data[3]), float(data[4]))

            candle.set_spread(float(data[5]))
            candle.set_volume(float(data[6]))

            if candle.timestamp >= Instrument.basetime(timeframe, time.time()):
                candle.set_consolidated(False)  # current

            last_ohlcs[timeframe].append(candle)

            # only the last
            current_ohlc[timeframe] = candle

            # generate higher candles
            for generator in generators:              
                candles = generator.generate_from_candles(last_ohlcs[generator.from_tf], False)
                if candles:
                    if 1:  # self._store_ohlc: need to store initial-fetch to retrieve them from the strategy
                        for c in candles:
                            self.store_candle(market_id, generator.to_tf, c)

                    last_ohlcs[generator.to_tf].extend(candles)

                    # only the last as current
                    current_ohlc[generator.to_tf] = candles[-1]

                if generator.current:
                    if 1:  # self._store_ohlc: need to store initial-fetch to retrieve them from the strategy
                        self.store_candle(market_id, generator.to_tf, generator.current)

                    current_ohlc[generator.to_tf] = generator.current

                # remove consumed candles
                last_ohlcs[generator.from_tf] = []

            n += 1

        for k, ohlc in current_ohlc.items():
            if ohlc:
                ohlc.set_consolidated(False)

        # keep the current OHLC for each timeframe
        with self._mutex:
            if market_id not in self._last_ohlc:
                self._last_ohlc[market_id] = {}

            for k, ohlc in current_ohlc.items():
                # set current OHLC
                self._last_ohlc[market_id][k] = ohlc

    def fetch_ticks(self, market_id: str, tick_depth: Optional[int] = None):
        """
        For initial fetching of the recent ticks.
        """
        # compute a from date
        today = datetime.now().astimezone(UTC())
        from_date = today

        # update from last know
        last_tick = Database.inst().get_last_tick(self.name, market_id)
        next_date = datetime.fromtimestamp(last_tick[0] + 0.001, tz=UTC()) if last_tick else None

        if not next_date:
            # or fetch the complete current month
            from_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())

        to_date = today

        n = 0

        # fetch ticks history
        for data in self.fetch_trades(market_id, from_date, to_date, None):
            # store (int timestamp in ms, str bid, str ask, str last, str volume, int direction)
            Database.inst().store_market_trade((self.name, market_id,
                                                data[0], data[1], data[2], data[3], data[4], data[5]))

            n += 1

            # calm down the storage of tick, if parsing is faster
            while Database.inst().num_pending_ticks_storage() > Watcher.MAX_PENDING_TICK:
                time.sleep(Watcher.TICK_STORAGE_DELAY)  # wait a little before continue

    def fetch_trades(self, market_id: str, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None,
                     n_last: Optional[int] = None) -> List[TickType]:
        """
        Retrieve the historical trades data for a certain a period of date.
        @param market_id Specific name of the market
        @param from_date
        @param to_date
        @param n_last:
        """
        return []

    def fetch_candles(self, market_id: str, timeframe: float, from_date: Optional[datetime] = None,
                      to_date: Optional[datetime] = None, n_last: Optional[int] = None) -> List[OHLCType]:
        """
        Retrieve the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Time unit in second.
        @param from_date
        @param to_date
        @param n_last Last n data
        """
        return []

    def store_candle(self, market_id: str, timeframe: float, candle: Candle):
        Database.inst().store_market_ohlc((
            self.name, market_id, int(candle.timestamp*1000.0), int(timeframe),
            str(candle.open), str(candle.high), str(candle.low), str(candle.close),
            str(candle.spread),
            str(candle.volume)))
