# @date 2019-10-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Watchdog service

import time, datetime
import threading

from .service import Service
from config import utils

import logging
logger = logging.getLogger('siis.watchdog')
error_logger = logging.getLogger('siis.error.watchdog')


class WatchdogService(Service):
    """
    Watchdog service to track other services.
    """

    TIMER_DELAY = 5.0
    PING_TIMEOUT = 30.0

    def __init__(self, options):
        super().__init__("watchdog", options)

        self._activity = options.get("watchdog", True)

        # not during backtesting
        if options.get("backtesting", False):
            self._activity = False

        self._timer = None
        self._services = []
        self._pending = {}
        self._npid = 1

    def add_service(self, service):
        with self._mutex:
            if service:
                self._services.append(service)

    def remove_service(self, service):
        with self._mutex:
            if service and service in self._services:
                self._service.remove(service)

    def run_watchdog(self):
        for service in self._services:
            service.watchdog(self, WatchdogService.PING_TIMEOUT)

        now = time.time()

        with self._mutex:
            if self._pending:
                rm_it = []

                for k, d in self._pending.items():
                    if now - d[0] > WatchdogService.PING_TIMEOUT:
                        error_logger.fatal("Pid %s not joinable : %s for %s seconds !" % (k, d[1] or "undefined", WatchdogService.PING_TIMEOUT))
                        rm_it.append(k)

                        # self.notify(Signal.SIGNAL_WATCHDOG_TIMEOUT, k, (k, d[1] or "undefined", WatchdogService.PING_TIMEOUT))

                if rm_it:
                    for it in rm_it:
                        # don't want continous signal
                        del self._pending[it]

        # autorestart
        self._timer = threading.Timer(WatchdogService.TIMER_DELAY, self.run_watchdog)
        self._timer.name = "watchdog"
        self._timer.start()

    def start(self, options):
        if self._activity and not self._timer:
            self._timer = threading.Timer(WatchdogService.TIMER_DELAY, self.run_watchdog)
            self._timer.name = "watchdog"
            self._timer.start()

    def terminate(self):
        if self._timer:
            self._timer.cancel()
            self._timer.join()
            self._timer = None

    def service_pong(self, pid, timestamp, msg):
        with self._mutex:
            if pid in self._pending:
                del self._pending[pid]

    def service_timeout(self, service, msg):
        error_logger.fatal("Service %s not joinable : %s !" % (service, msg))
        # self.notify(Signal.SIGNAL_WATCHDOG_UNREACHABLE, k, (service, msg))

    def gen_pid(self, ident):
        r = 0

        with self._mutex:
            r = self._npid
            self._npid += 1
            self._pending[r] = (time.time(), ident)

        return r

    def ping(self, timeout):
        for service in self._services:
            service.ping(timeout)
