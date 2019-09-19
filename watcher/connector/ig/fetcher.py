# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# ig.com watcher implementation

import urllib
import json
import time
import traceback

from datetime import datetime
from watcher.fetcher import Fetcher

from config import config

from terminal.terminal import Terminal
from connector.ig.connector import IGConnector

import logging
logger = logging.getLogger('siis.fetcher.ig')
error_logger = logging.getLogger('siis.error.fetcher.ig')


class IGFetcher(Fetcher):
    """
    IG watcher data fetcher.
    @noto Limitation on 10000 candles per week.
    """

    def __init__(self, service):
        super().__init__("ig.com", service)

        self._host = "ig.com"
        self._connector = None
        self._account_id = ""

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                self._host = identity.get('host')
                self._account_type = "LIVE" if self._host == "api.ig.com" else "demo"
                self._account_id = identity.get('account-id')

                self._connector = IGConnector(
                    self.service,
                    identity.get('username'),
                    identity.get('password'),
                    identity.get('account-id'),
                    identity.get('api-key'),
                    identity.get('host'))

                self._connector.connect()

                self._available_instruments = set()

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

            self._connector = None

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected

    def disconnect(self):
        super().disconnect()

        try:
            if self._connector:
                self._connector.disconnect()
                self._connector = None

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def has_instrument(self, instrument, fetch_option=""):
        return True  # @todo check...

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None, fetch_option=""):
        pass

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None, fetch_option=""):
        try:
            if n_last:
                data = self._connector.history_last_n(market_id, timeframe, n_last)
            else:
                data = self._connector.history_range(market_id, timeframe, from_date, to_date)
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

            data = {}

        prices = data.get('prices', [])

        for price in prices:
            timestamp = datetime.strptime(price['snapshotTime'], '%Y:%m:%d-%H:%M:%S').timestamp()

            if price.get('highPrice')['bid'] is None and price.get('highPrice')['ask'] is None:
                # ignore empty candles
                continue

            # yield (timestamp, high bid, low, open, close, high ofr, low, open, close, volume)
            yield([int(timestamp * 1000),
                str(price.get('highPrice')['bid'] or price.get('highPrice')['ask']),
                str(price.get('lowPrice')['bid'] or price.get('lowPrice')['ask']),
                str(price.get('openPrice')['bid'] or price.get('openPrice')['ask']),
                str(price.get('closePrice')['bid'] or price.get('closePrice')['ask']),
                str(price.get('highPrice')['ask'] or price.get('highPrice')['bid']),
                str(price.get('lowPrice')['ask'] or price.get('lowPrice')['bid']),
                str(price.get('openPrice')['ask'] or price.get('openPrice')['bid']),
                str(price.get('closePrice')['ask'] or price.get('closePrice')['bid']),
                price.get('lastTradedVolume', '0')])
