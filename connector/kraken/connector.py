# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# HTTPS+WS connector for kraken.com

import time
import json
import base64
import requests

import urllib.parse
import hashlib
import hmac

from datetime import datetime, timedelta
from common.utils import UTC

from monitor.service import MonitorService

from .ws import WssClient

import logging
logger = logging.getLogger('siis.connector.kraken')


class Connector(object):
    """
    Kraken.com HTTPS connector.

    @todo Rate limit
    With max at 15 or 20 initial, decrease by 1 every 3 or 2 seconds.
    Order/cancel does not affect this counter.
    Trade history increase by 2, other by 2

    # https://api.kraken.com/0/private/ClosedOrders
    # https://api.kraken.com/0/private/QueryOrders
    # https://api.kraken.com/0/private/QueryTrades

    # @ref REST https://www.kraken.com/features/api
    # @ref WSS https://www.kraken.com/en-us/features/websocket-api

    Public WS errors :
        "Already subscribed"
        "Currency pair not in ISO 4217-A3 format"
        "Malformed request"
        "Pair field must be an array"
        "Pair field unsupported for this subscription type"
        "Pair(s) not found"
        "Subscription book depth must be an integer"
        "Subscription depth not supported"
        "Subscription field must be an object"
        "Subscription name invalid"
        "Subscription object unsupported field"
        "Subscription ohlc interval must be an integer"
        "Subscription ohlc interval not supported"
        "Subscription ohlc requires interval"

    Private WS errors :
        "EAccount:Invalid permissions"
        "EAuth:Account temporary disabled"
        "EAuth:Account unconfirmed"
        "EAuth:Rate limit exceeded"
        "EAuth:Too many requests"
        "EGeneral:Invalid arguments"
        "EOrder:Cannot open opposing position"
        "EOrder:Cannot open position"
        "EOrder:Insufficient funds (insufficient user funds)""
        "EOrder:Insufficient margin (exchange does not have sufficient funds to allow margin trading)""
        "EOrder:Invalid price"
        "EOrder:Margin allowance exceeded"
        "EOrder:Margin level too low"
        "EOrder:Order minimum not met (volume too low)""
        "EOrder:Orders limit exceeded"
        "EOrder:Positions limit exceeded"
        "EOrder:Rate limit exceeded"
        "EOrder:Scheduled orders limit exceeded"
        "EOrder:Unknown position"
        "EService:Market in cancel_only mode"
        "EService:Market in limit_only mode"
        "EService:Market in post_only mode"
        "EService:Unavailable"
        "ETrade:Invalid request"
    """

    CANDLES_HISTORY_MAX_RETRY = 3
    TRADES_HISTORY_MAX_RETRY = 3

    INTERVALS = {
        1: 60.0,        # 1m
        5: 300.0,
        15: 900.0,
        30: 1800.0,
        60: 3600.0,
        240: 14400.0,   # 4h
        1440: 86400.0,  # 1d
        # 10080: 604800,
        # 21600: 1296000,
    }

    def __init__(self, service, account_id, api_key, api_secret, symbols, host="api.kraken.com", callback=None):
        self._protocol = "https://"
        self._host = host or "api.kraken.com"

        self._account_id = account_id

        self._apiversion = '0'

        self._base_url = "/"
        self._timeout = 7   
        self._retries = 0  # initialize counter

        self._watched_symbols = symbols  # followed instruments or ['*'] for any

        self.__api_key = api_key
        self.__api_secret = api_secret

        # REST API
        self._session = None

        # Create websocket for streaming data
        self._ws = WssClient(api_key, api_secret)

    def connect(self, use_ws=True):
        # Prepare HTTPS session
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({'user-agent': 'siis-' + '1.0'})

        if self._ws is not None and use_ws:
            # only subscribe to avalaibles instruments
            symbols = []

    def disconnect(self):
        if self._ws:
            self._ws.stop()
            self._ws = None

            MonitorService.release_reactor()

        if self._session:
            self._session = None

    @property
    def authenticated(self):
        return self.__api_key is not None

    @property
    def ws(self):
        return self._ws

    @property
    def connected(self):
        return self._session is not None

    @property
    def ws_connected(self):
        return self._ws is not None

    @property
    def account_id(self):
        return self._account_id

    @property
    def watched_instruments(self):
        return self._watched_symbols

    def instruments(self):
        data = self.query_public('AssetPairs')

        if not data:
            return []
        
        if data['error']:
            logger.error("query markets: %s" % ', '.join(data['error']))
            return []

        if data['result']:
            return data['result']

        return []

    def assets(self):
        data = self.query_public('Assets')

        if not data:
            return []
        
        if data['error']:
            logger.error("query assets: %s" % ', '.join(data['error']))
            return []

        if data['result']:
            return data['result']

        return []

    def get_ws_token(self):
        data = self.query_private('GetWebSocketsToken')

        if data['error']:
            logger.error("ws token: %s" % ', '.join(data['error']))
            return ""

        if data['result']:
            return data['result']

        return ""

    def get_historical_trades(self, symbol, from_date, to_date=None, limit=None):
        """
        @note Per chunck of 1000.
        """
        params = {
            'pair': symbol,
        }

        prev_last_ts = ""
        last_datetime = str(int(from_date.timestamp() * 1000000000)) if from_date else "0"
        to_ts = to_date.timestamp()
        retry_count = 0

        while 1:
            if last_datetime:
                params['since'] = last_datetime

            try:
                results = self.query_public('Trades', params)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 502:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.TRADES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical trades\nMultiple failures after consecutives errors 502.")

                    continue
                else:
                    raise ValueError("Kraken historical trades : %s !" % e.response.status_code)

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
                    continue

                elif results['error'][0] == "EService:Busy":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.TRADES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical trades : %s !" % '\n'.join(results['error']))

                    continue
                else:
                    raise ValueError("Kraken historical trades : %s !" % '\n'.join(results['error']))

            result = results.get('result', {})
            trades = result.get(symbol, [])

            for c in trades:
                # ["6523.70000","0.00309500",1537144913.0241,"b","l",""]  b for buy or s for sell
                dt = c[2]

                if to_ts and dt > to_ts:
                    break

                bid_ask = 0

                # bid or ask depending of order direction and type
                if c[3] == 'b' and c[4] == 'l':
                    bid_ask = -1
                elif c[3] == 'b' and c[4] == 'm':
                    bid_ask = 1
                if c[3] == 's' and c[4] == 'l':
                    bid_ask = 1
                if c[3] == 's' and c[4] == 'm':
                    bid_ask = -1

                yield (int(dt*1000),  # integer ms
                    c[0], c[0],  # bid, ask
                    c[0],  # last
                    c[1],  # volume
                    bid_ask)

            if dt > to_ts:  # or not len(trades):
                break

            last_ts = result.get('last', "")
            if last_ts != prev_last_ts:
                prev_last_ts = last_ts
                last_datetime = last_ts
                # last_datetime = str(int((dt+0.001)*1000000000))
            else:
                break

            time.sleep(1.5)  # don't excess API usage limit

    def get_historical_candles(self, symbol, interval, from_date, to_date=None, limit=None):
        """
        Time interval [1m,5m,1h,4h,1d,1w,15d].
        """
        if interval not in self.INTERVALS:
            raise ValueError("Kraken does not support interval %s !" % interval)

        params = {
            'pair': symbol,
            'interval': interval,
        }

        last_datetime = from_date.timestamp() - 1.0 if from_date else 0.0  # minus 1 sec else will not have from current
        to_ts = to_date.timestamp()
        retry_count = 0

        delta = None

        # but we disallow 1w and 15d because 1w starts on a thuesday
        if interval == 10080:
            delta = timedelta(days=3)

        while 1:
            if last_datetime:
                params['since'] = int(last_datetime)

            try:
                results = self.query_public('OHLC', params)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 502:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.CANDLES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical candles\nMultiple failures after consecutives errors 502.")

                    continue
                else:
                    raise ValueError("Kraken historical candles : %s !" % e.response.status_code)

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
                    continue

                elif results['error'][0] == "EService:Busy":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.CANDLES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical candles : %s !" % '\n'.join(results['error']))

                    continue
                else:
                    raise ValueError("Kraken historical candles : %s !" % '\n'.join(results['error']))

            candles = results.get('result', {}).get(symbol, [])

            for c in candles:
                if delta:
                    dt = (datetime.fromtimestamp(c[0]).replace(tzinfo=UTC()) - delta).timestamp()
                else:
                    dt = c[0]

                if to_ts and dt > to_ts:
                    break

                yield (int(dt*1000),  # integer ms
                    c[1], c[2], c[3], c[4],  # ohlc
                    0.0,  # spread
                    c[6])  # volume

                last_datetime = dt

                if (to_ts and dt > to_ts):
                    break

            # kraken does not manage lot of history (no need to loop)
            break

    def get_order_book(self, symbol, depth):
        """
        Get current order book.
        """
        # @todo https://api.kraken.com/0/public/Depth
        pass

    def get_account(self, asset="ZUSD"):
        params = {
            'aclass': "currency",
            'asset': asset
        }

        data = self.query_private('TradeBalance', params)

        if data['error']:
            logger.error("query trade balance: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result']

        return {}

    def get_balances(self):
        data = self.query_private('Balance')

        if data['error']:
            logger.error("query balance: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result']

        return {}

    def get_trade_volume(self):
        # pair = comma delimited list of asset pairs to get fee info on (optional)
        # fee-info = whether or not to include fee info info results (optional)
        data = self.query_private('TradeVolume')

        # currency = volume currency
        # volume = current discount volume
        # fees = array of asset pairs and fee tier info (if requested)
        #     fee = current fee in percent
        #     minfee = minimum fee for pair (if not fixed fee)
        #     maxfee = maximum fee for pair (if not fixed fee)
        #     nextfee = next tier's fee for pair (if not fixed fee.  nil if at lowest fee tier)
        #     nextvolume = volume level of next tier (if not fixed fee.  nil if at lowest fee tier)
        #     tiervolume = volume level of current tier (if not fixed fee.  nil if at lowest fee tier)
        # fees_maker = array of asset pairs and maker fee tier info (if requested) for any pairs on maker/taker schedule
        #     fee = current fee in percent
        #     minfee = minimum fee for pair (if not fixed fee)
        #     maxfee = maximum fee for pair (if not fixed fee)
        #     nextfee = next tier's fee for pair (if not fixed fee.  nil if at lowest fee tier)
        #     nextvolume = volume level of next tier (if not fixed fee.  nil if at lowest fee tier)
        #     tiervolume = volume level of current tier (if not fixed fee.  nil if at lowest fee tier)

        if data['error']:
            logger.error("query trade volume: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result']

        return {}

    def get_open_orders(self, trades=False, userref=None):
        # trades = inclure les trades ou non dans la requête (facultatif. par défaut = faux) 
        # userref = restreindre les résultats à un identifiant de référence utilisateur donné (facult
        params = {}

        if trades:
            params['trades'] = True

        if userref:
            params['userref'] = userref

        data = self.query_private('OpenOrders', params)

        # refid = identifiant de référence de la transaction qui a créé cette commande
        # userref = identifiant de référence de l'utilisateur
        # status = état de l'ordre
        #     pending = ordre en attente d'entrer dans le livre
        #     open = ordre ouvert
        #     closed = ordre fermé
        #     canceled = ordre annulé
        #     expired = ordre expiré
        # opentm = horodatage Unix où la commande a été passée
        # starttm = horodatage Unix de l'heure de début de la commande (ou 0 s'il n'est pas configure)
        # expiretm = horodatage Unix de l'heure de fin de la commande (ou 0 s'il n'est pas configure)
        # descr = description de l'ordre 
        #     pair = pair d'actifs
        #     type =  type de commande (achat/vente) 
        #     ordertype = type de commande (voir  Ajouter une commande standard )  
        #     price = prix primaire
        #     price2 = prix secondaire
        #     leverage = montant de l'effet de levier 
        #     order = description de l'ordre
        #     close = description de l'ordre de fermeture conditionnel (si l'ensemble de fermeture conditionnel est défini) 
        # vol = volume de l'ordre (devise de base sauf si viqc est défini sur oflags
        # vol_exec = volume exécuté (devise de base, sauf si viqc est définie dans oflags) 
        # cost = coût total (devise de cotation sauf si viqc n'est pas défini dans oflags) 
        # fee =total des frais (total de cotation) 
        # price = prix moyen (devise de cotation sauf si viqc est définie dans oflags) 
        # stopprice = prix stop (devise de cotation, pour les trailing stops)
        # limitprice = prix limite de déclenchement (devise de cotation, lorsque le type d'ordre basé sur la limite est déclenché)
        # misc = liste délimitée par des virgules d'informations diverses 
        #     stopped = déclenché par prix stop 
        #     touched = déclenché par une touche de prix 
        #     liquidated = liquidation
        #     partial = remplissage partiel
        # oflags = liste d'indicateurs d'ordre séparés par des virgule
        #     viqc = volume en devise de cotation 
        #     fcib = préférer frais dans la devise de base (défaut en cas de vente)
        #     fciq = préférer frais dans la devise de cotation (par défaut si achat)
        #     nompp = pas de protection des prix du marché
        # trades = tableau d'identifiants de transaction liés à l'ordre (si des informations sur les transactions sont demandées et les données disponibles)

        if data['error']:
            logger.error("query open orders: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result'].get('open', {})

        return {}

    def get_trades_history(self, trade_type='all', start_date=None, end_date=None):
        """
        @note Unless otherwise stated, costs, fees, prices, and volumes are in the asset pair's scale, not the currency's scale.
        @note Times given by trade tx ids are more accurate than unix timestamps.
        """
        # type = type of trade (optional)
        #     all = all types (default)
        #     any position = any position (open or closed)
        #     closed position = positions that have been closed
        #     closing position = any trade closing all or part of a position
        #     no position = non-positional trades
        # trades = whether or not to include trades related to position in output (optional.  default = false)
        # start = starting unix timestamp or trade tx id of results (optional.  exclusive)
        # end = ending unix timestamp or trade tx id of results (optional.  inclusive)
        # ofs = result offset
        params = {}

        if trade_type:
            params['type'] = trade_type

        # @todo start_date, and end_date

        result = self.query_private('TradesHistory', params)

        # trades = array of trade info with txid as the key
        #     ordertxid = order responsible for execution of trade
        #     pair = asset pair
        #     time = unix timestamp of trade
        #     type = type of order (buy/sell)
        #     ordertype = order type
        #     price = average price order was executed at (quote currency)
        #     cost = total cost of order (quote currency)
        #     fee = total fee (quote currency)
        #     vol = volume (base currency)
        #     margin = initial margin (quote currency)
        #     misc = comma delimited list of miscellaneous info
        #         closing = trade closes all or part of a position
        # count = amount of available trades info matching criteria
        # If the trade opened a position :
        #     posstatus = position status (open/closed)
        #     cprice = average price of closed portion of position (quote currency)
        #     ccost = total cost of closed portion of position (quote currency)
        #     cfee = total fee of closed portion of position (quote currency)
        #     cvol = total fee of closed portion of position (quote currency)
        #     cmargin = total margin freed in closed portion of position (quote currency)
        #     net = net profit/loss of closed portion of position (quote currency, quote currency scale)
        #     trades = list of closing trades for position (if available)

        if data['error']:
            logger.error("query trades history: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result'].get('trades', {})

        return {}

    def create_order(self, data):
        # pair = asset pair
        # type = type of order (buy/sell)
        # ordertype = order type:
        #     market
        #     limit (price = limit price)
        #     stop-loss (price = stop loss price)
        #     take-profit (price = take profit price)
        #     stop-loss-profit (price = stop loss price, price2 = take profit price)
        #     stop-loss-profit-limit (price = stop loss price, price2 = take profit price)
        #     stop-loss-limit (price = stop loss trigger price, price2 = triggered limit price)
        #     take-profit-limit (price = take profit trigger price, price2 = triggered limit price)
        #     trailing-stop (price = trailing stop offset)
        #     trailing-stop-limit (price = trailing stop offset, price2 = triggered limit offset)
        #     stop-loss-and-limit (price = stop loss price, price2 = limit price)
        #     settle-position
        # price = price (optional.  dependent upon ordertype)
        # price2 = secondary price (optional.  dependent upon ordertype)
        # volume = order volume in lots
        # leverage = amount of leverage desired (optional.  default = none)
        # oflags = comma delimited list of order flags (optional):
        #     viqc = volume in quote currency (not available for leveraged orders)
        #     fcib = prefer fee in base currency
        #     fciq = prefer fee in quote currency
        #     nompp = no market price protection
        #     post = post only order (available when ordertype = limit)
        # starttm = scheduled start time (optional):
        #     0 = now (default)
        #     +<n> = schedule start time <n> seconds from now
        #     <n> = unix timestamp of start time
        # expiretm = expiration time (optional):
        #     0 = no expiration (default)
        #     +<n> = expire <n> seconds from now
        #     <n> = unix timestamp of expiration time
        # userref = user reference id.  32-bit signed number.  (optional)
        # validate = validate inputs only.  do not submit order (optional)

        # optional closing order to add to system when order gets filled:
        #     close[ordertype] = order type
        #     close[price] = price
        #     close[price2] = secondary price
        params = data

        result = self.query_private('AddOrder', params)
        # descr = order description info
        #     order = order description
        #     close = conditional close order description (if conditional close set)
        # txid = array of transaction ids for order (if order was added successfully)

        return result

    def cancel_order(self, txid):
        """
        txid may be a user reference id.
        """
        params = {'txid': txid}

        result = self.query_private('CancelOrder', params)
        # count = number of orders canceled
        # pending = if set, order(s) is/are pending cancellation

        return result

    def get_open_positions(self, txids=None, docalcs=False):
        # txid = comma delimited list of transaction ids to restrict output to
        # docalcs = whether or not to include profit/loss calculations (optional.  default = false)
        # consolidation = what to consolidate the positions data around (optional.)
        # market = will consolidate positions based on market pair
        params = {}

        if txids:
            params['txid'] = ','.join(txids)

        if docalcs:
            params['docalcs'] = True

        data = self.query_private('OpenPositions', params)
        # <position_txid> = open position info
        #     ordertxid = order responsible for execution of trade
        #     pair = asset pair
        #     time = unix timestamp of trade
        #     type = type of order used to open position (buy/sell)
        #     ordertype = order type used to open position
        #     cost = opening cost of position (quote currency unless viqc set in oflags)
        #     fee = opening fee of position (quote currency)
        #     vol = position volume (base currency unless viqc set in oflags)
        #     vol_closed = position volume closed (base currency unless viqc set in oflags)
        #     margin = initial margin (quote currency)
        #     value = current value of remaining position (if docalcs requested.  quote currency)
        #     net = unrealized profit/loss of remaining position (if docalcs requested.  quote currency, quote currency scale)
        #     misc = comma delimited list of miscellaneous info
        #     oflags = comma delimited list of order flags
        #         viqc = volume in quote currency

        if data['error']:
            logger.error("query open positions: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            logger.info(data['result'])
            return data['result'].get('open', {})

        return {}

    def _query(self, urlpath, data, headers=None, timeout=None):
        """
        Low-level query handling.

        .. note::
           Use :py:meth:`query_private` or :py:meth:`query_public`
           unless you have a good reason not to.

        :param urlpath: API URL path sans host
        :type urlpath: str
        :param data: API request parameters
        :type data: dict
        :param headers: (optional) HTTPS headers
        :type headers: dict
        :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
                        will be thrown after ``timeout`` seconds if a response
                        has not been received
        :type timeout: int or float
        :returns: :py:meth:`requests.Response.json`-deserialised Python object
        :raises: :py:exc:`requests.HTTPError`: if response status not successful
        """
        if data is None:
            data = {}
        if headers is None:
            headers = {}

        url = self._protocol + self._host + urlpath

        response = self._session.post(url, data=data, headers=headers, timeout=timeout)

        if response.status_code not in (200, 201, 202):
            response.raise_for_status()

        # @todo a max retry

        return response.json()

    def query_public(self, method, data=None, timeout=None):
        """
        Performs an API query that does not require a valid key/secret pair.

        :param method: API method name
        :type method: str
        :param data: (optional) API request parameters
        :type data: dict
        :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
                        will be thrown after ``timeout`` seconds if a response
                        has not been received
        :type timeout: int or float
        :returns: :py:meth:`requests.Response.json`-deserialised Python object
        """
        if data is None:
            data = {}

        urlpath = '/' + self._apiversion + '/public/' + method

        return self._query(urlpath, data, timeout=timeout)

    def query_private(self, method, data=None, timeout=None):
        """
        Performs an API query that requires a valid key/secret pair.

        :param method: API method name
        :type method: str
        :param data: (optional) API request parameters
        :type data: dict
        :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
                        will be thrown after ``timeout`` seconds if a response
                        has not been received
        :type timeout: int or float
        :returns: :py:meth:`requests.Response.json`-deserialised Python object
        """
        if data is None:
            data = {}

        if not self.__api_key or not self.__api_secret:
            raise Exception("kraken.com Either key or secret is not set!.")

        data['nonce'] = self._nonce()

        urlpath = '/' + self._apiversion + '/private/' + method

        headers = {
            'API-Key': self.__api_key,
            'API-Sign': self._sign(data, urlpath)
        }

        return self._query(urlpath, data, headers, timeout = timeout)

    def _nonce(self):
        """
        Nonce counter.

        :returns: an always-increasing unsigned integer (up to 64 bits wide)
        """
        return int(1000*time.time())

    def _sign(self, data, urlpath):
        """
        Sign request data according to Kraken's scheme.

        :param data: API request parameters
        :type data: dict
        :param urlpath: API URL path sans host
        :type urlpath: str
        :returns: signature digest
        """
        postdata = urllib.parse.urlencode(data)

        # Unicode-objects must be encoded before hashing
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        signature = hmac.new(base64.b64decode(self.__api_secret),
                             message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        return sigdigest.decode()
