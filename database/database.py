# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Storage service

from __future__ import annotations

from typing import Tuple, Optional, Union, List

import time
import threading
import pathlib
from datetime import datetime

from strategy.indicator.models import VolumeProfile

from config import utils
from watcher.event import EconomicEvent

from .tickstorage import TickStorage, TickStreamer, FirstTickFinder, LastTickFinder
from .ohlcstorage import OhlcStreamer
# from .quotestorage import QuoteStorage, QuoteStreamer, LastQuoteFinder

import logging
logger = logging.getLogger('siis.database')
error_logger = logging.getLogger('siis.database.error')


class DatabaseException(Exception):
    pass


class Database(object):
    """
    Persistence database.

    Timestamp are stored in ms except if there is an object (not raw data).
    Timestamp fetched are converted as the object property (mostly second timestamp).

    What are story into the SQL DB :
        - Market information
        - Asset information
        - User asset quantities per account-identifier
        - User trade and strategy trader per account-identifier/strategy-identifier
        - OHLC history (any timeframes) but 1m and lower timeframes can create a big amount of data
        - Market liquidations
        -

    Ticks are run in exclusive read or write mode :
        - Writing when a watcher, fetcher or a specific tool is writing some news data.
        - Reading during a backtest, training, streaming data from ticks or generating OHLC from ticks...
            - During streaming for a backtest or training
            - Generation of ticks from OHLC
            - Checking data consistency and gaps

    OHLC
    ====

    They can be stored in live by the watcher if the --store-ohlc option is defined but this can create gaps when
    the program is not running or loss the network connexion.

    It is preferred to executed cron task to fetch each 4h the history of OHLC to stay in sync as possible (
    not always possible with any exchanges) or to recreate them from the fetched history of ticks/trades.

    The tool "optimizer" can be used to detect gaps.
    The tool "cleaner" can delete older OHLC according to previously defined rules.

    Purge of OHLC can be done automatically, but it is not really evident to know what to delete and what to keep.
    So that it is preferable to uses manually SQL operations or using the tool "cleaner" but it is not fully
    operational at this time (only remove any OHLC for a market, timeframe and specific period will be added).

    Watcher store timeframe of interest are 1m, 5m, 15m, 1h, 4h, daily, weekly but other can be computed using the tool
    "rebuilder".

    Every OHLC are kept above 2h. Others are cleaned if auto-cleaning is specified (opt-out) :
        - 2h, 1h and 45m ohlc are kept for 90 days.
        - 30m, 15m, 10m are kept for 21 days.
        - 5m, 3m, 1m are kept for 8 days.
        - 1s, 10s are never kept.

    Tick/Trade
    ==========

    Ticks are stored per market into multiple binary files or into ASCII files that can be optimized in binary version.
    Structure is one file per month and each market had its directory structure.

    They essentially exist for backtesting purpose and could serve as source to recreate OHLC bar or volume profiles.

    They can be stored in live by the watcher if the --store-trade option is defined but this can create gaps when
    the program is not running or loss the network connexion.

    It is preferred to executed cron task to fetch each 4h the history of ticks to stay in sync as possible (
    not always possible with any exchanges).

    The tool "optimizer" can be used to detect gaps or broken files (datetime inconsistency);

    If you launch many watchers/fetchers at the same time in writing mode to the same market it could multiply
    the ticks entries. Then some ticks files are corrupted because the implementation is sequential and need that you
    delete the broken files and fetch them back.

    Purge of ticks must be done manually from the file system.

    Volumes Profile
    ===============

    Not really functional currently. Use the distinct cache using SQLite (one file per market/strategy-identifier).
    But this will be centralized into the SQL DB. Generation tool will help to create history for different timeframe
    and even for non-temporal bar.

    Non-temporal Bar (OHLC)
    =======================

    It is planned to add the non temporal-bar as temporal OHLC are. It was planned to cache them into distinct
    SQLite DB but finally will be centralized into the SQL DB.
    """
    __instance = None

    OHLC_CLEANUP_DELAY = 4 * 60 * 60  # each 4 hours

    # from lesser to higher timeframe, higher timeframes are never purged
    OHLC_HOLD_DURATION = (
        (5 * 60, 8 * 24 * 60 * 60),  # until 5m keep for 8 days
        (30 * 60, 21 * 24 * 60 * 60),  # until 30m keep for 21 days
        (2 * 60 * 60, 90 * 24 * 60 * 60))  # until 2h keep for 90 days

    @classmethod
    def inst(cls):
        # singleton is instantiated by the create method
        # if Database.__instance is None:
        #     Database.__instance = Database()

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

        self._pending_range_bar_insert = []
        self._pending_range_bar_select = []

        self._pending_volume_profile_insert = []
        self._pending_volume_profile_select = []

        self._pending_user_trade_insert = []
        self._pending_user_trade_select = []
        self._pending_user_trade_delete = []

        self._pending_user_trader_insert = []
        self._pending_user_trader_select = []

        self._pending_user_closed_trade_insert = []

        self._pending_liquidation_insert = []

        self._pending_economic_event_select = []
        self._pending_economic_event_insert = []

        self._last_ohlc_flush = 0
        self._last_ohlc_clean = time.time()

        self._last_range_bar_flush = 0
        self._last_vp_flush = 0
        self._last_economic_event_flush = 0

        self._markets_path = None   # path where data are stored into the file-system

        self._tick_storages = {}    # TickStorage per market
        self._pending_tick_insert = set()

        # self._quote_storages = {}   # QuoteStorage per market
        # self._pending_quote_insert = set()

        self._auto_cleanup = False  # default never cleanup older OHLC (bar, volume-profile)
        self._fetch = False  # is fetch mode flush tick continuously, default is async mode

        self._store_trade_text = False
        self._store_trade_binary = True

    def lock(self, blocking: bool = True, timeout: float = -1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def setup(self, options: dict):
        # load database
        config = utils.load_config(options, 'databases')

        if 'siis' in config:
            self._auto_cleanup = config['siis'].get('auto-cleanup', False)
            self._store_trade_text = config['siis'].get('trade-text', False)
            self._store_trade_binary = config['siis'].get('trade-binary', True)

        self.connect(config)

        # optional tables creation
        self.setup_market_sql()
        self.setup_userdata_sql()
        self.setup_ohlc_sql()

        self.setup_range_bar_sql()
        self.setup_volume_profile_sql()

        self.setup_event_sql()

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

            while (self._pending_ohlc_insert or
                   self._pending_range_bar_insert or
                   self._pending_volume_profile_insert or
                   self._pending_asset_insert or
                   self._pending_market_info_insert or
                   self._pending_liquidation_insert or
                   self._pending_economic_event_insert):

                # force to flush the remaining
                self._last_ohlc_flush = 0
                self._last_range_bar_flush = 0
                self._last_vp_flush = 0
                self._last_economic_event_flush = 0

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

        # # flush remaining quotes
        # with self._mutex:
        #     for k, quote_storage in self._quote_storages.items():
        #         quote_storage.flush()
        #         quote_storage.close()
        #
        #     self._quote_storages = {}
        #     self._pending_quote_insert = set()

    def setup_market_sql(self):
        pass

    def setup_userdata_sql(self):
        pass

    def setup_ohlc_sql(self):
        pass

    def setup_range_bar_sql(self):
        pass

    def setup_volume_profile_sql(self):
        pass

    def setup_event_sql(self):
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
            tick_storage = self._tick_storages.get(key)

            if not tick_storage:
                tick_storage = TickStorage(self._markets_path, data[0], data[1],
                                           text=self._store_trade_text, binary=self._store_trade_binary)
                self._tick_storages[key] = tick_storage

            tick_storage.store(data)

            # pending list of TickStorage controller having data to process to avoid checking everyone
            self._pending_tick_insert.add(tick_storage)

        with self._condition:
            self._condition.notify()

    def num_pending_ticks_storage(self) -> int:
        """
        Return current pending tick list size, for storage.
        """
        with self._mutex:
            n = len(self._pending_tick_insert)
            return n

    def num_pending_bars_storage(self) -> int:
        """
        Return current pending OHLC, range-bar and others list size, for storage.
        """
        with self._mutex:
            n = len(self._pending_ohlc_insert) + len(self._pending_range_bar_insert)
            return n

    # def store_market_quote(self, data: Tuple[str, str, int, int, str, str, str, str, str, str]):
    #     """
    #     @param data: is a tuple or an array of tuples containing data in that order and format :
    #         str broker_id (not empty)
    #         str market_id (not empty)
    #         integer timestamp (ms since epoch)
    #         integer timeframe (time unit un seconds)
    #         str open (>= 0)
    #         str high (>= 0)
    #         str low (>= 0)
    #         str close (>= 0)
    #         str spread (>= 0)
    #         str volume (>= 0)
    #     """
    #     with self._mutex:
    #         # store market per keyed array
    #         key = data[0]+'/'+data[1]
    #         quote_storage = self._quote_storages.get(key)
    #
    #         if not quote_storage:
    #             quote_storage = QuoteStorage(self._markets_path, data[0], data[1], data[3],
    #                                          text=self._store_trade_text, binary=self._store_trade_binary)
    #
    #             self._quote_storages[key] = quote_storage
    #
    #         quote_storage.store(data)
    #
    #         # pending list of QuoteStorage controller having data to process to avoid checking everyone
    #         self._pending_quote_insert.add(quote_storage)
    #
    #     with self._condition:
    #         self._condition.notify()

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

    def store_market_info(self, data: Tuple[str, str, str, int, int, int, int, int, str, str, int, str, str, int,
                                            str, str, int, str, int, str, str, str, str, str, str, str, str, str,
                                            str, str, str, str, str, str, str, str, str, str, int]):
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
            str settlement (not empty)
            str settlement_display (not empty)
            int settlement_precision (not empty)
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
            int flags (bit mask : 0/hedging)
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_market_info_insert.extend(data)
            else:
                self._pending_market_info_insert.append(data)

        with self._condition:
            self._condition.notify()

    def store_market_range_bar(self, data: Tuple[str, str, int, int, int, str, str, str, str, str]):
        """
        @param data: is a tuple or an array of tuples containing data in that order and format :
            str broker_id (not empty)
            str market_id (not empty)
            integer timestamp (ms since epoch) opening timestamp
            integer duration (ms since timestamp)
            integer size (>0)
            str open (>= 0)
            str high (>= 0)
            str low (>= 0)
            str close (>= 0)
            str volume (>= 0)

        @note Replace if exists.
        """
        with self._mutex:
            if isinstance(data, list):
                self._pending_range_bar_insert.extend(data)
            else:
                self._pending_range_bar_insert.append(data)

        with self._condition:
            self._condition.notify()

    def store_market_volume_profile(self, data: Tuple[str, str, int]):
            """
            @param data: is a tuple or an array of tuples containing data in that order and format :
                str broker_id (not empty)
                str market_id (not empty)
                integer timestamp (ms since epoch)
                @todo

            @note Replace if exists.
            """
            with self._mutex:
                if isinstance(data, list):
                    self._pending_volume_profile_insert.extend(data)
                else:
                    self._pending_volume_profile_insert.append(data)

            with self._condition:
                self._condition.notify()

    #
    # economic event
    #

    def store_economic_event(self, data: Union[EconomicEvent, List[EconomicEvent]]):
        with self._mutex:
            if isinstance(data, list):
                self._pending_economic_event_insert.extend(data)
            else:
                self._pending_economic_event_insert.append(data)

        with self._condition:
            self._condition.notify()

    #
    # async loads
    #

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

    def load_market_ohlc(self, service, broker_id: str, market_id: str, analyser_name: str, timeframe: float,
                         from_datetime: Optional[datetime] = None, to_datetime: Optional[datetime] = None):
        """
        Load a set of market ohlc.
        @param service to be notified once done
        @param broker_id: str
        @param market_id: str
        @param analyser_name: str
        @param timeframe: float
        @param from_datetime datetime
        @param to_datetime datetime
        """
        with self._mutex:
            from_ts = int(from_datetime.timestamp() * 1000) if from_datetime else None
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 0 if from_ts and to_ts else 3
            self._pending_ohlc_select.append((service, broker_id, market_id, analyser_name,
                                              timeframe, mode, from_ts, to_ts))

        with self._condition:
            self._condition.notify()

    def load_market_ohlc_last_n(self, service, broker_id: str, market_id: str, analyser_name: str,
                                timeframe: float, last_n: int, to_datetime: Optional[datetime] = None):
        """
        Load a set of market ohlc.
        @param service to be notified once done
        @param market_id: str
        @param broker_id: str
        @param analyser_name: str
        @param timeframe: float
        @param last_n: int last max n OHLCs to load
        @param to_datetime
        """
        with self._mutex:
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 2 if to_ts else 1
            self._pending_ohlc_select.append((service, broker_id, market_id, analyser_name,
                                              timeframe, mode, last_n, to_ts))

        with self._condition:
            self._condition.notify()

    def load_market_range_bar(self, service, broker_id: str, market_id: str, analyser_name: str, size: int,
                              from_datetime: Optional[datetime] = None, to_datetime: Optional[datetime] = None):
        """
        Load a set of market non-temporal bar.
        @param service to be notified once done
        @param broker_id: str
        @param market_id: str
        @param analyser_name: str,
        @param size: int
        @param from_datetime datetime
        @param to_datetime datetime
        """
        with self._mutex:
            from_ts = int(from_datetime.timestamp() * 1000) if from_datetime else None
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 0 if from_ts and to_ts else 3
            self._pending_range_bar_select.append((service, broker_id, market_id, analyser_name,
                                                   size, mode, from_ts, to_ts))

        with self._condition:
            self._condition.notify()

    def load_market_range_bar_last_n(self, service, broker_id: str, market_id: str, analyser_name: str, size: int,
                                     last_n: int, to_datetime: Optional[datetime] = None):
        """
        Load a set of market non-temporal bar.
        @param service to be notified once done
        @param market_id: str
        @param broker_id: str
        @param analyser_name: str
        @param size: int
        @param last_n: int last max n results to load
        @param to_datetime
        """
        with self._mutex:
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 2 if to_ts else 1
            self._pending_range_bar_select.append((service, broker_id, market_id, analyser_name,
                                                   size, mode, last_n, to_ts))

        with self._condition:
            self._condition.notify()

    def load_market_volume_profile(self, service, broker_id: str, market_id: str, analyser_name: str, vp_type: str,
                                   from_datetime: Optional[datetime] = None, to_datetime: Optional[datetime] = None):
        """
        Load a set of market volume-profile.
        @param service to be notified once done
        @param broker_id: str
        @param market_id: str
        @param analyser_name: str
        @param vp_type: str
        @param from_datetime datetime
        @param to_datetime datetime
        """
        with self._mutex:
            from_ts = int(from_datetime.timestamp() * 1000) if from_datetime else None
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 0 if from_ts and to_ts else 3
            self._pending_volume_profile_select.append((service, broker_id, market_id, analyser_name,
                                                        vp_type, mode, from_ts, to_ts))

        with self._condition:
            self._condition.notify()

    def load_market_volume_profile_last_n(self, service, broker_id: str, market_id: str, analyser_name: str,
                                          vp_type: str, last_n: int, to_datetime: Optional[datetime] = None):
        """
        Load a set of market volume-profile.
        @param service to be notified once done
        @param market_id: str
        @param broker_id: str
        @param analyser_name: str
        @param vp_type: str
        @param last_n: int last max n results to load
        @param to_datetime
        """
        with self._mutex:
            to_ts = int(to_datetime.timestamp() * 1000) if to_datetime else None

            mode = 2 if to_ts else 1
            self._pending_volume_profile_select.append((service, broker_id, market_id, analyser_name,
                                                        vp_type, mode, last_n, to_ts))

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

    # def get_last_quote(self, broker_id: str, market_id: str, timeframe: float):
    #     """Load and return only the last found and most recent stored tick."""
    #     return LastQuoteFinder(self._markets_path, broker_id, market_id, timeframe, binary=True).last()

    def get_last_ohlc(self, broker_id: str, market_id: str, timeframe: float):
        """Load and return only the last found and most recent stored OHLC from a specific timeframe."""
        return None

    def get_last_ohlc_at(self, broker_id: str, market_id: str, timeframe: float, timestamp: float):
        """Load and return the single OHLC found at given timestamp in seconds from a specific timeframe."""
        return None

    def get_last_range_bar(self, broker_id: str, market_id: str, size: int):
        """Load and return only the last found and most recent stored range-bar from a specific size."""
        return None

    def get_last_range_bar_at(self, broker_id: str, market_id: str, size: int, timestamp: float):
        """Load and return the single range-bar found at given timestamp in seconds from a specific size."""
        return None

    def get_last_volume_profile(self, broker_id: str, market_id: str, vp_type: str):
        """Load and return only the last found and most recent stored volume-profile from a specific type."""
        return None

    def get_last_volume_profile_at(self, broker_id: str, market_id: str, vp_type: str, timestamp: float):
        """Load and return the single volume-profile found at given timestamp in seconds from a specific type."""
        return None

    def get_user_closed_trades(self, broker_id: str, account_id: str, strategy_id: str,
                               from_date: datetime, to_date: datetime, market_id: Optional[str] = None):
        """
        Sync load and return the user closed trades for an account and strategy identifier and a period of date
        Optional market_id.
        """
        return None

    def get_market_info(self, broker_id: str, market_id: str):
        """Load and return market info data."""
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

    # def create_quote_streamer(self, broker_id: str, market_id: str, timeframe: float,
    #                           from_date: datetime, to_date: datetime, buffer_size: int = 8192):
    #     """
    #     Create a new quote streamer. It comes from the OHLC file storage.
    #     """
    #     return QuoteStreamer(self._markets_path, broker_id, market_id, timeframe, from_date, to_date, buffer_size, True)

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
                self.process_range_bar()
                self.process_volume_profile()
                self.process_economic_events()

            self.process_tick()
            # self.process_quote()

    def process_market(self):
        pass

    def process_userdata(self):
        pass

    def process_ohlc(self):
        pass

    def process_range_bar(self):
        pass

    def process_volume_profile(self):
        pass

    def process_economic_events(self):
        pass

    def process_tick(self):
        with self._mutex:
            # are there some ticks to store
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

    # def process_quote(self):
    #     with self._mutex:
    #         # are there some quotes to store
    #         if not self._pending_quote_insert:
    #             return
    #
    #         pqi = self._pending_quote_insert
    #         self._pending_quote_insert = set()
    #
    #     for quote_storage in pqi:
    #         if self._fetch or quote_storage.can_flush():
    #             if quote_storage.has_data():
    #                 quote_storage.flush(close_at_end=not self._fetch)
    #
    #             if quote_storage.has_data():
    #                 # data remaining
    #                 with self._mutex:
    #                     self._pending_quote_insert.add(quote_storage)

    #
    # Extra
    #

    def cleanup_ohlc(self, broker_id: str, market_id: Optional[str] = None,
                     timeframe: Optional[float] = None,
                     from_date: Optional[datetime] = None, to_date: Optional[datetime] = None):
        """
        Cleanup any OHLC for a specific broker_id.
        If market_id is specified only delete for this market else any market related to the broker identifier
        If timeframes is specified only delete this timeframes else any
        @note This is a synchronous method.
        """
        pass

    def cleanup_range_bar(self, broker_id: str, market_id: Optional[str] = None,
                          bar_size: Optional[int] = None,
                          from_date: Optional[datetime] = None, to_date: Optional[datetime] = None):
        pass
