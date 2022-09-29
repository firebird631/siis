# @date 2018-08-23
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Websocket connector for bitmex.com
import time

import websocket
import threading
import traceback
import ssl
from time import sleep
import json
import decimal
from .apikeyauth import generate_nonce, generate_signature
from urllib.parse import urlparse, urlunparse

from decimal import Decimal

import logging
logger = logging.getLogger('siis.connector.bitmex.ws')
error_logger = logging.getLogger('siis.error.connector.bitmex.ws')
traceback_logger = logging.getLogger('siis.traceback.connector.bitmex.ws')


def to_nearest(num, tick_size):
    """
    Given a number, round it to the nearest tick. Very useful for sussing float error
    out of numbers: e.g. toNearest(401.46, 0.01) -> 401.46, whereas processing is
    normally with floats would give you 401.46000000000004.
    Use this after adding/subtracting/multiplying numbers.
    """
    tick_dec = Decimal(str(tick_size))
    return float((Decimal(round(num / tick_size, 0)) * tick_dec))


class BitMEXWebsocket(object):
    """
    Connects to BitMEX websocket for streaming realtime data.
    The Marketmaker still interacts with this as if it were a REST Endpoint, but now it can get
    much more realtime data without heavily polling the API.
    
    The Websocket offers a bunch of data as raw properties right on the object.
    On connect, it synchronously asks for a push of all this data then returns.
    Right after, the MM can start using its data. It will be updated in realtime, so the MM can poll as often as it wants.
    
    @todo Might need a mutex when reading/writing the data object.

    # ref #1: https://github.com/BitMEX/sample-market-maker/blob/master/market_maker/ws/ws_thread.py
    # ref #2: https://github.com/BitMEX/api-connectors/blob/master/official-ws/python/bitmex_websocket.py
    # ref #3: https://github.com/joliveros/bitmex-websocket
    # ref #4: https://www.bitmex.com/app/wsAPI
    """

    MAX_TABLE_LEN = 200  # Don't grow a table larger than this amount. Helps cap memory usage.
    PREFERED_ORDER_BOOK = "orderBookL2_25"

    def __init__(self, api_key, api_secret, callback=None):
        self.__api_key = api_key
        self.__api_secret = api_secret
        self._callback = callback
        self._message_last_time = 0.0

        self.__reset()

    def __del__(self):
        self.exit()

    def connect(self, endpoint="", symbols=["XBTUSD"], should_auth=True):
        """
        Connect to the websocket and initialize data stores.
        """
        self.symbols = symbols
        self.should_auth = should_auth

        self._message_last_time = 0.0

        subscriptions = []

        # We can subscribe right in the connection querystring, so let's build that.
        # Subscribe to all pertinent endpoints
        for symbol in symbols:
            subscriptions += [sub + ':' + symbol for sub in ["quote", "trade", "liquidation"]]  # , BitMEXWebsocket.PREFERED_ORDER_BOOK]]
    
        subscriptions += ["instrument"]  # We want all of them

        if self.should_auth:
            for symbol in symbols:
                subscriptions += [sub + ':' + symbol for sub in ["order", "execution"]]
    
            subscriptions += ["margin", "position"]

        # Get WS URL and connect.
        urlParts = list(urlparse(endpoint))
        urlParts[0] = urlParts[0].replace('http', 'ws')
        urlParts[2] = "/realtime?subscribe=" + ",".join(subscriptions)
        wsURL = urlunparse(urlParts)

        # @todo or
        # wsURL = self.__get_url(endpoint)

        logger.debug("BitMex connecting to %s" % wsURL)
        try:
            self.__connect(wsURL)
        except Exception as e:
            logger.error(repr(e))
            self.__reset()

        # Connected. Wait for partials
        if self._connected:
            logger.debug('- BitMex connected to WS. Waiting for data images, this may take a moment...')

            self.__wait_for_symbol(symbols)
            if self.should_auth:
                self.__wait_for_account()

            logger.info('- BitMex got account and market data. Running.')

    #
    # Data methods
    #

    @property
    def message_last_time(self):
        return self._message_last_time

    def get_instrument(self, symbol):
        """
        Get an instrument by symbol.
        """
        instruments = self.data.get('instrument', {})
        matchingInstruments = [i for i in instruments if i['symbol'] == symbol]

        if len(matchingInstruments) == 0:
            raise Exception("BitMex unable to find instrument or index with symbol: " + symbol)

        instrument = matchingInstruments[0]
        # Turn the 'tickSize' into 'tickLog' for use in rounding
        # http://stackoverflow.com/a/6190291/832202
        instrument['tickLog'] = decimal.Decimal(str(instrument['tickSize'])).as_tuple().exponent * -1

        return instrument

    def get_ticker(self, symbol):
        """
        Return a ticker object. Generated from instrument.
        """
        instrument = self.get_instrument(symbol)

        # If this is an index, we have to get the data from the last trade.
        if instrument['symbol'][0] == '.':
            ticker = {}
            ticker['mid'] = ticker['buy'] = ticker['sell'] = ticker['last'] = instrument['markPrice']
        # Normal instrument
        else:
            bid = instrument['bidPrice'] or instrument['lastPrice']
            ask = instrument['askPrice'] or instrument['lastPrice']
            ticker = {
                "last": instrument['lastPrice'],
                "buy": bid,
                "sell": ask,
                "mid": (bid + ask) / 2
            }

        # The instrument has a tickSize. Use it to round values.
        return {k: to_nearest(float(v or 0), instrument['tickSize']) for k, v in ticker.items()}

    def funds(self):
        return self.data.get('margin', [{}])[0]

    def market_depth(self, symbol):
        """
        Return order book for a symbol.
        """
        order_book = self.data.get(self.PREFERED_ORDER_BOOK, {})

        buys = []
        sells = []

        for order in order_book:
            if order['symbol'] == symbol:
                if order['side'] == 'Buy':
                    buys.append({'id': str(order['id']), 'size': order['size'], 'price': order['price']})
                elif order['side'] == 'Sell':
                    sells.append({'id': str(order['id']), 'size': order['size'], 'price': order['price']})

        return (buys, sells)

    def open_orders(self, clOrdIDPrefix):
        orders = self.data.get('order', [])
        # Filter to only open orders (leavesQty > 0) and those that we actually placed
        return [o for o in orders if str(o['clOrdID']).startswith(clOrdIDPrefix) and o['leavesQty'] > 0]

    def position(self, symbol):
        positions = self.data['position']
        pos = [p for p in positions if p['symbol'] == symbol]

        if len(pos) == 0:
            # No position found; stub it
            return {'avgCostPrice': 0, 'avgEntryPrice': 0, 'currentQty': 0, 'symbol': symbol, 'isOpen': False}

        return pos[0]

    def recent_trades(self):
        return self.data['trade']

    #
    # Lifecycle methods
    #

    def error(self, err):
        self._error = err

        logger.error(repr(err))
        traceback_logger.error(traceback.format_exc())

        self.exit()

    def exit(self):
        self.exited = True

        if self.ws is not None:
            try:
                if self._connected:
                    self.ws.close()
            except:
                pass

            self.ws = None          

        if self.wst is not None:
            try:
                if self.wst.is_alive():
                    self.wst.join()
            except:
                pass

            self.wst = None

        self._connected = False

    #
    # Private methods
    #

    def __connect(self, wsURL):
        """
        Connect to the websocket in a thread.
        """
        logger.debug("BitMex starting thread")
        ssl_defaults = ssl.get_default_verify_paths()
        sslopt_ca_certs = {'ca_certs': ssl_defaults.cafile}
        # sslopt_ca_certs = {'ca_certs': ssl.CERT_NONE, 'check_hostname': False}

        # websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(wsURL,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error,
                                         header=self.__get_auth())

        # self.wst = threading.Thread(name="bitmex.ws", target=lambda: self.ws.run_forever(
        #     sslopt=sslopt_ca_certs, ping_timeout=10, ping_interval=60))

        self.wst = threading.Thread(name="bitmex.ws", target=lambda: self.ws.run_forever(
            sslopt=sslopt_ca_certs, ping_timeout=None, ping_interval=None))
        self.wst.daemon = True
        self.wst.start()

        logger.debug("BitMex WS started thread")
        self.ws.last_ping_tm = 0.0

        # Wait for connect before continuing
        conn_timeout = 10
        while (not hasattr(self.ws, 'sock') or not self.ws.sock or not self.ws.sock.connected) and conn_timeout > 0:  # and not self._error:
            if hasattr(self.ws, 'sock') and self.ws and self.ws.sock:
                self.ws.sock.last_ping_tm = 0.0

            sleep(1)
            conn_timeout -= 1

        if conn_timeout <= 0:  # or self._error:
            logger.error("Couldn't connect to WS. Max conn timeout !")
            self.exit()

        if not self._connected or self._error:  # not hasattr(self.ws, 'sock') or not self.ws.sock or not self.ws.sock.connected or self._error:
            logger.error("Couldn't connect to WS. Error !")
            self.exit()

    def __get_auth(self):
        """Return auth headers. Will use API Keys."""
        if self.should_auth is False:
            return []

        logger.debug("Authenticating with API Key.")
        # To auth to the WS using an API key, we generate a signature of a nonce and
        # the WS API endpoint.
        nonce = generate_nonce()
        return [
            "api-nonce: " + str(nonce),
            "api-signature: " + generate_signature(self.__api_secret, 'GET', '/realtime', nonce, ''),
            "api-key:" + self.__api_key
        ]

    # def __get_url(self, endpoint):
    #   '''
    #   Generate a connection URL. We can define subscriptions right in the querystring.
    #   Most subscription topics are scoped by the symbol we're listening to.
    #   '''
    #   import urllib

    #   # You can sub to orderBookL2 for all levels, or orderBook10 for top 10 levels & save bandwidth
    #   symbolSubs = ["execution", "instrument", "order", "orderBookL2", "position", "quote", "trade"]
    #   genericSubs = ["margin"]

    #   subscriptions = [sub + ':' + self.symbol for sub in symbolSubs]
    #   subscriptions += genericSubs

    #   urlParts = list(urllib.parse.urlparse(endpoint))
    #   urlParts[0] = urlParts[0].replace('http', 'ws')
    #   urlParts[2] = "/realtime?subscribe={}".format(','.join(subscriptions))

    #   return urllib.parse.urlunparse(urlParts)

    @property
    def ready(self):
        return {'margin', 'position', 'order', 'instrument', 'trade', 'quote'} <= set(self.data)

    def __wait_for_account(self, timeout=0.1):
        """
        On subscribe, this data will come down. Wait for it.
        """
        # Wait for the keys to show up from the ws
        while not {'margin', 'position', 'order'} <= set(self.data):
            sleep(timeout)

    def __wait_for_symbol(self, symbol, timeout=0.1):
        """
        On subscribe, this data will come down. Wait for it.
        """
        while not {'instrument', 'trade', 'quote'} <= set(self.data):
            sleep(timeout)

    def __send_command(self, command, args):
        """
        Send a raw command.
        """
        self.ws.send(json.dumps({"op": command, "args": args or []}))

    def __on_message(self, cls, message):
        """
        Handler for parsing WS messages.
        """
        self._message_last_time = time.time()

        try:
            message = json.loads(message)
        except Exception as e:
            logger.error("Unable to loads json message for : %s" % (str(message)))
            message = []

        table = message['table'] if 'table' in message else None
        action = message['action'] if 'action' in message else None

        try:
            if 'subscribe' in message:
                if message['success']:
                    logger.debug("Subscribed to %s." % message['subscribe'])

                    if self._callback:
                        self._callback[1](self._callback[0], 'subscribed', None)
                else:
                    logger.error("Unable to subscribe to %s. Error: \"%s\" Please check and restart." % (message['request']['args'][0], message['error']))

            elif 'status' in message:
                if message['status'] == 400:
                    self.error(message['error'])

                    if self._callback:
                        self._callback[1](self._callback[0], 'error', 400)

                if message['status'] == 401:
                    self.error("API Key incorrect, please check and restart.")

                    if self._callback:
                        self._callback[1](self._callback[0], 'error', 401)

            elif action:

                if table not in self.data:
                    self.data[table] = []

                if table not in self.keys:
                    self.keys[table] = []

                updated = set()  # updated symbols

                # There are four possible actions from the WS:
                # 'partial' - full table image
                # 'insert'  - new row
                # 'update'  - update row
                # 'delete'  - delete row
                if action == 'partial':
                    # logger.debug("%s: partial" % table)
                    self.data[table] += message['data']
                    # Keys are communicated on partials to let you know how to uniquely identify an item. We use it for updates.
                    self.keys[table] = message['keys']

                elif action == 'insert':
                    # logger.debug('%s: inserting %s' % (table, message['data']))
                    self.data[table] += message['data']

                    # Limit the max length of the table to avoid excessive memory usage.
                    # Don't trim orders because we'll lose valuable state if we do.
                    if table not in ['order', 'orderBook10', 'orderBookL2', 'orderBookL2_25'] and len(self.data[table]) > BitMEXWebsocket.MAX_TABLE_LEN:
                        self.data[table] = self.data[table][(BitMEXWebsocket.MAX_TABLE_LEN // 2):]

                elif action == 'update':
                    # logger.debug('%s: updating %s' % (table, message['data']))

                    # Locate the item in the collection and update it.
                    for updateData in message['data']:
                        item = find_item_by_keys(self.keys[table], self.data[table], updateData)
                        if not item:
                            continue  # No item found to update. Could happen before push

                        # Log executions
                        # if table == 'order':
                        #     is_canceled = 'ordStatus' in updateData and updateData['ordStatus'] == 'Canceled'
                        #     if 'cumQty' in updateData and not is_canceled:
                        #         contExecuted = updateData['cumQty'] - item['cumQty']
                        #         if contExecuted > 0:
                        #             instrument = self.get_instrument(item['symbol'])
                        #
                        #             logger.info("BitMex execution: %s %d Contracts of %s at %.*f" % (
                        #                 item['side'], contExecuted, item['symbol'], instrument['tickLog'], item['price']))

                        # Update this item.
                        item.update(updateData)

                        # Remove canceled / filled orders
                        if table == 'order' and item['leavesQty'] <= 0:
                            self.data[table].remove(item)

                        if table == 'instrument' or table == self.PREFERED_ORDER_BOOK:
                            updated.add(updateData['symbol'])

                elif action == 'delete':
                    # logger.debug('%s: deleting %s' % (table, message['data']))
                    # Locate the item in the collection and remove it.
                    for deleteData in message['data']:
                        item = find_item_by_keys(self.keys[table], self.data[table], deleteData)
                        self.data[table].remove(item)
                else:
                    raise Exception("Unknown action: %s" % action)

                if self._callback and self.ready:
                    self._callback[1](self._callback[0], 'action', (action, table, updated, message['data']))

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    def __on_open(self, cls):
        logger.debug("BitMex websocket Opened.")
        self._connected = True

    def __on_close(self, cls, close_status_code, close_msg):
        logger.debug('BitMex websocket Closed (code:%s)' % close_status_code)
        self._connected = False

    def __on_error(self, cls, error):
        self._connected = False
        if not self.exited:
            self.error(error)

    def __reset(self):
        self.data = {}
        self.keys = {}
        self.ws = None
        self.wst = None
        self.exited = False
        self._error = None
        self._connected = False

    @property
    def connected(self) -> bool:
        # return self.ws and hasattr(self.ws, 'sock') and self.ws.sock and self.ws.sock.connected
        return self.ws is not None and self._connected


def find_item_by_keys(keys, table, match_data):
    for item in table:
        matched = True
        for key in keys:
            if item[key] != match_data[key]:
                matched = False
    
        if matched:
            return item
