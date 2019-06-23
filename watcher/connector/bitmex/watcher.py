# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# www.bitmex.com watcher implementation

import re
import json
import time
import datetime
import traceback
import math

from watcher.watcher import Watcher
from notifier.signal import Signal

from connector.bitmex.connector import Connector

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle, Tick

from config import config

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.bitmex')


class BitMexWatcher(Watcher):
    """
    BitMex market watcher using REST + WS.
    @note No having historical data fetching.

    Month code = F (jan) G H J K M N Q U V X Z (dec)

    @todo take care contract size and value per pip too... depends of the price, its not a good idea or have to update it
    @todo update market info

    @ref https://www.bitmex.com/app/wsAPI#All-Commands
    """

    EXPIRY_RE = re.compile(r'^(.{3})([FGHJKMNQUVXZ])(\d\d)$')

    def __init__(self, service):
        super().__init__("bitmex.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None

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
                        self.configured_symbols(),  # want WS subscribes to thats instruments or all if ['*']
                        identity.get('host'),
                        (self, BitMexWatcher._ws_message))

                # get list of all availables instruments, and list of subscribed
                self._available_instruments = set(self._connector.all_instruments)
                self._watched_instruments = set(self._connector.watched_instruments)

                # testnet (demo) server doesn't provided real prices, so never store info from it !
                if identity.get('host') == 'testnet.bitmex.com':
                    self._read_only = True

                if not self._connector.connected or not self._connector.ws_connected:
                    self._connector.connect()

                for symbol in self._watched_instruments:
                    self.insert_watched_instrument(symbol, [0])

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
        return self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self):
        return self._connector and self._connector.authenticated

    def pre_update(self):
        if self._connector is None or not self._connector.connected or not self._connector.ws_connected:
            # retry in 2 second
            self._connector = None

            time.sleep(2)
            self.connect()
            return

    def update(self):
        if not super().update():
            return False

        #
        # ohlc close/open
        #

        self.lock()
        self.update_from_tick()
        self.unlock()

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0005)

    def post_run(self):
        super().post_run()

    #
    # private
    #

    def _parse_datetime(self, date_str):
        return datetime.datetime.strptime(date_str or '1970-01-01 00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%fZ")

    #
    # protected
    #

    @staticmethod
    def _ws_message(self, message, data):
        if message == 'action':
            #
            # account data update
            #
            
            if data[1] in ('margin', 'instrument', 'quote'):
                funds = self.connector.ws.funds()
                ratio = 1.0
                currency = funds['currency']

                # convert XBt to BTC
                if currency == 'XBt':
                    ratio = 1.0 / 100000000.0
                    currency = 'BTC'

                # walletBalance or amount, riskLimit is max leverage
                account_data = (
                        funds['walletBalance']*ratio, funds['marginBalance']*ratio, funds['unrealisedPnl']*ratio,
                        currency, funds['riskLimit']*ratio)

                self.service.notify(Signal.SIGNAL_ACCOUNT_DATA, self.name, account_data)

            #
            # orders partial execution
            #
            
            if data[1] == 'execution' and data[2]:
                for ld in data[3]:
                    logger.info("bitmex l185 execution > ", ld)

            #
            # positions
            #

            elif data[1] == 'position':  # action
                for ld in data[3]:
                    # logger.info("bitmex l194 position > ", ld)

                    ref_order_id = ""
                    symbol = ld['symbol']
                    position_id = symbol

                    # 'leverage': 10, 'crossMargin': False

                    if ld['currentQty'] is None:
                        # no position
                        continue

                    if ld.get('currentQty', 0) != 0:
                        direction = Order.SHORT if ld['currentQty'] < 0 else Order.LONG
                    elif ld.get('openOrderBuyQty', 0) > 0:
                        direction = Order.LONG
                    elif ld.get('openOrderSellQty', 0) > 0:
                        direction = Order.SHORT
                    else:
                        direction = 0

                    operation_time = self._parse_datetime(ld.get('timestamp')).timestamp()
                    quantity = abs(float(ld['currentQty']))

                    # 'execQty': ?? 'execBuyQty', 'execSellQty': ??
                    # 'commission': 0.00075 'execComm': 0 ?? 'currentComm': 0

                    position_data = {
                        'id': symbol,
                        'symbol': symbol,
                        'direction': direction,
                        'timestamp': operation_time,
                        'quantity': quantity,
                        'avg-price': ld.get('avgEntryPrice', None),
                        'exec-price': None,
                        'stop-loss': None,
                        'take-profit': None,
                        'profit-currency': ld.get('currency'),
                        'profit-loss': ld.get('unrealisedPnl'),
                        'cumulative-filled': quantity,
                        'filled': None,  # no have
                        'liquidation-price': ld.get('liquidationPrice'),
                        'commission': ld.get('commission', 0.0)
                    }

                    if (ld.get('openOrderSellQty', 0) or ld.get('openOrderSellQty', 0)) and quantity == 0.0:
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

            elif data[1] == 'order':
                for ld in data[3]:
                    symbol = ld.get('symbol')
                    status = ld.get('ordStatus', None)

                    if not status:  # updated
                        # logger.info("> bitmex l249 Other", ld, message)
                        operation_time = self._parse_datetime(ld.get('timestamp')).timestamp()

                        # quantity or price modified
                        if (ld.get('orderQty') or ld.get('price') or ld.get('stopPx')) and ld.get('workingIndicator'):
                            order = {
                                'id': ld['orderID'],
                                'symbol': symbol,
                                'timestamp': operation_time,
                                'quantity': ld.get('orderQty', None),
                                'order-price': ld.get('price', ld.get('stopPx', None)),  # limit or stop @todo but if we have stop_limit... ?
                                'stop-loss': None,
                                'take-profit': None
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_UPDATED, self.name, (symbol, order, ""))

                    elif status == 'New':  # action='insert'
                        transact_time = self._parse_datetime(ld.get('transactTime')).timestamp()

                        if ld['ordType'] == 'Market':
                            order_type = Order.ORDER_MARKET
                        elif ld['ordType'] == 'Limit':
                            order_type = Order.ORDER_LIMIT
                        elif ld['ordType'] == 'Stop':
                            order_type = Order.ORDER_STOP
                        else:
                            order_type = Order.ORDER_MARKET
                        # ... @todo other kind but not really necessary the others

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
                            'order-price': ld.get('price', ld.get('stopPx', None)),  # limit or stop @todo but if we have stop_limit... ?
                            'stop-loss': None,
                            'time-in-force': time_in_force,
                            'post-only': 'ParticipateDoNotInitiate' in exec_inst,  # maker only (not taker)
                            'close-only': 'Close' in exec_inst,
                            'reduce-only': 'ReduceOnly' in exec_inst,
                            'price-type': price_type
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
                        operation_time = datetime.datetime.strptime(ld.get('timestamp', '1970-01-01 00:00:00.000Z'), "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
                        # 'workingIndicator': False, if fully filled
                        #  'leavesQty': 0, if fully filled

                        # 'currency': 'XBT', 'settlCurrency': 'XBt', 'triggered': '', 'simpleLeavesQty': None, 'leavesQty': 10000, 'simpleCumQty': None, 'cumQty': 0, 'avgPx': None, ...

                        order = {
                          'id': ld['orderID'],
                          'symbol': symbol,
                          'timestamp': operation_time,
                          'quantity': ld.get('orderQty', 0),
                          'filled': None,  # no have
                          'cumulative-filled': ld.get('cumQty', 0),
                          'exec-price': None,  # no have
                          'avg-price': ld.get('avgPx', 0),  # averaged for the cumulative
                        }

                        self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order, ld.get('clOrdID', "")))

            #
            # market
            #

            # if data[1] == 'instrument' and data[2]:
            elif (data[1] == 'instrument' or data[1] == 'quote') and data[2]:
                # updated market id
                for market_id in data[2]:
                    instrument = self.connector.ws.get_instrument(market_id)

                    if market_id not in self._watched_instruments:
                        # not a symbol of interest
                        continue

                    #
                    # notify a market data update
                    #

                    tradeable = instrument.get('state', 'Closed') == 'Open'
                    update_time = datetime.datetime.strptime(instrument.get('timestamp', '1970-01-01 00:00:00.000Z'), "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
                    symbol = instrument.get('symbol', '')
                    base_symbol = instrument.get('rootSymbol', 'USD')
                    quote_symbol = symbol[-3:]

                    # base to XBT
                    base_exchange_rate = 1.0

                    # base instrument
                    base_market_id = "XBT" + quote_symbol
                    base_market = None
                    if base_market_id != symbol:
                        base_market = self.connector.ws.get_instrument(base_market_id)
                        if base_market:
                            base_exchange_rate = base_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)

                    bid = instrument.get('bidPrice')
                    ofr = instrument.get('askPrice')

                    if bid is not None and ofr is not None:
                        # update contract size and value per pip
                        if quote_symbol == 'USD' and base_market_id == symbol:  # XBTUSD...
                            contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                        elif quote_symbol == 'USD' and base_market_id != symbol:  # ETHUSD...
                            contract_size = (0.001 * 0.01) * instrument.get('lastPrice', 1.0)
                        elif base_market and base_market_id != symbol:  # ADAZ18...
                            contract_size = 1.0 / instrument.get('lastPrice', 1.0)
                        else:
                            contract_size = 1.0 / instrument.get('lastPrice', 1.0)

                        # logger.debug(symbol, base_market_id, contract_size)
                        value_per_pip = contract_size / instrument.get('lastPrice', 1.0)

                        vol24h = instrument.get('volume24h')
                        vol24hquote = instrument.get('foreignNotional24h')

                        # @todo not a good idea too many signals for nothing, could only occurs each 5 minutes
                        market_data = (market_id, tradeable, update_time, bid, ofr, base_exchange_rate, contract_size, value_per_pip, vol24h, vol24hquote)
                        # if int(update_time / 5) * 5
                        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

                    #
                    # notify a market info data update (commented because to often, do it only at connection)
                    #

                    # @todo look at fetch_market and how to only update when necessary ? so for now only done at reconnection
                    # self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, market)

                    #
                    # notify a tick data update
                    #

                    # if action == 'update':
                    #    self.connector.ws.get_ticker(market_id)

                    volume = instrument.get('volume', 0)  # ex: 32057250
                    last_bid = None
                    last_ofr = None
                    last_vol = None

                    if 'bidPrice' in data[3][0] and data[3][0]['bidPrice']:
                        # price update
                        last_bid = float(data[3][0]['bidPrice'])

                    if 'askPrice' in data[3][0] and data[3][0]['askPrice']:
                        # price update
                        last_ofr = float(data[3][0]['askPrice'])

                    if 'volume' in data[3][0] and data[3][0]['volume']:
                        last_vol = float(data[3][0]['volume'])

                    # logger.info("bitmex l325 > ", market_id, bid, ofr, volume, " / ", last_bid, last_ofr, last_vol)

                    if bid is not None and ofr is not None and volume is not None and last_vol:
                        # we have a tick when we have a volume in data content
                        tick = Tick(update_time)

                        tick.set_price(bid, ofr)
                        tick.set_volume(volume)

                        self.lock()
                        self._last_tick[market_id] = tick
                        self.unlock()

                        # and notify
                        self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (market_id, tick))

                        #
                        # reconstruct candles for 1", 1', 5', 60' and clear olders ticks
                        #

                        # example of bin (candle) data
                        # 'openingTimestamp': '2018-09-16T00:00:00.000Z',
                        # 'closingTimestamp': '2018-09-16T02:00:00.000Z',
                        # 'highPrice': 6568,
                        # 'lowPrice': 6463.5,
                        # 'bidPrice': 6508,
                        # 'midPrice': 6508.25,
                        # 'askPrice': 6508.5,
                        # 'lastPrice': 6508.5,
                        # 'markPrice': 6510.71,

                        # disable for now because trade are usefull for backtesting but bitmex does not provides historical API
                        if not self._read_only:
                            Database.inst().store_market_trade((self.name, symbol, int(update_time*1000), bid, ofr, volume))

                    for tf in Watcher.STORED_TIMEFRAMES:
                        # generate candle per each timeframe
                        self.lock()

                        candle = self.update_ohlc(market_id, tf, update_time, last_bid, last_ofr, last_vol)
                        if candle is not None:
                            self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, candle))

                        self.unlock()

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
        Fetch and cache it. It rarely changes so assume it once for all.
        @todo min/max/step/min_notional
        """
        instrument = self.connector.ws.get_instrument(market_id)
        # funds = self.connector.ws.funds()  # to get account base currency (if XBt or XBT)
        xbt_usd = self.connector.ws.get_instrument("XBTUSD")

        if instrument:
            # tickSize is the minimum price increment (0.5USD for XBTUSD)
            tradeable = instrument.get('state', 'Closed') == 'Open'
            update_time = self._parse_datetime(instrument.get('timestamp')).timestamp()
            symbol = instrument.get('symbol', '')
            base_symbol = instrument.get('rootSymbol', '')
            quote_symbol = symbol[-3:]

            # if funds['currency'] == 'XBt':
            #   # XBt to XBT
            #   ratio = 1.0 / 100000000.0

            # if base_symbol == 'USD':
            #   # USD is base then convert to XBT
            #   ratio *= to_base_rate

            bid = instrument.get('bidPrice')
            ofr = instrument.get('askPrice')

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
            if base_market_id != symbol and base_market:
                market.base_exchange_rate = base_market.get('lastPrice', 1.0) / instrument.get('lastPrice', 1.0)

            # @todo value is multiplier 'multiplier': -100000000,
            # riskStep should be the current leverage in account currency and riskLimit the maximum for the market
            market.set_size_limits(0.0, 0.0, 1.0, 1.0)

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

            if bid is not None and ofr is not None:
                market.bid = bid
                market.ofr = ofr
                market.last_update_time = update_time

            market.lot_size = instrument.get('lotSize', 1.0)  # ex: 1.0 for XBTUSD
            market.contract_size = 1.0
            market.value_per_pip = 1.0
            market.one_pip_means = instrument.get('tickSize', 1.0)

            if quote_symbol == 'USD' and base_market_id == symbol:  # XBTUSD...
                market.contract_size = 1.0 / instrument.get('lastPrice', 1.0)
            elif quote_symbol == 'USD' and base_market_id != symbol:  # ETHUSD...
                market.contract_size = (0.001 * 0.01) * instrument.get('lastPrice', 1.0)
            elif base_market and base_market_id != symbol:  # ADAZ18...
                market.contract_size = 1.0 / instrument.get('lastPrice', 1.0)

            market.value_per_pip = market.contract_size / instrument.get('lastPrice', 1.0)

            market.maker_fee = instrument.get('makerFee', 0.0)
            market.taker_fee = instrument.get('takerFee', 0.0)

            # store the last market info to be used for backtesting
            if not self._read_only:
                Database.inst().store_market_info((self.name, market_id, market.symbol,
                    market.base, market.base_display, market.base_precision,
                    market.quote, market.quote_display, market.quote_precision,
                    market.expiry, int(market.last_update_time * 1000.0),
                    str(market.lot_size), str(market.contract_size), str(market.base_exchange_rate),
                    str(market.value_per_pip), str(market.one_pip_means), str(market.margin_factor),
                    "0.0", "0.0", "1.0", "1.0",
                    market.market_type, market.unit_type, str(market.bid), str(market.ofr),
                    str(market.maker_fee), str(market.taker_fee), "0.0"))

        return market

    def update_markets_info(self, markets):
        pass  # @todo (not very important because its seems it never changes)
