# -*- coding:utf-8 -*-

"""
IG Markets REST API Library for Python
http://labs.ig.com/rest-trading-api-reference
Original version by Lewis Barber - 2014 - http://uk.linkedin.com/in/lewisbarber/
Modified by Femto Trader - 2014-2015 - https://github.com/femtotrader/
"""

import json
import time
import urllib

from base64 import b64encode, b64decode
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from requests import Session

from .utils import conv_datetime, conv_to_ms

import logging
logger = logging.getLogger("siis.connector.ig.rest")


class IGException(Exception):
    pass


class IGSessionCRUD(object):
    """
    Session with CRUD operation
    @todo add the encryptionKey to send a salted password : /gateway/deal/session/encryptionKey
    """

    CLIENT_TOKEN = None
    SECURITY_TOKEN = None

    BASIC_HEADERS = None
    LOGGED_IN_HEADERS = None
    DELETE_HEADERS = None

    BASE_URL = None

    HEADERS = {}

    def __init__(self, base_url, api_key, session):
        self.BASE_URL = base_url
        self.API_KEY = api_key

        self.HEADERS['BASIC'] = {
            'X-IG-API-KEY': self.API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'
        }

        self.session = session

        self.create = self._create_first
        self.lightstreamer_endpoint = None

    def _get_session(self, session):
        """
        Returns a Requests session if session is None or session if it's not None (cached session
        with requests-cache for example)

        :param session:
        :return:
        """
        if session is None:
            session = self.session   # requests Session
        else:
            session = session
        return session

    def _url(self, endpoint):
        """
        Returns url from endpoint and base url
        """
        return self.BASE_URL + endpoint

    def _create_first(self, endpoint, params, session):
        """
        Create first = POST with headers=BASIC_HEADERS
        """
        url = self._url(endpoint)
        session = self._get_session(session)

        if type (params['password']) is bytes:
            params['password'] = params['password'].decode()

        response = session.post(url, data=json.dumps(params), headers=self.HEADERS['BASIC'])
        if not response.ok:
            raise(Exception("HTTP status code %s %s " % (response.status_code, response.text)))

        self._set_headers(response.headers, True)
        self.create = self._create_logged_in

        data = json.loads(response.text)
        self.lightstreamer_endpoint = data.get('lightstreamerEndpoint')

        return response

    def _create_logged_in(self, endpoint, params, session):
        """
        Create when logged in = POST with headers=LOGGED_IN_HEADERS
        """
        url = self._url(endpoint)
        session = self._get_session(session)
        response = session.post(url, data=json.dumps(params), headers=self.HEADERS['LOGGED_IN'])
        return response

    def read(self, endpoint, params, session):
        """
        Read = GET with headers=LOGGED_IN_HEADERS
        """
        url = self._url(endpoint)
        session = self._get_session(session)
        response = session.get(url, params=params, headers=self.HEADERS['LOGGED_IN'])
        return response

    def update(self, endpoint, params, session):
        """
        Update = PUT with headers=LOGGED_IN_HEADERS
        """
        url = self._url(endpoint)
        session = self._get_session(session)
        response = session.put(url, data=json.dumps(params), headers=self.HEADERS['LOGGED_IN'])
        return response

    def delete(self, endpoint, params, session):
        """
        Delete = POST with DELETE_HEADERS
        """
        url = self._url(endpoint)
        session = self._get_session(session)
        response = session.post(url, data=json.dumps(params), headers=self.HEADERS['DELETE'])
        return response

    def req(self, action, endpoint, params, session):
        """
        Send a request (CREATE READ UPDATE or DELETE)
        """
        d_actions = {
            'create': self.create,
            'read': self.read,
            'update': self.update,
            'delete': self.delete
        }
        return d_actions[action](endpoint, params, session)

    def _set_headers(self, response_headers, update_cst):
        """
        Sets headers
        """
        if update_cst:
            self.CLIENT_TOKEN = response_headers['CST']

        if 'X-SECURITY-TOKEN' in response_headers:
            self.SECURITY_TOKEN = response_headers['X-SECURITY-TOKEN']
        else:
            self.SECURITY_TOKEN = None

        self.HEADERS['LOGGED_IN'] = {
            'X-IG-API-KEY': self.API_KEY,
            'X-SECURITY-TOKEN': self.SECURITY_TOKEN,
            'CST': self.CLIENT_TOKEN,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'
        }

        self.HEADERS['DELETE'] = {
            'X-IG-API-KEY': self.API_KEY,
            'X-SECURITY-TOKEN': self.SECURITY_TOKEN,
            'CST': self.CLIENT_TOKEN,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8',
            '_method': 'DELETE'
        }


