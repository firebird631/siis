# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# www.ftx.com futures watcher implementation

from __future__ import annotations

from typing import Optional, List, Tuple

import time
import traceback

from datetime import datetime

from common.utils import decimal_place, UTC
from watcher.watcher import Watcher
from common.signal import Signal

from connector.ftx.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument

from database.database import Database

import logging

logger = logging.getLogger('siis.watcher.ftxfutures')
exec_logger = logging.getLogger('siis.exec.watcher.ftxfutures')
error_logger = logging.getLogger('siis.error.watcher.ftxfutures')
traceback_logger = logging.getLogger('siis.traceback.watcher.ftxfutures')


class FTXFuturesWatcher(Watcher):
    """
    FTX perpetual futures market watcher using REST + WS.
    It is possible to adapt to support for inverse perpetuals.

    @todo Implement order, account data, user WS
    @todo Implement unsubscribe method
    """

    SYMBOL_SUFFIX = "PERP"  # ...
    BASE_QUOTE = 'USD'  # BTC
    USE_DEPTH_AS_TRADE = False  # Use depth best bid/ask in place of aggregated trade data (use a single stream)

    def __setup_ws_state(self):
        return {
            'status': "offline",
            'timestamp': 0.0,
            'subscribed': False,
            'lost': False,
            'retry': 0.0
        }

    def __reset_ws_state(self, ws):
        """Reset the states of a WS connection watcher."""
        ws['status'] = "offline"
        ws['timestamp'] = 0.0
        ws['subscribed'] = False
        ws['lost'] = False
        ws['retry'] = 0.0

    def __check_reconnect(self, ws):
        """Return True if a reconnection in needed."""
        # if ws['lost']:
        #     return True

        # 15 seconds during maintenance, 5 the rest of the time (post_only, cancel_only, online, offline)
        delay = 15.0 if self.maintenance else 5.0

        # above a delay without activity then reconnect
        if ws['timestamp'] > 0.0 and time.time() - ws['timestamp'] > delay:
            # if maintenance need to wait 5 sec before try to reconnect
            # if ws['status'] == "maintenance" and ws['retry'] <= 0.0:
            #     ws['retry'] = time.time() + 5.0

            return True

        return False

    def __reconnect_ws(self, ws, callback, name):
        # if ws['retry'] > 0.0 and time.time() < ws['retry']:
        #     return

        with self._mutex:
            try:
                self._connector.ws.stop_socket(name)
                self.__reset_ws_state(ws)

                # try now, if fail it will retry later
                ws['timestamp'] = time.time()

                pairs = []
                instruments = self._available_instruments

                for market_id in self._watched_instruments:
                    if market_id in instruments:
                        pairs.append(market_id)

                for pair in pairs:
                    try:
                        self._connector.ws.subscribe_public(
                            subscription=name,
                            pair=[pair],
                            callback=callback)
                    except Exception as e:
                        error_logger.error(repr(e))
                        traceback_logger.error(traceback.format_exc())

                logger.debug("%s subscribe %s to markets data stream..." % (self.name, name))
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    def __reconnect_user_ws(self):
        # if self._ws_fills_data['retry'] > 0.0 and time.time() < self._ws_fills_data['retry']:
        #     return
        # if self._ws_orders_data['retry'] > 0.0 and time.time() < self._ws_orders_data['retry']:
        #     return

        with self._mutex:
            try:
                self._connector.ws.stop_private_socket('fills')
                self._connector.ws.stop_private_socket('orders')

                # error retrieving the token, retry later
                self._ws_fills_data['timestamp'] = time.time()
                self._ws_orders_data['timestamp'] = time.time()

                ws_token = self._connector.get_ws_token()

                if ws_token:
                    self.__reset_ws_state(self._ws_fills_data)
                    self.__reset_ws_state(self._ws_orders_data)

                    self._connector.ws.subscribe_private(
                        token=ws_token,
                        subscription='fills',
                        callback=self.__on_fills_data)

                    self._connector.ws.subscribe_private(
                        token=ws_token,
                        subscription='orders',
                        callback=self.__on_orders_data)

                    logger.debug("%s subscribe to user data stream..." % self.name)
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    def __init__(self, service):
        super().__init__("ftxfutures.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, asks)

        self._account_data = {}
        self._symbols_data = {}

        self._last_trade_id = {}

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()  # cache for matching symbols

        # user WS
        self._ws_fills_data = self.__setup_ws_state()
        self._ws_orders_data = self.__setup_ws_state()

        # public WS
        self._ws_ticker_data = self.__setup_ws_state()
        self._ws_trade_data = self.__setup_ws_state()
        self._ws_orderbook_data = self.__setup_ws_state()

    def connect(self):
        super().connect()

        with self._mutex:
            try:
                self._ready = False
                self._connecting = True

                identity = self.service.identity(self._name)

                # user WS
                self.__reset_ws_state(self._ws_fills_data)
                self.__reset_ws_state(self._ws_orders_data)

                # public WS
                self.__reset_ws_state(self._ws_ticker_data)
                self.__reset_ws_state(self._ws_trade_data)
                self.__reset_ws_state(self._ws_orderbook_data)

                if identity:
                    if not self._connector:
                        self._connector = Connector(
                            self.service,
                            identity.get('account-id', ""),
                            identity.get('api-key'),
                            identity.get('api-secret'),
                            identity.get('host'))
                    else:
                        # to get a clean connection
                        self._connector.disconnect()

                    if not self._connector.connected or not self._connector.ws_connected:
                        self._connector.connect()

                    if self._connector and self._connector.connected:
                        # get all products symbols
                        self._available_instruments = set()

                        instruments = self._connector.client.get_markets()

                        # filter only spot markets
                        filtered_instr = []
                        for instrument in instruments:
                            # only standard spot markets
                            if instrument.get('type') != 'future':
                                continue

                            # only perpetual
                            if instrument.get('futureType') != 'perpetual':
                                continue

                            if self.SYMBOL_SUFFIX not in instrument.get('name', ""):
                                continue

                            filtered_instr.append(instrument)

                        instruments = filtered_instr

                        configured_symbols = self.configured_symbols()
                        matching_symbols = self.matching_symbols_set(configured_symbols, [
                            instrument['name'] for instrument in instruments])

                        # cache them
                        self.__configured_symbols = configured_symbols
                        self.__matching_symbols = matching_symbols

                        # prefetch all markets data with a single request to avoid one per market
                        self.__prefetch_markets()

                        for instrument in instruments:
                            self._available_instruments.add(instrument['name'])

                        # and start ws manager if necessary
                        try:
                            # self._connector.ws.connect()
                            self._connector.ws.start()
                        except RuntimeError:
                            logger.debug("%s WS already started..." % self.name)

                        # user data only in real mode
                        if not self.service.paper_mode:
                            ws_token = self._connector.get_ws_token()

                            if ws_token:
                                self._connector.ws.subscribe_private(
                                    token=ws_token,
                                    subscription='fills',
                                    callback=self.__on_fills_data)

                                self._connector.ws.subscribe_private(
                                    token=ws_token,
                                    subscription='orders',
                                    callback=self.__on_orders_data)
                        else:
                            self._ws_fills_data['timestamp'] = time.time()
                            self._ws_orders_data['timestamp'] = time.time()

                        # retry the previous subscriptions
                        if self._watched_instruments:
                            logger.debug("%s subscribe to markets data stream..." % self.name)

                            pairs = []

                            for market_id in self._watched_instruments:
                                if market_id in self._available_instruments:
                                    pairs.append(market_id)

                            for pair in pairs:
                                try:
                                    self._connector.ws.subscribe_public(
                                        subscription='ticker',
                                        pair=[pair],
                                        callback=self.__on_ticker_data)

                                    self._connector.ws.subscribe_public(
                                        subscription='trades',
                                        pair=[pair],
                                        callback=self.__on_trade_data)

                                    # @todo order book

                                    # no more than 10 messages per seconds on websocket
                                    time.sleep(0.2)

                                except Exception as e:
                                    error_logger.error(repr(e))
                                    traceback_logger.error(traceback.format_exc())

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

                self._ready = False
                self._connecting = False

                self.stream_connection_status(False)

                logger.debug("%s disconnected" % self.name)

            except Exception as e:
                error_logger.error(repr(e))
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

    @property
    def maintenance(self) -> bool:
        return False

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

        # fetch from source
        if self._initial_fetch:
            logger.info("%s prefetch for %s" % (self.name, market_id))

            if ohlc_depths:
                for timeframe, depth in ohlc_depths.items():
                    try:
                        if timeframe == Instrument.TF_1M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth, None)

                        elif timeframe == Instrument.TF_2M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth * 2, Instrument.TF_2M)

                        elif timeframe == Instrument.TF_3M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth * 3, Instrument.TF_3M)

                        elif timeframe == Instrument.TF_5M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth, None)

                        elif timeframe == Instrument.TF_10M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth * 2, Instrument.TF_10M)

                        elif timeframe == Instrument.TF_15M:
                            self.fetch_and_generate(market_id, Instrument.TF_15M, depth, None)

                        elif timeframe == Instrument.TF_30M:
                            self.fetch_and_generate(market_id, Instrument.TF_15M, depth * 2, Instrument.TF_30M)

                        elif timeframe == Instrument.TF_1H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth, None)

                        elif timeframe == Instrument.TF_2H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth * 2, Instrument.TF_2H)

                        elif timeframe == Instrument.TF_3H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth * 3, Instrument.TF_3H)

                        elif timeframe == Instrument.TF_4H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth, None)

                        elif timeframe == Instrument.TF_6H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth * 6, Instrument.TF_6H)

                        elif timeframe == Instrument.TF_8H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth * 2, Instrument.TF_8H)

                        elif timeframe == Instrument.TF_12H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth * 3, Instrument.TF_12H)

                        elif timeframe == Instrument.TF_1D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth, None)

                        elif timeframe == Instrument.TF_2D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth * 2, Instrument.TF_2D)

                        elif timeframe == Instrument.TF_3D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth * 3, Instrument.TF_3D)

                        elif timeframe == Instrument.TF_1W:
                            self.fetch_and_generate(market_id, Instrument.TF_1W, depth, None)

                        elif timeframe == Instrument.TF_MONTH:
                            self.fetch_and_generate(market_id, Instrument.TF_MONTH, depth, None)

                        time.sleep(0.5)  # no more than 2 call per second

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

            # live data
            pair = [market_id]

            # and start listening for this symbol (trade+depth)
            self._connector.ws.subscribe_public(
                subscription='ticker',
                pair=pair,
                callback=self.__on_ticker_data)

            self._connector.ws.subscribe_public(
                subscription='trades',
                pair=pair,
                callback=self.__on_trade_data)

            # no more than 10 messages per seconds on websocket
            time.sleep(0.1)

        return True

    def unsubscribe(self, market_id, timeframe):
        with self._mutex:
            if market_id in self._watched_instruments:
                instruments = self._available_instruments

                if market_id in instruments:
                    pair = [market_id]

                    self._connector.ws.unsubscribe_public('ticker', pair)
                    self._connector.ws.unsubscribe_public('trade', pair)

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

        # disconnected for user socket in real mode, and auto-reconnect failed
        if not self.service.paper_mode:
            if self.__check_reconnect(self._ws_fills_data) or self.__check_reconnect(self._ws_orders_data):
                # logger.debug("%s reconnecting to user trades and user orders data stream..." % self.name)
                self.__reconnect_user_ws()

        # disconnected for a public socket, and auto-reconnect failed
        if self.__check_reconnect(self._ws_ticker_data):
            # logger.debug("%s reconnecting to tickers data stream..." % self.name)
            self.__reconnect_ws(self._ws_ticker_data, self.__on_ticker_data, 'ticker')

        if self.__check_reconnect(self._ws_trade_data):
            # logger.debug("%s reconnecting to trades data stream..." % self.name)
            self.__reconnect_ws(self._ws_trade_data, self.__on_trade_data, 'trade')

        # if self.__check_reconnect(self._ws_orderbook_data):
        #     # logger.debug("%s reconnecting to order book data stream..." % self.name)
        #     self.__reconnect_ws(self._ws_orderbook_data, self.__on_book_ticker_data, 'orderbook')

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= FTXFuturesWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
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
        account = self._account_data

        market = None

        if symbol:
            market = Market(symbol['name'], symbol['name'])

            market.is_open = symbol['enabled']
            market.expiry = '-'

            base_asset = symbol['underlying']
            market.set_base(base_asset, base_asset, decimal_place(symbol['sizeIncrement']))

            quote_asset = "USD"  # if symbol['futureType'] == 'perpetual' else "USD"
            market.set_quote(quote_asset, quote_asset, decimal_place(symbol['priceIncrement']))

            # tick size at the base asset precision
            market.one_pip_means = symbol['sizeIncrement']
            market.value_per_pip = 1.0
            market.contract_size = 1.0
            market.lot_size = 1.0

            market.margin_factor = 1.0 / account.get('leverage', 10.0)

            size_limits = ["1.0", "0.0", "1.0"]
            notional_limits = ["1.0", "0.0", "0.0"]
            price_limits = ["0.0", "0.0", "0.0"]

            # size min/max/step
            size_limits[0] = str(symbol['minProvideSize'])
            size_limits[2] = str(symbol['sizeIncrement'])
            notional_limits[0] = str(symbol['minProvideSize'])
            price_limits[2] = str(symbol['priceIncrement'])

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(float(notional_limits[0]), 0.0, 0.0)

            market.unit_type = Market.UNIT_AMOUNT
            market.market_type = Market.TYPE_CRYPTO
            market.contract_type = Market.CONTRACT_FUTURE

            market.trade = 0
            if not symbol.get('restricted', False):
                market.trade = Market.TRADE_MARGIN | Market.TRADE_IND_MARGIN

            # @todo orders capacities
            # symbol['orderTypes'] in ['LIMIT', 'LIMIT_MAKER', 'MARKET', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT']
            # market.orders =

            market.maker_fee = account['makerFee'] if account else 0.0002
            market.taker_fee = account['takerFee'] if account else 0.0005

            # only order book can give us bid/ask
            market.bid = float(symbol['bid'])
            market.ask = float(symbol['ask'])

            mid_price = float(symbol['price'])  # or last

            if quote_asset != self.BASE_QUOTE:
                if self._symbols_data.get("%s_%s" % (quote_asset, self.SYMBOL_SUFFIX)):
                    market.base_exchange_rate = float(self._symbols_data.get(
                        "%s_%s" % (quote_asset, self.SYMBOL_SUFFIX), {'price', '1.0'})['price'])
                elif self._symbols_data.get("%s_%s" % (self.BASE_QUOTE, self.SYMBOL_SUFFIX)):
                    market.base_exchange_rate = 1.0 / float(self._symbols_data.get(
                        "%s_%s" % (self.BASE_QUOTE, self.SYMBOL_SUFFIX), {'price', '1.0'})['price'])
                else:
                    market.base_exchange_rate = 1.0
            else:
                market.base_exchange_rate = 1.0

            market.contract_size = 1.0 / mid_price
            market.value_per_pip = market.contract_size / mid_price

            # volume 24h

            # in client.get_ticker but cost is 40 for any symbols then wait it at all-tickers WS event
            vol24_base = symbol.get('quoteVolume24h', 0.0)
            vol24_quote = symbol.get('volumeUsd24h', 0.0)

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

    @staticmethod
    def parse_datetime(date_str):
        if '.' in date_str:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f+00:00').replace(tzinfo=UTC()).timestamp()
        else:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S+00:00').replace(tzinfo=UTC()).timestamp()

    def __prefetch_markets(self):
        symbols = self._connector.client.get_markets()

        self._account_data = self._connector.client.get_account_info()
        self._symbols_data = {}

        for symbol in symbols:
            self._symbols_data[symbol['name']] = symbol

    def __on_ticker_data(self, message):
        # market data instrument by symbol
        msg_type = message.get('type')
        if msg_type == 'subscribed':
            self._ws_ticker_data['timestamp'] = time.time()
            self._ws_ticker_data['subscribed'] = True
            logger.debug("ticker data subscriptionStatus : subscribed to %s" % message.get('market'))

            return

        elif msg_type == 'unsubscribed':
            self._ws_ticker_data['timestamp'] = time.time()
            self._ws_ticker_data['subscribed'] = False
            logger.debug("ticker data subscriptionStatus : unsubscribed from %s" % message.get('market'))

            return

        elif msg_type == 'info':
            if message.get('code', 0) == 20001:
                # need reconnect
                self._ws_ticker_data['status'] = "offline"
                self._ws_ticker_data['lost'] = True

                return

        elif msg_type == 'error':
            error_logger.error(message)

            error_logger.error("ticker data subscriptionStatus : %s - %s" % (message.get('code'), message.get('msg')))

        if message.get('channel') != 'ticker':
            return

        # last update timestamp
        self._ws_ticker_data['timestamp'] = time.time()

        symbol = message.get('market')
        if not symbol:
            return

        # last_trade_id = 0
        data = message.get('data', [])
        if not data:
            return

        last_update_time = data['time']

        bid = data.get('bid')
        ask = data.get('ask')

        # vol24_base = data['v'] if data['v'] else 0.0
        # vol24_quote = data['q'] if data['q'] else 0.0
        vol24_base = 0.0
        vol24_quote = 0.0

        # @todo compute base_exchange_rate
        # if quote_asset != self.BASE_QUOTE:
        #     if self._symbols_data.get("%s_%s" % (quote_asset, self.SYMBOL_SUFFIX)):
        #         market.base_exchange_rate = float(self._symbols_data.get(
        #             "%s_%s" % (quote_asset, self.SYMBOL_SUFFIX), {'price', '1.0'})['price'])
        #     elif self._symbols_data.get(self.BASE_QUOTE, self.SYMBOL_SUFFIX)):
        #         market.base_exchange_rate = 1.0 / float(self._symbols_data.get(
        #             self.BASE_QUOTE, self.SYMBOL_SUFFIX), {'price', '1.0'})['price'])
        #     else:
        #         market.base_exchange_rate = 1.0
        # else:
        #     market.base_exchange_rate = 1.0

        market_data = (symbol, last_update_time > 0, last_update_time, bid, ask,
                       None, None, None, vol24_base, vol24_quote)

        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_trade_data(self, message):
        # market data instrument by symbol
        if type(message) is not dict:
            return

        msg_type = message.get('type')
        if msg_type == 'subscribed':
            self._ws_trade_data['timestamp'] = time.time()
            self._ws_trade_data['subscribed'] = True
            logger.debug("trade data subscriptionStatus : subscribed to %s" % message.get('market'))

            return

        elif msg_type == 'unsubscribed':
            self._ws_trade_data['timestamp'] = time.time()
            self._ws_trade_data['subscribed'] = False
            logger.debug("trade data subscriptionStatus : unsubscribed from %s" % message.get('market'))

            return

        elif msg_type == 'info':
            if message.get('code', 0) == 20001:
                # need reconnect
                self._ws_ticker_data['status'] = "offline"
                self._ws_ticker_data['lost'] = True

                return

        elif msg_type == 'error':
            error_logger.error(message)

            error_logger.error("trade subscriptionStatus : %s - %s" % (message.get('code'), message.get('msg')))

        if message.get('channel') != 'trades':
            return

        # last update timestamp
        self._ws_trade_data['timestamp'] = time.time()

        symbol = message.get('market')
        if not symbol:
            return

        # last_trade_id = 0
        data = message.get('data', [])
        if not data:
            return

        for d in data:
            trade_time = FTXFuturesWatcher.parse_datetime(d['time'])
            last_trade_id = d['id']

            if last_trade_id != self._last_trade_id.get(symbol, 0):
                self._last_trade_id[symbol] = last_trade_id

            buyer_maker = 0  # -1 if d['m'] else 1

            price = d['price']
            vol = d['size']

            # d['liquidation'] : bool

            # @todo from ticker ask - bid
            spread = 0.0

            tick = (trade_time, price, price, price, vol, buyer_maker)

            self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (symbol, tick))

            if self._store_trade:
                p = str(price)
                v = str(vol)
                t = int(trade_time * 1000)
                Database.inst().store_market_trade((self.name, symbol, t, p, p, p, v, buyer_maker))

            for tf in Watcher.STORED_TIMEFRAMES:
                # generate candle per timeframe
                candle = None

                with self._mutex:
                    candle = self.update_ohlc(symbol, tf, trade_time, price, spread, vol)

                if candle is not None:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

    def __on_book_ticker_data(self, message):
        if type(message) is not dict:
            return

        msg_type = message.get('type')
        if msg_type == 'subscribed':
            self._ws_orderbook_data['timestamp'] = time.time()
            self._ws_orderbook_data['subscribed'] = True
            logger.debug("order book data subscriptionStatus : subscribed to %s" % message.get('market'))

            return

        elif msg_type == 'unsubscribed':
            self._ws_orderbook_data['timestamp'] = time.time()
            self._ws_orderbook_data['subscribed'] = False
            logger.debug("order book subscriptionStatus : unsubscribed from %s" % message.get('market'))

            return

        elif msg_type == 'info':
            if message.get('code', 0) == 20001:
                # need reconnect
                self._ws_orderbook_data['status'] = "offline"
                self._ws_orderbook_data['lost'] = True

                return

        elif msg_type == 'error':
            error_logger.error(message)

            error_logger.error("order book subscriptionStatus : %s - %s" % (message.get('code'), message.get('msg')))

        if message.get('channel') != 'orderbook':
            return

        # last update timestamp
        self._ws_orderbook_data['timestamp'] = time.time()

        symbol = message.get('market')
        if not symbol:
            return

        data = message.get('data', [])
        if not data:
            return

        # @todo

    def __on_fills_data(self, message):
        # market data instrument by symbol
        if type(message) is not dict:
            return

        msg_type = message.get('type')
        if msg_type == 'subscribed':
            self._ws_fills_data['timestamp'] = time.time()
            self._ws_fills_data['subscribed'] = True
            logger.debug("user fills data subscriptionStatus : subscribed to %s" % message.get('market'))

            return

        elif msg_type == 'unsubscribed':
            self._ws_fills_data['timestamp'] = time.time()
            self._ws_fills_data['subscribed'] = False
            logger.debug("user fills subscriptionStatus : unsubscribed from %s" % message.get('market'))

            return

        elif msg_type == 'info':
            if message.get('code', 0) == 20001:
                # need reconnect
                self._ws_fills_data['status'] = "offline"
                self._ws_fills_data['lost'] = True

                return

        elif msg_type == 'error':
            error_logger.error(message)

            error_logger.error("user fills subscriptionStatus : %s - %s" % (message.get('code'), message.get('msg')))

        if message.get('channel') != 'fills':
            return

        # last update timestamp
        self._ws_fills_data['timestamp'] = time.time()

        symbol = message.get('market')
        if not symbol:
            return

        data = message.get('data', [])
        if not data:
            return

        # @todo

    def __on_orders_data(self, message):
        # market data instrument by symbol
        if type(message) is not dict:
            return

        msg_type = message.get('type')
        if msg_type == 'subscribed':
            self._ws_orders_data['timestamp'] = time.time()
            self._ws_orders_data['subscribed'] = True
            logger.debug("user orders data subscriptionStatus : subscribed to %s" % message.get('market'))

            return

        elif msg_type == 'unsubscribed':
            self._ws_orders_data['timestamp'] = time.time()
            self._ws_orders_data['subscribed'] = False
            logger.debug("user orders subscriptionStatus : unsubscribed from %s" % message.get('market'))

            return

        elif msg_type == 'info':
            if message.get('code', 0) == 20001:
                # need reconnect
                self._ws_orders_data['status'] = "offline"
                self._ws_orders_data['lost'] = True

                return

        elif msg_type == 'error':
            error_logger.error(message)

            error_logger.error("user orders subscriptionStatus : %s - %s" % (message.get('code'), message.get('msg')))

        if message.get('channel') != 'orders':
            return

        # last update timestamp
        self._ws_orders_data['timestamp'] = time.time()

        symbol = message.get('market')
        if not symbol:
            return

        data = message.get('data', [])
        if not data:
            return

        # @todo

    #
    # misc
    #

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        @todo
        """
        pass
        # try:
        #     d = self.connector.price_for_at(market_id, timestamp)
        #     return (float(d[0][1]) + float(d[0][4]) + float(d[0][3])) / 3.0
        # except Exception as e:
        #     logger.error("Cannot found price history for %s at %s" % (
        #         market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
        #     return None

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
            trades = self._connector.client.get_all_trades(market_id, start_time=from_date.timestamp(),
                                                           end_time=to_date.timestamp())
        except Exception as e:
            logger.error("Watcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            t = FTXFuturesWatcher.parse_datetime(trade['time'])
            yield (int(t * 1000.0), trade['price'], trade['price'], trade['price'], trade['size'],
                   -1 if trade['side'] == "sell" else 1)

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        TF_LIST = [15, 60, 300, 900, 3600, 14400, 86400, 259200, 604800, 2592000]

        if timeframe not in TF_LIST:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        tf = timeframe

        try:
            candles = self._connector.client.get_historical_prices(market_id, tf,
                                                                   from_date.timestamp(), to_date.timestamp())
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s (%s)" % (self.name, tf, market_id, str(e)))

        count = 0

        for candle in candles:
            count += 1
            yield (int(candle['time']), candle['open'], candle['high'], candle['low'], candle['close'], 0.0,
                   candle['volume'])
