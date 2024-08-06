# @date 2024-08-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# dailyfx.com watcher implementation

import json
from typing import Optional, List, Union

import os
import time
import copy
import requests
import traceback

from datetime import datetime, timedelta, date

from common.utils import parse_datetime, UTC
from database.database import Database

from watcher.event import BaseEvent, EconomicEvent
from watcher.fetcher import Fetcher
from watcher.service import WatcherService

import logging

logger = logging.getLogger('siis.fetcher.dailyfx')
error_logger = logging.getLogger('siis.error.fetcher.dailyfx')
traceback_logger = logging.getLogger('siis.traceback.fetcher.dailyfx')


class DailyFxFetcher(Fetcher):
    """
    DailyFx history and latest calendar economic fetcher.

    @note url example https://www.dailyfx.com/economic-calendar/events/2023-08-02
    """

    PROTOCOL = "https:/"
    BASE_URL = "www.dailyfx.com/economic-calendar/events"

    FETCH_DELAY = 1.0

    FILTER_CATEGORIES = [
        "country",
        "symbol",
        "importance",   # low, high, medium
        "currency"
    ]

    WRITE_TO_LOCAL_CACHE = False
    READ_FROM_LOCAL_CACHE = False
    LOCAL_CACHE_DIR = "dailyfx"   # from "user-path"

    CURRENCIES = [
        "AUD",
        "EUR",
        "BRL",
        "CAD",
        "CNY",
        "COP",
        "CZK",
        "DKK",
        "HKD",
        "HUF",
        "IDR",
        "JPY",
        "MXN",
        "NZD",
        "NOK",
        "PHP",
        "PLN",
        "RUB",
        "SGD",
        "ZAR",
        "KRW",
        "SEK",
        "CHF",
        "TWD",
        "THB",
        "GBP",
        "USD",
        "ILS",
        "INR",
    ]

    SYMBOLS_USD_LVL3 = [
        "NAPMPMI",  # ISM Manufacturing PMI
        "FDTR",  # FOMC Minutes
        "NFP TCH",  # Non Farm Payrolls
        "USURTOT",  # Unemployment Rate
        "UNITEDSTANONMANPMI",  # ISM Services PMI
        "CPI YOY",  # Inflation Rate YoY
        "USACORECPIRATE",  # Core Inflation Rate YoY
        "USAPPIM",  # PPI MoM
        "RSTAMOM",  # Retail Sales MoM
        "UNITEDSTABUIPER",  # Building Permits Prel
        "CONCCONF",  # Michigan Consumer Sentiment Prel
        "UNITEDSTADURGOOORD",  # Durable Goods Orders MoM
        "GDP CQOQ",  # GDP Growth Rate QoQ Adv
        "USACPPIAC",  # Core PCE Price Index YoY
        "USAPPIAC",  # PCE Price Index YoY
        # "",  # CB Consumer Confidence
    ]

    SYMBOLS_EUR_LVL3 = [
        "GERMANYUNECHA",  # Unemployment Change
        "GRUEPR",  # Unemployment Rate
        "GRBC20YY",  # Inflation Rate YoY Prel
        "FRCPIYOY",  # Inflation Rate YoY Prel
        "ITCPNICY",  # Inflation Rate YoY Prel
        "EUROAREACORINFRAT",  # Core Inflation Rate YoY Flash
        "DEUFYGG",  # Full Year GDP Growth
        "EUROAREAZEWECOSENIND",  # ZEW Economic Sentiment Index
        "GERMANYZEWECOSENIND",  # ZEW Economic Sentiment Index
        "EURR002W",  # ECB Monetary Policy Meeting Accounts
        "GRCCI",  # GfK Consumer Confidence
        "GRIFPBUS",  # IFO Business Climate
        "GRGDPPGY",  # GDP Growth Rate YoY Flash
        "EUGNEMUQ",  # GDP Growth Rate QoQ Flash
        "EUGNEMUY",  # GDP Growth Rate YoY Flash
        "ITPIRLYS",  # GDP Growth Rate YoY Adv
        "ITAFYGG",  # Full Year GDP Growth
        "WCSDITA",  # Government Budget
        "GERMANYMANPMI",  # HCOB Manufacturing PMI Flash
        # "",  # Euro Summit
    ]

    SYMBOLS_USD_LVL2 = [
        "UNITEDSTAMANPMI",  # S&P Global Manufacturing PMI Final
        "UNITEDSTACONTSPE",  # Construction Spending MoM
        "UNITEDSTAMORRAT",  # MBA 30-Year Mortgage Rate
        "UNITEDSTAMORAPP",  # MBA Mortgage Applications
        "UNITEDSTAADPEMPCHA",  # ADP Employment Change
        "UNITEDSTACONJOBCLA",  # Continuing Jobless Claims
        "IJCUSA",  # Initial Jobless Claims
        "TBEXTOT",  # Exports
        "TBIMTOT",  # Imports
        "USTBTOT",  # Balance of Trade
        "FDTR",  # Fed Bostic Speech
        "UNITEDSTACOMPMI",  # S&P Global Composite PMI Final
        "UNITEDSTASERPMI",  # S&P Global Services PMI Final
        "UNITEDSTAAVEHOUEAR",  # Average Hourly Earnings MoM
        "UNITEDSTAAVEWEEHOU",  # Average Weekly Hours
        "UNITEDSTANONPAY-PRI",  # Nonfarm Payrolls Private
        "UNITEDSTALABFORPARRA",  # Participation Rate
        "USAAHEY",  # Average Hourly Earnings YoY
        "USAINME",  # ISM Non-Manufacturing Employment
        "UNITEDSTAFACORD",  # Factory Orders MoM
        "UNITEDSTACONCRE",  # Consumer Credit Change
        "UNITEDSTAWHOINV",  # Wholesale Inventories MoM
        "UNITEDSTAINFRATMOM",  # Inflation Rate MoM
        "USACIRM",  # Core Inflation Rate MoM
        "UNITEDSTACONPRIINDCP",  # CPI
        "UNITEDSTAGOVBUDVAL",  # Monthly Budget Statement
        "USARSEGAAM",  # Retail Sales Ex Gas/Autos MoM
        "UNITEDSTARETSALEXAUT",  # Retail Sales Ex Autos MoM
        "IP YOY",  # Industrial Production YoY
        "UNITEDSTAINDPROMOM",  # Industrial Production MoM
        "UNITEDSTABUSINV",  # Business Inventories MoM
        "UNITEDSTANAHHOUMARIN",  # NAHB Housing Market Index
        "UNITEDSTANETLONTICFL",  # Net Long-term TIC Flows
        "USABPM",  # Building Permits MoM Prel
        "USAHSMOM",  # Housing Starts MoM
        "UNITEDSTAPHIFEDMANIN",  # Philadelphia Fed Manufacturing Index
        "USAEHSM",  # Existing Home Sales MoM
        # "",  # CB Leading Index MoM
        "UNITEDSTABUIPER",  # Building Permits Final
        "UNITEDSTACHIFEDNATAC",  # Chicago Fed National Activity Index
        "UNITEDSTAGOOTRABAL",  # Goods Trade Balance Adv
        "USARIEA",  # Retail Inventories Ex Autos MoM Adv
        "UNITEDSTADURGOOORDEX",  # Durable Goods Orders Ex Transp MoM
        "UNITEDSTAGDPDEF",  # GDP Price Index QoQ Adv
        "USAPPQ",  # PCE Prices QoQ Adv
        "USACPPQ",  # Core PCE Prices QoQ Adv
        "USANHSM",  # New Home Sales MoM
        "USACPPIM",  # Core PCE Price Index MoM
        "USAPPIMC",  # PCE Price Index MoM
        "UNITEDSTAPERINC",  # Personal Income (MoM)
        "UNITEDSTAPERSPE",  # Personal Spending MoM
        "UNITEDSTAPENHOMSAL",  # Pending Home Sales YoY
        "USAECIW",  # Employment Cost - Wages QoQ
        "USAECIB",  # Employment Cost - Benefits QoQ
        "USAHPIM",  # House Price Index MoM
        "USACSA",  # CPI s.a
        "UNITEDSTACORPRO",  # Corporate Profits QoQ
        "UNITEDSTAECOOPTIND",  # RCM/TIPP Economic Optimism Index
        "USAPPIM",  # PPI MoM Final
    ]

    SYMBOLS_EUR_LVL2 = [
        "SPAINMANPMI",  # S&P Global Manufacturing PMI
        "UMRTAT",  # Unemployment  Rate
        "ITALYMANPMI",  # S&P Global Manufacturing PMI
        "FRANCEMANPMI",  # S&P Global Manufacturing PMI Final
        "GERMANYMANPMI",  # S&P Global Manufacturing PMI Final
        "EUROAREAMANPMI",  # S&P Global Manufacturing PMI Final
        "SPAINUNECHA",  # Unemployment Change
        "GERMANYUNEPER",  # Unemployed Persons
        "GERMANYINFRATMOM",  # Inflation Rate MoM Prel
        "FRANCEINFRATMOM",  # Inflation Rate MoM Prel
        "FRCCI",  # Consumer Confidence
        "SPAINSERPMI",  # S&P Global Services PMI
        "ITALYSERPMI",  # S&P Global Services PMI
        "FRANCESERPMI",  # S&P Global Services PMI Final
        "GERMANYSERPMI",  # S&P Global Services PMI Final
        "EUROAREASERPMI",  # S&P Global Services PMI Final
        "GRTBALE",  # Balance of Trade
        "GERMANYCONPMI",  # S&P Global Construction PMI
        "ITALYINFRATMOM",  # Inflation Rate MoM Prel
        "SpainBC",  # Business Confidence
        "NECPIYOY",  # Inflation Rate YoY Prel
        "DEURetailSalesYoY",  # Retail Sales YoY
        "EMURetailSalesYoY",  # Retail Sales YoY
        "EUROAREAECOOPTIND",  # Economic Sentiment
        "EUCCEMU",  # Consumer Confidence Final
        "EUROAREAINDSEN",  # Industrial Sentiment
        "EUROAREAINFRATMOM",  # Inflation Rate MoM Flash
        "ECCPEMUY",  # Inflation Rate YoY Flash
        "FRTEBAL",  # Balance of Trade
        "UMRTIT",  # Unemployment Rate
        "UMRTEMU",  # Unemployment Rate
        "FRANCEINDPROMOM",  # Industrial Production MoM
        "EURR002W",  # ECB Schnabel Speech
        "ITARetailSalesMoM",  # Retail Sales MoM
        "GDBR10",  # 10-Year Bund Auction
        "FRCPIYOY",  # Inflation Rate YoY Final
        "ITPRWAY",  # Industrial Production YoY
        "ITALYINDPROMOM",  # Industrial Production MoM
        "EUIPEMUY",  # Industrial Production YoY
        "XTTBEZ",  # Balance of Trade
        "SPAINCC",  # Consumer Confidence
        # "",  # Eurogroup Meeting
        "EUROPEANUCAL",  # ECOFIN Meeting
        "ITCPNICY",  # Inflation Rate YoY Final
        "DEUZCC",  # ZEW Current Conditions
        "EUROPEANUCARREG",  # New Car Registrations YoY
        "ITTRBSAT",  # Balance of Trade
        "NEUETOTR",  # Unemployment Rate
        "SPTBEUBL",  # Balance of Trade
        "NECCI",  # Consumer Confidence
        "INSESYNT",  # Business Confidence
        "FRANCEINIJOBCLA",  # Unemployment Benefit Claims
        "UMRTES",  # Unemployment Rate
        "ITPSSA",  # Consumer Confidence
        "ITBCI",  # Business Confidence
        "SPNAGDPQ",  # GDP Growth Rate QoQ Flash
        "SPNAGDPY",  # GDP Growth Rate YoY Flash
        "SPIPCYOY",  # Inflation Rate YoY Prel
        "SPAININFRATMOM",  # Inflation Rate MoM Prel
        "GRGDPPGQ",  # GDP Growth Rate QoQ Flash
        "ITPIRLQS",  # GDP Growth Rate QoQ Adv
        "EUROAREALENRAT",  # Marginal Lending Rate
        "EUROAREADEPINTRAT",  # Deposit Facility Rate
        "FIGDPYOY",  # GDP Growth Rate YoY Prel
        "UMRTFR",  # Unemployment Rate
        "NEGDPEY",  # GDP Growth Rate YoY Flash
        "NEGDPEQ",  # GDP Growth Rate QoQ Flash
        "GRTBEXE",  # Exports MoM
        "WDEBEURO",  # Government Budget to GDP
        "ITPIRLYS",  # GDP Growth Rate YoY 2nd Estimate
        "FRANCECOMPMI",  # HCOB Composite PMI Flash
        "GERMANYCOMPMI",  # HCOB Composite PMI Flash
        "EUROAREACOMPMI",  # HCOB Composite PMI Flash
    ]

    SYMBOLS = set(SYMBOLS_USD_LVL3 + SYMBOLS_EUR_LVL3 + SYMBOLS_USD_LVL2 + SYMBOLS_EUR_LVL2)

    COUNTRIES = [
        "United States",
        "Euro Area",
        "United Kingdom",
        "Hong Kong",
        "France",
        "Spain",
        "Germany",
        "Italy",
        "China",
        "Hong Kong",
        "Mexico",
        "Czech Republic",
        "Switzerland",
        "South Korea",
        "Ireland",
        "Indonesia",
        "Japan",
        "Philippines",
        "Taiwan",
        "Thailand",
        "Australia",
        "Netherlands",
        "India",
        "Singapore",
        "Norway",
        "Russia",
        "Hungary",
        "Sweden",
        "Austria",
        "Hungary",
        "Poland",
        "Greece",
        "South Africa",
        "Portugal",
        "Israel",
        "Brazil",
        "Canada",
        "Colombia",
    ]

    MEANINGS = {
        "UNKNOWN": -2,
        "NEUTRAL": 0,
        "NEGATIVE": -1,
        "POSITIVE": 1
    }

    def __init__(self, service: WatcherService):
        super().__init__("dailyfx.com", service)

        self._host = "dailyfx.com"
        self._connector = None
        self._session = None

        self._cache_data_path = os.path.join(service.user_path, self.LOCAL_CACHE_DIR)

    def connect(self):
        super().connect()

        try:
            # identity = self.service.identity(self._name)

            if self._session is None:
                self._session = requests.Session()

                self._session.headers.update({'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'})

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

            self._connector = None

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        # return self._connector is not None and self._connector.connected
        return self._session

    def disconnect(self):
        super().disconnect()

        try:
            if self._session:
                self._session = None

            if self._connector:
                self._connector.disconnect()
                self._connector = None

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    #
    # fetch events
    #

    def fetch_events(self, event_type: int, from_date: Optional[datetime], to_date: Optional[datetime],
                     filters: Optional[List]):
        if not from_date:
            from_date = datetime.today().replace(tzinfo=UTC())
        if not to_date:
            to_date = datetime.today().replace(tzinfo=UTC())

        begin = from_date
        end = to_date

        curr = copy.copy(begin)
        delta = timedelta(days=1)

        count = 0

        if event_type == BaseEvent.EVENT_TYPE_ECONOMIC:
            while curr <= end:
                if self.READ_FROM_LOCAL_CACHE:
                    # only for testing from cached files
                    try:
                        filename = os.path.join(self._cache_data_path, curr.strftime("%Y%m%d")+".json")
                        if os.path.exists(filename):
                            with open(filename, "r") as f:
                                data = json.load(f)
                                self.store_calendar_events(data, filters, curr)
                    except IOError as e:
                        error_logger.error(repr(e))
                else:
                    url = '/'.join((self.PROTOCOL, self.BASE_URL, curr.strftime("%Y-%m-%d")))
                    try:
                        response = self._session.get(url)
                        if response.status_code == 200:
                            data = response.json()

                            # only store current day events
                            count += self.store_calendar_events(data, filters, curr)

                            if self.WRITE_TO_LOCAL_CACHE:
                                try:
                                    filename = os.path.join(self._cache_data_path, curr.strftime("%Y%m%d") + ".json")
                                    with open(filename, "w") as f:
                                        f.write(data)
                                except IOError as e:
                                    error_logger.error(repr(e))

                    except requests.RequestException as e:
                        error_logger.error(repr(e))

                    time.sleep(self.FETCH_DELAY)

                curr = curr + delta

        return count

    # done = []

    #
    # helpers
    #

    @staticmethod
    def parse_and_filter_economic_events(data: dict, filters: List, date_filter: Union[date, datetime] = None):
        """
        Each filter is a tuple with (category, List[values])

        Tokens :

        "id":"355248"
        "ticker":"UNITEDSTAMANPMI"
        "symbol":"UNITEDSTAMANPMI"
        "date":"2024-08-01T13:45"  ->  "%Y-%m-%dT%H:%M"
        "title":"S&P Global Manufacturing PMI Final"
        "description":"The S&P Global US Manufacturing PMI ... ."
        "importance":"medium"
        "previous":"51.6"
        "forecast":"49.5"
        "country":"United States"
        "actual":"49.6"
        "allDayEvent":false
        "currency":"USD"
        "reference":"Jul"  -> "%b"
        "revised":""  ->
        "economicMeaning" :
            "actual":"NEUTRAL"
            "previous":"UNKNOWN"
        "lastUpdate":"2024-08-01T13:45"  ->  "%Y-%m-%dT%H:%M"
        "importanceNum": 2  -> 1,2,3

        @param data:
        @param filters:
        @param date_filter:
        @return:
        """
        events = []

        for d in data:
            keep = 0

            event_date = parse_datetime(d.get('date', ""))
            if event_date is None:
                continue

            if date_filter:
                if (event_date.year != date_filter.year or
                        event_date.month != date_filter.month or
                        event_date.day != date_filter.day):
                    continue

            for _filter in filters:
                if _filter[0] not in DailyFxFetcher.FILTER_CATEGORIES:
                    continue

                if not _filter[1]:
                    continue

                value = d.get(_filter[0])
                if value in _filter[1]:
                    keep += 1

            if keep == len(filters):
                event = EconomicEvent()

                event.code = d.get('symbol', "")
                event.date = event_date.replace(tzinfo=UTC())
                event.title = d.get('title', "")
                event.level = d.get('importanceNum', 0)
                event.country = d.get('country', "")
                event.currency = d.get('currency', "")
                event.previous = d.get('previous', "")
                event.actual = d.get('actual', "")
                event.forecast = d.get('forecast', "")
                event.reference = d.get('reference', "")  # datetime.strptime(d.get('reference', ""), "%b").month if d.get('reference') else 0
                event.actual_meaning = DailyFxFetcher.MEANINGS.get(d.get('economicMeaning', {}).get('actual', "UNKNOWN"), -2)
                event.previous_meaning = DailyFxFetcher.MEANINGS.get(d.get('economicMeaning', {}).get('previous', "UNKNOWN"), -2)

                events.append(event)

        return events

    @staticmethod
    def store_calendar_events(data, filters: List, date_filter: date) -> int:
        if not data:
            return 0

        filtered_objects = DailyFxFetcher.parse_and_filter_economic_events(data, filters, date_filter)

        # for evt in filtered_objects:
        #     print(evt.__dict__)

        # only to list any codes and currencies
        # for evt in filtered_objects:
        #     # if evt.currency not in self.done:
        #     #     self.done.append(evt.currency)
        #     #     print("\"%s\"," % evt.currency)
        #
        #     # if evt.code not in self.done:
        #     #     self.done.append(evt.code)
        #     #     print("\"%s\",  # %s" % (evt.code, evt.title))

        Database.inst().store_economic_event(filtered_objects)

        return len(filtered_objects)
