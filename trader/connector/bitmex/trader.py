# @date 2018-08-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader connector for bitmex.com

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional

if TYPE_CHECKING:
    from trader.service import TraderService
    from instrument.instrument import Instrument

import traceback
import time
import copy

import requests

from datetime import datetime
from common.utils import UTC

from trader.trader import Trader
from trader.market import Market
from trader.position import Position
from trader.order import Order

from .account import BitMexAccount

import logging
logger = logging.getLogger('siis.trader.bitmex')
error_logger = logging.getLogger('siis.error.trader.bitmex')
order_logger = logging.getLogger('siis.order.trader.bitmex')


class BitMexTrader(Trader):
    """
    BitMex real or testnet trader based on the BitMexWatcher.

    @todo verify than on_order_updated is working without the temporary fixture now it has signal from watchers
    """

    REST_OR_WS = False  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service: TraderService):
        super().__init__("bitmex.com", service)

        self._watcher = None
        self._account = BitMexAccount(self)

        self._last_position_update = 0.0
        self._last_order_update = 0.0
        self._last_update = 0.0

    def connect(self):
        super().connect()

        # retrieve the ig.com watcher and take its connector
        with self._mutex:
            self._watcher = self.service.watcher_service.watcher(self._name)

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

    def on_watcher_connected(self, watcher_name: str):
        super().on_watcher_connected(watcher_name)

        logger.info("- Trader bitmex.com retrieving data...")

        for symbol in self._watcher.connector.watched_instruments:
            self.market(symbol, True)

        with self._mutex:
            self.__fetch_orders()
            self.__fetch_positions()

            # initial account update
            self.account.update(self._watcher.connector)

        logger.info("Trader bitmex.com got data. Running.")

    def on_watcher_disconnected(self, watcher_name: str):
        super().on_watcher_disconnected(watcher_name)

    def market(self, market_id: str, force: bool = False) -> Union[Market, None]:
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param market_id:
        @param force Force to update the cache
        """
        market = self._markets.get(market_id)
        if (market is None or force) and self._watcher is not None:
            try:
                market = self._watcher.fetch_market(market_id)
                self._markets[market_id] = market
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

        return market

    @property
    def authenticated(self) -> bool:
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self) -> bool:
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

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
        """
        Here we use the WS API so its only a simple sync we process here.
        """
        if not super().update():
            return False

        if self._watcher is None or not self._watcher.connected:
            return True

        if BitMexTrader.REST_OR_WS:
            # account data update
            with self._mutex:
                try:
                    self.__fetch_account()
                except Exception as e:
                    logger.error(traceback.format_exc())

            # positions
            with self._mutex:
                try:
                    self.__fetch_positions()
                    now = time.time()
                    self._last_update = now
                except Exception as e:
                    logger.error(traceback.format_exc())

            # orders
            with self._mutex:
                try:
                    self.__fetch_orders()
                    now = time.time()
                    self._last_update = now
                except Exception as e:
                    logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

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

    #
    # global information
    #

    def has_margin(self, market_id: str, quantity: float, price: float) -> bool:
        """
        Return True for a margin trading if the account have sufficient free margin.
        Specialized because of the margin balance is defined in XBT, but computed margin is in USD.
        """
        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

            if margin:
                return self.account.margin_balance >= margin

        return False

    #
    # ordering
    #

    def create_order(self, order: Order, market_or_instrument: Union[Market, Instrument]) -> int:
        if not order or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        postdict = {
            'symbol': order.symbol,
            'clOrdID': order.ref_order_id,
        }

        qty = order.quantity

        # short means negative quantity
        if order.direction == Position.SHORT:
            qty = -qty

        exec_inst = []

        # order type
        # @todo Order.ORDER_STOP_LIMIT
        if order.order_type == Order.ORDER_MARKET:
            postdict['ordType'] = 'Market'
            postdict['orderQty'] = qty

        elif order.order_type == Order.ORDER_LIMIT:
            postdict['ordType'] = 'Limit'
            postdict['orderQty'] = qty
            postdict['price'] = order.price

            # only possible with limit order
            if order.post_only:
                exec_inst.append("ParticipateDoNotInitiate")

        elif order.order_type == Order.ORDER_STOP:
            postdict['ordType'] = 'Stop'
            postdict['orderQty'] = qty
            postdict['stopPx'] = order.stop_price

        elif order.order_type == Order.ORDER_STOP_LIMIT:
            postdict['ordType'] = 'StopLimit'
            postdict['orderQty'] = qty
            postdict['price'] = order.price
            postdict['stopPx'] = order.stop_price

        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            postdict['ordType'] = 'MarketIfTouched'
            postdict['orderQty'] = qty
            postdict['stopPx'] = order.stop_price

        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            postdict['ordType'] = 'LimitIfTouched'
            postdict['orderQty'] = qty
            postdict['price'] = order.price
            postdict['stopPx'] = order.stop_price

        else:
            postdict['ordType'] = 'Market'
            postdict['orderQty'] = qty

        # execution price for stop orders
        if order.order_type in (Order.ORDER_STOP, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            if order.price_type == Order.PRICE_LAST:
                exec_inst.append('LastPrice')
            elif order.price_type == Order.PRICE_INDEX:
                exec_inst.append('IndexPrice')
            elif order.price_type == Order.PRICE_MARK:
                 exec_inst.append('MarkPrice')

        if order.reduce_only:
            exec_inst.append("ReduceOnly")
            # exec_inst.append("Close")  # distinct for reduce only but close imply reduceOnly
            # close implies a qty or a side

        if exec_inst:
            postdict['execInst'] = ','.join(exec_inst)

        logger.info("Trader %s order %s %s @%s %s" % (self.name, order.direction_to_str(), order.symbol, order.price, order.quantity))

        # @todo could test size limit, notional limit, price limit...

        try:
            result = self._watcher.connector.request(path="order", postdict=postdict, verb='POST', max_retries=15)
        except Exception as e:
            error_logger.error(str(e))
            # @todo reason to error
            return Order.REASON_ERROR

        order_logger.info(result)

        # rejected
        if result.get('ordRejReason'):
            error_logger.error("%s rejected order %s from %s %s - cause : %s !" % (
                self.name, order.direction_to_str(), order.quantity, order.symbol, result['ordRejReason']))

            # @todo reason to error
            return Order.REASON_ERROR

        # store the order with its order id
        order.set_order_id(result['orderID'])

        order.created_time = self._parse_datetime(result.get('timestamp')).replace(tzinfo=UTC()).timestamp()
        order.transact_time = self._parse_datetime(result.get('transactTime')).replace(tzinfo=UTC()).timestamp()

        return Order.REASON_OK

    def cancel_order(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> int:
        if not order_id or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        symbol = market_or_instrument.market_id

        postdict = {
            'orderID': order_id,
        }

        try:
            result = self._watcher.connector.request(path="order", postdict=postdict, verb='DELETE', max_retries=15)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # no longer exist, accepts as ok
                error_logger.warning("%s rejected cancel order %s %s - cause : no longer exists !" % (self.name,
                                                                                                      order_id, symbol))

                # @todo question
                return Order.REASON_OK
            else:
                error_logger.error("%s rejected cancel order %s %s - cause : %s !" % (self.name, order_id,
                                                                                      symbol, str(e)))

                # @todo error to reason
                return Order.REASON_ERROR
        except Exception as e:
            error_logger.error(str(e))

            # @todo error to reason
            return Order.REASON_ERROR

        order_logger.info(result)

        return Order.REASON_OK

    def close_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                       direction: int, quantity: float, market: bool = True,
                       limit_price: Optional[float] = None) -> bool:
        """Not supported, use create_order for that"""
        return False

    def modify_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                        stop_loss_price: Optional[float] = None, take_profit_price: Optional[float] = None) -> bool:
        """Not supported, use cancel_order/create_order for that"""
        return False

    #
    # slots
    #

    # def on_order_updated(self, market_id: str, order_data: dict, ref_order_id: str):
    #     with self._mutex:
    #         if not order_data['symbol'] in self._markets.get(order_data['symbol'])
    #             return

    #     try:
    #         self.__update_orders()
    #     except Exception as e:
    #         logger.error(repr(e))

    #
    # private
    #

    def _parse_datetime(self, date_str):
        return datetime.strptime(date_str or '1970-01-01 00:00:00.000Z', "%Y-%m-%dT%H:%M:%S.%fZ") # .%fZ")

    #
    # protected
    #

    def __fetch_account(self):
        # @todo use REST API to fetch account state
        self._account.update(self._watcher.connector)

    def __fetch_positions(self):
        # @todo use REST API to fetch open positions
        for symbol, market in self._markets.items():
            return self.__update_positions(symbol, market)

    def __fetch_orders(self):
        # @todo use REST API to fetch open orders
        return self.__update_orders()

    def __update_positions(self, symbol, market):
        if not self.connected:
            return

        # position for each configured market
        for symbol, market in self._markets.items():
            pos = self._watcher.connector.ws.position(symbol)
            position = None

            if self._positions.get(symbol):
                position = self._positions.get(symbol)

            elif pos['isOpen']:
                # insert the new position
                position = Position(self)
                position.set_position_id(symbol)
                position.set_key(self.service.gen_key())

                quantity = abs(float(pos['currentQty']))
                direction = Position.SHORT if pos['currentQty'] < 0 else Position.LONG

                position.entry(direction, symbol, quantity)

                position.leverage = pos['leverage']

                position.entry_price = pos['avgEntryPrice']
                position.created_time = datetime.strptime(pos['openingTimestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=UTC()).timestamp()

                # id is symbol
                self._positions[symbol] = position

            elif (not pos['isOpen'] or pos['currentQty'] == 0) and self._positions.get(symbol):
                # no more position
                del self._positions[symbol]

            if position:
                # absolute value because we work with positive quantity + direction information
                position.quantity = abs(float(pos['currentQty']))
                position.direction = Position.SHORT if pos['currentQty'] < 0 else Position.LONG

                position.leverage = pos['leverage']

                # position.market_close = pos['market_close']
                position.entry_price = pos['avgEntryPrice']
                position.created_time = datetime.strptime(pos['openingTimestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=UTC()).timestamp()

                # XBt to XBT
                ratio = 1.0
                if pos['currency'] == 'XBt':
                    ratio = 1.0 / 100000000.0

                # @todo minus taker-fee
                position.profit_loss = (float(pos['unrealisedPnl']) * ratio)
                position.profit_loss_rate = float(pos['unrealisedPnlPcnt'])

                # @todo minus maker-fee
                position.profit_loss_market = (float(pos['unrealisedPnl']) * ratio)
                position.profit_loss_market_rate = float(pos['unrealisedPnlPcnt'])

                # compute profit loss in base currency (disabled, uses values above)
                # position.update_profit_loss(market)

    def __update_orders(self):
        if not self.connected:
            return

        # filters only siis managed orders
        src_orders = self._watcher.connector.ws.open_orders("") # "siis_")

        # first delete older orders
        order_rm_list = []
        for k, order in self._orders.items():
            found = False
            
            for src_order in src_orders:
                src_order_id = src_order['clOrdID'] or src_order['orderID']

                if order.order_id == src_order['clOrdID'] or order.order_id == src_order['orderID']:
                    found = True
                    break

            if not found:
                order_rm_list.append(order.order_id)

        for order_id in order_rm_list:
            del self._orders[order_id]

        # insert or update active orders
        for src_order in src_orders:
            found = False
            src_order_id = src_order['clOrdID'] or src_order['orderID']

            order = self._orders.get(src_order_id)

            if order is None:
                # insert
                order = Order(self, src_order['symbol'])
                order.set_order_id(src_order_id)

                self._orders[order.order_id] = order
            else:
                order = self._orders.get(src_order_id)

            # logger.info(src_order)

            # probably modifier or when leavesQty is update the ordStatus must change
            # if src_order['ordStatus'] != "New":
            #   continue

            # update
            order.direction = Position.LONG if src_order['side'] == 'Buy' else Position.SHORT
            # 'orderQty' (ordered qty), 'cumQty' (cumulative done), 'leavesQty' (remaining)
            order.quantity = src_order.get('leavesQty', src_order.get('orderQty', 0))

            if src_order.get('transactTime'):
                order.transact_time = self._parse_datetime(src_order.get('transactTime')).replace(
                    tzinfo=UTC()).timestamp()

            if src_order['ordType'] == "Market":
                order.order_type = Order.ORDER_MARKET

            elif src_order['ordType'] == "Limit":
                order.order_type = Order.ORDER_LIMIT
                order.price = src_order.get('price')

            elif src_order['ordType'] == "Stop":
                order.order_type = Order.ORDER_STOP
                order.stop_price = src_order.get('stopPx')

            elif src_order['ordType'] == "StopLimit":
                order.order_type = Order.ORDER_STOP_LIMIT
                order.price = src_order.get('price')
                order.stop_price = src_order.get('stopPx')

            elif src_order['ordType'] == "MarketIfTouched":
                order.order_type = Order.ORDER_TAKE_PROFIT
                order.stop_price = src_order.get('stopPx')

            elif src_order['ordType'] == "LimitIfTouched":
                order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                order.price = src_order.get('price')
                order.stop_price = src_order.get('stopPx')

            if src_order['timeInForce'] == 'GoodTillCancel':
                order.time_in_force = Order.TIME_IN_FORCE_GTC
            elif src_order['timeInForce'] == 'ImmediateOrCancel':
                order.time_in_force = Order.TIME_IN_FORCE_IOC
            elif src_order['timeInForce'] == 'FillOrKill':
                order.time_in_force = Order.TIME_IN_FORCE_FOK
            else:
                order.time_in_force = Order.TIME_IN_FORCE_GTC

            # triggered, ordRejReason, currency
            # @todo

            # execution options
            exec_inst = src_order['execInst'].split(',')

            # taker or maker fee
            if 'ParticipateDoNotInitiate' in exec_inst:
                order.post_only = True
            else:
                order.post_only = False

            # close reduce only
            if 'Close' in exec_inst:
                # close only order (must be used with reduce only, only reduce a position, and close opposites orders)
                order.close_only = True
            else:
                order.close_only = False

            # close reduce only
            if 'ReduceOnly' in exec_inst:
                # reduce only order (only reduce a position)
                order.reduce_only = True
            else:
                order.redeuce_only = False

            # execution price
            if 'LastPrice' in exec_inst:
                order.price_type = Order.PRICE_LAST
            elif 'IndexPrice' in exec_inst:
                order.price_type = Order.PRICE_MARK
            elif 'MarkPrice' in exec_inst:
                order.price_type = Order.PRICE_INDEX
