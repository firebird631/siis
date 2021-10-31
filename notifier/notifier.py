# @date 2019-10-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Notifier module.

import time
import threading
import collections

from common.runnable import Runnable
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.notifier')


class Notifier(Runnable):
    """
    Notifier base class.
    """

    COMMAND_INFO = 1
    COMMAND_TOGGLE = 2

    def __init__(self, name, identifier, service):
        super().__init__("nt-%s" % name)

        self._name = name
        self._identifier = identifier
        self._notifier_service = service
        self._condition = threading.Condition()

        self._signals = collections.deque()  # filtered received signals accepted to process

        # listen to its service
        self.service.add_listener(self)

    @property
    def name(self):
        return self._name

    @property
    def identifier(self):
        """Unique notifier identifier"""
        return self._identifier

    def set_identifier(self, identifier):
        """Unique notifier identifier"""
        self._identifier = identifier

    @property
    def service(self):
        return self._notifier_service

    def set_activity(self, activity):
        self._playpause = activity

    def start(self, options):
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
                self.process_signal(signal)

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

    def command(self, command_type, data):
        if command_type == self.COMMAND_INFO:
            Terminal.inst().info("%s notifier is %s" % (self.identifier, "active" if self._playpause else "disabled",),
                                 view='content')

            return {
                'name': self._name,
                'identifier': self.identifier,
                'status': self._playpause,
            }

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
