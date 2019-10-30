# @date 2019-10-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Watchdog service

import time, datetime
import threading

from .service import Service
from config import utils

import logging
logger = logging.getLogger('siis.monitor')
error_logger = logging.getLogger('siis.error.monitor')


class WatchdogService(Service):
    """
    Watchdog service to track other services.
    """

    TIMER_DELAY = 5.0
    PING_TIMEOUT = 10.0

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
        self.lock()
        if service:
            self._services.append(service)
        self.unlock()

    def remove_service(self, service):
        self.lock()
        if service and service in self._services:
            self._service.remove(service)
        self.unlock()

    def run_watchdog(self):
        for service in self._services:
            service.watchdog(self, WatchdogService.PING_TIMEOUT)

        now = time.time()

        self.lock()

        if self._pending:
            rm_it = []

            for k, d in self._pending.items():
                if now - d[0] > WatchdogService.PING_TIMEOUT:
                    error_logger.fatal("Pid %s not joinable : %s for %s seconds !" % (k, d[1] or "undefined", WatchdogService.PING_TIMEOUT))
                    rm_it.append(k)

            if rm_it:
                for it in rm_it:
                    # don't want continous signal
                    del self._pending[it]

        self.unlock()

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
        self.lock()
        if pid in self._pending:
            del self._pending[pid]
        self.unlock()

    def service_timeout(self, service, msg):
        error_logger.fatal("Service %s not joinable : %s !" % (service, msg))

    def gen_pid(self, ident):
        r = 0

        self.lock()
        r = self._npid
        self._npid += 1
        self._pending[r] = (time.time(), ident)
        self.unlock()

        return r

    def ping(self, timeout):
        for service in self._services:
            service.ping(timeout)
