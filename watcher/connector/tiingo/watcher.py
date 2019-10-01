# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# tiingo.co watcher implementation

import math
import urllib
import json
import time
import os.path
import traceback
import requests

from watcher.watcher import Watcher
from notifier.signal import Signal

from connector.tiingo import Connector
from terminal.terminal import Terminal

from instrument.instrument import Instrument, Candle
from database.database import Database

from trader.market import Market

import logging
logger = logging.getLogger('siis.watcher.tiingo')
error_logger = logging.getLogger('siis.error.watcher.tiingo')


class TiingoWatcher(Watcher):
    """
    Tiingo watcher get price and volumes of instruments in live mode throught REST API + WS.
    """

    DEFAULT_MAX_QUERIES_PER_MIN = 5  # default for free account

    def __init__(self, service):
        super().__init__("tiingo.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None

    def connect(self):
        super().connect()

        try:
            self.lock()

            identity = self.service.identity(self._name)
            self._subscriptions = []  # reset previous list

            if identity:
                self._connector = Connector(self.service, identity.get('api-key'), identity.get('host'))

                instruments = []

                if '*' in self.configured_symbols():
                    # not permit there is thousand of symbols
                    self._available_instruments = []
                else:
                    instruments = self.configured_symbols()

                # susbcribe for symbols
                for symbol in instruments:
                    self._watched_instruments.add(symbol)

                self._ready = True

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

            self._connector = None
        finally:
            self.unlock()

        if self._ready and self._connector and self._connector.connected:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._connector:
                sefl._connector.disconnect()
                self._connector = None

            self._ready = False

        except Exception:
            error_logger.error(traceback.format_exc())
        finally:
            self.unlock()

    def pre_update(self):
        super().pre_update()

        if self._connector is None:
            self.connect()

            if not self.connected:
                # retry in 2 second
                time.sleep(2.0)

            return

    def update(self):
        if not super().update():
            return False

        if self._connector is None or not self._connector.connected:
            return False

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0001)

    def post_run(self):
        super().post_run()
