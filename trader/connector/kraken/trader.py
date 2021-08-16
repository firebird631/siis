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

        self._quotes = ("ZUSD", "ZEUR", "ZCAD", "ZAUD", "ZJPY", "XXBT", "XETH")

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

        # fetch account data each minute
        with self._mutex:
            try:
                self.__fetch_account()
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    @Trader.mutexed
    def on_asset_updated(self, asset_name, locked, free):
        asset = self._assets.get(asset_name)
        if asset is not None:
            asset.set_quantity(locked, free)

            market_id = asset.market_ids[0] if asset.market_ids else asset.symbol+asset.quote if asset.quote else None
            market = self._markets.get(market_id)
            if market:
                asset.update_profit_loss(market)

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

    def order_info(self, order_id, market_or_instrument):
        if not order_id or not market_or_instrument:
            return None

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to retrieve order info because of missing connector" % (self.name,))
            return None

        results = None

        try:
            results = self._watcher.connector.get_orders_info(txids=[order_id])
        except Exception:
            # None as error
            return None

        if results and order_id in results:
            order_data = results[order_id]

            try:
                descr = order_data['descr']
                symbol = self._watcher.market_alias(descr['pair'])
                market = self.market(symbol)

                if not market:
                    return None

                price = None
                stop_price = None
                completed = False
                order_ref_id = ""
                event_timestamp = float(order_data['lastupdated']) if 'lastupdated' in order_data else float(order_data['opentm'])

                if order_data['status'] == 'open':
                    status = 'opened'
                elif order_data['status'] == 'pending':
                    status = 'pending'
                elif order_data['status'] == 'closed':
                    status = 'closed'
                    completed = True
                    if 'closetm' in order_data:
                        event_timestamp = float(order_data['closetm'])
                elif order_data['status'] == 'deleted':
                    status = 'deleted'
                elif order_data['status'] == 'canceled':
                    status = 'canceled'
                elif order_data['status'] == 'expired':
                    status = 'canceled'
                    # completed = True ? and on watcher WS...
                else:
                    status = ""

                if order_data['userref']:
                    # userref is int
                    order_ref_id = str(order_data['userref'])

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

                if order_data['expiretm'] is not None and order_data['expiretm'] > 0:
                    time_in_force = Order.TIME_IN_FORCE_GTD
                    expiry = float(order_data['expiretm'])

                if descr['leverage'] is not None and descr['leverage'] != 'none':
                    margin_trade = True
                    leverage = int(descr['leverage'])
                else:
                    margin_trade = False
                    leverage = 0

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

                # trades = array of trade ids related to order (if trades info requested and data available)
                trades = []

                order_info = {
                    'id': order_id,
                    'symbol': symbol,
                    'status': status,
                    'ref-id': order_ref_id,
                    'direction': Order.LONG if descr['type'] == "buy" else Order.SHORT,
                    'type': order_type,
                    'timestamp': event_timestamp,
                    'avg-price': float(order_data['price']),
                    'quantity': order_volume,
                    'cumulative-filled': cumulative_filled,
                    'cumulative-commission-amount': float(order_data['fee']),
                    'price': price,
                    'stop-price': stop_price,
                    'time-in-force': time_in_force,
                    'post-only': post_only,
                    # 'close-only': ,
                    # 'reduce-only': ,
                    'stop-loss': None,
                    'take-profit': None,
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
    # protected
    #

    def __fetch_account(self):
        self._account.update(self._watcher.connector)

    def __fetch_assets(self):
        assets = self._watcher.connector.assets()
        balances = self._watcher.connector.get_balances()
        # open_orders = self._watcher.connector.get_open_orders()
        instruments = self._watcher.connector.instruments()

        for asset_name, data in assets.items():
            if asset_name.endswith('.S') or asset_name.endswith('.M') or asset_name.endswith('.HOLD'):
                continue

            if asset_name == 'KFEE':
                continue

            asset = Asset(self, asset_name, data.get('decimals', 8))

            for market_id, instrument in instruments.items():
                if market_id.endswith('.d') or market_id.endswith('.S') or market_id.endswith('.M') or market_id.endswith('.HOLD'):
                    continue

                has_currency = False
                has_alt_currency = False

                # find related markets
                if instrument.get('base', "") == asset_name:
                    quote = instrument.get('quote', "")

                    if quote == self._account.currency:
                        asset.add_market_id(market_id, True)
                        has_currency = True
                    elif quote == self._account.alt_currency:
                        asset.add_market_id(market_id)
                        has_alt_currency = True

                if has_currency:
                    asset.quote = self._account.currency

                if not asset.quote and has_alt_currency:
                    asset.quote = self._account.alt_currency

            self._assets[asset_name] = asset

            if not asset.quote:
                logger.warning("No found quote for asset %s" % asset.symbol)

        for asset_name, balance in balances.items():
            asset = self._assets.get(asset_name)

            if asset:
                # cannot distinct from locked to free, compute locked from active orders
                asset.set_quantity(0.0, float(balance))

                # uses open orders to found the locked quantity
                # @todo

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
        open_orders = self._watcher.connector.get_open_orders()

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
                    # userref is int
                    order.set_ref_order_id(str(data['userref']))

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

                # only have the order open timestamp
                order.created_time = data['opentm']
                order.transact_time = data['opentm']

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
