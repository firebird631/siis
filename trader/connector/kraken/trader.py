# @date 2019-08-28
# @author Frederic SCHERMA
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

        if KrakenTrader.REST_OR_WS:
            # account data update
            with self._mutex:
                try:
                    self.__fetch_account()
                    self.__fetch_assets()
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

            # positions
            with self._mutex:
                try:
                    self.__fetch_positions()
                    now = time.time()
                    self._last_update = now
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

            # orders
            with self._mutex:
                try:
                    self.__fetch_orders()
                    now = time.time()
                    self._last_update = now
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

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
        #     error_logger.error("Trader %s refuse order because the min size is not reached (%.f<%.f) %s in order %s !" % (
        #         self.name, order.quantity, market_or_instrument.min_size, pair, order.ref_order_id))
        #     return False

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        # volume = market_or_instrument.format_quantity(market_or_instrument.adjust_quantity(order.quantity))
        volume = market_or_instrument.adjust_quantity(order.quantity or 0.1)
        notional = volume * (order.price or market_or_instrument.market_ofr)

        # if notional < market_or_instrument.min_notional:
        #     # reject if lesser than min notinal
        #     error_logger.error("Trader %s refuse order because the min notional is not reached (%.f<%.f) %s in order %s !" % (
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

        # limit order need timeInForce
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

        data['userref'] = int(order.ref_order_id)  # 32bits integer

        # starttm (for scheduled start time, 0 now)
        # expiretm (for expiration time, 0, none or not defined no expiry)

        # close[ordertype], close[price], close[price2] for optional closing order

        # @todo for testing only
        # data['validate'] = True

        logger.info("Trader %s order %s %s %s @%s" % (self.name, order.direction_to_str(), data.get('quantity'), pair, data.get('price')))

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

                order.set_order_id(str(result.get('txid')))

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
            result = self._watcher.connector.cancel_order(order_id)
        except Exception as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, pair, reason))
            return False

        if result.get('count', 0) <= 0:
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, pair, reason))
            order_logger.error(result)
            return False

        order_logger.info(result)

        return True

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

        # # find the most appriopriate quote of an asset.
        quote_symbol = None

        if asset.symbol == self._account.currency and self._watcher.has_instrument(asset.symbol+self._account.alt_currency):
            # probably BTCUSDT
            quote_symbol = self._account.alt_currency
        elif asset.symbol != self._account.currency and self._watcher.has_instrument(asset.symbol+self._account.currency):
            # any pair based on BTC
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
        positions = self._watcher.connector.get_open_positions()

        for position in positions:
            pass

    def __fetch_orders(self):
        orders = self._watcher.connector.get_open_orders()

        for order in orders:
            pass
