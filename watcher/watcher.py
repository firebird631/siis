# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# watcher interface

import time
import collections

from common.runnable import Runnable
from common.utils import matching_symbols_set
from terminal.terminal import Terminal

from notifier.signal import Signal
from config import config
from database.database import Database

from instrument.instrument import Instrument, Candle


class Watcher(Runnable):
    """
    Watcher base class.
    """

    WATCHER_UNDEFINED = 0
    WATCHER_PRICE_AND_VOLUME = 1
    WATCHER_BUY_SELL_SIGNAL = 2
    WATCHER_ALL = 1|2

    # ohlc timeframes of interest for storage
    STORED_TIMEFRAMES = (
        Instrument.TF_MIN,
        Instrument.TF_5MIN,
        Instrument.TF_15MIN,
        Instrument.TF_HOUR,
        Instrument.TF_4HOUR,
        Instrument.TF_DAY,
        Instrument.TF_WEEK)

    def __init__(self, name, service, watcher_type):
        super().__init__("wt-%s" % (name,))

        self._name = name
        self._service = service
        self._authors = {}
        self._positions = {}
        self._watcher_type = watcher_type

        self._signals = collections.deque()

        self._available_instruments = set()  # all avalaibles instruments
        self._watched_instruments = set()    # watched instruments

        self._data_streams = {}
        self._read_only = service.read_only  # no db storage in read-only mode

        self._last_tick = {}  # last tick per market id
        self._last_ohlc = {}  # last ohlc per market id and then per timeframe

        # listen to its service
        self.service.add_listener(self)       

    @property
    def watcher_type(self):
        return self._watcher_type

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

    @property
    def has_prices_and_volumes(self):
        return self._watcher_type & Watcher.WATCHER_PRICE_AND_VOLUME == Watcher.WATCHER_PRICE_AND_VOLUME

    @property
    def has_buy_sell_signals(self):
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

    def update_markets_info(self, markets):
        """
        Update a given list of markets details sychronously.
        It only update the informational details of the market, NOT the price and related informations,
        but info like market expiry, price filters, fees.

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

    def __update_ohlc(self, ohlc, bid, ofr, volume):
        if volume:
            ohlc._volume += volume

        if bid:
            if not ohlc._bid_open:
                ohlc.set_bid_ohlc(bid, bid, bid, bid)

            # update bid prices
            ohlc._bid_high = max(ohlc._bid_high, bid)
            ohlc._bid_low = min(ohlc._bid_low, bid)

            # potential close
            ohlc._bid_close = bid

        if ofr:
            if not ohlc.ofr_open:
                ohlc.set_ofr_ohlc(ofr, ofr, ofr, ofr)

            # update ofr prices
            ohlc._ofr_high = max(ohlc._ofr_high, ofr)
            ohlc._ofr_low = min(ohlc._ofr_low, ofr)

            # potential close
            ohlc._ofr_close = ofr

    def update_ohlc(self, market_id, tf, ts, bid, ofr, volume):
        base_time = Instrument.basetime(ts, time.time())

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

        if ohlc and (ohlc.timestamp + tf <= base_time):
            # later tick data (laggy ?)
            if ts < base_time:
                # but after that next in laggy data will be ignored...
                # its not perfect in laggy cases for storage, but in live we can't deals we later data
                self.__update_ohlc(ohlc, bid, ofr, volume)

            # need to close the ohlc and to open a new one
            ohlc.set_consolidated(True)
            ended_ohlc = ohlc

            last_ohlc_by_timeframe[tf] = None
            ohlc = None

        if ohlc is None:
            # open a new one
            ohlc = Candle(base_time, tf)

            ohlc.set_consolidated(False)

            if bid:
                ohlc.set_bid_ohlc(bid, bid, bid, bid)
            if ofr:
                ohlc.set_ofr_ohlc(ofr, ofr, ofr, ofr)

            last_ohlc_by_timeframe[tf] = ohlc

        if ts >= ohlc.timestamp:
            self.__update_ohlc(ohlc, bid, ofr, volume)

        # stored timeframes only
        if ended_ohlc and (tf in self.STORED_TIMEFRAMES):
            # @todo REDIS cache too
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

            # bid = self._last_tick[market_id].bid
            # ofr = self._last_tick[market_id].ofr

            for tf, _ohlc in last_ohlc_by_timeframe.items():
                # for closing candles, generate them
                ohlc = self.update_ohlc(market_id, tf, time.time(), None, None, None)
                if ohlc:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, ohlc))
