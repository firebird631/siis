# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Tick storage/streaming per market

import os
import json
import copy
import time
import threading
import traceback
import pathlib
import struct
import collections

import numpy as np

from datetime import datetime

import logging
logger = logging.getLogger('siis.database')


class TickStorage(object):
    """
    Default implementation store in a single file but further one file per month.
    File format is a tab separated file with no header and :
    timestamp(int ms since epoch) bid(str) ask(str) last(str) volume(str) direction(signed char)

    Price and volume should be formated with the asset precision if possible but scientific notation
    is tolerate.

    @todo Seek to file position before writing.
    """

    FLUSH_DELAY = 60.0

    def __init__(self, markets_path, broker_id, market_id, text=True, binary=True):
        self._markets_path = markets_path
        self._mutex = threading.RLock()

        self._broker_id = broker_id
        self._market_id = market_id

        self._last_save = 0

        self._ticks = []
        self._curr_date = None

        self._text_file = None
        self._binary_file = None

        self._text = text
        self._binary = binary

        self._struct = struct.Struct('<dddddb')

    def store(self, data):
        """
        @param data tuple with (broker_id, market_id, timestamp, bid, ask, last, volume)
        """
        with self._mutex:
            if isinstance(data, list):
                self._ticks.extend(data)
            else:
                self._ticks.append(data)        

    def has_data(self):
        with self._mutex:
            return len(self._ticks) > 0

    def open(self, date_utc):
        if self._text and not self._text_file:
            try:
                broker_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, 'T')  # use broker name as directory
                if not broker_path.exists():
                    broker_path.mkdir(parents=True)

                self._curr_date = date_utc

                # append to file, filename according to the month (UTC) of the timestamp
                filename = self._curr_date.strftime('%Y%m') + self._market_id
                self._text_file = open(str(broker_path) + '/' + filename, 'at')  # user market as file name
            except Exception as e:
                logger.error(repr(e))

        if self._binary and not self._binary_file:
            try:
                broker_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, 'T')  # use broker name as directory
                if not broker_path.exists():
                    broker_path.mkdir(parents=True)

                self._curr_date = date_utc

                # append to file, filename according to the month (UTC) of the timestamp
                filename = self._curr_date.strftime('%Y%m') + self._market_id + ".dat"
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
        return (time.time() - self._last_save) >= TickStorage.FLUSH_DELAY

    def flush(self, close_at_end=True):
        with self._mutex:
            ticks = self._ticks
            self._ticks = []

        if not ticks:
            return

        n = 0
        try:
            for d in ticks:
                # while ticks:
                #     # process next
                #     d = ticks.pop(0)  # too slow when millions of elements

                date_utc = datetime.utcfromtimestamp(d[2] * 0.001)

                if self._curr_date and (self._curr_date.year != date_utc.year or self._curr_date.month != date_utc.month):
                    self.close()

                self.open(date_utc)  # if necessary

                if self._text_file: 
                    # convert to a tabular row          
                    content = "%i\t%s\t%s\t%s\t%s\t%i\n" % (d[2], d[3], d[4], d[5], d[6], d[7])  # t b a l v d
                    self._text_file.write(content)

                if self._binary_file:
                    # convert to a struct
                    f = (float(d[2]) * 0.001, float(d[3]), float(d[4]), float(d[5]), float(d[6]), d[7])  # t b a l v d (t in second)
                    # s = struct.pack('<dddddb', *f)
                    s = self._struct.pack(*f)

                    self._binary_file.write(s)

                n += 1
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            with self._mutex:
                # self._ticks = ticks + self._ticks
                self._ticks = ticks[n:] + self._ticks

        self._last_save = time.time()

        if close_at_end:
            self.close()  # avoid too many handles


