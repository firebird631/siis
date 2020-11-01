# @date 2019-01-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Candle storage/reading per market

import os
import json
import time
import threading
import traceback
import collections

from datetime import datetime, timedelta

from common.signal import Signal
from instrument.instrument import Candle

from common.utils import UTC

import logging
logger = logging.getLogger('siis.database.ohlcstorage')


class OhlcStorage(object):
    """
    Store per market sqlite DB.
    @note Generic SQL.

    Delete if timestamp :
        - timeframe for 45m to 2h older than 90 days
        - 10m to 30m older than 21 days
        - 1m to 5m olders than 8 days
    """

    DEFAULT_FLUSH_DELAY = 5*60  # every 5 mins
    MAX_PENDING_LEN = 500       # or 500 inserts

    # must be from lesser timeframe to higher
    CLEANERS = (
        (5*60, 8*24*60*60),      # until 5m
        (30*60, 21*24*60*60),    # until 30m
        (2*60*60, 90*24*60*60))  # until 2h

    CLEANUP_DELAY = 4*60*60      # each 4 hours

    def __init__(self, db, broker_id, market_id):
        self._db = db

        self._broker_id = broker_id
        self._market_id = market_id

        self._ohlcs = []
        self._mutex = threading.RLock()

        self._queries = []
        self._last_write = 0

    def set_thread_id(self, thread_id):
        self._thread_id = thread_id

    @property
    def thread_id(self):
        return self._thread_id

    def has_data(self):
        return len(self._ohlcs) > 0

    def has_query(self):
        return len(self._queries) > 0

    def store(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            integer timeframe (time unit in seconds)
            str open, high, low, close (>= 0)
            str spread (>= 0)
            str volume (>= 0)
        """
        if data[3] < 60:
            # never store ohlcs lesser than 1m
            return

        with self._mutex:
            if isinstance(data, list):
                self._ohlcs.extend(data)
            else:
                self._ohlcs.append(data)

    def flush(self):
        with self._mutex:
            ohlcs = self._ohlcs = []

        try:
            cursor = self._db.cursor()

            for ohlc in ohlcs:
                cursor.execute("""
                    INSERT INTO ohlc(timestamp, timeframe, open, high, low, close, spread, volume)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?)""", ohlc)

            self._db.commit()

        except Exception as e:
            logger.error(repr(e))

            # retry next time
            with self._mutex:
                self._ohlcs = ohlcs + self._ohlcs

    def clean(self):
        now = time.time()

        try:
            cursor = self._db.cursor()

            for timeframe, timestamp in OhlcStorage.CLEANERS:
                ts = int(now - timestamp) * 1000
                cursor.execute("DELETE FROM ohlc WHERE timeframe <= %i AND timestamp < %i" % (timeframe, ts))

            self._db.commit()
        except Exception as e:
            logger.error(repr(e))

    # def async_query(self, service, timeframe, from_date, to_date, limit):
    #     with self._mutex:
    #         self._queries.append((service, timeframe, from_date, to_date, limit))

    # def query(self, timeframe, from_date, to_date, limit_or_last_n, auto_close=True):
    #     """
    #     Query ohlcs for a timeframe.
    #     @param from_date Optional
    #     @param to_date Optional
    #     @param limit_or_last_n Optional
    #     """
    #     cursor = self._db.cursor()

    #     try:
    #         if from_date and to_date:
    #             from_ts = int(from_date.timestamp() * 1000.0)
    #             to_ts = int(to_date.timestamp() * 1000.0)
    #             self.query_from_to(cursor, timeframe, from_date, to_date)
    #         elif from_date:
    #             from_ts = int(from_date.timestamp() * 1000.0)
    #             self.query_from_limit(cursor, timeframe, from_date, limit_or_last_n)
    #         elif to_date:
    #             to_ts = int(to_date.timestamp() * 1000.0)
    #             self.query_from_limit(cursor, timeframe, to_date)
    #         elif limit:
    #             self.query_last(cursor, timeframe, limit_or_last_n)
    #         else:
    #             self.query_all(cursor, timeframe)
    #     except Exception as e:
    #         logger.error(repr(e))

    #         self.close()
    #         return []

    #     rows = cursor.fetchall()
    #     ohlcs = []

    #     for row in rows:
    #         timestamp = float(row[0]) * 0.001  # to float second timestamp
    #         ohlc = Candle(timestamp, timeframe)

    #         ohlc.set_ohlc(float(row[1]), float(row[2]), float(row[3]), float(row[4]))

    #         ohlc.set_spread(float(row[5]))
    #         ohlc.set_volume(float(row[6]))

    #         ohlcs.append(ohlc)

    #     if auto_close:
    #         self.close()

    #     return data

    # def query_all(self, cursor, timeframe):
    #     cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
    #                         WHERE timeframe = %s ORDER BY timestamp ASC""" % (timeframe,))

    # def query_last(self, cursor, timeframe, limit):
    #     cursor.execute("""SELECT COUNT(*) FROM ohlc WHERE timeframe = %s""" % (timeframe,))
    #     count = int(cursor.fetchone()[0])
    #     offset = max(0, count - limit)

    #     # LIMIT should not be necessary then
    #     cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
    #                     WHERE timeframe = %s ORDER BY timestamp ASC LIMIT %i OFFSET %i""" % (timeframe, limit, offset))

    # def query_from_to(self, cursor, timeframe, from_ts, to_ts):
    #     cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
    #                     WHERE timeframe = %s AND timestamp >= %i AND timestamp <= %i ORDER BY timestamp ASC""" % (
    #                         timeframe, from_ts, to_ts))

    # def query_from_limit(self, cursor, timeframe, from_ts, limit):
    #     cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
    #                     WHERE timeframe = %s AND timestamp >= %i ORDER BY timestamp ASC LIMIT %i""" % (
    #                         timeframe, from_ts, limit))

    # def query_to(self, cursor, timeframe, to_ts):
    #     cursor.execute("""SELECT timestamp, open, high, low, close, spread volume FROM ohlc
    #                     WHERE timeframe = %s AND timestamp <= %i ORDER BY timestamp ASC""" % (
    #                         timeframe, to_ts))

    # def process_async_queries(self):
    #     with self._mutex:
    #         queries = self._queries
    #         self._queries.clear()

    #     failed = []

    #     for query in queries:
    #         try:
    #             ohlcs = self.query(query[1], query[2], query[3], query[4], False)

    #             # and signal notification
    #             service.notify(Signal.SIGNAL_CANDLE_DATA_BULK, self._broker_id, (self._market_id, query[1], ohlcs))
    #         except Exception as e:
    #             logger.error(repr(e))
    #             failed.append(query)

    #     # retry the next time
    #     if failed:
    #         with self._mutex:
    #             self._queries = failed + self._queries

    def process(self):
        """
        Process the writing, cleaning and pending reading queries.
        Writing and cleaning are processed at a default rate.
        Queries are executed as possible.
        """
        do_flush = False

        if ((time.time() - self._last_write) >= self.DEFAULT_FLUSH_DELAY) or (len(self._ohlcs) > self.MAX_PENDING_LEN):
            do_flush = True

        if do_flush or self._queries:
            self.open()

            if do_flush:
                self.flush()

                if self._db._autocleanup:
                    self.clean()

                self._last_write = time.time()

            # if self._queries:
            #     self.process_async_queries()
            
            self.close()


