# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Storage service

import os
import json
import time
import threading
import copy
import traceback
import pathlib

from watcher.service import WatcherService

from instrument.instrument import Candle

from trader.market import Market
from trader.asset import Asset

from config import utils

from .tickstorage import TickStorage, TickStreamer
from .ohlcstorage import OhlcStorage, OhlcStreamer

import logging
logger = logging.getLogger('siis.database')


class DatabaseException(Exception):
    pass


class Database(object):
    """
    Persistance database.
    Timestamp during storing are in ms except if there is an object (not raw data).
    Timestamp fetched are in accordance with the object property (mostly second timestamp).

    @todo store maker/taker fee and commission for each market
    ://www.postgresqltutorial.com/postgresql-python/connect/

    All markets information are stored in postgresql DB.
    User asset are stored in postgresql DB.
    User trades and stored in postgresl DB.
    OHLC are stored in posgresql DB.

    Ticks are run in exclusive read or write mode :
        - first case is when watcher or fetcher are writing some news data.
        - second case is during backtesting, streaming data from ticks.

    PosgreSQL DB creation :

    CREATE DATABASE siis;
    CREATE USER siis WITH ENCRYPTED PASSWORD 'siis';
    GRANT ALL PRIVILEGES ON DATABASE siis TO siis;

    OHLCs
    =======

    Prefered ohlc of interest are 1m, 5m, 15m, 1h, 4h, daily, weekly.

        - Weekly, daily, 4h and 3h ohlc are always kept and store in the SQL DB.
        - 2h, 1h and 45m ohlc are kept for 90 days (if the cleaner is executed).
        - 30m, 15m, 10m are kept for 21 days.
        - 5m, 3m, 1m are kept for 8 days.
        - 1s, 10s are never kept.

    Optimizer can be used to detect gaps.
    Cleaner delete older ohlc according to previously defined rules.

    Ticks
    =====

    Ticks are stored per market into mutliple text files that can be optimized.
    Organisation is one file per month.

    They essentially exists for backtesting purpose. But could serve as source to recreate ohlc also.
    They are stored in live by the watcher because its difficult to fetch historical data on most of the brokers.

    Optimizer can be used to detect gaps, but some crypto market have few trades per hours.

    If you launch many watcher writing to the same market it could multiply the ticks entries,
    or if you make a manual fetch of a specific market. Then the tick file will be broken and need to be optimized or re-fetched.
    """
    __instance = None

    @classmethod
    def inst(cls):
        if Database.__instance is None:
            Database.__instance = Database()

        return Database.__instance

    @classmethod
    def terminate(cls):
        if Database.__instance is not None:
            Database.__instance.close()
            Database.__instance = None

    @classmethod
    def create(cls, options):
        config = utils.load_config(options, 'databases')

        if config['siis'].get('type', 'mysql') == 'mysql':
            from .mysql import MySql
            Database.__instance = MySql()

        elif config['siis'].get('type', 'pgsql') == 'pgsql':
            from .pgsql import PgSql
            Database.__instance = PgSql()

        else:
            raise ValueError("Unknown DB type")

    def __init__(self):
        Database.__instance = self

        self._mutex = threading.RLock()
        self._condition = threading.Condition()
        self._running = False
        self._thread = threading.Thread(name="db", target=self.run)

        self._db = None

        self._pending_market_info_insert = []
        self._pending_market_info_select = []
        self._pending_market_list_select = []

        self._pending_asset_insert = []
        self._pending_asset_select = []

        self._pending_ohlc_insert = []
        self._pending_ohlc_select = []

        self._pending_user_trade_insert = []
        self._pending_user_trade_select = []
        self._pending_user_trade_delete = []

        self._pending_user_trader_insert = []
        self._pending_user_trader_select = []

        self._pending_liquidation_insert = []

        self._last_tick_flush = 0
        self._last_ohlc_flush = 0
        self._last_ohlc_clean = time.time()

        self._markets_path = None
        self._tick_storages = {}    # TickStorage per market
        self._pending_tick_insert = set()

        self._autocleanup = False
        self._fetch = False

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def setup(self, options):
        # load database
        config = utils.load_config(options, 'databases')

        self._autocleanup = config.get('auto-cleanup', False)

        self.connect(config)

        # optionnal tables creation
        self.setup_market_sql()
        self.setup_userdata_sql()
        self.setup_ohlc_sql()

        # keep data path for usage in per market DB location
        self._markets_path = pathlib.Path(options['markets-path'])

        # start the thread
        self._running = True
        self._thread.start()

        # is fetch mode fush tick continueously
        self._fetch = options.get('fetch', False)

    def connect(self, config):
        """
        Connection to the database host.
        """
        pass

    def disconnect(self):
        """
        Close the connection to the database host and cleanup.
        """        
        pass

    @property
    def connected(self):
        return False

    def close(self):
        if self.connected:
            # wait until all insertions
            self.lock()

            while self._pending_ohlc_insert or self._pending_asset_insert or self._pending_market_info_insert:
                self._last_ohlc_flush = 0  # force flush remaining non stored ohlc
                self.unlock()

                with self._condition:
                    self._condition.notify()
                    
                time.sleep(0.1)
                self.lock()

            self.unlock()

        # wake-up and join the thread
        self._running = False
        with self._condition:
            self._condition.notify()

        if self._thread:
            self._thread.join()
            self._thread = None

        if self.connected:
            self.disconnect()

        # flush remaining ticks
        with self._mutex:
            for k, tick_storage in self._tick_storages.items():
                tick_storage.flush()
                tick_storage.close()

            self._tick_storages = {}
            self._pending_tick_insert = set()

    def setup_market_sql(self):
        pass

    def setup_userdata_sql(self):
        pass

    def setup_ohlc_sql(self):
        pass

    #
    # asyncs saves
    #

    def store_market_trade(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            str bid (>= 0)
            str ask (>= 0)
            str volume (>= 0)
        """
        with self._mutex:
            # store market per keyed array
            key = data[0]+'/'+data[1]
            tickstorage = self._tick_storages.get(key)

            if not tickstorage:
                tickstorage = TickStorage(self._markets_path, data[0], data[1])
                self._tick_storages[key] = tickstorage

            tickstorage.store(data)

            # pending list of TickStorage controller having data to process to avoid to check everyone
            self._pending_tick_insert.add(tickstorage)

        with self._condition:
            self._condition.notify()

    def num_pending_ticks_storage(self):
        """
        Return current pending tick list size, for storage.
        """
        with self._mutex:
            n = len(self._pending_tick_insert)
            return n

    def store_market_ohlc(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            integer timeframe (time unit in seconds)        
            str bid_open, bid_high, bid_low, bid_close (>= 0)
            str ask_open, ask_high, ask_low, ask_close (>= 0)
            str volume (>= 0)

        @note Replace if exists.
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_ohlc_insert.extend(data)
            else:
                self._pending_ohlc_insert.append(data)

        with self._condition:
            self._condition.notify()

    def store_market_liquidation(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            integer direction (-1 or 1)
            str price > 0
            str quantity > 0
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_liquidation_insert.extend(data)
            else:
                self._pending_liquidation_insert.append(data)

        with self._condition:
            self._condition.notify()

    def store_market_info(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            str symbol (not empty)
            int market_type
            int unit_type
            int contract_type
            int trade_type
            int orders
            str base (not empty)
            str base_display (not empty)
            int base_precision (not empty)
            str quote (not empty)
            str quote_display (not empty)
            int quote_precision (not empty)
            str expiry
            int timestamp (or 0)
            str lot_size
            str contract_size
            str base_exchange_rate
            str value_per_pip
            str one_pip_means
            str margin_factor decimal as string or '-' for no margin
            str min_size
            str max_size
            str step_size
            str min_notional
            str max_notional
            str step_notional
            str min_price
            str max_price
            str step_price
            str maker_fee
            str taker_fee
            str maker_commission
            str taker_commission
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_market_info_insert.extend(data)
            else:
                self._pending_market_info_insert.append(data)

        with self._condition:
            self._condition.notify()

    #
    # asyncs loads
    #

    def load_market_ohlc(self, service, broker_id, market_id, timeframe, from_datetime=None, to_datetime=None):
        """
        Load a set of market ohlc, fill the intermetiades missing ohlcs if necessary
        @param service to be notified once done
        @param from_datetime Timestamp in ms
        @param to_datetime Timestamp in ms
        """
        with self._mutex:
            from_ts = int(from_datetime.timestamp() * 1000) if from_datetime else None
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            self._pending_ohlc_select.append((service, broker_id, market_id, timeframe, from_ts, to_ts, None))

        with self._condition:
            self._condition.notify()

    def load_market_ohlc_last_n(self, service, broker_id, market_id, timeframe, last_n):
        """
        Load a set of market ohlc, fill the intermetiades missing ohlcs if necessary
        @param service to be notified once done
        @param last_n last max n ohlcs to load
        """
        with self._mutex:
            self._pending_ohlc_select.append((service, broker_id, market_id, timeframe, None, None, last_n))

        with self._condition:
            self._condition.notify()

    def load_market_info(self, service, broker_id, market_id):
        """
        Load a specific market info given its market id.
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_market_info_select.append((service, broker_id, market_id))

        with self._condition:
            self._condition.notify()

    def load_market_list(self, service, broker_id):
        """
        Load the complete list of market available for a specific broker id.
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_market_list_select.append((service, broker_id))

        with self._condition:
            self._condition.notify()

    #
    # Tick and ohlc streamer
    #

    def create_tick_streamer(self, broker_id, market_id, from_date, to_date, buffer_size=32768):
        """
        Create a new tick streamer.
        """
        return TickStreamer(self._markets_path, broker_id, market_id, from_date, to_date, buffer_size, True)

    def create_ohlc_streamer(self, broker_id, market_id, timeframe, from_date, to_date, buffer_size=8192):
        """
        Create a new tick streamer.
        """
        return OhlcStreamer(self._db, broker_id, market_id, timeframe, from_date, to_date, buffer_size)

    #
    # User
    # 

    def store_asset(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str asset_id (not empty) identifier of the asset
            str last_trade_id (not empty) unique identifier when average price was updated
            int timestamp (or 0) of the last PRU update in (ms)
            str quantity (last update quantity)
            str price (average unit price cost)
            str quote_symbol (not empty) symbol of the quote used for the average price
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_asset_insert.extend(data)
            else:
                self._pending_asset_insert.append(data)

        with self._condition:
            self._condition.notify()

    def load_assets(self, service, trader, broker_id, account_id):
        """
        Load all asset for a specific broker_id
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_asset_select.append((service, trader, broker_id, account_id))

        with self._condition:
            self._condition.notify()

    def store_user_trade(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str market_id (not empty)
            str appliance_id (not empty)
            integer trade_id (not empty)
            integer trade_type (not empty)
            dict data (to be json encoded)
            dict operations (to be json encoded)
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_user_trade_insert.extend(data)
            else:
                self._pending_user_trade_insert.append(data)

        with self._condition:
            self._condition.notify()

    def load_user_trades(self, service, appliance, broker_id, account_id, appliance_id):
        """
        Load all user trades data and options for a specific appliance_id / broker_id / account_id
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_user_trade_select.append((service, appliance, broker_id, account_id, appliance_id))

        with self._condition:
            self._condition.notify()

    def clear_user_trades(self, broker_id, account_id, appliance_id):
        """
        Delete all user trades data and options for a specific appliance_id / broker_id / account_id
        """
        with self._mutex:
            self._pending_user_trade_delete.append((broker_id, account_id, appliance_id))

        with self._condition:
            self._condition.notify()

    def store_user_trader(self, data):
        """
        @param data is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str market_id (not empty)
            str appliance_id (not empty)
            integer activity (not null)
            dict data (to be json encoded)
            dict regions (to be json encoded)
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_user_trader_insert.extend(data)
            else:
                self._pending_user_trader_insert.append(data)

        with self._condition:
            self._condition.notify()

    def load_user_traders(self, service, appliance, broker_id, account_id, appliance_id):
        """
        Load all user traders data and options for a specific appliance_id / broker_id / account_id
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_user_trader_select.append((service, appliance, broker_id, account_id, appliance_id))

        with self._condition:
            self._condition.notify()

    #
    # Processing
    #

    def run(self):
        while self._running:
            with self._condition:
                self._condition.wait()

            if self.connected:
                self.process_userdata()
                self.process_market()
                self.process_ohlc()

            self.process_tick()

    def process_market(self):
        pass

    def process_userdata(self):
        pass

    def process_ohlc(self):
        pass

    def process_tick(self):
        with self._mutex:
            pti = self._pending_tick_insert
            self._pending_tick_insert = set()

        for tick_storage in pti:
            if self._fetch or tick_storage.can_flush():
                if tick_storage.has_data():
                    tick_storage.flush(close_at_end=not self._fetch)

                if tick_storage.has_data():
                    # data remaining
                    with self._mutex:
                        self._pending_tick_insert.add(tick_storage)
