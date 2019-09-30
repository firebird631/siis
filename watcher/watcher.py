# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# watcher interface

import time
import collections

from datetime import datetime, timedelta

from common.runnable import Runnable
from common.utils import matching_symbols_set, UTC
from terminal.terminal import Terminal

from notifier.signal import Signal
from config import config
from database.database import Database

from instrument.instrument import Instrument, Candle
from instrument.candlegenerator import CandleGenerator


class Watcher(Runnable):
    """
    Watcher base class.

    @todo subscribe/unsubscribe
    """

    UPDATE_MARKET_INFO_DELAY = 4*60*60  # 4h between each market data info fetch

    WATCHER_UNDEFINED = 0
    WATCHER_PRICE_AND_VOLUME = 1
    WATCHER_BUY_SELL_SIGNAL = 2
    WATCHER_ALL = 1|2

    DEFAULT_PREFETCH_SIZE = 100  # by defaut prefetch 100 OHLCs for each stored timeframe

    # ohlc timeframes of interest for storage
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

    # candles from 1m to 1 week
    GENERATED_TF = [60, 60*3, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

    def __init__(self, name, service, watcher_type):
        super().__init__("wt-%s" % (name,))

        self._name = name
        self._service = service
        self._authors = {}
        self._positions = {}
        self._watcher_type = watcher_type
        self._ready = False

        self._signals = collections.deque()

        self._available_instruments = set()  # all avalaibles instruments
        self._watched_instruments = set()    # watched instruments

        self._data_streams = {}
        self._read_only = service.read_only  # no db storage in read-only mode
        self._store_trade = False            # default never store trade/tick/quote during watching

        self._last_tick = {}  # last tick per market id
        self._last_ohlc = {}  # last ohlc per market id and then per timeframe

        self._last_market_update = time.time()

        # listen to its service
        self.service.add_listener(self)

    @property
    def watcher_type(self):
        """
        Type of watched data
        """
        return self._watcher_type

    @property
    def has_prices_and_volumes(self):
        """
        This watchers looks for price and volumes data.
        """
        return self._watcher_type & Watcher.WATCHER_PRICE_AND_VOLUME == Watcher.WATCHER_PRICE_AND_VOLUME

    @property
    def has_buy_sell_signals(self):
        """
        This watcher looks for buy/sell signals data.
        """
        return self._watcher_type & Watcher.WATCHER_BUY_SELL_SIGNAL == Watcher.WATCHER_BUY_SELL_SIGNAL

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self):
        return False

    @property
    def connector(self):
        return None

    @property
    def ready(self):
        return self._ready

    #
    # instruments
    #

    def insert_watched_instrument(self, market_id, timeframes):
        """
        Must be called for each subscribed market to initialize the last price data structure.
        """
        if market_id not in self._watched_instruments:
            self._watched_instruments.add(market_id)

        ltimeframes = set.union(set(Watcher.STORED_TIMEFRAMES), set(timeframes))

        for timeframe in ltimeframes:
            if timeframe == Instrument.TF_TICK and market_id not in self._last_tick:
                self._last_tick[market_id] = None
            else:
                if market_id not in self._last_ohlc:
                    self._last_ohlc[market_id] = {}

                if timeframe not in self._last_ohlc[market_id]:
                    self._last_ohlc[market_id][timeframe] = None

    def configured_symbols(self):
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

    def matching_symbols_set(self, configured_symbols, available_symbols):
        """
        Special '*' symbol mean every symbol.
        Starting with '!' mean except this symbol.
        Starting with '*' mean every wildchar before the suffix.

        @param available_symbols List containing any supported markets symbol of the broker. Used when a wildchar is defined.
        """
        return matching_symbols_set(configured_symbols, available_symbols)

    def has_instrument(self, instrument):
        return instrument in self._available_instruments

    def is_watched_instrument(self, instrument):
        return instrument in self._watched_instruments

    def available_instruments(self):
        """
        All availables instruments.
        """
        return self._available_instruments

    def watched_instruments(self):
        """
        Watched instruments.
        """
        return self._watched_instruments

    def subscribe(self, market_id, timeframe):
        """
        Subscribes for receiving data from price source for a market and a timeframe.

        @param market_id str Valid market identifier
        @param timeframe int TF_xxx, 0 for tick/trade data
        """
        return False

    def unsubscribe(self, market_id, timeframe):
        """
        Unsubscribes from receiving data for a market and a timeframe or any timeframe.

        @param market_id str Valid market identifier
        @param timeframe int TF_xxx or -1 for any
        """
        return False

    def current_ohlc(self, market_id, timeframe):
        """
        Return current OHLC for a specific market-id and timeframe or None.
        """
        if market_id in self._last_ohlc:
            if timeframe in self._last_ohlc[market_id]:
                return self._last_ohlc[market_id][timeframe]

        return None

    #
    # processing
    #

    def receiver(self, signal):
        """
        Notifiable listener.
        """ 
        if signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name != self._name:
                # only interested by the watcher of the same name
                return

            elif signal.signal_type not in [
                    Signal.SIGNAL_MARKET_LIST_DATA,]:
                return

            # signal of interest
            self._signals.append(signal)

    def pre_run(self):
        Terminal.inst().info("Running watcher %s..." % self._name)
        self.connect()

    def post_run(self):
        Terminal.inst().info("Joining watcher %s..." % self._name)
        self.disconnect()

    def post_update(self):
        pass

    def update(self):
        """
        Nothing by default by you must call at least update_from_tick.
        """
        return True

    @property
    def name(self):
        return self._name

    def find_author(self, author_id):
        return self._authors.get(str(author_id))

    @property
    def service(self):
        return self._service

    def command(self, command_type, data):
        """
        Some parts are mutexed some others are not.
        @todo some command are only display, so could be moved to a displayer, and command could only return an object
        """
        pass

    def pong(self, msg):
        # display watcher activity
        if self.connected:
            Terminal.inst().action("Watcher worker %s is alive %s" % (self._name, msg), view='content')
        else:
            Terminal.inst().action("Watcher worker %s is alive but waiting for (re)connection %s" % (self._name, msg), view='content')

    def fetch_market(self, market_id):
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

    def historical_data(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        """
        Async fetch the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Non zero time unit in second
        @param from_date date object
        @param to_date date object
        @param n Last n data
        """
        if timeframe <= 0:
            return

        if n_last:
            Database.inst().load_market_ohlc_last_n(self.service, self.name, market_id, timeframe, n_last)
        else:
            Database.inst().load_market_ohlc(self.service, self.name, market_id, timeframe, from_date, to_date)       

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        return None

    #
    # utils
    #

    def update_ohlc(self, market_id, tf, ts, bid, ofr, volume):
        """
        Update the current OHLC or create a new one, and save them.
        @param market_id str Unique market identifier
        @param tf float Timeframe (normalized timeframe at second)
        @param ts float Timestamp of the update or of the tick/trade
        @param bid float Bid price.
        @param ofr float Offer/ask price.
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

            if bid:
                ohlc.set_bid(bid)
            if ofr:
                ohlc.set_ofr(ofr)

            last_ohlc_by_timeframe[tf] = ohlc

        if ts >= ohlc.timestamp:
            # update the current OHLC
            if volume:
                ohlc._volume += volume

            if bid:
                if not ohlc._bid_open:
                    ohlc.set_bid(bid)

                # update bid prices
                ohlc._bid_high = max(ohlc._bid_high, bid)
                ohlc._bid_low = min(ohlc._bid_low, bid)

                # potential close
                ohlc._bid_close = bid

            if ofr:
                if not ohlc.ofr_open:
                    ohlc.set_ofr(ofr)

                # update ofr prices
                ohlc._ofr_high = max(ohlc._ofr_high, ofr)
                ohlc._ofr_low = min(ohlc._ofr_low, ofr)

                # potential close
                ohlc._ofr_close = ofr

        # stored timeframes only
        if ended_ohlc and (tf in self.STORED_TIMEFRAMES):
            Database.inst().store_market_ohlc((
                self.name, market_id, int(ended_ohlc.timestamp*1000), tf,
                ended_ohlc.bid_open, ended_ohlc.bid_high, ended_ohlc.bid_low, ended_ohlc.bid_close,
                ended_ohlc.ofr_open, ended_ohlc.ofr_high, ended_ohlc.ofr_low, ended_ohlc.ofr_close,
                ended_ohlc.volume))

        return ohlc

    def update_from_tick(self):
        """
        During update processing, update currently opened candles.
        Then notify a signal if a ohlc is generated (and closed).
        """
        for market_id in self._watched_instruments:
            last_ohlc_by_timeframe = self._last_ohlc.get(market_id)
            if not last_ohlc_by_timeframe:
                continue

            for tf, _ohlc in last_ohlc_by_timeframe.items():
                # for closing candles, generate them
                ohlc = self.update_ohlc(market_id, tf, time.time(), None, None, None)
                if ohlc:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, ohlc))

    def fetch_and_generate(self, market_id, timeframe, n_last=1, cascaded=None):
        """
        For initial fetching of the current OHLC.
        """
        if timeframe > 0 and timeframe not in self.GENERATED_TF:
            logger.error("Timeframe %i is not allowed !" % (timeframe,))
            return

        generators = []
        from_tf = timeframe

        if not market_id in self._last_ohlc:
            self._last_ohlc[market_id] = {}

        # compute a from date
        today = datetime.now().astimezone(UTC())
        from_date = today

        # for n last, minus a delta time
        if timeframe == Instrument.TF_MONTH:
            from_date = today - timedelta(months=int(timeframe/Instrument.TF_MONTH)*n_last)
        else:
            from_date = today - timedelta(seconds=int(timeframe)*n_last)

        to_date = today

        last_ohlcs = {}

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

        for data in self.fetch_candles(market_id, timeframe, from_date, to_date, None):
            # store (int timestamp ms, str open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
            Database.inst().store_market_ohlc((
                self.name, market_id, data[0], int(timeframe),
                data[1], data[2], data[3], data[4],
                data[5], data[6], data[7], data[8],
                data[9]))

            candle = Candle(float(data[0]) * 0.001, timeframe)

            candle.set_bid_ohlc(float(data[1]), float(data[2]), float(data[3]), float(data[4]))
            candle.set_ofr_ohlc(float(data[5]), float(data[6]), float(data[7]), float(data[8]))

            candle.set_volume(float(data[9]))

            if candle.timestamp >= Instrument.basetime(timeframe, time.time()):
                candle.set_consolidated(False)  # current

            last_ohlcs[timeframe].append(candle)

            # only the last
            self._last_ohlc[market_id][timeframe] = candle

            # generate higher candles
            for generator in generators:              
                candles = generator.generate_from_candles(last_ohlcs[generator.from_tf], False)
                if candles:
                    if not self._read_only:
                        for c in candles:
                            self.store_candle(market_id, generator.to_tf, c)

                    last_ohlcs[generator.to_tf].extend(candles)

                    # only the last as current
                    self._last_ohlc[market_id][generator.to_tf] = candles[-1]

                elif generator.current:
                    self._last_ohlc[market_id][generator.to_tf] = generator.current

                # remove consumed candles
                last_ohlcs[generator.from_tf] = []

            n += 1

        for k, ohlc in self._last_ohlc[market_id].items():
            if ohlc:
                ohlc.set_consolidated(False)

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        """
        Retrieve the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Time unit in second.
        @param from_date
        @param to_date
        @param n_last Last n data
        """
        pass

    def store_candle(self, market_id, timeframe, candle):
        Database.inst().store_market_ohlc((
            self.name, market_id, int(candle.timestamp*1000.0), int(timeframe),
            str(candle.bid_open), str(candle.bid_high), str(candle.bid_low), str(candle.bid_close),
            str(candle.ofr_open), str(candle.ofr_high), str(candle.ofr_low), str(candle.ofr_close),
            str(candle.volume)))