class OhlcStreamer(object):
    """
    Streamer that read ohlc from a start to end date.
    @note Generic SQL.
    """

    def __init__(self, db, broker_id, market_id, timeframe, from_date, to_date=None, buffer_size=1000):
        """
        @param from_date datetime Object
        @param to_date datetime Object
        """

        self._db = db

        self._broker_id = broker_id
        self._market_id = market_id

        self._timeframe = timeframe

        self._from_date = from_date
        self._to_date = to_date

        self._curr_date = from_date

        self._buffer = collections.deque()
        self._buffer_size = buffer_size

    def finished(self):
        return self._curr_date >= self._to_date and not self._buffer

    def next(self, timestamp):
        results = []

        while 1:
            if not self._buffer:
                self.__bufferize()

            while self._buffer and self._buffer[0].timestamp <= timestamp:
                results.append(self._buffer.popleft())

            if self.finished() or (self._buffer and self._buffer[0].timestamp > timestamp):
                break

        return results

    def __bufferize(self):
        results = self.query(self._timeframe, self._curr_date, None, self._buffer_size, False)
        if results:
            self._buffer.extend(results)
            self._curr_date = datetime.fromtimestamp(results[-1].timestamp).replace(tzinfo=UTC())
        else:
            self._curr_date = self._curr_date + timedelta(seconds=self._timeframe)

    def query(self, timeframe, from_date, to_date, limit_or_last_n, auto_close=True):
        """
        Query ohlcs for a timeframe.
        @param from_date Optional
        @param to_date Optional
        @param limit_or_last_n Optional
        """
        cursor = self._db.cursor()

        try:
            if from_date and to_date:
                from_ts = int(from_date.timestamp() * 1000.0)
                to_ts = int(to_date.timestamp() * 1000.0)
                self.query_from_to(cursor, timeframe, from_ts, to_ts)
            elif from_date:
                from_ts = int(from_date.timestamp() * 1000.0)
                self.query_from_limit(cursor, timeframe, from_ts, limit_or_last_n)
            elif to_date:
                to_ts = int(to_date.timestamp() * 1000.0)
                self.query_from_limit(cursor, timeframe, to_ts)
            elif limit:
                self.query_last(cursor, timeframe, limit_or_last_n)
            else:
                self.query_all(cursor, timeframe)
        except Exception as e:
            logger.error(repr(e))
            return []

        rows = cursor.fetchall()
        ohlcs = []

        for row in rows:
            timestamp = float(row[0]) * 0.001  # to float second timestamp
            ohlc = Candle(timestamp, timeframe)

            ohlc.set_ohlc(float(row[1]), float(row[2]), float(row[3]), float(row[4]))

            ohlc.set_spread(float(row[5]))
            ohlc.set_volume(float(row[6]))

            ohlcs.append(ohlc)

        return ohlcs

    def query_all(self, cursor, timeframe):
        cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
                            WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s ORDER BY timestamp ASC""" % (
                                self._broker_id, self._market_id, timeframe))

    def query_last(self, cursor, timeframe, limit):
        cursor.execute("""SELECT COUNT(*) FROM ohlc WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s""" % (
            self._broker_id, self._market_id, timeframe))

        count = int(cursor.fetchone()[0])
        offset = max(0, count - limit)

        # LIMIT should not be necessary then
        cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
                        WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s ORDER BY timestamp ASC LIMIT %i OFFSET %i""" % (
                            self._broker_id, self._market_id, timeframe, limit, offset))

    def query_from_to(self, cursor, timeframe, from_ts, to_ts):
        cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
                        WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp >= %i AND timestamp <= %i ORDER BY timestamp ASC""" % (
                            self._broker_id, self._market_id, timeframe, from_ts, to_ts))

    def query_from_limit(self, cursor, timeframe, from_ts, limit):
        cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
                        WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp >= %i ORDER BY timestamp ASC LIMIT %i""" % (
                            self._broker_id, self._market_id, timeframe, from_ts, limit))

    def query_to(self, cursor, timeframe, to_ts):
        cursor.execute("""SELECT timestamp, open, high, low, close, spread, volume FROM ohlc
                        WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp <= %i ORDER BY timestamp ASC""" % (
                            self._broker_id, self._market_id, timeframe, to_ts))
