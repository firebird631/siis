# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

import collections
import threading
import os
import time
import logging
import traceback

from datetime import datetime, timedelta

from trader.position import Position

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from terminal.terminal import Terminal

from common.utils import timeframe_to_str

from view.view import View


class ViewService(Notifiable):
    """
    View manager service.
    It support the refreh of actives views, receive signal from others services.

    @todo
    """

    def __init__(self):
        super().__init__("view")

        self.strategy_service = None
        self.trader_service = None
        self.watcher_service = None

        self._mutex = threading.RLock()  # reentrant locker
        self._signals = collections.deque()  # filtered received signals

        self._refresh = 0
        self._item = 0

        self._views = []
        self._active_view = None

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def init(self):
        pass

    def terminate(self):
        pass

    def prev_item(self):
        self._item -= 1
        if self._item < 0:
            self._item = 0

        self._refresh = 0  # force refresh

    def next_item(self):
        self._item += 1
        self._refresh = 0  # force refresh

    def set_active_view(self, view_id):
        pass  # @todo or comes from the Terminal

    def on_key_pressed(self, key):
        if key and self._active_view:
            # progagate to active view
            self._active_view.on_key_pressed(key)

    def receiver(self, signal):
        pass

    def sync(self):
        pass

    def add_view(self, view):
        if not view:
            return

        self.lock()

        if view in self._views:
            self.unlock()
            raise Exception("View %s already registred" % view.id)

        self._views[view.id] = view

        self.unlock()

    def remove_view(self, view_id):
        self.lock()

        if view_id in self._views:
            del self._views[view_id]

        self.unlock()
