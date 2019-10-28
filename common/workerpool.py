# @date 2018-09-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy appliance worker pool.

import traceback
import threading
import time
import multiprocessing
import collections

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.common.workerpool')
error_logger = logging.getLogger('siis.error.common.workerpool')


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
        count_down, job = self._pool.next_job()

        if job:
            job[0](*job[1])

        if count_down:
            count_down.done()

        if not job:
            # avoid CPU usage
            time.sleep(0.00001)

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
                logger.error(repr(e))
                error_logger.error(traceback.format_exc())

                self._error = e

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

    __slots__ = '_num_workers', '_workers', '_queue', '_mutex'

    def __init__(self, num_workers=None):
        if not num_workers:
            self._num_workers = multiprocessing.cpu_count()
        else:
            self._num_workers = num_workers

        self._workers = []
        self._queue = collections.deque()
        self._mutex = threading.RLock()

    def start(self):
        self._workers = [Worker(self, i) for i in range(0, self._num_workers)]

        for worker in self._workers:
            worker.start()

    def stop(self):
        for worker in self._workers:
            if worker._running:
                worker.stop()
                worker.join()

    def ping(self, timeout):
        if self._mutex.acquire(timeout=timeout):
            for worker in self._workers:
                worker.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join worker pool for %s seconds" % (timeout,), view='content')

    def watchdog(self, watchdog_service, timeout):
        if self._mutex.acquire(timeout=timeout):
            for worker in self._workers:
                worker.watchdog(watchdog_service, timeout)
            self._mutex.release()
        else:
            watchdog_service.service_timeout("workerpool", "Unable to join worker pool for %s seconds" % timeout)

    def add_job(self, count_down, job):
        self._mutex.acquire()
        self._queue.append((count_down, job))
        self._mutex.release()

    def next_job(self):
        count_down = None
        job = None

        self._mutex.acquire()
        if len(self._queue):
            count_down, job = self._queue.popleft()
        self._mutex.release()

        return count_down, job

    def new_count_down(self, n):
        return CountDown(n)
