# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Storage service

from __future__ import annotations

from typing import Tuple, Optional, Union, List

import os
import json
import time
import threading
import pathlib
from datetime import datetime

from importlib import import_module

from strategy.indicator.models import Limits, VolumeProfile

from config import utils

from .tickstorage import TickStorage, TickStreamer, FirstTickFinder, LastTickFinder
from .ohlcstorage import OhlcStreamer
from .quotestorage import QuoteStorage, QuoteStreamer, LastQuoteFinder

import logging
logger = logging.getLogger('siis.database')
error_logger = logging.getLogger('siis.database.error')


class DatabaseException(Exception):
    pass


class Database(object):
    """
    Persistence database.
    Timestamp during storing are in ms except if there is an object (not raw data).
    Timestamp fetched are in accordance with the object property (mostly second timestamp).

    @todo store maker/taker fee and commission for each market

    All markets information are stored in postgresql DB.
    User asset are stored in postgresql DB.
    User trades and stored in postgresql DB.
    OHLC are stored in postgresql DB.

    Ticks are run in exclusive read or write mode :
        - first case is when watcher or fetcher are writing some news data.
        - second case is during backtesting, streaming data from ticks.

    OHLCs
    =======

    Preferred ohlc of interest are 1m, 5m, 15m, 1h, 4h, daily, weekly.

        - Weekly, daily, 4h and 3h ohlc are always kept and store in the SQL DB.
        - 2h, 1h and 45m ohlc are kept for 90 days (if the cleaner is executed).
        - 30m, 15m, 10m are kept for 21 days.
        - 5m, 3m, 1m are kept for 8 days.
        - 1s, 10s are never kept.

    Optimizer can be used to detect gaps.
    Cleaner delete older ohlc according to previously defined rules.

    Ticks
    =====

    Ticks are stored per market into multiple text files that can be optimized.
    Organisation is one file per month.

    They essentially exists for backtesting purpose. But could serve as source to recreate ohlc also.
    They are stored in live by the watcher because its difficult to fetch historical data on most of the brokers.

    Optimizer can be used to detect gaps, but some crypto market have few trades per hours.

    If you launch many watcher writing to the same market it could multiply the ticks entries,
    or if you make a manual fetch of a specific market. Then the tick file will be broken and need to be optimized
    or re-fetched.
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
    def create(cls, options: dict):
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
        self._pending_user_closed_trade_insert = []

        self._pending_liquidation_insert = []

        self._last_ohlc_flush = 0
        self._last_ohlc_clean = time.time()

        self._markets_path = None   # path where data are stored into files (ticks, quotes, cached indicators)

        self._tick_storages = {}    # TickStorage per market
        self._pending_tick_insert = set()

        self._quote_storages = {}   # QuoteStorage per market
        self._pending_quote_insert = set()

        self._autocleanup = False
        self._fetch = False
        self._store_trade_text = False
        self._store_trade_binary = True

        # sqlite3 support needed for cached data
        self.sqlite3 = None

        try:
            self.sqlite3 = import_module('sqlite3', package='')
        except ModuleNotFoundError as e:
            logger.error(repr(e))

    def lock(self, blocking: bool = True, timeout: float = -1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def setup(self, options: dict):
        # load database
        config = utils.load_config(options, 'databases')

        if 'siis' in config:
            self._autocleanup = config['siis'].get('auto-cleanup', False)
            self._store_trade_text = config['siis'].get('trade-text', False)
            self._store_trade_binary = config['siis'].get('trade-binary', True)

        self.connect(config)

        # optional tables creation
        self.setup_market_sql()
        self.setup_userdata_sql()
        self.setup_ohlc_sql()

        # keep data path for usage in per market DB location
        self._markets_path = pathlib.Path(options['markets-path'])

        # start the thread
        self._running = True
        self._thread.start()

    def enable_fetch_mode(self):
        # is fetch mode flush tick continuously
        self._fetch = True

    def connect(self, config: dict):
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
    def connected(self) -> bool:
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

        # flush remaining quotes
        with self._mutex:
            for k, quote_storage in self._quote_storages.items():
                quote_storage.flush()
                quote_storage.close()

            self._quote_storages = {}
            self._pending_quote_insert = set()

    def setup_market_sql(self):
        pass

    def setup_userdata_sql(self):
        pass

    def setup_ohlc_sql(self):
        pass

    #
    # async saves
    #

    def store_market_trade(self, data: Tuple[str, str, int, str, str, str, str, int]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            str bid (>= 0)
            str ask (>= 0)
            str trade price (>= 0)
            str volume (>= 0)
            integer bid/ask (-1 for bid, 1 for ask, or 0 if no info)
        """
        with self._mutex:
            # store market per keyed array
            key = data[0]+'/'+data[1]
            tickstorage = self._tick_storages.get(key)

            if not tickstorage:
                tickstorage = TickStorage(self._markets_path, data[0], data[1], text=self._store_trade_text,
                                          binary=self._store_trade_binary)
                self._tick_storages[key] = tickstorage

            tickstorage.store(data)

            # pending list of TickStorage controller having data to process to avoid to check everyone
            self._pending_tick_insert.add(tickstorage)

        with self._condition:
            self._condition.notify()

    def num_pending_ticks_storage(self) -> int:
        """
        Return current pending tick list size, for storage.
        """
        with self._mutex:
            n = len(self._pending_tick_insert)
            return n

    def store_market_quote(self, data: Tuple[str, str, int, int, str, str, str, str, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            integer timeframe (time unit un seconds)
            str open (>= 0)
            str high (>= 0)
            str low (>= 0)
            str close (>= 0)
            str spread (>= 0)
            str volume (>= 0)
        """
        with self._mutex:
            # store market per keyed array
            key = data[0]+'/'+data[1]
            quotestorage = self._quote_storages.get(key)

            if not quotestorage:
                quotestorage = QuoteStorage(self._markets_path, data[0], data[1], data[3],
                                            text=self._store_trade_text, binary=self._store_trade_binary)

                self._quote_storages[key] = quotestorage

            quotestorage.store(data)

            # pending list of QuoteStorage controller having data to process to avoid to check everyone
            self._pending_quote_insert.add(quotestorage)

        with self._condition:
            self._condition.notify()

    def store_market_ohlc(self, data: Tuple[str, str, int, int, str, str, str, str, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch)
            integer timeframe (time unit in seconds)        
            str open (>= 0)
            str high (>= 0)
            str low (>= 0)
            str close (>= 0)
            str spread (>= 0)
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

    def store_market_liquidation(self, data: Tuple[str, str, int, int, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
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

    def store_market_info(self, data: Tuple[str, str, str, int, int, int, int, int, str, str, int, str, str, int, str,
                                            int, str, str, str, str, str, str, str, str, str, str, str, str, str, str,
                                            str, str, str, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
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
    # async loads
    #

    def load_market_ohlc(self, service, broker_id: str, market_id: str, timeframe: float,
                         from_datetime: Optional[datetime] = None, to_datetime: Optional[datetime] = None):
        """
        Load a set of market ohlc, fill the intermediates missing ohlcs if necessary
        @param service to be notified once done
        @param broker_id: str
        @param market_id: str
        @param timeframe: float
        @param from_datetime datetime
        @param to_datetime datetime
        """
        with self._mutex:
            from_ts = int(from_datetime.timestamp() * 1000) if from_datetime else None
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            self._pending_ohlc_select.append((service, broker_id, market_id, timeframe, from_ts, to_ts, None))

        with self._condition:
            self._condition.notify()

    def load_market_ohlc_last_n(self, service, broker_id: str, market_id: str, timeframe: float, last_n: int):
        """
        Load a set of market ohlc, fill the intermediates missing ohlcs if necessary
        @param service to be notified once done
        @param market_id: str
        @param broker_id: str
        @param timeframe: float
        @param last_n: int last max n ohlcs to load
        """
        with self._mutex:
            self._pending_ohlc_select.append((service, broker_id, market_id, timeframe, None, None, last_n))

        with self._condition:
            self._condition.notify()

    def load_market_info(self, service, broker_id: str, market_id: str):
        """
        Load a specific market info given its market id.
        @param service to be notified once done
        @param market_id:
        @param broker_id:
        """
        with self._mutex:
            self._pending_market_info_select.append((service, broker_id, market_id))

        with self._condition:
            self._condition.notify()

    def load_market_list(self, service, broker_id: str):
        """
        Load the complete list of market available for a specific broker id.
        @param service to be notified once done
        @param broker_id: str
        """
        with self._mutex:
            self._pending_market_list_select.append((service, broker_id))

        with self._condition:
            self._condition.notify()

    #
    # sync loads
    #

    def get_first_tick(self, broker_id: str, market_id: str):
        """Load and return only the first found and older stored tick."""
        return FirstTickFinder(self._markets_path, broker_id, market_id, binary=True).first()

    def get_last_tick(self, broker_id: str, market_id: str):
        """Load and return only the last found and most recent stored tick."""
        return LastTickFinder(self._markets_path, broker_id, market_id, binary=True).last()

    def get_last_quote(self, broker_id: str, market_id: str, timeframe: float):
        """Load and return only the last found and most recent stored tick."""
        return LastQuoteFinder(self._markets_path, broker_id, market_id, timeframe, binary=True).last()

    def get_last_ohlc(self, broker_id: str, market_id: str, timeframe: float):
        """Load and return only the last found and most recent stored OHLC from a specific timeframe."""
        return None

    def get_user_closed_trades(self, broker_id: str, account_id: str, strategy_id: str,
                               from_date: datetime, to_date: datetime, market_id: Optional[str] = None):
        """
        Sync load and return the user closed trades for an account and strategy identifier and a period of date
        Optional market_id.
        """
        return None

    #
    # Tick and ohlc streamer
    #

    def create_tick_streamer(self, broker_id: str, market_id: str, from_date: datetime, to_date: datetime,
                             buffer_size: int = 32768):
        """
        Create a new tick streamer.
        """
        return TickStreamer(self._markets_path, broker_id, market_id, from_date, to_date, buffer_size, True)

    def create_quote_streamer(self, broker_id: str, market_id: str, timeframe: float,
                              from_date: datetime, to_date: datetime, buffer_size: int = 8192):
        """
        Create a new quote streamer. It comes from the OHLC file storage.
        """
        return QuoteStreamer(self._markets_path, broker_id, market_id, timeframe, from_date, to_date, buffer_size, True)

    def create_ohlc_streamer(self, broker_id: str, market_id: str, timeframe: float,
                             from_date: datetime, to_date: datetime, buffer_size: int = 8192):
        """
        Create a new OHLC streamer. It comes from OHLC database table.
        """
        return OhlcStreamer(self._db, broker_id, market_id, timeframe, from_date, to_date, buffer_size)

    #
    # User
    # 

    def store_asset(self, data: Tuple[str, str, str, str, int, str, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
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

    def load_assets(self, service, trader, broker_id: str, account_id: str):
        """
        Load all asset for a specific broker_id
        @param service to be notified once done
        @param trader: Trader
        @param account_id: str
        @param broker_id: str
        """
        with self._mutex:
            self._pending_asset_select.append((service, trader, broker_id, account_id))

        with self._condition:
            self._condition.notify()

    def store_user_trade(self, data: Tuple[str, str, str, str, int, int, dict, dict]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str market_id (not empty)
            str strategy_id (not empty)
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

    def load_user_trades(self, service, strategy, broker_id: str, account_id: str, strategy_id: str):
        """
        Load all user trades data and options for a specific strategy_id / broker_id / account_id
        @param strategy_id: str
        @param account_id: str
        @param broker_id: str
        @param strategy: Strategy
        @param service to be notified once done
        """
        with self._mutex:
            self._pending_user_trade_select.append((service, strategy, broker_id, account_id, strategy_id))

        with self._condition:
            self._condition.notify()

    def clear_user_trades(self, broker_id: str, account_id: str, strategy_id: str):
        """
        Delete all user trades data and options for a specific strategy_id / broker_id / account_id
        """
        with self._mutex:
            self._pending_user_trade_delete.append((broker_id, account_id, strategy_id))

        with self._condition:
            self._condition.notify()

    def store_user_trader(self, data: Tuple[str, str, str, str, int, dict, dict, dict]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str market_id (not empty)
            str strategy_id (not empty)
            integer activity (not null)
            dict data (to be json encoded)
            dict regions (to be json encoded)
            dict alerts (to be json encoded)
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_user_trader_insert.extend(data)
            else:
                self._pending_user_trader_insert.append(data)

        with self._condition:
            self._condition.notify()

    def load_user_traders(self, service, strategy, broker_id: str, account_id: str, strategy_id: str):
        """
        Load all user traders data and options for a specific strategy_id / broker_id / account_id
        @param service to be notified once done
        @param strategy: Strategy
        @param strategy_id: str
        @param account_id: str
        @param broker_id: str
        """
        with self._mutex:
            self._pending_user_trader_select.append((service, strategy, broker_id, account_id, strategy_id))

        with self._condition:
            self._condition.notify()

    def store_user_closed_trade(self, data: Tuple[str, str, str, str, int, dict]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str account_id (not empty)
            str market_id (not empty)
            str strategy_id (not empty)
            integer timestamp (not empty)
            dict data (to be json encoded)
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_user_closed_trade_insert.extend(data)
            else:
                self._pending_user_closed_trade_insert.append(data)

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
            self.process_quote()

    def process_market(self):
        pass

    def process_userdata(self):
        pass

    def process_ohlc(self):
        pass

    def process_tick(self):
        with self._mutex:
            # is there some ticks to store
            if not self._pending_tick_insert:
                return

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

    def process_quote(self):
        with self._mutex:
            # is there some quotes to store
            if not self._pending_quote_insert:
                return

            pqi = self._pending_quote_insert
            self._pending_quote_insert = set()

        for quote_storage in pqi:
            if self._fetch or quote_storage.can_flush():
                if quote_storage.has_data():
                    quote_storage.flush(close_at_end=not self._fetch)

                if quote_storage.has_data():
                    # data remaining
                    with self._mutex:
                        self._pending_quote_insert.add(quote_storage)

    #
    # Extra
    #

    def cleanup_ohlc(self, broker_id: str, market_id: Optional[str] = None, timeframes=None,
                     from_date: Optional[datetime] = None, to_date: Optional[datetime] = None):
        """
        Cleanup any OHLC for a specific broker_id.
        If market_id is specified only delete for this market else any market related to the broker identifier
        If timeframes is specified only delete this timeframes else any
        @note This is a synchronous method.
        """
        pass

    #
    # sync cache data
    #

    def get_cached_db_filename(self, broker_id: str, market_id: str, strategy_id: str):
        cleanup_name = strategy_id
        return os.path.join(self._markets_path, broker_id, market_id, 'C', cleanup_name + '.db')

    def open_cached_db(self, broker_id: str, market_id: str, strategy_id: str):
        filename = self.get_cached_db_filename(broker_id, market_id, strategy_id)
        db = None
        exist = False

        if os.path.exists(filename):
            exist = True
        else:
            cached_path = pathlib.Path(self._markets_path, broker_id, market_id, 'C')
            if not cached_path.exists():
                cached_path.mkdir(parents=True)

        try:
            db = self.sqlite3.connect(filename)
        except Exception as e:
            error_logger.error(repr(e))

        if not exist:
            try:
                self.setup_cached_limits_sql(db)
                self.setup_cached_volume_profile_sql(db)
            except Exception as e:
                error_logger.error(repr(e))

        return db

    def setup_cached_limits_sql(self, db):
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                from_timestamp INTEGER NOT NULL,
                last_timestamp INTEGER NOT NULL,
                min_price VARCHAR(16) NOT NULL,
                max_price VARCHAR(16) NOT NULL)""")
        db.commit()

    def setup_cached_volume_profile_sql(self, db):
        """
        market_id
        peaks and valleys are JSON dict price:volume
        """
        cursor = db.cursor()
        # The volume profile table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS volume_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                timestamp INTEGER NOT NULL, timeframe INTEGER NOT NULL,
                poc VARCHAR(32) NOT NULL,
                low_area VARCHAR(32) NOT NULL,
                high_area VARCHAR(32) NOT NULL,
                volumes VARCHAR(16384) NOT NULL,
                peaks VARCHAR(4096) NOT NULL,
                valleys VARCHAR(4096) NOT NULL,
                sensibility INTEGER NOT NULL,
                volume_area INTEGER NOT NULL,
                UNIQUE (timestamp, timeframe, sensibility, volume_area))""")

        db.commit()

    def get_cached_limits(self, broker_id: str, market_id: str, strategy_id: str):
        """Load TA limits from the data cache for a specific broker id market id and strategy identifier."""
        try:
            db = self.open_cached_db(broker_id, market_id, strategy_id)
            cursor = db.cursor()

            cursor.execute("""SELECT from_timestamp, last_timestamp, min_price, max_price FROM limits""")
            row = cursor.fetchone()

            db.close()
            db = None

            if row:
                return Limits(
                    float(row[0]) * 0.001, float(row[1]) * 0.001,
                    float(row[2]), float(row[3])
                )
            else:
                return None
        except Exception as e:
            error_logger.error(repr(e))
            raise DatabaseException("Unable to get cached limits for %s %s" % (broker_id, market_id))

    def get_cached_volume_profile(self, broker_id: str, market_id: str, strategy_id: str, timeframe: float,
                                  from_date: datetime, to_date: Optional[datetime] = None,
                                  sensibility: int = 10, volume_area: int = 70):
        """
        Load TA Volume Profile cache for a specific broker id market id and strategy identifier and inclusive period.
        """
        from_ts = from_date.timestamp()
        to_ts = to_date.timestamp() if to_date else time.time()

        try:
            db = self.open_cached_db(broker_id, market_id, strategy_id)
            cursor = db.cursor()

            cursor.execute("""SELECT timestamp, poc, low_area, high_area, volumes, peaks, valleys FROM volume_profile
                            WHERE timeframe = ? AND sensibility = ? AND volume_area = ? AND timestamp >= ? AND timestamp <= ?
                            ORDER BY timestamp ASC""", (
                                timeframe, sensibility, volume_area, int(from_ts * 1000), int(to_ts * 1000)))

            rows = cursor.fetchall()
            now = time.time()

            db.close()
            db = None

            results = []

            for row in rows:
                timestamp = float(row[0]) * 0.001  # to float second timestamp
                vp = VolumeProfile(timestamp, timeframe, float(row[1]),  float(row[2]), float(row[3]),
                                   {b: v for b, v in json.loads(row[4])},
                                   json.loads(row[5]),
                                   json.loads(row[6]))

                results.append(vp)

            return results

        except Exception as e:
            error_logger.error(repr(e))
            raise DatabaseException("Unable to get a range of cached Volume Profile for %s %s" % (broker_id, market_id))

    def store_cached_limits(self, broker_id: str, market_id: str, strategy_id: str, limits: Limits):
        """
        limits is Limits dataclass.
        """
        if not limits:
            return

        try:
            db = self.open_cached_db(broker_id, market_id, strategy_id)
            cursor = db.cursor()

            cursor.execute("""INSERT OR REPLACE INTO limits(from_timestamp, last_timestamp, min_price, max_price) VALUES (?, ?, ?, ?)""", (
                int(limits.from_timestamp * 1000),
                int(limits.last_timestamp * 1000),
                limits.min_price, limits.max_price))

            db.commit()

            db.close()
            db = None
        except self.sqlite3.IntegrityError as e:
            error_logger.error(repr(e))
            raise DatabaseException("SQlite Integrity Error: Failed to insert cached Limits for %s.\n" % (
                market_id,) + str(e))

    def store_cached_volume_profile(self, broker_id: str, market_id: str, strategy_id: str, timeframe: float,
                                    data: Union[List[VolumeProfile], VolumeProfile],
                                    sensibility: int = 10, volume_area: int = 70):
        """
        @param volume_area:
        @param sensibility:
        @param timeframe:
        @param strategy_id:
        @param market_id:
        @param broker_id:
        @param data A single tuple or a list of tuple.

        Format of a Volume Profile tuple is (timestamp:float in seconds, POC_price:float, POC_volume:float, Volumes:dict, Peaks:list, Valleys:list)
        Format of a peak or a valley is price as key, volume as value.
        """
        if not data:
            return

        if type(data) is list:
            # array of VPs
            data_set = [(timeframe, sensibility, volume_area, int(d.timestamp*1000), d.poc, d.low_area, d.high_area,
                json.dumps(tuple((b, v) for b, v in d.volumes.items())), json.dumps(d.peaks), json.dumps(d.valleys)) for d in data]

            try:
                db = self.open_cached_db(broker_id, market_id, strategy_id)
                cursor = db.cursor()
                
                cursor.executemany("""INSERT OR REPLACE INTO volume_profile(timeframe, sensibility, volume_area, timestamp, poc, low_area, high_area, volumes, peaks, valleys) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", data_set)

                db.commit()
            except self.sqlite3.IntegrityError as e:
                error_logger.error(repr(e))
                raise DatabaseException("SQlite Integrity Error: Failed to insert cached Volume Profile for %s %s.\n" % (broker_id, market_id,) + str(e))

        elif type(data) is VolumeProfile:
            # single VP
            try:
                db = self.open_cached_db(broker_id, market_id, strategy_id)
                cursor = db.cursor()

                cursor.execute("""INSERT OR REPLACE INTO volume_profile(timeframe, sensibility, volume_area, timestamp, poc, low_area, high_area, volumes, peaks, valleys) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (timeframe, sensibility, volume_area, int(data.timestamp*1000), data.poc, data.low_area, data.high_area,
                            json.dumps(data.volumes), json.dumps(data.peaks), json.dumps(data.valleys)))

                db.commit()
            except self.sqlite3.IntegrityError as e:
                error_logger.error(repr(e))
                raise DatabaseException("SQlite Integrity Error: Failed to insert cached Volume Profile for %s %s.\n" % (broker_id, market_id,) + str(e))
