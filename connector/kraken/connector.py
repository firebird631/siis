# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# HTTPS+WS connector for kraken.com

import time
import base64
import requests
import threading

import urllib.parse
import hashlib
import hmac

from datetime import datetime, timedelta
from common.utils import UTC

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_LONG_NAME, APP_RELEASE

from .ws import WssClient

import logging
logger = logging.getLogger('siis.connector.kraken')


class MaxConns(object):

    __slots__ = '_count', '_max_conns', '_condition'

    def __init__(self, max_conns):
        self._count = 0
        self._max_conns = max_conns
        self._condition = threading.Condition()

    def wait(self):
        self._condition.acquire()
        while self._count >= self._max_conns:
            self._condition.wait()
        self._count += 1
        self._condition.release()

    def done(self):
        self._condition.acquire()
        if self._count > 0:
            self._count -= 1
        self._condition.notify()
        self._condition.release()


class WaitingConns(object):

    __slots__ = '_delay', '_next_ts', '_mutex'

    def __init__(self, delay):
        self._delay = delay
        self._next_ts = 0.0
        self._mutex = threading.Lock()

    def wait(self):
        self._mutex.acquire()
        now = time.time()
        if now < self._next_ts:
            time.sleep(self._next_ts - now)
        self._mutex.release()

    def done(self):
        self._mutex.acquire()
        self._next_ts = time.time() + self._delay
        self._mutex.release()


