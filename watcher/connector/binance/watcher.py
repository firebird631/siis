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
from notifier.signal import Signal

from connector.binance.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle, Tick

from config import config

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.binance')


class BinanceWatcher(Watcher):
    """
    Binance market watcher using REST + WS.

    @note Market step-size are scaled for the smallers of them to avoid somes weirds issues (have to check more on that).

    @todo Eeach day or 4h update/store markets info.
    @todo Soon support of margin trading, get position from REST API + WS events.
    @todo Finish order book events.
    @todo Update base_exchange_rate as price change.
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

        self._acount_data = {}
        self._symbols_data = {}
        self._tickers_data = {}

        self._init = False
        self._last_trade_id = {}

    def connect(self):
        super().connect()

        try:
            self.lock()
            identity = self.service.identity(self._name)

            if identity:
                if not self._connector:
                    self._connector = Connector(
                        self.service,
                        identity.get('api-key'),
                        identity.get('api-secret'),
                        identity.get('host'))

                if not self._connector.connected or not self._connector.ws_connected:
                    self._connector.connect()

                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                instruments = self._connector.client.get_products().get('data', [])
                configured_symbols = self.configured_symbols()
                matching_symbols = self.matching_symbols_set(configured_symbols, [instrument['symbol'] for instrument in instruments])

                # prefetch all markets data with a single request to avoid one per market
                self.__prefetch_markets()

                multiplex = []

                for instrument in instruments:
                    self._available_instruments.add(instrument['symbol'])

                    # and watch it if configured or any
                    if instrument['symbol'] in matching_symbols:
                        # live data
                        symbol = instrument['symbol'].lower()

                        # depth - order book
                        # multiplex.append(symbol + '@depth')

                        # aggreged trade
                        multiplex.append(symbol + '@aggTrade')

                        # ohlc (1m, 5m, 1h), prefer rebuild ourself using aggreged trades
                        # multiplex.append('{}@kline_{}'.format(symbol, '1m'))
                        # multiplex.append('{}@kline_{}'.format(symbol, '5m'))
                        # multiplex.append('{}@kline_{}'.format(symbol, '1h'))

                        # one more watched instrument
                        self.insert_watched_instrument(instrument['symbol'], [0])

                # all 24h mini tickers (prefers ticker@arr)
                # multiplex.append('!miniTicker@arr')

                # all tickers
                multiplex.append('!ticker@arr')

                # depth+kline+ticker
                self._multiplex_handler = self._connector.ws.start_multiplex_socket(multiplex, self.__on_multiplex_data)

                # userdata
                self._user_data_handler = self._connector.ws.start_user_socket(self.__on_user_data)

                # and start ws manager
                self._connector.ws.start()

                # once market are init
                self._init = True

            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

        except Exception as e:
            Terminal.inst().error(repr(e))
            logger.error(traceback.format_exc())
        finally:
            self.unlock()

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._connector:
                self._connector.disconnect()
                self._connector = None

            self._init = False

        except Exception as e:
            Terminal.inst().error(repr(e))
            logger.error(traceback.format_exc())
        finally:
            self.unlock()

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._init and self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self):
        return self._init and self._connector and self._connector.authenticated

    def pre_update(self):
        if not self._init or self._connector is None or not self._connector.connected or not self._connector.ws_connected:
            # retry in 2 second
            self._init = False
            self._connector = None

            time.sleep(2)
            self.connect()
            return

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            return False

        #
        # ohlc close/open
        #

        self.lock()
        self.update_from_tick()
        self.unlock()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= BinanceWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
            self.update_markets_info()
            self._last_market_update = time.time()

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
        account = self._acount_data

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
                if afilter['filterType'] == "LOT_SIZE":
                    size_limits = [afilter['minQty'], afilter['maxQty'], afilter['stepSize']]

                elif afilter['filterType'] == "MIN_NOTIONAL":
                    notional_limits[0] = afilter['minNotional']

                elif afilter['filterType'] == "PRICE_FILTER":
                    price_limits = [afilter['minPrice'], afilter['maxPrice'], afilter['tickSize']]

            if float(size_limits[2]) < 1:
                size_limits[2] = str(float(size_limits[2]))  # * 10)

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(float(notional_limits[0]), 0.0, 0.0)

            market.unit_type = Market.UNIT_AMOUNT
            market.market_type = Market.TYPE_CRYPTO
            market.trade = Market.TRADE_ASSET
            market.contract_type = Market.CONTRACT_SPOT

            # @todo orders capacities
            # symbol['orderTypes'] in ['LIMIT', 'LIMIT_MAKER', 'MARKET', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT']
            # market.orders = 

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

            # in client.get_ticker but cost is 40 for any symbols then wait it at all-tickets WS event
            # vol24_base = ticker24h('volume')
            # vol24_quote = ticker24h('quoteVolume')

            # store the last market info to be used for backtesting
            if not self._read_only:
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

        self._acount_data = self._connector.client.get_account()
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
                # base_exchange_rate = ...

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

        if data['stream'] == '!ticker@arr':
            self.__on_tickers_data(data['data'])
        elif data['stream'].endswith('@aggTrade'):
            self.__on_trade_data(data['data'])
        elif data['stream'].endswith('@depth'):
            self.__on_depth_data(data['data'])
        elif '@kline_' in data['stream']:
            self.__on_kline_data(data['data'])

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

            tick = Tick(trade_time)

            tick.set_price(bid, ofr)
            tick.set_volume(vol)

            # store for generation of OHLCs
            self.lock()
            self._last_tick[symbol] = tick
            self.unlock()

            self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (symbol, tick))

            if not self._read_only:
                Database.inst().store_market_trade((self.name, symbol, int(data['T']), data['p'], data['p'], data['q']))

            for tf in Watcher.STORED_TIMEFRAMES:
                # generate candle per timeframe
                self.lock()
                candle = self.update_ohlc(symbol, tf, trade_time, bid, ofr, vol)
                self.unlock()

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

            if k['x'] and not self._read_only:
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
            logger.info("binance.com executionReport %s", str(data))

            event_timestamp = float(data['E']) * 0.001
            symbol = data['s']
            cid = data['c']

            reason = ""
            side = ''
            quantity = 0
            partially = 0

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

                if data['o'] == 'LIMIT':
                    order_type = Order.ORDER_LIMIT
                elif data['o'] == 'MARKET':
                    order_type = Order.ORDER_MARKET
                elif data['o'] == 'STOP_LOSS':
                    order_type = Order.ORDER_STOP
                elif data['o'] == 'STOP_LOSS_LIMIT':
                    order_type = Order.ORDER_STOP_LIMIT
                elif data['o'] == 'TAKE_PROFIT':
                    order_type = Order.ORDER_TAKE_PROFIT
                elif data['o'] == 'TAKE_PROFIT_LIMIT':
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                elif data['o'] == 'LIMIT_MAKER':
                    order_type = Order.ORDER_LIMIT
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
                    'order-price': float(data['p']),
                    'exec-price': float(data['L']),
                    'filled': float(data['l']),
                    'cumulative-filled': float(data['z']),
                    'quote-transacted': float(data['Y']),  # similar as float(data['Z']) for cumulative
                    'stop-loss': float(data['P']),
                    'take-profit': 0,
                    'time-in-force': time_in_force,
                    'commission-amount': float(data['n']),
                    'commission-asset': data['N']
                }

                self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

            elif data['x'] == 'NEW' and data['X'] == 'NEW':
                order_id = str(data['i'])
                timestamp = float(data['O']) * 0.001  # order creation time
                client_order_id = str(data['c'])

                iceberg_qty = float(data['F'])

                if data['o'] == 'LIMIT':
                    order_type = Order.ORDER_LIMIT
                elif data['o'] == 'MARKET':
                    order_type = Order.ORDER_MARKET
                elif data['o'] == 'STOP_LOSS':
                    order_type = Order.ORDER_STOP
                elif data['o'] == 'STOP_LOSS_LIMIT':
                    order_type = Order.ORDER_STOP_LIMIT
                elif data['o'] == 'TAKE_PROFIT':
                    order_type = Order.ORDER_TAKE_PROFIT
                elif data['o'] == 'TAKE_PROFIT_LIMIT':
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                elif data['o'] == 'LIMIT_MAKER':
                    order_type = Order.ORDER_LIMIT
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
                    'order-price': float(data['p']),
                    'stop-loss': float(data['P']),
                    'time-in-force': time_in_force
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
            return 0.0

    def update_markets_info(self):
        """
        Update market info.
        """
        self.__prefetch_markets()

        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market.is_open:
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ofr,
                        market.base_exchange_rate, market.contract_size, market.value_per_pip,
                        market.vol24h_base, market.vol24h_quote)
            else:
                market_data = (market_id, market.is_open, market.last_update_time, 0.0, 0.0, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)
