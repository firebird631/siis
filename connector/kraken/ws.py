# @date 2020-01-31
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Kraken Websocket connector.

import traceback
import threading
import json
import hmac
import hashlib
import logging

from autobahn.twisted.websocket import WebSocketClientFactory, WebSocketClientProtocol, connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.error import ReactorAlreadyRunning

from monitor.service import MonitorService

error_logger = logging.getLogger('siis.error.kraken.ws')
traceback_logger = logging.getLogger('siis.traceback.kraken.ws')
logger = logging.getLogger('siis.kraken.ws')


class KrakenClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        subscriptions = self.factory.subscriptions
        if subscriptions:
            for subscription, pair in subscriptions.items():
                if pair:
                    data = {
                        'event': 'subscribe',
                        'subscription': {
                            'name': subscription
                        },
                        'pair': list(pair)
                    }

                    payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                    self.sendMessage(payload, isBinary=False)

        # reset the delay after reconnecting
        self.factory.resetDelay()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                payload_obj = json.loads(payload.decode('utf8'))
            except ValueError:
                pass
            else:
                try:
                    self.factory.callback(payload_obj)
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())


class KrakenPrivateClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        subscriptions = self.factory.subscriptions
        if subscriptions:
            for subscription in subscriptions:
                data = {
                    'event': 'subscribe',
                    'subscription': {
                        'name': subscription,
                        'token': self.factory.token
                    }
                }

                payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                self.sendMessage(payload, isBinary=False)

        # reset the delay after reconnecting
        self.factory.resetDelay()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                payload_obj = json.loads(payload.decode('utf8'))
            except ValueError:
                pass
            else:
                try:
                    self.factory.callback(payload_obj)
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())


class KrakenReconnectingClientFactory(ReconnectingClientFactory):

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 20

    maxRetries = 30


