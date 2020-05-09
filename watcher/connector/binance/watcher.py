# @date 2018-10-10
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# www.binance.com watcher implementation

import re
import json
import time
import traceback
import bisect
import math

from datetime import datetime

from watcher.watcher import Watcher
from common.signal import Signal

from connector.binance.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle, Tick

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.binance')
exec_logger = logging.getLogger('siis.exec.watcher.binance')
error_logger = logging.getLogger('siis.error.watcher.binance')


class BinanceWatcher(Watcher):
    """
    Binance market watcher using REST + WS.

    @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md

    @todo Margin trading, get position from REST API + WS events.
    @todo Finish order book events.
    @todo Update base_exchange_rate as price change.
    @todo Once a market is not longer found (market update) we could remove it from watched list,
        and even have a special signal to strategy, and remove the subscriber, and markets data from watcher and trader
    """

    BASE_QUOTE = 'BTC'

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
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, ofrs)

        self._account_data = {}
        self._symbols_data = {}
        self._tickers_data = {}

        self._last_trade_id = {}

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()    # cache for matching symbols

        self._multiplex_handler = None  # WS multiple instruments
        self._multiplex_handlers = {}   # WS instruments per instrument
        self._tickers_handler = None    # WS all tickers
        self._user_data_handler = None  # WS user data

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

                    if not self._connector.connected or not self._connector.ws_connected:
                        self._connector.connect()

                    if self._connector and self._connector.connected:
                        #
                        # instruments
                        #

                        # get all products symbols
                        self._available_instruments = set()

                        instruments = self._connector.client.get_products().get('data', [])
                        configured_symbols = self.configured_symbols()
                        matching_symbols = self.matching_symbols_set(configured_symbols, [instrument['symbol'] for instrument in instruments])

                        # cache them
                        self.__configured_symbols = configured_symbols
                        self.__matching_symbols = matching_symbols

                        # prefetch all markets data with a single request to avoid one per market
                        self.__prefetch_markets()

                        for instrument in instruments:
                            self._available_instruments.add(instrument['symbol'])

                        # all tickers
                        self._tickers_handler = self._connector.ws.start_ticker_socket(self.__on_tickers_data)

                        # userdata
                        self._user_data_handler = self._connector.ws.start_user_socket(self.__on_user_data)

                        # and start ws manager if necessarry
                        try:
                            self._connector.ws.start()
                        except RuntimeError:
                            logger.debug("%s WS already started..." % (self.name))

                        # once market are init
                        self._ready = True
                        self._connecting = False

                        logger.debug("%s connection successed" % (self.name))

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

        if self._connector and self._connector.connected and self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

    def disconnect(self):
        super().disconnect()

        logger.debug("%s disconnecting..." % (self.name))

        with self._mutex:
            try:
                if self._connector:
                    self._connector.disconnect()
                    self._connector = None

                    # reset WS handlers
                    self._multiplex_handler = None
                    self._multiplex_handlers = {}
                    self._tickers_handler = None
                    self._user_data_handler = None

                self._ready = False

                logger.debug("%s disconnected" % (self.name))

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self):
        return self._connector and self._connector.authenticated

    def pre_update(self):
        if not self._connecting and not self._ready:
            reconnect = False

            with self._mutex:
                if not self._ready or self._connector is None or not self._connector.connected or not self._connector.ws_connected:
                    # cleanup
                    self._ready = False
                    self._connector = None

                    # @todo does the subsriptions renegociated by the ws client ?
                    reconnect = True

            if reconnect:
                time.sleep(2)
                self.connect()
                return

    #
    # instruments
    #

    def subscribe(self, market_id, timeframe, ohlc_depths=None, order_book_depth=None):
        result = False
        with self._mutex:
            try:
                if market_id in self.__matching_symbols:
                    multiplex = []

                    # live data
                    symbol = market_id.lower()

                    # depth - order book
                    # multiplex.append(symbol + '@depth')

                    # aggreged trade
                    multiplex.append(symbol + '@aggTrade')

                    # not used : ohlc (1m, 5m, 1h), prefer rebuild ourself using aggreged trades
                    # multiplex.append('{}@kline_{}'.format(symbol, '1m'))  # '5m' '1h'...

                    # fetch from 1M to 1W
                    if self._initial_fetch:
                        logger.info("%s prefetch for %s" % (self.name, market_id))

                        self.fetch_and_generate(market_id, Instrument.TF_1M, 3*self.DEFAULT_PREFETCH_SIZE, Instrument.TF_3M)
                        self.fetch_and_generate(market_id, Instrument.TF_5M, self.DEFAULT_PREFETCH_SIZE, None)
                        self.fetch_and_generate(market_id, Instrument.TF_15M, 2*self.DEFAULT_PREFETCH_SIZE, Instrument.TF_30M)
                        self.fetch_and_generate(market_id, Instrument.TF_1H, 4*self.DEFAULT_PREFETCH_SIZE, Instrument.TF_4H)
                        self.fetch_and_generate(market_id, Instrument.TF_1D, 7*self.DEFAULT_PREFETCH_SIZE, Instrument.TF_1W)               

                    # one more watched instrument
                    self.insert_watched_instrument(market_id, [0])

                    # trade+depth
                    self._multiplex_handlers[market_id] = self._connector.ws.start_multiplex_socket(multiplex, self.__on_multiplex_data)

                    result = True

            except Exception as e:
                error_logger.error(repr(e))

        return result

    def unsubscribe(self, market_id, timeframe):
        with self._mutex:
            if market_id in self._multiplex_handlers:
                self._multiplex_handlers[market_id].close()
                del self._multiplex_handlers[market_id]

                return True

        return False

    #
    # processing
    #

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, ready status to false to retry a connection
            self._ready = False
            return False

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # market info update (each 4h), might be a Timer
        #

        if time.time() - self._last_market_update >= BinanceWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
            try:
                logger.info("%s update market info" % self.name)
                self.update_markets_info()
                self._last_market_update = time.time()
            except Exception as e:
                error_logger.error("update_update_markets_info %s" % str(e))

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
            for afilter in symbol["filters"]:
                if afilter['filterType'] == "LOT_SIZE":  # 'MARKET_LOT_SIZE'
                    size_limits = [afilter['minQty'], afilter['maxQty'], afilter['stepSize']]

                elif afilter['filterType'] == "MIN_NOTIONAL":
                    notional_limits[0] = afilter['minNotional']

                elif afilter['filterType'] == "PRICE_FILTER":
                    price_limits = [afilter['minPrice'], afilter['maxPrice'], afilter['tickSize']]

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

            # only order book can give us bid/ofr
            market.bid = float(ticker['price'])
            market.ofr = float(ticker['price'])

            mid_price = float(ticker['price'])

            if quote_asset != self.BASE_QUOTE:
                if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                    market.base_exchange_rate = float(self._tickers_data.get(quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                    market.base_exchange_rate = 1.0 / float(self._tickers_data.get(self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
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
            Database.inst().store_market_info((self.name, market.market_id, market.symbol,
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
                str(market.maker_fee), str(market.taker_fee), str(market.maker_commission), str(market.taker_commission))
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

    def __on_tickers_data(self, data):
        # market data instrument by symbol
        for ticker in data:
            symbol = ticker['s']
            last_trade_id = ticker['L']

            if last_trade_id != self._last_trade_id.get(symbol, 0):
                self._last_trade_id[symbol] = last_trade_id

                last_update_time = ticker['C'] * 0.001

                bid = float(ticker['b'])
                ofr = float(ticker['a'])

                vol24_base = float(ticker['v']) if ticker['v'] else 0.0
                vol24_quote = float(ticker['q']) if ticker['q'] else 0.0

                # @todo compute base_exchange_rate
                # if quote_asset != self.BASE_QUOTE:
                #     if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                #         market.base_exchange_rate = float(self._tickers_data.get(quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                #     elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                #         market.base_exchange_rate = 1.0 / float(self._tickers_data.get(self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
                #     else:
                #         market.base_exchange_rate = 1.0
                # else:
                #     market.base_exchange_rate = 1.0

                market_data = (symbol, last_update_time > 0, last_update_time, bid, ofr, None, None, None, vol24_base, vol24_quote)
                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_depth_data(self, data):
        # @todo using binance.DepthCache
        return

        if data['e'] == 'depthUpdate':
            symbol = data['s']

            if symbol not in self._depths:
                # initial snapshot of the order book from REST API
                initial = self._connector.client.get_order_book(symbol=symbol, limit=100)

                bids = {}
                asks = {}

                for bid in initial['bids']:
                    bids[bid[0]] = bid[1]

                for ask in initial['asks']:
                    asks[ask[0]] = ask[1]

                self._depths[symbol] = [initial.get('lastUpdateId', 0), bids, asks]

            depth = self._depths[symbol]

            # The first processed should have U <= lastUpdateId+1 AND u >= lastUpdateId+1
            if data['u'] <= depth[0] or data['U'] >= depth[0]:
                # drop event if older than the last snapshot
                return

            if data['U'] != depth[0] + 1:
                logger.warning("Watcher %s, there is a gap into depth data for symbol %s" % (self._name, symbol))

            for bid in data['b']:
                # if data['U'] <= depth[0]+1 and data['u'] >= depth[0]+1:
                if bid[1] == 0:
                    del depth[1][bid[0]]  # remove at price
                else:
                    depth[2][bid[0]] = bid[1]  # price : volume

            for ask in data['a']:
                if ask[1] == 0:
                    del depth[2][ask[0]]
                else:
                    depth[2][ask[0]] = ask[1]

            # last processed id, next must be +1
            depth[0] = data['u']

            # self.service.notify(Signal.SIGNAL_ORDER_BOOK, self.name, (symbol, depth[1], depth[2]))

    def __on_multiplex_data(self, data):
        """
        Intercepts ticker all, depth for followed symbols.
        Klines are generated from tickers data. Its a prefered way to recuce network traffic and API usage.
        """
        if not data.get('stream'):
            return

        if data['stream'].endswith('@aggTrade'):
            self.__on_trade_data(data['data'])
        elif data['stream'].endswith('@depth'):
            self.__on_depth_data(data['data'])
        elif '@kline_' in data['stream']:
            self.__on_kline_data(data['data'])
        # elif data['stream'] == '!ticker@arr':
        #     self.__on_tickers_data(data['data'])

    def __on_trade_data(self, data):
        event_type = data.get('e', "")

        if event_type == "aggTrade":
            symbol = data['s']
            trade_time = data['T'] * 0.001

            # trade_id = data['t']
            # buyer_maker = data['m']

            price = float(data['p'])
            vol = float(data['q'])

            bid = price
            ofr = price

            tick = (trade_time, bid, ofr, vol)

            self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (symbol, tick))

            if self._store_trade:
                Database.inst().store_market_trade((self.name, symbol, int(data['T']), data['p'], data['p'], data['q']))

            for tf in Watcher.STORED_TIMEFRAMES:
                # generate candle per timeframe
                candle = None

                with self._mutex:
                    candle = self.update_ohlc(symbol, tf, trade_time, bid, ofr, vol)

                if candle is not None:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

    def __on_kline_data(self, data):
        event_type = data.get('e', '')

        if event_type == 'kline':
            k = data['k']

            symbol = k['s']
            timestamp = k['t'] * 0.001

            tf = self.REV_TF_MAP[k['i']]

            candle = Candle(timestamp, tf)

            # only price, no spread
            candle.set_bid_ohlc(
              float(k['o']),
              float(k['h']),
              float(k['l']),
              float(k['c']))

            candle.set_ofr_ohlc(
              float(k['o']),
              float(k['h']),
              float(k['l']),
              float(k['c']))

            candle.set_volume(float(k['v']))
            candle.set_consolidated(k['x'])

            self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

            if k['x'] and self._store_ohlc:
                # write only consolidated candles. values are string its perfect
                Database.inst().store_market_ohlc((
                    self.name, symbol, int(k['t']), tf,
                    k['o'], k['h'], k['l'], k['c'],
                    k['o'], k['h'], k['l'], k['c'],
                    k['v']))

    def __on_user_data(self, data):
        """
        @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md#web-socket-payloads
        @todo Soon support of margin trading.
        """
        event_type = data.get('e', '')

        if event_type == 'executionReport':
            exec_logger.info("binance.com executionReport %s" % str(data))

            event_timestamp = float(data['E']) * 0.001
            symbol = data['s']
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
    # miscs
    #

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        try:
            d = self.connector.price_for_at(market_id, timestamp)
            return (float(d[0][1]) + float(d[0][4]) + float(d[0][3])) / 3.0
        except Exception as e:
            logger.error("Cannot found price history for %s at %s" % (market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
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
                # market exists and tradable
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ofr,
                        market.base_exchange_rate, market.contract_size, market.value_per_pip,
                        market.vol24h_base, market.vol24h_quote)
            else:
                # market exists but closed
                market_data = (market_id, market.is_open, market.last_update_time, None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

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
            candles = self._connector.client.get_historical_klines(market_id, tf, int(from_date.timestamp() * 1000), int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s (%s)" % (self.name, tf, market_id, str(e)))

        count = 0
        
        for candle in candles:
            count += 1
            # (timestamp, open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
            yield((candle[0], candle[1], candle[2], candle[3], candle[4], candle[1], candle[2], candle[3], candle[4], candle[5]))
