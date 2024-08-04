# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy service

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Type, Optional

if TYPE_CHECKING:
    from watcher.service import WatcherService
    from trader.service import TraderService
    from monitor.service import MonitorService
    from common.watchdog import WatchdogService
    from .alert.alert import Alert
    from .region.region import Region
    from .tradeop.tradeop import TradeOp
    from .indicator.indicator import Indicator

from typing import Union

import time
import threading
import traceback

from datetime import datetime
from importlib import import_module

from common.service import Service
from common.workerpool import WorkerPool
from common.signal import Signal
from common.utils import format_delta

from terminal.terminal import Terminal

from .strategy import Strategy
from .strategyexception import StrategyServiceException

from config import utils

import logging
logger = logging.getLogger('siis.strategy.service')
error_logger = logging.getLogger('siis.error.strategy.service')
traceback_logger = logging.getLogger('siis.traceback.strategy.service')


class StrategyService(Service):
    """
    Strategy service is responsible for build, initialize, load configuration, start/stop the strategy.
    """

    _watcher_service: WatcherService
    _trader_service: TraderService
    _monitor_service: MonitorService

    _strategy: Union[Strategy, None]

    def __init__(self, watcher_service: Optional[WatcherService], trader_service: Optional[TraderService],
                 monitor_service: Optional[MonitorService], options: dict):
        super().__init__("strategy", options)

        self._strategies = {}
        self._indicators = {}
        self._tradeops = {}
        self._regions = {}
        self._alerts = {}

        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._monitor_service = monitor_service

        self._identity = options.get('identity', 'demo')
        self._report_path = options.get('reports-path', './')
        self._watcher_only = options.get('watcher-only', False)
        self._profile = options.get('profile', 'mixins')
        self._fetch_delay = options.get('delay', 0.0)
        self._learning = options.get('learning')  # trainer input and output file

        self._indicators_config = utils.load_config(options, 'indicators')
        self._tradeops_config = utils.load_config(options, 'tradeops')
        self._regions_config = utils.load_config(options, 'regions')
        self._alerts_config = utils.load_config(options, 'alerts')
        self._strategies_config = utils.load_config(options, 'strategies')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)
        self._learning_config = utils.load_learning(options, self._learning)
        self._learning_path = options['learning-path']

        # backtesting options
        self._backtesting = options.get('backtesting', False)
        self._from_date = options.get('from')  # UTC tz
        self._to_date = options.get('to')  # UTC tz
        self._timestep = options.get('timestep', 60.0)
        self._timeframe = options.get('timeframe', 0.0)
        self._training = options.get('training', False)

        self._timestamp = 0.0  # in backtesting current processed timestamp

        self._strategy = None

        self._load_on_startup = options.get('load', False)
        self._terminate_on_exit = False
        self._save_on_exit = False
        self._completed = False

        # cannot be more recent than now
        from common.utils import UTC
        today = datetime.now().astimezone(UTC())

        if self._from_date and self._from_date > today:
            self._from_date = today

        if self._to_date and self._to_date > today:
            self._to_date = today

        if not self._to_date:
            self._to_date = today

        self._backtest = False
        self._backtesting_play = True
        self._begin_ts = self._from_date.timestamp() if self._from_date else 0
        self._end_ts = self._to_date.timestamp() if self._to_date else 0
        self._timestep_thread = None
        self._time_factor = 0.0
        self._backtest_progress = 0.0

        self._check_trades_at_start = options.get('check-trades', False)

        if self._backtesting:
            # can use the time factor in backtesting only
            self._time_factor = options.get('time-factor', 0.0)

        # paper mode options
        self._paper_mode = options.get('paper-mode', False)

        self._next_key = 1

        # worker pool of jobs for running data analysis
        self._worker_pool = WorkerPool()

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def learning_path(self) -> str:
        return self._learning_path

    @property
    def profile_config(self) -> dict:
        return self._profile_config

    @property
    def watcher_service(self) -> WatcherService:
        return self._watcher_service

    @property
    def trader_service(self) -> TraderService:
        return self._trader_service

    @property
    def monitor_service(self) -> MonitorService:
        return self._monitor_service

    @property
    def worker_pool(self) -> WorkerPool:
        return self._worker_pool

    @property
    def tradeops(self) -> Dict[str, Type[TradeOp]]:
        return self._tradeops

    @property
    def regions(self) -> Dict[str, Type[Region]]:
        return self._regions

    @property
    def alerts(self) -> Dict[str, Type[Alert]]:
        return self._alerts

    @property
    def load_on_startup(self) -> bool:
        return self._load_on_startup

    @property
    def save_on_exit(self) -> bool:
        return self._save_on_exit

    @property
    def terminate_on_exit(self) -> bool:
        return self._terminate_on_exit

    @property
    def check_trades_at_start(self) -> bool:
        return self._check_trades_at_start

    def set_activity(self, status: bool):
        """
        Enable/disable execution of orders on strategy
        """
        if self._strategy:
            self._strategy.set_activity(status)

    def toggle_play_pause(self):
        """
        Toggle backtesting play/pause.
        Pause timer.
        """
        if self._backtesting and self._backtest:
            self._backtesting_play = not self._backtesting_play

        return self._backtesting_play

    def play_backtesting(self):
        self._backtesting_play = True

    def pause_backtesting(self):
        self._backtesting_play = False

    def set_save_on_exit(self, status):
        self._save_on_exit = status

    def set_terminate_on_exit(self, status):
        self._terminate_on_exit = status

    @property
    def backtest_progress(self) -> float:
        return self._backtest_progress

    @property
    def completed(self):
        """
        When a backtest is completed returns True.
        """
        return self._completed

    def start(self, options: dict):
        # indicators
        for k, indicator in self._indicators_config.items():
            if indicator.get("status") is not None and indicator.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = indicator.get('classpath').split('.')

                try:
                    module = import_module('.'.join(parts[:-1]))
                    Clazz = getattr(module, parts[-1])
                except Exception as e:
                    traceback_logger.error(traceback.format_exc())
                    raise

                if not Clazz:
                    raise StrategyServiceException("Cannot load indicator %s" % k) 

                self._indicators[k] = Clazz

        # tradeops
        for k, tradeop in self._tradeops_config.items():
            if tradeop.get("status") is not None and tradeop.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = tradeop.get('classpath').split('.')

                try:
                    module = import_module('.'.join(parts[:-1]))
                    Clazz = getattr(module, parts[-1])
                except Exception as e:
                    traceback_logger.error(traceback.format_exc())
                    raise

                if not Clazz:
                    raise StrategyServiceException("Cannot load tradeop %s" % k) 

                self._tradeops[k] = Clazz

        # regions
        for k, region in self._regions_config.items():
            if region.get("status") is not None and region.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = region.get('classpath').split('.')

                try:
                    module = import_module('.'.join(parts[:-1]))
                    Clazz = getattr(module, parts[-1])
                except Exception as e:
                    traceback_logger.error(traceback.format_exc())
                    raise

                if not Clazz:
                    raise StrategyServiceException("Cannot load region %s" % k) 

                self._regions[k] = Clazz

        # alerts
        for k, alert in self._alerts_config.items():
            if alert.get("status") is not None and alert.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = alert.get('classpath').split('.')

                try:
                    module = import_module('.'.join(parts[:-1]))
                    Clazz = getattr(module, parts[-1])
                except Exception as e:
                    traceback_logger.error(traceback.format_exc())
                    raise

                if not Clazz:
                    raise StrategyServiceException("Cannot load alert %s" % k) 

                self._alerts[k] = Clazz

        # strategies
        for k, strategy in self._strategies_config.items():
            if k == "default":
                continue

            if strategy.get("status") is not None and strategy.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = strategy.get('classpath', "strategy.strategy.Strategy").split('.')

                try:
                    module = import_module('.'.join(parts[:-1]))
                    Clazz = getattr(module, parts[-1])

                    parts = strategy.get('strategytrader', {}).get('classpath', "").split('.')

                    module = import_module('.'.join(parts[:-1]))
                    TraderClazz = getattr(module, parts[-1])

                    parts = strategy.get('parameters', {}).get('classpath', "")

                    module = import_module(parts)
                    DefaultParams = getattr(module, 'DEFAULT_PARAMS')

                    parts = strategy.get('options', {}).get('processor', 'alphaprocess')

                    module = import_module(parts)
                    ProcessModule = module
                except Exception as e:
                    traceback_logger.error(traceback.format_exc())
                    raise

                if not Clazz:
                    raise StrategyServiceException("Cannot load strategy %s" % k)

                if not TraderClazz:
                    raise StrategyServiceException("Cannot load strategy trader for strategy %s" % k)

                if not DefaultParams:
                    raise StrategyServiceException("Cannot load strategy DEFAULT_PARAMS for strategy %s" % k)

                if not ProcessModule:
                    raise StrategyServiceException("Cannot load strategy processor for strategy %s" % k)

                self._strategies[k] = (Clazz, TraderClazz, DefaultParams, ProcessModule)

        if self._watcher_only:
            return

        # and finally strategy
        strategy_profile = self._profile_config.get('strategy')
        if not strategy_profile or strategy_profile.get('name', "") == "default":
            return

        if self._strategy is not None:
            Terminal.inst().error("Strategy %s already started" % self._strategy.name)
            return

        # override strategy parameters
        parameters = strategy_profile.get('parameters', {})

        if not strategy_profile or not strategy_profile.get('name'):
            error_logger.error("Invalid strategy configuration for strategy %s. Ignored !" % strategy_profile['name'])

        strategy = self._strategies.get(strategy_profile['name'])
        if not strategy:
            error_logger.error("Unknown strategy name %s. Ignored !" % strategy_profile['name'])
            return

        # merge learning file options to user params before instantiate
        if self._learning_config:
            utils.merge_learning_config(parameters, self._learning_config)

        strategy_inst = strategy[0](
                # strategy name
                strategy_profile['name'],
                # services
                self, self.watcher_service, self.trader_service,
                # strategy trader clazz
                strategy[1],
                # options, default param, user params
                self._profile_config, default_parameters=strategy[2], user_parameters=parameters,
                # strategy processor module
                processor=strategy[3])

        strategy_inst.set_identifier(strategy_profile.get('id', strategy_profile['name']))

        if strategy_inst.start(options):
            self._strategy = strategy_inst
        else:
            error_logger.error("Unable to start strategy name %s. Ignored !" % strategy_profile['name'])
            return

        # start the worker pool
        self._worker_pool.start()

    def terminate(self):
        if self._timestep_thread and self._timestep_thread.is_alive():
            # abort backtesting
            if not self._backtesting_play:
                self._backtesting_play = True

            self._timestep_thread.abort = True
            self._timestep_thread.join()
            self._timestep_thread = None

        # term trainer subprocesses
        from strategy.learning.trainer import Trainer
        if Trainer.has_executors():
            Terminal.inst().info("Terminate trainer executors...")
            Trainer.term_executors()

        if self._strategy:
            strategy = self._strategy

            # stop all workers
            if strategy.running:
                strategy.stop()

            # join them
            if strategy.thread.is_alive():
                strategy.thread.join()

            # and save state to database
            if not self.backtesting and (strategy.trader() and not strategy.trader().paper_mode):
                try:
                    if self._terminate_on_exit:
                        Terminal.inst().info("Terminate strategy...")
                        strategy.terminate()

                    if self._save_on_exit:
                        Terminal.inst().info("Save strategy...")
                        strategy.save()

                except Exception as e:
                    error_logger.error(repr(e))
                    error_logger.error(traceback.format_exc())

            Terminal.inst().info("Strategy terminated.")

        # terminate the worker pool
        Terminal.inst().info("Stopping strategy worker pool...")
        self._worker_pool.stop()
        Terminal.inst().info("Strategy worker pool stopped.")

        self._strategy = None

        self._strategies = {}
        self._indicators = {}
        self._regions = {}
        self._alerts = {}

    def sync(self):
        """
        Initial backtesting if necessary. First wait for any market data to be ready.
        Then start a thread. This thread will first bootstrap/preprocess with history if necessary (timeless iteration),
        then after that it process the backtest until ending time (time iteration).

        The abort state stop any loop immediately.

        @note Trader service is called per loop during only the time iteration of the backtest. That's mean the
        instanced paper trader has no dedicated thread in that case (different from a live mode). And the ping/pong
        message are only processing during the (time iteration) where there trader update are processed.

        @note Strategy workers are only instanced if there is at least 4 instruments to performs. Else the processing
        in synchronous.

        @note During live mode the preparing/bootstrapping steps are done before processing of the strategy if
        necessary and in the real time iteration. It is different because in live mode we cannot stop the time.
        """
        # start backtesting
        if self._backtesting and not self._backtest:
            go_ready = True

            self._backtest_progress = 0.0

            if self._strategy:
                strategy = self._strategy
                if not strategy.running or not strategy.backtest_ready():
                    go_ready = False

            if go_ready:
                # start the time thread once the strategy instance get its data and are ready
                class TimeStepThread(threading.Thread):

                    def __init__(self, service, begin, end, timestep, base_timeframe=0.0, time_factor=0.0):
                        super().__init__(name="backtest")

                        self.service = service
                        self.abort = False

                        self.begin = begin
                        self.end = end
                        self.current = begin

                        self.timestep = timestep
                        self.time_factor = time_factor
                        self.base_timeframe = base_timeframe

                        # bench begin and end timestamp
                        self.begin_ts = 0
                        self.end_ts = 0

                    def run(self):
                        # complete the preprocessing and bootstrapping. don't want time progression until any
                        # strategy traders be prepared.
                        _strategy = self.service.strategy()
                        trader = _strategy.trader() if _strategy else None

                        Terminal.inst().info("Preparing strategy...", view='status')

                        while not _strategy.backtest_prepared():
                            # now sync the trader base time
                            trader.set_timestamp(self.current)

                            # need initial timestamp for bootstrapping
                            _strategy.backtest_prepare(self.current)

                            time.sleep(0.000001)  # yield

                            if self.abort:
                                break

                        if self.abort:
                            return

                        # now can perform backtest
                        Terminal.inst().info("Backtesting started...", view='status')

                        self.begin_ts = time.time()   # bench

                        if _strategy and trader:
                            while self.current < self.end + self.timestep:
                                if not self.service.backtesting_play:
                                    time.sleep(0.01)
                                    continue

                                # now sync the trader base time
                                trader.set_timestamp(self.current)

                                _strategy.backtest_update(self.current, self.end)

                                if self.time_factor > 0:
                                    # wait factor of time step, so 1 mean realtime simulation,
                                    # 0 mean as fast as possible
                                    time.sleep((1/self.time_factor)*self.timestep)

                                self.current += self.timestep  # add one time step
                                self.service._timestamp = self.current

                                # one more step, then we can update trader (limits orders, P/L update...)
                                trader.update()

                                if trader._ping:
                                    trader.pong(time.time(), trader._ping[0], trader._ping[1], trader._ping[2])
                                    trader._ping = None

                                time.sleep(0.000001)  # yield

                                if self.abort:
                                    break

                        self.end_ts = time.time()

                self._timestep_thread = TimeStepThread(self, self._begin_ts, self._end_ts, self._timestep,
                                                       self._timeframe, self._time_factor)
                self._timestep_thread.setDaemon(True)
                self._timestep_thread.start()

                # backtesting started, avoid re-enter
                self._backtest = True               

        if self._backtesting and self._backtest and self._backtest_progress < 100.0:
            progress = 0

            strategy = self._strategy
            if strategy and strategy.running:
                progress += strategy.progress()

            total = self._end_ts - self._begin_ts
            remaining = self._end_ts - progress

            pc = 100.0 - (remaining / (total+0.001) * 100)

            if pc - self._backtest_progress >= 1.0 and pc < 100.0:
                self._backtest_progress = pc
                Terminal.inst().info("Backtesting %s%%..." % round(pc), view='status')

            if self._end_ts - progress <= 0.0:
                # finished !
                self._backtest_progress = 100.0

                # backtesting done => waiting user
                Terminal.inst().info("Backtesting 100% finished !", view='status')

                # bench message
                logger.info("Backtested %i samples within a duration of %s" % (
                    int((self._timestep_thread.current - self._timestep_thread.begin) / self._timestep_thread.timestep),
                    format_delta(self._timestep_thread.end_ts - self._timestep_thread.begin_ts)))

                # write trainer output data if specified
                if self._learning:
                    self._strategy.write_trainer_report(self._learning_path, self._learning, self._learning_config)

                self._completed = True

    def notify(self, signal_type: int, source_name: str, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_STRATEGY, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def command(self, command_type: int, data: dict) -> Union[dict, None]:
        results = None

        strategy = self._strategy

        if strategy:
            results = strategy.command(command_type, data)

        return results

    def __gen_command_key(self) -> int:
        with self._mutex:
            next_key = self._next_key
            self._next_key += 1

            return next_key

    def receiver(self, signal: Signal):
        pass

    def indicator(self, name: str) -> Union[Type[Indicator], None]:
        """Return a specific indicator model by its name"""
        return self._indicators.get(name)

    def strategy(self) -> Strategy:
        """Return the instanced strategy"""
        return self._strategy

    def strategy_name(self) -> Union[str, None]:
        """Returns the name of the loaded strategy"""
        return self._strategy.name if self._strategy else None

    def strategy_identifier(self) -> Union[str, None]:
        """Returns the identifier of the loaded strategy"""
        return self._strategy.identifier if self._strategy else None

    @property
    def timestamp(self) -> float:
        """Current live or backtesting timestamp"""
        return self._timestamp if self._backtesting else time.time()

    @property
    def paper_mode(self) -> bool:
        """True in paper trading mode"""
        return self._paper_mode

    @property
    def fetch_delay(self) -> bool:
        """Optional additional data fetching delay (between 2 calls)"""
        return self._fetch_delay

    @property
    def backtesting(self) -> bool:
        """True if backtesting"""
        return self._backtesting

    @property
    def backtesting_play(self) -> bool:
        """True if backtesting playing"""
        return self._backtesting_play

    @property
    def training(self) -> bool:
        """True if training option enable in backtesting"""
        return self._training

    @property
    def from_date(self) -> datetime:
        """Backtesting starting datetime"""
        return self._from_date

    @property
    def to_date(self) -> datetime:
        """Backtesting ending datetime"""
        return self._to_date

    @property
    def timeframe(self) -> float:
        """Backtesting base timeframe"""
        return self._timeframe

    @property
    def report_path(self) -> str:
        """Base path where to store strategy reports"""
        return self._report_path

    def strategy_config(self) -> dict:
        """Get the strategy configurations as dict"""
        return self._strategies_config

    def indicator_config(self, name: str) -> dict:
        """Get the configurations for an indicator as dict"""
        return self._indicators_config.get(name, {})

    def tradeop_config(self, name: str) -> dict:
        """Get the configurations for a tradeop as dict"""
        return self._tradeops_config.get(name, {})

    def ping(self, timeout: float):
        if self._mutex.acquire(timeout=timeout):
            strategy = self._strategy
            if strategy:
                strategy.ping(timeout)

            self._worker_pool.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service: WatchdogService, timeout: float):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping strategy
            strategy = self._strategy
            if strategy:
                strategy.watchdog(watchdog_service, timeout)

            # and workers
            self._worker_pool.watchdog(watchdog_service, timeout)

            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (
                self.name, timeout))
