# @date 2019-01-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.histdata.com data fetcher

import os
import shutil
import traceback
import zipfile

from datetime import datetime

from common.utils import UTC, timeframe_to_str
from watcher.fetcher import Fetcher

import logging
logger = logging.getLogger('siis.fetcher.histdata')


class HistDataFetcher(Fetcher):
    """
    HistData market data fetcher.

    Identity configuration must contains an entry with a "base-path" defined where the raw histdata are located.

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

    BASE_PATH = "/mnt/storage/Data/market/histdata.com"

    FILE_NONE = 0
    FILE_MONTHLY = 1
    FILE_YEARLY = 2

    # BASE_URL = "http://www.histdata.com/download-free-forex-data/?/ascii/"
    # POST Content-Type: application/x-www-form-urlencoded
    # Accept: Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
    # Host: www.histdata.com
    # Origin: http://www.histdata.com
    # Referer: http://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/eurchf/2007/12
    # User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36
    # Form Data: tk=afa5d16664d4d63c7e2f227702f1561b&date=2007&datemonth=200712&platform=ASCII&timeframe=T&fxpair=EURCHF
    # @todo need get the token
    # @todo but some old year are in a single file, recents are per month...

    # CANDLE_1M_ENDPOINT = "1-minute-bar-quotes/%s/%s/%s"  # symbol / year / month
    # TICK_ENDPOINT = "tick-data-quotes/%s/%s/%s"  # symbol / year / month

    def __init__(self, service):
        super().__init__("histdata.com", service)

        self._connector = None
        self._base_path = ""

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                self._base_path = identity.get('base-path', HistDataFetcher.BASE_PATH)

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

            self._connector = None

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        return True  # self._connector is not None and self._connector.connected

    def disconnect(self):
        super().disconnect()

        try:
            if self._connector:
                self._connector.disconnect()
                self._connector = None

        except Exception as e:
            logger.error(repr(e))

    @property
    def authenticated(self) -> bool:
        return True  # self._connector  # and self._connector.authenticated

    def has_instrument(self, instrument, fetch_option="") -> bool:
        # @todo could make a call to check if the market exists
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
                file_type, target = self.is_yearly_or_monthly(True, market_id, cur_date)

                if file_type != self.FILE_NONE:
                    zip_dir = self.unzip_file(target)
                    filename = zip_dir + '/' + self.internal_filename(True, file_type, market_id, cur_date)

                    try:
                        handle = open(filename, "rt")

                        for line in handle:
                            count += 1
                            # 20180101 170014370,1.200370,1.200870,0
                            # timestamp, bid, ask, volume, direction
                            yield self.parse_tick(line)

                        handle.close()
                    finally:
                        self.remove_dir(zip_dir)

                # next month/year
                if not file_type or file_type == HistDataFetcher.FILE_MONTHLY:
                    # missing file, suppose monthly
                    if cur_date.month < 12:
                        cur_date = cur_date.replace(month=cur_date.month+1)
                    elif cur_date.month == 12:
                        cur_date = cur_date.replace(month=1, year=cur_date.year+1)
                elif file_type == HistDataFetcher.FILE_YEARLY:
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
                file_type, target = self.is_yearly_or_monthly(False, market_id, cur_date)

                if file_type != HistDataFetcher.FILE_NONE:
                    zip_dir = self.unzip_file(target)
                    filename = zip_dir + '/' + self.internal_filename(False, file_type, market_id, cur_date)

                    try:
                        handle = open(filename, "rt")

                        for line in handle:
                            count += 1
                            # 20180101 170014;1.200370;1.200870,0;1.200870,0;1.200870,0
                            # timestamp, open, high, low, close
                            yield self.parse_min(line)

                        handle.close()
                    finally:
                        self.remove_dir(zip_dir)

                # next month/year
                if file_type == HistDataFetcher.FILE_MONTHLY:
                    if cur_date.month < 12:
                        cur_date = cur_date.replace(month=cur_date.month+1)
                    elif cur_date.month == 12:
                        cur_date = cur_date.replace(month=1, year=cur_date.year+1)
                elif file_type == HistDataFetcher.FILE_YEARLY:
                    cur_date = cur_date.replace(month=1, year=cur_date.year+1)

        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, tf, market_id))
            logger.error(repr(e))

        count = 0

        # for candle in candles:
        #     count += 1
        #     # (timestamp, open, high, low, open, close, spread, volume)
        #     yield candle[0], candle[2], candle[3], candle[1], candle[4], 0.0, candle[5]

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (
            self.name, market_id, count, timeframe_to_str(tf)))

    def is_yearly_or_monthly(self, tick, market_id, cur_date):
        if tick:
            filename = "%s/%s/T/%s/HISTDATA_COM_ASCII_%s_T%s%02i.zip" % (
                self._base_path, market_id, cur_date.year, market_id, cur_date.year, cur_date.month)
            if os.path.isfile(filename):
                return HistDataFetcher.FILE_MONTHLY, filename
        else:
            filename = "%s/%s/1M/%s/HISTDATA_COM_ASCII_%s_M%s%02i.zip" % (
                self._base_path, market_id, cur_date.year, market_id, cur_date.year, cur_date.month)
            if os.path.isfile(filename):
                return HistDataFetcher.FILE_MONTHLY, filename

            filename = "%s/%s/1M/%s/HISTDATA_COM_ASCII_%s_M%s.zip" % (
                self._base_path, market_id, cur_date.year, market_id, cur_date.year)
            if os.path.isfile(filename):
                return HistDataFetcher.FILE_YEARLY, filename

        return HistDataFetcher.FILE_NONE, ""

    def unzip_file(self, filename, tmpdir="/tmp/"):
        target = tmpdir + 'siis_' + filename.split('/')[-1].rstrip(".zip")

        with zipfile.ZipFile(filename, 'r') as zip_ref:
            zip_ref.extractall(target)

        return target

    def remove_dir(self, path):
        if os.path.isdir(path):
            shutil.rmtree(path)

    def internal_filename(self, tick, file_type, market_id, cur_date):
        if tick:
            if file_type == HistDataFetcher.FILE_MONTHLY:
                return "DAT_ASCII_%s_T_%s%02i.csv" % (market_id, cur_date.year, cur_date.month)
            elif file_type == HistDataFetcher.FILE_YEARLY:
                return "DAT_ASCII_%s_T_%s.csv" % (market_id, cur_date.year)
            else:
                return None
        else:
            if file_type == HistDataFetcher.FILE_MONTHLY:
                return "DAT_ASCII_%s_1M_%s%02i.csv" % (market_id, cur_date.year, cur_date.month)
            elif file_type == HistDataFetcher.FILE_YEARLY:
                return "DAT_ASCII_%s_1M_%s.csv" % (market_id, cur_date.year)
            else:
                return None

    def parse_tick(self, row):
        parts = row.rstrip('\n').split(',')
        ts = int(datetime.strptime(parts[0]+'000', '%Y%m%d %H%M%S%f').replace(tzinfo=UTC()).timestamp() * 1000)

        # no direction detail, but distinct bid/ask prices
        # @todo is there a last price ?
        return ts, parts[1], parts[2], parts[2], parts[3], 0

    def parse_min(self, row):
        parts = row.rstrip('\n').split(';')
        ts = int(datetime.strptime(parts[0], '%Y%m%d %H%M%S').replace(tzinfo=UTC()).timestamp() * 1000)

        return ts, parts[1], parts[2], parts[3], parts[4], 0.0, parts[5]

    def install_market(self, market_id):
        fetcher_config = self.service.fetcher_config(self._name)
        if fetcher_config:
            markets = fetcher_config.get('markets', {})

            if market_id in markets:
                logger.info("Fetcher %s retrieve and install market %s from local data" % (self.name, market_id))
                self.install_market_data(market_id, markets[market_id])
            else:
                logger.error("Fetcher %s cannot retrieve market %s on local data" % (self.name, market_id))
