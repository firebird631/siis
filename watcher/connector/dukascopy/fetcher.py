# @date 2023-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# dukascopy.com watcher implementation
import copy
import io
import lzma
import math

import requests
import struct
import time
import traceback

from datetime import datetime, timedelta
from common.utils import UTC, truncate
from watcher.fetcher import Fetcher
from instrument.instrument import Instrument

from .symbols import DUKASCOPY_SYMBOLS_DECIMALS

from __init__ import APP_VERSION, APP_SHORT_NAME

import logging
logger = logging.getLogger('siis.fetcher.dukascopy')
error_logger = logging.getLogger('siis.error.fetcher.dukascopy')
traceback_logger = logging.getLogger('siis.traceback.fetcher.dukascopy')


class DukascopyFetcher(Fetcher):
    """
    Dukascopy history and market data fetcher.

    @note month code is 0 based
    @note url example http://datafeed.dukascopy.com/datafeed/USATECHIDXUSD/2023/07/18/16h_ticks.bi5
    """

    PROTOCOL = "http:/"
    BASE_URL = "datafeed.dukascopy.com/datafeed"

    def __init__(self, service):
        super().__init__("dukascopy.com", service)

        self._host = "dukascopy.com"
        self._connector = None
        self._session = None

    def connect(self):
        super().connect()

        try:
            # identity = self.service.identity(self._name)
            self._available_instruments = set(DUKASCOPY_SYMBOLS_DECIMALS.keys())

            if self._session is None:
                self._session = requests.Session()

                self._session.headers.update({'user-agent': "%s-%s" % (
                    APP_SHORT_NAME, '.'.join([str(x) for x in APP_VERSION]))})
                self._session.headers.update({'content-type': 'application/text'})

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

            self._connector = None

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        # return self._connector is not None and self._connector.connected
        return self._session

    def disconnect(self):
        super().disconnect()

        try:
            if self._session:
                self._session = None

            if self._connector:
                self._connector.disconnect()
                self._connector = None

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def has_instrument(self, instrument, fetch_option="") -> bool:
        if instrument in DUKASCOPY_SYMBOLS_DECIMALS:
            return True

        return False

    @staticmethod
    def read_bi5(source: bytearray, fmt: str):
        chunk_size = struct.calcsize(fmt)
        data = []
        with lzma.LZMAFile(io.BytesIO(source)) as f:
            while True:
                chunk = f.read(chunk_size)
                if chunk:
                    data.append(struct.unpack(fmt, chunk))
                else:
                    break

        return data

    @staticmethod
    def fmt_price(price: int, decimal: float, digits: int):
        return truncate(price * decimal, digits)

    def _get_tick_file(self, market_id: str, from_date: datetime):
        api_url = '/'.join((DukascopyFetcher.PROTOCOL, DukascopyFetcher.BASE_URL, market_id,
                            '{:0>4}'.format(from_date.year), '{:0>2}'.format(from_date.month-1), '{:0>2}'.format(from_date.day),
                            '{:0>2}h'.format(from_date.hour) + "_ticks.bi5"))

        # logger.info(api_url)

        try:
            response = self._session.get(api_url)
        except requests.exceptions.HTTPError as e:
            logger.error(str(e))
            return None

        if not response or not response.ok:
            logger.error("HTTP status code %s from %s" % (response.status_code, api_url))
            return None

        decimal = DUKASCOPY_SYMBOLS_DECIMALS.get(market_id, 1.0)
        digits = int(-math.log10(decimal))

        base_timestamp = int(from_date.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)

        if not response.content:
            return []

        try:
            data = DukascopyFetcher.read_bi5(response.content, '>3I2f')
        except Exception as e:
            logger.error("Fetcher %s cannot parse ticks on market %s from %s" % (self.name, market_id, api_url))
            traceback_logger.error(traceback.format_exc())
            return []

        trades = []

        # timestamp, bid, ask, last, volume, direction
        for t in data:
            bid = DukascopyFetcher.fmt_price(t[1], decimal, digits)
            ask = DukascopyFetcher.fmt_price(t[2], decimal, digits)
            last = (bid + ask) * 0.5

            trades.append((
                t[0] + base_timestamp,
                bid,
                ask,
                last,
                t[3] + t[4],  # bid+ask volume
                0  # no have direction
            ))
            # print(trades[-1])

        if trades:
            print(trades[-1])

        return trades

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None, fetch_option=""):
        trades = []
        cur_date = from_date
        last_ts = int(to_date.timestamp() * 1000) if to_date else 0
        from_ts = int(from_date.timestamp() * 1000) if from_date else 0

        count = 0

        while cur_date <= to_date:
            try:
                trades = self._get_tick_file(market_id, cur_date)
            except Exception as e:
                logger.error("Fetcher %s cannot retrieve ticks on market %s" % (self.name, market_id))
                traceback_logger.error(traceback.format_exc())

            if trades is not None and type(trades) is list:
                for trade in trades:
                    # exclusive from
                    if from_ts > 0 and trade[0] <= from_ts:
                        continue

                    # inclusive to
                    if 0 < last_ts < trade[0]:
                        break
                    count += 1
                    # timestamp, bid, ask, last, volume, direction
                    yield trade

            cur_date += timedelta(hours=1)

        logger.info("Fetcher %s has retrieved on market %s %s ticks" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None, fetch_option=""):
        # @todo
        return []
