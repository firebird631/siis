# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

import threading


class View(object):
    """
    View base class.
    """

    def __init__(self):
        self._id = ""
        self._mutex = threading.RLock()  # reentrant locker

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def on_key_pressed(self, key):
        pass

    def refresh(self):
        pass

    def fetch(self):
        pass
