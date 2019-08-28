# @date 2019-08-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# www.kraken.com data fetcher

import json
import time
import traceback

from watcher.fetcher import Fetcher

from connector.binance.connector import Connector

from config import config

import logging
logger = logging.getLogger('siis.fetcher.kraken')
error_logger = logging.getLogger('siis.error.fetcher.kraken')


class KrakenFetcher(Fetcher):
    """
    Kraken market data fetcher.
    """

    TF_MAP = {
        60: '1m',
        180: '3m',
        300: '5m',
        900: '15m',
        1800: '30m',
        3600: '1h',
        7200: '2h',
        14400: '4h',
        21600: '6h',
        28800: '8h',
        43200: '12h',
        86400: '1d',
        259200: '3d',
        604800: '1w',
        2592000: '1M'
    }

    def __init__(self, service):
        super().__init__("kraken.com", service)

        self._connector = None

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                if not self._connector:
                    self._connector = Connector(
                        self.service,
                        identity.get('api-key'),
                        identity.get('api-secret'),
                        identity.get('host'))

                if not self._connector.connected:
                    self._connector.connect(use_ws=False)

                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                # @todo

                # instruments = self._connector.client.get_products().get('data', [])

                # for instrument in instruments:
                #     self._available_instruments.add(instrument['symbol'])

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def disconnect(self):
        super().disconnect()

        try:
            if self._connector:
                self._connector.disconnect()
                self._connector = None
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected

    @property
    def authenticated(self):
        return self._connector and self._connector.authenticated

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        pass
    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        pass