class IGService:

    D_BASE_URL = {
        'live': 'https://api.ig.com/gateway/deal',
        'demo': 'https://demo-api.ig.com/gateway/deal'
    }

    API_KEY = None
    IG_USERNAME = None
    IG_PASSWORD = None

    def __init__(self, username, password, api_key, acc_type="demo", session=None):
        """
        Constructor, calls the method required to connect to the API (accepts acc_type = LIVE or DEMO)
        """
        self.API_KEY = api_key
        self.IG_USERNAME = username
        self.IG_PASSWORD = password

        self.ig_session = None

        try:
            self.BASE_URL = self.D_BASE_URL[acc_type.lower()]
        except Exception:
            raise(Exception("Invalid account type specified, please provide LIVE or DEMO."))

        self.parse_response = self.parse_response_with_exception

        if session is None:
            self.session = Session()  # Requests Session (global)
        else:
            self.session = session

        self.crud_session = IGSessionCRUD(self.BASE_URL, self.API_KEY, self.session)

    def _get_session(self, session):
        """
        Returns a Requests session (from self.session) if session is None
        or session if it's not None (cached session with requests-cache for example)
        """
        if session is None:
            session = self.session  # requests Session
        else:
            assert(isinstance(session, Session)), "session must be <requests.session.Session object> not %s" % type(session)
            session = session
        return session

    def _req(self, action, endpoint, params, session):
        """
        Creates a CRUD request and returns response
        """
        session = self._get_session(session)
        response = self.crud_session.req(action, endpoint, params, session)
        return response

    # ---------- PARSE_RESPONSE ----------- #

    def parse_response_without_exception(self, *args, **kwargs):
        """
        Parses JSON response
        returns dict
        no exception raised when error occurs"""
        response = json.loads(*args, **kwargs)
        return response

    def parse_response_with_exception(self, *args, **kwargs):
        """
        Parses JSON response
        returns dict
        exception raised when error occurs"""
        response = json.loads(*args, **kwargs)
        if 'errorCode' in response:
            raise(Exception(response['errorCode']))
        return response

    # -------- ACCOUNT ------- #

    def fetch_account(self, accountId, session=None):
        """
        Fetch account and filter for a particular.
        """
        params = {}
        endpoint = '/accounts'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        if data is not None and data.get('accounts'):
            for account in data.get('accounts'):
                if account.get('accountId') == accountId:
                    return account

        # nothing
        return {'accountType': '', 'accountName': '', 'currency': '', 'balance': {'profitLoss': 0, 'balance': 0, 'available': 0}}

    def fetch_account_activity_by_period(self, milliseconds, session=None):
        """
        Returns the account activity history for the last specified period
        """
        milliseconds = conv_to_ms(milliseconds)
        params = {}
        url_params = {
            'milliseconds': milliseconds
        }
        endpoint = '/history/activity/{milliseconds}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_transaction_history_by_type_and_period(self, milliseconds, trans_type, session=None):
        """
        Returns the transaction history for the specified transaction type and period
        """
        milliseconds = conv_to_ms(milliseconds)
        params = {}
        url_params = {
            'milliseconds': milliseconds,
            'trans_type': trans_type
        }
        endpoint = '/history/transactions/{trans_type}/{milliseconds}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_transaction_history(self, trans_type=None, from_date=None,
                                  to_date=None, max_span_seconds=None,
                                  page_size=None, page_number=None,
                                  session=None):
        """
        Returns the transaction history for the specified transaction type and period
        """ 
        params = {}
        if trans_type:
            params['type'] = trans_type
        if from_date:
            if hasattr(from_date, 'isoformat'):
                from_date = from_date.isoformat()
            params['from'] = from_date
        if to_date:
            if hasattr(to_date, 'isoformat'):
                to_date = to_date.isoformat()
            params['to'] = to_date
        if max_span_seconds:
            params['maxSpanSeconds'] = max_span_seconds
        if page_size:
            params['pageSize'] = page_size
        if page_number:
            params['pageNumber'] = page_number

        endpoint = '/history/transactions'
        action = 'read'

        self.crud_session.HEADERS['LOGGED_IN']['Version'] = "2"
        response = self._req(action, endpoint, params, session)
        del(self.crud_session.HEADERS['LOGGED_IN']['Version'])
        data = self.parse_response(response.text)

        return data

    # -------- DEALING -------- #

    def fetch_deal_by_deal_reference(self, deal_reference, session=None, retry=True):
        """
        Returns a deal confirmation for the given deal reference
        """
        params = {}
        url_params = {
            'deal_reference': deal_reference
        }
        endpoint = '/confirms/{deal_reference}'.format(**url_params)
        action = 'read'
        for i in range(5):
            response = self._req(action, endpoint, params, session)
            if response.status_code == 404:
                # 404 error.confirms.deal-not-found Deal confirmation not found
                err_code = json.loads(response.text).get('errorCode', "")
                logger.debug(response.text)

                if err_code == "error.confirms.deal-not-found" and not retry:
                    return {}
                elif err_code == "invalid.url":
                    break

                logger.info("Deal reference %s not found, retrying." % deal_reference)
                time.sleep(1)
            else:
                break
        data = self.parse_response(response.text)
        return data

    def fetch_open_positions(self, session=None):
        """
        Returns all open positions for the active account
        """
        params = {}
        endpoint = '/positions'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data.get('positions', [])

    def close_open_position(self, deal_id, direction, epic, expiry, level, order_type, quote_id, size, session=None):
        """
        Closes one or more OTC positions
        """
        params = {
            'dealId': deal_id,
            'direction': direction,
            'epic': epic,
            'expiry': expiry,
            'level': level,
            'orderType': order_type,
            'quoteId': quote_id,
            'size': size
        }

        endpoint = '/positions/otc'
        action = 'delete'
        response = self._req(action, endpoint, params, session)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    def create_open_position(self, currency_code, direction, epic, expiry,
                             force_open, guaranteed_stop, level,
                             limit_distance, limit_level, order_type,
                             quote_id, size, stop_distance, stop_level, time_in_force,
                             deal_reference=None, session=None):
        """
        Creates an OTC position
        """
        params = {
            'currencyCode': currency_code,
            'direction': direction,
            'epic': epic,
            'expiry': expiry,
            'forceOpen': force_open,
            'guaranteedStop': guaranteed_stop,
            'level': level,
            'limitDistance': limit_distance,
            'limitLevel': limit_level,
            'orderType': order_type,
            'quoteId': quote_id,
            'size': size,
            'stopDistance': stop_distance,
            'stopLevel': stop_level
        }

        if deal_reference:
            params['dealReference'] = deal_reference

        endpoint = '/positions/otc'
        action = 'create'
        response = self._req(action, endpoint, params, session)

        if response.status_code == 200:
            res_deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(res_deal_reference)
        else:
            raise IGException(response.text)

    def update_open_position(self, limit_level, stop_level, deal_id, session=None):
        """
        Updates an OTC position
        """
        params = {
            'limitLevel': limit_level,
            'stopLevel': stop_level,
            # 'trailingStop': False,  # only in v2
            # 'trailingStopDistance': None,
            # 'trailingStopIncrement': None
        }

        url_params = {
            'deal_id': deal_id
        }
        endpoint = '/positions/otc/{deal_id}'.format(**url_params)
        action = 'update'
        response = self._req(action, endpoint, params, session)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    def fetch_working_orders(self, session=None):
        """
        Returns all open working orders for the active account
        """
        params = {}
        endpoint = '/workingorders'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def create_working_order(self, currency_code, direction, epic, expiry,
                             guaranteed_stop, level, size,
                             time_in_force, order_type,
                             limit_distance=None, limit_level=None,
                             stop_distance=None, stop_level=None,
                             good_till_date=None, deal_reference=None,
                             force_open=False, session=None):
        """
        Creates an OTC working order
        """
        VERSION = 2
        if good_till_date is not None and type(good_till_date) is not int:
            good_till_date = conv_datetime(good_till_date, VERSION)

        params = {
            'currencyCode': currency_code,
            'direction': direction,
            'epic': epic,
            'expiry': expiry,
            'goodTillDate': good_till_date,
            'guaranteedStop': guaranteed_stop,
            'forceOpen': force_open,
            'level': level,
            'size': size,
            'timeInForce': time_in_force,
            'type': order_type
        }
        if limit_distance:
            params['limitDistance'] = limit_distance
        if limit_level:
            params['limitLevel'] = limit_level
        if stop_distance:
            params['stopDistance'] = stop_distance
        if stop_level:
            params['stopLevel'] = stop_level
        if deal_reference:
            params['dealReference'] = deal_reference

        endpoint = '/workingorders/otc'
        action = 'create'

        self.crud_session.HEADERS['LOGGED_IN']['Version'] = str(VERSION)
        response = self._req(action, endpoint, params, session)
        del(self.crud_session.HEADERS['LOGGED_IN']['Version'])

        if response.status_code == 200:
            deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    def delete_working_order(self, deal_id, session=None):
        """
        Deletes an OTC working order
        """
        params = {}
        url_params = {
            'deal_id': deal_id
        }
        endpoint = '/workingorders/otc/{deal_id}'.format(**url_params)
        action = 'delete'
        response = self._req(action, endpoint, params, session)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    def update_working_order(self, good_till_date, level, limit_distance,
                             limit_level, stop_distance, stop_level,
                             time_in_force, order_type, deal_id, session=None):
        """
        Updates an OTC working order
        """
        params = {
            'goodTillDate': good_till_date,
            'limitDistance': limit_distance,
            'level': level,
            'limitLevel': limit_level,
            'stopDistance': stop_distance,
            'stopLevel': stop_level,
            'timeInForce': time_in_force,
            'type': order_type
        }
        url_params = {
            'deal_id': deal_id
        }
        endpoint = '/workingorders/otc/{deal_id}'.format(**url_params)
        action = 'update'
        response = self._req(action, endpoint, params, session)

        if response.status_code == 200:
            deal_reference = json.loads(response.text)['dealReference']
            return self.fetch_deal_by_deal_reference(deal_reference)
        else:
            raise IGException(response.text)

    # -------- MARKETS -------- #

    def fetch_client_sentiment_by_instrument(self, market_id, session=None):
        """
        Returns the client sentiment for the given instrument's market
        """
        params = {}
        url_params = {
            'market_id': market_id
        }
        endpoint = '/clientsentiment/{market_id}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_related_client_sentiment_by_instrument(self, market_id, session=None):
        """
        Returns a list of related (also traded) client sentiment for the given instrument's market
        """
        params = {}
        url_params = {
            'market_id': market_id
        }
        endpoint = '/clientsentiment/related/{market_id}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_top_level_navigation_nodes(self, session=None):
        """Returns all top-level nodes (market categories) in the market
        navigation hierarchy."""
        params = {}
        endpoint = '/marketnavigation'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        # if self.return_munch:
        #     # ToFix: ValueError: The truth value of a DataFrame is ambiguous.
        #     # Use a.empty, a.bool(), a.item(), a.any() or a.all().
        #     from .utils import munchify
        #     data = munchify(data)
        return data

    def fetch_sub_nodes_by_node(self, node, session=None):
        """Returns all sub-nodes of the given node in the market
        navigation hierarchy"""
        params = {}
        url_params = {
            'node': node
        }
        endpoint = '/marketnavigation/{node}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_market_by_epic(self, epic, session=None):
        """
        Returns the details of the given market
        """
        params = {}
        url_params = {
            'epic': epic
        }
        endpoint = '/markets/{epic}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        
        return data

    def search_markets(self, search_term, session=None):
        """Returns all markets matching the search term"""
        endpoint = '/markets'
        params = {
            'searchTerm': search_term
        }
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def fetch_historical_prices_by_epic(self, epic, resolution=None,
                                        start_date=None,
                                        end_date=None,
                                        numpoints=None,
                                        pagesize=0,
                                        pagenumber=None,
                                        session=None):
        """
        Returns a list of historical prices for the given epic, resolution, number of points
        Result datetime format : 2019/03/25 01:00:00
        """
        params = {}

        if resolution:
            params['resolution'] = resolution
        if start_date:
            params['from'] = conv_datetime(start_date, 4)
        if end_date:
            params['to'] = conv_datetime(end_date, 4)
        if numpoints:
            params['max'] = numpoints
        if pagesize:
            params['pageSize'] = pagesize
        if pagenumber:
            params['pageNumber'] = pagenumber

        endpoint = '/prices/' + epic
        action = 'read'

        self.crud_session.HEADERS['LOGGED_IN']['Version'] = "3"
        response = self._req(action, endpoint, params, session)
        del(self.crud_session.HEADERS['LOGGED_IN']['Version'])
        data = self.parse_response(response.text)

        return(data)

    def fetch_historical_prices_by_epic_and_num_points(self, epic, resolution, numpoints, session=None):
        """
        Returns a list of historical prices for the given epic, resolution, number of points
        """
        params = {}
        url_params = {
            'epic': epic,
            'resolution': resolution,
            'numpoints': numpoints
        }
        endpoint = '/prices/{epic}/{resolution}/{numpoints}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return(data)

    def fetch_historical_prices_by_epic_and_date_range(self, epic, resolution, start_date, end_date, session=None):
        """
        Returns a list of historical prices for the given epic, resolution, multiplier and date range
        """
        # v3
        start_date = conv_datetime(start_date, 4)
        end_date = conv_datetime(end_date, 4)
        params = {}
        url_params = {
            'resolution': resolution,
            'from': start_date,
            'to': end_date
        }

        # https://demo-api.ig.com/gateway/deal/prices/CS.D.EURUSD.CFD.IP?resolution=MONTH&from=2019-12-01T00%3A00%3A00
        endpoint = "/prices/%s?%s" % (epic, urllib.parse.urlencode(url_params))

        # v1
        # start_date = conv_datetime(start_date, 1)
        # end_date = conv_datetime(end_date, 1)
        # params = {
        #     'startdate': start_date,
        #     'enddate': end_date
        # }
        # url_params = {
        #     'epic': epic,
        #     'resolution': resolution
        # }
        # endpoint = "/prices/{epic}/{resolution}".format(**url_params)

        # need header version 3
        action = 'read'

        self.crud_session.HEADERS['LOGGED_IN']['Version'] = "3"
        response = self._req(action, endpoint, params, session)
        del(self.crud_session.HEADERS['LOGGED_IN']['Version'])

        data = self.parse_response(response.text)

        return data

    # -------- WATCHLISTS -------- #

    def fetch_all_watchlists(self, session=None):
        """Returns all watchlists belonging to the active account"""
        params = {}
        endpoint = '/watchlists'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def create_watchlist(self, name, epics, session=None):
        """Creates a watchlist"""
        params = {
            'name': name,
            'epics': epics
        }
        endpoint = '/watchlists'
        action = 'create'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    def delete_watchlist(self, watchlist_id, session=None):
        """Deletes a watchlist"""
        params = {}
        url_params = {
            'watchlist_id': watchlist_id
        }
        endpoint = '/watchlists/{watchlist_id}'.format(**url_params)
        action = 'delete'
        response = self._req(action, endpoint, params, session)
        return response.text

    def fetch_watchlist_markets(self, watchlist_id, session=None):
        """Returns the given watchlist's markets"""
        params = {}
        url_params = {
            'watchlist_id': watchlist_id
        }
        endpoint = '/watchlists/{watchlist_id}'.format(**url_params)
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)

        return data

    def add_market_to_watchlist(self, watchlist_id, epic, session=None):
        """Adds a market to a watchlist"""
        params = {
            'epic': epic
        }
        url_params = {
            'watchlist_id': watchlist_id
        }
        endpoint = '/watchlists/{watchlist_id}'.format(**url_params)
        action = 'update'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    def remove_market_from_watchlist(self, watchlist_id, epic, session=None):
        """Remove an market from a watchlist"""
        params = {}
        url_params = {
            'watchlist_id': watchlist_id,
            'epic': epic
        }
        endpoint = '/watchlists/{watchlist_id}/{epic}'.format(**url_params)
        action = 'delete'
        response = self._req(action, endpoint, params, session)
        return response.text

    # -------- LOGIN -------- #

    def logout(self, session=None):
        """Log out of the current session"""
        params = {}
        endpoint = '/session'
        action = 'delete'
        self._req(action, endpoint, params, session)

    def get_encryption_key(self, session=None):
        """Get encryption key to encrypt the password"""
        endpoint = '/session/encryptionKey'
        session = self._get_session(session)
        response = session.get(self.BASE_URL + endpoint, headers=self.crud_session.HEADERS['BASIC'])
        if not response.ok:
            raise IGException('Could not get encryption key for login.')
        data = response.json()
        return data['encryptionKey'], data['timeStamp']

    def encrypted_password(self, session=None):
        """Encrypt password for login"""
        key, timestamp = self.get_encryption_key(session)
        rsakey = RSA.importKey(b64decode(key))
        string = self.IG_PASSWORD + '|' + str(int(timestamp))
        message = b64encode(string.encode())
        return b64encode(PKCS1_v1_5.new(rsakey).encrypt(message))

    def create_session(self, session=None, encryption=False):
        """Creates a trading session, obtaining session tokens for subsequent API access"""
        password = self.encrypted_password(session) if encryption else self.IG_PASSWORD
        params = {
            'identifier': self.IG_USERNAME,
            'password': password
        }
        if encryption: params['encryptedPassword'] = True
        endpoint = '/session'
        action = 'create'
        # this is the first create (BASIC_HEADERS)
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        self.ig_session = data  # store IG session
        return data

    def switch_account(self, account_id, default_account, session=None):
        """
        Switches active accounts, optionally setting the default account
        """
        params = {
            'accountId': account_id,
            'defaultAccount': default_account
        }
        endpoint = '/session'
        action = 'update'
        response = self._req(action, endpoint, params, session)
        self.crud_session._set_headers(response.headers, False)
        data = self.parse_response(response.text)
        return data

    def read_session(self, session=None):
        """
        Retrieves current session details
        """
        params = {}
        endpoint = '/session'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    # -------- GENERAL -------- #

    def get_client_apps(self, session=None):
        """
        Returns a list of client-owned applications
        """
        params = {}
        endpoint = '/operations/application'
        action = 'read'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    def update_client_app(self, allowance_account_overall, allowance_account_trading, api_key, status, session=None):
        """
        Updates an application
        """
        params = {
            'allowanceAccountOverall': allowance_account_overall,
            'allowanceAccountTrading': allowance_account_trading,
            'apiKey': api_key,
            'status': status
        }
        endpoint = '/operations/application'
        action = 'update'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    def disable_client_app_key(self, session=None):
        """
        Disables the current application key from processing further requests.
        Disabled keys may be reenabled via the My Account section on
        the IG Web Dealing Platform.
        """
        params = {}
        endpoint = '/operations/application/disable'
        action = 'update'
        response = self._req(action, endpoint, params, session)
        data = self.parse_response(response.text)
        return data

    @property
    def cst(self):
        return self.crud_session.CLIENT_TOKEN

    @property
    def xst(self):
        return self.crud_session.SECURITY_TOKEN

    @property
    def lightstreamer_endpoint(self):
        return self.crud_session.lightstreamer_endpoint

    @property
    def connected(self) -> bool:
        return 'LOGGED_IN' in self.crud_session.HEADERS
