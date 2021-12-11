# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.kraken.com watcher implementation

import time
import traceback
import math

from watcher.watcher import Watcher
from common.signal import Signal
from common.utils import timeframe_to_str

from connector.kraken.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument

from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.kraken')
exec_logger = logging.getLogger('siis.exec.watcher.kraken')
error_logger = logging.getLogger('siis.error.watcher.kraken')
traceback_logger = logging.getLogger('siis.traceback.watcher.kraken')


class KrakenWatcher(Watcher):
    """
    Kraken market watcher using REST + WS.

    @todo position info
    @todo contract_size, value_per_pip, base_exchange_rate (initials and updates)
    @todo fee from 30 day traded volume
    @todo order book WS

    @ref WS 'status' online|maintenance|cancel_only|limit_only|post_only
    @ref https://docs.kraken.com/websockets
    """

    BASE_QUOTE = "ZUSD"
    UPDATE_ASSET_BALANCE_DELAY = 60.0  # each minute
    
    USE_SPREAD = False  # use spread data in place of ticker (more faster and precise but wakeup a lot the listeners)
    
    RECONNECT_WINDOW = 10*60.0  # 10min of rolling window
    MAX_RETRY_PER_WINDOW = 150  # 150 retry per rolling window

    TF_MAP = {
        60: 1,          # 1m
        300: 5,         # 5m
        900: 15,        # 15m
        1800: 30,       # 30m
        3600: 60,       # 1h
        14400: 240,     # 4h
        86400.0: 1440,  # 1d
        # 604800: 10080,  # 1w (not allowed because starts on tuesday)
        # 1296000: 21600  # 15d
    }

    def __setup_ws_state(self):
        # ['status'] in "online" | "maintenance" | "cancel_only" | "limit_only" | "post_only"
        return {
            'status': "offline",
            'version': "0",
            'timestamp': 0.0,
            'subscribed': False,
            'lost': False,
            'retry': 0.0
        }

    def __reset_ws_state(self, ws):
        """Reset the states of a WS connection watcher."""
        ws['status'] = "offline"
        ws['version'] = "0"
        ws['timestamp'] = 0.0
        ws['subscribed'] = False
        ws['lost'] = False
        ws['retry'] = 0.0

    def __check_reconnect(self, ws):
        """Return True if a reconnection in needed."""
        if ws['lost']:
            return True

        # above 5 seconds without activity then reconnect
        if ws['timestamp'] > 0.0 and time.time() - ws['timestamp'] > 5.0:
            # if maintenance need to wait 5 sec before try to reconnect
            # if ws['status'] == "maintenance" and ws['retry'] <= 0.0:
            #     ws['retry'] = time.time() + 5.0

            return True

        return False

    def __reconnect_ws(self, ws, callback, name):
        # if ws['retry'] > 0.0 and time.time() < ws['retry']:
        #     return

        logger.debug("%s re-subscribe %s to markets data stream..." % (self.name, name))

        with self._mutex:
            try:
                self._connector.ws.stop_socket(name)
                self.__reset_ws_state(ws)

                pairs = []
                instruments = self._instruments

                for market_id in self._watched_instruments:
                    if market_id in instruments:
                        pairs.append(instruments[market_id]['wsname'])

                # if pairs:
                self._connector.ws.subscribe_public(
                    subscription=name,
                    pair=pairs,
                    callback=callback
                )
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    def __reconnect_user_ws(self):
        # if self._ws_own_trades['retry'] > 0.0 and time.time() < self._ws_own_trades['retry']:
        #     return
        # if self._ws_open_orders['retry'] > 0.0 and time.time() < self._ws_open_orders['retry']:
        #     return

        logger.debug("%s re-subscribe to user data stream..." % self.name)

        with self._mutex:
            try:
                self._connector.ws.stop_private_socket('ownTrades')
                self._connector.ws.stop_private_socket('openOrders')

                ws_token = self._connector.get_ws_token()

                if ws_token and ws_token.get('token'):
                    self.__reset_ws_state(self._ws_own_trades)
                    self.__reset_ws_state(self._ws_open_orders)

                    self._connector.ws.subscribe_private(
                        token=ws_token['token'],
                        subscription='ownTrades',
                        callback=self.__on_own_trades
                    )

                    self._connector.ws.subscribe_private(
                        token=ws_token['token'],
                        subscription='openOrders',
                        callback=self.__on_open_orders
                    )
                else:
                    # error retrieving the token, retry
                    self._ws_own_trades['timestamp'] = time.time()
                    self._ws_open_orders['timestamp'] = time.time()

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    def __init__(self, service):
        super().__init__("kraken.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, asks)

        self._symbols_data = {}
        self._tickers_data = {}

        self._last_trade_id = {}

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()    # cache for matching symbols
        self.__ws_symbols = set()          # cache for matching symbols WS names

        self._assets = {}
        self._instruments = {}
        self._wsname_lookup = {}
        self._markets_aliases = {}

        self._last_balance_update = 0.0  # last update of balances (assets) timestamp
        self._last_assets_balances = {}  # last free/locked balances values for each asset

        # user WS
        self._ws_own_trades = self.__setup_ws_state()
        self._ws_open_orders = self.__setup_ws_state()

        # public WS
        self._ws_ticker_data = self.__setup_ws_state()
        self._ws_trade_data = self.__setup_ws_state()
        self._ws_spread_data = self.__setup_ws_state()
        self._ws_depth_data = self.__setup_ws_state()

        self._got_orders_init_snapshot = False
        self._got_trades_init_snapshot = False

        self._orders_ws_cache = {}     # orders data cache to be updated per WS
        self._positions_ws_cache = {}  # positions data cache to be updated per WS

    def connect(self):
        super().connect()

        with self._mutex:
            try:
                self._ready = False
                self._connecting = True

                # initial snapshot and cache for WS
                self._got_orders_init_snapshot = False
                self._got_trades_init_snapshot = False

                self._orders_ws_cache = {}
                self._positions_ws_cache = {}

                # user WS
                self.__reset_ws_state(self._ws_own_trades)
                self.__reset_ws_state(self._ws_open_orders)

                # public WS
                self.__reset_ws_state(self._ws_ticker_data)
                self.__reset_ws_state(self._ws_trade_data)
                self.__reset_ws_state(self._ws_spread_data)
                self.__reset_ws_state(self._ws_depth_data)

                identity = self.service.identity(self._name)

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
                        #
                        # assets and instruments
                        #

                        # get all products symbols
                        self._available_instruments = set()

                        # prefetch all markets data with a single request to avoid one per market
                        self.__prefetch_markets()

                        instruments = self._instruments
                        configured_symbols = self.configured_symbols()
                        matching_symbols = self.matching_symbols_set(configured_symbols, [
                            instrument for instrument in list(self._instruments.keys())])

                        # cache them
                        self.__configured_symbols = configured_symbols
                        self.__matching_symbols = matching_symbols

                        for market_id, instrument in instruments.items():
                            self._available_instruments.add(market_id)

                            # and the related name mapping from WS that is different
                            if instrument.get('wsname'):
                                self._wsname_lookup[instrument['wsname']] = market_id

                        # and start ws manager if necessary
                        try:
                            self._connector.ws.start()
                        except RuntimeError:
                            logger.debug("%s WS already started..." % self.name)

                        # user data only in real mode
                        if not self.service.paper_mode:
                            ws_token = self._connector.get_ws_token()

                            if ws_token and ws_token.get('token'):
                                self._connector.ws.subscribe_private(
                                    token=ws_token['token'],
                                    subscription='ownTrades',
                                    callback=self.__on_own_trades
                                )

                                self._connector.ws.subscribe_private(
                                    token=ws_token['token'],
                                    subscription='openOrders',
                                    callback=self.__on_open_orders
                                )
                        else:
                            # error retrieving the token, retry
                            self._ws_own_trades['timestamp'] = time.time()
                            self._ws_open_orders['timestamp'] = time.time()

                        # retry the previous subscriptions
                        if self._watched_instruments:
                            logger.debug("%s subscribe to markets data stream..." % self.name)

                            pairs = []

                            for market_id in self._watched_instruments:
                                if market_id in instruments:
                                    pairs.append(instruments[market_id]['wsname'])

                            # if pairs:
                            try:
                                self._connector.ws.subscribe_public(
                                    subscription='ticker',
                                    pair=pairs,
                                    callback=self.__on_ticker_data
                                )

                                self._connector.ws.subscribe_public(
                                    subscription='trade',
                                    pair=pairs,
                                    callback=self.__on_trade_data
                                )

                                # market spread (order book of first level)
                                if KrakenWatcher.USE_SPREAD:
                                    self._connector.ws.subscribe_public(
                                        subscription='spread',
                                        pair=pairs,
                                        callback=self.__on_spread_data
                                    )

                                # @todo order book

                                logger.debug("%s re-subscribe to markets succeed" % self.name)

                            except Exception as e:
                                error_logger.error(repr(e))
                                traceback_logger.error(traceback.format_exc())

                        # once market are init
                        self._ready = True
                        self._connecting = False

                        logger.debug("%s connection succeed" % self.name)

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

                self._ready = False
                self._connecting = False
                self._connector = None

        if self._ready and self._connector and self._connector.connected:
            self.stream_connection_status(True)
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

    def disconnect(self):
        super().disconnect()

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
                traceback_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self):
        return self._connector and self._connector.authenticated

    #
    # instruments
    #

    def subscribe(self, market_id, ohlc_depths=None, tick_depth=None, order_book_depth=None):
        if market_id not in self.__matching_symbols:
            return False

        instrument = self._instruments.get(market_id)
        if not instrument:
            return False

        # fetch from 1m to 1w
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
                            self.fetch_and_generate(market_id, Instrument.TF_15M, depth*2, Instrument.TF_30M)

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
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth*7, Instrument.TF_1W)

                        elif timeframe == Instrument.TF_MONTH:
                            self.fetch_and_generate(market_id, Instrument.TF_MONTH, depth*32, Instrument.TF_MONTH)

                    except Exception as e:
                        error_logger.error(repr(e))

            if tick_depth:
                try:
                    self.fetch_ticks(market_id, tick_depth)
                except Exception as e:
                    error_logger.error(repr(e))

        # one more watched instrument
        with self._mutex:
            self.insert_watched_instrument(market_id, [0])

            # live data
            pairs = [instrument['wsname']]

            self._connector.ws.subscribe_public(
                subscription='ticker',
                pair=pairs,
                callback=self.__on_ticker_data
            )

            self._connector.ws.subscribe_public(
                subscription='trade',
                pair=pairs,
                callback=self.__on_trade_data
            )

            # market spread (order book of first level)
            if KrakenWatcher.USE_SPREAD:
                self._connector.ws.subscribe_public(
                    subscription='spread',
                    pair=pairs,
                    callback=self.__on_spread_data
                )

            if order_book_depth and order_book_depth in (10, 25, 100, 500, 1000):
                self._connector.ws.subscribe_public(
                    subscription='book',
                    pair=pairs,
                    depth=order_book_depth,
                    callback=self.__on_depth_data
                )

        return True

    def unsubscribe(self, market_id, timeframe):
        """Unsubscribe to public market data streams for a specified market id."""
        with self._mutex:
            instruments = self._instruments

            if market_id in self._watched_instruments:
                if market_id in instruments:
                    pairs = [instruments[market_id]['wsname']]

                    self._connector.ws.unsubscribe_public('ticker', pairs)
                    self._connector.ws.unsubscribe_public('trade', pairs)

                    if KrakenWatcher.USE_SPREAD:
                        self._connector.ws.unsubscribe_public('spread', pairs)

                    self._connector.ws.unsubscribe_public('book', pairs)

                    del self._watched_instruments[market_id]

                    return True

        return False

    #
    # processing
    #

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

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, ready status to false to retry a connection
            self._ready = False
            return False

        # disconnected for user socket in real mode, and auto-reconnect failed
        # mostly in case of EGeneral:Internal Error or ESession:Invalid session
        if not self.service.paper_mode:
            if self.__check_reconnect(self._ws_own_trades) or self.__check_reconnect(self._ws_open_orders):
                logger.debug("%s try to reconnect to user trades and user orders data stream" % self.name)
                self.__reconnect_user_ws()

        # disconnected for a public socket, and auto-reconnect failed
        if self.__check_reconnect(self._ws_ticker_data):
            logger.debug("%s try to reconnect to tickers data stream" % self.name)
            self.__reconnect_ws(self._ws_ticker_data, self.__on_ticker_data, 'ticker')

        if self.__check_reconnect(self._ws_trade_data):
            logger.debug("%s try to reconnect to trades data stream" % self.name)
            self.__reconnect_ws(self._ws_trade_data, self.__on_trade_data, 'trade')

        if KrakenWatcher.USE_SPREAD:
            if self.__check_reconnect(self._ws_spread_data):
                logger.debug("%s try to reconnect to spreads data stream" % self.name)
                self.__reconnect_ws(self._ws_spread_data, self.__on_spread_data, 'spread')

        if self.__check_reconnect(self._ws_depth_data):
            logger.debug("%s try to reconnect to depths data stream" % self.name)
            self.__reconnect_ws(self._ws_depth_data, self.__on_depth_data, 'depth')

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # sync fetching
        #

        if not self.service.paper_mode:
            # asset balances (each 1m) (only in real mode)
            if time.time() - self._last_balance_update >= KrakenWatcher.UPDATE_ASSET_BALANCE_DELAY:
                try:
                    self.update_assets_balances()
                except Exception as e:
                    error_logger.error("update_assets_balances %s" % str(e))
                finally:
                    self._last_balance_update = time.time()

            # if no WS supported or activate fetch orders and positions manually and generate appropriates signals
            # @todo

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= KrakenWatcher.UPDATE_MARKET_INFO_DELAY:
            try:
                self.update_markets_info()
            except Exception as e:
                error_logger.error("update_update_markets_info %s" % str(e))
            finally:
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

            market.margin_factor = 1.0 / max(leverages) if len(leverages) > 0 else 1.0

            market.set_leverages(leverages)

            min_price = math.pow(10.0, -instrument['pair_decimals'])

            size_limits = [instrument.get('ordermin', "0.0"), "0.0", math.pow(10.0, -instrument['lot_decimals'])]
            notional_limits = ["0.0", "0.0", "0.0"]
            price_limits = [str(min_price), "0.0", str(min_price)]

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(float(notional_limits[0]), float(notional_limits[1]), float(notional_limits[2]))

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

            # @todo take the first but it might depends of the traded volume per 30 days, then
            #       request volume window to got it
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
                # from XXBTZUSD, XXBTZEUR, XETHZUSD ...
                # @todo
                pass
                # if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                #     market.base_exchange_rate = float(self._tickers_data.get(quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                # elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                #     market.base_exchange_rate = 1.0 / float(self._tickers_data.get(self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
                # else:
                #     market.base_exchange_rate = 1.0
            else:
                market.base_exchange_rate = 1.0

            # @todo contract_size and value_per_pip
            # market.contract_size = 1.0 / mid_price
            # market.value_per_pip = market.contract_size / mid_price

            # volume 24h : not have here

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
        # https://api.kraken.com/0/public/Depth
        pass

    #
    # protected
    #

    def __prefetch_markets(self):
        self._assets = self._connector.assets()
        self._instruments = self._connector.instruments()

        # map alias name to market-id, need for fetch orders, trades and positions
        markets_aliases = {}

        for market_id, instr in self._instruments.items():
            markets_aliases[instr["altname"]] = market_id

        self._markets_aliases = markets_aliases

    #
    # public trade WS
    #

    def __on_depth_data(self, data):
        # @ref https://www.kraken.com/en-us/features/websocket-api#message-book
        pass

    def __on_ticker_data(self, data):
        if isinstance(data, list) and data[2] == "ticker":
            # last update timestamp
            self._ws_ticker_data['timestamp'] = time.time()

            market_id = self._wsname_lookup.get(data[3])
            base_asset, quote_asset = data[3].split('/')

            if not market_id:
                return

            last_update_time = time.time()
            ticker = data[1]
            
            bid = float(ticker['b'][0])
            ask = float(ticker['a'][0])

            vol24_base = float(ticker['v'][0])
            vol24_quote = float(ticker['v'][0]) * float(ticker['p'][0])

            # compute base_exchange_rate (its always over primary account currency)
            # @todo
            # if quote_asset != self.BASE_QUOTE:
            #     if quote_asset in self._assets:
            #         pass  # @todo direct or indirect
            #     else:
            #         market.base_exchange_rate = 1.0  # could be EURUSD... but we don't have
            # else:
            #     market.base_exchange_rate = 1.0

            if KrakenWatcher.USE_SPREAD:
                # only update vol24h data
                market_data = (market_id, None, None, None, None, None, None, None, vol24_base, vol24_quote)
                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)
            else:
                if bid > 0.0 and ask > 0.0:
                    market_data = (market_id, last_update_time > 0, last_update_time, bid, ask,
                                   None, None, None, vol24_base, vol24_quote)
                    self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)           

        elif isinstance(data, dict):
            event = data.get('event')
            if not event:
                return

            if event == 'heartbeat':
                self._ws_ticker_data['timestamp'] = time.time()

            elif event == 'systemStatus':
                # {'connectionID': 000, 'event': 'systemStatus', 'status': 'online', 'version': '0.2.0'}
                self._ws_ticker_data['timestamp'] = time.time()
                self._ws_ticker_data['status'] = data['status']
                self._ws_ticker_data['version'] = data['version']

                logger.debug("%s connection status to tickers data stream : %s" % (self.name, data['status']))

            elif event == "subscriptionStatus":
                self._ws_ticker_data['timestamp'] = time.time()

                if data['status'] == "subscribed" and data['channelName'] == "ticker":
                    self._ws_ticker_data['subscribed'] = True
                    logger.debug("tickers data subscriptionStatus : subscribed")

                elif data['status'] == "unsubscribed" and data['channelName'] == "ticker":
                    self._ws_ticker_data['subscribed'] = False
                    logger.debug("tickers data subscriptionStatus : unsubscribed")

                elif data['status'] == "error":
                    self._ws_ticker_data['status'] = "offline"
                    self._ws_ticker_data['lost'] = True

                    error_logger.error("ticker subscriptionStatus : %s - %s" % (data.get('errorMessage'),
                                                                                data.get('name')))

    def __on_spread_data(self, data):
        if isinstance(data, list) and data[2] == "spread":
            # last update timestamp
            self._ws_spread_data['timestamp'] = time.time()

            market_id = self._wsname_lookup.get(data[3])
            base_asset, quote_asset = data[3].split('/')

            if not market_id:
                return

            spread = data[1]

            last_update_time = float(spread[2])

            bid = float(spread[0])
            ask = float(spread[1])

            # 3 is bid volume
            # 4 is ask volume

            if bid > 0.0 and ask > 0.0:
                market_data = (market_id, last_update_time > 0, last_update_time, bid, ask,
                               None, None, None, None, None)
                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

        elif isinstance(data, dict):
            event = data.get('event')
            if not event:
                return

            if event == 'heartbeat':
                self._ws_spread_data['timestamp'] = time.time()

            elif event == 'systemStatus':
                # {'connectionID': 000, 'event': 'systemStatus', 'status': 'online', 'version': '0.2.0'}
                self._ws_spread_data['timestamp'] = time.time()
                self._ws_spread_data['status'] = data['status']
                self._ws_spread_data['version'] = data['version']

                logger.debug("%s connection status to spreads data stream : %s" % (self.name, data['status']))

            elif event == "subscriptionStatus":
                self._ws_spread_data['timestamp'] = time.time()

                if data['status'] == "subscribed" and data['channelName'] == "spread":
                    self._ws_spread_data['subscribed'] = True
                    logger.debug("spreads data subscriptionStatus : subscribed")

                elif data['status'] == "unsubscribed" and data['channelName'] == "spread":
                    self._ws_spread_data['subscribed'] = False
                    logger.debug("spreads data subscriptionStatus : unsubscribed")

                elif data['status'] == "error":
                    self._ws_spread_data['status'] = "offline"
                    self._ws_spread_data['lost'] = True

                    error_logger.error("spread subscriptionStatus : %s - %s" % (data.get('errorMessage'),
                                                                                data.get('name')))

    def __on_trade_data(self, data):
        if isinstance(data, list) and data[2] == "trade":
            # last update timestamp
            self._ws_trade_data['timestamp'] = time.time()

            market_id = self._wsname_lookup.get(data[3])

            if not market_id:
                return

            for trade in data[1]:
                price = float(trade[0])
                vol = float(trade[1])
                trade_time = float(trade[2])
                bid_ask = 0
                spread = 0.0

                # bid or ask depending of order direction and type
                if trade[3] == 'b' and trade[4] == 'l':
                    bid_ask = -1
                elif trade[3] == 'b' and trade[4] == 'm':
                    bid_ask = 1
                if trade[3] == 's' and trade[4] == 'l':
                    bid_ask = 1
                if trade[3] == 's' and trade[4] == 'm':
                    bid_ask = -1

                tick = (trade_time, price, price, price, vol, bid_ask)

                # store for generation of OHLCs
                self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (market_id, tick))

                if self._store_trade:
                    Database.inst().store_market_trade((self.name, market_id, int(trade_time*1000.0),
                                                        trade[0], trade[0], trade[0], trade[1], bid_ask))

                for tf in Watcher.STORED_TIMEFRAMES:
                    # generate candle per timeframe
                    with self._mutex:
                        candle = self.update_ohlc(market_id, tf, trade_time, price, spread, vol)

                    if candle is not None:
                        self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, candle))

        elif isinstance(data, dict):
            event = data.get('event')
            if not event:
                return

            if event == 'heartbeat':
                self._ws_trade_data['timestamp'] = time.time()

            elif event == 'systemStatus':
                # {'connectionID': 000, 'event': 'systemStatus', 'status': 'online', 'version': '0.2.0'}
                self._ws_trade_data['timestamp'] = time.time()
                self._ws_trade_data['status'] = data['status']
                self._ws_trade_data['version'] = data['version']

                logger.debug("%s connection status to trades data stream : %s" % (self.name, data['status']))

            elif event == "subscriptionStatus":
                self._ws_trade_data['timestamp'] = time.time()

                if data['status'] == "subscribed" and data['channelName'] == "trade":
                    self._ws_trade_data['subscribed'] = True
                    logger.debug("trades data subscriptionStatus : subscribed")

                elif data['status'] == "unsubscribed" and data['channelName'] == "trade":
                    self._ws_trade_data['subscribed'] = False
                    logger.debug("trades data subscriptionStatus : unsubscribed")

                elif data['status'] == "error":
                    self._ws_trade_data['status'] = "offline"
                    self._ws_trade_data['lost'] = True

                    error_logger.error("trades subscriptionStatus : %s - %s" % (data.get('errorMessage'),
                                                                                data.get('name')))

    def __on_kline_data(self, data):
        pass

    #
    # private trade/position WS
    #

    def __update_position_cache(self, position_id, new_position_data):
        position_data_cache = self._positions_ws_cache.get(position_id)
        status = new_position_data['posstatus']

        if position_data_cache:
            # update the cached data
            self._positions_ws_cache[position_id] = new_position_data

            # remove from cache if Closing
            if status == "Closing":
                del self._positions_ws_cache[position_id]

            # exists, data
            return status == "Opened", new_position_data
        else:
            # add to cache if Opened
            if status == "Opened":
                self._positions_ws_cache[position_id] = new_position_data

            # exists, data
            return status == "Opened", new_position_data

    def __del_position_cache(self, position_id):
        if position_id in self._positions_ws_cache:
            del self._positions_ws_cache[position_id]

    def __on_own_trades(self, data):
        if isinstance(data, list) and data[1] == "ownTrades":
            # last update timestamp
            self._ws_own_trades['timestamp'] = time.time()

            if not self._got_trades_init_snapshot:
                # ignore the initial snapshot (got them through REST api), but keep open positions for the cache
                for entry in data[0]:
                    # only single object per entry
                    trade_id, trade_data = next(iter(entry.items()))

                    if trade_data.get('posstatus'):
                        position_id = trade_data['postxid']
                        self.__update_position_cache(position_id, trade_data)

                self._got_trades_init_snapshot = True

                return

            for entry in data[0]:
                # only single object per entry
                trade_id, trade_data = next(iter(entry.items()))

                exec_logger.info("kraken.com ownTrades : %s - %s" % (trade_id, trade_data))

                symbol = self._wsname_lookup.get(trade_data['pair'])

                if not symbol:
                    continue

                if trade_data.get('posstatus'):
                    order_id = trade_data['ordertxid']
                    client_order_id = str(trade_data['userref']) if trade_data.get('userref') else ""
                    position_id = trade_data['postxid']

                    self.__update_position_cache(position_id, trade_data)

                    timestamp = float(trade_data['time'])
                    posstatus = trade_data['posstatus']

                    price = None
                    stop_price = None

                    if trade_data['ordertype'] == "limit":
                        order_type = Order.ORDER_LIMIT
                    elif trade_data['ordertype'] == "stop-loss":
                        order_type = Order.ORDER_STOP
                    elif trade_data['ordertype'] == "take-profit":
                        order_type = Order.ORDER_TAKE_PROFIT
                    elif trade_data['ordertype'] == "stop-loss-limit":
                        order_type = Order.ORDER_STOP_LIMIT
                    elif trade_data['ordertype'] == "take-profit-limit":
                        order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    elif trade_data['ordertype'] == "market":
                        order_type = Order.ORDER_MARKET
                    else:
                        order_type = Order.ORDER_MARKET

                    exec_vol = float(trade_data['vol'])
                    exec_price = float(trade_data['price'])
                    fee = float(trade_data['fee'])  # in quote (or base depend of order)

                    # trade
                    order = {
                        'id': order_id,
                        'symbol': symbol,
                        'type': order_type,
                        'trade-id': trade_id,
                        'direction': Order.LONG if trade_data['type'] == 'buy' else Order.SHORT,
                        'timestamp': timestamp,
                        'exec-price': exec_price,
                        'filled': exec_vol,
                        # 'cumulative-filled': ,
                        'quote-transacted': float(trade_data['cost']),
                        'commission-amount': fee,
                        # 'commission-asset': , is quote
                        # 'maker': ,   # trade execution over or counter the market : true if maker, false if taker
                        # 'fully-filled':   # fully filled status else its partially
                    }

                    # self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

                    # position
                    # @todo
                    # 'margin': used margin
                    # 'cost': size in quote

                    position_data = {
                        'id': position_id,
                        'symbol': symbol,
                        'direction': Order.LONG if trade_data['type'] == 'buy' else Order.SHORT,
                        'timestamp': timestamp,
                        'stop-loss': None,
                        'take-profit': None,
                        # 'avg-entry-price': ,
                        'exec-price': exec_price,
                        'filled': exec_vol,  # no have
                        # 'cumulative-filled': ,
                        'liquidation-price': None,  # no have
                        'commission': fee,
                        # 'profit-currency': self.BASE_QUOTE,
                        # 'profit-loss': float(pos['up']),
                        'profit-loss-rate': None,
                    }

                    # if posstatus == 'Closing':
                    #     pass  # @todo

                    #     # position closed...
                    #     # self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (symbol, position_data, client_order_id))
                    #     # self.service.notify(Signal.SIGNAL_POSITION_CLOSED, self.name, (symbol, position_data, client_order_id))

                    # elif posstatus == 'Opened':
                    #     pass  # @todo   

                    #     # position opened...
                    #     # self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (symbol, position_data, client_order_id))
                    #     # self.service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (symbol, position_data, client_order_id))
                else:
                    # spot order traded (partial or full). for now we use the trade update message
                    order_id = trade_data['ordertxid']
                    client_order_id = str(trade_data['userref']) if trade_data.get('userref') else ""
                    timestamp = float(trade_data['time'])

                    price = None
                    stop_price = None

                    if trade_data['ordertype'] == "limit":
                        order_type = Order.ORDER_LIMIT
                    elif trade_data['ordertype'] == "stop-loss":
                        order_type = Order.ORDER_STOP
                    elif trade_data['ordertype'] == "take-profit":
                        order_type = Order.ORDER_TAKE_PROFIT
                    elif trade_data['ordertype'] == "stop-loss-limit":
                        order_type = Order.ORDER_STOP_LIMIT
                    elif trade_data['ordertype'] == "take-profit-limit":
                        order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    elif trade_data['ordertype'] == "market":
                        order_type = Order.ORDER_MARKET
                    else:
                        order_type = Order.ORDER_MARKET

                    order = {
                        'id': order_id,
                        'symbol': symbol,
                        'type': order_type,
                        'trade-id': trade_id,
                        'direction': Order.LONG if trade_data['type'] == 'buy' else Order.SHORT,
                        'timestamp': timestamp,
                        'exec-price': float(trade_data['price']),
                        'filled': float(trade_data['vol']),
                        # 'cumulative-filled': ,
                        'quote-transacted': float(trade_data['cost']),
                        'commission-amount': float(trade_data['fee']),
                        # 'commission-asset': , is quote
                        # 'maker': ,   # trade execution over or counter the market : true if maker, false if taker
                        # 'fully-filled':   # fully filled status else its partially
                    }

                    # @todo
                    # self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

        elif isinstance(data, dict):
            event = data.get('event')
            if not event:
                return

            if event == 'heartbeat':
                self._ws_own_trades['timestamp'] = time.time()

            elif event == 'systemStatus':
                # {'connectionID': 000, 'event': 'systemStatus', 'status': 'online', 'version': '0.2.0'}
                self._ws_own_trades['timestamp'] = time.time()
                self._ws_own_trades['status'] = data['status']
                self._ws_own_trades['version'] = data['version']

                logger.debug("%s connection status to user trades stream : %s" % (self.name, data['status']))

            elif event == "subscriptionStatus":
                self._ws_own_trades['timestamp'] = time.time()

                if data['status'] == "subscribed" and data['channelName'] == "ownTrades":
                    self._ws_own_trades['subscribed'] = True
                    logger.debug("user trades data subscriptionStatus : subscribed")

                elif data['status'] == "unsubscribed" and data['channelName'] == "ownTrades":
                    self._ws_own_trades['subscribed'] = False
                    logger.debug("user trades data subscriptionStatus : unsubscribed")

                elif data['status'] == "error":
                    self._ws_own_trades['status'] = "offline"
                    self._ws_own_trades['lost'] = True

                    error_logger.error("ownTrades subscriptionStatus : %s - %s" % (data.get('errorMessage'),
                                                                                   data.get('name')))

    #
    # private order WS
    #

    def __set_order(self, symbol, order_id, order_data):
        descr = order_data['descr']

        price = None
        stop_price = None

        if descr['ordertype'] == "limit":
            order_type = Order.ORDER_LIMIT
            price = float(descr['price']) if 'price' in descr else None

        elif descr['ordertype'] == "stop-loss":
            order_type = Order.ORDER_STOP
            stop_price = float(descr['price']) if 'price' in descr else None

        elif descr['ordertype'] == "take-profit":
            order_type = Order.ORDER_TAKE_PROFIT
            top_price = float(descr['price']) if 'price' in descr else None

        elif descr['ordertype'] == "stop-loss-limit":
            order_type = Order.ORDER_STOP_LIMIT
            price = float(descr['price2']) if 'price2' in descr else None
            stop_price = float(descr['price']) if 'price' in descr else None

        elif descr['ordertype'] == "take-profit-limit":
            order_type = Order.ORDER_TAKE_PROFIT_LIMIT
            price = float(descr['price2']) if 'price2' in descr else None
            stop_price = float(descr['price']) if 'price' in descr else None

        elif descr['ordertype'] == "market":
            order_type = Order.ORDER_MARKET

        else:
            order_type = Order.ORDER_MARKET

        time_in_force = Order.TIME_IN_FORCE_GTC
        partial = False

        if order_data['expiretm'] is not None and order_data['expiretm'] > 0:
            time_in_force = Order.TIME_IN_FORCE_GTD
            expiry = float(order_data['expiretm'])

        if descr['leverage'] is not None and descr['leverage'] != 'none':
            margin_trade = True
            leverage = int(descr['leverage'])
        else:
            margin_trade = False
            leverage = 0

        executed = float(order_data.get('vol_exec', "0.0"))
        post_only = False
        commission_asset_is_quote = True

        if order_data['oflags']:
            flags = order_data['oflags'].split(',')
       
            if 'fcib' in flags:
                # fee in base currency
                commission_asset_is_quote = False

            elif 'fciq' in flags:
                # fee in quote currency:
                commission_asset_is_quote = True

            if 'post' in flags:
                post_only = True

        # conditional close
        # if descr['close']:
        #     pass  # @todo

        # most of the event are update, except for the open event where it is replace by opentm
        event_timestamp = float(order_data['lastupdated']) if 'lastupdated' in order_data else time.time()

        return {
            'id': order_id,
            'symbol': symbol,
            'direction': Order.LONG if descr['type'] == "buy" else Order.SHORT,
            'type': order_type,
            'timestamp': event_timestamp,
            'quantity': float(order_data.get('vol', "0.0")),
            'price': price,
            'stop-price': stop_price,
            'time-in-force': time_in_force,
            'post-only': post_only,
            # 'close-only': ,
            # 'reduce-only': ,
            'stop-loss': None,
            'take-profit': None
        }

    def __fill_order(self, order, order_data, filled_volume, completed=False):
        if filled_volume > 0.0 or completed:
            cumulative_filled = float(order_data['vol_exec'])
            order_volume = float(order_data['vol'])
            partial = False
            fully_filled = completed

            if order_data['misc']:
                misc = order_data['misc'].split(',')

                if 'partial' in misc:
                    partial = True

            if cumulative_filled >= order_volume and not partial:
                fully_filled = True

            order['timestamp'] = float(order_data['lastupdated']) if 'lastupdated' in order_data else time.time()
            order['exec-price'] = float(order_data['avg_price'])
            order['filled'] = filled_volume
            order['cumulative-filled'] = cumulative_filled
            order['cumulative-commission-amount'] = float(order_data['fee'])
            # order['commission-asset'] =   # is quote symbol because order always use quote fee flag
            # order['maker'] =    # trade execution over or counter the market : true if maker, false if taker
            order['fully-filled'] = fully_filled

        return order

    def __update_order_cache(self, order_id, new_order_data):
        order_data_cache = self._orders_ws_cache.get(order_id)

        opened = False
        new_exec_vol = 0.0

        if order_data_cache:
            # detect a diff in executed volume
            prev_exec_vol = 0.0

            if 'vol_exec' in order_data_cache:
                prev_exec_vol = float(order_data_cache['vol_exec'])

            if 'vol_exec' in new_order_data:
                new_exec_vol = float(new_order_data['vol_exec'])

            filled_volume = new_exec_vol - prev_exec_vol

            # status changed
            if 'status' in new_order_data:
                # remove from cache if closed, canceled or deleted
                if new_order_data['status'] in ("closed", "deleted", "canceled"):
                    del self._orders_ws_cache[order_id]

                # or open state
                if new_order_data['status'] == "open":
                    if 'status' in order_data_cache:
                        if order_data_cache['status'] == "pending":
                            # was pending, now its open : opened state for signal
                            opened = True
                    else:
                        # no previous status in cache : opened state for signal
                        opened = True

            # update the cached data
            order_data_cache.update(new_order_data)

            # executed vol diff (can be 0), data are updated
            return opened, filled_volume, order_data_cache
        else:
            # add to cache if pending or opened
            if ('status' in new_order_data) and (new_order_data['status'] in ("pending", "open")):
                self._orders_ws_cache[order_id] = new_order_data

                # first for open state (sometime it doesnt have pending state so we direct opened from here)
                if new_order_data['status'] == "open":
                    opened = True

            if 'vol_exec' in new_order_data:
                new_exec_vol = float(new_order_data['vol_exec'])

            filled_volume = new_exec_vol

            return opened, filled_volume, new_order_data

    def __del_order_cache(self, order_id):
        if order_id in self._orders_ws_cache:
            del self._orders_ws_cache[order_id]

    def __on_open_orders(self, data):
        if isinstance(data, list) and data[1] == "openOrders":
            # last update timestamp
            self._ws_open_orders['timestamp'] = time.time()

            if not self._got_orders_init_snapshot:
                # ignore the initial snapshot (got them through REST api)
                self._got_orders_init_snapshot = True

                for entry in data[0]:
                    # only single object per entry
                    order_id, order_data = next(iter(entry.items()))

                    # cache the initials entries
                    self.__update_order_cache(order_id, order_data)

                return

            for entry in data[0]:
                # only single object per entry
                order_id, order_data = next(iter(entry.items()))

                exec_logger.info("kraken.com openOrders : %s - %s" % (order_id, order_data))

                opened, filled_volume, order_data = self.__update_order_cache(order_id, order_data)

                if 'descr' not in order_data:
                    # no have previous message to tell the symbol
                    error_logger.warning(
                        "kraken.com openOrder : Could not retrieve the description for %s. Message ignored !" % (
                            order_id,))
                    continue

                symbol = self._wsname_lookup.get(order_data['descr']['pair'])

                if not symbol:
                    # not managed symbol
                    error_logger.warning(
                        "kraken.com openOrder : Could not retrieve the symbol for %s. Message ignored !" % (order_id,))
                    continue

                status = order_data.get('status', "")

                if status == "pending":
                    # nothing is done here, waiting for a rejection or open
                    pass

                elif status == "open":
                    # only if we have the order in a pending state at a previous msg
                    client_order_id = str(order_data['userref']) if order_data.get('userref') else ""
                    order = self.__set_order(symbol, order_id, order_data)

                    if opened:
                        # uses the open timestamp only for the OPENED signal
                        order['timestamp'] = float(order_data['opentm']) 
                        self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (symbol, order, client_order_id))

                    if filled_volume > 0.0:
                        self.__fill_order(order, order_data, filled_volume)
                        self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

                elif status == "closed":
                    client_order_id = str(order_data['userref']) if order_data.get('userref') else ""
                    order = self.__set_order(symbol, order_id, order_data)

                    # last fill with fully-filled state, before deleted signal
                    self.__fill_order(order, order_data, filled_volume, True)
                    self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

                    self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (symbol, order_id, client_order_id))

                elif status == "updated":
                    client_order_id = str(order_data['userref']) if order_data.get('userref') else ""
                    order = self.__set_order(symbol, order_id, order_data)

                    self.service.notify(Signal.SIGNAL_ORDER_UPDATED, self.name, (symbol, order, client_order_id))

                    if filled_volume > 0.0:
                        self.__fill_order(order, order_data, filled_volume)
                        self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

                elif status == "deleted":
                    client_order_id = str(order_data['userref']) if order_data.get('userref') else ""
                    order = self.__set_order(symbol, order_id, order_data)

                    if filled_volume > 0.0:
                        self.__fill_order(order, order_data, filled_volume)
                        self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, client_order_id))

                    self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (symbol, order_id, ""))

                elif status == "canceled":
                    client_order_id = str(order_data['userref']) if order_data.get('userref') else ""

                    self.service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (symbol, order_id, client_order_id))

        elif isinstance(data, dict):
            event = data.get('event')
            if not event:
                return

            if event == 'heartbeat':
                self._ws_open_orders['timestamp'] = time.time()

            elif event == 'systemStatus':
                # {'connectionID': 000, 'event': 'systemStatus', 'status': 'online', 'version': '0.2.0'}
                self._ws_open_orders['timestamp'] = time.time()
                self._ws_open_orders['status'] = data['status']
                self._ws_open_orders['version'] = data['version']

                logger.debug("%s connection status to user orders stream : %s" % (self.name, data['status']))

            elif event == "subscriptionStatus":
                self._ws_open_orders['timestamp'] = time.time()

                if data['status'] == "subscribed" and data['channelName'] == "openOrders":
                    self._ws_open_orders['subscribed'] = True
                    logger.debug("user orders data subscriptionStatus : subscribed")

                elif data['status'] == "unsubscribed" and data['channelName'] == "openOrders":
                    self._ws_open_orders['subscribed'] = False
                    logger.debug("user orders data subscriptionStatus : unsubscribed")

                elif data['status'] == "error":
                    self._ws_open_orders['status'] = "offline"
                    self._ws_open_orders['lost'] = True

                    error_logger.error("kraken.com openOrders:openOrders subscriptionStatus : %s - %s" % (
                        data.get('errorMessage'), data.get('name')))

            elif event == "addOrderStatus":
                self._ws_open_orders['timestamp'] = time.time()

                if data['status'] == "error":
                    error_logger.error("kraken.com openOrders:addOrderStatus : %s - %s" % (
                        data.get('errorMessage'), data.get('name')))

                    # already get in REST response
                    # self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (symbol, client_order_id))

                elif data['status'] == "ok":
                    trade_id = data['txid']

                    exec_logger.info("kraken.com openOrders:addOrderStatus : %s" % (trade_id,))

            elif event == "cancelOrderStatus":
                self._ws_open_orders['timestamp'] = time.time()

                if data['status'] == "error":
                    error_logger.error("kraken.com openOrders:cancelOrderStatus : %s - %s" % (
                        data.get('errorMessage'), data.get('name')))

                elif data['status'] == "ok":
                    order_ids = data['txid']  # array of order_id

                    exec_logger.info("kraken.com openOrders:cancelOrderStatus ids : %s" % (repr(order_ids),))

            elif event == "cancelAllStatus":
                self._ws_open_orders['timestamp'] = time.time()

                if data['status'] == "error":
                    error_logger.error("cancelAllStatus : %s - %s" % (data.get('errorMessage'), data.get('name')))

                elif data['status'] == "ok":
                    canceled_orders_count = data['count']

                    exec_logger.info("kraken.com openOrders:cancelAllStatus : %s orders" % (canceled_orders_count,))

    #
    # misc
    #

    def market_alias(self, market_id):
        return self._markets_aliases.get(market_id)

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        return None

    def update_markets_info(self):
        """
        Update market info.
        """
        with self._mutex:
            try:
                self.__prefetch_markets()
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

                return

        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market.is_open:
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ask,
                               market.base_exchange_rate, market.contract_size, market.value_per_pip,
                               market.vol24h_base, market.vol24h_quote)
            else:
                market_data = (market_id, market.is_open, market.last_update_time,
                               None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def update_assets_balances(self):
        """
        Update asset balance.

        @note Non thread-safe because only called at each sync update.
        """
        balances = self._connector.get_balances()

        for asset_name, balance in balances.items():
            if asset_name not in self._last_assets_balances:
                # initiate cache
                self._last_assets_balances[asset_name] = [0.0, 0.0]  # locked, free

            asset = self._last_assets_balances[asset_name]

            # use the last computed locked value from opened orders using this asset
            locked = asset[0]
            free = float(balance) - locked

            if locked != asset[0] or free != asset[1]:
                # update cache for next comparison
                asset[0] = locked
                asset[1] = free

                # asset updated
                self.service.notify(Signal.SIGNAL_ASSET_UPDATED, self.name, (asset_name, locked, free))

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        trades = []

        try:
            trades = self._connector.get_historical_trades(market_id, from_date, to_date)
        except Exception as e:
            logger.error("Watcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            yield trade

        logger.info("Watcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        if timeframe not in self.TF_MAP:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe_to_str(timeframe)))
            return

        candles = []

        # second timeframe to kraken interval
        interval = self.TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, interval, from_date, to_date)
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s" % (self.name, interval, market_id))
            traceback_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open, high, low, close, spread, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield candle[0], candle[1], candle[2], candle[3], candle[4], candle[5], candle[6]

        logger.info("Watcher %s has retrieved on market %s %s candles for timeframe %s" % (
            self.name, market_id, count, timeframe_to_str(timeframe)))
