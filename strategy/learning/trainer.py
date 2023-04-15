# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer base class

from __future__ import annotations

import math
import random
import threading
import base64
import subprocess
import uuid
from typing import TYPE_CHECKING, Optional, Union, List, Dict, Type, Tuple, Callable

from common.utils import timeframe_from_str, truncate
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
    @todo A fetcher mode doing a simple HTTP GET in place of starting process, in the case trainers are done apart
    """

    executor = None

    NAME = ""

    COMMANDER = None  # must be set to a TrainerCommander class
    CLIENT = None     # must be set to a TrainerClient class

    processing = {}   # current market-id in process market-id/thread

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

    #
    # class builders
    #

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def create_commander(cls, profile_name: str,
                         profile_parameters: dict,
                         learning_parameters: dict) -> Union[TrainerCommander, None]:
        """
        Override this method to return an instance of TrainerCommander to be executed by the tool Trainer.
        @param profile_name: str
        @param profile_parameters: dict
        @param learning_parameters: dict
        @return: Instance of inherited TrainerCommander class
        """
        return cls.COMMANDER(profile_name, profile_parameters, learning_parameters)

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

        market_id = strategy_trader.instrument.market_id

        org_strategy_params = profile_config.get('strategy', {})
        org_learning_params = org_strategy_params.get('parameters', {}).get('learning', {})

        trainer_params = copy.deepcopy(org_learning_params.get('trainer', {}))

        # filters only necessary markets from watchers, trader and strategy
        strategy_params = copy.deepcopy(org_learning_params.get('strategy', {}))
        strategy_params['symbols'] = [market_id]

        watchers_params = {}
        for watcher_name, watcher_config in profile_config.get('watchers', {}).items():
            watchers_params[watcher_name] = {}
            if market_id in watcher_config['symbols']:
                watchers_params[watcher_name]['symbols'] = [market_id]
            else:
                watchers_params[watcher_name]['symbols'] = []

        trader_params = {'symbols': [market_id]}

        if market_id in Trainer.processing:
            logger.warning("Unable to train market %s now because previous is still waited" % market_id)
            return

        from_dt, to_dt, timeframe = Trainer.compute_period(strategy_trader, profile_config)

        trainer_params['from'] = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['to'] = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['timeframe'] = timeframe

        learning_filename = "learning_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace(
                '/', '_').replace('+', '0')

        data = {
            'created': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'trainer': trainer_params,
            'strategy': strategy_params,
            'watchers': watchers_params,
            'trader': trader_params
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
                # register the thread (executor)
                Trainer.processing[self._market_id] = self

                msg = ""

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
                            if stdout:
                                msg = stdout.decode()

                        except subprocess.TimeoutExpired:
                            pass

                    if code != 0:
                        logger.error("Trainer process terminated with error code %s !" % p.returncode)
                        logger.error(msg)

                        utils.delete_learning(learning_path, learning_filename)

                        del Trainer.processing[self._market_id]
                        return False
                    else:
                        logger.info("Trainer process completed, lookup for results...")
                        self.complete()

                        utils.delete_learning(learning_path, learning_filename)

                        del Trainer.processing[self._market_id]
                        return True

            def complete(self):
                learning_result = utils.load_learning(learning_path, learning_filename)

                _strategy = self._strategy_service.strategy()
                if not _strategy:
                    return

                _strategy_trader = strategy.strategy_trader(market_id)
                if not _strategy_trader:
                    return

                performance = learning_result.get('performance', '0.00%')

                logger.info("Best performance for %s : %s" % (_strategy_trader.instrument.market_id, performance))

                self.apply(_strategy, _strategy_trader, learning_result)

            def apply(self, _strategy: Strategy, _strategy_trader: StrategyTrader, learning_result: dict):
                logger.info("Trainer apply new parameters to %s and then restart" %
                            _strategy_trader.instrument.market_id)

                new_parameters = copy.deepcopy(_strategy.parameters)

                # merge new parameters
                utils.merge_learning_config(new_parameters, learning_result)

                # @todo setup (and subs) with new parameters

                _strategy_trader.restart()
                _strategy.send_initialize_strategy_trader(_strategy_trader.instrument.market_id)

        logger.info("Start trainer thread...")

        executor = Executor(strategy_service, market_id)
        executor.start()

    @staticmethod
    def join_executor():
        while Trainer.processing:
            market_id, processor = next(iter(Trainer.processing.items()))
            processor.join()

            del Trainer.processing[market_id]

    @staticmethod
    def setup_strategy_parameters(learning_config: dict, trainer_strategy_parameters: dict):
        strategy_parameters = learning_config.get('strategy', {}).get('parameters', {})

        for pname, pvalue in strategy_parameters.items():
            if pname.startswith('_'):
                # commented
                continue

            trainer_strategy_parameters[pname] = Trainer.set_rand_value(pvalue)

    @staticmethod
    def bind_strategy_parameters(learning_config: dict, trainer_strategy_parameters: dict):
        strategy_parameters = learning_config.get('strategy', {}).get('parameters', {})

        for pname, pvalue in strategy_parameters.items():
            if pname.startswith('_'):
                # commented
                continue

            trainer_strategy_parameters[pname] = pvalue

    @staticmethod
    def set_rand_value(param, prev=None):
        if param.get('type') == "int":
            return random.randrange(param.get('min', 0), param.get('max', 0) + 1, param.get('step', 1))

        elif param.get('type') == "float":
            precision = param.get('precision', 1) or 1
            step = param.get('step', 0.01) or 0.01

            number = random.randrange(
                param.get('min', 0) * math.pow(10, precision),
                param.get('max', 0) * math.pow(10, precision) + 1, 1) * math.pow(10, -precision)

            return truncate(round(number / step) * step, precision)

        else:
            return 0


class TrainerCommander(object):

    _profile_parameters: dict
    _learning_parameters: dict

    def __init__(self, profile_name: str, profile_parameters: dict, learning_parameters: dict):
        self._profile_name = profile_name
        self._profile_parameters = profile_parameters
        self._learning_parameters = learning_parameters

        self._params_info = []
        self._last_strategy_parameters = {}

        self.bind_parameters()

    def bind_parameters(self):
        strategy_params = self._learning_parameters.get('strategy', {}).get('parameters', {})

        for p_name, p_value in strategy_params.items():
            param = copy.copy(p_value)
            param['name'] = p_name  # for binding

            self._params_info.append(param)

    def unbind_parameters(self, individu):
        if not individu:
            return None

        strategy_params = copy.deepcopy(self._learning_parameters.get('strategy', {}).get('parameters', {}))

        for i, param_info in enumerate(self._params_info):
            strategy_params[param_info['name']] = individu.params[i]

        return strategy_params

    def start(self, callback):
        pass

    @property
    def results(self):
        return None


class TrainerClient(object):

    _profile_parameters: dict
    _trainer_parameters: dict

    def __init__(self, profile_parameters: dict, trainer_parameters: dict):
        self._profile_parameters = profile_parameters
        self._trainer_parameters = trainer_parameters
