# @date 2019-10-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Watchdog service

from __future__ import annotations

from typing import Dict, List, Tuple, Union

import time
import threading

from .service import Service

import logging
logger = logging.getLogger('siis.watchdog')
error_logger = logging.getLogger('siis.error.watchdog')


class WatchdogService(Service):
    """
    Watchdog service to track other services.
    """

    TIMER_DELAY = 15.0
    PING_TIMEOUT = 30.0

    _timer: Union[threading.Timer, None]
    _services: List[Service]
    _pending: Dict[int, Tuple[float, str]]

    def __init__(self, options: dict):
        super().__init__("watchdog", options)

        self._activity = options.get("watchdog", True)

        # not during backtesting
        if options.get("backtesting", False):
            self._activity = False

        self._timer = None
        self._services = []
        self._pending = {}
        self._npid = 1

    def add_service(self, service: Service):
        with self._mutex:
            if service:
                self._services.append(service)

    def remove_service(self, service: Service):
        with self._mutex:
            if service and service in self._services:
                self._services.remove(service)

    def run_watchdog(self):
        for service in self._services:
            service.watchdog(self, WatchdogService.PING_TIMEOUT)

        now = time.time()

        with self._mutex:
            if self._pending:
                rm_it = []

                for k, d in self._pending.items():
                    if now - d[0] > WatchdogService.PING_TIMEOUT:
                        error_logger.fatal("Pid %s not reachable : %s for %s seconds !" % (
                            k, d[1] or "undefined", WatchdogService.PING_TIMEOUT))
                        rm_it.append(k)

                        # self.notify(Signal.SIGNAL_WATCHDOG_TIMEOUT, k, (k, d[1] or "undefined", WatchdogService.PING_TIMEOUT))

                if rm_it:
                    for it in rm_it:
                        # don't want continuous signal
                        del self._pending[it]

        # auto-restart
        self._timer = threading.Timer(WatchdogService.TIMER_DELAY, self.run_watchdog)
        self._timer.name = "watchdog"
        self._timer.start()

    def start(self, options: dict):
        if self._activity and not self._timer:
            self._timer = threading.Timer(WatchdogService.TIMER_DELAY, self.run_watchdog)
            self._timer.name = "watchdog"
            self._timer.start()

    def terminate(self):
        if self._timer:
            self._timer.cancel()
            self._timer.join()
            self._timer = None

    def service_pong(self, pid: int, timestamp: float, msg: str):
        with self._mutex:
            if pid in self._pending:
                del self._pending[pid]

    def service_timeout(self, service: str, msg: str):
        error_logger.fatal("Service %s not reachable : %s !" % (service, msg))
        # self.notify(Signal.SIGNAL_WATCHDOG_UNREACHABLE, k, (service, msg))

    def gen_pid(self, ident: str) -> int:
        r = 0

        with self._mutex:
            r = self._npid
            self._npid += 1
            self._pending[r] = (time.time(), ident)

        return r

    def ping(self, timeout: float):
        for service in self._services:
            service.ping(timeout)
