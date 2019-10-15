# @date 2018-08-26
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# HTTPS+WS connector for ig.com

import requests

from instrument.instrument import Instrument

from .rest import IGService

import logging
logger = logging.getLogger('siis.connector.ig')
error_logger = logging.getLogger('siis.error.connector.ig')


class IGConnector(object):
    """
    IG connector.
    @todo could add a REST request limit per minute
    The create order request limit of 1sec with the same value on the same market is implementated in the trader.
    """

    TF_MAP = {
        Instrument.TF_SEC: 'SECOND',
        Instrument.TF_MIN: 'MINUTE',
        Instrument.TF_2MIN: 'MINUTE_2',
        Instrument.TF_3MIN: 'MINUTE_3',
        Instrument.TF_5MIN: 'MINUTE_5',
        Instrument.TF_10MIN: 'MINUTE_10',
        Instrument.TF_15MIN: 'MINUTE_15',
        Instrument.TF_30MIN: 'MINUTE_30',
        Instrument.TF_HOUR: 'HOUR',
        Instrument.TF_2HOUR: 'HOUR_2',
        Instrument.TF_3HOUR: 'HOUR_3',
        Instrument.TF_4HOUR: 'HOUR_4',
        Instrument.TF_DAY: 'DAY',
        Instrument.TF_WEEK: 'WEEK',
        Instrument.TF_MONTH: 'MONTH'
    }

    def __init__(self, service, username, password, account_id, api_key, host="ig.com"):
        self._host = host or "ig.com"
        self._base_url = "/api/v2/"
        self._timeout = 7
        self._connected = False
        self._service = service

        self.__username = username
        self.__password = password
        self.__account_id = account_id
        self.__api_key = api_key

        self._session = None
        self._ig_service = None
        self._client_id = None

        self._account_type = "LIVE" if self._host == "api.ig.com" else "DEMO"

    @property
    def username(self):
        return self.__username

    def connect(self):
        if self.connected:
            return

        self._session = requests.Session()

        self._ig_service = IGService(
            self.__username,
            self.__password,
            self.__api_key,
            self._account_type,
            self._session)

        try:
            res = self._ig_service.create_session()
            self._client_id = res.get('clientId')
        except Exception as e:
            self._session = None
            self._ig_service = None

            raise e

    def disconnect(self):
        self._ig_service = None
        self._session = None

    @property
    def client_id(self):
        return self._client_id

    @property
    def connected(self):
        return self._session is not None and self._ig_service is not None and self._ig_service.connected

    def update_session(self):
        """
        Every 6h we have to update the user session.
        """
        try:
            res = self._ig_service.create_session()
            self._client_id = res.get('clientId')
        except:
            self._session = None
            self._ig_service = None

    def funds(self):
        return self._ig_service.fetch_account(self.__account_id)

    def positions(self):
        positions = self._ig_service.fetch_open_positions()
        return positions

    def orders(self):
        orders = self._ig_service.fetch_working_orders()
        return orders

    def market(self, instrument):
        market = self._ig_service.fetch_market_by_epic(instrument)
        return market

    def history_range(self, market_id, tf, from_date, to_date):
        # history = self._ig_service.fetch_historical_prices_by_epic(market_id, IGConnector.TF_MAP[tf], from_date, to_date)  # V3 format
        history = self._ig_service.fetch_historical_prices_by_epic_and_date_range(market_id, IGConnector.TF_MAP[tf], from_date, to_date)
        return history

    def history_last_n(self, market_id, tf, n):
        history = self._ig_service.fetch_historical_prices_by_epic_and_num_points(market_id, IGConnector.TF_MAP[tf], n)
        return history

    @property
    def ig(self):
        return self._ig_service 

    @property
    def cst(self):
        if self._ig_service:
            return self._ig_service.cst
        else:
            return None

    @property
    def xst(self):
        if self._ig_service:
            return self._ig_service.xst
        else:
            return None

    @property
    def lightstreamer_endpoint(self):
        if self._ig_service:        
            return self._ig_service.lightstreamer_endpoint
        else:
            return None
