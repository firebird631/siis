# @date 2020-10-29
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Quote streaming per market

import os
import time
import threading
import pathlib
import struct
import collections

import numpy as np

from datetime import datetime
from common.utils import timeframe_to_str, UTC
from instrument.instrument import Candle

import logging
logger = logging.getLogger('siis.database.quotestorage')


class QuoteStorage(object):
    """
    Default implementation store in a single file but further one file per month.
    File format is a tab separated file with no header and :
    timestamp(int ms since epoch) open(str) high(str) low(str) close(str) spread(str) volume(str)

    Price and volume should be formatted with the asset precision if possible but scientific notation
    is tolerate.
    """

    FLUSH_DELAY = 60.0

    def __init__(self, markets_path, broker_id, market_id, timeframe, text=True, binary=True):
        self._markets_path = markets_path
        self._mutex = threading.RLock()

        self._broker_id = broker_id
        self._market_id = market_id

        self._timeframe = timeframe
        self._timeframe_str = timeframe_to_str(timeframe)

        self._last_save = 0

        self._quotes = []
        self._curr_date = None

        self._text_file = None
        self._binary_file = None

        self._text = text
        self._binary = binary

        self._struct = struct.Struct('<ddddddd')

    def store(self, data):
        """
        @param data Candle
        """
        with self._mutex:
            if isinstance(data, list):
                self._quotes.extend(data)
            else:
                self._quotes.append(data)        

    def has_data(self):
        with self._mutex:
            return len(self._quotes) > 0

    def open(self, date_utc):
        if self._text and not self._text_file:
            try:
                broker_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id,
                                           self._timeframe_str)  # use broker name as directory
                if not broker_path.exists():
                    broker_path.mkdir(parents=True)

                self._curr_date = date_utc

                # append to file, filename according to the month (UTC) of the timestamp
                filename = "%s%s_%s" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
                self._text_file = open(str(broker_path) + '/' + filename, 'at')  # user market as file name
            except Exception as e:
                logger.error(repr(e))

        if self._binary and not self._binary_file:
            try:
                broker_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id,
                                           self._timeframe_str)  # use broker name as directory
                if not broker_path.exists():
                    broker_path.mkdir(parents=True)

                self._curr_date = date_utc

                # append to file, filename according to the month (UTC) of the timestamp
                filename = "%s%s_%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
                self._binary_file = open(str(broker_path) + '/' + filename, 'ab')  # user market as file name
            except Exception as e:
                logger.error(repr(e))

    def close(self):
        if self._text_file:
            self._text_file.close()
            self._text_file = None

        if self._binary_file:
            self._binary_file.close()
            self._binary_file = None            

    def can_flush(self):
        # save only once per minute
        return (time.time() - self._last_save) >= QuoteStorage.FLUSH_DELAY

    def flush(self, close_at_end=True):
        with self._mutex:
            quotes = self._quotes
            self._quotes = []

        if not quotes:
            return

        n = 0
        try:
            for d in quotes:
                # while v:
                #     # process next
                #     d = quotes.pop(0)  # too slow when millions of elements

                date_utc = datetime.utcfromtimestamp(d[2] * 0.001)  # .replace(tzinfo=UTC()) not necessary because not directly compared

                if self._curr_date and (self._curr_date.year != date_utc.year or self._curr_date.month != date_utc.month):
                    self.close()

                self.open(date_utc)  # if necessary

                if self._text_file: 
                    # convert to a tabular row          
                    content = "%i\t%s\t%s\t%s\t%s\t%s\t%s\n" % (d.timestamp, d.open, d.high, d.low, d.close,
                                                                d.spread, d.volume)  # t o h l c s v
                    self._text_file.write(content)

                if self._binary_file:
                    # convert to a struct
                    f = (float(d[2]) * 0.001, float(d[3]), float(d[4]), float(d[5]), float(d[6]),
                         float(d[7]), float(d[8]))  # t o h l c s v (t in second)
                    # s = struct.pack('<ddddddd', *f)
                    s = self._struct.pack(*f)

                    self._binary_file.write(s)

                n += 1
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            with self._mutex:
                # self._quotes = quotes + self._quotes
                self._quotes = quotes[n:] + self._quotes

        self._last_save = time.time()

        if close_at_end:
            self.close()  # avoid too many handles


