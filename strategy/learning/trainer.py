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

from common.utils import timeframe_from_str, period_from_str
from config import utils
from config.utils import get_stats
from terminal.terminal import Terminal
from .trainerselect import trainer_selection

if TYPE_CHECKING:
    from strategy.strategytraderbase import StrategyTraderBase
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

    Trainer model must be simply specialized for the two following class members :
        - NAME: Unique name of the trainer method (@see DummyTrainer)
        - COMMANDER: Reference to the specialized class of TrainerCommander (@see DummyTrainerCommander)

    It is necessary to provide them so then the trainer tool could retrieve and import the module correctly.

    @todo A fetcher mode doing a simple HTTP GET in place of starting process, in the case trainers are done apart
    """

    NAME = ""

    MODE_NONE = 0
    MODE_CALLING = 1
    MODE_FETCHING = 2

    MAX_TRAINER = 1         # Maximum trainer running at the same time (specially on local to keep a fair CPU load)
    RETRY_DELAY = 2.0 * 60  # Delay to wait before retry
    COMMANDER = None        # must be set to a TrainerCommander class

    processing = {}   # current market-id in process market-id/thread

    def __init__(self, strategy_trader: StrategyTraderBase, params):
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

        period = period_from_str(trainer_params.get('period', '1w'))
        update = period_from_str(trainer_params.get('update', '1w'))
        selection = trainer_params.get('selection', 'best-performance')

        self._period = period
        self._update = update
        self._selection = selection

        timestep = trainer_params.get('timestep', 60.0)
        timeframe = timeframe_from_str(trainer_params.get('timeframe', 't'))

        self._timestep = timestep
        self._timeframe = timeframe

        self._parallel = trainer_params.get('parallel', 1)
        self._fitness = trainer_params.get('fitness', 'default')

        self._next_update = 0.0
        self._working = False      # work in progress

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

        # initial stats values for comparisons/triggers (not used)
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
    def fitness(self) -> int:
        return self._fitness

    @property
    def selection(self) -> int:
        return self._selection

    @property
    def original_strategy_trader_params(self) -> dict:
        return self._strategy_trader_params

    @property
    def working(self) -> bool:
        return self._working

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

            self._working = True

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

    def adjust_date_and_last_n(self, from_date: datetime, to_date: datetime) -> tuple[datetime, datetime]:
        # crypto are h24, d7, nothing to do
        strategy_trader = self._strategy_trader
        instrument = strategy_trader.instrument

        if instrument.market_type == instrument.TYPE_CRYPTO:
            return from_date, to_date

        # there are weekend off and nationals days off
        # but this does not count the regionals holidays
        day_generator = (from_date + timedelta(x + 1) for x in range((to_date - from_date).days))
        days_off = sum(1 for day in [from_date] + list(day_generator) if day.weekday() >= 5)

        from_date -= timedelta(days=days_off)

        return from_date, to_date

    def compute_period(self) -> tuple[datetime, datetime]:
        strategy_trader = self._strategy_trader
        strategy = strategy_trader.strategy

        now_dt = datetime.utcfromtimestamp(strategy.timestamp)
        from_dt = now_dt - timedelta(seconds=self._period)

        return self.adjust_date_and_last_n(from_dt, now_dt)

    def complete(self, learning_result):
        """
        Complete the computation of the learning processing, finalize the results and apply them.
        Finally, play the strategy for both modes and the backtesting process only for backtest mode.
        @param learning_result: dict
        """
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
            logger.info("No results found from training, no changes to apply for %s. Set in pause !" %
                        strategy_trader.instrument.market_id)

            # no results meaning undetermined ability then pause the market until manual or next training
            strategy_trader.set_activity(False)
        else:
            # log summary, will display in primary console
            logger.info("Best performance for %s : %s" % (strategy_trader.instrument.market_id, performance))
            log_summary(learning_result)

            logger.info("Trainer apply new parameters to %s." % strategy_trader.instrument.market_id)
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

            if not strategy_trader.activity:
                logger.info("Strategy trader %s was in pause, now enable it !" % strategy_trader.instrument.market_id)
                strategy_trader.set_activity(True)

        # training state
        self._working = False

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
    def create_trainer(strategy_trader: StrategyTraderBase, params: dict) -> Union[Trainer, None]:
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
    def caller(identity: str, profile: str, learning_path: str, strategy_trader: StrategyTraderBase, profile_config: dict):
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

        if len(Trainer.processing) >= Trainer.MAX_TRAINER:
            logger.debug("Current %i/%i trainer(s) are in progress. Retry in %s seconds to train market %s" % (
                len(Trainer.processing), Trainer.MAX_TRAINER, Trainer.RETRY_DELAY, market_id))

            trainer._next_update = time.time() + Trainer.RETRY_DELAY
            return False

        from_dt, to_dt = trainer.compute_period()

        trainer_params['from'] = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['to'] = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        trainer_params['timestep'] = trainer.timestep
        trainer_params['fitness'] = trainer.fitness
        trainer_params['selection'] = trainer.selection

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
                code = None

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
                            # stdout, stderr = process.communicate(timeout=0.1)

                            while 1:
                                stdout = process.stdout.readline()
                                if not stdout:
                                    break

                                msg = stdout.decode()
                                if msg:
                                    if msg.startswith("["):
                                        while 1:
                                            i = msg.find("[")
                                            if i >= 0:
                                                j = msg.find("m", i + 1)
                                                if j > 0:
                                                    msg = msg[:i] + msg[j + 1:]
                                                else:
                                                    break
                                            else:
                                                break

                                    if "error" in msg.lower():
                                        logger.error("Error during process of training for %s" % market_id)
                                        process.kill()
                                    elif "Progress " in msg:
                                        Terminal.inst().message("%s for %s" % (msg.rstrip('\n'), market_id), view='default')
                                    elif "Estimate total duration to " in msg:
                                        logger.debug("%s for %s" % (msg.rstrip('\n'), market_id))

                        except subprocess.TimeoutExpired:
                            pass

                        except IOError:
                            pass

                self._process = None

                if self._market_id in Trainer.processing:
                    del Trainer.processing[self._market_id]

                if code is None:
                    logger.error("Cannot run trainer process !")
                    logger.error(msg)

                    utils.delete_learning(learning_path, learning_filename)
                    return False
                elif code != 0:
                    logger.error("Trainer process terminated with error code %s !" % process.returncode)
                    logger.error(msg)

                    utils.delete_learning(learning_path, learning_filename)
                    return False
                else:
                    logger.info("Trainer process completed, lookup for results...")

                    # retrieve trainer
                    _strategy = self._strategy_service.strategy()
                    if not _strategy:
                        utils.delete_learning(learning_path, learning_filename)
                        return False

                    _strategy_trader = _strategy.strategy_trader(self._market_id)
                    if not _strategy_trader:
                        utils.delete_learning(learning_path, learning_filename)
                        return False

                    _trainer = _strategy_trader.trainer
                    if not _trainer:
                        utils.delete_learning(learning_path, learning_filename)
                        return False

                    learning_result = utils.load_learning(learning_path, learning_filename)
                    # logger.debug(learning_result)
                    utils.delete_learning(learning_path, learning_filename)

                    # analyse results and apply to strategy trader
                    _trainer.complete(learning_result)
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
    """
    The trainer caller must be specialized per each computed individu.
    It manages internal individu generation states and take the result back through the call of the set_result method.
    """

    def set_result(self, results):
        pass


class TrainerJob(threading.Thread):
    """
    A job start a distinct process to compute and communicate using a learning file (training_HASHID.json).

    Each job is started in its unique thread and uses a Popen process to manage the distinct process :
        - either an instance of Python SiiS in backtesting mode,
        - either an instance of C++ Siis Revolution in backtesting mode.

    The callback must be defined manage the process, the communication file, filtering the results and adjusts the
    fitness score.

    The signature of the callback is :
        callback(learning_parameters: dict, profile_name: str, caller: Union[TrainerJob, None]) -> Any

    The caller parameters is self TrainerJob.
    The return type is any object containing the results.

    One TrainerCaller per individu (analyse + results) and must override the set_result method.
    """

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
        self._learning_path = None
        self._learning_filename = None

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

        # make sure the "trainer_*.json" file is removed
        if self._learning_filename:
            utils.delete_learning(self._learning_path, self._learning_filename)
            self._learning_filename = None

    def term_process(self):
        if self._process:
            self._process.terminate()
            self._process = None

    def on_start(self, process, learning_path, learning_filename):
        self._process = process
        self._learning_path = learning_path
        self._learning_filename = learning_filename


class TrainerCommander(object):
    """
    The trainer commander is the main entry of the trainer and must be specialized (@see DummyTrainerCommander)
    The name of the specialized class must be defined into a specialization of the Trainer class (@see Trainer)
    """

    BEST_PERF = 0            # best performance in percentage.
    BEST_PROFIT = 1          # best profit in currency.
    BEST_WINRATE = 2         # best win-rate (win number of trade / loss number of trade)
    LOWER_CONT_LOSS = 3      # lesser contiguous losses
    TAKE_PROFIT_RATIO = 4    # best ratio of trade exit at take profit versus other exits
    BEST_AVG_MFE = 5         # greater value for the average MFE factor
    BEST_AVG_MAE = 6         # nearest from 0 for the average MAE factor
    BEST_AVG_ETD = 7         # nearest from 0 for the average ETD factor
    BEST_STDDEV_MFE = 8      # lower MFE std-dev crossed with higher avg MFE
    BEST_STDDEV_MAE = 9      # lower MAE std-dev crossed with higher avg MAE
    BEST_STDDEV_ETD = 10     # lower ETD std-dev crossed with higher avg ETD
    HIGHER_AVG_EEF = 11      # higher average entry efficiency
    HIGHER_AVG_XEF = 12      # higher average exit efficiency
    HIGHER_AVG_TEF = 13      # higher average total (entry and exit) efficiency
    BEST_WIN_LOSS_RATE = 14  # higher winning/loosing rate
    BEST_SHARPE_RATIO = 30   # higher Sharpe ratio
    BEST_SORTINO_RATIO = 31  # higher Sortino ratio
    BEST_ULCER_INDEX = 32    # lower Ulcer index

    SELECTION = {
        'best-performance': BEST_PERF,
        'best-profit': BEST_PROFIT,
        'best-perf': BEST_PERF,
        'best-winrate': BEST_WINRATE,
        'lower-cont-loss': LOWER_CONT_LOSS,
        'take-profit-ratio': TAKE_PROFIT_RATIO,
        'best-avg-mfe': BEST_AVG_MFE,
        'best-avg-mae': BEST_AVG_MAE,
        'best-avg-etd': BEST_AVG_ETD,
        'best-stddev-mfe': BEST_STDDEV_MFE,
        'best-stddev-mae': BEST_STDDEV_MAE,
        'best-stddev-etd': BEST_STDDEV_ETD,
        'higher-avg-entry-efficiency': HIGHER_AVG_EEF,
        'higher-avg-exit-efficiency': HIGHER_AVG_XEF,
        'higher-avg-total-efficiency': HIGHER_AVG_TEF,
        'best-win-loss-rate': BEST_WIN_LOSS_RATE,
        'best-sharpe-ratio': BEST_SHARPE_RATIO,
        'best-sortino-ratio': BEST_SORTINO_RATIO,
        'best-ulcer-index': BEST_ULCER_INDEX,
    }

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
        """Number of parallel jobs (default 1). You should not set more than numbers of CPUs/cores"""
        self._parallel = num if num > 0 else 1

    @property
    def parallel(self) -> int:
        """Number of parallels jobs."""
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

    def evaluate_best(self, method=BEST_PERF):
        """
        Simple implementation to select the best candidate from the evaluated ones.
        @return: A single candidate or None.
        """
        return trainer_selection(self.results, self._learning_parameters, method)


def log_summary(candidate):
    # summary
    logger.info("Summary :")

    logger.info("-- performance / profit / non-realized = %s / %s / %s" % (candidate.get('performance', "0.00%"),
                                                                           candidate.get('realized-pnl', "0.00"),
                                                                           candidate.get('profit-loss', "0.00")))
    logger.info("-- max-draw-down = %s %s" % (candidate.get('max-draw-down', "0"),
                                              candidate.get('max-draw-down-rate', "0.00%")))
    logger.info("-- best / worst = %s / %s" % (candidate.get('best', "0.00%"),
                                               candidate.get('worst', "0.00%")))
    logger.info("-- # trades : total / canceled = %i / %i" % (
        candidate.get('total-trades', 0), candidate.get('canceled-trades', 0)))
    logger.info("-- # trades : succeed / failed / ROE = %i / %i / %i" % (
        candidate.get('succeed-trades', 0), candidate.get('failed-trades', 0), candidate.get('roe-trades', 0)))
    logger.info("-- max win / loss series = %i / %i" % (
        candidate.get('max-win-series', 0), candidate.get('max-loss-series', 0)))
    logger.info("-- stop-loss in gain / loss = %i / %i" % (
        candidate.get('stop-loss-in-gain', 0), candidate.get('stop-loss-in-loss', 0)))
    logger.info("-- take-profit in gain / loss = %i / %i" % (
        candidate.get('take-profit-in-gain', 0), candidate.get('take-profit-in-loss', 0)))
    logger.info("-- # trades : open / active = %i / %i" % (
        candidate.get('open-trades', 0), candidate.get('active-trades', 0)))

    # global stats
    logger.info("-- longest flat period = %s" % timedelta(seconds=float(candidate.get('longest-flat-period', '0.000'))))
    logger.info("-- avg time in market = %s" % timedelta(seconds=float(candidate.get('avg-time-in-market', '0.000'))))

    logger.info("-- # traded days = %i" % candidate.get('num-traded-days', '0'))
    logger.info("-- avg trade per day / inc WE = %g / %g" % (candidate.get('avg-trade-per-day', 0),
                                                             candidate.get('avg-trade-per-day-inc-we', 0)))

    # based on percent PNL per trade (not on quote/settlement currency)
    percent = candidate.get('percent', {})

    logger.info("-- Sharpe ratio / Sortino ratio / Ulcer index = %g / %g / %g" % (
        get_stats(candidate, 'percent.sharpe-ratio', 1),
        get_stats(candidate, 'percent.sortino-ratio', 1),
        get_stats(candidate, 'percent.ulcer-index', 0)))

    logger.info("-- MFE : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.mfe.min', 0) * 100,
        get_stats(candidate, 'percent.mfe.max', 0) * 100,
        get_stats(candidate, 'percent.mfe.avg', 0) * 100,
        get_stats(candidate, 'percent.mfe.std-dev', 0) * 100))

    logger.info("-- MAE : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.mae.min', 0) * 100,
        get_stats(candidate, 'percent.mae.max', 0) * 100,
        get_stats(candidate, 'percent.mae.avg', 0) * 100,
        get_stats(candidate, 'percent.mae.std-dev', 0) * 100))

    logger.info("-- ETD : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.etd.min', 0) * 100,
        get_stats(candidate, 'percent.etd.max', 0) * 100,
        get_stats(candidate, 'percent.etd.avg', 0) * 100,
        get_stats(candidate, 'percent.etd.std-dev', 0) * 100))

    logger.info("-- entry efficiency : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.entry-efficiency.min', 0) * 100,
        get_stats(candidate, 'percent.entry-efficiency.max', 0) * 100,
        get_stats(candidate, 'percent.entry-efficiency.avg', 0) * 100,
        get_stats(candidate, 'percent.entry-efficiency.std-dev', 0) * 100))

    logger.info("-- exit efficiency : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.exit-efficiency.min', 0) * 100,
        get_stats(candidate, 'percent.exit-efficiency.max', 0) * 100,
        get_stats(candidate, 'percent.exit-efficiency.avg', 0) * 100,
        get_stats(candidate, 'percent.exit-efficiency.std-dev', 0) * 100))

    logger.info("-- total efficiency : min / max / avg / std-dev = %.2f%% / %.2f%% / %.2f%% / %.2f%%" % (
        get_stats(candidate, 'percent.total-efficiency.min', 0) * 100,
        get_stats(candidate, 'percent.total-efficiency.max', 0) * 100,
        get_stats(candidate, 'percent.total-efficiency.avg', 0) * 100,
        get_stats(candidate, 'percent.total-efficiency.std-dev', 0) * 100))

    logger.info("-- max time to recover = %s" % timedelta(seconds=float(percent.get('max-time-to-recover', '0.000'))))
    logger.info("-- estimate profit per month = %s" % percent.get('estimate-profit-per-month', '0.00%'))
    logger.info("-- avg win/loss rate = %g" % percent.get('avg-win-loss-rate', 0))
