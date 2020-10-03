# @date 2018-09-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy worker pool.

import traceback
import threading
import time
import multiprocessing
import collections

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.common.workerpool')
error_logger = logging.getLogger('siis.error.common.workerpool')
traceback_logger = logging.getLogger('siis.traceback.common.workerpool')


class CountDown(object):

    __slots__ = '_count', '_condition'

    def __init__(self, n):
        self._count = n
        self._condition = threading.Condition()

    def wait(self):
        self._condition.acquire()
        while self._count > 0:
            self._condition.wait()
        self._condition.release()

    def done(self):
        self._condition.acquire()
        self._count -= 1
        if self._count <= 0:
            self._condition.notifyAll()
        self._condition.release()


class Worker(threading.Thread):

    def __init__(self, pool, uid):
        super().__init__(name="st-wk-%s" % uid)

        self._pool = pool
        self._uid = uid
        self._running = False
        self._ping = None

    def start(self):
        if not self._running:
            self._running = True
            try:
                super().start()
            except Exception as e:
                self._running = False
                return False

            return True
        else:
            return False

    def stop(self):
        if self._running:
            self._running = False

    def __process_once(self):
        count_down, job = self._pool.next_job(self)

        if job:
            try:
                job[0](*job[1])
            except Exception as e:
                error_logger.error(str(e))
                traceback_logger.error(traceback.format_exc())

        if count_down:
            count_down.done()

        if self._ping:
            # process the pong message
            self.pong(time.time(), self._ping[0], self._ping[1], self._ping[2])
            self._ping = None

    def run(self):
        # don't waste with try/catch, do it only at last level
        # restart the loop if exception thrown
        while self._running:
            try:
                while self._running:
                    self.__process_once()
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        self._running = False

    @property
    def running(self):
        return self._running

    @property
    def uid(self):
        return self._uid

    def ping(self, timeout):
        self._ping = (0, None, True)

    def watchdog(self, watchdog_service, timeout):
        self._ping = (watchdog_service.gen_pid("worker-%s" % self._uid), watchdog_service, False)

    def pong(self, timestamp, pid, watchdog_service, msg):
        if msg:
            Terminal.inst().action("WokerPool::Worker %s is alive %s" % (self._uid, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)


class WorkerPool(object):

    __slots__ = '_num_workers', '_workers', '_queue', '_condition'

    def __init__(self, num_workers=None):
        if not num_workers:
            self._num_workers = multiprocessing.cpu_count()
        else:
            self._num_workers = num_workers

        self._workers = []
        self._queue = collections.deque()
        self._condition = threading.Condition()

    def start(self):
        self._workers = [Worker(self, i) for i in range(0, self._num_workers)]

        for worker in self._workers:
            worker.start()

    def stop(self):
        for worker in self._workers:
            if worker._running:
                worker.stop()

        # wake up all with stop running status
        with self._condition:
            self._condition.notifyAll()

        for worker in self._workers:
            worker.join()

        self._workers = []

    def ping(self, timeout):
        if not self._workers:
            return

        if self._condition.acquire(timeout=timeout):
            for worker in self._workers:
                worker.ping(timeout)

            self._condition.notifyAll()
            self._condition.release()
        else:
            Terminal.inst().action("Unable to join worker pool for %s seconds" % (timeout,), view='content')

    def watchdog(self, watchdog_service, timeout):
        if not self._workers:
            return

        if self._condition.acquire(timeout=timeout):
            for worker in self._workers:
                worker.watchdog(watchdog_service, timeout)

            self._condition.notifyAll()
            self._condition.release()
        else:
            watchdog_service.service_timeout("workerpool", "Unable to join worker pool for %s seconds" % timeout)

    def add_job(self, count_down, job):
        with self._condition:
            self._queue.append((count_down, job))
            self._condition.notify()

    def next_job(self, worker):
        count_down = None
        job = None

        with self._condition:
            # running cancel wait, ping too, normal case is a job is pending
            while not len(self._queue) and worker._running and not worker._ping:
                self._condition.wait()

            if len(self._queue):
                count_down, job = self._queue.popleft()

        return count_down, job

    def new_count_down(self, n):
        return CountDown(n)
