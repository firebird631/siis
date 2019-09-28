# @date 2019-08-28
# @author Frederic SCHERMA
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
from config import config
from common.utils import UTC

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

    # https://api.kraken.com/0/private/OpenOrders
    # https://api.kraken.com/0/private/ClosedOrders
    # https://api.kraken.com/0/private/QueryOrders
    # https://api.kraken.com/0/private/TradesHistory
    # https://api.kraken.com/0/private/QueryTrades
    # https://api.kraken.com/0/private/OpenPositions
    # https://api.kraken.com/0/private/TradeVolume
    # https://api.kraken.com/0/private/AddOrder
    # https://api.kraken.com/0/private/CancelOrder

    # @ref REST https://www.kraken.com/features/api
    # @ref WSS https://www.kraken.com/en-us/features/websocket-api
    """

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

    def __init__(self, service, api_key, api_secret, symbols, host="api.kraken.com", callback=None):
        self._protocol = "https://"
        self._host = host or "api.kraken.com"

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

            # self._ws.subscribe_public(...)
            # @todo
            # self._ws.connect(self.__api_key, self.__api_secret)

    def disconnect(self):
        if self._ws:
            self._ws.stop()
            self._ws = None

            # but might be more general with a ref counter
            from twisted.internet import reactor
            try:
                reactor.stop()
            except:
                # if not running avoid exception
                pass

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
        last_datetime = str(int(from_date.timestamp() * 1000000000))
        to_ts = to_date.timestamp()

        while 1:
            if last_datetime:
                params['since'] = last_datetime

            results = self.query_public('Trades', params)

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
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

                yield (int(dt*1000),  # integer ms
                    c[0], c[0],  # price
                    c[1])  # volume

            if dt > to_ts or not len(trades):
                break

            last_ts = result.get('last', "")
            if last_ts != prev_last_ts:
                prev_last_ts = last_ts
                last_datetime = last_ts
                # last_datetime = str(int((dt+0.001)*1000000000))
            else:
                break

            # kraken does not manage lot of history (no need to loop)
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

        last_datetime = from_date.timestamp() - 1.0  # minus 1 sec else will not have from current
        to_ts = to_date.timestamp()

        delta = None

        # but we disallow 1w and 15d because 1w starts on a thuesday
        if interval == 10080:
            delta = timedelta(days=3)

        while 1:
            if last_datetime:
                params['since'] = int(last_datetime)

            results = self.query_public('OHLC', params)

            if results.get('error', []):
                raise ValueError("Kraken historical candle : %s !" % '\n'.join(results['error']))

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
                    c[6])  # volume

                last_datetime = dt

                if (to_ts and dt > to_ts):
                    break

            # kraken does not manage lot of history (no need to loop)
            break

            # last_datetime = float(results.get('last', dt*1000)) * 0.001
            # time.sleep(1.5)  # don't excess API usage limit

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
        result = self.query_private('Balance')

        if data['error']:
            logger.error("query balance: %s" % ', '.join(data['error']))
            return {}

        if data['result']:
            return data['result']

        return {}

    def get_open_orders(self):
        # trades = inclure les trades ou non dans la requête (facultatif. par défaut = faux) 
        # userref = restreindre les résultats à un identifiant de référence utilisateur donné (facult
        params = {}

        result = self.query_private('OpenOrders', params)
        # refid = identifiant de référence de la transaction qui a créé cette commande
        # userref = identifiant de référence de l'utilisateur
        # status = état de l'ordre
        #     pending = ordre en attente d'entrer dans le livre
        #     open = ordre ouvert
        #     closed = ordre fermé
        #     canceled = ordre annulé
        #     expired = ordre expiré
        # opentm = horodatage Unix où la commande a été passée
        # starttm = horodatage Unix de l'heure de début de la commande (ou 0 s'il n'est pas configuré)
        # expiretm = horodatage Unix de l'heure de fin de la commande (ou 0 s'il n'est pas configuré)
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
