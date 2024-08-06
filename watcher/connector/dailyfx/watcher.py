# @date 2023-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# dailyfx.com watcher implementation

import traceback

from datetime import datetime

import requests

from watcher.service import WatcherService
from watcher.connector.dailyfx.fetcher import DailyFxFetcher
from watcher.event import BaseEvent
from watcher.watcher import Watcher
from common.signal import Signal

from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.dailyfx')
exec_logger = logging.getLogger('siis.exec.dailyfx')
error_logger = logging.getLogger('siis.error.watcher.dailyfx')
traceback_logger = logging.getLogger('siis.traceback.watcher.dailyfx')


class DailyFxWatcher(Watcher):
    """
    DailyFx watcher get events (economic calendar events) using HTTP GET.
    """

    PROTOCOL = "https:/"
    BASE_URL = "www.dailyfx.com/economic-calendar/events"

    FETCH_DELAY = 1.0
    UPDATE_DELAY = 6 * 60 * 60  # each 6 hours (4 times a day)

    def __init__(self, service: WatcherService):
        super().__init__("dailyfx.com", service, Watcher.WATCHER_EVENTS)

        self._host = "dailyfx.com"
        self._session = None

        self._filters = [(k, v) for k, v in service.watcher_config(self.name).get("filters", {}).items()]
        self._store_events = False

        self._last_update_timestamp = 0.0

    def connect(self):
        super().connect()

        with self._mutex:
            try:
                self._ready = False
                self._connecting = True

                if self._session is None:
                    self._session = requests.Session()
                    self._session.headers.update({'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'})

                self._ready = True
                self._connecting = False

            except Exception as e:
                logger.error(repr(e))
                error_logger.error(traceback.format_exc())

                self._connecting = False

    @property
    def connected(self) -> bool:
        return self._session is not None

    def disconnect(self):
        super().disconnect()

        try:
            if self._session:
                self._session = None

            self._ready = False
            self._connecting = False

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def pre_update(self):
        # try auto-reconnect
        if not self._connecting and not self._ready:
            self.connect()

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, set ready status to false in way to retry a connection
            self._ready = False
            return False

        # real time (no necessity to get it from service)
        now = datetime.utcnow()

        if now.timestamp() - self._last_update_timestamp >= self.UPDATE_DELAY:
            self.fetch_last_events(BaseEvent.EVENT_TYPE_ECONOMIC, now)
            self._last_update_timestamp = now.timestamp()

    def fetch_last_events(self, event_type: int, today: datetime):
        """
        Fetch only last events and filter only them for today.
        Others filters are also applied. Must be configured into the watcher.

        @see DailyFxFetcher for more details about filters.

        @param event_type: Event type, only support economic
        @param today: Today date in UTC timezone
        """
        # logger.debug("fetch events")
        if self._session is None:
            return

        if event_type == BaseEvent.EVENT_TYPE_ECONOMIC:
            url = '/'.join((self.PROTOCOL, self.BASE_URL, today.strftime("%Y-%m-%d")))
            try:
                response = self._session.get(url)
                if response.status_code == 200:
                    data = response.json()

                    filtered_objects = DailyFxFetcher.parse_and_filter_economic_events(data, self._filters, today)

                    for evt in filtered_objects:
                        # logger.debug(evt)  # @todo dev only
                        self.service.notify(Signal.SIGNAL_ECONOMIC_EVENT, self.name, evt)

                    if self._store_events:
                        Database.inst().store_economic_event(filtered_objects)

            except requests.RequestException as e:
                error_logger.error(repr(e))

    # def fetch_events(self, event_type: int, from_date: Optional[datetime], to_date: Optional[datetime]):
    #     if not from_date:
    #         from_date = datetime.today().replace(tzinfo=UTC())
    #     if not to_date:
    #         to_date = datetime.today().replace(tzinfo=UTC())
    #
    #     begin = from_date
    #     end = to_date
    #
    #     curr = copy.copy(begin)
    #     delta = timedelta(days=1)
    #
    #     if event_type == BaseEvent.EVENT_TYPE_ECONOMIC:
    #         while curr <= end:
    #             url = '/'.join((self.PROTOCOL, self.BASE_URL, curr.strftime("%Y-%m-%d")))
    #             try:
    #                 response = self._session.get(url)
    #                 if response.status_code == 200:
    #                     data = response.json()
    #
    #                     filtered_objects = DailyFxFetcher.parse_and_filter_economic_events(data, self._filters, curr)
    #
    #                     if self._store_events:
    #                         self.store_calendar_events(filtered_objects)
    #
    #             except requests.RequestException as e:
    #                 error_logger.error(repr(e))
    #
    #             time.sleep(self.FETCH_DELAY)
    #
    #             curr = curr + delta
