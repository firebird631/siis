# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy interface

import traceback
import threading
import time
from typing import Union, Callable

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.common.runnable')
error_logger = logging.getLogger('siis.error.common.runnable')


class Runnable(object):

    DEFAULT_USE_BENCH = False
    MAX_BENCH_SAMPLES = 30

    def __init__(self, thread_name=""):
        self._running = False
        self._playpause = False
        self._thread = threading.Thread(name=thread_name, target=self.run)
        self._mutex = threading.RLock()  # reentrant locker
        self._error = None
        self._ping = None

        self._bench = Runnable.DEFAULT_USE_BENCH
        self._last_time = []
        self._worst_time = 0
        self._avg_time = 0

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

    def update(self):
        # time.sleep(1)  # default does not use CPU
        return True

    def command(self, command: int, data: dict) -> Union[dict, None]:
        return None

    def pre_run(self):
        pass

    def post_run(self):
        pass

    def pre_update(self):
        pass

    def post_update(self):
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
    def name(self) -> str:
        return ""

    @property
    def identifier(self) -> str:
        return ""

    @property
    def running(self) -> bool:
        return self._running
    
    @property
    def playing(self) -> bool:
        return self._playpause

    def sync(self):
        pass

    def ping(self, timeout: float):
        if not self._running:
            return
        
        if self._mutex.acquire(timeout=timeout):
            self._ping = (0, None, True)
            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join thread %s for %s seconds" % (
                self._thread.name if self._thread else "unknown", timeout), view='content')

    def watchdog(self, watchdog_service, timeout: float):
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

    def pong(self, timestamp: float, pid: int, watchdog_service, msg: str):
        if msg:
            Terminal.inst().action("Thread %s is alive %s" % (self.name, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    @classmethod
    def mutexed(cls, fn: Callable):
        """
        Annotation for methods that require mutex locker.
        """
        def wrapped(self, *args, **kwargs):
            with self._mutex:
                return fn(self, *args, **kwargs)
    
        return wrapped