class Connector(object):
    """
    Kraken.com HTTPS connector.

    Public API
    ==========

    The public endpoints are rate limited by IP address and currency pair for calls to Trades and OHLC, 
    and by IP address only for calls to all other public endpoints.
    Calling the public endpoints at a frequency of 1 per second (or less) would remain within the rate limits, 
    but exceeding this frequency could cause the calls to be rate limited. If the rate limits are reached, 
    additional calls would be restricted for a few seconds (or possibly longer if calls continue to be made while
    the rate limits are active).

    Private API
    ===========

    Request limits are determined from cost associated with each API call. Clients can spend up to 500 every 10 seconds.
    @ref https://support.kraken.com/hc/en-us/articles/206548367-What-are-the-API-rate-limits-
    @ref https://support.kraken.com/hc/en-us/articles/360045239571

    @todo Private rate limit by call cost but need a global lock for multiple call

    The private rate limit counter increase by call cost 1 per call (or 2 for history call),
    with max at 15(starter) or 20(intermediate and pro) initial. It decrease by 1 every 3(starter) or 2(intermediate)
    or 1(pro) seconds. This counter is per API key.

    Order/cancel does not affect the same counter, they are per market and for any API keys.

    # https://api.kraken.com/0/private/QueryTrades
    # https://api.kraken.com/0/private/TradeVolume

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
        "EAPI:Invalid nonce"
        "EAccount:Invalid permissions"
        "EAuth:Account temporary disabled"
        "EAuth:Account unconfirmed"
        "EAuth:Rate limit exceeded"
        "EAuth:Too many requests"
        "EGeneral:Invalid arguments"
        "EGeneral:Internal Error[:<code>]"
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
        "ESession:Invalid session"
        "ETrade:Invalid request"
    """

    CANDLES_HISTORY_MAX_RETRY = 3
    TRADES_HISTORY_MAX_RETRY = 3
    ORDER_HISTORY_MAX_RETRY = 3
    QUERY_PRIVATE_MAX_RETRY = 3

    PUBLIC_QUERY_DELAY = 1.5
    MAX_PUBLIC_CONNS = 5

    STARTER_PRIVATE_QUERY_DELAY = 3
    INTERMEDIATE_PRIVATE_QUERY_DELAY = 2
    PRO_PRIVATE_QUERY_DELAY = 1

    STARTER_PRIVATE_MAX_COUNTER = 15
    INTERMEDIATE_PRIVATE_MAX_COUNTER = 20
    PRO_PRIVATE_MAX_COUNTER = 20

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

    def __init__(self, service, account_id, api_key, api_secret, host="api.kraken.com"):
        self._protocol = "https://"
        self._host = host or "api.kraken.com"

        self._account_id = account_id

        self._apiversion = '0'

        self._base_url = "/"
        self._timeout = 7   
        self._retries = 0  # initialize counter

        self._public_pairs_conn_conds = {}
        self._public_conn_cond = MaxConns(Connector.MAX_PUBLIC_CONNS)

        self._private_call_counter = 0
        self._private_call_max_counter = Connector.INTERMEDIATE_PRIVATE_MAX_COUNTER
        self._private_call_delay = Connector.INTERMEDIATE_PRIVATE_QUERY_DELAY
        self._private_call_last_ts = 0

        self.__api_key = api_key
        self.__api_secret = api_secret

        self._session = None
        self._ws = None

    def connect(self, use_ws=True):
        # Prepare HTTPS session
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({'user-agent': "%s-%s" % (APP_SHORT_NAME,
                                                                   '.'.join([str(x) for x in APP_VERSION]))})

        if self._ws is None and use_ws:
            # only subscribe to available instruments
            self._ws = WssClient(self.__api_key, self.__api_secret)

    def disconnect(self):
        if self._ws:
            self._ws.stop()
            self._ws = None

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

    def instruments(self):
        data = self.query_public('AssetPairs')

        if not data:
            return {}
        
        if data.get('error'):
            logger.error("query markets: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result']

        return {}

    def assets(self):
        data = self.query_public('Assets')

        if not data:
            return {}
        
        if data.get('error'):
            logger.error("query assets: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result']

        return {}

    def get_ws_token(self):
        data = self.query_private('GetWebSocketsToken')

        if not data:
            logger.error("ws token no result")
            return {}

        if data.get('error'):
            logger.error("ws token: %s" % ', '.join(data['error']))
            return ""

        if data.get('result'):
            return data['result']

        return ""

    def get_historical_trades(self, symbol, from_date, to_date=None, limit=None):
        """
        @note Per chunk of 1000.
        """
        params = {
            'pair': symbol,
        }

        prev_last_ts = ""
        last_datetime = str(int(from_date.timestamp() * 1000000000)) if from_date else "0"
        to_ts = to_date.timestamp()
        retry_count = 0
        dt = 0

        while 1:
            if last_datetime:
                params['since'] = last_datetime

            try:
                results = self.query_public('Trades', params)
            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code <= 599 or 1000 <= e.response.status_code <= 1100:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.TRADES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical trades : Multiple failures after consecutive errors %s." %
                                         e.response.status_code)

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

                # integer ms, bid, ask, last, volume, bid or ask direction
                yield int(dt*1000), c[0], c[0], c[0], c[1], bid_ask

            if not len(trades) or dt > to_ts:
                break

            last_ts = result.get('last', "")
            if last_ts != prev_last_ts:
                prev_last_ts = last_ts
                last_datetime = last_ts
                # last_datetime = str(int((dt+0.001)*1000000000))
            else:
                break

            time.sleep(0.5)  # don't excess API usage limit (managed by query_public, but extra needed...)

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

        # but we disallow 1w and 15d because 1w starts on thursday
        if interval == 10080:
            delta = timedelta(days=3)

        while 1:
            if last_datetime:
                params['since'] = int(last_datetime)

            try:
                results = self.query_public('OHLC', params)
            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code <= 599 or 1000 <= e.response.status_code <= 1100:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.CANDLES_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical candles : Multiple failures after consecutive errors %s" %
                                         e.response.status_code)

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

                # integer ms, ohlc, spread, volume
                yield int(dt*1000), c[1], c[2], c[3], c[4], 0.0, c[6]

                last_datetime = dt

                if to_ts and dt > to_ts:
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

        # data = self.query_private('TradeBalance', params)
        data = self.retry_query_private('TradeBalance', params)

        if not data:
            logger.error("query trade balance no result")
            return {}

        if data.get('error'):
            logger.error("query trade balance: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result']

        return {}

    def get_balances(self):
        # data = self.query_private('Balance')
        data = self.retry_query_private('Balance')

        if not data:
            logger.error("query balance no result")
            return {}

        if data.get('error'):
            logger.error("query balance: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result']

        return {}

    def get_trade_volume(self):
        # pair = comma delimited list of asset pairs to get fee info on (optional)
        # fee-info = whether or not to include fee info info results (optional)
        # data = self.query_private('TradeVolume')
        data = self.retry_query_private('TradeVolume')

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

        if not data:
            logger.error("query trade volume no result")
            return {}

        if data.get('error'):
            logger.error("query trade volume: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
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

        # data = self.query_private('OpenOrders', params)
        data = self.retry_query_private('OpenOrders', params)

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

        if not data:
            logger.error("query open orders no result")
            return {}

        if data.get('error'):
            logger.error("query open orders: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result'].get('open', {})

        return {}

    def get_closed_orders(self, from_date, to_date=None, trades=False, userref=None):
        # trades = inclure les trades ou non dans la requete (facultatif. par defaut = faux)
        # userref = restreindre les resultats à un identifiant de référence utilisateur donne (facultatif)
        params = {}

        if trades:
            params['trades'] = True

        if userref:
            params['userref'] = userref

        last_datetime = from_date.timestamp() - 1.0 if from_date else 0.0  # minus 1 sec else will not have from current
        to_ts = to_date.timestamp() if to_date else time.time()
        retry_count = 0

        if from_date:
            params['start'] = last_datetime

        if to_date:
            params['end'] = to_ts

        params['ofs'] = 0

        while 1:
            try:
                results = self.query_private('ClosedOrders', params, cost=2)
            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code <= 599 or 1000 <= e.response.status_code <= 1100:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.ORDER_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical orders : Multiple failures after consecutive errors %s." %
                                         e.response.status_code)

                    continue
                else:
                    raise ValueError("Kraken historical orders : %s !" % e.response.status_code)

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
                    continue

                elif results['error'][0] == "EService:Busy":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.ORDER_HISTORY_MAX_RETRY:
                        raise ValueError("Kraken historical orders : %s !" % '\n'.join(results['error']))

                    continue
                else:
                    raise ValueError("Kraken historical orders : %s !" % '\n'.join(results['error']))

            orders = results.get('result', {}).get('closed', {})

            for order_id, data in orders.items():
                dt = data['closetm']

                if to_ts and dt > to_ts:
                    break

                data['orderid'] = order_id

                yield data

                last_datetime = dt

            if len(orders) < 50:
                break

            params['ofs'] += len(orders)

    def get_trades_history(self, trade_type='all', start_date=None, end_date=None):
        """
        @note Unless otherwise stated, costs, fees, prices, and volumes are in the asset pair's scale,
            not the currency's scale.
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

        # result = self.query_private('TradesHistory', params, cost=2)
        result = self.retry_query_private('TradesHistory', params, cost=2)

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

        if not result:
            logger.error("query trade history no result")
            return {}

        if result.get('error'):
            logger.error("query trades history: %s" % ', '.join(result['error']))
            return {}

        if result.get('result'):
            return result['result'].get('trades', {})

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

        # result = self.query_private_order('AddOrder', params)
        result = self.retry_query_private_order('AddOrder', params)
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

        # result = self.query_private_order('CancelOrder', params)
        result = self.retry_query_private_order('CancelOrder', params)
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

        # data = self.query_private('OpenPositions', params)
        data = self.retry_query_private('OpenPositions', params)

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

        if not data:
            logger.error("query open positions no result")
            return {}

        if data.get('error'):
            logger.error("query open positions: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            # logger.info(data['result'])
            return data['result'].get('open', {})

        return {}

    def get_orders_info(self, txids=None, userref=None, trades=False):
        # trades = whether or not to include trades in output (optional.  default = false)
        # userref = restrict results to given user reference id (optional)
        # txid = comma delimited list of transaction ids to query info about (50 maximum)
        if not txids:
            return {}

        params = {
            'txid': ','.join(txids)
        }

        if trades:
            params['trades'] = True

        if userref:
            params['userref'] = userref

        # data = self.query_private('QueryOrders', params)
        data = self.retry_query_private('QueryOrders', params)

        if not data:
            logger.error("query orders info no result")
            return {}

        if data.get('error'):
            logger.error("query orders info: %s" % ', '.join(data['error']))
            return {}

        if data.get('result'):
            return data['result']

        return {}

    #
    # internal
    #

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

        self._public_conn_cond.wait()

        results = None

        pair = data.get('pair', "")

        if pair not in self._public_pairs_conn_conds:
            self._public_pairs_conn_conds[pair] = WaitingConns(Connector.PUBLIC_QUERY_DELAY)

        pair_cond = self._public_pairs_conn_conds[pair]
        pair_cond.wait()
        results = self._query(urlpath, data, timeout=timeout)
        pair_cond.done()

        self._public_conn_cond.done()

        return results

    def query_private(self, method, data=None, timeout=None, cost=1):
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

        # now = time.time()
        #
        # times = now - self._private_call_last_ts
        # if times > self._private_call_delay:
        #     n = times / self._private_call_delay
        #     self._private_call_counter -= n
        #
        #     if self._private_call_counter < 0:
        #         self._private_call_counter = 0
        #
        # # check the private call counter, if reached compute the best time to wait before doing the call
        # if self._private_call_counter + cost > self._private_call_max_counter:
        #     # need to wait before
        #     count = self._private_call_counter + cost - self._private_call_max_counter
        #     # self._private_call_delay = Connector.INTERMEDIATE_PRIVATE_QUERY_DELAY
        #
        # self._private_call_counter += cost
        # self._private_call_last_ts = now

        return self._query(urlpath, data, headers, timeout=timeout)

    def retry_query_private(self, method, data=None, timeout=None, cost=1):
        """
        Retry query private for common operation excepted add and cancel order.
        """
        retry_count = 0

        while 1:
            try:
                results = self.query_private(method, data, timeout, cost)
            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code <= 599 or 1000 <= e.response.status_code <= 1100:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        raise

                    continue
                else:
                    raise

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

                elif results['error'][0] == "EAPI:Invalid nonce":
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

                elif results['error'][0] == "EService:Busy":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

            return results

    def query_private_order(self, method, data=None, timeout=None):
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

        # @todo check the private call counter per market, if reached compute the best time to wait before
        # doing the call, but it is for all the API key... then there is some unknowns

        return self._query(urlpath, data, headers, timeout=timeout)

    def retry_query_private_order(self, method, data=None, timeout=None):
        """
        Retry query private for add and cancel order only.
        """
        retry_count = 0

        while 1:
            try:
                results = self.query_private_order(method, data, timeout)
            except requests.exceptions.HTTPError as e:
                if 500 <= e.response.status_code <= 599 or 1000 <= e.response.status_code <= 1100:
                    # bad gateway service, retry for 3 times delayed by 5 seconds
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        raise

                    continue
                else:
                    raise

            if results.get('error', []):
                if results['error'][0] == "EAPI:Rate limit exceeded":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

                elif results['error'][0] == "EOrder:Rate limit exceeded":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

                elif results['error'][0] == "EAPI:Invalid nonce":
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

                elif results['error'][0] == "EService:Busy":
                    time.sleep(5.0)
                    retry_count += 1

                    if retry_count > Connector.QUERY_PRIVATE_MAX_RETRY:
                        break

                    continue

            return results

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
