# @date 2022-09-14
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# FTX Websocket connector.

import traceback
import threading
import json
import logging

from autobahn.twisted.websocket import WebSocketClientFactory, WebSocketClientProtocol, connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory

from monitor.service import MonitorService

logger = logging.getLogger('siis.ftx.ws')
error_logger = logging.getLogger('siis.error.ftx.ws')
traceback_logger = logging.getLogger('siis.traceback.ftx.ws')


class FTXClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        subscriptions = self.factory.subscriptions
        if subscriptions:
            for subscription, pair in subscriptions.items():
                for p in pair:
                    data = {
                        'op': 'subscribe',
                        'channel': subscription,
                        'market': p
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

    # def connectionLost(self, reason):
    #     WebSocketClientProtocol.connectionLost(self, reason)
    #     error_logger.error("FTX WS public connection lost: Reason is {}".format(reason))


class FTXPrivateClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        # login
        payload = json.dumps(self.factory.token, ensure_ascii=False).encode('utf8')
        self.sendMessage(payload, isBinary=False)

        # subscriptions
        subscriptions = self.factory.subscriptions
        if subscriptions:
            for subscription in subscriptions:
                data = {
                    'op': 'subscribe',
                    'channel': subscription,
                    # 'subscription': {
                    #     'name': subscription,
                    #     'token': self.factory.token
                    # }
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

    # def connectionLost(self, reason):
    #     WebSocketClientProtocol.connectionLost(self, reason)
    #     error_logger.error("FTX WS private connection lost: Reason is {}".format(reason))


class FTXReconnectingClientFactory(ReconnectingClientFactory):
    """
    Finally manage at watcher level (reconnect = False)
    """

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 2  # 20

    maxRetries = 3  # 30


class FTXClientFactory(WebSocketClientFactory, FTXReconnectingClientFactory):

    def __init__(self, *args, subscription=None, pair=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

        # active pairs
        self.subscriptions = {}

        if subscription and pair:
            self.subscriptions[subscription] = set(pair)

    protocol = FTXClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return FTXClientProtocol(self)


class FTXPrivateClientFactory(WebSocketClientFactory, FTXReconnectingClientFactory):

    def __init__(self, *args, token, subscription=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

        self.subscriptions = set()
        self.token = token

        if subscription:
            self.subscriptions.add(subscription)

    protocol = FTXPrivateClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        if not self.reconnect:
            return

        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return FTXPrivateClientProtocol(self)


class FTXSocketManager(threading.Thread):
    STREAM_URL = 'wss://ftx.com/ws'
    PRIVATE_STREAM_URL = 'wss://ftx.com/ws'

    def __init__(self):  # client
        """Initialise the FTXSocketManager"""
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
        factory = FTXClientFactory(factory_url, subscription=subscription, pair=pair)
        factory.base_client = self
        factory.protocol = FTXClientProtocol
        factory.callback = callback
        factory.reconnect = False  # True
        self.factories[id_] = factory
        reactor.callFromThread(self.add_connection, id_, factory_url)

    def _start_private_socket(self, id_, token, subscription, callback):
        if id_ in self._private_conns:
            return False

        factory_url = self.PRIVATE_STREAM_URL
        factory = FTXPrivateClientFactory(factory_url, token=token, subscription=subscription)
        factory.base_client = self
        factory.protocol = FTXPrivateClientProtocol
        factory.callback = callback
        factory.reconnect = False  # True
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

        hostname = url[6:].split('/')[0]

        factory = self.factories[id_]
        options = ssl.optionsForClientTLS(hostname=hostname)  # for TLS SNI
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

        hostname = url[6:].split('/')[0]

        factory = self.factories[id_]
        options = ssl.optionsForClientTLS(hostname=hostname)  # for TLS SNI
        self._private_conns[id_] = connectWS(factory, options)

    def send_subscribe(self, id_, subscription, pair):
        try:
            factory = self.factories[id_]

            if subscription and pair and factory:
                if subscription not in factory.subscriptions:
                    factory.subscriptions[subscription] = set()

                factory.subscriptions[subscription].update(pair)

                if factory.protocol_instance:
                    for p in pair:
                        data = {
                            'op': 'subscribe',
                            'channel': subscription,
                            'market': p
                        }

                        payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                        factory.protocol_instance.sendMessage(payload, isBinary=False)

        except Exception as e:
            error_logger.error("%s : %s" % (subscription, repr(e)))
            traceback_logger.error(traceback.format_exc())

    def send_unsubscribe(self, id_, subscription, pair):
        try:
            factory = self.factories[id_]

            if subscription and pair and factory:
                if subscription not in factory.subscriptions:
                    factory.subscriptions[subscription] = set()

                factory.subscriptions[subscription] = factory.subscriptions[subscription].difference(pair)

                if factory.protocol_instance:
                    for p in pair:
                        data = {
                            'op': 'unsubscribe',
                            'channel': subscription,
                            'market': p
                        }

                        payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                        factory.protocol_instance.sendMessage(payload, isBinary=False)

        except Exception as e:
            error_logger.error("%s : %s" % (subscription, repr(e)))
            traceback_logger.error(traceback.format_exc())

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
        self._conns[conn_key].factory.reconnect = False
        # self._conns[conn_key].factory = WebSocketClientFactory(self.STREAM_URL)
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
        self._private_conns[conn_key].factory.reconnect = False
        # self._private_conns[conn_key].factory = WebSocketClientFactory(self.PRIVATE_STREAM_URL)
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


class WssClient(FTXSocketManager):
    """
    Websocket client for FTX.

    Public sockets are grouped by event (trade, ticker, spread, book),
    then adding a subscription only create one socket per type, and share the same
    across the different instruments pairs.

    Private socket are grouped by event (fills, orders) and are for any instruments pairs.

    This mean a common case will use 2 privates socket plus from 1 to 4 public sockets.
    """

    ###########################################################################
    # FTX commands
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

        if id_ not in self._conns:
            self._start_socket(id_, subscription, pair, callback)
        else:
            reactor.callFromThread(self.send_subscribe, id_, subscription, pair)

    def unsubscribe_public(self, subscription, pair):
        id_ = "_".join([subscription])

        if id_ in self._conns:
            reactor.callFromThread(self.send_unsubscribe, id_, subscription, pair)

    def subscribe_private(self, token, subscription, callback):
        id_ = "_".join([subscription])

        return self._start_private_socket(id_, token, subscription, callback)

    # def request(self, request, callback, **kwargs):
    #     id_ = "_".join([request['event'], request['type']])
    #     return self._start_private_socket(id_, request, callback, private=True)


# order book misc
#         self._orderbook_timestamps: DefaultDict[str, float] = defaultdict(float)
#         self._orderbook_update_events.clear()
#         self._orderbooks: DefaultDict[str, Dict[str, DefaultDict[float, float]]] = defaultdict(
#             lambda: {side: defaultdict(float) for side in {'bids', 'asks'}})
#         self._orderbook_timestamps.clear()
#         self._last_received_orderbook_data_at: float = 0.0

#     def _reset_orderbook(self, market: str) -> None:
#         if market in self._orderbooks:
#             del self._orderbooks[market]
#         if market in self._orderbook_timestamps:
#             del self._orderbook_timestamps[market]

#     def get_orderbook(self, market: str) -> Dict[str, List[Tuple[float, float]]]:
#         subscription = {'channel': 'orderbook', 'market': market}
#         if subscription not in self._subscriptions:
#             self._subscribe(subscription)
#         if self._orderbook_timestamps[market] == 0:
#             self.wait_for_orderbook_update(market, 5)
#         return {
#             side: sorted(
#                 [(price, quantity) for price, quantity in list(self._orderbooks[market][side].items())
#                  if quantity],
#                 key=lambda order: order[0] * (-1 if side == 'bids' else 1)
#             )
#             for side in {'bids', 'asks'}
#         }

#     def get_orderbook_timestamp(self, market: str) -> float:
#         return self._orderbook_timestamps[market]

#     def wait_for_orderbook_update(self, market: str, timeout: Optional[float]) -> None:
#         subscription = {'channel': 'orderbook', 'market': market}
#         if subscription not in self._subscriptions:
#             self._subscribe(subscription)
#         self._orderbook_update_events[market].wait(timeout)

#     def _handle_orderbook_message(self, message: Dict) -> None:
#         market = message['market']
#         subscription = {'channel': 'orderbook', 'market': market}
#         if subscription not in self._subscriptions:
#             return
#         data = message['data']
#         if data['action'] == 'partial':
#             self._reset_orderbook(market)
#         for side in {'bids', 'asks'}:
#             book = self._orderbooks[market][side]
#             for price, size in data[side]:
#                 if size:
#                     book[price] = size
#                 else:
#                     del book[price]
#             self._orderbook_timestamps[market] = data['time']
#         checksum = data['checksum']
#         orderbook = self.get_orderbook(market)
#         checksum_data = [
#             ':'.join([f'{float(order[0])}:{float(order[1])}' for order in (bid, offer) if order])
#             for (bid, offer) in zip_longest(orderbook['bids'][:100], orderbook['asks'][:100])
#         ]
#
#         computed_result = int(zlib.crc32(':'.join(checksum_data).encode()))
#         if computed_result != checksum:
#             self._last_received_orderbook_data_at = 0
#             self._reset_orderbook(market)
#             self._unsubscribe({'market': market, 'channel': 'orderbook'})
#             self._subscribe({'market': market, 'channel': 'orderbook'})
#         else:
#             self._orderbook_update_events[market].set()
#             self._orderbook_update_events[market].clear()

#     def _on_message(self, ws, raw_message: str) -> None:
#         message = json.loads(raw_message)
#         message_type = message['type']
#         if message_type in {'subscribed', 'unsubscribed'}:
#             return
#         elif message_type == 'info':
#             if message['code'] == 20001:
#                 return self.reconnect()
#         elif message_type == 'error':
#             raise Exception(message)
#         channel = message['channel']
#
#         if channel == 'orderbook':
#             self._handle_orderbook_message(message)
#         elif channel == 'fills':
#             self._handle_fills_message(message)
#         elif channel == 'orders':
#             self._handle_orders_message(message)
