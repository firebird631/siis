# @date 2018-08-23
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# HTTPS+WS connector for bitmex.com

import time
import json
import requests

from datetime import datetime, timedelta
from common.utils import UTC

from .apikeyauthwithexpires import APIKeyAuthWithExpires
from .ws import BitMEXWebsocket

import logging
logger = logging.getLogger('siis.connector.bitmex')


class Connector(object):

    TRADES_HISTORY_MAX_RETRY = 3
    CANDLES_HISTORY_MAX_RETRY = 3

    TIMEFRAME_TO_BIN_SIZE = {
        60: '1m',
        5*60: '5m',
        60*60: '1h',
        24*60*60: '1d'
    }

    # bin size reverse map (str: double)
    BIN_SIZE_TO_TIMEFRAME = {v: k for k, v in TIMEFRAME_TO_BIN_SIZE.items()}

    BIN_SIZE = ('1m', '5m', '1h', '1d')

    def __init__(self, service, api_key, api_secret, symbols, host="www.bitmex.com", callback=None):
        self._protocol = "https://"
        self._host = host or "www.bitmex.com"

        self._base_url = "/api/v1/"
        self._timeout = 7
        self._retries = 0  # initialize counter

        self._watched_symbols = symbols or set()  # followed instruments
        self._all_instruments = []   # available listed instruments

        # always XBTUSD as needed for others pairs or computing
        if 'XBTUSD' not in self._watched_symbols:
            self._watched_symbols.add('XBTUSD')

        self.__api_key = api_key
        self.__api_secret = api_secret
        self._callback = callback

        self._session = None
        self._ws = None

    def connect(self, use_ws=True):
        # Prepare HTTPS session
        if self._session is None:
            self._session = requests.Session()

            # These headers are always sent
            self._session.headers.update({'user-agent': 'siis-' + '1.0'})
            self._session.headers.update({'content-type': 'application/json'})
            self._session.headers.update({'accept': 'application/json'})

            # list all instruments
            endpoint = "/instrument/active"
            result = self.request(path=endpoint, verb='GET')

            self._all_instruments = []

            if isinstance(result, list):
                for instrument in result:
                    if instrument['typ'] in ('FFCCSX', 'FFWCSX'):
                        self._all_instruments.append(instrument['symbol'])

        if use_ws:
            if self._ws is None:
                self._ws = BitMEXWebsocket(self.__api_key, self.__api_secret, self._callback)

            if self._ws is not None and not self._ws.connected:
                self._ws = BitMEXWebsocket(self.__api_key, self.__api_secret, self._callback)
                # only subscribe to available instruments
                symbols = []

                if '*' in self._watched_symbols:
                    # follow any
                    self._watched_symbols = self._all_instruments
                else:
                    # follow only listed symbols
                    for symbol in self._watched_symbols:
                        if symbol in self._all_instruments:
                            symbols.append(symbol)
                        else:
                            logger.warning('- BitMex instrument %s is not available.' % (symbol,))

                    self._watched_symbols = symbols

                self._ws.connect("wss://" + self._host, symbols, should_auth=True)

    def disconnect(self):
        if self._ws:
            if self._ws.connected:
                self._ws.exit()

            self._ws = None

        if self._session:
            self._session = None

    @property
    def authenticated(self) -> bool:
        return self.__api_key is not None

    def request(self, path, query=None, postdict=None, verb=None, timeout=None, max_retries=None):
        url = self._protocol + self._host + self._base_url + path

        if timeout is None:
            timeout = self._timeout

        # default to POST if data is attached, GET otherwise
        if not verb:
            verb = 'POST' if postdict else 'GET'

        # by default don't retry POST or PUT. Retrying GET/DELETE is okay because they are idempotent.
        # in the future we could allow retrying PUT, so long as 'leavesQty' is not used (not idempotent),
        # or you could change the clOrdID (set {"clOrdID": "new", "origClOrdID": "old"}) so that an amend
        # can't erroneously be applied twice.
        if max_retries is None:
            max_retries = 0 if verb in ['POST', 'PUT'] else 3

        # auth: API Key/Secret
        auth = APIKeyAuthWithExpires(self.__api_key, self.__api_secret)

        def retry():
            self._retries += 1
            if self._retries > max_retries:
                raise Exception("Max retries on %s (%s) hit, raising." % (path, json.dumps(postdict or '')))

            return self.request(path, query, postdict, verb, timeout, max_retries)

        # Make the request
        response = None
        try:
            # logger.debug("Sending req to %s: %s" % (url, json.dumps(postdict or query or '')))

            req = requests.Request(verb, url, json=postdict, auth=auth, params=query)
            prepped = self._session.prepare_request(req)
            response = self._session.send(prepped, timeout=timeout)
            # Make non-200s throw
            response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            if response is None:
                raise e

            # 401 - Auth error. This is fatal.
            if response.status_code == 401:
                logger.error("API Key or Secret incorrect, please check and restart.")
                logger.error("Error: " + response.text, True)

                if postdict:
                    # fatal error...
                    return False

            # 404, can be thrown if order canceled or does not exist.
            elif response.status_code == 404:
                if verb == 'DELETE':
                    # logger.error("Order not found: %s" % postdict['orderID'])
                    # return

                    logger.error("Unable to contact the BitMEX API (404). ")
                    logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))
                    raise e

            # 429, ratelimit; cancel orders & wait until X-RateLimit-Reset
            elif response.status_code == 429:
                # logger.error("Ratelimited on current request (contact support@bitmex.com to raise your limits). ")
                # logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))

                # Figure out how long we need to wait.
                ratelimit_reset = response.headers['X-RateLimit-Reset']
                to_sleep = int(ratelimit_reset) - int(time.time()) + 1.0  # add 1.0 more second be we still have issues
                reset_str = datetime.fromtimestamp(int(ratelimit_reset)).strftime('%X')

                to_sleep = float(response.headers.get('Retry-After', to_sleep))

                # We're ratelimited, and we may be waiting for a long time. Cancel orders.
                # logger.warning("Canceling all known orders in the meantime.")

                # for o in self.open_orders():
                #     if 'orderID' in o:
                #         self.cancel(o['orderID'])

                logger.error("Sleeping from %s for %d seconds." % (reset_str, to_sleep))
                time.sleep(to_sleep)

                # Retry the request
                return retry()

            # 503 - BitMEX temporary downtime, likely due to a deploy. Try again
            elif response.status_code == 503:
                logger.warning("Unable to contact the BitMEX API (503), retrying.")
                logger.warning("Request: %s \n %s" % (url, json.dumps(postdict)))

                time.sleep(5)

                return retry()

            elif response.status_code == 400:
                error = response.json()['error']
                message = error['message'].lower() if error else ''

                # Duplicate clOrdID: that's fine, probably a deployment, go get the order(s) and return it
                if 'duplicate clordid' in message:
                    orders = postdict['orders'] if 'orders' in postdict else postdict

                    IDs = json.dumps({'clOrdID': [order['clOrdID'] for order in orders]})
                    order_results = self.request('/order', query={'filter': IDs}, verb='GET')

                    for i, order in enumerate(order_results):
                        if (order['orderQty'] != abs(postdict['orderQty']) or
                            order['side'] != ('Buy' if postdict['orderQty'] > 0 else 'Sell') or
                            order['price'] != postdict['price'] or
                            order['symbol'] != postdict['symbol']):

                            raise Exception('Attempted to recover from duplicate clOrdID, but order returned from API ' +
                                        'did not match POST.\nPOST data: %s\nReturned order: %s' % (
                                                json.dumps(orders[i]), json.dumps(order)))

                    # All good
                    return order_results

                elif 'insufficient available balance' in message:
                    logger.error('BitMex Account out of funds. The message: %s' % error['message'])
                    raise Exception('BitMex Insufficient Funds')

                # If we haven't returned or re-raised yet, we get here.
                logger.error("BitMex unhandled Error: %s: %s" % (e, response.text))
                logger.error("Endpoint was: %s %s: %s" % (verb, path, json.dumps(postdict)))

                raise e

        except requests.exceptions.Timeout as e:
            # Timeout, re-run this request (retry immediately)
            logger.warning("Timed out on request: %s (%s), retrying..." % (path, json.dumps(postdict or '')))
            return retry()

        except requests.exceptions.ConnectionError as e:
            logger.warning("Unable to contact the BitMEX API (%s). Please check the URL. Retrying. ")
            logger.warning("Request: %s %s \n %s" % (e, url, json.dumps(postdict)))

            time.sleep(2)
            return retry()

        # Reset retry counter on success
        self._retries = 0

        return response.json()

    @property
    def ws(self):
        return self._ws

    @property
    def connected(self) -> bool:
        return self._session is not None

    @property
    def ws_connected(self):
        return self._ws is not None and self._ws.connected

    @property
    def watched_instruments(self):
        return self._watched_symbols

    @property
    def all_instruments(self):
        return self._all_instruments

    def get_historical_trades(self, symbol, from_date, to_date=None, limit=None):
        trades = []

        endpoint = "trade" # quote"

        params = {
            'symbol': symbol,
            'reverse': 'false',
            'count': limit or 500,  # or max limit
            'start': 0
        }

        if to_date:
            params['endTime'] = self._format_datetime(to_date)

        start = 0
        last_datetime = from_date
        last_trade_id = ""
        retry_count = 0  # in case of request http error (timeout, expired timestamp)

        while 1:
            if last_datetime:
                params['startTime'] = self._format_datetime(last_datetime)

            params['start'] = start  # offset if timestamp are same
            results = []

            try:
                results = self.request(path=endpoint, query=params, verb='GET')
            except requests.exceptions.HTTPError as e:
                retry_count += 1
                if retry_count > Connector.TRADES_HISTORY_MAX_RETRY:
                    raise e

            for c in results:
                if not c['timestamp']:
                    continue

                dt = self._parse_datetime(c['timestamp']).replace(tzinfo=UTC())
                if to_date and dt > to_date:
                    break

                if dt < last_datetime:
                    start += 1
                    continue

                if last_trade_id == c['trdMatchID']:
                    # could be in case of the last trade of the prev query is the first of the current query
                    continue

                # increase offset when similar timestamp, else reset
                if dt == last_datetime:
                    start += 1
                else:
                    start = 0

                # PlusTick,MinusTick,ZeroPlusTick,ZeroMinusTick
                direction = 0

                if c['tickDirection'] in ('PlusTick', 'ZeroPlusTick'):
                    direction = 1
                elif c['tickDirection'] in ('MinusTick', 'ZeroMinusTick'):
                    direction = -1

                yield (int(dt.timestamp()*1000),  # integer ms
                    c['price'], c['price'],  # bid, ask
                    c['price'],  # last
                    c['size'],  # volume
                    direction)

                last_datetime = dt
                last_trade_id = c['trdMatchID']

            if (to_date and last_datetime > to_date) or len(results) < 500:
                break

            time.sleep(1.0)  # don't excess API usage limit

        return trades

    def get_historical_candles(self, symbol, bin_size, from_date, to_date=None, limit=None, partial=False):
        """
        Time interval [1m,5m,1h,1d].
        """
        candles = []
        endpoint = "trade/bucketed"  # "quote/bucketed"

        if bin_size not in self.BIN_SIZE:
            raise ValueError("BitMex does not support bin size %s !" % bin_size)

        params = {
            'binSize': bin_size,
            'symbol': symbol,
            'reverse': 'false',
            'count': limit or 750,  # or max limit
            # 'start': 0
        }

        if partial:
            params['partial'] = True

        # because bitmex works in close time but we are in open time
        # delta = self.BIN_SIZE_TO_TIMEFRAME[bin_size]
        # have issue using delta in seconds why...

        delta_time = timedelta(seconds=0)

        if bin_size == '1m':
            delta_time = timedelta(minutes=1)
        elif bin_size == '5m':
            delta_time = timedelta(minutes=5)
        elif bin_size == '1h':
            delta_time = timedelta(hours=1)
        elif bin_size == '1d':
            delta_time = timedelta(days=1)

        if to_date:
            # params['endTime'] = self._format_datetime(to_date + timedelta(seconds=delta))
            params['endTime'] = self._format_datetime(to_date + delta_time)

        # last_datetime = from_date + timedelta(seconds=delta)
        last_datetime = from_date + delta_time
        ot = from_date  # init
        retry_count = 0

        while 1:
            results = []

            if last_datetime:
                params['startTime'] = self._format_datetime(last_datetime)

            try:
                results = self.request(path=endpoint, query=params, verb='GET')
            except requests.exceptions.HTTPError as e:
                retry_count += 1
                if retry_count > Connector.CANDLES_HISTORY_MAX_RETRY:
                    raise e

            for c in results:
                dt = self._parse_datetime(c['timestamp']).replace(tzinfo=UTC())

                # its close time, want open time
                ot = dt - delta_time  # timedelta(seconds=delta)

                if to_date and ot > to_date:
                    break

                yield (int(ot.timestamp()*1000),  # integer ms
                    c['open'], c['high'], c['low'], c['close'],
                    0.0,  # spread
                    c['volume'])

                last_datetime = dt

            if (to_date and ot > to_date) or len(results) < 750:
                break

            time.sleep(1.0)  # don't excess API usage limit

    def _format_datetime(self, dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S+00:00')

    def _parse_datetime(self, dt):
        return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%fZ')

    def get_order_book_l2(self, symbol, depth):
        """
        Get current order book.
        @return A tuple with two arrays of dict : (buys, sells)
            Each entry contains the id of the order, size and price.
        """

        orders = []
        endpoint = "orderBook/L2"

        params = {
            'symbol': symbol,
            'depth': depth or 0,
        }

        results = self.request(path=endpoint, query=params, verb='GET')

        buys = []
        sells = []

        for data in results:
            if data['side'] == 'Buy':
                buys.append({
                    'id': str(data['id']),
                    'size': data['size'],
                    'price': data['price']
                })
            elif data['side'] == 'Sell':
                sells.append({
                    'id': str(data['id']),
                    'size': data['size'],
                    'price': data['price']
                })

        return buys, sells
