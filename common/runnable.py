# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy interface

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union, Callable, Optional, Tuple

import traceback
import threading
import time

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.common.runnable')
error_logger = logging.getLogger('siis.error.common.runnable')


class Runnable(ABC):
    """
    Abstract model for any service
    """

    DEFAULT_USE_BENCH = False
    MAX_BENCH_SAMPLES = 30

    _ping: Optional[Tuple[int, object, bool]]

    def __init__(self, thread_name=""):
        self._running = False
        self._playpause = False
        self._thread = threading.Thread(name=thread_name, target=self.run)
        self._mutex = threading.RLock()  # reentrant locker
        self._error = None
        self._ping = None

        self._bench = Runnable.DEFAULT_USE_BENCH
        self._last_time = []
        self._worst_time = 0.0
        self._avg_time = 0.0

    #
    # running
    #

    @property
    def thread(self) -> threading.Thread:
        return self._thread

    @property
    def mutex(self) -> threading.RLock:
        return self._mutex

    def start(self, options):
        if not self._running:
            self._running = True
            try:
                self._thread.start()
                self._playpause = True
            except Exception as e:
                self._running = False
                logger.error(repr(e))
                return False

            return True
        else:
            return False

    def play(self):
        if self._running:
            self._playpause = True

    def pause(self):
        if self._running:
            self._playpause = False

    def toggle_playpause(self):
        self._playpause = not self._playpause

    def stop(self):
        if self._running:
            self._running = False

    #
    # command
    #

    def command(self, command: int, data: dict) -> Union[dict, None]:
        """A helper to manage the call of some specific actions"""
        return None

    #
    # processing
    #

    def pre_run(self):
        """Anything that must be done before running the iteration loop. It is called a single time"""
        pass

    def post_run(self):
        """Anything that must be done after terminate the iteration loop. It is called a single time"""
        pass

    def pre_update(self):
        """Anything that must be done before each update. It is called at any iteration"""
        pass

    def update(self):
        # time.sleep(1)  # default does not use CPU
        return True

    def post_update(self):
        """Anything that must be done after each update. It is called at any iteration"""
        pass

    def __process_once(self):
        if self._playpause:
            self.pre_update()
            self.update()
            self.post_update()
        else:
            time.sleep(0.1)  # avoid CPU usage

        if self._ping:
            # process the pong message
            self.pong(time.time(), self._ping[0], self._ping[1], self._ping[2])
            self._ping = None

    def __process_once_bench(self):
        begin = time.time()

        if self._playpause:
            self.pre_update()
            self.update()
            self.post_update()
        else:
            time.sleep(0.1)  # avoid CPU usage

        self._last_time.append(time.time() - begin)
        self._worst_time = max(self._worst_time, self._last_time[-1])
        self._avg_time = sum(self._last_time) / len(self._last_time)

        if len(self._last_time) > Runnable.MAX_BENCH_SAMPLES:
            self._last_time.pop(0)

        if self._ping:
            # process the pong message
            msg = "%s - Bench : last loop %.3fms / worst loop %.3fms / avg loop %.3fms" % (
                self._ping[2],
                self._last_time[-1]*1000, self._worst_time*1000, self._avg_time*1000)

            logger.debug(msg)

            self.pong(begin, self._ping[0], self._ping[1], self._ping[2])
            self._ping = None

    def run(self):
        try:
            self.pre_run()
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())
            
            self._error = e
            self._running = False

            return

        # restart the loop if exception thrown
        if self._bench:
            while self._running:
                try:
                    while self._running:
                        self.__process_once_bench()
                except Exception as e:
                    logger.error(repr(e))
                    error_logger.error(traceback.format_exc())
                    self._error = e
        else:
            while self._running:
                try:
                    while self._running:
                        self.__process_once()
                except Exception as e:
                    logger.error(repr(e))
                    error_logger.error(traceback.format_exc())
                    self._error = e

        try:
            self.post_run()
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())
            self._error = e

        self._running = False

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    @property
    @abstractmethod
    def name(self) -> str:
        """Must be always valid"""
        return ""

    @property
    def identifier(self) -> str:
        """Not any service need an identifier then depending it is not always mandatory"""
        return ""

    @property
    def running(self) -> bool:
        return self._running
    
    @property
    def playing(self) -> bool:
        """Activity status. If False none of pre_update, update and post_update are called per iteration"""
        return self._playpause

    def sync(self):
        """
        This method is called by the main thread of the application at each frame. If a runnable need a global
        synchronous process it can be done here.
        """
        pass

    def ping(self, timeout: float):
        """Could be overrides to add specificities"""
        if not self._running:
            return
        
        if self._mutex.acquire(timeout=timeout):
            self._ping = (0, None, True)
            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join thread %s for %s seconds" % (
                self._thread.name if self._thread else "unknown", timeout), view='content')

    def watchdog(self, watchdog_service, timeout: float):
        """Could be overrides to add specificities"""
        if not self._running:
            return

        if self._mutex.acquire(timeout=timeout):
            self._ping = (watchdog_service.gen_pid(self._thread.name if self._thread else "unknown"),
                          watchdog_service, False)
            self._mutex.release()
        else:
            watchdog_service.service_timeout(
                self._thread.name if self._thread else "unknown",
                "Unable to join thread %s for %s seconds" % (self._thread.name if self._thread else "unknown", timeout))

    def pong(self, timestamp: float, pid: int, watchdog_service, status: bool):
        """Could be overrides to add specificities"""
        if status:
            Terminal.inst().action("Thread %s is alive" % self.name, view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, status)

    @classmethod
    def mutexed(cls, fn: Callable):
        """
        Annotation for methods that require mutex locker.
        """
        def wrapped(self, *args, **kwargs):
            with self._mutex:
                return fn(self, *args, **kwargs)
    
        return wrapped
