# @date 2020-01-31
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Binance Websocket connector.

import json
import threading
import traceback

from autobahn.twisted.websocket import WebSocketClientFactory, WebSocketClientProtocol, connectWS
from twisted.internet import ssl, reactor
from twisted.internet.protocol import ReconnectingClientFactory

from connector.binance.client import Client
from monitor.service import MonitorService

import logging
logger = logging.getLogger('siis.connector.binance.ws')
error_logger = logging.getLogger('siis.error.connector.binance.ws')
traceback_logger = logging.getLogger('siis.traceback.connector.binance.ws')


class BinanceClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        subscriptions = self.factory.subscriptions
        if subscriptions:
            params = []
            rid = 1

            for subscription, pair in subscriptions.items():
                if pair:
                    params += ["%s@%s" % (p.lower(), subscription) for p in pair]
                # else:
                #     params.append(subscription)

            data = {
                "method": "SUBSCRIBE",
                "params": params,
                "id": rid
            }

            if params:
                logger.debug("onConnect %s" % data)

                payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                self.sendMessage(payload, isBinary=False)
            else:
                logger.debug("onConnect %s" % '/'.join(subscriptions.keys()))

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
    #     subs = '/'.join(self.factory.subscriptions.keys())
    #     error_logger.error("Binance WS public connection lost for %s: Reason is %s" % (subs, reason))


class BinanceReconnectingClientFactory(ReconnectingClientFactory):

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 10

    maxRetries = 30


