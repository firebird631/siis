# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer base class

from __future__ import annotations

import threading
import base64
import subprocess
import time
import traceback
import uuid
from typing import TYPE_CHECKING, Union

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
    Contains the class builder for the commander.
    It is also responsible to start the sub-process of the commander by using the trainer tool.
    A learning file is created before starting the trainer tool to communicate parameters and get back the results.

    Then the strategy trader can be restart using the new optimized parameters by overloading the profile parameters
    using the newly determined ones.

    @todo Executor might be join at close or killed
    @todo A fetcher mode doing a simple HTTP GET in place of starting process, in the case trainers are done apart
    """

    NAME = ""

    MODE_NONE = 0
    MODE_CALLING = 1
    MODE_FETCHING = 2

    COMMANDER = None  # must be set to a TrainerCommander class

    processing = {}   # current market-id in process market-id/thread

    def __init__(self, strategy_trader: StrategyTrader, params):
        """
        @param strategy_trader: Strategy trader instance
        """
        self._strategy_trader = strategy_trader
        self._strategy_service = strategy_trader.strategy.service

        # keep a copy of the strategy trader parameters
        self._strategy_trader_params = copy.deepcopy(params)

        learning_params = params.get('learning')
        trainer_params = learning_params.get('trainer')

        self._initial = trainer_params.get('initial', False)  # does an initial training

        period = timeframe_from_str(trainer_params.get('period', '1w'))
        update = timeframe_from_str(trainer_params.get('update', '1w'))

        self._period = period
        self._update = update

        timestep = trainer_params.get('timestep', 60.0)
        timeframe = timeframe_from_str(trainer_params.get('timeframe', 't'))

        self._timestep = timestep
        self._timeframe = timeframe

        self._parallel = trainer_params.get('parallel', 1)
        self._next_update = 0.0

        self._mode = Trainer.MODE_NONE

        if 'fetch' in trainer_params:
            fetcher_params = trainer_params['fetch']

            self._fetch_host = fetcher_params.get('host', "")

            if self._fetch_host and self._update > 0:
                self._fetching = Trainer.MODE_FETCHING
        else:
            if self._update > 0:
                self._mode = Trainer.MODE_CALLING

        try:
            self._perf_deviation = float(trainer_params.get('performance-deviation', "0.00%").rstrip('%'))
        except ValueError:
            pass

        # initial stats values for comparisons/triggers
        self._last_perf = strategy_trader.get_stat('perf')
        self._last_worst = strategy_trader.get_stat('worst')
        self._last_best = strategy_trader.get_stat('best')
        self._last_success = strategy_trader.get_stat('success')
        self._last_failed = strategy_trader.get_stat('failed')

    @property
    def service(self) -> StrategyService:
        return self._strategy_service

    @property
    def timestep(self) -> float:
        return self._timestep

    @property
    def timeframe(self) -> float:
        return self._timeframe

    @property
    def parallel(self) -> int:
        return self._parallel

    @property
    def original_strategy_trader_params(self) -> dict:
        return self._strategy_trader_params

    def update(self, timestamp: float) -> bool:
        # init counter or does an initial training
        if self._next_update <= 0:
            if self._initial:
                # begin by a training
                self._next_update = timestamp
            else:
                # wait after duration for the first training
                self._next_update = timestamp + self._update

        if timestamp < self._next_update:
            return False

        self._next_update = self._next_update + self._update

        # @todo call or fetch
        if self._mode == Trainer.MODE_FETCHING:
            # from_dt, to_dt = self.compute_period()
            # from_str = from_dt.strftime("%Y-%m-%dT%H:%M:%S")
            # to_str = to_dt.strftime("%Y-%m-%dT%H:%M:%S")
            result = self.fetch_update()

            # @todo

            if not result:
                return False

        elif self._mode == Trainer.MODE_CALLING:
            strategy_service = self._strategy_service
            result = self.start()

            if not result:
                return False

        return True

    def fetch_update(self) -> bool:
        """
        Support for HTTP, HTTPS or local file.
        @todo rest and local file get
        """
        if self._fetch_host.startwith('http://') or self._fetch_host.startwith('https://'):
            pass
        elif self._fetch_host.startwith('file://'):
            pass

        return False

    def start(self) -> bool:
        """
        Start trainer sub-process.
        @return:
        """
        strategy_trader = self._strategy_trader
        strategy = strategy_trader.strategy

        # pause during a backtesting
        if self._strategy_service.backtesting:
            self._strategy_service.pause_backtesting()

        try:
            return Trainer.caller(strategy.service.identity, strategy.service.profile, strategy.service.learning_path,
                                  strategy_trader, strategy.service.profile_config)
        except Exception as e:
            logger.error(repr(e))

        return False

    def compute_period(self) -> tuple[datetime, datetime]:
        strategy_trader = self._strategy_trader
        strategy = strategy_trader.strategy

        now_dt = datetime.utcfromtimestamp(strategy.timestamp)
        from_dt = now_dt - timedelta(seconds=self._period)

        return from_dt, now_dt

    def complete(self, learning_result):
        strategy_trader = self._strategy_trader
        strategy = strategy_trader.strategy

        # update stats values
        self._last_perf = strategy_trader.get_stat('perf')
        self._last_worst = strategy_trader.get_stat('worst')
        self._last_best = strategy_trader.get_stat('best')
        self._last_success = strategy_trader.get_stat('success')
        self._last_failed = strategy_trader.get_stat('failed')

        performance = learning_result.get('performance', '0.00%')

        if not learning_result.get('results', []):
            logger.info("No results found from training, no changes to apply for %s" % strategy_trader.instrument.market_id)
        else:
            logger.info("Best performance for %s : %s" % (strategy_trader.instrument.market_id, performance))
            logger.info("Trainer apply new parameters to %s and then restart" % strategy_trader.instrument.market_id)

            new_parameters = copy.deepcopy(self._strategy_trader_params)

            # merge new parameters
            utils.merge_learning_config(new_parameters, learning_result)

            # display news values
            for n, v in learning_result.get('strategy', {}).get('parameters', {}).items():
                logger.info("-- %s = %s" % (n, v))

            # update strategy trader with new parameters
            strategy_trader.update_parameters(new_parameters)

            # if not self._strategy_service.backtesting:
            #     # and restart (will reload necessary OHLC...)
            #     strategy_trader.restart()
            #     strategy.send_initialize_strategy_trader(strategy_trader.instrument.market_id)

        if self._strategy_service.backtesting:
            self._strategy_service.play_backtesting()

    #
    # class methods
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

    #
    # For strategy trader : trainer instance
    #

    @staticmethod
    def create_trainer(strategy_trader: StrategyTrader, params: dict) -> Union[Trainer, None]:
        try:
            trainer = Trainer(strategy_trader, params)

            # check it is configured properly else return None
            if trainer._mode == Trainer.MODE_NONE:
                logger.error("Miss configured strategy trainer for %s" % strategy_trader.instrument.market_id)
                return None

            logger.info("Instantiate a trainer for %s" % strategy_trader.instrument.market_id)
            return trainer

        except Exception as e:
            logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        return None

    #
    # caller proxy helper
    #

    @staticmethod
    def caller(identity: str, profile: str, learning_path: str, strategy_trader: StrategyTrader, profile_config: dict):
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
        if not strategy:
            return

        trainer = strategy_trader.trainer
        if not trainer:
            return False

        market_id = strategy_trader.instrument.market_id

        org_learning_params = trainer.original_strategy_trader_params.get('learning', {})
        trainer_params = copy.deepcopy(org_learning_params.get('trainer', {}))

        # filters only necessary markets from watchers, trader and strategy
        strategy_params = {
            # 'symbols': [market_id],
            'parameters': copy.deepcopy(org_learning_params.get('strategy', {}).get('parameters', {}))
        }

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
            return False

        from_dt, to_dt = trainer.compute_period()

        trainer_params['from'] = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['to'] = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['timestep'] = trainer.timestep

        if trainer.timeframe:
            trainer_params['timeframe'] = trainer.timeframe

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
            '--timestep=%s' % trainer.timestep
        ]

        if trainer.timeframe:
            cmd_opts.append('--timeframe=%s' % trainer.timeframe)

        if trainer.parallel > 1:
            cmd_opts.append('--parallel=%i' % trainer.parallel)

        class Executor(threading.Thread):

            def __init__(self, _strategy_service: StrategyService, _market_id: str):
                super().__init__()

                self._strategy_service = _strategy_service
                self._market_id = _market_id
                self._process = None

            def term_process(self):
                if self._process:
                    self._process.terminate()
                    self._process = None

            def kill_process(self):
                if self._process:
                    self._process.kill()
                    self._process = None

            def run(self):
                # register the thread (executor)
                Trainer.processing[self._market_id] = self

                msg = ""

                with subprocess.Popen(cmd_opts,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      stdin=subprocess.DEVNULL) as process:

                    self._process = process

                    while 1:
                        code = process.poll()
                        if code is not None:
                            break

                        try:
                            stdout, stderr = process.communicate(timeout=0.1)
                            if stdout:
                                msg = stdout.decode()
                                if msg:
                                    if "error" in msg.lower():
                                        logger.error("Error during process of training for %s" % market_id)
                                        process.kill()
                                    elif "Progress " in msg:
                                        i = msg.find("Progress ")
                                        if i >= 0:
                                            j = msg[i+9:].find("%")
                                            if j >= 0:
                                                progress = msg[i+9:][:j+1]
                                                logger.debug("Training progression at %s for %s" % (progress, market_id))

                        except subprocess.TimeoutExpired:
                            pass

                        except IOError:
                            pass

                    self._process = None

                    if code != 0:
                        logger.error("Trainer process terminated with error code %s !" % process.returncode)
                        logger.error(msg)

                        utils.delete_learning(learning_path, learning_filename)

                        if self._market_id in Trainer.processing:
                            del Trainer.processing[self._market_id]
                        return False
                    else:
                        logger.info("Trainer process completed, lookup for results...")

                        # retrieve trainer
                        _strategy = self._strategy_service.strategy()
                        if not _strategy:
                            return False

                        _strategy_trader = _strategy.strategy_trader(self._market_id)
                        if not _strategy_trader:
                            return False

                        _trainer = _strategy_trader.trainer
                        if not _trainer:
                            return False

                        learning_result = utils.load_learning(learning_path, learning_filename)

                        # analyse results and apply to strategy trader
                        _trainer.complete(learning_result)

                        utils.delete_learning(learning_path, learning_filename)

                        if self._market_id in Trainer.processing:
                            del Trainer.processing[self._market_id]

                        return True

        logger.info("Start a trainer thread...")

        executor = Executor(strategy.service, market_id)
        executor.start()

        return True

    @staticmethod
    def has_executors():
        return len(Trainer.processing) > 0

    @staticmethod
    def join_executors():
        while Trainer.processing:
            market_id, processor = next(iter(Trainer.processing.items()))
            processor.join()

            del Trainer.processing[market_id]

    @staticmethod
    def kill_executors():
        while Trainer.processing:
            market_id, processor = next(iter(Trainer.processing.items()))
            processor.kill_process()

            del Trainer.processing[market_id]

    @staticmethod
    def term_executors():
        while Trainer.processing:
            market_id, processor = next(iter(Trainer.processing.items()))
            processor.term_process()

            del Trainer.processing[market_id]


class TrainerCaller(object):

    def set_result(self, results):
        pass


class TrainerJob(threading.Thread):

    def __init__(self, commander: TrainerCommander,
                 caller: TrainerCaller, callback: callable,
                 learning_parameters: dict, profile_name: str):

        super().__init__()

        self._commander = commander
        self._caller = caller
        self._callback = callback
        self._learning_parameters = learning_parameters
        self._profile_name = profile_name

        self._results = None
        self._completed = False

        self._process = None

    @property
    def process(self):
        return self._process

    @process.setter
    def process(self, process):
        self._process = process

    def run(self):
        self._results = self._callback(self._learning_parameters, self._profile_name, self)
        self._completed = True

        if self._caller and self._results is not None:
            self._caller.set_result(self._results)

        self._commander.complete_job(self)

    def kill_process(self):
        if self._process:
            self._process.kill()
            self._process = None

    def term_process(self):
        if self._process:
            self._process.terminate()
            self._process = None


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

        self._parallel = 1
        self._sub_processes = []  # for multi-processing
        self._executed_jobs = 0

    def set_parallel(self, num: int):
        self._parallel = num if num > 0 else 1

    @property
    def parallel(self) -> int:
        return self._parallel

    def estimate_duration(self, avg_job_time: float) -> float:
        """
        Overrides to return the remaining computation time.
        @param avg_job_time:
        @return:
        """
        return 0

    def progress(self) -> float:
        """
        Overrides to return the remaining computation time.
        @return: Progression in percentile.
        """
        return 0

    def join(self):
        logger.debug("join subs...")
        while self._sub_processes:
            self._sub_processes[0].join()
        logger.debug("joined subs !")

    def kill(self):
        logger.debug("kill subs jobs...")
        for process in self._sub_processes:
            process.kill_process()
        # while self._sub_processes:
        #     self._sub_processes[0].kill_process()
        logger.debug("killed subs jobs !")

    def term(self):
        logger.debug("term subs jobs...")
        for process in self._sub_processes:
            process.term_process()
        logger.debug("Terminated subs jobs !")

    def start_job(self, caller: TrainerCaller, callback: callable, learning_parameters: dict, profile_name: str):
        while len(self._sub_processes) >= self._parallel:
            # @todo optimize with a count condition
            time.sleep(1.0)

        job = TrainerJob(self, caller, callback, learning_parameters, profile_name)
        self._sub_processes.append(job)

        job.start()

    def complete_job(self, job: TrainerJob):
        if job in self._sub_processes:
            self._sub_processes.remove(job)

        self._executed_jobs += 1

    def bind_parameters(self):
        strategy_params = self._learning_parameters.get('strategy', {}).get('parameters', {})

        for p_name, p_value in strategy_params.items():
            param = copy.copy(p_value)
            param['name'] = p_name  # for binding

            self._params_info.append(param)

    def start(self, callback: callable):
        """
        Override this method to implement the starting of the evaluation/fitness method.
        @param callback:
        @return:
        """
        pass

    @property
    def results(self) -> list:
        """
        Return the best evaluated candidate during the training process.
        @return: list
        """
        return []

    def evaluate_best(self):
        """
        Simple implementation to select a best candidate from the evaluated ones.
        @return: A single candidate or None.
        """
        best_result = None
        results = self.results

        try:
            min_perf = float(self._learning_parameters.get('trainer', {}).get('min-performance', "0.00%").rstrip('%'))
        except ValueError:
            min_perf = 0.0

        max_perf = min_perf

        # simple method, the best overall performance
        for result in results:
            try:
                performance = float(result.get('performance', "0.00%").rstrip('%'))
            except ValueError:
                continue

            if performance > max_perf:
                max_perf = performance
                best_result = result

        return best_result
