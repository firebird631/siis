# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer base class

from __future__ import annotations

import threading
import base64
import subprocess
import uuid
from typing import TYPE_CHECKING, Optional, Union, List, Dict, Type, Tuple, Callable

from common.utils import timeframe_from_str
from config import utils

if TYPE_CHECKING:
    from strategy.strategy import Strategy
    from strategy.strategytrader import StrategyTrader
    from ..service import StrategyService

import copy

from datetime import datetime, timedelta

import logging
logger = logging.getLogger('siis.strategy.learning.trainer')
error_logger = logging.getLogger('siis.error.strategy.learning.trainer')
traceback_logger = logging.getLogger('siis.traceback.strategy.learning.trainer')


class Trainer(object):
    """
    Contains the class builder for the commander and the client.
    It is also responsible to start the sub-process of the commander by using the trainer tool.
    A learning file is created before starting the trainer tool to communicate parameters and get back the results.

    Then the strategy trader can be restart using the new optimized parameters by overloading the profile parameters
    using the newly determined ones.

    @todo Executor might be join at close or killed
    """

    executor = None

    NAME = ""

    COMMANDER = None  # must be set to a TrainerCommander class
    CLIENT = None     # must be set to a TrainerClient class

    def __init__(self, strategy_trader: StrategyTrader):
        """
        @param strategy_trader: Strategy trader instance
        """
        self._strategy_service = strategy_trader.strategy.service

        learning_params = strategy_trader.strategy.parameters.get('learning')
        trainer_params = learning_params.get('trainer')

        period = timeframe_from_str(trainer_params.get('period', '1w'))

        self._next_update = strategy_trader.strategy.timestamp + period

    @property
    def service(self) -> StrategyService:
        return self._strategy_service

    def need_training(self, timestamp):
        # @todo or performance deviation
        if timestamp >= self._next_update:
            self._next_update = 0.0
            return True

        return False

    def read_learning_results(self):
        # @todo
        pass

    # def default_cleanup(self, broker_id: str, market_id: str, before_datetime: datetime,
    #                     ohlc_depths: Optional[dict[float]] = None,
    #                     tick_depth: Optional[int] = None,
    #                     order_book_depth: Optional[int] = None):
    #
    #     for ohlc, depth in ohlc_depths.items():
    #         # @todo calculer la portion de date qui peut etre supprime pour les OHLC
    #         pass
    #
    #     if tick_depth:
    #         # @todo pareil mais pour les tick/trades et donc quel(s) fichiers peuvent etre efface
    #         pass
    #
    #     if order_book_depth:
    #         # no stored data
    #         pass
    #
    # def apply_to_strategy_trader(self, strategy_trader: StrategyTrader):
    #     strategy = self._strategy_service.strategy()
    #
    #     if strategy_trader is None:
    #         return False
    #
    #     market_id = strategy_trader.instrument.market_id
    #
    #     # @todo
    #
    #     return True
    #
    # #
    # # static
    # #
    #
    # @staticmethod
    # def parse_parameters(parameters: dict) -> dict:
    #     return parameters

    #
    # class builders
    #

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def create_commander(cls, profile_parameters: dict, learning_parameters: dict) -> Union[TrainerCommander, None]:
        """
        Override this method to return an instance of TrainerCommander to be executed by the tool Trainer.
        @param profile_parameters: dict
        @param learning_parameters: dict
        @return: Instance of inherited TrainerCommander class
        """
        return cls.COMMANDER(profile_parameters, learning_parameters)

    @classmethod
    def create_client(cls, profile_parameters: dict, trainer_parameters: dict) -> Union[TrainerClient, None]:
        """
        Override this method to return an instance of TrainerClient to be executed by the strategy backtesting.
        @param profile_parameters: dict
        @param trainer_parameters: dict
        @return: Instance of inherited TrainerClient class
        """
        return cls.CLIENT(profile_parameters, trainer_parameters)

    #
    # caller proxy helper
    #

    @staticmethod
    def compute_period(strategy_trader: StrategyTrader, profile_config: dict):
        learning_params = strategy_trader.strategy.parameters.get('learning')
        trainer_params = learning_params.get('trainer')

        timeframe = trainer_params.get('timeframe', 1)
        if type(timeframe) is str:
            timeframe = timeframe_from_str(timeframe)

        period = timeframe_from_str(trainer_params.get('period', '1w'))

        from_dt = datetime.utcnow() - timedelta(seconds=period)
        to_dt = datetime.utcnow()

        return from_dt, to_dt, timeframe

    @staticmethod
    def caller(identity, profile, learning_path, strategy_trader: StrategyTrader, profile_config: dict):
        """
        Must be called by a command manually or automatically according to some parameters like deviation from
        performance or a minimal duration.

        @param identity:
        @param profile:
        @param learning_path:
        @param strategy_trader:
        @param profile_config:
        @return:
        """
        strategy = strategy_trader.strategy
        strategy_service = strategy.service

        trainer_params = copy.deepcopy(profile_config.get('trainer', {}))
        strategy_params = copy.deepcopy(profile_config.get('strategy', {}))

        # filters only necessary markets from watchers, trader and strategy
        market_id = strategy_trader.instrument.market_id

        from_dt, to_dt, timeframe = Trainer.compute_period(strategy_trader, profile_config)

        trainer_params['from'] = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['to'] = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['timeframe'] = timeframe

        learning_filename = "learning_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace(
                '/', '_').replace('+', '0')

        data = {
            'created': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'trainer': trainer_params,
            'strategy': strategy_params
        }

        utils.write_learning(learning_path, learning_filename, data)

        cmd_opts = [
            'python',
            'siis.py',
            identity,
            '--tool=trainer',
            '--profile=%s' % profile,
            '--learning=%s' % learning_filename,
            '--from=%s' % from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            '--to=%s' % to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            '--timeframe=%s' % timeframe
        ]

        class Executor(threading.Thread):

            def __init__(self, _strategy_service: StrategyService, _market_id: str):
                super().__init__()

                self._strategy_service = _strategy_service
                self._market_id = _market_id

            def run(self):
                with subprocess.Popen(cmd_opts,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      stdin=subprocess.DEVNULL) as p:
                    while 1:
                        code = p.poll()
                        if code is not None:
                            break

                        try:
                            stdout, stderr = p.communicate(timeout=0.1)
                        except subprocess.TimeoutExpired:
                            pass

                    if code != 0:
                        logger.error("Trainer process terminated with error code %s !" % p.returncode)

                        utils.delete_learning(learning_path, learning_filename)
                        return False
                    else:
                        logger.info("Trainer process completed, lookup for results...")
                        self.complete()

                        utils.delete_learning(learning_path, learning_filename)
                        return True

            def complete(self):
                result = utils.load_learning(learning_path, learning_filename)

                _strategy = self._strategy_service.strategy()
                if not _strategy:
                    return

                _strategy_trader = strategy.strategy_trader(market_id)
                if not _strategy_trader:
                    return

                performance = result.get('performance', '0.00%')

                logger.info("Best performance for %s : %s" % (performance, _strategy_trader.instrument.market_id))

                self.apply(_strategy, _strategy_trader)

            def apply(self, _strategy: Strategy, _strategy_trader: StrategyTrader):
                logger.info("Trainer apply new parameters to %s and then restart" %
                            _strategy_trader.instrument.market_id)

                # @todo load and merge new parameters, setup (and subs), finally restart it

                _strategy_trader.restart()
                _strategy.send_initialize_strategy_trader(_strategy_trader.instrument.market_id)

        logger.info("Start trainer thread...")

        Trainer.executor = Executor(strategy_service, market_id)
        Trainer.executor.start()

    @staticmethod
    def join_executor():
        if Trainer.executor:
            Trainer.executor.join()
            Trainer.executor = None


class TrainerCommander(object):

    _profile_parameters: dict
    _learning_parameters: dict

    def __init__(self, profile_parameters: dict, learning_parameters: dict):
        self._profile_parameters = profile_parameters
        self._learning_parameters = learning_parameters


class TrainerClient(object):

    _profile_parameters: dict
    _trainer_parameters: dict

    def __init__(self, profile_parameters: dict, trainer_parameters: dict):
        self._profile_parameters = profile_parameters
        self._trainer_parameters = trainer_parameters
