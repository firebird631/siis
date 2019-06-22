# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# OHLC watcher querying on SIIS-DSS (siis datastore service)

import http.client
import urllib
import json
import time
import datetime

from watcher.watcher import Watcher
from watcher.author import Author
from watcher.position import Position
from notifier.signal import Signal

from config import config

from terminal.terminal import Terminal


class SiisOHLC(Watcher):
    """
    WebSocket based OHLC + volume + timestamp streaming client.
    """

    def __init__(self, service, name="ohlc.siis.com"):
        super().__init__(name, service)

        self._host = "siis.com"
        self._base_url = "/api/v1/"
        self._end_point = "ohlc/"
        self._connected = False
        self._checkout = False

        # identity
        identity = service.identity(self._name)
        if identity:
            self.__api_key = identity.get('api-key')
            self._host = identity.get('host')

    def connect(self):
        super().connect()

        # self._conn = http.client.HTTPSConnection(self._host, timeout=10)

        # var = {
        #   'pretty': 'false',
        #   'token': self.__apitoken
        # }

        # url = self._base_url + '?' + urllib.parse.urlencode(var)
        # self._conn.request("GET", url)

        # response = self._conn.getresponse()   
        # data = response.read()

        # if response.status == 200:
        #   self._connected = True
        # else:
        #   self._connected = False

    @Watcher.mutexed
    def checkout(self):
        self._checkout = True

    def pre_run(self):
        super().pre_run()

        if self._connected:
            self.checkout()

    def post_run(self):
        super().post_run()

    def disconnect(self):
        super().disconnect()
        self._conn = None
        self._connected = False
        self._checkout = False

    def update(self):
        if not super().update():
            return

        if not self._connected:
            # try reconnect
            time.sleep(0.5)
            self.connect()
            return

        if not self._checkout:
            # need checkout performed before update
            self.checkout()
            if not self._checkout:
                return

    def post_update(self):
        super().post_update()

        # ok for social but not if websocket
        time.sleep(0.5)
