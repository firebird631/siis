# @date 2019-08-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# www.kraken.com watcher implementation

import re
import json
import time
import traceback
import bisect
import math

from datetime import datetime

from watcher.watcher import Watcher
from notifier.signal import Signal

from connector.kraken.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle, Tick

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.binance')
exec_logger = logging.getLogger('siis.exec.binance')
error_logger = logging.getLogger('siis.error.binance')


class KrakenWatcher(Watcher):
    """
    Kraken market watcher using REST + WS.

    @todo complete
    """

    BASE_QUOTE = "ZUSD"

    TF_MAP = {
        60: 1,          # 1m
        300: 5,         # 5m
        900: 15,        # 15m
        1800: 30,       # 30m
        3600: 60,       # 1h
        14400: 240,     # 4h
        86400.0: 1440,  # 1d
        # 604800: 10080,  # 1w (not allowed because starts on thuesday)
        # 1296000: 21600  # 15d
    }

    def __init__(self, service):
        super().__init__("kraken.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, ofrs)

        self._acount_data = {}
        self._symbols_data = {}
        self._tickers_data = {}

        self._last_trade_id = {}

        self._assets = {}
        self._instruments = {}
        self._wsname_lookup = {}

    def connect(self):
        super().connect()

        try:
            self.lock()
            self._ready = False

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

                # assets
                self._assets = self._connector.assets()

                for asset_name, details in self._assets.items():
                    # {'aclass': 'currency', 'altname': 'ADA', 'decimals': 8, 'display_decimals': 6},
                    pass
 
                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                # prefetch all markets data with a single request to avoid one per market
                self.__prefetch_markets()

                instruments = self._instruments
                configured_symbols = self.configured_symbols()
                matching_symbols = self.matching_symbols_set(configured_symbols, [instrument for instrument in list(self._instruments.keys())])

                pairs = []

                for market_id, instrument in instruments.items():
                    self._available_instruments.add(market_id)

                    # and watch it if configured or any
                    if market_id in matching_symbols:
                        # live data
                        pairs.append(instrument['wsname'])
                        self._wsname_lookup[instrument['wsname']] = market_id

                        # fetch from 1m to 1w
                        self.fetch_and_generate(market_id, Instrument.TF_1M, self.DEFAULT_PREFETCH_SIZE*3, Instrument.TF_3M)
                        self.fetch_and_generate(market_id, Instrument.TF_5M, self.DEFAULT_PREFETCH_SIZE, None)
                        self.fetch_and_generate(market_id, Instrument.TF_15M, self.DEFAULT_PREFETCH_SIZE*2, Instrument.TF_30M)
                        self.fetch_and_generate(market_id, Instrument.TF_1H, self.DEFAULT_PREFETCH_SIZE*2, Instrument.TF_2H)
                        self.fetch_and_generate(market_id, Instrument.TF_4H, self.DEFAULT_PREFETCH_SIZE, None)
                        self.fetch_and_generate(market_id, Instrument.TF_1D, self.DEFAULT_PREFETCH_SIZE*7, Instrument.TF_1W)

                        time.sleep(6.0)

                        logger.info("%s prefetch for %s" % (self.name, market_id))

                        # one more watched instrument
                        self.insert_watched_instrument(market_id, [0])

                if pairs:
                    self._connector.ws.subscribe_public(
                        subscription={
                            'name': 'ticker'
                        },
                        pair=pairs,
                        callback=self.__on_ticker_data
                    )

                    self._connector.ws.subscribe_public(
                        subscription={
                            'name': 'trade'
                        },
                        pair=pairs,
                        callback=self.__on_trade_data
                    )

                    # @todo see later
                    # self._connector.ws.subscribe_public(
                    #     subscription={
                    #         'name': 'book'
                    #     },
                    #     pair=pairs,
                    #     depth=10,  # 10 25 100 500 1000
                    #     callback=self.__on_depth_data
                    # )

                #
                # user data
                #

                ws_token = self._connector.get_ws_token()

                if ws_token and ws_token.get('token'):
                    self._connector.ws.subscribe_private(
                        subscription={
                            'name': 'ownTrades',
                            'token': ws_token['token']
                        },
                        callback=self.__on_own_trades
                    )

                    self._connector.ws.subscribe_private(
                        subscription={
                            'name': 'openOrders',
                            'token': ws_token['token']
                        },
                        callback=self.__on_open_orders
                )

                # and start ws manager
                self._connector.ws.start()

                # once market are init
                self._ready = True

        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())
        finally:
            self.unlock()

        if self._ready and self._connector and self._connector.connected:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._connector:
                self._connector.disconnect()
                self._connector = None

            self._ready = False

        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())
        finally:
            self.unlock()

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
        if not self._ready or self._connector is None or not self._connector.connected or not self._connector.ws_connected:
            # retry in 2 second
            self._ready = False
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

        if time.time() - self._last_market_update >= KrakenWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
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
        instrument = self._instruments.get(market_id)

        market = None

        if instrument:
            market = Market(market_id, instrument['altname'])

            market.is_open = True
            market.expiry = '-'

            # "wsname":"XBT\/USD"
            # wsname = WebSocket pair name (if available)
            # pair_decimals = scaling decimal places for pair
            # lot_decimals = scaling decimal places for volume
            # lot_multiplier = amount to multiply lot volume by to get currency volume

            # "aclass_base":"currency"
            base_asset = instrument['base']  # XXBT
            market.set_base(base_asset, base_asset, instrument['pair_decimals'])

            # "aclass_quote":"currency"
            quote_asset = instrument['quote']  # ZUSD 
            market.set_quote(quote_asset, quote_asset, instrument['lot_decimals'])  # 8

            # tick size at the base asset precision
            market.one_pip_means = math.pow(10.0, -instrument['pair_decimals'])  # 1
            market.value_per_pip = 1.0
            market.contract_size = 1.0
            market.lot_size = 1.0  # "lot":"unit", "lot_multiplier":1

            # "margin_call":80, "margin_stop":40
            # margin_call = margin call level
            # margin_stop = stop-out/liquidation margin level

            leverages = set(instrument.get('leverage_buy', []))
            leverages.intersection(set(instrument.get('leverage_sell', [])))

            market.margin_factor = 1.0 / max(leverages) if leverages else 1.0

            market.set_leverages(leverages)

            size_limit = self._size_limits.get(instrument['altname'], {})
            min_size = size_limit.get('min-size', 1.0)

            size_limits = [str(min_size), "0.0", str(min_size)]
            notional_limits = ["0.0", "0.0", "0.0"]
            price_limits = ["0.0", "0.0", "0.0"]

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(float(notional_limits[0]), 0.0, 0.0)

            # "lot":"unit"
            market.unit_type = Market.UNIT_AMOUNT
            market.market_type = Market.TYPE_CRYPTO
            market.contract_type = Market.CONTRACT_SPOT

            market.trade = Market.TRADE_ASSET
            if leverages:
                market.trade |= Market.TRADE_MARGIN
                market.trade |= Market.TRADE_FIFO

            # orders capacities
            market.orders = Order.ORDER_LIMIT | Order.ORDER_MARKET | Order.ORDER_STOP | Order.ORDER_TAKE_PROFIT

            # @todo take the first but it might depends of the traded volume per 30 days, then request volume window to got it
            # "fees":[[0,0.26],[50000,0.24],[100000,0.22],[250000,0.2],[500000,0.18],[1000000,0.16],[2500000,0.14],[5000000,0.12],[10000000,0.1]],
            # "fees_maker":[[0,0.16],[50000,0.14],[100000,0.12],[250000,0.1],[500000,0.08],[1000000,0.06],[2500000,0.04],[5000000,0.02],[10000000,0]],
            fees = instrument.get('fees', [])
            fees_maker = instrument.get('fees_maker', [])

            if fees:
                market.taker_fee = round(fees[0][1] * 0.01, 6)
            if fees_maker:
                market.maker_fee = round(fees_maker[0][1] * 0.01, 6)

            if instrument.get('fee_volume_currency'):
                market.fee_currency = instrument['fee_volume_currency']

            if quote_asset != self.BASE_QUOTE:
                pass
            #     if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
            #         market.base_exchange_rate = float(self._tickers_data.get(quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
            #     elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
            #         market.base_exchange_rate = 1.0 / float(self._tickers_data.get(self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
            #     else:
            #         market.base_exchange_rate = 1.0
            else:
                market.base_exchange_rate = 1.0

            # market.contract_size = 1.0 / mid_price
            # market.value_per_pip = market.contract_size / mid_price

            # volume 24h : not have here

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

            # notify for strategy
            self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, (market_id, market))

        return market

    def fetch_order_book(self, market_id):
        # https://api.kraken.com/0/public/Depth
        pass

    #
    # protected
    #

    def __prefetch_markets(self):
        # size limits from conf
        self._size_limits = self.service.watcher_config(self._name).get("size-limits", {})

        self._assets = self._connector.assets()
        self._instruments = self._connector.instruments()

    def __on_depth_data(self, data):
        # @ref https://www.kraken.com/en-us/features/websocket-api#message-book
        pass

    def __on_ticker_data(self, data):
        if isinstance(data, list) and data[2] == "ticker":
            market_id = self._wsname_lookup.get(data[3])
            base_asset, quote_asset = data[3].split('/')

            if not market_id:
                return

            last_update_time = time.time()
            ticker = data[1]
            
            bid = float(ticker['b'][0])
            ofr = float(ticker['a'][0])

            vol24_base = float(ticker['v'][0])
            vol24_quote = float(ticker['v'][0]) * float(ticker['p'][0])

            # @todo compute base_exchange_rate
            # if quote_asset != self.BASE_QUOTE:
            #     if quote_asset in self._assets:
            #         pass  # @todo direct or indirect
            #     else:
            #         market.base_exchange_rate = 1.0  # could be EURUSD... but we don't have
            # else:
            #     market.base_exchange_rate = 1.0

            if bid > 0.0 and ofr > 0.0:
                market_data = (market_id, last_update_time > 0, last_update_time, bid, ofr, None, None, None, vol24_base, vol24_quote)
                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

        elif isinstance(data, dict):
            if data['event'] == "subscriptionStatus" and data['channelName'] == "ticker":
                # @todo register channelID...
                # {'channelID': 93, 'channelName': 'trade', 'event': 'subscriptionStatus', 'pair': 'ETH/USD', 'status': 'subscribed', 'subscription': {'name': 'ticker'}}
                pass

    def __on_trade_data(self, data):
        if isinstance(data, list) and data[2] == "trade":
            market_id = self._wsname_lookup.get(data[3])

            if not market_id:
                return

            for trade in data[1]:
                bid = float(trade[0])
                ofr = float(trade[0])
                vol = float(trade[1])
                trade_time = float(trade[2])
                # side = trade[3]

                tick = (trade_time, bid, ofr, vol)

                # store for generation of OHLCs
                self.lock()
                self._last_tick[market_id] = tick
                self.unlock()

                self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (market_id, tick))

                if not self._read_only and self._store_trade:
                    Database.inst().store_market_trade((self.name, market_id, int(trade_time*1000.0), trade[0], trade[0], trade[1]))

                for tf in Watcher.STORED_TIMEFRAMES:
                    # generate candle per timeframe
                    self.lock()
                    candle = self.update_ohlc(market_id, tf, trade_time, bid, ofr, vol)
                    self.unlock()

                    if candle is not None:
                        self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, candle))

        elif isinstance(data, dict):
            if data['event'] == "subscriptionStatus" and data['channelName'] == "trade":
                # @todo register channelID...
                # {'channelID': 93, 'channelName': 'trade', 'event': 'subscriptionStatus', 'pair': 'ETH/USD', 'status': 'subscribed', 'subscription': {'name': 'trade'}}
                pass

    def __on_kline_data(self, data):
        pass

    def __on_own_trades(self, data):
        pass

    def __on_open_orders(self, data):
        pass

    #
    # miscs
    #

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        return None

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
                market_data = (market_id, market.is_open, market.last_update_time, None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        if timeframe not in self.TF_MAP:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        # second timeframe to kraken interval
        interval = self.TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, interval, from_date, to_date)
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s" % (self.name, interval, market_id))
            error_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield((candle[0], candle[1], candle[2], candle[3], candle[4], candle[1], candle[2], candle[3], candle[4], candle[5]))

        logger.info("Watcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, interval))
