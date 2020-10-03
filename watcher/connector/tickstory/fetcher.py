# @date 2020-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.tickstore.com data fetcher

import os
import json
import shutil
import time
import traceback

from datetime import datetime

from common.utils import UTC
from watcher.fetcher import Fetcher

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.fetcher.tickstory')


class TickStoryFetcher(Fetcher):
    """
    TickStory market data fetcher from exports.

    Identity configuration must contains an entry with a "base-path" defined where the raw tickstory export are located.

    Could be used for TickStory data export using 1 file per month :
        - tick :
            - Datetime : UTC
            - Header : None
            - Format : {Timestamp:yyyyMMdd} {Timestamp:HHmmssfff} {BidPrice},{AskPrice},{BidVolume},{AskVolume}
            - Filename : DAT_ASCII_{Symbol}_T{Timestamp:yyyyMM}.csv
        - ohlc :
            - Datetime : UTC
            - Header : None
            - Format : @todo
            - Filename : @todo
    """

    BASE_PATH = "/mnt/storage/Data/market/tickstory.com"

    FILE_NONE = 0
    FILE_MONTHLY = 1
    FILE_YEARLY = 2

    def __init__(self, service):
        super().__init__("tickstory.com", service)

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                self._base_path = identity.get('base-path', TickStoryFetcher.BASE_PATH)

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

    @property
    def connected(self):
        return True

    @property
    def authenticated(self):
        return True

    def has_instrument(self, instrument, fetch_option=""):
        return True

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None, fetch_option=""):
        count = 0

        # get all trades and append them into a file
        try:
            if from_date is None:
                from_date = datetime.now()

            if to_date is None:
                to_date = datetime.now()

            cur_date = from_date
            file_type = self.FILE_NONE

            while cur_date.timestamp() < to_date.timestamp():
                file_type, filename = self.is_yearly_or_monthly(True, market_id, cur_date)

                if file_type != self.FILE_NONE:
                    handle = open(filename, "rt")

                    for line in handle:
                        count += 1
                        # 20180101 170014370,1.200370,1.200870,0
                        # timestamp, bid, ofr, volume, direction
                        yield self.parse_tick(line)

                    handle.close()

                # next month/year
                if not file_type or file_type == TickStoryFetcher.FILE_MONTHLY:
                    # missing file, suppose monthly
                    if cur_date.month < 12:
                        cur_date = cur_date.replace(month=cur_date.month+1)
                    elif cur_date.month == 12:
                        cur_date = cur_date.replace(month=1, year=cur_date.year+1)
                elif file_type == TickStoryFetcher.FILE_YEARLY:
                    cur_date = cur_date.replace(month=1, year=cur_date.year+1)

        except Exception as e:
            logger.error("Fetcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        logger.info("Fetcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, tf, from_date=None, to_date=None, n_last=None, fetch_option=""):
        # only 1m candles
        count = 0

        try:
            if from_date is None:
                from_date = datetime.now()

            if to_date is None:
                to_date = datetime.now()

            cur_date = from_date

            while cur_date.timestamp() < to_date.timestamp():
                file_type, filename = self.is_yearly_or_monthly(False, market_id, cur_date)

                if file_type != TickStoryFetcher.FILE_NONE:
                    handle = open(filename, "rt")

                    for line in handle:
                        count += 1
                        # 20180101 170014;1.200370;1.200870,0;1.200870,0;1.200870,0
                        # timestamp, open, high, low, close
                        yield self.parse_candle(line)

                    handle.close()

                # next month/year
                if file_type == TickStoryFetcher.FILE_MONTHLY:
                    if cur_date.month < 12:
                        cur_date = cur_date.replace(month=cur_date.month+1)
                    elif cur_date.month == 12:
                        cur_date = cur_date.replace(month=1, year=cur_date.year+1)
                elif file_type == TickStoryFetcher.FILE_YEARLY:
                    cur_date = cur_date.replace(month=1, year=cur_date.year+1)

        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, tf, symbol))
            logger.error(repr(e))

        count = 0

        for candle in candles:
            count += 1
            # (timestamp, open bid, high, low, open, close, open ofr, high, low, close, volume)
            yield([candle[0], candle[2], candle[3], candle[1], candle[4], candle[2], candle[3], candle[1], candle[4], candle[5]])

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, tf))

    def is_yearly_or_monthly(self, tick, market_id, cur_date):
        if tick:
            filename = "%s/%s/T/%s/DAT_ASCII_%s_T%s%02i.csv" % (self._base_path, market_id, cur_date.year, market_id, cur_date.year, cur_date.month)
            if os.path.isfile(filename):
                return TickStoryFetcher.FILE_MONTHLY, filename
        else:
            filename = "%s/%s/1M/%s/DAT_ASCII_%s_M%s%02i.csv" % (self._base_path, market_id, cur_date.year, market_id, cur_date.year, cur_date.month)
            if os.path.isfile(filename):
                return TickStoryFetcher.FILE_MONTHLY, filename

            filename = "%s/%s/1M/%s/DAT_ASCII_%s_M%s.csv" % (self._base_path, market_id, cur_date.year, market_id, cur_date.year)
            if os.path.isfile(filename):
                return TickStoryFetcher.FILE_YEARLY, filename

        return TickStoryFetcher.FILE_NONE, ""

    def parse_tick(self, row):
        parts = row.rstrip('\n').split(',')
        ts = int(datetime.strptime(parts[0]+'000', '%Y%m%d %H%M%S%f').replace(tzinfo=UTC()).timestamp() * 1000)

        # no direction but distinct bid/ask prices
        return ts, parts[1], parts[2], parts[3], 0

    def parse_min(self, row):
        parts = row.rstrip('\n').split(';')
        ts = int(datetime.strptime(parts[0], '%Y%m%d %H%M%S').replace(tzinfo=UTC()) * 1000)

        return ts, parts[1], parts[2], parts[3], parts[4], parts[1], parts[2], parts[3], parts[4], parts[5]

    def install_market(self, market_id):
        fetcher_config = self.service.fetcher_config(self._name)
        if fetcher_config:
            markets = fetcher_config.get('markets', {})
            
            if market_id in markets:
                logger.info("Fetcher %s retrieve and install market %s from local data" % (self.name, market_id))
                self.install_market_data(market_id, markets[market_id])
            else:
                logger.error("Fetcher %s cannot retrieve market %s on local data" % (self.name, market_id))
