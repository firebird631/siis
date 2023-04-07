# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer base class

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union, List, Dict, Type, Tuple, Callable

if TYPE_CHECKING:
    from datetime import datetime

    from watcher.service import WatcherService
    from strategy.strategytrader import StrategyTrader
    from ..service import StrategyService

from config.utils import merge_parameters

import copy

import logging
logger = logging.getLogger('siis.strategy.learning.trainer')
error_logger = logging.getLogger('siis.error.strategy.learning.trainer')
traceback_logger = logging.getLogger('siis.traceback.strategy.learning.trainer')


class Trainer(object):
    """
    A trainer call a separate process with a set of parameter that are back-tested with a specific strategy
    and settings and return the performance.

    The fitter must adjust the parameter in way to restart the process until it satisfy the requirements.
    With trainer, it is possible to implement a genetic algorithm or any reinforcement learning machine.

    Finally, the strategy will re-inject the news parameters (if better are found) or just update its internal state.
    """

    _name: str
    _strategy_service: StrategyService

    _parameters: Dict[str, Union[str, int, float, Tuple, Dict]]

    _autoclean: bool

    def __init__(self, name: str,
                 strategy_service: StrategyService,
                 parameters: dict):
        """
        @param name: Trainer unique name
        @param strategy_service: Strategy service instance
        @param parameters: From strategy
        """
        self._name = name
        self._strategy_service = strategy_service

        self._parameters = copy.copy(parameters)

        self._autoclean = self._parameters.get("autoclean", True)

    @property
    def name(self) -> str:
        return self._name

    @property
    def service(self) -> StrategyService:
        return self._strategy_service

    @property
    def parameters(self) -> dict:
        """Configuration default merge with users"""
        return self._parameters

    def specific_parameters(self, market_id: str) -> dict:
        """Strategy trader parameters overloaded by per market-id specific if exists"""
        if market_id in self._parameters['markets']:
            return merge_parameters(self._parameters, self._parameters['markets'][market_id])
        else:
            return self._parameters

    #
    # internal processing
    #

    def iterate(self, n: int):
        return True

    def process_iterations(self):
        return True

    #
    # processing (overload)
    #

    def prefetch_market_data(self, broker_id: str, market_id: str,
                             from_datetime: datetime,
                             to_datetime: datetime,
                             ohlc_depths: Optional[dict[float]] = None,
                             tick_depth: Optional[int] = None,
                             order_book_depth: Optional[int] = None):
        """
        This method must check that data are stored locally before processing.
        If some data are missing then a separate process must be called to fetch necessary data.

        For example fetching an OHLC or trades/ticks history for the period to process the trainer.

        @param broker_id str Valid broker identifier
        @param market_id str Valid market identifier
        @param from_datetime datetime
        @param to_datetime datetime
        @param ohlc_depths A dict of timeframe with an integer value depth of history or -1 for full update from
            last stored point
        @param tick_depth An integer of depth value of ticks/trader or -1 for full update from last stored point
        @param order_book_depth An integer of order book size

        @return: True if success. If False is return the process will not be continued.

        @note Can be problematic for getting older tick/trade data because the fetcher and data storage only supports
            appends.
        @note For OHLC they must be fetched or built for the period of test plus the history necessary.
        """
        return True

    def process(self):
        """
        This method process a separate process in way to optimize a dataset or to fit strategy parameters
        calling a backtesting.

        @return: True if success. If False is return the process will not be completed and no news parameters
            will be injected into the strategy.
        """
        return True

    def complete(self):
        """
        This method check the optimized dataset or the newly optimized parameters of the strategy and
        finally inject them into the running strategy in live without changing the actives or pending trades.

        @return: True if success. If False is return the process will be incomplete and not changes will be applied.
        """
        return True

    def cleanup(self, broker_id: str, market_id: str, before_datetime: datetime,
                ohlc_depths: Optional[dict[float]] = None,
                tick_depth: Optional[int] = None,
                order_book_depth: Optional[int] = None):
        """
        This method can clean up older prefetched dataset.
        """
        self.default_cleanup(broker_id, market_id, before_datetime, ohlc_depths, tick_depth, order_book_depth)

    #
    # helpers
    #

    def start(self, strategy_trader: StrategyTrader):
        strategy = self._strategy_service.strategy()

        if strategy_trader is None:
            return False

        market_id = strategy_trader.instrument.market_id

        for watcher_type, watcher in strategy_trader.instrument.watchers().items():
            if watcher_type == watcher.WATCHER_PRICE_AND_VOLUME:
                from_datetime = None
                to_datetime = None

                ohlc_depths = None
                tick_depth = None
                order_book_depth = None

                # @todo
                self.prefetch_market_data(watcher.name, market_id,
                                          from_datetime, to_datetime,
                                          ohlc_depths, tick_depth, order_book_depth)

                if self._autoclean:
                    before_datetime = from_datetime

                    self.cleanup(watcher.name, market_id, before_datetime,
                                 ohlc_depths, tick_depth, order_book_depth)

        return True

    def read_strategy_results(self):
        pass

    def write_strategy_parameters(self):
        pass

    def default_cleanup(self, broker_id: str, market_id: str, before_datetime: datetime,
                        ohlc_depths: Optional[dict[float]] = None,
                        tick_depth: Optional[int] = None,
                        order_book_depth: Optional[int] = None):

        for ohlc, depth in ohlc_depths.items():
            # @todo calculer la portion de date qui peut etre supprime pour les OHLC
            pass

        if tick_depth:
            # @todo pareil mais pour les tick/trades et donc quel(s) fichiers peuvent etre efface
            pass

        if order_book_depth:
            # no stored data
            pass

    def apply_to_strategy_trader(self, strategy_trader: StrategyTrader):
        strategy = self._strategy_service.strategy()

        if strategy_trader is None:
            return False

        market_id = strategy_trader.instrument.market_id

        # @todo

        return True

    #
    # static
    #

    @staticmethod
    def parse_parameters(parameters: dict) -> dict:
        return parameters
