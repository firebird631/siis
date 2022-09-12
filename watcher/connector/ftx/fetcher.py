# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# www.ftx.com data fetcher

import traceback

from datetime import datetime

from common.utils import timeframe_to_str, UTC
from watcher.fetcher import Fetcher

from connector.ftx.connector import Connector

import logging

logger = logging.getLogger('siis.fetcher.ftx')
error_logger = logging.getLogger('siis.error.fetcher.ftx')


class FTXFetcher(Fetcher):
    """
    FTX market data fetcher.
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
        super().__init__("ftx.com", service)

        self._connector = None

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                if not self._connector:
                    self._connector = Connector(
                        self.service,
                        identity.get('account-id', ""),
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

                instruments = self._connector.client.get_markets()

                for instrument in instruments:
                    self._available_instruments.add(instrument['name'])

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
    def connected(self) -> bool:
        return self._connector is not None and self._connector.connected

    @property
    def authenticated(self) -> bool:
        return self._connector and self._connector.authenticated

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        trades = []

        try:
            trades = self._connector.client.aggregate_trade_iter(market_id, start_str=from_date.timestamp(),
                                                                 end_str=to_date.timestamp())
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            t = datetime.strptime(trade['time'], '%Y-%m-%dT%H:%M:%S.%f+00:00').replace(tzinfo=UTC()).timestamp()
            yield t, trade['price'], trade['price'], trade['price'], trade['size'], -1 if trade['side'] == "sell" else 1

        logger.info("Fetcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        TF_LIST = [15, 60, 300, 900, 3600, 14400, 86400, 259200, 604800, 2592000]

        if timeframe not in TF_LIST:
            logger.error("Fetcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        tf = timeframe

        try:
            candles = self._connector.client.get_historical_prices(market_id, tf,
                                                                   from_date.timestamp(), to_date.timestamp())
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s (%s)" % (self.name, tf, market_id, str(e)))

        count = 0

        for candle in candles:
            count += 1
            # (timestamp, open, high, low, close, spread, volume)
            yield int(candle['time']), candle['open'], candle['high'], candle['low'], candle['close'], 0.0, \
                  candle['volume']
