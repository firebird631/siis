# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# www.bitmex.com watcher implementation

import re
import json
import time
import traceback
import math

from datetime import datetime
from common.utils import UTC

from watcher.watcher import Watcher
from common.signal import Signal

from connector.bitmex.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.bitmex')
exec_logger = logging.getLogger('siis.exec.bitmex')
error_logger = logging.getLogger('siis.error.bitmex')


class BitMexWatcher(Watcher):
    """
    BitMex market watcher using REST + WS.
    @note No having historical data fetching.

    Month code = F (jan) G H J K M N Q U V X Z (dec)

    @ref https://www.bitmex.com/app/wsAPI#All-Commands
    """

    EXPIRY_RE = re.compile(r'^(.{3})([FGHJKMNQUVXZ])(\d\d)$')

    def __init__(self, service):
        super().__init__("bitmex.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None

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
                            identity.get('api-key'),
                            identity.get('api-secret'),
                            self.configured_symbols(),  # want WS subscribes to thats instruments or all if ['*']
                            identity.get('host'),
                            (self, BitMexWatcher._ws_message))
                    else:
                        # to get a clean connection
                        self._connector.disconnect()

                    # testnet (demo) server doesn't provided real prices, so never store info from it !
                    if identity.get('host') == 'testnet.bitmex.com':
                        self._store_ohlc = False
                        self._store_trade = False

                    if not self._connector.connected or not self._connector.ws_connected:
                        self._connector.connect()

                    # get list of all availables instruments, and list of subscribed
                    self._available_instruments = set(self._connector.all_instruments)
                    self._watched_instruments = set(self._connector.watched_instruments)

                    # any markets are watched by default WS connection

                    self._ready = True
                    self._connecting = False

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

        if self._connector and self._connector.connected and self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

    def disconnect(self):
        super().disconnect()

        with self._mutex:
            try:
                if self._connector:
                    self._connector.disconnect()
                    self._connector = None
            
                self._ready = False

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

                    # any configured market are subscribed at ws connection
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

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= BitMexWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
            try:
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

    #
    # instruments
    #

    def subscribe(self, market_id, ohlc_depths=None, tick_depth=None, order_book_depth=None):
        if market_id in self._watched_instruments:
            # subscribed instrument
            self.insert_watched_instrument(market_id, [0])

            # fetch from source
            if self._initial_fetch:
                logger.info("%s prefetch for %s" % (self.name, market_id))

                if ohlc_depths:
                    for timeframe, depth in ohlc_depths.items():
                        if timeframe >= Instrument.TF_1M and timeframe <= Instrument.TF_3M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth * 3, Instrument.TF_3M)
                        
                        elif timeframe >= Instrument.TF_5M and timeframe <= Instrument.TF_30M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth * 6, Instrument.TF_30M)
                        
                        elif timeframe >= Instrument.TF_1H and timeframe <= Instrument.TF_4H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth * 4, Instrument.TF_4H)
                        
                        elif timeframe >= Instrument.TF_1D and timeframe <= Instrument.TF_1W:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth * 7, Instrument.TF_1W)

                if tick_depth:
                    self.fetch_ticks(market_id, tick_depth)

                # debug only
                # if market_id == "XBTUSD":
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*5)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*15)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*60)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*60*4)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*60*2)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*60*24)))
                #     logger.info(str(self._last_ohlc["XBTUSD"].get(60*60*24*7)))

            # connector by default any
            # nothing to do, see connector

            return True
        else:
            return False

    def unsubscribe(self, market_id, timeframe):
        with self._mutex:
            if market_id in self._watched_instruments:
                # connector by default any
                return True
            else:
                return False

    #
    # private
    #

    def _parse_datetime(self, date_str):
        return datetime.strptime(date_str or '1970-01-01 00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%fZ")

    #
    # protected
    #

    @staticmethod
    def _ws_message(self, message, data):
        if message == 'action':
            #
            # account data update
            #
            
            if (data[1] == 'margin'):
                funds = self.connector.ws.funds()
                ratio = 1.0
                currency = funds['currency']

                # convert XBt to BTC
                if currency == 'XBt':
                    ratio = 1.0 / 100000000.0
                    currency = 'XBT'

                # walletBalance or amount, riskLimit is max leverage
                account_data = (
                        funds['walletBalance']*ratio, funds['marginBalance']*ratio, funds['unrealisedPnl']*ratio,
                        currency, funds['riskLimit']*ratio)

                self.service.notify(Signal.SIGNAL_ACCOUNT_DATA, self.name, account_data)

            elif (data[1] == 'liquidation') and (data[0] == 'insert'):  # action
                exec_logger.info("bitmex l226 liquidation > %s " % str(data))

                for ld in data[3]:
                    # data[3]['orderID']
                    # symbol is market-id, side is the liquidation order direction, then the initial liquided order was in the opposite
                    liquidation_data = (
                        ld['symbol'],
                        time.time(),
                        1 if ld['side'] == "Buy" else -1,
                        ld['price'],
                        ld['leavesQty'])

                    self.service.notify(Signal.SIGNAL_LIQUIDATION_DATA, self.name, liquidation_data)

                    Database.inst().store_market_liquidation((self.name, liquidation_data[0],
                        int(liquidation_data[1]*1000.0),
                        liquidation_data[2],
                        liquidation_data[3],
                        liquidation_data[4]))

            #
            # orders partial execution
            #

            if (data[1] == 'execution') and data[2]:
                for ld in data[3]:
                    exec_logger.info("bitmex l185 execution > %s" % str(ld))

            #
            # positions
            #

            elif (data[1] == 'position'):  # action
                for ld in data[3]:
                    ref_order_id = ""
                    symbol = ld['symbol']
                    position_id = symbol

                    # 'leverage': 10, 'crossMargin': False

                    if ld.get('currentQty') is None:
                        # no position
                        continue

                    # exec_logger.info("bitmex.com position %s" % str(ld))

                    if ld.get('currentQty', 0) != 0:
                        direction = Order.SHORT if ld['currentQty'] < 0 else Order.LONG
                    elif ld.get('openOrderBuyQty', 0) > 0:
                        direction = Order.LONG
                    elif ld.get('openOrderSellQty', 0) > 0:
                        direction = Order.SHORT
                    else:
                        direction = 0

                    operation_time = self._parse_datetime(ld.get('timestamp')).replace(tzinfo=UTC()).timestamp()
                    quantity = abs(float(ld['currentQty']))

                    # 'execQty': ?? 'execBuyQty', 'execSellQty': ??
                    # 'commission': 0.00075 'execComm': 0 ?? 'currentComm': 0

                    position_data = {
                        'id': symbol,
                        'symbol': symbol,
                        'direction': direction,
                        'timestamp': operation_time,
                        'quantity': quantity,
                        'avg-entry-price': ld.get('avgEntryPrice', None),
                        'exec-price': None,
                        'stop-loss': None,
                        'take-profit': None,
                        'cumulative-filled': quantity,
                        'filled': None,  # no have
                        'liquidation-price': ld.get('liquidationPrice'),
                        'commission': ld.get('commission', 0.0),
                        'profit-currency': ld.get('currency'),
                        'profit-loss': ld.get('unrealisedPnl'),
                        'profit-loss-rate': ld.get('unrealisedPnlPcnt')
                    }

                    if (ld.get('openOrderBuyQty', 0) or ld.get('openOrderSellQty', 0)) and quantity == 0.0:
                        # not current quantity, but open order qty
                        self.service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (symbol, position_data, ref_order_id))
                    elif quantity > 0:
                        # current qty updated
                        self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (symbol, position_data, ref_order_id))
                    else:
                        # empty quantity no open order qty, position deleted
                        self.service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (symbol, position_data, ref_order_id))

            #
            # orders
            #

            elif (data[1] == 'order'):
                for ld in data[3]:
                    exec_logger.info("bitmex.com order %s" % str(ld))

                    symbol = ld.get('symbol')
                    status = ld.get('ordStatus', None)

                    if not status:  # updated
                        operation_time = self._parse_datetime(ld.get('timestamp')).replace(tzinfo=UTC()).timestamp()

                        # quantity or price modified
                        if (ld.get('orderQty') or ld.get('price') or ld.get('stopPx')) and ld.get('workingIndicator'):
                            order = {
                                'id': ld['orderID'],
                                'symbol': symbol,
                                'timestamp': operation_time,
                                'quantity': ld.get('orderQty', None),
                                'price': ld.get('price'),
                                'stop-price': ld.get('stopPx'),
                                'stop-loss': None,
                                'take-profit': None
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_UPDATED, self.name, (symbol, order, ""))

                    elif status == 'New':  # action='insert'
                        transact_time = self._parse_datetime(ld.get('transactTime')).replace(tzinfo=UTC()).timestamp()

                        if ld['ordType'] == 'Market':
                            order_type = Order.ORDER_MARKET
                        elif ld['ordType'] == 'Limit':
                            order_type = Order.ORDER_LIMIT
                        elif ld['ordType'] == 'Stop':
                            order_type = Order.ORDER_STOP
                        elif ld['ordType'] == 'StopLimit':
                            order_type = Order.ORDER_STOP_LIMIT
                        elif ld['ordType'] == 'MarketIfTouched':
                            order_type = Order.ORDER_TAKE_PROFIT
                        elif ld['ordType'] == 'LimitIfTouched':
                            order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                        else:
                            order_type = Order.ORDER_MARKET

                        if ld['timeInForce'] == 'GoodTillCancel':
                            time_in_force = Order.TIME_IN_FORCE_GTC
                        elif ld['timeInForce'] == 'ImmediateOrCancel':
                            time_in_force = Order.TIME_IN_FORCE_IOC
                        elif ld['timeInForce'] == 'FillOrKill':
                            time_in_force = Order.TIME_IN_FORCE_FOK
                        else:
                            time_in_force = Order.TIME_IN_FORCE_GTC

                        # execution options
                        exec_inst = ld.get('execInst', '').split(',')

                        # execution price
                        if 'LastPrice' in exec_inst:
                            price_type = Order.PRICE_LAST
                        elif 'IndexPrice' in exec_inst:
                            price_type = Order.PRICE_MARK
                        elif 'MarkPrice' in exec_inst:
                            price_type = Order.PRICE_INDEX
                        else:
                            price_type = Order.PRICE_LAST

                        order = {
                            'id': ld['orderID'],
                            'symbol': symbol,
                            'direction': Order.LONG if ld['side'] == 'Buy' else Order.SHORT,
                            'type': order_type,
                            'timestamp': transact_time,
                            'quantity': ld.get('orderQty', 0),
                            'price': ld.get('price'),
                            'stop-price': ld.get('stopPx'),
                            'time-in-force': time_in_force,
                            'post-only': 'ParticipateDoNotInitiate' in exec_inst,  # maker only (not taker)
                            'close-only': 'Close' in exec_inst,
                            'reduce-only': 'ReduceOnly' in exec_inst,
                            'price-type': price_type,
                            'stop-loss': None,
                            'take-profit': None
                        }

                        self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (symbol, order, ld.get('clOrdID', "")))

                    elif status == 'Canceled':  # action='update'
                        self.service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (symbol, ld['orderID'], ld.get('clOrdID', "")))

                    elif status == 'Rejected':  # action='update'
                        reason = ""

                        if ld.get('ordRejReason') == 'INSUFFICIENT_BALANCE':
                            reason = 'insufficient balance'

                        self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (symbol, ld.get('clOrdID', "")))

                    elif status == 'Filled':  # action='update'
                        operation_time = datetime.strptime(ld.get('timestamp', '1970-01-01 00:00:00.000Z'), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC()).timestamp()
                        # 'workingIndicator': False, if fully filled
                        #  'leavesQty': 0, if fully filled
                        # 'currency': 'XBT', 'settlCurrency': 'XBt', 'triggered': '', 'simpleLeavesQty': None, 'leavesQty': 10000, 'simpleCumQty': None, 'cumQty': 0, 'avgPx': None, ...

                        order = {
                          'id': ld['orderID'],
                          'symbol': symbol,
                          # 'direction': direction,  # no have
                          'timestamp': operation_time,
                          'quantity': ld.get('orderQty', 0.0),
                          'filled': None,  # no have
                          'cumulative-filled': ld.get('cumQty', 0),
                          'exec-price': None,  # no have
                          'avg-price': ld.get('avgPx', 0),  # averaged for the cumulative
                          # 'maker': ,   # trade execution over or counter the market : true if maker, false if taker
                        }

                        self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, ld.get('clOrdID', "")))

            #
            # market
            #

            elif (data[1] == 'trade') and (data[0] == 'insert' or data[0] == 'update'):
                # exec_logger.info("bitmex.com trade %s" % str(data))

                for trade in data[3]:
                    # trade data
                    market_id = trade['symbol']
                    trade_time = datetime.strptime(trade['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC()).timestamp()
                    # direction = Order.LONG if trade['side'] == 'Buy' else Order.SHORT
                    volume = trade['size']
                    price = trade['price']
                    spread = 0.0  # @todo
                    # trade_id = trade['trdMatchID']
                    # trade['homeNotional']  # 0.4793 value in XBT

                    # PlusTick,MinusTick,ZeroPlusTick,ZeroMinusTick
                    bid_ask = 0

                    if trade['tickDirection'] in ('PlusTick', 'ZeroPlusTick'):
                        bid_ask = 1
                    elif trade['tickDirection'] in ('MinusTick', 'ZeroMinusTick'):
                        bid_ask = -1

                    # we have a tick when we have a volume in data content
                    tick = (trade_time, price, price, price, volume, bid_ask)

                    # and notify
                    self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (market_id, tick))

                    if self._store_trade:
                        # store trade
                        Database.inst().store_market_trade((self.name, symbol, int(trade_time*1000), price, price, price, volume, bid_ask))

                    for tf in Watcher.STORED_TIMEFRAMES:
                        # generate candle per each timeframe
                        with self._mutex:
                            candle = self.update_ohlc(market_id, tf, trade_time, price, spread, volume)
                            if candle is not None:
                                self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, candle))

            elif (data[1] == 'instrument' or data[1] == 'quote') and data[0] == 'insert' or data[0] == 'update':
                for market_id in data[2]:
                    instrument = self.connector.ws.get_instrument(market_id)

                    if market_id not in self._watched_instruments:
                        # not a symbol of interest
                        continue

                    #
                    # notify a market data update
                    #

                    tradeable = instrument.get('state', 'Closed') == 'Open'
                    update_time = datetime.strptime(instrument.get('timestamp', '1970-01-01 00:00:00.000Z'), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC()).timestamp()
                    symbol = instrument.get('symbol', '')
                    base_symbol = instrument.get('rootSymbol', 'USD')
                    quote_symbol = symbol[-3:]

                    # base to XBT
                    base_exchange_rate = 1.0

                    # base instrument
                    base_market_id = "XBT" + quote_symbol
                    base_market = None

                    if quote_symbol == "USD" and base_market_id != symbol:
                        xbtusd_market = self.connector.ws.get_instrument("XBTUSD")
                        if xbtusd_market:
                            base_exchange_rate = instrument.get('lastPrice', 1.0)  # / xbtusd_market.get('lastPrice', 1.0)

                    elif base_market_id != symbol:
                        base_market = self.connector.ws.get_instrument(base_market_id)
                        xbtusd_market = self.connector.ws.get_instrument("XBTUSD")
                        if base_market and xbtusd_market:
                            base_exchange_rate = instrument.get('lastPrice', 1.0) / (base_market.get('lastPrice', 1.0))  # / xbtusd_market.get('lastPrice', 1.0))

                    bid = instrument.get('bidPrice')
                    ask = instrument.get('askPrice')

                    if bid is not None and ask is not None:
                        # update contract size and value per pip
                        if quote_symbol == 'USD' and base_market_id == symbol:  # XBTUSD (xbt perpetual)
                            base_exchange_rate = instrument.get('lastPrice', 1.0)
                            contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                            value_per_pip = contract_size * instrument.get('lastPrice', 1.0)

                        elif base_market_id == symbol:  # XBTU19 (xbt futures)
                            base_exchange_rate = instrument.get('lastPrice', 1.0)
                            contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                            value_per_pip = contract_size * instrument.get('lastPrice', 1.0)

                        elif quote_symbol == 'USD' and base_market_id != symbol:  # ETHUSD, XRPUSD... (alts perpetuals)
                            if base_symbol == 'ETH':
                                # ETHUSD Contract Size  0,001 mXBT per 1 USD (Currently 0,00022754 XBT per contract) @ XBTUSD 10140$
                                base_exchange_rate = 1.0 / (instrument.get('lastPrice', 1.0) * 0.001 * 0.001)
                                contract_size = instrument.get('lastPrice', 1.0) * 0.001 * 0.001
                                value_per_pip = contract_size * instrument.get('lastPrice', 1.0)

                            elif base_symbol == 'XRP':
                                # XRPUSD Contract Size 0,0002 XBT per 1 USD (Currently 0,00005642 XBT per contract) @ XBTUSD 10140$
                                base_exchange_rate =  1.0 / (instrument.get('lastPrice', 1.0) * 0.0002)
                                contract_size = instrument.get('lastPrice', 1.0) * 0.0002
                                value_per_pip = contract_size * instrument.get('lastPrice', 1.0)

                        elif base_market and base_market_id != symbol:  # ADAZ18... (alts futures)
                            base_exchange_rate = xbtusd_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)
                            contract_size = xbtusd_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)
                            value_per_pip = 1.0

                        vol24h = instrument.get('volume24h')
                        vol24hquote = instrument.get('foreignNotional24h')

                        market_data = (market_id, tradeable, update_time, bid, ask, base_exchange_rate, contract_size, value_per_pip, vol24h, vol24hquote)
                        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

            #
            # order book L2 top 25
            #
            
            elif data[1] == 'orderBookL2_25' and data[2]:
                pass
                # for market_id in data[2]:
                #   market_depth = self.connector.ws.market_depth(market_id)
                #   self.service.notify(Signal.SIGNAL_ORDER_BOOK, self.name, (market_id, market_depth[0], market_depth[1]))

    def fetch_market(self, market_id):
        """
        Fetch and cache it. It rarely changes, except for base exchange rate, so assume it once for all.
        @todo min/max/step/min_notional
        """
        instrument = self.connector.ws.get_instrument(market_id)
        # funds = self.connector.ws.funds()  # to get account base currency (if XBt or XBT)
        xbt_usd = self.connector.ws.get_instrument("XBTUSD")

        if instrument:
            # tickSize is the minimum price increment (0.5USD for XBTUSD)
            tradeable = instrument.get('state', 'Closed') == 'Open'
            update_time = self._parse_datetime(instrument.get('timestamp')).replace(tzinfo=UTC()).timestamp()
            symbol = instrument.get('symbol', '')
            base_symbol = instrument.get('rootSymbol', '')
            quote_symbol = symbol[-3:]

            # if funds['currency'] == 'XBt':
            #     # XBt to XBT
            #     ratio = 1.0 / 100000000.0

            # if base_symbol == 'USD':
            #     # USD is base then convert to XBT
            #     ratio *= to_base_rate

            bid = instrument.get('bidPrice')
            ask = instrument.get('askPrice')

            market = Market(market_id, symbol)

            # compute base precision from the tick size, example 0.05 => 2
            base_precision = -math.floor(math.log10(instrument.get('tickSize', 1.0)))

            market.set_base(base_symbol, base_symbol, base_precision)
            market.set_quote(quote_symbol, quote_symbol)

            # base to XBT
            market.base_exchange_rate = 1.0

            # base instrument
            base_market_id = "XBT" + quote_symbol
            base_market = self.connector.ws.get_instrument(base_market_id)
            xbtusd_market = self.connector.ws.get_instrument("XBTUSD")

            # @todo 'multiplier', 'riskStep', 'riskLimit'

            # limits
            min_notional = 1.0  # $

            if quote_symbol != "USD" and base_market_id != "XBT":
                # any contract on futur XBT quote
                min_notional = 0.0001

            # BCHXBT 'maxOrderQty': 100000000, 'maxPrice': 10, 'lotSize': 1, 'tickSize': 0.0001,
            # XBCUSD 'maxOrderQty': 10000000, 'maxPrice': 1000000, 'lotSize': 1, 'tickSize': 0.5,
            market.set_size_limits(instrument.get('tickSize', 1.0), instrument.get('maxOrderQty', 0.0), instrument.get('tickSize', 1.0))
            market.set_notional_limits(min_notional, instrument.get('maxPrice', 0.0), 0.0)
            market.set_price_limits(0.0, 0.0, instrument.get('tickSize', 1.0))

            # need to divided by account currency XBt = 100000000
            market.margin_factor = instrument.get('initMargin', 1.0)
            # market.max_margin_factor = 1.0 / (instrument.get('riskLimit', 1.0) * ratio) # ex: 20000000000 for max leverage 200

            # '-' if perpetual else match the regexp and keep the expiry part only
            expiry = BitMexWatcher.EXPIRY_RE.match(market_id)

            # or instrument.get(expiry') == '2018-12-28T12:00:00.000Z' for Z18 its 28 of month Z (december) and year 2018
            if expiry is None:
                market.expiry = '-'
            else:
                market.expiry = expiry.group(2) + expiry.group(3)

            market.market_type = Market.TYPE_CRYPTO
            market.unit_type = Market.UNIT_CONTRACTS
            market.contract_type = Market.CONTRACT_CFD if not expiry else Market.CONTRACT_FUTURE
            market.trade = Market.TRADE_MARGIN | Market.TRADE_IND_MARGIN

            if bid is not None and ask is not None:
                market.bid = bid
                market.ask = ask
                market.last_update_time = update_time

            market.lot_size = instrument.get('lotSize', 1.0)  # ex: 1.0 for XBTUSD
            market.contract_size = 1.0
            market.value_per_pip = 1.0
            market.one_pip_means = instrument.get('tickSize', 1.0)

            # contract_size need to be updated as price changes
            if quote_symbol == 'USD' and base_market_id == symbol:  # XBTUSD (xbt perpetual)
                market.base_exchange_rate = instrument.get('lastPrice', 1.0)
                market.contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                market.value_per_pip = market.contract_size * instrument.get('lastPrice', 1.0)

            elif base_market_id == symbol:  # XBTU19 (xbt futures)
                market.base_exchange_rate = instrument.get('lastPrice', 1.0)
                market.contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                market.value_per_pip = market.contract_size * instrument.get('lastPrice', 1.0)

            elif quote_symbol == 'USD' and base_market_id != symbol:  # ETHUSD, XRPUSD... (alts perpetuals)
                if base_symbol == 'ETH':
                    # ETHUSD Contract Size  0,001 mXBT per 1 USD (Currently 0,00022754 XBT per contract) @ XBTUSD 10140$
                    market.base_exchange_rate = 1.0 / (instrument.get('lastPrice', 1.0) * 0.001 * 0.001)
                    market.contract_size = instrument.get('lastPrice', 1.0) * 0.001 * 0.001
                    market.value_per_pip = market.contract_size * instrument.get('lastPrice', 1.0)

                elif base_symbol == 'XRP':
                    # XRPUSD Contract Size 0,0002 XBT per 1 USD (Currently 0,00005642 XBT per contract) @ XBTUSD 10140$
                    market.base_exchange_rate =  1.0 / (instrument.get('lastPrice', 1.0) * 0.0002)
                    market.contract_size = instrument.get('lastPrice', 1.0) * 0.0002
                    market.value_per_pip = market.contract_size * instrument.get('lastPrice', 1.0)

            elif base_market and base_market_id != symbol:  # ADAZ18... (alts futures)
                market.base_exchange_rate =  xbtusd_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)
                contract_size = xbtusd_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)
                market.value_per_pip = market.contract_size * instrument.get('lastPrice', 1.0)

            market.maker_fee = instrument.get('makerFee', 0.0)
            market.taker_fee = instrument.get('takerFee', 0.0)

            # store the last market info to be used for backtesting
            Database.inst().store_market_info((self.name, market_id, market.symbol,
                market.market_type, market.unit_type, market.contract_type,  # type
                market.trade, market.orders,  # type
                market.base, market.base_display, market.base_precision,  # base
                market.quote, market.quote_display, market.quote_precision,  # quote
                market.expiry, int(market.last_update_time * 1000.0),  # expiry, timestamp
                str(market.lot_size), str(market.contract_size), str(market.base_exchange_rate),
                str(market.value_per_pip), str(market.one_pip_means), str(market.margin_factor),
                str(market.min_size), str(market.max_size), str(market.step_size),  # size limits
                str(market.min_notional), str(market.max_notional), str(market.step_notional),  # notional limits
                str(market.min_price), str(market.max_price), str(market.tick_price),  # price limits
                str(market.maker_fee), str(market.taker_fee), str(market.maker_commission), str(market.taker_commission))  # fees
            )

            # notify for strategy
            self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, (market_id, market))

        return market

    def update_markets_info(self):
        """
        Update market info.
        """
        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market.is_open:
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ask,
                        market.base_exchange_rate, market.contract_size, market.value_per_pip,
                        market.vol24h_base, market.vol24h_quote)
            else:
                market_data = (market_id, market.is_open, market.last_update_time, None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

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
            yield(trade)

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        TF_MAP = {
            60: '1m',
            300: '5m',
            3600: '1h',
            86400: '1d'
        }

        if timeframe not in TF_MAP:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        # second timeframe to bitmex bin size
        bin_size = TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, bin_size, from_date, to_date, partial=True)
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s" % (self.name, bin_size, market_id))
            error_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open, high, low, close, spread, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield((candle[0], candle[1], candle[2], candle[3], candle[4], candle[5], candle[6]))
