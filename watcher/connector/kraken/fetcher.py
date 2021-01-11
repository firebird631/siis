# @date 2019-08-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.kraken.com data fetcher

import json
import time
import traceback
import math

from common.utils import timeframe_to_str

from database.database import Database
from watcher.fetcher import Fetcher

from connector.kraken.connector import Connector

import logging
logger = logging.getLogger('siis.fetcher.kraken')
error_logger = logging.getLogger('siis.error.fetcher.kraken')


class KrakenFetcher(Fetcher):
    """
    Kraken market data fetcher.
    """

    BASE_QUOTE = "ZEUR"

    TF_MAP = {
        60: 1,          # 1m
        300: 5,         # 5m
        900: 15,        # 15m
        1800: 30,       # 30m
        3600: 60,       # 1h
        14400: 240,     # 4h
        86400.0: 1440,  # 1d
        # 604800: 10080,  # 1w (not allowed because starts on thuesday)
        # 1296000: 21600  # 15d
    }

    def __init__(self, service):
        super().__init__("kraken.com", service)

        self._connector = None
        self._instruments = {}

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                if not self._connector:
                    self._connector = Connector(
                        self.service,
                        identity.get('api-key'),
                        identity.get('api-secret'),
                        [],
                        identity.get('host'))

                if not self._connector.connected:
                    self._connector.connect(use_ws=False)

                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                instruments = self._connector.instruments()

                for market_id, instrument in instruments.items():
                    self._available_instruments.add(market_id)

                # size limits are locally defined as for the watcher
                self._size_limits = self.service.fetcher_config(self._name).get("size-limits", {})

                # keep them for market install
                self._instruments = instruments

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def disconnect(self):
        super().disconnect()

        try:
            if self._connector:
                self._connector.disconnect()
                self._connector = None
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected

    @property
    def authenticated(self):
        return self._connector and self._connector.authenticated

    def install_market(self, market_id):
        instrument = self._instruments.get(market_id)

        logger.info("Fetcher %s retrieve and install market %s from local data" % (self.name, market_id))

        if instrument:
            try:
                symbol = instrument['altname']

                is_open = True
                expiry = '-'

                # "aclass_base":"currency"
                base_display = base_asset = instrument['base']  # XXBT
                base_precision = instrument['pair_decimals']

                # "aclass_quote":"currency"
                quote_display = quote_asset = instrument['quote']  # ZUSD 
                quote_precision = instrument['lot_decimals']

                # tick size at the base asset precision
                one_pip_means = math.pow(10.0, -instrument['pair_decimals'])  # 1
                value_per_pip = 1.0
                contract_size = 1.0
                lot_size = 1.0  # "lot":"unit", "lot_multiplier":1

                # "margin_call":80, "margin_stop":40
                # margin_call = margin call level
                # margin_stop = stop-out/liquidation margin level

                leverages = set(instrument.get('leverage_buy', []))
                leverages.intersection(set(instrument.get('leverage_sell', [])))

                margin_factor = 1.0 / max(leverages) if len(leverages) > 0 else 1.0

                size_limit = self._size_limits.get(instrument['altname'], {})
                min_size = size_limit.get('min-size', 1.0)

                size_limits = [str(min_size), "0.0", str(min_size)]
                notional_limits = ["0.0", "0.0", "0.0"]
                price_limits = ["0.0", "0.0", "0.0"]

                # "lot":"unit"
                unit_type = 0
                market_type = 2
                contract_type = 0

                trade = 1
                if leverages:
                    trade |= 2
                    trade |= 8

                # orders capacities
                orders = 1 | 0 | 2 | 4

                # @todo take the first but it might depends of the traded volume per 30 days, then request volume window to got it
                # "fees":[[0,0.26],[50000,0.24],[100000,0.22],[250000,0.2],[500000,0.18],[1000000,0.16],[2500000,0.14],[5000000,0.12],[10000000,0.1]],
                # "fees_maker":[[0,0.16],[50000,0.14],[100000,0.12],[250000,0.1],[500000,0.08],[1000000,0.06],[2500000,0.04],[5000000,0.02],[10000000,0]],
                fees = instrument.get('fees', [])
                fees_maker = instrument.get('fees_maker', [])

                if fees:
                    taker_fee = round(fees[0][1] * 0.01, 6)
                if fees_maker:
                    maker_fee = round(fees_maker[0][1] * 0.01, 6)

                if instrument.get('fee_volume_currency'):
                    fee_currency = instrument['fee_volume_currency']

                if quote_asset != self.BASE_QUOTE:
                    # from XXBTZUSD / XXBTZEUR ...
                    # @todo
                    pass
                    # if self._tickers_data.get(quote_asset+self.BASE_QUOTE):
                    #     base_exchange_rate = float(self._tickers_data.get(quote_asset+self.BASE_QUOTE, {'price', '1.0'})['price'])
                    # elif self._tickers_data.get(self.BASE_QUOTE+quote_asset):
                    #     base_exchange_rate = 1.0 / float(self._tickers_data.get(self.BASE_QUOTE+quote_asset, {'price', '1.0'})['price'])
                    # else:
                    #     base_exchange_rate = 1.0
                else:
                    base_exchange_rate = 1.0

                # @todo contract_size
                # contract_size = 1.0 / mid_price
                # value_per_pip = contract_size / mid_price

                # store the last market info to be used for backtesting
                Database.inst().store_market_info((self.name, market_id, symbol,
                    market_type, unit_type, contract_type,  # type
                    trade, orders,  # type
                    base_asset, base_display, base_precision,  # base
                    quote_asset, quote_display, quote_precision,  # quote
                    expiry, int(time.time() * 1000.0),  # expiry, timestamp
                    str(lot_size), str(contract_size), str(base_exchange_rate),
                    str(value_per_pip), str(one_pip_means), '-',
                    *size_limits,
                    *notional_limits,
                    *price_limits,
                    str(maker_fee), str(taker_fee), "0.0", "0.0")
                )
            except Exception as e:
                logger.error("Fetcher %s error retrieve market %s on local data" % (self.name, market_id))
        else:
            logger.error("Fetcher %s cannot retrieve market %s on local data" % (self.name, market_id))


    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        trades = []

        try:
            trades = self._connector.get_historical_trades(market_id, from_date, to_date)
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            yield(trade)

        logger.info("Fetcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        if timeframe not in self.TF_MAP:
            logger.error("Fetcher %s does not support timeframe %s" % (self.name, timeframe_to_str(timeframe)))
            return

        candles = []

        # second timeframe to kraken interval
        interval = self.TF_MAP[timeframe]

        try:
            candles = self._connector.get_historical_candles(market_id, interval, from_date, to_date)
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, interval, market_id))
            error_logger.error(traceback.format_exc())

        count = 0
        
        for candle in candles:
            count += 1
            # store (timestamp, open, high, low, close, spread, volume)
            if candle[0] is not None and candle[1] is not None and candle[2] is not None and candle[3] is not None:
                yield((candle[0], candle[1], candle[2], candle[3], candle[4], 0.0, candle[5]))

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, timeframe_to_str(timeframe)))
