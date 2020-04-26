# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# ig.com watcher implementation

import urllib
import json
import time
import pytz
import traceback

from datetime import datetime, timedelta
from common.utils import UTC
from watcher.fetcher import Fetcher
from instrument.instrument import Instrument

from terminal.terminal import Terminal
from connector.ig.connector import IGConnector

import logging
logger = logging.getLogger('siis.fetcher.ig')
error_logger = logging.getLogger('siis.error.fetcher.ig')


class IGFetcher(Fetcher):
    """
    IG watcher data fetcher.
    @note Initial limitation to 10000 candles per week.
    @warning UTC timestamp are erroneous in D, W and M because there is an issue with DST changes.
    Then have to fix that cases.
    """

    def __init__(self, service):
        super().__init__("ig.com", service)

        self._host = "ig.com"
        self._connector = None
        self._account_id = ""
        self._tzname = None

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

                self._tzname = identity.get('tzname')
                self._connector.connect(encryption=identity.get('encryption', False))

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
        return []

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

        # get local timezone, assume its the same of the account, or overrided by account detail
        tzname = self._tzname or time.tzname[0]
        pst = pytz.timezone(tzname)

        for price in prices:
            dt = datetime.strptime(price['snapshotTimeUTC'], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC())
            # ldt = datetime.strptime(price['snapshotTime'], '%Y/%m/%d %H:%M:%S')

            # timezone + DST aware conversion
            # print("<", dt, ldt)
            # dt = dt + pst.localize(ldt).dst() + pst.localize(ldt).utcoffset()

            # fix for D,W,M snapshotTimeUTC, probaby because of the DST (then might be +1 or -1 hour)
            if timeframe in (Instrument.TF_1D, Instrument.TF_1W, Instrument.TF_1M):
                if dt.hour == 23:
                    # is 23:00 on the previous day, add 1h
                    dt = dt + timedelta(hours=1)
                elif dt.hour == 1:
                    # is 01:00 on the same day, sub 1h
                    dt = dt - timedelta(hours=1)

            elif timeframe == Instrument.TF_4H:
                if dt.hour in (3, 7, 11, 15, 19, 23):
                    dt = dt + timedelta(hours=1)
                elif dt.hour in (1, 5, 9, 13, 17, 21):
                     dt = dt - timedelta(hours=1)

            # print(">", dt, ldt)
            timestamp = dt.timestamp()

            if price.get('highPrice')['bid'] is None and price.get('highPrice')['ask'] is None:
                # ignore empty candles
                continue

            # yield (timestamp, high bid, low, open, close, high ofr, low, open, close, volume)
            yield([int(timestamp * 1000),
                str(price.get('openPrice')['bid'] or price.get('openPrice')['ask']),
                str(price.get('highPrice')['bid'] or price.get('highPrice')['ask']),
                str(price.get('lowPrice')['bid'] or price.get('lowPrice')['ask']),
                str(price.get('closePrice')['bid'] or price.get('closePrice')['ask']),
                str(price.get('openPrice')['ask'] or price.get('openPrice')['bid']),
                str(price.get('highPrice')['ask'] or price.get('highPrice')['bid']),
                str(price.get('lowPrice')['ask'] or price.get('lowPrice')['bid']),
                str(price.get('closePrice')['ask'] or price.get('closePrice')['bid']),
                price.get('lastTradedVolume', '0')])
