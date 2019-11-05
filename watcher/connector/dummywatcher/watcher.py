# @date 2018-08-11
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Dummy watcher implementation

import json
import time

from watcher.watcher import Watcher
from common.signal import Signal

from terminal.terminal import Terminal


class DummyWatcher(Watcher):
    """
    Dummy watcher used mostly for backtesting.
    """

    def __init__(self, service, name, watcher_type=Watcher.WATCHER_ALL):
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
    def connected(self):
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
                    self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

            if count > 10:
                # no more than per loop
                break

        return True

    def post_update(self):
        super().post_update()

        # don't waste the cpu
        time.sleep(0.5)
