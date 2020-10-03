# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.kraken.com data fetcher

import json
import time
import traceback

from watcher.fetcher import Fetcher

from connector.kraken.connector import Connector

import logging
logger = logging.getLogger('siis.fetcher.kraken')
error_logger = logging.getLogger('siis.error.fetcher.kraken')


class KrakenFetcher(Fetcher):
    """
    Kraken market data fetcher.
    """

    TF_MAP = {
        60: 1,          # 1m
        300: 5,         # 5m
        900: 15,        # 15m
        1800: 30,       # 30m
        3600: 60,       # 1h
        14400: 240,     # 4h
        86400.0: 1440,  # 1d
        # 604800: 10080,  # 1w (not allowed because starts on thuesday)
        # 1296000: 21600  # 15d
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
                        [],
                        identity.get('host'))

                if not self._connector.connected:
                    self._connector.connect(use_ws=False)

                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                instruments = self._connector.instruments()

                for market_id, instrument in instruments.items():
                    self._available_instruments.add(market_id)

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
        # get all trades and append them into a file
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

        # second timeframe to kraken interval
        interval = self.TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, interval, from_date, to_date)
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, interval, market_id))
            error_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield((candle[0], candle[1], candle[2], candle[3], candle[4], candle[1], candle[2], candle[3], candle[4], candle[5]))

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, interval))
