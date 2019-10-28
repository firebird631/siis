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

        self._views = {}

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def init(self):
        pass

    def terminate(self):
        pass
 
    @property
    def name(self):
        return "view"

    def ping(self, timeout):
        pass

    def watchdog(self, watchdog_service, timeout):
        pass

    def set_active_view(self, view_id):
        Terminal.inst().switch_view(view_id)

    def on_key_pressed(self, key):
        # progagate to active view
        if key:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    self.view.on_key_pressed(key)

    def receiver(self, signal):
        pass

    def sync(self):
        vt = Terminal.inst().active_content()
        if vt:
            view = self._views.get(vt.name)
            if view:
                self.view.refreh()

    def add_view(self, view):
        if not view:
            return

        self.lock()

        if view in self._views:
            self.unlock()
            raise Exception("View %s already registred" % view.id)

        try:
            view.create()
        except:
            self.unlock()
            raise

        self._views[view.id] = view

        self.unlock()

    def remove_view(self, view_id):
        self.lock()

        if view_id in self._views:
            view = self._views[view_id]
            if view:
                view.destroy()

            del self._views[view_id]

        self.unlock()
