# @date 2018-08-21
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader/autotrader connector for bitmex.com

import time
import base64
import uuid
import copy
import requests

from datetime import datetime
from common.utils import UTC

from trader.trader import Trader
from trader.market import Market

from .account import BitMexAccount

from trader.position import Position
from trader.order import Order

from connector.bitmex.connector import Connector

import logging
logger = logging.getLogger('siis.trader.bitmex')
error_logger = logging.getLogger('siis.error.bitmex')
order_logger = logging.getLogger('siis.order.bitmex')


class BitMexTrader(Trader):
    """
    BitMex real or testnet trader based on the BitMexWatcher.

    @todo verify than on_order_updated is working without the temporary fixture now it has signal from watchers
    """

    REST_OR_WS = False  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service):
        super().__init__("bitmex.com", service)

        self._watcher = None
        self._account = BitMexAccount(self)

        self._last_position_update = 0
        self._last_order_update = 0

    def connect(self):
        super().connect()

        # retrieve the ig.com watcher and take its connector
        self.lock()

        self._watcher = self.service.watcher_service.watcher(self._name)

        if self._watcher:
            self.service.watcher_service.add_listener(self)
        
        self.unlock()

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)

    def disconnect(self):
        super().disconnect()

        self.lock()
    
        if self._watcher:
            self.service.watcher_service.remove_listener(self)
            self._watcher = None

        self.unlock()

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        # markets, orders and positions
        logger.info("- Trader bitmex.com retrieving symbols and markets...")

        configured_symbols = self.configured_symbols()
        matching_symbols = self.matching_symbols_set(configured_symbols, self._watcher.watched_instruments())

        # markets, orders and positions
        self.lock()

        for symbol in matching_symbols:
            self.market(symbol, True)

        self.__fetch_orders()
        self.__fetch_positions()

        self.unlock()

        # initial account update
        self.account.update(self._watcher.connector)

        logger.info("Trader bitmex.com got data. Running.")

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
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
    def authenticated(self):
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self):
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

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
        """
        Here we use the WS API so its only a simple sync we process here.
        """
        if not super().update():
            return False

        if self._watcher is None or not self._watcher.connected:
            return True

        if BitMexTrader.REST_OR_WS:
            # account data update
            try:
                self.lock()
                self.__fetch_account()
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

            # positions
            try:
                self.lock()
                self.__fetch_positions()

                now = time.time()
                self._last_update = now
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

            # orders
            try:
                self.lock()
                self.__fetch_orders()

                now = time.time()
                self._last_update = now
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    @Trader.mutexed
    def create_order(self, order):
        if not order:
            return False

        if not self.has_market(order.symbol):
            logger.error("%s does not support market %s in order %s !" % (self.name, order.symbol, order.order_id))
            return False

        if not self._activity:
            return False

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

        try:
            result = self._watcher.connector.request(path="order", postdict=postdict, verb='POST', max_retries=15)
        except Exception as e:
            error_logger.error(str(e))
            return False

        order_logger.info(result)
        
        # rejected
        if result.get('ordRejReason'):
            error_logger.error("%s rejected order %s from %s %s - cause : %s !" % (
                self.name, order.direction_to_str(), order.quantity, order.symbol, result['ordRejReason']))

            return False

        # store the order with its order id
        order.set_order_id(result['orderID'])

        order.created_time = self._parse_datetime(result.get('timestamp')).replace(tzinfo=UTC()).timestamp()
        order.transact_time = self._parse_datetime(result.get('transactTime')).replace(tzinfo=UTC()).timestamp()

        self._orders[order.order_id] = order

        return True

    @Trader.mutexed
    def cancel_order(self, order_id):
        # DELETE endpoint=order
        if not self._activity:
            return False

        order = self._orders.get(order_id)

        if order is None:
            logger.error("%s does not found order %s !" % (self.name, order_id))
            return False

        symbol = order.symbol or ""

        postdict = {
            'orderID': order_id,
        }

        try:
            result = self._watcher.connector.request(path="order", postdict=postdict, verb='DELETE', max_retries=15)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # no longer exist, accepts as ok
                error_logger.warning("%s rejected cancel order %s %s - cause : no longer exists !" % (self.name, order_id, symbol))
                return True
            else:
                error_logger.error("%s rejected cancel order %s %s - cause : %s !" % (self.name, order_id, symbol, str(e)))
                return False
        except Exception as e:
            error_logger.error(str(e))
            return False

        order_logger.info(result)

        return True

    @Trader.mutexed
    def close_position(self, position_id, market=True, limit_price=None):
        if not self._activity:
            return False

        position = self._positions.get(position_id)

        if position is None or not position.is_opened():
            return False

        if not self.has_market(position.symbol):
            logger.error("%s does not support market %s on close position %s !" % (
                self.name, position.symbol, position.position_id))
            return False

        ref_order_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')

        # keep for might be useless in this case
        order.set_ref_order_id(ref_order_id)

        order = Order(self, position.symbol)
        order.set_position_id(position.position_id)
        order.quantity = position.quantity
        order.direction = -position.direction  # neg direction

        postdict = {
            'symbol': order.symbol,
            'clOrdID': ref_order_id,
            'execInst': 'Close',
            # 'execInst': 'ReduceOnly,Close'  # @todo why rejected with ReduceOnly ?
        }

        # short mean negative quantity
        if order.direction == Position.SHORT:
            qty = -qty

        # fully close (using Close and need 'side' when qty is not defined)
        # qty = None

        # order type
        if market:
            order.order_type = Order.ORDER_MARKET
            postdict['ordType'] = "Market"
            postdict['orderQty'] = qty
        else:
            order.order_type = Order.ORDER_LIMIT
            order.price = limit_price

            postdict['ordType'] = "Limit"
            postdict['price'] = order.price
            postdict['orderQty'] = qty

        if qty is None:
            postdict['side'] = "Buy" if order.direction > 0 else "Sell"

        try:
            result = self._watcher.connector.request(path="order", postdict=postdict, verb='POST', max_retries=15)
        except Exception as e:
            logger.error(str(e))
            return False

        if result and result.get('ordRejReason'):
            logger.error("%s rejected closing order %s from %s %s - cause : %s !" % (
                self.name, order.direction_to_str(), order.quantity, order.symbol, result['ordRejReason']))
            return False

        # store the order with its order id
        order.set_order_id(result['orderID'])

        # and store the order
        self._orders[order.order_id] = order

        # set position closing until we get confirmation on a next update
        position.closing(limit_price)

        return True

    @Trader.mutexed
    def modify_position(self, position_id, stop_loss_price=None, take_profit_price=None):
        """Not supported"""        
        return False

    def positions(self, market_id):
        self.lock()

        position = self._positions.get(market_id)
        if position:
            positions = [copy.copy(position)]
        else:
            positions = []

        self.unlock()
        return positions

    #
    # slots
    #

    @Trader.mutexed
    def on_order_updated(self, market_id, order_data, ref_order_id):
        market = self._markets.get(order_data['symbol'])
        if market is None:
            # not interested by this market
            return

        try:
            # @todo temporary substitution
            self.__update_orders()
        except Exception as e:
            logger.error(repr(e))

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
                position.created_time = datetime.strptime(pos['openingTimestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC()).timestamp()

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
                position.created_time = datetime.strptime(pos['openingTimestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC()).timestamp()

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

                # compute profit loss in base currency (disabled, uses values aboves)
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
            # 'orderQty' (ordered qty), 'cumQty' (cumulative done), 'leavesQty' (remaning)
            order.quantity = src_order.get('leavesQty', src_order.get('orderQty', 0))

            if src_order.get('transactTime'):
                order.transact_time = self._parse_datetime(src_order.get('transactTime')).replace(tzinfo=UTC()).timestamp()

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