class TickStreamer(object):
    """
    Streamer that read data from an initial position.
    """

    TICK_SIZE = 5*8+1  # 41bytes

    def __init__(self, markets_path, broker_id, market_id, from_date, to_date=None, buffer_size=1000, binary=True):
        """
        @param from_date datetime Object
        @param to_date datetime Object
        """

        self._markets_path = markets_path
        self._broker_id = broker_id
        self._market_id = market_id

        self._from_date = from_date
        self._to_date = to_date

        self._curr_date = from_date

        self._buffer = collections.deque()
        self._buffer_size = buffer_size
        self._file = None

        self._binary = binary  # use binary format
        self._is_binary = False

        self._struct = struct.Struct('dddddb')
        self._tick_type = np.dtype([('t', 'float64'), ('b', 'float64'), ('a', 'float64'), ('l', 'float64'), ('v', 'float64'), ('d', 'int8')])

    def open(self):
        if self._file:
            return

        data_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, 'T')
        if not data_path.exists():
            return

        # try first with binary file
        if self._binary:
            # with .dat extension
            filename = "%s%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id)
            pathname = '/'.join((str(data_path), filename))

            if os.path.isfile(pathname):
                self._file = open(pathname, "rb")
                self._is_binary = True

                st = os.stat(pathname)
                file_size = st.st_size

                # directly seek to intial position to avoid useless parsing
                timestamp = self._curr_date.timestamp()
                prev_timestamp = 0
                pos = 0
                left = 0
                right = file_size
                eof = file_size-1 if file_size > 0 else 0

                while 1:
                    data = self._file.read(TickStreamer.TICK_SIZE)

                    if not data:
                        break

                    tick = self._struct.unpack(data)

                    if right - left <= TickStreamer.TICK_SIZE:
                        # found our starting offset
                        self._file.seek(-TickStreamer.TICK_SIZE, 1)
                        break

                    if tick[0] < timestamp:
                        # move forward
                        left = pos + TickStreamer.TICK_SIZE
                        prev_timestamp = timestamp

                    elif tick[0] > timestamp:
                        # move backward
                        right = pos - TickStreamer.TICK_SIZE

                    elif self._file.tell() >= eof:
                        break

                    pos = max(0, left + ((right - left) // TickStreamer.TICK_SIZE) // 2 * TickStreamer.TICK_SIZE)
                    self._file.seek(pos, 0)

        # if not binary asked or binary not found try with text file
        if not self._file:
            # no extension
            filename = "%s%s" % (self._curr_date.strftime('%Y%m'), self._market_id)
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
            # for tick in self._buffer:
            #   if tick[0] <= timestamp:
            #       n += 1
            #   else:
            #       break

            # if n > 0:
            #   # more results
            #   results.extend(self._buffer[:n])

            #   # remaining buffer
            #   self._buffer = self._buffer[n:]

            # until timestamp (pop version is 30% speedup)
            # while self._buffer and self._buffer[0].timestamp <= timestamp:
            while self._buffer and self._buffer[0][0] <= timestamp:
                # results.append(self._buffer.pop(0))
                results.append(self._buffer.popleft())

            # if self.finished() or (self._buffer and self._buffer[0].timestamp > timestamp):
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
                dest.append(self._buffer.popleft())
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
                    arr = self._file.read(TickStreamer.TICK_SIZE*self._buffer_size)
                    data = self._struct.iter_unpack(arr)

                    if len(arr) < self._buffer_size:
                       file_end = True

                    # speedup using numpy fromfile but its a one shot loads
                    # data = np.fromfile(self._file, dtype=self._tick_type)
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

                        ts, bid, ask, last, vol, d = row.rstrip('\n').split('\t')

                        ts = float(ts) * 0.001
                        if ts < self._from_date.timestamp():
                            # ignore older than initial date
                            continue

                        self._buffer.append((ts, float(bid), float(ask), float(last), float(vol), int(d)))
            else:
                file_end = True

            if file_end:
                self.close()

                # next month/year
                if self._curr_date.month == 12:
                    self._curr_date = self._curr_date.replace(year=self._curr_date.year+1, month=1, day=1)
                else:
                    self._curr_date = self._curr_date.replace(month=self._curr_date.month+1, day=1)


class TextToBinary(object):
    """
    Tab separated text format to binary file.
    """

    def __init__(self, markets_path, broker_id, market_id, from_date, to_date):
        """
        @param from_date datetime Object
        @param to_date datetime Object
        """

        self._markets_path = markets_path
        self._broker_id = broker_id
        self._market_id = market_id

        self._from_date = from_date
        self._to_date = to_date

        self._curr_date = from_date

        self._buffer = []
        
        self._text_file = None
        self._binary_file = None

        self._struct = struct.Struct('<dddddb')

    def open(self):
        if self._text_file:
            return

        data_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, 'T')
        if not data_path.exists():
            return

        # no extension
        filename = "%s%s" % (self._curr_date.strftime('%Y%m'), self._market_id)
        pathname = '/'.join((str(data_path), filename))

        if os.path.isfile(pathname):
            self._text_file = open(pathname, "rt")

        if self._text_file:
            # with .dat extension
            filename = "%s%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id)
            pathname = '/'.join((str(data_path), filename))

            self._binary_file = open(pathname, "wb")

    def close(self):
        if self._text_file:
            self._text_file.close()
            self._text_file = None

        if self._binary_file:
            self._binary_file.close()
            self._binary_file = None

    def process(self):
        while not self.finished():
            self.next()

    def finished(self):
        return (self._curr_date >= self._to_date)

    def next(self):
        if self._curr_date < self._to_date:
            self.open()

            if self._text_file and self._binary_file:
                for row in self._text_file:
                    ts, bid, ask, last, vol, d = row.rstrip('\n').split('\t')

                    ts = float(ts) * 0.001

                    # convert to a struct
                    f = [ts, float(bid), float(ask), float(vol), float(last), int(d)]  # t b a l v d (t in second)
                    # s = struct.pack('<dddddb', *f)
                    s = self._struct.pack(*f)

                    self._binary_file.write(s)

            self.close()

            # next month/year
            if self._curr_date.month == 12:
                self._curr_date = self._curr_date.replace(year=self._curr_date.year+1, month=1)
            else:
                self._curr_date = self._curr_date.replace(month=self._curr_date.month+1)


class LastTickFinder(object):
    """
    Last tick find helper.
    """

    TICK_SIZE = 5*8+1  # 41bytes

    def __init__(self, markets_path, broker_id, market_id, buffer_size=1000, binary=True):
        self._markets_path = markets_path
        self._broker_id = broker_id
        self._market_id = market_id

        self._curr_date = datetime.now()

        self._buffer_size = buffer_size
        self._binary = binary  # use binary format

        self._struct = struct.Struct('ddddb')
        self._tick_type = np.dtype([('t', 'float64'), ('b', 'float64'), ('a', 'float64'), ('l', 'float64'), ('v', 'float64'), ('d', 'int8')])

    def open(self):
        data_path = pathlib.Path(self._markets_path, self._broker_id, self._market_id, 'T')
        if not data_path.exists():
            return None

        # try first with binary file
        if self._binary:
            # with .dat extension
            filename = "%s%s.dat" % (self._curr_date.strftime('%Y%m'), self._market_id)
            pathname = '/'.join((str(data_path), filename))

            tick = None

            if os.path.isfile(pathname):
                bfile = open(pathname, "rb")

                # directly seek to the last tick entry
                bfile.seek(-TickStreamer.TICK_SIZE, 2)

                arr = bfile.read(TickStreamer.TICK_SIZE)
                tick = self._struct.unpack(arr)

                bfile.close()

            return tick

        # if not binary asked or binary not found try with text file
        else:
            # no extension
            filename = "%s%s" % (self._curr_date.strftime('%Y%m'), self._market_id)
            pathname = '/'.join((str(data_path), filename))

            tick = None

            if os.path.isfile(pathname):
                tfile = open(pathname, "rb")

                # directly seek to the last tick entry
                tfile.seek(-self._buffer_size, 2)

                data = tfile.read(self._buffer_size)
                content = data.decode('utf-8').rstrip('\n')
                pos = content.rfind('\n')

                if pos >= 0:
                    row = content[pos+1:]
                    ts, bid, ask, last, vol, d = row.rstrip('\n').split('\t')

                    # timestamp in seconds
                    tick = (float(ts) * 0.001, float(bid), float(ask), float(last), float(vol), int(d))

                tfile.close()

            return tick

        return None

    def last(self):
        tick = None

        while 1:
            tick = self.open()

            if tick:
                break

            # prev month/year
            if self._curr_date.month == 1:
                if self._curr_date.year < 2000:
                    return None

                self._curr_date = self._curr_date.replace(year=self._curr_date.year-1, month=12, day=1)
            else:
                self._curr_date = self._curr_date.replace(month=self._curr_date.month-1, day=1)

        return tick

    def __bufferize(self):
        if self._curr_date < self._to_date:
            if not self._file:
                self.open()

            file_end = False

            if self._file:
                if self._is_binary:
                    arr = self._file.read(LastTickFinder.TICK_SIZE*self._buffer_size)
                    data = self._struct.iter_unpack(arr)

                    if len(arr) < self._buffer_size:
                       file_end = True

                    # speedup using numpy fromfile but its a one shot loads
                    # data = np.fromfile(self._file, dtype=self._tick_type)
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

                        ts, bid, ask, last, vol, d = row.rstrip('\n').split('\t')

                        ts = float(ts) * 0.001
                        if ts < self._from_date.timestamp():
                            # ignore older than initial date
                            continue

                        self._buffer.append((ts, float(bid), float(ask), float(last), float(vol), int(d)))
            else:
                file_end = True

            if file_end:
                self.close()

                # prev month/year
                if self._curr_date.month == 1:
                    self._curr_date = self._curr_date.replace(year=self._curr_date.year-1, month=12, day=1)
                else:
                    self._curr_date = self._curr_date.replace(month=self._curr_date.month-1, day=1)
