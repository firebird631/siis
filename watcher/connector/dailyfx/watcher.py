# @date 2023-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# dailyfx.com watcher implementation

import copy
import json
import time
from typing import Optional, List

import pytz
import traceback

from datetime import datetime, timedelta

import requests

from watcher.event import BaseEvent
from watcher.watcher import Watcher
from common.signal import Signal

from connector.ig.connector import IGConnector
from connector.ig.lightstreamer import LSClient, Subscription

from instrument.instrument import Instrument
from database.database import Database

from trader.order import Order
from trader.market import Market

from common.utils import decimal_place, UTC

import logging
logger = logging.getLogger('siis.watcher.dailyfx')
exec_logger = logging.getLogger('siis.exec.dailyfx')
error_logger = logging.getLogger('siis.error.watcher.dailyfx')
traceback_logger = logging.getLogger('siis.traceback.watcher.dailyfx')


class DailyFxWatcher(Watcher):
    """
    DailyFx watcher get events (economic calendar events) using HTTP GET.

    @note todo fetch once a day latest's calendar events
    """

    PROTOCOL = "https:/"
    BASE_URL = "www.dailyfx.com/economic-calendar/events"

    FETCH_DELAY = 1.0

    UPDATE_HOURS = [0, 12]  # update twice a day (in UTC)

    def __init__(self, service):
        super().__init__("dailyfx.com", service, Watcher.WATCHER_EVENTS)

        self._host = "dailyfx.com"
        self._connector = None
        self._session = None

        self._filters = []

        self._last_updates = [0] * len(self.UPDATE_HOURS)

    def connect(self):
        super().connect()

        try:
            # identity = self.service.identity(self._name)

            if self._session is None:
                self._session = requests.Session()

                self._session.headers.update({'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'})

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

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, set ready status to false in way to retry a connection
            self._ready = False
            return False

        today = datetime.today().replace(tzinfo=UTC())

        for i, h in enumerate(self.UPDATE_HOURS):
            if today.hour == h:
                if today.day != self._last_updates[i]:
                    self._last_updates[i] = today.day
                    logger.debug("fetch events")
                    self.fetch_last_events(BaseEvent.EVENT_TYPE_ECONOMIC)

    def parse_and_filter_economic_events(self, data: dict, filters: List):
        # @todo
        return data

    def fetch_last_events(self, event_type: int):
        curr = datetime.today().replace(tzinfo=UTC())

        if event_type == BaseEvent.EVENT_TYPE_ECONOMIC:
            url = '/'.join((self.PROTOCOL, self.BASE_URL, curr.strftime("%Y-%m-%d")))
            response = self._session.get(url)
            if response.status_code == 200:
                data = response.json()

                filtered_objects = self.parse_and_filter_economic_events(data, self._filters)
                for d in filtered_objects:
                    # @todo if we want to store them automatically
                    # self.store_calendar_events(data)
                    pass

                    # @todo notify for strategies

    def fetch_events(self, event_type: int, from_date: Optional[datetime], to_date: Optional[datetime]):
        if not from_date:
            from_date = datetime.today().replace(tzinfo=UTC())
        if not to_date:
            to_date = datetime.today().replace(tzinfo=UTC())

        begin = from_date
        end = to_date

        curr = copy.copy(begin)
        delta = timedelta(days=1)

        if event_type == BaseEvent.EVENT_TYPE_ECONOMIC:
            while curr <= end:
                url = '/'.join((self.PROTOCOL, self.BASE_URL, curr.strftime("%Y-%m-%d")))
                response = self._session.get(url)
                if response.status_code == 200:
                    data = response.json()

                    filtered_objects = self.parse_and_filter_economic_events(data, self._filters)
                    for d in filtered_objects:
                        self.store_calendar_events(d)

                time.sleep(self.FETCH_DELAY)

                curr = curr + delta

    def store_calendar_events(self, data):
        if not data:
            return

        # @todo
