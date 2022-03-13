# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Service base class

import threading

from common.signalhandler import SignalHandler
from common.baseservice import BaseService

from terminal.terminal import Terminal


class Service(BaseService):
    """
    Base class for any service.
    """

    def __init__(self, name: str, options: dict):
        super().__init__(name)

        self._signals_handler = SignalHandler(self)
        self._mutex = threading.RLock()

    def lock(self, blocking: bool = True, timeout: float = -1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def start(self, options: dict):
        pass

    def terminate(self):
        pass

    def sync(self):
        pass

    def notify(self, signal_type: int, source_name: str, signal_data):
        pass

    def add_listener(self, base_service):
        with self._mutex:
            self._signals_handler.add_listener(base_service)

    def remove_listener(self, base_service):
        with self._mutex:
            self._signals_handler.remove_listener(base_service)

    def command(self, command_type: int, data):
        return None

    def receiver(self, signal):
        pass

    def ping(self, timeout: float):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            self._mutex.release()
        else:
            Terminal.inst().action("%s is not joinable for %s seconds !" % (self.name, timeout))

    def watchdog(self, watchdog_service, timeout: float):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (
                self.name, timeout))