class BinanceClientFactory(WebSocketClientFactory, BinanceReconnectingClientFactory):

    protocol = BinanceClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def __init__(self, *args, subscription=None, pair=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None

        # active pairs
        self.subscriptions = {}

        if subscription:
            self.subscriptions[subscription] = set(pair or [])

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
        return BinanceClientProtocol(self)


class BinanceSocketManager(threading.Thread):
    """
    Binance spot and futures WS socket and subscription manager.

    @todo Reuse the same connection for multiplex to avoid multiple sockets (have to do like in the kraken WS).
        Also have to be sure to stay connected after 24h.
    """

    STREAM_URL = 'wss://stream.binance.com:9443/'
    FUTURES_STREAM_URL = 'wss://fstream.binance.com/'
    # FUTURES_STREAM_URL = 'wss://fstream3.binance.com'

    WEBSOCKET_DEPTH_5 = '5'
    WEBSOCKET_DEPTH_10 = '10'
    WEBSOCKET_DEPTH_20 = '20'

    DEFAULT_USER_TIMEOUT = 30 * 60  # 30 minutes

    def __init__(self, client, user_timeout=DEFAULT_USER_TIMEOUT, futures=False):
        """Initialise the BinanceSocketManager

        :param client: Binance API client
        :type client: binance.Client
        :param user_timeout: Custom websocket timeout
        :type user_timeout: int

        """
        threading.Thread.__init__(self, name="binance-ws")

        self._next_id = 2  # 1 is for connect
        self.factories = {}

        self._conns = {}
        self._user_timer = None
        self._user_listen_key = None
        self._user_callback = None
        self._client = client
        self._user_timeout = user_timeout

        self._future = futures
        self._url = BinanceSocketManager.FUTURES_STREAM_URL if futures else BinanceSocketManager.STREAM_URL

    def _start_socket(self, id_, path, callback, prefix='ws/', subscription=None, pair=None):
        try:
            if id_ in self._conns:  # path in self._conns:
                return False

            factory_url = self._url + prefix + path
            factory = BinanceClientFactory(factory_url, subscription=subscription, pair=pair)
            factory.base_client = self
            factory.protocol = BinanceClientProtocol
            factory.callback = callback
            factory.reconnect = True
            self.factories[id_] = factory
            context_factory = ssl.ClientContextFactory()

            # self._conns[path] = reactor.connectSSL(factory_url, 443 if self._future else 9443, factory,
            #                                        context_factory, 5.0)
            # self._conns[path] = connectWS(factory, context_factory)
            self._conns[id_] = connectWS(factory, context_factory)
        except Exception as e:
            logger.error(repr(e))

        return path

    def start_depth_socket(self, symbol, callback, depth=None):
        """Start a websocket for symbol market depth returning either a diff or a partial book

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#partial-book-depth-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :param depth: optional Number of depth entries to return, default None. If passed returns a partial book instead of a diff
        :type depth: str

        :returns: connection key string if successful, False otherwise

        Partial Message Format

        .. code-block:: python

            {
                "lastUpdateId": 160,  # Last update ID
                "bids": [             # Bids to be updated
                    [
                        "0.0024",     # price level to be updated
                        "10",         # quantity
                        []            # ignore
                    ]
                ],
                "asks": [             # Asks to be updated
                    [
                        "0.0026",     # price level to be updated
                        "100",        # quantity
                        []            # ignore
                    ]
                ]
            }


        Diff Message Format

        .. code-block:: python

            {
                "e": "depthUpdate", # Event type
                "E": 123456789,     # Event time
                "s": "BNBBTC",      # Symbol
                "U": 157,           # First update ID in event
                "u": 160,           # Final update ID in event
                "b": [              # Bids to be updated
                    [
                        "0.0024",   # price level to be updated
                        "10",       # quantity
                        []          # ignore
                    ]
                ],
                "a": [              # Asks to be updated
                    [
                        "0.0026",   # price level to be updated
                        "100",      # quantity
                        []          # ignore
                    ]
                ]
            }

        """
        socket_name = symbol.lower() + '@depth'
        if depth and depth != '1':
            socket_name = '{}{}'.format(socket_name, depth)
        return self._start_socket(socket_name, socket_name, callback, subscription='depth', pair=symbol.lower())

    def start_kline_socket(self, symbol, callback, interval=Client.KLINE_INTERVAL_1MINUTE):
        """Start a websocket for symbol kline data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#klinecandlestick-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function
        :param interval: Kline interval, default KLINE_INTERVAL_1MINUTE
        :type interval: str

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "kline",                   # event type
                "E": 1499404907056,             # event time
                "s": "ETHBTC",                  # symbol
                "k": {
                    "t": 1499404860000,         # start time of this bar
                    "T": 1499404919999,         # end time of this bar
                    "s": "ETHBTC",              # symbol
                    "i": "1m",                  # interval
                    "f": 77462,                 # first trade id
                    "L": 77465,                 # last trade id
                    "o": "0.10278577",          # open
                    "c": "0.10278645",          # close
                    "h": "0.10278712",          # high
                    "l": "0.10278518",          # low
                    "v": "17.47929838",         # volume
                    "n": 4,                     # number of trades
                    "x": false,                 # whether this bar is final
                    "q": "1.79662878",          # quote volume
                    "V": "2.34879839",          # volume of active buy
                    "Q": "0.24142166",          # quote volume of active buy
                    "B": "13279784.01349473"    # can be ignored
                    }
            }
        """
        socket_name = '{}@kline_{}'.format(symbol.lower(), interval)
        return self._start_socket(socket_name, socket_name, callback, subscription='kline', pair=symbol.lower())

    def start_miniticker_socket(self, callback, update_time=1000):
        """Start a miniticker websocket for all trades

        This is not in the official Binance api docs, but this is what
        feeds the right column on a ticker page on Binance.

        :param callback: callback function to handle messages
        :type callback: function
        :param update_time: time between callbacks in milliseconds, must be 1000 or greater
        :type update_time: int

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            [
                {
                    'e': '24hrMiniTicker',  # Event type
                    'E': 1515906156273,     # Event time
                    's': 'QTUMETH',         # Symbol
                    'c': '0.03836900',      # close
                    'o': '0.03953500',      # open
                    'h': '0.04400000',      # high
                    'l': '0.03756000',      # low
                    'v': '147435.80000000', # volume
                    'q': '5903.84338533'    # quote volume
                }
            ]
        """

        return self._start_socket('!miniTicker', '!miniTicker@arr@{}ms'.format(update_time), callback,
                                  subscription='!miniTicker')

    def start_trade_socket(self, symbol, callback):
        """Start a websocket for symbol trade data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#trade-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "trade",     # Event type
                "E": 123456789,   # Event time
                "s": "BNBBTC",    # Symbol
                "t": 12345,       # Trade ID
                "p": "0.001",     # Price
                "q": "100",       # Quantity
                "b": 88,          # Buyer order Id
                "a": 50,          # Seller order Id
                "T": 123456785,   # Trade time
                "m": true,        # Is the buyer the market maker?
                "M": true         # Ignore.
            }

        """
        return self._start_socket(symbol.lower() + '@trade', symbol.lower() + '@trade', callback,
                                  subscription='trade', pair=symbol.lower())

    def start_aggtrade_socket(self, symbol, callback):
        """Start a websocket for symbol trade data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#aggregate-trade-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "aggTrade",        # event type
                "E": 1499405254326,     # event time
                "s": "ETHBTC",          # symbol
                "a": 70232,             # aggregated tradeid
                "p": "0.10281118",      # price
                "q": "8.15632997",      # quantity
                "f": 77489,             # first breakdown trade id
                "l": 77489,             # last breakdown trade id
                "T": 1499405254324,     # trade time
                "m": false,             # whether buyer is a maker
                "M": true               # can be ignored
            }

        """
        return self._start_socket(symbol.lower() + '@aggTrade', symbol.lower() + '@aggTrade', callback,
                                  subscription='aggTrade', pair=symbol.lower())

    def start_symbol_ticker_socket(self, symbol, callback):
        """Start a websocket for a symbol's ticker data

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#individual-symbol-ticker-streams

        :param symbol: required
        :type symbol: str
        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            {
                "e": "24hrTicker",  # Event type
                "E": 123456789,     # Event time
                "s": "BNBBTC",      # Symbol
                "p": "0.0015",      # Price change
                "P": "250.00",      # Price change percent
                "w": "0.0018",      # Weighted average price
                "x": "0.0009",      # Previous day's close price
                "c": "0.0025",      # Current day's close price
                "Q": "10",          # Close trade's quantity
                "b": "0.0024",      # Best bid price
                "B": "10",          # Bid bid quantity
                "a": "0.0026",      # Best ask price
                "A": "100",         # Best ask quantity
                "o": "0.0010",      # Open price
                "h": "0.0025",      # High price
                "l": "0.0010",      # Low price
                "v": "10000",       # Total traded base asset volume
                "q": "18",          # Total traded quote asset volume
                "O": 0,             # Statistics open time
                "C": 86400000,      # Statistics close time
                "F": 0,             # First trade ID
                "L": 18150,         # Last trade Id
                "n": 18151          # Total number of trades
            }

        """
        return self._start_socket(symbol.lower() + '@ticker', symbol.lower() + '@ticker', callback,
                                  subscription='ticker', pair=symbol.lower())

    def start_ticker_socket(self, callback):
        """Start a websocket for all ticker data

        By default all markets are included in an array.

        https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#all-market-tickers-stream

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            [
                {
                    'F': 278610,
                    'o': '0.07393000',
                    's': 'BCCBTC',
                    'C': 1509622420916,
                    'b': '0.07800800',
                    'l': '0.07160300',
                    'h': '0.08199900',
                    'L': 287722,
                    'P': '6.694',
                    'Q': '0.10000000',
                    'q': '1202.67106335',
                    'p': '0.00494900',
                    'O': 1509536020916,
                    'a': '0.07887800',
                    'n': 9113,
                    'B': '1.00000000',
                    'c': '0.07887900',
                    'x': '0.07399600',
                    'w': '0.07639068',
                    'A': '2.41900000',
                    'v': '15743.68900000'
                }
            ]
        """
        return self._start_socket('!ticker@arr', '!ticker@arr', callback, subscription='!ticker@arr')

    def start_book_ticker_socket(self, callback):
        """Start a websocket for all book ticker data

        By default all markets are included in an array.

        https://binance-docs.github.io/apidocs/futures/en/#all-market-tickers-streams

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format

        .. code-block:: python

            [
                {
                    "u":400900217,     // order book updateId
                    "s":"BNBUSDT",     // symbol
                    "b":"25.35190000", // best bid price
                    "B":"31.21000000", // best bid qty
                    "a":"25.36520000", // best ask price
                    "A":"40.66000000"  // best ask qty
                }
            ]
        """
        return self._start_socket('!bookTicker', '!bookTicker', callback, prefix="stream?streams=",
                                  subscription='!bookTicker')

    # def start_multiplex_socket(self, streams, callback):
    #     """Start a multiplexed socket using a list of socket names.
    #     User stream sockets can not be included.
    #
    #     Symbols in socket name must be lowercase i.e bnbbtc@aggTrade, neobtc@ticker
    #
    #     Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
    #
    #     https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md
    #
    #     :param streams: list of stream names in lower case
    #     :type streams: list
    #     :param callback: callback function to handle messages
    #     :type callback: function
    #
    #     :returns: connection key string if successful, False otherwise
    #
    #     Message Format - see Binance API docs for all types
    #
    #     """
    #     stream_path = 'streams={}'.format('/'.join(streams))
    #     return self._start_socket('multiplex', stream_path, callback, subscription='stream?')

    def send_subscribe(self, id_, subscription, pair):
        try:
            factory = self.factories.get(id_)

            if subscription and pair and factory:
                if subscription not in factory.subscriptions:
                    factory.subscriptions[subscription] = set()

                factory.subscriptions[subscription].update(pair)

                # logger.info("send_subscribe %s / %s" % (id_, factory.protocol_instance))
                if factory.protocol_instance:
                    rid = self._next_id
                    self._next_id += 1
                    # logger.info("2 send_subscribe %s" % id_)

                    data = {
                        "method": "SUBSCRIBE",
                        "params": ["%s@%s" % (p.lower(), subscription) for p in pair],
                        "id": rid
                    }

                    # logger.info("send_subscribe %s" % data)
                    payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                    factory.protocol_instance.sendMessage(payload, isBinary=False)

        except Exception as e:
            error_logger.error("%s : %s" % (subscription, repr(e)))
            traceback_logger.error(traceback.format_exc())

    def send_unsubscribe(self, id_, subscription, pair):
        try:
            factory = self.factories.get(id_)

            if subscription and pair and factory:
                if subscription not in factory.subscriptions:
                    factory.subscriptions[subscription] = set()

                factory.subscriptions[subscription] = factory.subscriptions[subscription].difference(pair)

                if factory.protocol_instance:
                    rid = self._next_id
                    self._next_id += 1

                    data = {
                        "method": "UNSUBSCRIBE",
                        "params": ["%s@%s" % (p.lower(), subscription) for p in pair],
                        "id": rid
                    }

                    payload = json.dumps(data, ensure_ascii=False).encode('utf8')
                    factory.protocol_instance.sendMessage(payload, isBinary=False)

        except Exception as e:
            error_logger.error("%s : %s" % (subscription, repr(e)))
            traceback_logger.error(traceback.format_exc())

    def subscribe_public(self, subscription, pair, callback):
        id_ = "_".join([subscription])

        if id_ not in self._conns:
            # stream_path = 'streams={}'.format('/'.join(subscription))
            stream_path = 'streams={}'.format(subscription)
            return self._start_socket(subscription, stream_path, callback, subscription=subscription, pair=pair)
        else:
            reactor.callFromThread(self.send_subscribe, id_, subscription, pair)

    def unsubscribe_public(self, subscription, pair):
        id_ = "_".join([subscription])

        if id_ in self._conns:
            reactor.callFromThread(self.send_unsubscribe, id_, subscription, pair)

    def start_user_socket(self, callback):
        """Start a websocket for user data

        https://www.binance.com/restapipub.html#user-wss-endpoint

        :param callback: callback function to handle messages
        :type callback: function

        :returns: connection key string if successful, False otherwise

        Message Format - see Binance API docs for all types
        """
        # Get the user listen key
        user_listen_key = self._client.future_stream_get_listen_key() if self._future else self._client.stream_get_listen_key()
        # and start the socket with this specific key
        conn_key = self._start_user_socket(user_listen_key, callback)
        return conn_key

    def _start_user_socket(self, user_listen_key, callback):
        # With this function we can start a user socket with a specific key
        if self._user_listen_key:
            # cleanup any sockets with this key
            for conn_key in self._conns:
                if len(conn_key) >= 60 and conn_key[:60] == self._user_listen_key:
                    self.stop_socket(conn_key)
                    break
        self._user_listen_key = user_listen_key
        self._user_callback = callback
        conn_key = self._start_socket('user', self._user_listen_key, callback)
        if conn_key:
            # start timer to keep socket alive
            self._start_user_timer()

        return conn_key

    def _start_user_timer(self):
        self._user_timer = threading.Timer(self._user_timeout, self._keepalive_user_socket)
        self._user_timer.setDaemon(True)
        self._user_timer.start()

    def _keepalive_user_socket(self):
        try:
            user_listen_key = self._client.future_stream_get_listen_key() if self._future else self._client.stream_get_listen_key()
        except Exception as e:
            # very rare exception ConnectTimeout
            error_logger.error(repr(e))

            # assume unchanged
            user_listen_key = self._user_listen_key

        # check if they key changed and
        if user_listen_key != self._user_listen_key:
            # Start a new socket with the key received
            # `_start_user_socket` automatically cleanup open sockets
            # and starts timer to keep socket alive
            self._start_user_socket(user_listen_key, self._user_callback)
        else:
            # Restart timer only if the user listen key is not changed
            self._start_user_timer()

    def stop_socket(self, conn_key):
        """Stop a websocket given the connection key

        :param conn_key: Socket connection key
        :type conn_key: string

        :returns: connection key string if successful, False otherwise
        """
        if conn_key not in self._conns:
            return

        # disable reconnecting if we are closing
        self._conns[conn_key].factory = WebSocketClientFactory(self._url + 'tmp_path')
        self._conns[conn_key].disconnect()
        del self._conns[conn_key]

        # check if we have a user stream socket
        if len(conn_key) >= 60 and conn_key[:60] == self._user_listen_key:
            self._stop_user_socket()

    def _stop_user_socket(self):
        if not self._user_listen_key:
            return
        # stop the timer
        self._user_timer.cancel()
        self._user_timer = None
        self._user_listen_key = None

    def run(self):
        MonitorService.use_reactor(installSignalHandlers=False)

    def close(self):
        """Close all connections
        """
        keys = set(self._conns.keys())
        for key in keys:
            self.stop_socket(key)

        self._conns = {}
