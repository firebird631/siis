# @date 2019-01-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# alphavantage.co watcher implementation

import time
import traceback

from watcher.watcher import Watcher
from common.signal import Signal

from connector.alphavantage.connector import Connector

import logging
logger = logging.getLogger('siis.watcher.alphavantage')
error_logger = logging.getLogger('siis.error.watcher.alphavantage')


class AlphaVantageWatcher(Watcher):
    """
    AlphaVantage watcher get price and volumes of instruments in live mode throught REST API.

    >> https://www.alphavantage.co/documentation/

    - crypto list : https://www.alphavantage.co/digital_currency_list/
    - currency list: https://www.alphavantage.co/physical_currency_list/

    A free account rate is 5 requests/min and 500/day.
    So it is possible to watch :
        - 0 markets at 1m (scalp)
        - 1 at 5m (intraday)
        - 5 at 15m (intraday)
        - 20 at 1h (swing, hold)
        - 83 at 4h (hold, long term)
        - 500 at 1d (hold, long term)

    >> https://www.alphavantage.co/premium/ with a 30 call per min is a better option.

    This will offers :
        - 30 market at 1m 
        - 150 at 5m
        - 450 at 15m
        - 1800 at 1h
        - 7200 at 4h

    @todo Option for payed account to increse the max queries per min rate.
    @todo Option to toggle between multiples API keys (need 1 account per email).
    @todo A cyclic list to update more than allowed queries/min => because a query (1m to 1h) returns 100 candles,
    we can at worst 99 cycles after its first update and we will save all the data like this for further backtesting.

    @todo Fetch and write candles. Also write what we have as lower timeframe as ticks to the database.
    """

    DEFAULT_TF = 60  # default watch 1m candles
    DEFAULT_MAX_QUERIES_PER_MIN = 5  # default for free account

    INTRADAY_TF_MAP = {
        60: '1min',
        5*60: '5min',
        15*60: '15min',
        30*60: '30min',
        60*60: '60min'
    }

    def __init__(self, service):
        super().__init__("alphavantage.co", service, Watcher.WATCHER_PRICE_AND_VOLUME)
        
        self._connector = None

        self._base_tf = AlphaVantageWatcher.DEFAULT_TF
        self._max_queries = AlphaVantageWatcher.DEFAULT_MAX_QUERIES_PER_MIN

        self._last_updates = {}

        self._markets_map = {}
        self._currencies = {}
        self._subscriptions = []

    def connect(self):
        super().connect()

        try:
            self.lock()
            self._ready = False

            identity = self.service.identity(self._name)
            self._subscriptions = []  # reset previous list

            if identity:
                self._connector = Connector(self.service, identity.get('api-key'), identity.get('host'))
                self._connector.connect()

                # @todo fetch crypto, currency, stocks
                markets = self.fetch_markets()

                self._markets_map['MSFT'] = (Connector.MARKET_STOCK, 'MSFT', None, 0.0)

                all_stocks = []
                all_stocks.append('MSFT')

                # @todo could list currencies
                # self._currencies = ...
                instruments = []

                if '*' in self.configured_symbols():
                    # not permit there is thousand of symbols
                    self._available_instruments = []
                else:
                    instruments = self.configured_symbols()

                # susbcribe for symbols
                for symbol in instruments:
                    self._watched_instruments.add(symbol)

                self._ready = True

        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())

            self._connector = None
        finally:
            self.unlock()

        if self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        return self._connector is not None and self._connector.connected

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._connector:
                self._connector.disconnect()
                self._connector = None
            
            self._ready = False

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())
        finally:
            self.unlock()

    def pre_update(self):
        super().pre_update()

        if self._connector is None:
            self.connect()

            if not self.connected:
                # retry in 2 second
                time.sleep(2.0)

            return

    def update(self):
        if not super().update():
            return False

        if self._connector is None or not self._connector.connected:
            return False

        #
        # Fetch markets
        #

        now = time.time()

        for instrument in self._watched_instruments:
            market = self._markets_map.get(instrument)

            try:
                # 100 candle of 1min... but need the last one
                if now - market[3] >= self._base_tf:
                    if market[0] == Connector.MARKET_STOCK:
                        result = self._connector.fetch_stock(market[1], self._base_tf)
                        if result:
                            # @todo store and generate higher candles
                            self._last_updates[instrument] = time.time()
                    elif market[0] == Connector.MARKET_FOREX:
                        pass
                    elif market[0] == Connector.MARKET_CRYPTO:
                        pass
            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.05)

    def post_run(self):
        super().post_run()

    def fetch_markets(self):
        return []

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        pass  # @todo
