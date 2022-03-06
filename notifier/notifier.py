# @date 2019-10-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Notifier module.

import pytz
import time
import threading
import collections

from datetime import datetime

from common.runnable import Runnable
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.notifier')


class Notifier(Runnable):
    """
    Notifier base class.

    @todo Make a NotifierMsgFormatterMixin for light and verbose standardized message format, and share it on
        the different notifiers.
    """

    COMMAND_INFO = 1
    COMMAND_TOGGLE = 2

    def __init__(self, name: str, identifier: str, service):
        super().__init__("nt-%s" % name)

        self._name = name
        self._identifier = identifier
        self._notifier_service = service
        self._condition = threading.Condition()

        self._signals = collections.deque()  # filtered received signals accepted to process

        # listen to its service
        self.service.add_listener(self)

    @property
    def name(self) -> str:
        return self._name

    @property
    def identifier(self) -> str:
        """Unique notifier identifier"""
        return self._identifier

    def set_identifier(self, identifier: str):
        """Unique notifier identifier"""
        self._identifier = identifier

    @property
    def service(self):
        return self._notifier_service

    def set_activity(self, activity: bool):
        self._playpause = activity

    def start(self, options: dict):
        return super().start(options)

    def stop(self):
        # want to leave now
        if self._running:
            self._running = False

        # unlock
        self._condition.acquire()
        self._condition.notify()
        self._condition.release()

    def terminate(self):
        pass

    def notify(self):
        pass

    def pre_run(self):
        Terminal.inst().message("Running notifier %s - %s..." % (self._name, self._identifier), view='content')

    def post_run(self):
        Terminal.inst().message("Joining notifier %s - %s..." % (self._name, self._identifier), view='content')

    def pre_update(self):
        self.wait_signal()

    def process_signal(self, signal):
        """
        To be override
        """
        pass

    def update(self):
        count = 0

        while self._signals:
            signal = self._signals.popleft()
            if signal:
                try:
                    self.process_signal(signal)
                except Exception as e:
                    logger.error(repr(e))

            count += 1
            if count > 10:
                # yield
                time.sleep(0)

        return True

    def post_update(self):
        pass

    def wait_signal(self):
        self._condition.acquire()
        while self._running and not self._signals:
            self._condition.wait()
        self._condition.release()

    def push_signal(self, signal):
        if not signal:
            return

        self._condition.acquire()
        self._signals.append(signal)
        self._condition.notify()
        self._condition.release()

    def command(self, command_type: int, data):
        if command_type == self.COMMAND_INFO:
            message = "%s notifier is %s" % (self.identifier, "active" if self._playpause else "disabled")
            return {'error': False, 'messages': message}

        return None

    def receiver(self, signal):
        if not self._playpause:
            return

    def ping(self, timeout):
        pass

    def watchdog(self, watchdog_service, timeout):
        pass

    def pong(self, timestamp, pid, watchdog_service, msg):
        pass

    @staticmethod
    def parse_utc_datetime(utc_dt: str) -> datetime:
        if utc_dt:
            return datetime.strptime(utc_dt, '%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            return datetime.now()

    @staticmethod
    def format_datetime(dt: datetime, local: str = "fr") -> str:
        if local == "fr":
            dt = dt.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Europe/Paris'))
            return dt.strftime('%Y-%m-%d %H:%M:%S (Paris)') if dt else ''
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S (UTC)') if dt else ''

    @staticmethod
    def estimate_profit_loss(instrument, trade):
        """
        Estimate PLN without fees.
        """
        direction = 1 if trade['direction'] == "long" else -1

        # estimation at close price
        close_exec_price = instrument.close_exec_price(direction)

        # no current price update
        if not close_exec_price:
            return 0.0

        entry_price = float(trade['avg-entry-price'])

        if direction > 0 and entry_price > 0:
            profit_loss = (close_exec_price - entry_price) / entry_price
        elif direction < 0 and entry_price > 0:
            profit_loss = (entry_price - close_exec_price) / entry_price
        else:
            profit_loss = 0.0

        return profit_loss
