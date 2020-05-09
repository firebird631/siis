# @date 2020-05-09
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Trader/autotrader connector for binance.com

import time
import copy
import traceback

from operator import itemgetter, attrgetter

from trader.trader import Trader

from .account import BinanceFuturesAccount

from trader.position import Position
from trader.order import Order
from trader.account import Account
from trader.market import Market

from database.database import Database

from connector.binance.exceptions import *
from connector.binance.client import Client

from trader.traderexception import TraderException

import logging
logger = logging.getLogger('siis.trader.binancefutures')
error_logger = logging.getLogger('siis.error.trader.binancefutures')
order_logger = logging.getLogger('siis.order.trader.binancefutures')
traceback_logger = logging.getLogger('siis.traceback.trader.binancefutures')


class BinanceFuturesTrader(Trader):
    """
    Binance futures market trader.

    @todo WIP
    """

    def __init__(self, service):
        super().__init__("binancefutures.com", service)

        self._watcher = None
        self._account = BinanceFuturesAccount(self)

        self._quotes = []
        self._ready = False

    @property
    def authenticated(self):
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self):
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

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

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        # markets, orders and positions
        logger.info("- Trader %s retrieving data..." % self._name)

        with self._mutex:
            try:
                self.account.update(self._watcher.connector)

            except Exception as e:
                error_logger.error(repr(e))

        logger.info("Trader %s got data. Running." % self._name)

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def pre_update(self):
        super().pre_update()

        if self._watcher is None:
            self.connect()
        elif self._watcher.connector is None or not self._watcher.connector.connected:
            # wait for the watcher be connected
            retry = 0
            while self._watcher.connector is None or not self._watcher.connector.connected:
                retry += 1

                if retry >= int(5 / 0.01):
                    self._watcher.connect()

                    # and wait 0.5 second to be connected
                    time.sleep(0.5)

                # don't waste the CPU
                time.sleep(0.01)

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

    def create_order(self, order, market_or_instrument):
        """
        Create a market or limit order using the REST API. Take care to does not make too many calls per minutes.
        """
        if not order or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return False

        # order type
        if order.order_type == Order.ORDER_LIMIT:
            order_type = Client.ORDER_TYPE_LIMIT
        elif order.order_type == Order.ORDER_STOP:
            order_type = Client.ORDER_TYPE_STOP_LOSS
        else:
            # @todo others
            order_type = Client.ORDER_TYPE_MARKET

        symbol = order.symbol
        side = Client.SIDE_BUY if order.direction == Order.LONG else Client.SIDE_SELL

        # @todo as option for the order strategy
        time_in_force = Client.TIME_IN_FORCE_GTC

        if order.quantity < market_or_instrument.min_size:
            # reject if lesser than min size
            error_logger.error("Trader %s refuse order because the min size is not reached (%.f<%.f) %s in order %s !" % (
                self.name, order.quantity, market_or_instrument.min_size, symbol, order.ref_order_id))
            return False

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        # quantity = market_or_instrument.format_quantity(market_or_instrument.adjust_quantity(order.quantity))
        quantity = market_or_instrument.adjust_quantity(order.quantity)
        notional = quantity * (order.price or market_or_instrument.market_ofr)

        if notional < market_or_instrument.min_notional:
            # reject if lesser than min notinal
            error_logger.error("Trader %s refuse order because the min notional is not reached (%.f<%.f) %s in order %s !" % (
                self.name, notional, market_or_instrument.min_notional, symbol, order.ref_order_id))
            return False

        data = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'newOrderRespType': Client.ORDER_RESP_TYPE_RESULT,
            'recvWindow': 10000
        }

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

        data['newClientOrderId'] = order.ref_order_id
        # data['icebergQty'] = 0.0

        logger.info("Trader %s order %s %s %s @%s" % (self.name, order.direction_to_str(), data.get('quantity'), symbol, data.get('price')))

        result = None
        reason = None

        try:
            result = self._watcher.connector.client.create_order(**data)
            # result = self._watcher.connector.client.create_test_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected order %s %s %s - reason : %s !" % (self.name, order.direction_to_str(), quantity, symbol, reason))
            return False

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(), quantity, symbol))
                order_logger.error(result)
                
                return False

            if 'orderId' in result:
                order_logger.info(result)

                order.set_order_id(result['orderId'])

                order.created_time = result['transactTime'] * 0.001
                order.transact_time = result['transactTime'] * 0.001

                # if result['executedQty']:
                #     # partially or fully executed quantity
                #     order.set_executed(float(result['executedQty']), result.get['status'] == "FILLED", float(result['price']))

                return True

        error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(), quantity, symbol))
        order_logger.error(result)

        return False

    def cancel_order(self, order_id, market_or_instrument):
        """
        Cancel a pending or partially filled order.
        """
        if not order_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return False

        symbol = market_or_instrument.market_id

        data = {
            # 'newClientOrderId': ref_order_id,
            'symbol': symbol,
            'orderId': order_id,
            'recvWindow': 10000
        }

        reason = None
        result = None

        try:
            result = self._watcher.connector.client.cancel_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, symbol, reason))
            return False

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, symbol, reason))
                order_logger.error(result)
                return False

            order_logger.info(result)

        return True

    def close_position(self, position_id, market_or_instrument, direction, quantity, market=True, limit_price=None):
        if not position_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to close position because of missing connector" % (self.name,))
            return False

        # @todo

        return False

    def modify_position(self, position_id, market_or_instrument, stop_loss_price=None, take_profit_price=None):
        if not position_id or not market_or_instrument:
            return False
        
        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to close position because of missing connector" % (self.name,))
            return False

        # @todo

        return False

    def positions(self, market_id):
        positions = []

        with self._mutex:
            position = self._positions.get(market_id)
            if position:
                positions = [copy.copy(position)]
            else:
                positions = []

        return positions

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
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
            open_orders = self._watcher.connector.futures_open_orders()
        except Exception as e:
            logger.error("__fetch_orders: %s" % repr(e))
            raise

        orders = {}

        for data in open_orders:
            market = self.market(data['symbol'])

            if data['status'] == 'NEW':  # might be...
                order = Order(self, data['symbol'])

                order.set_order_id(data['orderId'])
                order.quantity = float(data.get('origQty', "0.0"))
                order.executed = float(data.get('executedQty', "0.0"))

                order.direction = Order.LONG if data['side'] == 'BUY' else Order.SHORT

                if data['type'] == 'LIMIT':
                    order.order_type = Order.ORDER_LIMIT
                    order.price = float(data['price']) if 'price' in data else None

                elif data['type'] == 'LIMIT_MAKER':
                    order.order_type = Order.ORDER_LIMIT # _MAKER
                    order.price = float(data['price']) if 'price' in data else None

                elif data['type'] == 'MARKET':
                    order.order_type = Order.ORDER_MARKET

                elif data['type'] == 'STOP_LOSS':
                    order.order_type = Order.ORDER_STOP
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'STOP_LOSS_LIMIT':
                    order.order_type = Order.ORDER_STOP_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'TAKE_PROFIT':
                    order.order_type = Order.ORDER_TAKE_PROFIT
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'TAKE_PROFIT_LIMIT':
                    order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                order.created_time = data['time'] * 0.001
                order.transact_time = data['updateTime'] * 0.001

                if data['timeInForce'] == 'GTC':
                    order.time_in_force = Order.TIME_IN_FORCE_GTC
                elif data['timeInForce'] == 'IOC':
                    order.time_in_force = Order.TIME_IN_FORCE_IOC
                elif data['timeInForce'] == 'FOK':
                    order.time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    order.time_in_force = Order.TIME_IN_FORCE_GTC

                # "icebergQty": "0.0"  # @todo a day when I'll be rich
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

        @todo
        """
        pass

    #
    # markets
    #

    def on_update_market(self, market_id, tradable, last_update_time, bid, ofr,
            base_exchange_rate, contract_size=None, value_per_pip=None,
            vol24h_base=None, vol24h_quote=None):

        super().on_update_market(market_id, tradable, last_update_time, bid, ofr, base_exchange_rate, contract_size, value_per_pip, vol24h_base, vol24h_quote)

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

    #
    # order slots
    #

    @Trader.mutexed
    def on_order_traded(self, market_id, data, ref_order_id):
        """
        Order update.
        @note Consume 1 API credit to get the asset quote price at the time of the trade.
        """
        market = self._markets.get(data['symbol'])

        if market is None:
            # not interested by this market
            return

        if data['trade-id']:
            pass # @todo

        if data.get('fully-filled', False):
            # fully filled, need to delete
            if order.order_id in self._orders:
                del self._orders[order.order_id]

    def on_order_deleted(self, market_id,  order_id, ref_order_id):
        with self._mutex:
            if order_id in self._orders:
                del self._orders[order_id]

    def on_order_canceled(self, market_id, order_id, ref_order_id):
        with self._mutex:
            if order_id in self._orders:
                del self._orders[order_id]

    #
    # positions slots
    #

    # @todo
