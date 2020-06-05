# @date 2020-05-24
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# http websocket server

import json
import time, datetime
import tempfile, os, posix
import threading
import traceback
import collections
import base64, hashlib

import asyncio

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory

from twisted.python import log
from twisted.internet import reactor, ssl

from monitor.service import MonitorService

import logging
logger = logging.getLogger('siis.monitor.httpwsserver')
error_logger = logging.getLogger('siis.error.monitor.httpwsserver')
traceback_logger = logging.getLogger('siis.traceback.monitor.httpwsserver')


class ServerProtocol(WebSocketServerProtocol):
    connections = list()

    def onConnect(self, request):
        logger.debug("Client connecting: {0}".format(request.peer))
        self.connections.append(self)

    def onOpen(self):
        logger.debug("WebSocket connection open")

    def onMessage(self, payload, isBinary):
        pass

    def onClose(self, wasClean, code, reason):
        logger.debug("WebSocket connection closed: {0}".format(reason))
        self.connections.remove(self)

    @classmethod
    def broadcast_message(cls, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf8')
        for c in set(cls.connections):
            reactor.callFromThread(cls.sendMessage, c, payload)

    @classmethod
    def close_all(cls, data):
        payload = json.dumps({'reason': "bye"}, ensure_ascii=False).encode('utf8')
        for c in set(cls.connections):
            reactor.callFromThread(cls.sendClose, c, payload)


class HttpWebSocketServer(object):

    def __init__(self, host, port):
        self._server = None
        self._listener = None

        self._host = host
        self._port = port

        self._mutex = threading.RLock()

    def start(self):
        factory = WebSocketServerFactory("ws://%s:%i" % (self._host, self._port))
        factory.protocol = ServerProtocol
        factory.setProtocolOptions(maxConnections=5)

        MonitorService.ref_reactor()
        self._listener = reactor.listenTCP(self._port, factory)

        if self._listener:
            MonitorService.set_reactor(installSignalHandlers=False)

    def publish(self, stream_category, stream_group, stream_name, content):
        # insert category, group and stream name
        content['c'] = stream_category
        content['g'] = stream_group
        content['s'] = stream_name

        ServerProtocol.broadcast_message(content)

    def stop(self):
        if self._listener:
            self._listener.stopListening()
            self._listener = None

            MonitorService.release_reactor()