class KrakenClientFactory(WebSocketClientFactory, KrakenReconnectingClientFactory):

    def __init__(self, *args, subscription=None, pair=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

        # active pairs
        self.subscriptions = {}

        if subscription and pair:
            self.subscriptions[subscription] = set(pair)

    protocol = KrakenClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return KrakenClientProtocol(self)


class KrakenPrivateClientFactory(WebSocketClientFactory, KrakenReconnectingClientFactory):

    def __init__(self, *args, token, subscription=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

        self.subscriptions = set()
        self.token = token

        if subscription:
            self.subscriptions.add(subscription)

    protocol = KrakenPrivateClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return KrakenPrivateClientProtocol(self)


class KrakenSocketManager(threading.Thread):

    STREAM_URL = 'wss://ws.kraken.com'
    PRIVATE_STREAM_URL = 'wss://ws-auth.kraken.com'

    def __init__(self):  # client
        """Initialise the KrakenSocketManager"""
        threading.Thread.__init__(self)
        self.factories = {}
        self._connected_event = threading.Event()
        self._conns = {}
        self._private_conns = {}
        self._user_timer = None
        self._user_listen_key = None
        self._user_callback = None

    def _start_socket(self, id_, subscription, pair, callback):
        if id_ in self._conns:
            return False

        factory_url = self.STREAM_URL
        factory = KrakenClientFactory(factory_url, subscription=subscription, pair=pair)
        factory.base_client = self
        factory.protocol = KrakenClientProtocol
        factory.callback = callback
        factory.reconnect = True
        self.factories[id_] = factory
        reactor.callFromThread(self.add_connection, id_, factory_url)

    def _start_private_socket(self, id_, token, subscription, callback):
        if id_ in self._private_conns:
            return False

        factory_url = self.PRIVATE_STREAM_URL
        factory = KrakenPrivateClientFactory(factory_url, token=token, subscription=subscription)
        factory.base_client = self
        factory.protocol = KrakenPrivateClientProtocol
        factory.callback = callback
        factory.reconnect = True
        self.factories[id_] = factory
        reactor.callFromThread(self.add_private_connection, id_, factory_url)

    def add_connection(self, id_, url):
        """
        Convenience function to connect and store the resulting
        connector.
        """
        # factory = self.factories[id_]
        # context_factory = ssl.ClientContextFactory()
        # self._conns[id_] = connectWS(factory, context_factory)

        if not url.startswith("wss://"):
            raise ValueError("expected wss:// URL prefix")

        hostname = url[6:]

        factory = self.factories[id_]
        options = ssl.optionsForClientTLS(hostname=hostname) # for TLS SNI
        self._conns[id_] = connectWS(factory, options)

    def add_private_connection(self, id_, url):
        """
        Convenience function to connect and store the resulting
        connector.
        """
        # factory = self.factories[id_]
        # context_factory = ssl.ClientContextFactory()
        # self._conns[id_] = connectWS(factory, context_factory)

        if not url.startswith("wss://"):
            raise ValueError("expected wss:// URL prefix")

        hostname = url[6:]

        factory = self.factories[id_]
        options = ssl.optionsForClientTLS(hostname=hostname) # for TLS SNI
        self._private_conns[id_] = connectWS(factory, options)

    def send_subscribe(self, id_, subscription, pair):
        factory = self.factories[id_]

        if subscription and pair and factory:
            if not subscription in factory.subscriptions:
                factory.subscriptions[subscription] = set()

            factory.subscriptions[subscription].update(pair)

            if factory.protocol_instance:
                data = {
                    'event': 'subscribe',
                    'subscription': {
                        'name': subscription
                    },
                    'pair': pair
                }

                factory.protocol_instance.sendMessage(data, isBinary=False)

    def send_unsubscribe(self, id_, subscription, pair):
        factory = self.factories[id_]

        if subscription and pair and factory:
            if not subscription in factory.subscriptions:
                factory.subscriptions[subscription] = set()

            factory.subscriptions[subscription] = factory.subscriptions[subscription].difference(pair)

            if factory.protocol_instance:
                data = {
                    'event': 'unsubscribe',
                    'subscription': {
                        'name': subscription
                    },
                    'pair': pair
                }

                factory.protocol_instance.sendMessage(data, isBinary=False)

    def stop_socket(self, conn_key):
        """Stop a websocket given the connection key

        Parameters
        ----------
        conn_key : str
            Socket connection key

        Returns
        -------
        str, bool
            connection key string if successful, False otherwise
        """
        if conn_key not in self._conns:
            return

        # disable reconnecting if we are closing
        self._conns[conn_key].factory = WebSocketClientFactory(self.STREAM_URL)
        self._conns[conn_key].disconnect()
        del self._conns[conn_key]

    def stop_private_socket(self, conn_key):
        """Stop a websocket given the connection key

        Parameters
        ----------
        conn_key : str
            Socket connection key

        Returns
        -------
        str, bool
            connection key string if successful, False otherwise
        """
        if conn_key not in self._private_conns:
            return

        # disable reconnecting if we are closing
        self._private_conns[conn_key].factory = WebSocketClientFactory(self.PRIVATE_STREAM_URL)
        self._private_conns[conn_key].disconnect()
        del self._private_conns[conn_key]

    def run(self):
        MonitorService.use_reactor(installSignalHandlers=False)

    def close(self):
        """Close all connections
        """
        keys = set(self._conns.keys())
        for key in keys:
            self.stop_socket(key)
        self._conns = {}

        keys = set(self._private_conns.keys())
        for key in keys:
            self.stop_private_socket(key)
        self._private_conns = {}


class WssClient(KrakenSocketManager):
    """
    Websocket client for Kraken.
    
    Public sockets are grouped by event (trade, ticker, spread, book),
    then adding a subscription only create one socket per type, and share the same
    accross the differents instruments pairs.

    Private socket are grouped by event (ownTrades, myOrders) and are for any instruments pairs.

    This mean a common case will use 2 privates socket plus from 1 to 4 public sockets.

    # @todo request private might use the myOrders socket
    # @todo add unsubscribe_public
    """

    ###########################################################################
    # Kraken commands
    ###########################################################################

    def __init__(self, key=None, secret=None, nonce_multiplier=1.0):  # client
        super().__init__()
        self.key = key
        self.secret = secret
        self.nonce_multiplier = nonce_multiplier

    def stop(self):
        """Tries to close all connections and finally stops the reactor.
        Properly stops the program."""
        try:
            self.close()
        finally:
            MonitorService.release_reactor()

    def subscribe_public(self, subscription, pair, callback):
        id_ = "_".join([subscription])

        if not id_ in self.factories:
            self._start_socket(id_, subscription, pair, callback)
        else:
            reactor.callFromThread(self.send_subscribe, id_, subscription, pair)

    def unsubscribe_public(self, subscription, pair):
        id_ = "_".join([subscription])

        if id_ in self.factories:
            reactor.callFromThread(self.send_unsubscribe, id_, subscription, pair)

    def subscribe_private(self, token, subscription, callback):
        id_ = "_".join([subscription])

        return self._start_private_socket(id_, token, subscription, callback)

    # def request(self, request, callback, **kwargs):
    #     id_ = "_".join([request['event'], request['type']])
    #     return self._start_private_socket(id_, request, callback, private=True)
