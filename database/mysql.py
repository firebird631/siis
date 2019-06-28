# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Storage service, mysql implementation

import os
import json
import time
import datetime
import threading
import copy
import traceback
import pathlib
import MySQLdb

from watcher.service import WatcherService
from notifier.signal import Signal

from instrument.instrument import Candle, Tick

from trader.market import Market
from trader.asset import Asset

from config.utils import databases

from .tickstorage import TickStorage, TickStreamer
from .candlestorage import CandleStorage, CandleStreamer

from .database import Database

import logging
logger = logging.getLogger('siis.database')


class MySql(Database):
    """
    Storage service, mysql implementation.
    """
    def __init__(self):
        super().__init__()
        self._db = None

    def connect(self, config):
        if 'siis' in config:
            self._db = MySQLdb.connect(
                db='siis',
                host=config['siis'].get('host', 'localhost'),
                port=config['siis'].get('port', 3306),
                user=config['siis'].get('user', 'siis'),
                passwd=config['siis'].get('password', 'siis'),
                connect_timeout=5)

    def disconnect(self):
        # postresql db
        if self._db:
            self._db.close()
            self._db = None

    def setup_market_sql(self):
        cursor = self._db.cursor()

        # market table
        cursor.execute("SHOW TABLES LIKE 'market'")
        if len(cursor.fetchall()) > 0:
            return

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market(
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL, symbol VARCHAR(32) NOT NULL,
                market_type INTEGER NOT NULL DEFAULT 0, unit_type INTEGER NOT NULL DEFAULT 0, contract_type INTEGER NOT NULL DEFAULT 0,
                trade_type INTEGER NOT NULL DEFAULT 0, orders INTEGER NOT NULL DEFAULT 0,
                base VARCHAR(32) NOT NULL, base_display VARCHAR(32) NOT NULL, base_precision VARCHAR(32) NOT NULL,
                quote VARCHAR(32) NOT NULL, quote_display VARCHAR(32) NOT NULL, quote_precision VARCHAR(32) NOT NULL,
                expiry VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL,
                lot_size VARCHAR(32) NOT NULL, contract_size VARCHAR(32) NOT NULL, base_exchange_rate VARCHAR(32) NOT NULL,
                value_per_pip VARCHAR(32) NOT NULL, one_pip_means VARCHAR(32) NOT NULL, margin_factor VARCHAR(32) NOT NULL DEFAULT '1.0',
                min_size VARCHAR(32) NOT NULL, max_size VARCHAR(32) NOT NULL, step_size VARCHAR(32) NOT NULL,
                min_notional VARCHAR(32) NOT NULL, max_notional VARCHAR(32) NOT NULL, step_notional VARCHAR(32) NOT NULL,
                min_price VARCHAR(32) NOT NULL, max_price VARCHAR(32) NOT NULL, step_price VARCHAR(32) NOT NULL,
                maker_fee VARCHAR(32) NOT NULL DEFAULT '0', taker_fee VARCHAR(32) NOT NULL DEFAULT '0',
                maker_commission VARCHAR(32) NOT NULL DEFAULT '0', taker_commission VARCHAR(32) NOT NULL DEFAULT '0',
                UNIQUE KEY(broker_id, market_id))""")

        self._db.commit()

    def setup_userdata_sql(self):
        cursor = self._db.cursor()

        # asset table
        cursor.execute("SHOW TABLES LIKE 'asset'")
        if len(cursor.fetchall()) > 0:
            return

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset(
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                broker_id VARCHAR(255) NOT NULL, asset_id VARCHAR(255) NOT NULL,
                last_trade_id VARCHAR(32) NOT NULL, timestamp BIGINT NOT NULL, 
                quantity VARCHAR(32) NOT NULL, price VARCHAR(32) NOT NULL, quote_symbol VARCHAR(32) NOT NULL,
                UNIQUE KEY(broker_id, asset_id))""")

        self._db.commit()

    def setup_ohlc_sql(self):
        cursor = self._db.cursor()

        # ohlc table
        cursor.execute("SHOW TABLES LIKE 'ohlc'")
        if len(cursor.fetchall()) > 0:
            return

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlc(
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                broker_id VARCHAR(255) NOT NULL, market_id VARCHAR(255) NOT NULL,
                timestamp BIGINT NOT NULL, timeframe INTEGER NOT NULL,
                bid_open VARCHAR(32) NOT NULL, bid_high VARCHAR(32) NOT NULL, bid_low VARCHAR(32) NOT NULL, bid_close VARCHAR(32) NOT NULL,
                ask_open VARCHAR(32) NOT NULL, ask_high VARCHAR(32) NOT NULL, ask_low VARCHAR(32) NOT NULL, ask_close VARCHAR(32) NOT NULL,
                volume VARCHAR(48) NOT NULL,
                UNIQUE KEY(broker_id, market_id, timestamp, timeframe))""")

        self._db.commit()

    def create_ohlc_streamer(self, broker_id, market_id, timeframe, from_date, to_date, buffer_size=8192):
        """
        Create a new tick streamer.
        """
        return CandleStreamer(self._db, timeframe, broker_id, market_id, from_date, to_date, buffer_size)

    #
    # Processing
    #

    def process_market(self):
        #
        # insert market info
        #

        self.lock()
        mki = copy.copy(self._pending_market_info_insert)
        self._pending_market_info_insert.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for mi in mki:
                if mi[16] is None:
                    # margin factor is unavailable when market is down, so use previous value if available
                    cursor.execute("""SELECT margin_factor FROM market WHERE broker_id = '%s' AND market_id = '%s'""" % (mi[0], mi[1]))
                    row = cursor.fetchone()

                    if row:
                        # replace by previous margin factor from the DB
                        margin_factor = row[0]
                        mi = list(mi)
                        mi[16] = margin_factor

                cursor.execute("""INSERT INTO market(broker_id, market_id, symbol,
                                    market_type, unit_type, contract_type,
                                    trade_type, orders,
                                    base, base_display, base_precision,
                                    quote, quote_display, quote_precision,
                                    expiry, timestamp,
                                    lot_size, contract_size, base_exchange_rate,
                                    value_per_pip, one_pip_means, margin_factor,
                                    min_size, max_size, step_size,
                                    min_notional, max_notional, step_notional,
                                    min_price, max_price, step_price,
                                    maker_fee, taker_fee, maker_commission, taker_commission) 
                                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE symbol = %s,
                                    market_type = %s, unit_type = %s, contract_type = %s,
                                    trade_type = %s, orders = %s,
                                    base = %s, base_display = %s, base_precision = %s,
                                    quote = %s, quote_display = %s, quote_precision = %s,
                                    expiry = %s, timestamp = %s,
                                    lot_size = %s, contract_size = %s, base_exchange_rate = %s,
                                    value_per_pip = %s, one_pip_means = %s, margin_factor = %s,
                                    min_size = %s, max_size = %s, step_size = %s,
                                    min_notional = %s, max_notional = %s, step_notional = %s,
                                    min_price = %s, max_price = %s, step_price = %s,
                                    maker_fee = %s, taker_fee = %s, maker_commission = %s, taker_commission = %s""",
                                (*mi, *mi[2:]))

            self._db.commit()
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_market_info_insert = mki + self._pending_market_info_insert
            self.unlock()

        #
        # select market info
        #

        self.lock()
        mis = copy.copy(self._pending_market_info_select)
        self._pending_market_info_select.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for mi in mis:
                cursor.execute("""SELECT symbol,
                                    market_type, unit_type, contract_type,
                                    trade_type, orders,
                                    base, base_display, base_precision,
                                    quote, quote_display, quote_precision,
                                    expiry, timestamp,
                                    lot_size, contract_size, base_exchange_rate,
                                    value_per_pip, one_pip_means, margin_factor,
                                    min_size, max_size, step_size,
                                    min_notional, max_notional, step_notional,
                                    min_price, max_price, step_price,
                                    maker_fee, taker_fee, maker_commission, taker_commission FROM market
                                WHERE broker_id = '%s' AND market_id = '%s'""" % (
                                    mi[1], mi[2]))

                row = cursor.fetchone()

                if row:
                    market_info = Market(mi[2], row[0])

                    market_info.is_open = True

                    market_info.market_type = row[1]
                    market_info.unit_type = row[2]
                    market_info.contract_type = row[3]

                    market_info.trade = row[4]
                    market_info.orders = row[5]

                    market_info.set_base(row[6], row[7], int(row[8]))
                    market_info.set_quote(row[9], row[10], int(row[11]))

                    market_info.expiry = row[12]
                    market_info.last_update_time = row[13]

                    market_info.lot_size = float(row[14])
                    market_info.contract_size = float(row[15])
                    market_info.base_exchange_rate = float(row[16])
                    market_info.value_per_pip = float(row[17])
                    market_info.one_pip_means = float(row[18])

                    if row[19] is not None or row[19] is not 'None':
                        if row[19] == '-':  # not defined mean 1.0 or no margin
                            market_info.margin_factor = 1.0
                        else:
                            market_info.margin_factor = float(row[19])

                    market_info.set_size_limits(float(row[20]), float(row[21]), float(row[22]))
                    market_info.set_notional_limits(float(row[23]), float(row[24]), float(row[25]))
                    market_info.set_price_limits(float(row[26]), float(row[27]), float(row[28]))

                    market_info.maker_fee = float(row[29])
                    market_info.taker_fee = float(row[30])

                    market_info.maker_commission = float(row[31])
                    market_info.taker_commission = float(row[32])
                else:
                    market_info = None

                # notify
                mi[0].notify(Signal.SIGNAL_MARKET_INFO_DATA, mi[1], (mi[2], market_info))
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_market_info_select = mis + self._pending_market_info_select
            self.unlock()

        #
        # select market list
        #

        self.lock()
        mls = copy.copy(self._pending_market_list_select)
        self._pending_market_list_select.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for m in mls:
                cursor.execute("""SELECT market_id, symbol, base, quote FROM market WHERE broker_id = '%s'""" % (m[1],))

                rows = cursor.fetchall()

                market_list = []

                for row in rows:
                    market_list.append(row)

                # notify
                m[0].notify(Signal.SIGNAL_MARKET_LIST_DATA, m[1], market_list)
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_market_list_select = mls + self._pending_market_list_select
            self.unlock()

    def process_userdata(self):
        #
        # inset asset
        #
        self.lock()
        uai = copy.copy(self._pending_asset_insert)
        self._pending_asset_insert.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for ua in uai:
                cursor.execute("""
                    INSERT INTO asset(broker_id, asset_id, last_trade_id, timestamp, quantity, price, quote_symbol)
                        VALUES(%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        last_trade_id = %s, timestamp = %s, quantity = %s, price = %s, quote_symbol = %s""", (*ua, *ua[2:]))

            self._db.commit()
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_asset_insert = uai + self._pending_asset_insert
            self.unlock()

        #
        # select asset
        #

        self.lock()
        uas = copy.copy(self._pending_asset_select)
        self._pending_asset_select.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for ua in uas:
                cursor.execute("""SELECT asset_id, last_trade_id, timestamp, quantity, price, quote_symbol FROM asset WHERE broker_id = '%s'""" % (ua[2]))

                rows = cursor.fetchall()

                assets = []

                for row in rows:
                    asset = Asset(ua[1], row[0])

                    # only a sync will tell which quantity is free, which one is locked
                    asset.update_price(float(row[2]) * 0.001, row[1], float(row[4]), row[5])
                    asset.set_quantity(0.0, float(row[3]))

                    assets.append(asset)

                # notify
                ua[0].notify(Signal.SIGNAL_ASSET_DATA_BULK, ua[2], assets)
        except Exception as e:
            # check database for valid ohlc and volumes
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_asset_select = uas + self._pending_asset_select
            self.unlock()

        #
        # inset user trade
        #
        self.lock()
        uti = copy.copy(self._pending_user_trade_insert)
        self._pending_user_trade_insert.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for ut in uti:
                # str broker_id (not empty)
                # str market_id (not empty)
                # str appliance_id (not empty)
                # integer trade_id (not empty)
                # integer trade_type (not empty)
                # integer timestamp (ms since epoch)
                # integer direction (not empty)
                # str price (not empty)
                # str stop_loss (not empty)
                # str take_profit (not empty)
                # str quantity (not empty)
                # str entry_quantity (not empty)
                # str exit_quantity (not empty)
                # str profit_loss (not empty)
                # str timeframes (not empty, comma separeted list of timeframes)
                # integer entry_status
                # integer exit_status
                # str entry_order_id
                # str exit1_order_id
                # str exit2_order_id
                # str exit3_order_id
                # str entry_ref_order_id
                # str exit1_ref_order_id
                # str exit2_ref_order_id
                # str exit3_ref_order_id
                # str position_id
                # str copied_position_id

                cursor.execute("""
                    INSERT INTO user_trade(broker_id, market_id, appliance_id, trade_id, trade_type, timestamp, direction, price, stop_loss, take_profit,
                        quantity, entry_quantity, exit_quantity, profit_loss, timeframes, entry_status, exit_status,
                        entry_order_id, exit1_order_id, exit2_order_id, exit3_order_id,
                        entry_ref_order_id, exit1_ref_order_id, exit2_ref_order_id, exit3_ref_order_id,
                        positiond_id, copied_position_id
                        VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        price = %s, stop_loss = %s, take_profit = %s, quantity = %s, entry_quantity = %s, exit_quantity = %s,
                        profit_loss = %s, timeframes = %s, entry_status = %s, exit_status = %s,
                        entry_order_id = %s, exit1_order_id = %s, exit2_order_id = %s, exit3_order_id = %s,
                        entry_ref_order_id = %s, exit1_ref_order_id = %s, exit2_ref_order_id = %s, exit3_ref_order_id = %s,
                        positiond_id, copied_position_id""", (*ut, *ut[7:-1]))

            self._db.commit()
        except Exception as e:
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_user_trade_insert = uti + self._pending_user_trade_insert
            self.unlock()

        #
        # select user trade
        #

        self.lock()
        uts = copy.copy(self._pending_user_trade_select)
        self._pending_user_trade_select.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for ut in uts:
                cursor.execute("""SELECT asset_id, last_trade_id, timestamp, quantity, price, quote_symbol FROM asset WHERE broker_id = '%s'""" % (ua[2]))

                rows = cursor.fetchall()

                user_trades = []

                for row in rows:
                    pass
            #         asset = Asset(ua[1], row[0])

            #         # only a sync will tell which quantity is free, which one is locked
            #         asset.update_price(float(row[2]) * 0.001, row[1], float(row[4]), row[5])
            #         asset.set_quantity(0.0, float(row[3]))

            #         assets.append(asset)

                # notify
                ua[0].notify(Signal.SIGNAL_STRATEGY_TRADE_LIST, ua[2], user_trades)
        except Exception as e:
            # check database for valid ohlc and volumes
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_user_trade_select = uts + self._pending_user_trade_select
            self.unlock()            

    def process_ohlc(self):       
        #
        # select market ohlcs
        #

        self.lock()
        mks = copy.copy(self._pending_ohlc_select)
        self._pending_ohlc_select.clear()
        self.unlock()

        try:
            cursor = self._db.cursor()

            for mk in mks:
                if mk[6]:
                    # last n
                    cursor.execute("""SELECT COUNT(*) FROM ohlc WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s""" % (mk[1], mk[2], mk[3]))
                    count = int(cursor.fetchone()[0])
                    offset = max(0, count - mk[6])

                    # LIMIT should not be necessary then
                    cursor.execute("""SELECT timestamp, bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close, volume FROM ohlc
                                    WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s ORDER BY timestamp ASC LIMIT %i OFFSET %i""" % (
                                        mk[1], mk[2], mk[3], mk[6], offset))
                elif mk[4] and mk[5]:
                    # from to
                    cursor.execute("""SELECT timestamp, bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close, volume FROM ohlc
                                    WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp >= %i AND timestamp <= %i ORDER BY timestamp ASC""" % (
                                        mk[1], mk[2], mk[3], mk[4], mk[5]))
                elif mk[4]:
                    # from to now
                    cursor.execute("""SELECT timestamp, bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close, volume FROM ohlc
                                    WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp >= %i ORDER BY timestamp ASC""" % (
                                        mk[1], mk[2], mk[3], mk[4]))
                elif mk[5]:
                    # to now
                    cursor.execute("""SELECT timestamp, bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close, volume FROM ohlc
                                    WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s AND timestamp <= %i ORDER BY timestamp ASC""" % (
                                        mk[1], mk[2], mk[3], mk[5]))
                else:
                    # all
                    cursor.execute("""SELECT timestamp, bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close, volume FROM ohlc
                                    WHERE broker_id = '%s' AND market_id = '%s' AND timeframe = %s ORDER BY timestamp ASC""" % (
                                        mk[1], mk[2], mk[3]))

                rows = cursor.fetchall()

                ohlcs = []

                for row in rows:
                    timestamp = float(row[0]) / 1000.0  # to float second timestamp
                    ohlc = Candle(timestamp, mk[3])

                    ohlc.set_bid_ohlc(float(row[1]), float(row[2]), float(row[3]), float(row[4]))
                    ohlc.set_ofr_ohlc(float(row[5]), float(row[6]), float(row[7]), float(row[8]))

                    # if float(row[9]) <= 0:
                    #   # prefer to ignore empty volume ohlc because it can broke volume signal and it is a no way but it could be
                    #   # a lack of this information like on SPX500 of ig.com. So how to manage that cases...
                    #   continue

                    ohlc.set_volume(float(row[9]))

                    ohlcs.append(ohlc)

                # notify
                mk[0].notify(Signal.SIGNAL_CANDLE_DATA_BULK, mk[1], (mk[2], mk[3], ohlcs))
        except Exception as e:
            # check database for valide ohlc and volumes
            logger.error(repr(e))

            # retry the next time
            self.lock()
            self._pending_ohlc_select = mks + self._pending_ohlc_select
            self.unlock()

        #
        # insert market ohlcs
        #

        if time.time() - self._last_ohlc_flush >= 60 or len(self._pending_ohlc_insert) > 500:
            self.lock()
            mkd = copy.copy(self._pending_ohlc_insert)
            self._pending_ohlc_insert.clear()
            self.unlock()

            try:
                cursor = self._db.cursor()

                for mk in mkd:
                    if mk[1]:  # replace
                        cursor.execute("""INSERT INTO ohlc(broker_id, market_id, timestamp, timeframe,
                                bid_open, bid_high, bid_low, bid_close,
                                ask_open, ask_high, ask_low, ask_close,
                                volume)
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                                bid_open = %s, bid_high = %s, bid_low = %s, bid_close = %s,
                                ask_open = %s, ask_high = %s, ask_low = %s, ask_close = %s,
                                volume = %s""", (*mk[0], *mk[0][4:]))
                    else:  # keep original (default)
                        cursor.execute("""INSERT INTO ohlc(broker_id, market_id, timestamp, timeframe,
                                bid_open, bid_high, bid_low, bid_close,
                                ask_open, ask_high, ask_low, ask_close,
                                volume)
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE""", (*mk[0],))

                self._db.commit()
            except Exception as e:
                logger.error(repr(e))

                # retry the next time
                self.lock()
                self._pending_ohlc_insert = mkd + self._pending_ohlc_insert
                self.unlock()

            self._last_ohlc_flush = time.time()

        #
        # clean older ohlcs
        #

        # @todo transaction
        if time.time() - self._last_ohlc_clean >= 60*60:  # no more than once per hour
            try:
                now = time.time()
                cursor = self._db.cursor()

                for timeframe, timestamp in CandleStorage.CLEANERS:
                    ts = int(now - timestamp) * 1000
                    cursor.execute("DELETE FROM ohlc WHERE timeframe <= %i AND timestamp < %i" % (timeframe, ts))

                self._db.commit()
            except Exception as e:
                logger.error(repr(e))

            self._last_ohlc_clean = time.time()
