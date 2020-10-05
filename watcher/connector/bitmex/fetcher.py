# @date 2019-01-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.bitmex.com data fetcher

import re
import json
import time
import traceback

from watcher.fetcher import Fetcher

from connector.bitmex.connector import Connector
from database.database import Database

import logging
logger = logging.getLogger('siis.fetcher.bitmex')
error_logger = logging.getLogger('siis.error.fetcher.bitmex')


class BitMexFetcher(Fetcher):
    """
    BitMex data fetcher.
    """

    TF_MAP = {
        60: '1m',
        300: '5m',
        3600: '1h',
        86400: '1d'
    }

    def __init__(self, service):
        super().__init__("bitmex.com", service)

        self._connector = None

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                self._host = identity.get('host')

                if not self._connector:
                    self._connector = Connector(
                        self.service,
                        identity.get('api-key'),
                        identity.get('api-secret'),
                        [],
                        identity.get('host'))

                if not self._connector.connected:
                    self._connector.connect(use_ws=False)

                    # get list of all availables instruments
                    self._available_instruments = set(self._connector.all_instruments)

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
        trades = []

        try:
            trades = self._connector.get_historical_trades(market_id, from_date, to_date)
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ofr, volume, direction
            yield(trade)

        logger.info("Fetcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        if timeframe not in self.TF_MAP:
            logger.error("Fetcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        # second timeframe to bitmex bin size
        bin_size = self.TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, bin_size, from_date, to_date)
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, bin_size, market_id))
            error_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield((candle[0], candle[1], candle[2], candle[3], candle[4], candle[1], candle[2], candle[3], candle[4], candle[5]))

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, bin_size))
