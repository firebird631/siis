# @date 2020-05-09
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Trader connector for binancefutures.com

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional

if TYPE_CHECKING:
    from trader.service import TraderService
    from trader.market import Market
    from instrument.instrument import Instrument
    from watcher.connector.binancefutures.watcher import BinanceFuturesWatcher

import time
import copy
import traceback

from trader.trader import Trader

from .account import BinanceFuturesAccount

from trader.position import Position
from trader.order import Order

from connector.binance.exceptions import *
from connector.binance.client import Client

import logging
logger = logging.getLogger('siis.trader.binancefutures')
error_logger = logging.getLogger('siis.error.trader.binancefutures')
order_logger = logging.getLogger('siis.order.trader.binancefutures')
traceback_logger = logging.getLogger('siis.traceback.trader.binancefutures')


class BinanceFuturesTrader(Trader):
    """
    Binance futures market trader.

    @todo hedging, IOC/FIK mode
    """

    _watcher: Union[BinanceFuturesWatcher, None]

    def __init__(self, service: TraderService):
        super().__init__("binancefutures.com", service)

        self._watcher = None
        self._account = BinanceFuturesAccount(self)

        self._quotes = []
        self._ready = False

    @property
    def authenticated(self) -> bool:
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self) -> bool:
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    @property
    def watcher(self) -> BinanceFuturesWatcher:
        return self._watcher

    def connect(self):
        super().connect()

        # retrieve the binancefutures.com watcher and take its connector
        with self._mutex:
            self._watcher = self.service.watcher_service.watcher(self._name)
            self._ready = False

            if self._watcher:
                self.service.watcher_service.add_listener(self)

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)

    def disconnect(self):
        super().disconnect()

        with self._mutex:
            if self._watcher:
                self.service.watcher_service.remove_listener(self)
                self._watcher = None
                self._ready = False

    def on_watcher_connected(self, watcher_name: str):
        super().on_watcher_connected(watcher_name)

        # markets, orders and positions
        logger.info("- Trader %s retrieving data..." % self._name)

        with self._mutex:
            try:
                self.account.update(self._watcher.connector)

                self.__fetch_orders()
                self.__fetch_positions()

            except Exception as e:
                error_logger.error(repr(e))

        logger.info("Trader %s got data. Running." % self._name)

    def on_watcher_disconnected(self, watcher_name: str):
        super().on_watcher_disconnected(watcher_name)

    def pre_update(self):
        super().pre_update()

        if self._watcher is None:
            self.connect()

        # elif self._watcher.connector is None or not self._watcher.connector.connected:
        #     # wait for the watcher be connected
        #     retry = 0
        #     while self._watcher.connector is None or not self._watcher.connector.connected:
        #         retry += 1

        #         if retry >= int(5 / 0.01):
        #             self._watcher.connect()

        #             # and wait 0.5 second to be connected
        #             time.sleep(0.5)

        #         # don't waste the CPU
        #         time.sleep(0.01)

    def update(self):
        if not super().update():
            return False

        if self._watcher is None or not self._watcher.connected:
            return True

        if not self._ready:
            return False

        #
        # account data update (normal case don't call REST)
        #

        with self._mutex:
            self._account.update(self._watcher.connector)

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    #
    # ordering
    #

    def create_order(self, order: Order, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Create a market or limit order using the REST API. Take care to does not make too many calls per minutes.
        @todo Hedging with positionSide
        """
        if not order or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        # order type
        if order.order_type == Order.ORDER_MARKET:
            order_type = Client.ORDER_TYPE_MARKET

        elif order.order_type == Order.ORDER_LIMIT:
            order_type = Client.ORDER_TYPE_LIMIT

        elif order.order_type == Order.ORDER_STOP:
            order_type = Client.ORDER_TYPE_STOP_MARKET

        elif order.order_type == Order.ORDER_STOP_LIMIT:
            order_type = Client.ORDER_TYPE_STOP

        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            order_type = Client.ORDER_TYPE_TAKE_PROFIT_MARKET

        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            order_type = Client.ORDER_TYPE_TAKE_PROFIT

        elif order.order_type == Order.ORDER_TRAILING_STOP_MARKET:
            order_type = Client.ORDER_TYPE_TRAILING_STOP_MARKET

        else:
            error_logger.error("Trader %s refuse order because the order type is unsupported %s in order %s !" % (
                self.name, market_or_instrument.symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        symbol = order.symbol
        side = Client.SIDE_BUY if order.direction == Order.LONG else Client.SIDE_SELL

        # @todo as option for the order strategy
        time_in_force = Client.TIME_IN_FORCE_GTC

        if order.quantity < market_or_instrument.min_size:
            # reject if lesser than min size
            error_logger.error("Trader %s refuse order because the min size is not reached (%s<%s) %s in order %s !" % (
                self.name, order.quantity, market_or_instrument.min_size, symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        # quantity = market_or_instrument.format_quantity(market_or_instrument.adjust_quantity(order.quantity))
        quantity = market_or_instrument.adjust_quantity(order.quantity)
        notional = quantity * (order.price or market_or_instrument.market_ask)

        if notional < market_or_instrument.min_notional:
            # reject if lesser than min notional
            error_logger.error("Trader %s refuse order because the min notional is not reached (%s<%s) %s in order %s !" % (
                self.name, notional, market_or_instrument.min_notional, symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        data = {
            'symbol': symbol,
            'side': side,
            'positionSide': 'BOTH',
            'type': order_type,
            'quantity': quantity,
            'newOrderRespType': Client.ORDER_RESP_TYPE_RESULT,
            'recvWindow': 10000
        }

        # reduce only
        if order.reduce_only:
            data['reduceOnly'] = True

        # price type
        if order.price_type == Order.PRICE_MARK:
            data['workingType'] = 'MARK_PRICE'
        elif order.price_type == Order.PRICE_LAST:
            data['workingType'] = 'CONTRACT_PRICE'

        # limit order need timeInForce
        if order.order_type == Order.ORDER_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['timeInForce'] = time_in_force

        elif order.order_type == Order.ORDER_STOP:
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)

        elif order.order_type == Order.ORDER_STOP_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)
            data['timeInForce'] = time_in_force

        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)

        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)
            data['timeInForce'] = time_in_force

        elif order.order_type == Order.ORDER_TRAILING_STOP_MARKET:
            # @todo
            # data['activationPrice'] = market_or_instrument.format_price(order.trailing_price)
            # data['callbackRate'] = market_or_instrument.format_price(order.trailing_distance)
            data['timeInForce'] = time_in_force

        data['newClientOrderId'] = order.ref_order_id

        logger.info("Trader %s order %s %s %s @%s" % (self.name, order.direction_to_str(),
                                                      data.get('quantity'), symbol, data.get('price')))

        result = None
        reason = None

        try:
            result = self._watcher.connector.client.futures_create_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected order %s %s %s - reason : %s !" % (
                self.name, order.direction_to_str(), quantity, symbol, reason))

            # @todo convert reason to error
            return Order.REASON_ERROR

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected order %s %s %s !" % (
                    self.name, order.direction_to_str(), quantity, symbol))
                order_logger.error(result)

                return Order.REASON_ERROR

            if 'orderId' in result:
                order_logger.info(result)

                order.set_order_id(str(result['orderId']))

                # relate position to its market id
                # @todo distinct position id if using hedging
                order.set_position_id(market_or_instrument.market_id)

                order.created_time = result['updateTime'] * 0.001
                order.transact_time = result['updateTime'] * 0.001

                # if result['executedQty']:
                #     # partially or fully executed quantity
                #     order.set_executed(float(result['executedQty']), result.get['status'] == "FILLED", float(result['price']))

                return Order.REASON_OK

        # unknown error
        error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(), quantity,
                                                                    symbol))
        order_logger.error(result)

        return Order.REASON_ERROR

    def cancel_order(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Cancel a pending or partially filled order.
        """
        if not order_id or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_INVALID_ARGS

        symbol = market_or_instrument.market_id

        data = {
            # 'newClientOrderId': ref_order_id,
            'symbol': symbol,
            'orderId': order_id,
            'recvWindow': 10000
        }

        reason = None
        result = None
        code = 0

        try:
            result = self._watcher.connector.client.futures_cancel_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
            code = e.code
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (
                self.name, order_id, symbol, reason))

            if code == -2011:  # not exists assume its already canceled
                # @todo question...
                return Order.REASON_OK

            # @todo reason to error
            return Order.REASON_ERROR

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (
                    self.name, order_id, symbol, reason))
                order_logger.error(result)

                if code == -2011:  # not exists assume its already canceled
                    # @todo question...
                    return Order.REASON_OK

                # @todo reason to error
                return Order.REASON_ERROR

            order_logger.info(result)

        # ok, done
        return Order.REASON_OK

    def cancel_all_orders(self, market_or_instrument: Union[Market, Instrument]) -> bool:
        """
        Cancel any existing order for a specific market.
        """
        if not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to cancel all orders because of missing connector" % (self.name,))
            return False

        reason = None
        result = None

        symbol = market_or_instrument.market_id

        data = {
            # 'newClientOrderId': ref_order_id,
            'symbol': symbol,
            'recvWindow': 10000
        }

        try:
            result = self._watcher.connector.client.futures_cancel_all_open_orders(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected cancel all orders %s reason %s !" % (self.name, symbol, reason))
            return False

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected cancel all orders %s reason %s !" % (self.name, symbol, reason))
                order_logger.error(result)
                return False

            order_logger.info(result)

        return False

    def close_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                       direction: int, quantity: float, market: bool = True,
                       limit_price: Optional[float] = None) -> bool:
        """Not supported, use create_order for that"""
        return False

    def modify_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                        stop_loss_price: Optional[float] = None, take_profit_price: Optional[float] = None) -> bool:
        """Not supported, use cancel_order/create_order for that"""
        return False

    def positions(self, market_id: str) -> List[Position]:
        """
        @deprecated
        """
        positions = []

        with self._mutex:
            position = self._positions.get(market_id)
            if position:
                positions = [copy.copy(position)]
            else:
                positions = []

        return positions

    def market(self, market_id: str, force: bool = False) -> Union[Market, None]:
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param market_id
        @param force Force to update the cache
        """
        market = None

        with self._mutex:
            market = self._markets.get(market_id)

        if (market is None or force) and self._watcher is not None and self._watcher.connected:
            try:
                market = self._watcher.fetch_market(market_id)
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

            if market:
                with self._mutex:
                    self._markets[market_id] = market

        return market

    def order_info(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> Union[dict, None]:
        """
        Retrieve the detail of an order.
        """
        if not order_id or not market_or_instrument:
            return None

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to retrieve order info because of missing connector" % self.name)
            return None

        results = None

        try:
            results = self._watcher.connector.future_order_info(market_or_instrument.market_id, order_id)
        except Exception:
            # None as error
            return None

        if results and str(results.get('orderId', 0)) == order_id:
            order_data = results

            try:
                symbol = order_data['symbol']
                market = self.market(symbol)

                if not market:
                    return None

                price = None
                stop_price = None
                completed = False
                order_ref_id = order_data['clientOrderId']
                event_timestamp = order_data['updateTime'] * 0.001 if 'updateTime' in order_data else order_data['time'] * 0.001

                if order_data['status'] == Client.ORDER_STATUS_NEW:
                    status = 'opened'
                elif order_data['status'] == Client.ORDER_STATUS_PENDING_CANCEL:
                    # @note not exactly the same meaning
                    status = 'pending'
                elif order_data['status'] == Client.ORDER_STATUS_FILLED:
                    status = 'closed'
                    completed = True
                    if 'updateTime' in order_data:
                        event_timestamp = order_data['updateTime'] * 0.001
                elif order_data['status'] == Client.ORDER_STATUS_PARTIALLY_FILLED:
                    status = 'opened'
                    completed = False
                    if 'updateTime' in order_data:
                        event_timestamp = order_data['updateTime'] * 0.001
                elif order_data['status'] == Client.ORDER_STATUS_CANCELED:
                    status = 'canceled'
                    # status = 'deleted'
                elif order_data['status'] == Client.ORDER_STATUS_EXPIRED:
                    status = 'expired'
                    # completed = True ? and on watcher WS...
                else:
                    status = ""

                # reduce only
                reduce_only = order_data['reduceOnly']

                # price type
                if order_data['workingType'] == 'MARK_PRICE':
                    price_type = Order.PRICE_MARK
                elif order_data['workingType'] == 'CONTRACT_PRICE':
                    price_type = Order.PRICE_LAST
                else:
                    price_type = Order.PRICE_LAST

                # 'type' and 'origType'
                if order_data['type'] == Client.ORDER_TYPE_LIMIT:
                    order_type = Order.ORDER_LIMIT
                    price = float(order_data['price']) if 'price' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_MARKET:
                    order_type = Order.ORDER_MARKET

                elif order_data['type'] == Client.ORDER_TYPE_STOP:
                    order_type = Order.ORDER_STOP
                    price = float(order_data['price']) if 'price' in order_data else None
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_TAKE_PROFIT:
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(order_data['price']) if 'price' in order_data else None
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_TAKE_PROFIT_MARKET:
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_TRAILING_STOP_MARKET:
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    # @todo not supported

                else:
                    order_type = Order.ORDER_MARKET

                if order_data['timeInForce'] == Client.TIME_IN_FORCE_GTC:
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif order_data['timeInForce'] == Client.TIME_IN_FORCE_IOC:
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif order_data['timeInForce'] == Client.TIME_IN_FORCE_FOK:
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                # order_data['cumQuote'] "0",
                # order_data['positionSide'] "SHORT",

                # if Close - All
                # order_data['closePosition'] false

                # ignored when order type is TRAILING_STOP_MARKET
                # order_data['stopPrice'] "9300"

                # only for trailing stop market
                # order_data['activatePrice'] "9020"
                # order_data['priceRate'] "0.3"
                # order_data['priceProtect'] false

                post_only = False
                cumulative_commission_amount = 0.0  # @todo

                cumulative_filled = float(order_data['executedQty'])
                order_volume = float(order_data['origQty'])
                fully_filled = completed

                # trades = array of trade ids related to order (if trades info requested and data available)
                trades = []

                order_info = {
                    'id': order_id,
                    'symbol': symbol,
                    'status': status,
                    'ref-id': order_ref_id,
                    'direction': Order.LONG if order_data['side'] == Client.SIDE_BUY else Order.SHORT,
                    'type': order_type,
                    'timestamp': event_timestamp,
                    'avg-price': float(order_data['avgPrice']),
                    'quantity': order_volume,
                    'cumulative-filled': cumulative_filled,
                    'cumulative-commission-amount': cumulative_commission_amount,
                    'price': price,
                    'stop-price': stop_price,
                    'time-in-force': time_in_force,
                    'post-only': post_only,
                    # 'close-only': ,
                    'reduce-only': reduce_only,
                    # 'stop-loss': None,
                    # 'take-profit': None,
                    'fully-filled': fully_filled
                    # 'trades': trades
                }

                return order_info

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

                # error during processing
                return None

        # empty means success returns but does not exists
        return {
            'id': None
        }

    #
    # slots
    #

    #
    # protected
    #

    def __fetch_orders(self, signals=False):
        """
        This is the synchronous REST fetching, but prefer the WS asynchronous and live one.
        Mainly used for initial fetching.
        """
        try:
            open_orders = self._watcher.connector.future_open_orders()  # API cost 40 
        except Exception as e:
            logger.error("__fetch_orders: %s" % repr(e))
            raise

        orders = {}

        for data in open_orders:
            market = self.market(data['symbol'])

            if data['status'] == Client.ORDER_STATUS_NEW:  # might be...
                order = Order(self, data['symbol'])

                order.set_order_id(str(data['orderId']))
                order.set_ref_order_id(data['clientOrderId'])

                order.quantity = float(data.get('origQty', "0.0"))
                order.executed = float(data.get('executedQty', "0.0"))

                order.direction = Order.LONG if data['side'] == Client.SIDE_BUY else Order.SHORT

                if data['type'] == Client.ORDER_TYPE_LIMIT:
                    order.order_type = Order.ORDER_LIMIT
                    order.price = float(data['price']) if 'price' in data else None

                elif data['type'] == Client.ORDER_TYPE_MARKET:
                    order.order_type = Order.ORDER_MARKET

                elif data['type'] == Client.ORDER_TYPE_STOP:
                    order.order_type = Order.ORDER_STOP_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == Client.ORDER_TYPE_TAKE_PROFIT:
                    order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == Client.ORDER_TYPE_STOP_MARKET:
                    order.order_type = Order.ORDER_STOP
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == Client.ORDER_TYPE_TAKE_PROFIT_MARKET:
                    order.order_type = Order.ORDER_TAKE_PROFIT
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == Client.ORDER_TYPE_TRAILING_STOP_MARKET:
                    order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    # @todo order.trailing_distance data['callbackRate']

                order.created_time = data['time'] * 0.001
                order.transact_time = data['updateTime'] * 0.001

                order.reduce_only = data['reduceOnly']
                # data['closePosition']
                # data['positionSide']
                # data['cumQuote']

                # time-in-force
                if data['timeInForce'] == Client.TIME_IN_FORCE_GTC:
                    order.time_in_force = Order.TIME_IN_FORCE_GTC
                elif data['timeInForce'] == Client.TIME_IN_FORCE_IOC:
                    order.time_in_force = Order.TIME_IN_FORCE_IOC
                elif data['timeInForce'] == Client.TIME_IN_FORCE_FOK:
                    order.time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    order.time_in_force = Order.TIME_IN_FORCE_GTC

                # execution price
                if data['workingType'] == 'CONTRACT_PRICE':
                    order.price_type = Order.PRICE_LAST
                elif data['workingType'] == 'MARK_PRICE':
                    order.price_type = Order.PRICE_MARK
                else:
                    order.price_type = Order.PRICE_LAST

                orders[order.order_id] = order

        # if signals:
        #     # deleted (for signals if no WS)
        #     deleted_list = self._orders.keys() - orders.keys()
        #     # @todo

        #     # created (for signals if no WS)
        #     created_list = orders.keys() - self._orders.keys()
        #     # @todo

        if orders:
            with self._mutex:
                self._orders = orders

    def __fetch_positions(self, signals=False):
        """
        This is the synchronous REST fetching, but prefer the WS asynchronous and live one.
        Mainly used for initial fetching.
        @todo Distinct LONG/SHORT position when hedging enabled
        """
        try:
            open_positions = self._watcher.connector.futures_position_information()  # API cost 5
        except Exception as e:
            logger.error("__fetch_positions: %s" % repr(e))
            raise

        positions = {}

        for data in open_positions:
            symbol = data['symbol']
            quantity = float(data['positionAmt'])
            market = self.market(symbol)
            position = None

            if data['positionSide'] == 'LONG' or data['positionSide'] == 'SHORT':
                # only if hedging @todo
                continue

            if self._positions.get(symbol):
                position = self._positions.get(symbol)

            elif quantity != 0.0:
                # insert the new position
                position = Position(self)
                position.set_position_id(symbol)
                position.set_key(self.service.gen_key())

                quantity = abs(quantity)
                direction = Position.LONG if quantity > 0.0 else Position.SHORT

                position.entry(direction, symbol, quantity)

                position.leverage = float(data['leverage'])

                # liquidation_price = data['liquidationPrice']
                # position.mark_price = data['markPrice']
                # data['marginType'] == 'isolated'
                # data['maxNotionalValue']
                # data['isAutoAddMargin']
                position.entry_price = float(data['entryPrice'])
                # position.created_time =

                # id is symbol
                self._positions[symbol] = position

            elif (quantity == 0.0) and self._positions.get(symbol):
                # no more position
                del self._positions[symbol]

            if position:
                # absolute value because we work with positive quantity + direction information
                position.quantity = abs(quantity)
                position.direction = Position.LONG if quantity > 0.0 else Position.SHORT

                position.leverage = float(data['leverage'])

                # position.liquidation_price = data['liquidationPrice']
                # position.mark_price = data['markPrice']
                position.entry_price = float(data['entryPrice'])
                # position.created_time = 

                # @todo minus taker-fee (it is compared to mark-price, but it worth only for mark-price stop-loss)
                position.profit_loss = float(data['unRealizedProfit'])
                # position.profit_loss_rate = float(data[''])

                # @todo minus maker-fee
                position.profit_loss_market = float(data['unRealizedProfit'])
                # position.profit_loss_market_rate = float(data[''])

                # compute profit loss in base currency (disabled, uses values above)
                # position.update_profit_loss(market)

        if positions:
            with self._mutex:
                self._positions = positions

    #
    # markets
    #

    def on_update_market(self, market_id: str, tradeable: bool, last_update_time: float, bid: float, ask: float,
                         base_exchange_rate: Optional[float] = None,
                         contract_size: Optional[float] = None, value_per_pip: Optional[float] = None,
                         vol24h_base: Optional[float] = None, vol24h_quote: Optional[float] = None):

        super().on_update_market(market_id, tradeable, last_update_time, bid, ask, base_exchange_rate,
                                 contract_size, value_per_pip, vol24h_base, vol24h_quote)

        # update positions profit/loss for the related market id
        market = self.market(market_id)

        # market must be valid
        if market is None:
            return

        with self._mutex:
            try:
                # update profit/loss for each positions
                for k, position in self._positions.items():
                    if position.symbol == market.market_id:
                        position.update_profit_loss(market)
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())
