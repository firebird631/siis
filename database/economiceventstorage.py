# @date 2024-07-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Economic event streaming with filtering, from database.

import os
import time
import threading
import pathlib
import struct
import collections
from typing import Optional, List

import numpy as np

from datetime import datetime, timedelta
from common.utils import timeframe_to_str, UTC
from instrument.instrument import Candle

import logging

from watcher.event import EconomicEvent

logger = logging.getLogger('siis.database.economiceventstorage')


class EconomicEventStreamer(object):
    """
    Economic event streaming with filtering, from database.
    """

    def __init__(self, db, from_date: datetime, to_date: Optional[datetime],
                 country: str, currency: str, min_level: int = 1,
                 buffer_size=1000):
        """
        @param from_date datetime Object
        @param to_date datetime Object
        """
        self._db = db

        self._country = country
        self._currency = currency
        self._min_level = min_level

        self._from_date = from_date
        self._to_date = to_date

        self._curr_date = from_date

        self._buffer = collections.deque()
        self._buffer_size = buffer_size

    @property
    def from_date(self):
        return self._from_date

    @property
    def to_date(self):
        return self._to_date

    def finished(self):
        return self._curr_date >= self._to_date and not self._buffer

    def next(self, timestamp):
        results = []

        while 1:
            if not self._buffer:
                self.__bufferize()

            while self._buffer and self._buffer[0].date.timestamp() <= timestamp:
                results.append(self._buffer.popleft())

            if self.finished() or (self._buffer and self._buffer[0].date.timestamp() > timestamp):
                break

        return results

    def __bufferize(self):
        results = self.query(self._curr_date, None, self._buffer_size)
        if results:
            self._buffer.extend(results)
            self._curr_date = results[-1].date
        else:
            self._curr_date = self._curr_date + timedelta(days=1)

    def query(self, from_date, to_date, limit_or_last_n):
        """
        Query economic event according to filters
        @param from_date Optional
        @param to_date Optional
        @param limit_or_last_n Optional
        """
        cursor = self._db.cursor()

        try:
            if from_date and to_date:
                self.query_from_to(cursor, from_date, to_date)
            elif from_date:
                self.query_from_limit(cursor, from_date, limit_or_last_n)
            elif to_date:
                self.query_to(cursor, to_date)
            elif limit_or_last_n:
                self.query_last(cursor, limit_or_last_n)
            else:
                self.query_all(cursor)
        except Exception as e:
            logger.error(repr(e))
            return []

        rows = cursor.fetchall()
        events = []

        for row in rows:
            economic_event = EconomicEvent()

            economic_event.code = row[0]
            economic_event.date = datetime.strptime(row[1], '%Y-%m-%dT%H:%M').replace(tzinfo=UTC())
            economic_event.country = row[2]
            economic_event.currency = row[3]
            economic_event.title = row[4]
            economic_event.reference = row[5]
            economic_event.level = row[6]
            economic_event.previous = row[7]
            economic_event.actual = row[8]
            economic_event.forecast = row[9]
            economic_event.actual_meaning = row[10]
            economic_event.previous_meaning = row[11]

            events.append(economic_event)
            # logger.info(economic_event)

        return events

    def query_all(self, cursor):
        cursor.execute(self.base_query() + " ORDER BY date ASC")

    def query_last(self, cursor, limit):
        cursor.execute(self.base_count_query())

        count = int(cursor.fetchone()[0])
        offset = max(0, count - limit)

        cursor.execute(self.base_query() + " ORDER BY date ASC LIMIT %i OFFSET %i""" % (limit, offset))

    def query_from_to(self, cursor, from_date, to_date):
        from_to = " AND date >= '%s' AND date <= '%s'" % (from_date, to_date)
        cursor.execute(self.base_query() + from_to + " ORDER BY date ASC")

    def base_query(self):
        base_query = "SELECT code, date, country, currency, title, reference, level, previous, actual, forecast, actual_meaning, previous_meaning FROM economic_event WHERE level >= %i" % self._min_level

        if self._country:
            base_query += " AND country = '%s'" % self._country
        if self._currency:
            base_query += " AND currency = '%s'" % self._currency
            
        return base_query

    def base_count_query(self):
        base_query = "SELECT COUNT(*) WHERE level >= %i" % self._min_level

        if self._country:
            base_query += " AND country = '%s'" % self._country
        if self._currency:
            base_query += " AND currency = '%s'" % self._currency

        return base_query
    
    def query_from_limit(self, cursor, from_date, limit):
        cursor.execute(self.base_query() + " AND date >= '%s' ORDER BY date ASC LIMIT %i" % (from_date, limit))

    def query_to(self, cursor, to_date):
        cursor.execute(self.base_query() + " AND date <= '%s' ORDER BY date ASC" % to_date)
