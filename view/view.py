# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

import time
import threading

from terminal.terminal import Terminal


class View(object):
    """
    View base class.
    """

    REFRESH_RATE = 0.5

    DATETIME_FORMATS = (
        '%Y-%m-%d %H:%M:%S',
        '%y-%m-%d %H:%M:%S',
        '%m-%d %H:%M:%S',
        '%d %H:%M:%S',
        '%H:%M:%S')

    def __init__(self, _id, service):
        self._id = _id
        self._service = service
        self._mutex = threading.RLock()  # reentrant locker
        self._item = 0  # in case of multiple item like more than a single strategy or trader
        self._refresh = 0
        self._percent = False  # display percent for tables
        self._group = False    # group by (depending of the view)
        self._datetime_format = View.DATETIME_FORMATS[0]

    @property
    def id(self):
        return self._id

    @property
    def service(self):
        return self._service

    def create(self):
        Terminal.inst().create_content_view(self._id)

    def destroy(self):
        Terminal.inst().destroy_content_view(self._id)

    def set_title(self, title):
        Terminal.inst().set_title(self._id, title)

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def need_refresh(self):
        if self._refresh < 0:
            return False

        return time.time() - self._refresh >= self.REFRESH_RATE

    def style(self):
        return Terminal.inst().style()
    
    def refresh(self):
        pass

    def is_active(self):
        return Terminal.inst().is_active(self._id)

    def width(self):
        vt = Terminal.inst().view(self._id)
        return vt.width if vt else 0

    def height(self):
        vt = Terminal.inst().view(self._id)
        return vt.height if vt else 0

    def scroll_row(self, n):
        pass

    def scroll_col(self, n):
        pass

    def on_key_pressed(self, key):
        if key == 'KEY_SPREVIOUS':
            self.prev_item()
        elif key == 'KEY_SNEXT':
            self.next_item()

    def on_char(self, char):
        pass

    def count_items(self):
        return 0

    def prev_item(self):
        self._item -= 1
        if self._item < 0:
            self._item = self.count_items() - 1
            if self._item < 0:
                self._item = 0

        self._refresh = 0  # force refresh

    def next_item(self):
        self._item += 1
        if self._item >= self.count_items():
            self._item = 0

        self._refresh = 0  # force refresh

    def toggle_percent(self):
        self._percent = not self._percent
        self._refresh = 0  # force refresh

    def toggle_group(self):
        self._group = not self._group
        self._refresh = 0  # force refresh

    def toggle_datetime_format(self):
        idx = View.DATETIME_FORMATS.index(self._datetime_format)
        idx += 1

        if idx >= len(View.DATETIME_FORMATS):
            self._datetime_format = View.DATETIME_FORMATS[0]
        else:
            self._datetime_format = View.DATETIME_FORMATS[idx]

        self._refresh = 0  # force refresh