class QuoteStreamer(object):
    """
    Streamer that read data from an initial position.
    This models is inspired from the quote streamer.
    """

    QUOTE_SIZE = 7*8  # 56bytes

    def __init__(self, markets_path, broker_id, market_id, timeframe, from_date, to_date=None,
                 buffer_size=1000, binary=True):
        """
        @param from_date datetime Object
        @param to_date datetime Object
        """
        self._markets_path = markets_path

        self._broker_id = broker_id
        self._market_id = market_id

        self._timeframe = timeframe
        self._timeframe_str = timeframe_to_str(timeframe)

        self._from_date = from_date
        self._to_date = to_date

        self._curr_date = from_date

        self._buffer = collections.deque()
        self._buffer_size = buffer_size
        self._file = None

        self._binary = binary  # use binary format
        self._is_binary = False

        self._struct = struct.Struct('ddddddd')
        self._format = np.dtype([('t', 'float64'), ('o', 'float64'), ('h', 'float64'), ('l', 'float64'),
                                 ('c', 'float64'), ('s', 'float64'), ('v', 'float64')])

    @property
    def from_date(self):
        return self._from_date

    @property
    def to_date(self):
        return self._to_date

    def open(self):
        if self._file:
            return

        data_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, self._timeframe_str)
        if not data_path.exists():
            return

        # try first with binary file
        if self._binary:
            # with .dat extension
            filename = "%s%s_%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
            pathname = '/'.join((str(data_path), filename))

            if os.path.isfile(pathname):
                self._file = open(pathname, "rb")
                self._is_binary = True

                st = os.stat(pathname)
                file_size = st.st_size

                # directly seek to initial position to avoid useless parsing
                timestamp = self._curr_date.timestamp()
                prev_timestamp = 0
                pos = 0
                prev_pos = -1
                left = 0
                right = file_size
                eof = file_size-1 if file_size > 0 else 0

                while 1:
                    data = self._file.read(QuoteStreamer.QUOTE_SIZE)

                    if not data:
                        break

                    quote = self._struct.unpack(data)

                    # if right - left <= QuoteStreamer.QUOTE_SIZE or prev_pos == pos:
                    if right - left < QuoteStreamer.QUOTE_SIZE or prev_pos == pos:
                        # found our starting offset or the first entry is later but should be in this file
                        self._file.seek(-QuoteStreamer.QUOTE_SIZE, 1)
                        break

                    if quote[0] < timestamp:
                        # move forward
                        left = pos + QuoteStreamer.QUOTE_SIZE
                        prev_timestamp = timestamp

                    elif quote[0] > timestamp:
                        # move backward
                        right = pos - QuoteStreamer.QUOTE_SIZE

                    elif self._file.tell() >= eof:
                        break

                    prev_pos = pos
                    # pos = max(0, left + ((right - left) // QuoteStreamer.QUOTE_SIZE) // 2 * QuoteStreamer.QUOTE_SIZE)
                    pos = max(0, left + ((right - left) // QuoteStreamer.QUOTE_SIZE) // 2 * QuoteStreamer.QUOTE_SIZE)
                    self._file.seek(pos, 0)

        # if not binary asked or binary not found try with text file
        if not self._file:
            # no extension
            filename = "%s%s_%s" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
            pathname = '/'.join((str(data_path), filename))

            if os.path.isfile(pathname):
                self._file = open(pathname, "rt")
                self._is_binary = False

                # @todo seeking

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    def finished(self):
        """
        No more data into the buffer and "to date" reached.
        """
        return (self._curr_date >= self._to_date) and not self._buffer

    def next(self, timestamp):
        results = []

        while 1:
            if not self._buffer:  # len(self._buffer) < self._buffer_size:
                self.__bufferize()

            # # until timestamp
            # n = 0
            # for quote in self._buffer:
            #   if quote[0] <= timestamp:
            #       n += 1
            #   else:
            #       break

            # if n > 0:
            #   # more results
            #   results.extend(self._buffer[:n])

            #   # remaining buffer
            #   self._buffer = self._buffer[n:]

            # until timestamp (pop version is 30% speedup)
            while self._buffer and self._buffer[0][0] <= timestamp:
                # results.append(self._buffer.pop(0))
                elt = self._buffer.popleft()

                quote = Candle(elt[0], self._timeframe)
                quote.set_ohlc_s_v(elt[1], elt[2], elt[3], elt[4], elt[5], elt[6])

                results.append(quote)

            if self.finished() or (self._buffer and self._buffer[0][0] > timestamp):
                break

        return results

    def next_to(self, timestamp, dest):
        n = 0

        while 1:
            if not self._buffer:  # len(self._buffer) < self._buffer_size:
                self.__bufferize()

            # until timestamp
            while self._buffer and self._buffer[0][0] <= timestamp:
                elt = self._buffer.popleft()

                quote = Candle(elt[0], self._timeframe)
                quote.set_ohlc_s_v(elt[1], elt[2], elt[3], elt[4], elt[5], elt[6])

                dest.append(quote)
                n += 1

            if self.finished() or (self._buffer and self._buffer[0][0] > timestamp):
                break

        return n

    def __bufferize(self):
        if self._curr_date < self._to_date:
            if not self._file:
                self.open()

            file_end = False

            if self._file:
                if self._is_binary:
                    arr = self._file.read(QuoteStreamer.QUOTE_SIZE*self._buffer_size)
                    data = self._struct.iter_unpack(arr)

                    if len(arr) < self._buffer_size:
                        file_end = True

                    # speedup using numpy fromfile but its a one shot loads
                    # data = np.fromfile(self._file, dtype=self._format)
                    # file_end = True

                    self._buffer.extend(data)

                    # not really necessary, its slow
                    # no longer necessary because open() at the best initial position
                    # for d in data:
                    #     if d[0] >= self._from_date.timestamp():
                    #         self._buffer.append(d)
                else:
                    # text
                    for n in range(0, self._buffer_size):
                        row = self._file.readline()

                        if not row:
                            file_end = True
                            break

                        ts, o, h, l, c, s, vol = row.rstrip('\n').split('\t')

                        ts = float(ts) * 0.001
                        if ts < self._from_date.timestamp():
                            # ignore older than initial date
                            continue

                        self._buffer.append((ts, float(o), float(h), float(l), float(c), float(s), float(vol)))
            else:
                file_end = True

            if file_end:
                self.close()

                # next month/year
                if self._curr_date.month == 12:
                    self._curr_date = datetime(year=self._curr_date.year+1, month=1, day=1, tzinfo=UTC())
                else:
                    self._curr_date = datetime(year=self._curr_date.year, month=self._curr_date.month+1,
                                               day=1, tzinfo=UTC())


class LastQuoteFinder(object):
    """
    Last quote find helper.
    """

    QUOTE_SIZE = 7*8  # 56bytes

    def __init__(self, markets_path, broker_id, market_id, timeframe, buffer_size=1000, binary=True):
        self._markets_path = markets_path

        self._broker_id = broker_id
        self._market_id = market_id

        self._timeframe = timeframe
        self._timeframe_str = timeframe_to_str(timeframe)

        self._curr_date = datetime.now()

        self._buffer_size = buffer_size
        self._binary = binary  # use binary format

        self._struct = struct.Struct('ddddddd')
        self._format = np.dtype([('t', 'float64'), ('o', 'float64'), ('h', 'float64'), ('l', 'float64'),
                                 ('c', 'float64'), ('s', 'float64'), ('v', 'float64')])

    def open(self):
        data_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, self._timeframe_str)
        if not data_path.exists():
            return None

        # try first with binary file
        if self._binary:
            # with .dat extension
            filename = "%s%s_%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
            pathname = '/'.join((str(data_path), filename))

            quote = None

            if os.path.isfile(pathname):
                bfile = open(pathname, "rb")

                # directly seek to the last quote entry
                try:
                    bfile.seek(-QuoteStreamer.QUOTE_SIZE, 2)
                    arr = bfile.read(QuoteStreamer.QUOTE_SIZE)

                    elt = self._struct.unpack(arr)

                    quote = Candle(elt[0], self._timeframe)
                    quote.set_ohlc_s_v(elt[1], elt[2], elt[3], elt[4], elt[5], elt[6])
                except:
                    pass

                bfile.close()

            return quote

        # if not binary asked or binary not found try with text file
        else:
            # no extension
            filename = "%s%s_%s" % (self._curr_date.strftime('%Y%m'), self._market_id, self._timeframe_str)
            pathname = '/'.join((str(data_path), filename))

            quote = None

            if os.path.isfile(pathname):
                tfile = open(pathname, "rb")

                # directly seek to the last quote entry
                tfile.seek(-self._buffer_size, 2)

                data = tfile.read(self._buffer_size)
                content = data.decode('utf-8').rstrip('\n')
                pos = content.rfind('\n')

                if pos >= 0:
                    row = content[pos+1:]
                    ts, o, h, l, c, s, vol = row.rstrip('\n').split('\t')

                    # timestamp in seconds
                    quote = Candle(float(ts) * 0.001, self._timeframe)
                    quote.set_ohlc_s_v(float(o), float(h), float(l), float(c), float(s), float(vol))

                tfile.close()

            return quote

        return None

    def last(self):
        quote = None

        while 1:
            quote = self.open()

            if quote:
                break

            # prev month/year
            if self._curr_date.month == 1:
                if self._curr_date.year < 2000:
                    return None

                self._curr_date = self._curr_date.replace(year=self._curr_date.year-1, month=12, day=1, hour=0,
                                                          minute=0, second=0, microsecond=0)
            else:
                self._curr_date = self._curr_date.replace(month=self._curr_date.month-1, day=1, hour=0,
                                                          minute=0, second=0, microsecond=0)

        return quote

    # def __bufferize(self):
    #     if self._curr_date < self._to_date:
    #         if not self._file:
    #             self.open()
    #
    #         file_end = False
    #
    #         if self._file:
    #             if self._is_binary:
    #                 arr = self._file.read(LastQuoteFinder.QUOTE_SIZE*self._buffer_size)
    #                 data = self._struct.iter_unpack(arr)
    #
    #                 if len(arr) < self._buffer_size:
    #                    file_end = True
    #
    #                 # speedup using numpy fromfile but its a one shot loads
    #                 # data = np.fromfile(self._file, dtype=self._format)
    #                 # file_end = True
    #
    #                 self._buffer.extend(data)
    #
    #                 # not really necessary, its slow
    #                 # no longer necessary because open() at the best initial position
    #                 # for d in data:
    #                 #     if d[0] >= self._from_date.timestamp():
    #                 #         self._buffer.append(d)
    #             else:
    #                 # text
    #                 for n in range(0, self._buffer_size):
    #                     row = self._file.readline()
    #
    #                     if not row:
    #                         file_end = True
    #                         break
    #
    #                     ts, o, h, l, c, s, vol = row.rstrip('\n').split('\t')
    #
    #                     ts = float(ts) * 0.001
    #                     if ts < self._from_date.timestamp():
    #                         # ignore older than initial date
    #                         continue
    #
    #                     self._buffer.append((ts, float(o), float(h), float(l), float(c), float(s), float(vol)))
    #         else:
    #             file_end = True
    #
    #         if file_end:
    #             self.close()
    #
    #             # prev month/year
    #             if self._curr_date.month == 1:
    #                 self._curr_date = datetime(year=self._curr_date.year-1, month=12, day=1, tzinfo=UTC())
    #             else:
    #                 self._curr_date = datetime(year=self._curr_date.year, month=self._curr_date.month-1,
    #                                            day=1, tzinfo=UTC())
