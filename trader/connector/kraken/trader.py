# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Trader/autotrader connector for kraken.com

import traceback
import time
import base64
import uuid
import copy
import requests

from datetime import datetime

from common.signal import Signal

from trader.trader import Trader
from trader.market import Market

from .account import KrakenAccount

from trader.position import Position
from trader.order import Order
from trader.asset import Asset

from connector.kraken.connector import Connector
from database.database import Database

import logging
logger = logging.getLogger('siis.trader.kraken')
error_logger = logging.getLogger('siis.error.trader.kraken')
order_logger = logging.getLogger('siis.order.trader.kraken')
traceback_logger = logging.getLogger('siis.traceback.trader.kraken')


class KrakenTrader(Trader):
    """
    Kraken real trader.
    """

    REST_OR_WS = False  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service):
        super().__init__("kraken.com", service)

        self._watcher = None
        self._account = KrakenAccount(self)

        self._quotes = ("ZUSD", "ZEUR", "ZCAD", "ZJPY", "XXBT", "XETH")

        self._last_position_update = 0
        self._last_order_update = 0

    def connect(self):
        super().connect()

        # retrieve the kraken.com watcher and take its connector
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

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        # markets, orders and positions
        logger.info("- Trader kraken.com retrieving data...")

        with self._mutex:
            self.__fetch_assets()
            self.__fetch_orders()
            self.__fetch_positions()

            # initial account update
            self._account.update(self._watcher.connector)

        logger.info("Trader kraken.com got data. Running.")

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
                if market:
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

        # if KrakenTrader.REST_OR_WS:
        #     # @todo need wait time
        #     # account data update
        #     with self._mutex:
        #         try:
        #             self.__fetch_account()
        #             self.__fetch_assets()
        #         except Exception as e:
        #             error_logger.error(repr(e))
        #             traceback_logger.error(traceback.format_exc())

        #     # positions
        #     with self._mutex:
        #         try:
        #             self.__fetch_positions()
        #             now = time.time()
        #             self._last_update = now
        #         except Exception as e:
        #             error_logger.error(repr(e))
        #             traceback_logger.error(traceback.format_exc())

        #     # orders
        #     with self._mutex:
        #         try:
        #             self.__fetch_orders()
        #             now = time.time()
        #             self._last_update = now
        #         except Exception as e:
        #             error_logger.error(repr(e))
        #             traceback_logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    @Trader.mutexed
    def on_asset_updated(self, asset_name, locked, free):
        asset = self.__get_or_add_asset(asset_name)
        if asset is not None:
            # significant deviation... @todo update qty after traded signal
            # if abs((locked+free)-asset.quantity) / ((locked+free) or 1.0) >= 0.001:
            #     logger.debug("%s deviation of computed quantity for %s from %s but must be %s" % (self._name, asset_name, asset.quantity, (locked+free)))

            asset.set_quantity(locked, free)

            if asset.quote and asset.symbol != asset.quote:
                prefered_market = self._markets.get(asset.symbol+asset.quote)
                if prefered_market:
                    asset.update_profit_loss(prefered_market)

            # store in database with the last update quantity
            Database.inst().store_asset((self._name, self.account.name,
                asset_name, asset.last_trade_id, int(asset.last_update_time*1000.0),
                asset.quantity, asset.price, asset.quote))

        # call base for stream
        super().on_asset_updated(asset_name, locked, free)

    #
    # ordering
    #

    @staticmethod
    def to_signed_int(i):
        return (i + 2**31) % 2**32 - 2**31

    def set_ref_order_id(self, order):
        """
        Kraken wait for a 32 bits integer.
        """
        if order and not order.ref_order_id:
            n = datetime.utcnow()
            order.set_ref_order_id("%i" % KrakenTrader.to_signed_int(
                (n.month << 28 | n.day << 23 | n.hour << 18 | n.minute << 12 | n.second << 6 | int(n.microsecond * 0.00006))))

            return order.ref_order_id

        return None

    def create_order(self, order, market_or_instrument):
        if not order or not market_or_instrument:
            return False

        # oflags = comma delimited list of order flags (optional):
        #     viqc = volume in quote currency (not available for leveraged orders)
        #     fcib = prefer fee in base currency
        #     fciq = prefer fee in quote currency
        #     nompp = no market price protection
        #     post = post only order (available when ordertype = limit)

        # fees always on quote
        oflags = ['fciq']

        # order type (what is stop-loss-profit)
        if order.order_type == Order.ORDER_LIMIT:
            ordertype = "limit"
            if order.post_only:
                oflags.append("post")
        elif order.order_type == Order.ORDER_STOP:
            ordertype = "stop-loss"
        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            ordertype = "take-profit"
        elif order.order_type == Order.ORDER_STOP_LIMIT:
            ordertype = "stop-loss-limit"
        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            ordertype = "take-profit-limit"
        else:
            ordertype = "market"

        pair = order.symbol
        _type = "buy" if order.direction == Position.LONG else "sell"

        # @todo as option for the order strategy
        # time_in_force = Client.TIME_IN_FORCE_GTC

        # if order.quantity < market_or_instrument.min_size:
        #     # reject if lesser than min size
        #     error_logger.error("Trader %s refuse order because the min size is not reached (%s<%s) %s in order %s !" % (
        #         self.name, order.quantity, market_or_instrument.min_size, pair, order.ref_order_id))
        #     return False

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        # volume = market_or_instrument.format_quantity(market_or_instrument.adjust_quantity(order.quantity))
        volume = market_or_instrument.adjust_quantity(order.quantity)
        notional = volume * (order.price or market_or_instrument.market_ask)

        # if notional < market_or_instrument.min_notional:
        #     # reject if lesser than min notinal
        #     error_logger.error("Trader %s refuse order because the min notional is not reached (%s<%s) %s in order %s !" % (
        #         self.name, notional, market_or_instrument.min_notional, pair, order.ref_order_id))
        #     return False

        data = {
            'pair': pair,
            'type': _type,
            'ordertype': ordertype,
            'volume': volume,
            'oflags': ','.join(oflags)
        }

        if order.margin_trade:
            data['leverage'] = order.leverage

        if order.order_type == Order.ORDER_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
        elif order.order_type == Order.ORDER_STOP:
            data['price'] = market_or_instrument.format_price(order.stop_price)
        elif order.order_type == Order.ORDER_STOP_LIMIT:
            data['price2'] = market_or_instrument.format_price(order.price)
            data['price'] = market_or_instrument.format_price(order.stop_price)
        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            data['price'] = market_or_instrument.format_price(order.stop_price)
        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            data['price2'] = market_or_instrument.format_price(order.price)
            data['price'] = market_or_instrument.format_price(order.stop_price)

        data['userref'] = int(order.ref_order_id) if order.ref_order_id else 0  # 32bits integer

        # starttm (for scheduled start time, 0 now)
        # expiretm (for expiration time, 0, none or not defined no expiry)

        # close['ordertype'], close['price'], close['price2'] for optional closing order

        # @todo for testing only
        # data['validate'] = True

        logger.info("Trader %s order %s %s %s @%s" % (self.name, order.direction_to_str(), data.get('volume'), pair, data.get('price')))

        results = None
        reason = None

        try:
            results = self._watcher.connector.create_order(data)
        except Exception as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected order %s %s %s - reason : %s !" % (self.name, order.direction_to_str(), volume, pair, reason))
            return False

        if results:
            if results.get('error', []):
                reason = ','.join(results['error'])

                error_logger.error("Trader %s rejected order %s %s %s - reason : %s !" % (self.name, order.direction_to_str(), volume, pair, reason))
                order_logger.error(results)

                return False

            elif results.get('result', {}):
                result = results['result']

                order_logger.info(results)

                order.set_order_id(str(result.get('txid')[0]))

                order.created_time = time.time()
                order.transact_time = time.time()

                return True

        error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(), volume, pair))
        order_logger.error(results)

        return False

    def cancel_order(self, order_id, market_or_instrument):
        if not order_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return False

        pair = market_or_instrument.market_id

        reason = None
        result = None

        try:
            results = self._watcher.connector.cancel_order(order_id)
        except Exception as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, pair, reason))
            return False

        if results:
            if results.get('error', []):
                reason = ','.join(results['error'])

                error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, pair, reason))
                order_logger.error(results)

                return False

            elif results.get('result', {}):
                result = results['result']

                if result.get('count', 0) <= 0:
                    error_logger.error("Trader %s cancel order %s %s invalid count !" % (self.name, order_id, pair))
                    order_logger.error(result)
                    return False

                else:
                    order_logger.info(result)
                    return True

        error_logger.error("Trader %s rejected cancel order %s %s !" % (self.name, order_id, pair))
        order_logger.error(results)

        return False

    def close_position(self, position_id, market_or_instrument, direction, quantity, market=True, limit_price=None):
        if not position_id or not market_or_instrument:
            return False

        ref_order_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')

        # keep for might be useless in this case
        order.set_ref_order_id(ref_order_id)

        order = Order(self, market_or_instrument.market_id)
        order.set_position_id(position_id)
        order.quantity = quantity
        order.direction = -direction  # neg direction

        # @todo

        return True

    def modify_position(self, position_id, market_or_instrument, stop_loss_price=None, take_profit_price=None):
        """Not supported"""
        return False

    def positions(self, market_id):
        """
        @deprecated
        """
        with self._mutex:
            position = self._positions.get(market_id)
            if position:
                positions = [copy.copy(position)]
            else:
                positions = []

            return positions

    #
    # protected
    #

    def __get_or_add_asset(self, asset_name, precision=8):
        if asset_name in self._assets:
            return self._assets[asset_name]

        asset = Asset(self, asset_name, precision)
        self._assets[asset_name] = asset

        # and find related watched markets
        for qs in self._quotes:
            if asset_name+qs in self._markets:
                asset.add_market_id(asset_name+qs)

        # find the most appriopriate quote of an asset.
        quote_symbol = None

        # @todo update
        if asset.symbol == self._account.currency and self._watcher.has_instrument(asset.symbol+self._account.alt_currency):
            # probably XXBTZUSD
            quote_symbol = self._account.alt_currency
        elif asset.symbol != self._account.currency and self._watcher.has_instrument(asset.symbol+self._account.currency):
            # any pair based on XBT
            quote_symbol = self._account.currency
        else:
            # others case but might not occurs often because most of the assets are expressed in BTC
            for qs in self._quotes:
                if self._watcher.has_instrument(asset.symbol+qs):
                    quote_symbol = qs
                    break

        if not quote_symbol:
            if not asset.quote:
                logger.warning("No found quote for asset %s" % asset.symbol)

            quote_symbol = asset.symbol

        asset.quote = quote_symbol

        return asset

    def __fetch_account(self):
        self._account.update(self._watcher.connector)

    def __fetch_assets(self):
        balances = self._watcher.connector.get_balances()

        for asset_name, balance in balances.items():
            asset = self.__get_or_add_asset(asset_name)

            asset_info = self._watcher._assets.get(asset_name)

            if asset_info:
                asset.precision = asset_info.get('decimals', 8)

            # @todo how to distinct locked from free ?
            asset.set_quantity(0.0, float(balance))

    def __fetch_positions(self):
        open_positions = self._watcher.connector.get_open_positions()

        positions = {}

        for tx_id, data in open_positions:
            # @todo
            pass

        if positions:
            with self._mutex:
                self._positions = positions

    def __fetch_orders(self):
        open_orders = self._watcher.connector.get_open_orders()  # userref=int

        orders = {}

        for order_id, data in open_orders.items():
            try:
                descr = data['descr']
                symbol = self._watcher.market_alias(descr['pair'])
                market = self.market(symbol)

                if not market:
                    continue

                # must be
                if data['status'] != 'open':
                    continue

                order = Order(self, symbol)

                order.set_order_id(order_id)

                if data['userref']:
                    order.set_ref_order_id(str(data['refid']))

                # if data['refid']:
                #     order.set_ref_order_id(data['refid'])

                order.quantity = float(data.get('vol', "0.0"))
                order.executed = float(data.get('vol_exec', "0.0"))

                order.direction = Order.LONG if descr['type'] == 'buy' else Order.SHORT

                if descr['leverage'] is not None and descr['leverage'] != 'none':
                    order.margin_trade = True
                    order.leverage = int(descr['leverage'])

                if descr['ordertype'] == "limit":
                    order.order_type = Order.ORDER_LIMIT
                    order.price = float(descr['price']) if 'price' in descr else None

                elif descr['ordertype'] == "stop-loss":
                    order.order_type = Order.ORDER_STOP
                    order.stop_price = float(descr['price']) if 'price' in descr else None

                elif descr['ordertype'] == "take-profit":
                    order.order_type = Order.ORDER_TAKE_PROFIT
                    order.stop_price = float(descr['price']) if 'price' in descr else None

                elif descr['ordertype'] == "stop-loss-limit":
                    order.order_type = Order.ORDER_STOP_LIMIT
                    order.price = float(descr['price2']) if 'price2' in descr else None
                    order.stop_price = float(descr['price']) if 'price' in descr else None

                elif descr['ordertype'] == "take-profit-limit":
                    order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    order.price = float(descr['price2']) if 'price2' in descr else None
                    order.stop_price = float(descr['price']) if 'price' in descr else None

                elif descr['ordertype'] == "market":
                    order.order_type = Order.ORDER_MARKET

                # stop-loss-profit
                order.created_time = data['opentm']
                order.transact_time = data['starttm']

                if data['oflags']:
                    flags = data['oflags'].split(',')

                    if 'fcib' in flags:
                        # fee in base currency
                        pass

                    elif 'fciq' in flags:
                        # fee in quote currency:
                        pass

                    if 'post' in flags:
                        order.post_only = True

                if data['misc']:
                    misc = data['misc'].split(',')

                    # stopped = triggered by stop price
                    # touched = triggered by touch price
                    # liquidated = liquidation

                if data['expiretm'] is not None and data['expiretm'] > 0:
                    order.time_in_force = Order.TIME_IN_FORCE_GTD
                    # @todo order.expiry = float(data['expiretm'])

                # cost = total cost (quote currency unless unless viqc set in oflags)
                # fee = total fee (quote currency)
                # price = average price (quote currency unless viqc set in oflags)

                # conditional close
                if descr['close']:
                    pass  # @todo

                # @todo
                # trades = array of trade ids related to order (if trades info requested and data available)

                orders[order.order_id] = order

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

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
