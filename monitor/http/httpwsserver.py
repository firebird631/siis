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
from autobahn.websocket.types import ConnectionDeny

from twisted.python import log
from twisted.internet import reactor, ssl

from monitor.service import MonitorService
from monitor.http.httprestserver import HttpRestServer, check_ws_auth_token

import logging
logger = logging.getLogger('siis.monitor.httpwsserver')
error_logger = logging.getLogger('siis.error.monitor.httpwsserver')
traceback_logger = logging.getLogger('siis.traceback.monitor.httpwsserver')


class ServerProtocol(WebSocketServerProtocol):
    connections = list()
    monitor_service = None

    def onConnect(self, request):
        logger.debug("Client connecting: {0}".format(request.peer))

        if not check_ws_auth_token(ServerProtocol.monitor_service, request):
            raise ConnectionDeny(4000, reason="Invalid auth")
        else:
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


class AllowedIPOnlyFactory(WebSocketServerFactory):

    def buildProtocol(self, addr):
        if HttpRestServer.DENIED_IPS and addr.host in HttpRestServer.DENIED_IPS:
            return None

        if HttpRestServer.ALLOWED_IPS and addr.host in HttpRestServer.ALLOWED_IPS:
            return super().buildProtocol(addr)

        return None


class HttpWebSocketServer(object):

    def __init__(self, host, port, monitor_service):
        self._listener = None

        self._host = host
        self._port = port

        self._monitor_service = monitor_service

        self._mutex = threading.RLock()

    def start(self):
        # factory = WebSocketServerFactory("ws://%s:%i" % (self._host, self._port))
        factory = AllowedIPOnlyFactory("ws://%s:%i" % (self._host, self._port))
        factory.protocol = ServerProtocol
        factory.protocol.monitor_service = self._monitor_service
        factory.setProtocolOptions(maxConnections=5)

        MonitorService.ref_reactor()
        self._listener = reactor.listenTCP(self._port, factory)
        # self._listener = reactor.listenSSL(self._port, factory, contextFactory)

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
