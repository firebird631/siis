# @date 2018-08-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Dummy watcher implementation

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watcher.service import WatcherService

import time

from watcher.watcher import Watcher
from common.signal import Signal


class DummyWatcher(Watcher):
    """
    Dummy watcher used mostly for backtesting.
    """

    def __init__(self, service: WatcherService, name: str, watcher_type: int = Watcher.WATCHER_ALL):
        super().__init__(name, service, watcher_type)

        self._connected = False

    def connect(self):
        self._connected = False
        self._ready = False

        from database.database import Database
        Database.inst().load_market_list(self.service, self.name)

    def disconnect(self):
        self._connected = False
        self._ready = False

    @property
    def connected(self) -> bool:
        return self._connected

    def update(self):
        if not super().update():
            return False

        #
        # signals processing
        #

        count = 0

        while self._signals:
            signal = self._signals.popleft()

            # only on live mode, because in backtesting watchers are dummies
            if signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_MARKET_LIST_DATA:
                    with self._mutex:
                        # only the symbol
                        self._available_instruments = set([x[0] for x in signal.data])
                        self._watched_instruments = set([x[0] for x in signal.data])

                        self._connected = True
                        self._ready = True

                    # now connected and signal
                    self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

            if count > 10:
                # no more than per loop
                break

        return True

    def post_update(self):
        super().post_update()

        # don't waste the cpu
        time.sleep(0.5)
