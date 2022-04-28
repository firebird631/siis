# @date 2018-10-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# www.binance.com watcher implementation

from __future__ import annotations

from typing import Optional, List, Tuple

import time
import traceback
import math

from datetime import datetime

from watcher.watcher import Watcher
from common.signal import Signal

from connector.binance.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle

from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.binance')
exec_logger = logging.getLogger('siis.exec.watcher.binance')
error_logger = logging.getLogger('siis.error.watcher.binance')
traceback_logger = logging.getLogger('siis.traceback.watcher.binance')


class BinanceWatcher(Watcher):
    """
    Binance market watcher using REST + WS.

    @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md

    @todo Margin trading, get position from REST API + WS events.
    @todo Finish order book events.
    @todo Update base_exchange_rate as price change.
    @todo Once a market is not longer found (market update) we could remove it from watched list,
        and even have a special signal to strategy, and remove the subscriber, and markets data from watcher and trader

    @todo does the subscriptions renegotiated by the ws client at reconnection

    @note A single connection can listen to a maximum of 200 streams.
    @note WebSocket connections have a limit of 10 incoming messages per second.
    """

    BASE_QUOTE = 'BTC'
    USE_DEPTH_AS_TRADE = False  # Use depth best bid/ask in place of aggregated trade data (use a single stream)

    REV_TF_MAP = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '8h': 28800,
        '12h': 43200,
        '1d': 86400,
        '3d': 259200,
        '1w': 604800,
        '1M': 2592000
    }

    def __init__(self, service):
        super().__init__("binance.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, asks)

        self._account_data = {}
        self._symbols_data = {}
        self._tickers_data = {}

        self._last_trade_id = {}

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()    # cache for matching symbols

        self._tickers_handler = None       # WS all tickers
        self._book_tickers_handler = None  # WS all book tickers
        self._user_data_handler = None     # WS user data

    def connect(self):
        super().connect()

        with self._mutex:
            try:
                self._ready = False
                self._connecting = True

                identity = self.service.identity(self._name)

                if identity:
                    if not self._connector:
                        self._connector = Connector(
                            self.service,
                            identity.get('account-id', ""),
                            identity.get('api-key'),
                            identity.get('api-secret'),
                            identity.get('host'))
                    # else:
                    #     # to get a clean connection
                    #     self._connector.disconnect()

                    if not self._connector.connected or not self._connector.ws_connected:
                        self._connector.connect()

                    if self._connector and self._connector.connected:
                        #
                        # instruments
                        #

                        # get all products symbols
                        self._available_instruments = set()

                        instruments = self._connector.client.get_exchange_info().get('symbols', [])
                        configured_symbols = self.configured_symbols()
                        matching_symbols = self.matching_symbols_set(configured_symbols, [
                            instrument['symbol'] for instrument in instruments])

                        # cache them
                        self.__configured_symbols = configured_symbols
                        self.__matching_symbols = matching_symbols

                        # prefetch all markets data with a single request to avoid one per market
                        self.__prefetch_markets()

                        for instrument in instruments:
                            self._available_instruments.add(instrument['symbol'])

                        # all tickers and book tickers
                        # self._tickers_handler = self._connector.ws.start_ticker_socket(self.__on_ticker_arr_data)
                        # self._book_tickers_handler = self._connector.ws.start_book_ticker_socket(
                        #     self.__on_book_ticker_data)

                        # userdata
                        self._user_data_handler = self._connector.ws.start_user_socket(self.__on_user_data)

                        # retry the previous subscriptions
                        if self._watched_instruments:
                            logger.debug("%s subscribe to markets data stream..." % self.name)

                            pairs = []

                            for market_id in self._watched_instruments:
                                if market_id in self._available_instruments:
                                    pairs.append(market_id.lower())

                            try:
                                self._connector.ws.subscribe_public(
                                    subscription='ticker',  # 'miniTicker'
                                    pair=pairs,
                                    callback=self.__on_ticker_data
                                )

                                # ticker data gives best bid and ask price
                                # self._connector.ws.subscribe_public(
                                #     subscription='bookTicker',
                                #     pair=pairs,
                                #     callback=self.__on_book_ticker_data
                                # )

                                self._connector.ws.subscribe_public(
                                    subscription='aggTrade',
                                    pair=pairs,
                                    callback=self.__on_trade_data
                                )

                                # @todo order book

                            except Exception as e:
                                error_logger.error(repr(e))
                                traceback_logger.error(traceback.format_exc())

                        # and start ws manager if necessary
                        try:
                            self._connector.ws.start()
                        except RuntimeError:
                            logger.debug("%s WS already started..." % self.name)

                        # once market are init
                        self._ready = True
                        self._connecting = False

                        logger.debug("%s connection successes" % self.name)

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

                self._ready = False
                self._connecting = False
                self._connector = None

        if self._connector and self._connector.connected and self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

    def disconnect(self):
        super().disconnect()

        logger.debug("%s disconnecting..." % self.name)

        with self._mutex:
            try:
                if self._connector:
                    self._connector.disconnect()
                    self._connector = None

                    # reset WS handlers
                    self._tickers_handler = None
                    self._book_tickers_handler = None
                    self._user_data_handler = None

                self._ready = False
                self._connecting = False

                logger.debug("%s disconnected" % self.name)

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        return self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self) -> bool:
        return self._connector and self._connector.authenticated

    def pre_update(self):
        if not self._connecting and not self._ready:
            reconnect = False

            with self._mutex:
                if (not self._ready or self._connector is None or not self._connector.connected or
                        not self._connector.ws_connected):
                    # cleanup
                    self._ready = False
                    self._connector = None

                    reconnect = True

            if reconnect:
                time.sleep(2)
                self.connect()
                return

    #
    # instruments
    #

    def subscribe(self, market_id, ohlc_depths=None, tick_depth=None, order_book_depth=None):
        if market_id not in self.__matching_symbols:
            return False

        # live data
        symbol = market_id.lower()

        # fetch from source
        if self._initial_fetch:
            logger.info("%s prefetch for %s" % (self.name, market_id))

            if ohlc_depths:
                for timeframe, depth in ohlc_depths.items():
                    try:
                        if timeframe == Instrument.TF_1M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth, None)

                        elif timeframe == Instrument.TF_2M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth*2, None)

                        elif timeframe == Instrument.TF_3M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth*3, None)

                        elif timeframe == Instrument.TF_5M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth, None)

                        elif timeframe == Instrument.TF_10M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth*2, None)

                        elif timeframe == Instrument.TF_15M:
                            self.fetch_and_generate(market_id, Instrument.TF_15M, depth, None)

                        elif timeframe == Instrument.TF_30M:
                            self.fetch_and_generate(market_id, Instrument.TF_30M, depth, None)

                        elif timeframe == Instrument.TF_1H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth, None)

                        elif timeframe == Instrument.TF_2H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*2, Instrument.TF_2H)

                        elif timeframe == Instrument.TF_3H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*3, None)

                        elif timeframe == Instrument.TF_4H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth, None)

                        elif timeframe == Instrument.TF_6H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*6, None)

                        elif timeframe == Instrument.TF_8H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth*2, None)

                        elif timeframe == Instrument.TF_12H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth*3, None)

                        elif timeframe == Instrument.TF_1D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth, None)

                        elif timeframe == Instrument.TF_2D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth*2, None)

                        elif timeframe == Instrument.TF_3D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth*3, None)

                        elif timeframe == Instrument.TF_1W:
                            self.fetch_and_generate(market_id, Instrument.TF_1W, depth, None)

                        elif timeframe == Instrument.TF_MONTH:
                            self.fetch_and_generate(market_id, Instrument.TF_MONTH, depth, None)

                    except Exception as e:
                        error_logger.error(repr(e))

            if tick_depth:
                try:
                    self.fetch_ticks(market_id, tick_depth)
                except Exception as e:
                    error_logger.error(repr(e))

            with self._mutex:
                # one more watched instrument
                self.insert_watched_instrument(market_id, [0])

                # and start listening for this symbol (trade+depth)

                self._connector.ws.subscribe_public(
                    subscription='ticker',  # 'miniTicker'
                    pair=[symbol],
                    callback=self.__on_ticker_data
                )

                # ticker data gives best bid and ask price
                # self._connector.ws.subscribe_public(
                #     subscription='bookTicker',
                #     pair=[symbol],
                #     callback=self.__on_book_ticker_data
                # )

                # not used : ohlc (1m, 5m, 1h), prefer rebuild ourselves using aggregated trades
                # kline_data = ['{}@kline_{}'.format(symbol, '1m')]  # '5m' '1h'...

                self._connector.ws.subscribe_public(
                    subscription='aggTrade',
                    pair=[symbol],
                    callback=self.__on_trade_data
                )

                # if order_book_depth and order_book_depth in (10, 25, 100, 500, 1000):
                #     self._connector.ws.subscribe_public(
                #         subscription='depth',
                #         pair=[symbol],
                #         callback=self.__on_book_ticker_data
                #     )

                # no more than 10 messages per seconds on websocket
                time.sleep(0.1)

        return True

    def unsubscribe(self, market_id, timeframe):
        with self._mutex:
            if market_id in self._watched_instruments:
                instruments = self._available_instruments

                if market_id in instruments:
                    pair = [market_id.lower()]

                    # self._connector.ws.unsubscribe_public('miniTicker', pair)
                    self._connector.ws.unsubscribe_public('aggTrade', pair)
                    # self._connector.ws.unsubscribe_public('depth', pair)

                    self._watched_instruments.remove(market_id)

                    return True

    #
    # processing
    #

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, ready status to false before to retry a connection
            self._ready = False
            return False

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= BinanceWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
            try:
                self.update_markets_info()
                self._last_market_update = time.time()  # update in 4h
            except Exception as e:
                error_logger.error("update_markets_info %s" % str(e))
                self._last_market_update = time.time() - 300.0  # retry in 5 minutes

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0005)

    def post_run(self):
        super().post_run()

    def fetch_market(self, market_id):
        """
        Fetch and cache it. It rarely changes.
        """
        symbol = self._symbols_data.get(market_id)
        ticker = self._tickers_data.get(market_id)
        account = self._account_data

        market = None

        if symbol and ticker and account:
            market = Market(symbol['symbol'], symbol['symbol'])

            market.is_open = symbol['status'] == "TRADING"
            market.expiry = '-'

            base_asset = symbol['baseAsset']
            market.set_base(base_asset, base_asset, symbol['baseAssetPrecision'])

            quote_asset = symbol['quoteAsset']
            market.set_quote(quote_asset, symbol.get('quoteAssetUnit', quote_asset), symbol['quotePrecision'])

            # tick size at the base asset precision
            market.one_pip_means = math.pow(10.0, -symbol['baseAssetPrecision'])
            market.value_per_pip = 1.0
            market.contract_size = 1.0
            market.lot_size = 1.0

            # @todo add margin support
            market.margin_factor = 1.0

            size_limits = ["1.0", "0.0", "1.0"]
            notional_limits = ["1.0", "0.0", "0.0"]
            price_limits = ["0.0", "0.0", "0.0"]

            # size min/max/step
            for sym_filter in symbol["filters"]:
                if sym_filter['filterType'] == "LOT_SIZE":  # 'MARKET_LOT_SIZE'
                    size_limits = [sym_filter['minQty'], sym_filter['maxQty'], sym_filter['stepSize']]

                elif sym_filter['filterType'] == "MIN_NOTIONAL":
                    notional_limits[0] = sym_filter['minNotional']

                elif sym_filter['filterType'] == "PRICE_FILTER":
                    price_limits = [sym_filter['minPrice'], sym_filter['maxPrice'], sym_filter['tickSize']]

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(float(notional_limits[0]), 0.0, 0.0)

            market.unit_type = Market.UNIT_AMOUNT
            market.market_type = Market.TYPE_CRYPTO
            market.contract_type = Market.CONTRACT_SPOT

            market.trade = 0
            if symbol.get('isSpotTradingAllowed', False):
                market.trade |= Market.TRADE_ASSET
            if symbol.get('isMarginTradingAllowed', False):
                market.trade |= Market.TRADE_IND_MARGIN

            # @todo orders capacities
            # symbol['orderTypes'] in ['LIMIT', 'LIMIT_MAKER', 'MARKET', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT']
            # market.orders = 

            if symbol.get('ocoAllowed', False):
                market.orders |= Market.ORDER_ONE_CANCEL_OTHER

            market.maker_fee = account['makerCommission'] * 0.0001
            market.taker_fee = account['takerCommission'] * 0.0001

            # market.buyer_commission = account['buyerCommission']
            # market.seller_commission = account['sellerCommission']

            # only order book can give us bid/ask
            market.bid = float(ticker['price'])
            market.ask = float(ticker['price'])

            mid_price = float(ticker['price'])

            if quote_asset != self.BASE_QUOTE:
                if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                    market.base_exchange_rate = float(self._tickers_data.get(
                        quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                    market.base_exchange_rate = 1.0 / float(self._tickers_data.get(
                        self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
                else:
                    market.base_exchange_rate = 1.0
            else:
                market.base_exchange_rate = 1.0

            market.contract_size = 1.0 / mid_price
            market.value_per_pip = market.contract_size / mid_price

            # volume 24h

            # in client.get_ticker but cost is 40 for any symbols then wait it at all-tickers WS event
            # vol24_base = ticker24h('volume')
            # vol24_quote = ticker24h('quoteVolume')

            # notify for strategy
            self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, (market_id, market))

            # store the last market info to be used for backtesting
            Database.inst().store_market_info((
                self.name, market.market_id, market.symbol,
                market.market_type, market.unit_type, market.contract_type,  # type
                market.trade, market.orders,  # type
                market.base, market.base_display, market.base_precision,  # base
                market.quote, market.quote_display, market.quote_precision,  # quote
                market.expiry, int(market.last_update_time * 1000.0),  # expiry, timestamp
                str(market.lot_size), str(market.contract_size), str(market.base_exchange_rate),
                str(market.value_per_pip), str(market.one_pip_means), '-',
                *size_limits,
                *notional_limits,
                *price_limits,
                str(market.maker_fee), str(market.taker_fee),
                str(market.maker_commission), str(market.taker_commission))
            )

        return market

    def fetch_order_book(self, market_id):
        # get_orderbook_tickers
        # get_order_book(market_id)
        pass

    #
    # protected
    #

    def __prefetch_markets(self):
        symbols = self._connector.client.get_exchange_info().get('symbols', [])
        tickers = self._connector.client.get_all_tickers()

        self._account_data = self._connector.client.get_account()
        self._symbols_data = {}
        self._tickers_data = {}

        for symbol in symbols:
            self._symbols_data[symbol['symbol']] = symbol

        for ticker in tickers:
            self._tickers_data[ticker['symbol']] = ticker

    def __on_ticker_data(self, data):
        # market data instrument by symbol
        if type(data) is not dict:
            return

        event_type = data.get('e', "")
        if event_type != '24hrTicker':
            return

        symbol = data.get('s')
        if not symbol:
            return

        last_trade_id = data.get('L', 0)

        if last_trade_id != self._last_trade_id.get(symbol, 0):
            self._last_trade_id[symbol] = last_trade_id

            last_update_time = data['C'] * 0.001

            bid = float(data['b']) if data.get('b') else None
            ask = float(data['a']) if data.get('a') else None

            vol24_base = float(data['v']) if data['v'] else 0.0
            vol24_quote = float(data['q']) if data['q'] else 0.0

            # @todo compute base_exchange_rate
            # if quote_asset != self.BASE_QUOTE:
            #     if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
            #         market.base_exchange_rate = float(self._tickers_data.get(
            #             quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
            #     elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
            #         market.base_exchange_rate = 1.0 / float(self._tickers_data.get(
            #             self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
            #     else:
            #         market.base_exchange_rate = 1.0
            # else:
            #     market.base_exchange_rate = 1.0

            market_data = (symbol, last_update_time > 0, last_update_time, bid, ask,
                           None, None, None, vol24_base, vol24_quote)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_ticker_arr_data(self, data):
        # market data instrument by symbol
        if type(data) not in (list, tuple):
            return

        for ticker in data:
            if type(ticker) is not dict:
                continue

            if 's' not in ticker:
                continue

            symbol = ticker.get('s')
            if not symbol:
                continue

            last_trade_id = ticker.get('L', 0)

            if last_trade_id != self._last_trade_id.get(symbol, 0):
                self._last_trade_id[symbol] = last_trade_id

                last_update_time = ticker['C'] * 0.001

                # here we have best bid and ask price
                bid = float(ticker['b']) if ticker.get('b') else None
                ask = float(ticker['a']) if ticker.get('a') else None

                vol24_base = float(ticker['v']) if ticker['v'] else 0.0
                vol24_quote = float(ticker['q']) if ticker['q'] else 0.0

                # @todo compute base_exchange_rate
                # if quote_asset != self.BASE_QUOTE:
                #     if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                #         market.base_exchange_rate = float(self._tickers_data.get(
                #             quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                #     elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                #         market.base_exchange_rate = 1.0 / float(self._tickers_data.get(
                #             self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
                #     else:
                #         market.base_exchange_rate = 1.0
                # else:
                #     market.base_exchange_rate = 1.0

                market_data = (symbol, last_update_time > 0, last_update_time, bid, ask,
                               None, None, None, vol24_base, vol24_quote)

                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_book_ticker_data(self, data):
        if type(data) is not dict:
            return

        event_type = data.get('e', "")
        if event_type != 'bookTicker':
            return

        # market data instrument by symbol
        symbol = data.get('s')
        if not symbol:
            return

        # not available in futures but only for spot
        bid = float(data['b']) if data.get('b') else None  # B for qty
        ask = float(data['a']) if data.get('a') else None  # A for qty

        market_data = (symbol, None, None, bid, ask, None, None, None, None, None)
        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_multiplex_data(self, data):
        """
        Intercepts ticker all, depth for followed symbols.
        Klines are generated from tickers data. It is a preferred way to reduce network traffic and API usage.
        """
        if type(data) is not dict:
            return

        if not data.get('stream'):
            return

        if data['stream'].endswith('@aggTrade'):
            self.__on_trade_data(data['data'])
        elif data['stream'].endswith('@depth'):
            self.__on_depth_data(data['data'])
        elif data['stream'].endswith('@kline_'):
            self.__on_kline_data(data['data'])
        elif data['stream'].endswith('@ticker'):
            self.__on_ticker_data(data['data'])
        elif data['stream'].endswith('@bookTicker'):
            self.__on_book_ticker_data(data['data'])

    def __on_depth_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', "")
        if event_type != 'depthUpdate':
            return

        symbol = data.get('s')
        if not symbol:
            return

        # get bid/ask for market update from depth book
        last_update_time = data['T'] * 0.001

        if 'b' in data and data['b']:
            bid = float(data['b'][0][0])  # B for qty
        else:
            bid = None

        if 'a' in data and data['a']:
            ask = float(data['a'][0][0])  # A for qty
        else:
            ask = None

        market_data = (symbol, last_update_time > 0, last_update_time, bid, ask, None, None, None, None, None)
        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

        # # @todo using binance.DepthCache
        # if symbol not in self._depths:
        #     # initial snapshot of the order book from REST API
        #     initial = self._connector.client.get_order_book(symbol=symbol, limit=100)
        #
        #     bids = {}
        #     asks = {}
        #
        #     for bid in initial['bids']:
        #         bids[bid[0]] = bid[1]
        #
        #     for ask in initial['asks']:
        #         asks[ask[0]] = ask[1]
        #
        #     self._depths[symbol] = [initial.get('lastUpdateId', 0), bids, asks]
        #
        # depth = self._depths[symbol]
        #
        # # The first processed should have U <= lastUpdateId+1 AND u >= lastUpdateId+1
        # if data['u'] <= depth[0] or data['U'] >= depth[0]:
        #     # drop event if older than the last snapshot
        #     return
        #
        # if data['U'] != depth[0] + 1:
        #     logger.warning("Watcher %s, there is a gap into depth data for symbol %s" % (self._name, symbol))
        #
        # for bid in data['b']:
        #     # if data['U'] <= depth[0]+1 and data['u'] >= depth[0]+1:
        #     if bid[1] == 0:
        #         del depth[1][bid[0]]  # remove at price
        #     else:
        #         depth[2][bid[0]] = bid[1]  # price : volume
        #
        # for ask in data['a']:
        #     if ask[1] == 0:
        #         del depth[2][ask[0]]
        #     else:
        #         depth[2][ask[0]] = ask[1]
        #
        # # last processed id, next must be +1
        # depth[0] = data['u']
        #
        # # self.service.notify(Signal.SIGNAL_ORDER_BOOK, self.name, (symbol, depth[1], depth[2]))

    def __on_trade_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', "")
        if event_type == "aggTrade":
            symbol = data.get('s')

            if not symbol:
                return

            trade_time = data['T'] * 0.001

            # trade_id = data['t']
            buyer_maker = -1 if data['m'] else 1

            price = float(data['p'])
            vol = float(data['q'])

            # @todo from ticker ask - bid
            spread = 0.0

            tick = (trade_time, price, price, price, vol, buyer_maker)

            self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (symbol, tick))

            if self._store_trade:
                Database.inst().store_market_trade((self.name, symbol, int(data['T']), data['p'], data['p'], data['p'],
                                                    data['q'], buyer_maker))

            for tf in Watcher.STORED_TIMEFRAMES:
                # generate candle per timeframe
                candle = None

                with self._mutex:
                    candle = self.update_ohlc(symbol, tf, trade_time, price, spread, vol)

                if candle is not None:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

    def __on_kline_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', '')
        if event_type == 'kline':
            k = data['k']

            symbol = k['s']
            timestamp = k['t'] * 0.001

            tf = self.REV_TF_MAP[k['i']]

            candle = Candle(timestamp, tf)

            candle.set_ohlc(
              float(k['o']),
              float(k['h']),
              float(k['l']),
              float(k['c']))

            spread = 0.0

            candle.set_spread(spread)
            candle.set_volume(float(k['v']))
            candle.set_consolidated(k['x'])

            self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

            if self._store_ohlc and k['x']:
                # write only consolidated candles. values are string its perfect
                Database.inst().store_market_ohlc((
                    self.name, symbol, int(k['t']), tf,
                    k['o'], k['h'], k['l'], k['c'],
                    spread,
                    k['v']))

    def __on_user_data(self, data):
        """
        @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md#web-socket-payloads
        """
        if type(data) is not dict:
            return

        event_type = data.get('e', '')

        if event_type == 'executionReport':
            exec_logger.info("binance.com executionReport %s" % str(data))

            symbol = data.get('s')
            if not symbol:
                return

            event_timestamp = float(data['E']) * 0.001
            cid = data['c']

            if data['x'] == 'REJECTED':  # and data['X'] == '?':
                client_order_id = str(data['c'])
                reason = ""

                if data['r'] == 'INSUFFICIENT_BALANCE':
                    reason = 'insufficient balance'

                self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (symbol, client_order_id))

            elif (data['x'] == 'TRADE') and (data['X'] == 'FILLED' or data['X'] == 'PARTIALLY_FILLED'):
                order_id = str(data['i'])
                client_order_id = str(data['c'])

                timestamp = float(data['T']) * 0.001  # transaction time

                price = None
                stop_price = None

                if data['o'] == 'LIMIT':
                    order_type = Order.ORDER_LIMIT
                    price = float(data['p'])

                elif data['o'] == 'MARKET':
                    order_type = Order.ORDER_MARKET

                elif data['o'] == 'STOP_LOSS':
                    order_type = Order.ORDER_STOP
                    stop_price = float(data['P'])

                elif data['o'] == 'STOP_LOSS_LIMIT':
                    order_type = Order.ORDER_STOP_LIMIT
                    price = float(data['p'])
                    stop_price = float(data['P'])

                elif data['o'] == 'TAKE_PROFIT':
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(data['P'])

                elif data['o'] == 'TAKE_PROFIT_LIMIT':
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(data['p'])
                    stop_price = float(data['P'])

                elif data['o'] == 'LIMIT_MAKER':
                    order_type = Order.ORDER_LIMIT
                    price = float(data['p'])

                else:
                    order_type = Order.ORDER_LIMIT

                if data['f'] == 'GTC':
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif data['f'] == 'IOC':
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif data['f'] == 'FOK':
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                order = {
                    'id': order_id,
                    'symbol': symbol,
                    'type': order_type,
                    'trade-id': str(data['t']),
                    'direction': Order.LONG if data['S'] == 'BUY' else Order.SHORT,
                    'timestamp': timestamp,
                    'quantity': float(data['q']),
                    'price': price,
                    'stop-price': stop_price,
                    'exec-price': float(data['L']),
                    'filled': float(data['l']),
                    'cumulative-filled': float(data['z']),
                    'quote-transacted': float(data['Y']),  # similar as float(data['Z']) for cumulative
                    'stop-loss': None,
                    'take-profit': None,
                    'time-in-force': time_in_force,
                    'commission-amount': float(data['n']),
                    'commission-asset': data['N'],
                    'maker': data['m'],   # trade execution over or counter the market : true if maker, false if taker
                    'fully-filled': data['X'] == 'FILLED'  # fully filled status else its partially
                }

                self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

            elif data['x'] == 'NEW' and data['X'] == 'NEW':
                order_id = str(data['i'])
                timestamp = float(data['O']) * 0.001  # order creation time
                client_order_id = str(data['c'])

                iceberg_qty = float(data['F'])

                price = None
                stop_price = None

                if data['o'] == 'LIMIT':
                    order_type = Order.ORDER_LIMIT
                    price = float(data['p'])

                elif data['o'] == 'MARKET':
                    order_type = Order.ORDER_MARKET

                elif data['o'] == 'STOP_LOSS':
                    order_type = Order.ORDER_STOP
                    stop_price = float(data['P'])

                elif data['o'] == 'STOP_LOSS_LIMIT':
                    order_type = Order.ORDER_STOP_LIMIT
                    price = float(data['p'])
                    stop_price = float(data['P'])

                elif data['o'] == 'TAKE_PROFIT':
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(data['P'])

                elif data['o'] == 'TAKE_PROFIT_LIMIT':
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(data['p'])
                    stop_price = float(data['P'])

                elif data['o'] == 'LIMIT_MAKER':
                    order_type = Order.ORDER_LIMIT
                    price = float(data['p'])

                else:
                    order_type = Order.ORDER_LIMIT

                if data['f'] == 'GTC':
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif data['f'] == 'IOC':
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif data['f'] == 'FOK':
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                order = {
                    'id': order_id,
                    'symbol': symbol,
                    'direction': Order.LONG if data['S'] == 'BUY' else Order.SHORT,
                    'type': order_type,
                    'timestamp': event_timestamp,
                    'quantity': float(data['q']),
                    'price': price,
                    'stop-price': stop_price,
                    'time-in-force': time_in_force,
                    'stop-loss': None,
                    'take-profit': None
                }

                self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (symbol, order, client_order_id))

            elif data['x'] == 'CANCELED' and data['X'] == 'CANCELED':
                order_id = str(data['i'])
                org_client_order_id = data['C']

                self.service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (symbol, order_id, org_client_order_id))

            elif data['x'] == 'EXPIRED' and data['X'] == 'EXPIRED':
                order_id = str(data['i'])

                self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (symbol, order_id, ""))

            elif data['x'] == 'REPLACED' or data['X'] == 'REPLACED':
                pass  # nothing to do (currently unused)

        elif event_type == 'outboundAccountInfo':
            event_timestamp = float(data['E']) * 0.001

            # balances
            for balance in data['B']:
                asset_name = balance['a']
                free = balance['f']
                locked = balance['l']

                # asset updated
                self.service.notify(Signal.SIGNAL_ASSET_UPDATED, self.name, (asset_name, float(locked), float(free)))

    #
    # misc
    #

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        try:
            d = self.connector.price_for_at(market_id, timestamp)
            return (float(d[0][1]) + float(d[0][4]) + float(d[0][3])) / 3.0
        except Exception as e:
            logger.error("Cannot found price history for %s at %s" % (
                market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
            return None

    def update_markets_info(self):
        """
        Update market info.
        """
        self.__prefetch_markets()

        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market is None:
                # can be a removed market, signal its closed
                market_data = (market_id, False, time.time(), None, None, None, None, None, None, None)

            elif market.is_open:
                # market exists and tradeable
                market_data = (
                    market_id, market.is_open, market.last_update_time, market.bid, market.ask,
                    market.base_exchange_rate, market.contract_size, market.value_per_pip,
                    market.vol24h_base, market.vol24h_quote)
            else:
                # market exists but closed
                market_data = (market_id, market.is_open, market.last_update_time,
                               None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def fetch_trades(self, market_id: str, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None,
                     n_last: Optional[int] = None) -> List[Tuple[float, float, float, float, float, float]]:

        trades = []

        try:
            trades = self._connector.client.aggregate_trade_iter(market_id,
                                                                 start_str=int(from_date.timestamp() * 1000),
                                                                 end_str=int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Watcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            yield trade['T'], trade['p'], trade['p'], trade['p'], trade['q'], -1 if trade['m'] else 1

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        TF_MAP = {
            60: '1m',
            180: '3m',
            300: '5m',
            900: '15m',
            1800: '30m',
            3600: '1h',
            7200: '2h',
            14400: '4h',
            21600: '6h',
            28800: '8h',
            43200: '12h',
            86400: '1d',
            259200: '3d',
            604800: '1w',
            2592000: '1M'
        }

        if timeframe not in TF_MAP:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        tf = TF_MAP[timeframe]

        try:
            candles = self._connector.client.get_historical_klines(market_id, tf,
                                                                   int(from_date.timestamp() * 1000),
                                                                   int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s (%s)" % (self.name, tf, market_id, str(e)))

        count = 0
        
        for candle in candles:
            count += 1
            # (timestamp, open, high, low, close, spread, volume)
            yield candle[0], candle[1], candle[2], candle[3], candle[4], 0.0, candle[5]
