# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
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

from common.baseservice import BaseService
from common.signal import Signal

from terminal.terminal import Terminal

from common.utils import timeframe_to_str
from common.signalhandler import SignalHandler

from view.view import View
from view.viewexception import ViewServiceException


class ViewService(BaseService):
    """
    View manager service.
    It support the refreh of actives views, receive signal from others services.
    @todo
    """

    def __init__(self, options):
        super().__init__("view")

        self.strategy_service = None
        self.trader_service = None
        self.watcher_service = None

        self._mutex = threading.RLock()  # reentrant locker
        self._signals = collections.deque()  # filtered received signals
        self._signals_handler = SignalHandler(self)

        self._views = {}

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def init(self):
        self.setup_default()

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
                    view.on_key_pressed(key)

    def on_char(self, key):
        # progagate to active view
        if key:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    view.on_char(key)

    def add_listener(self, base_service):
        with self._mutex:
            self._signals_handler.add_listener(base_service)

    def remove_listener(self, base_service):
        with self._mutex:
            self._signals_handler.remove_listener(base_service)

    def receiver(self, signal):
        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
                # propagate the signal to the views
                with self._mutex:
                    self._signals_handler.notify(signal)

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_VIEW, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def sync(self):
        vt = Terminal.inst().active_content()
        if vt:
            view = self._views.get(vt.name)
            if view and view.need_refresh():
                view.refresh()
                view._refresh = time.time()
    
    def add_view(self, view):
        if not view:
            return

        with self._mutex:
            if view in self._views:
                raise ViewServiceException("View %s already registred" % view.id)

            view.create()
            self._views[view.id] = view

    def remove_view(self, view_id):
        with self._mutex:
            if view_id in self._views:
                view = self._views[view_id]
                if view:
                    view.destroy()

                del self._views[view_id]

    def toggle_percent(self, active=True):
        if active:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    view.toggle_percent()
        else:
            with self._mutex:
                for k, view in self._views.items():
                    view.toggle_percent()

    def toggle_group(self, active=True):
        if active:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    view.toggle_group()
        else:
            with self._mutex:
                for k, view in self._views.items():
                    view.toggle_group()

    def toggle_order(self, active=True):
        if active:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    view.toggle_order()
        else:
            with self._mutex:
                for k, view in self._views.items():
                    view.toggle_order()

    def toggle_datetime_format(self, active=True):
        if active:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    view.toggle_datetime_format()
        else:
            with self._mutex:
                for k, view in self._views.items():
                    view.toggle_datetime_format()
