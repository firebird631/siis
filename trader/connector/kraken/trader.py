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

    REST_OR_WS = True  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service):
        super().__init__("kraken.com", service)

        self._watcher = None
        self._account = KrakenAccount(self)

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

    def create_order(self, order, market_or_instrument):
        if not position_id or not market_or_instrument:
            return False

        # @todo

        return True

    def cancel_order(self, order_id, market_or_instrument):
        if not position_id or not market_or_instrument:
            return False

        # @todo

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

    def __fetch_account(self):
        # @todo use REST API to fetch account state
        self._account.update(self._watcher.connector)

    def __fetch_assets(self):
        # @todo use REST API to fetch assets balances
        pass

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

    def __update_orders(self):
        if not self.connected:
            return
