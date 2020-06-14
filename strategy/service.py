# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker for strategy

import time
import threading
import traceback

from datetime import datetime
from importlib import import_module

from common.service import Service
from common.workerpool import WorkerPool
from common.signal import Signal
from common.utils import format_datetime, format_delta

from terminal.terminal import Terminal
from strategy.strategy import Strategy
from strategy.strategyexception import StrategyServiceException

from config import utils

import logging
logger = logging.getLogger('siis.strategy.service')
error_logger = logging.getLogger('siis.strategy.service')


class StrategyService(Service):
    """
    Strategy service is responsible of build, initialize, load configuration, start/stop the strategy.
    """

    def __init__(self, watcher_service, trader_service, monitor_service, options):
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
        self._profile = options.get('profile', 'default')

        self._indicators_config = utils.load_config(options, 'indicators')
        self._tradeops_config = utils.load_config(options, 'tradeops')
        self._regions_config = utils.load_config(options, 'regions')
        self._alerts_config = utils.load_config(options, 'alerts')
        self._strategies_config = utils.load_config(options, 'strategies')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        # backtesting options
        self._backtesting = options.get('backtesting', False)
        self._from_date = options.get('from')  # UTC tz
        self._to_date = options.get('to')  # UTC tz
        self._timestep = options.get('timestep', 60.0)
        self._timeframe = options.get('timeframe', 0.0)

        self._timestamp = 0  # in backtesting current processed timestamp

        self._strategy = None

        # cannot be more recent than now
        from common.utils import UTC
        today = datetime.now().astimezone(UTC())

        if self._from_date and self._from_date > today:
            self._from_date = today

        if self._to_date and self._to_date > today:
            self._to_date = today

        self._backtest = False
        self._start_ts = self._from_date.timestamp() if self._from_date else 0
        self._end_ts = self._to_date.timestamp() if self._to_date else 0
        self._timestep_thread = None
        self._time_factor = 0.0

        if self._backtesting:
            # can use the time factor in backtesting only
            self._time_factor = options.get('time-factor', 0.0)

        # paper mode options
        self._paper_mode = options.get('paper-mode', False)

        self._next_key = 1

        # worker pool of jobs for running data analysis
        self._worker_pool = WorkerPool()

    @property
    def watcher_service(self):
        return self._watcher_service

    @property
    def trader_service(self):
        return self._trader_service

    @property
    def monitor_service(self):
        return self._monitor_service

    @property
    def worker_pool(self):
        return self._worker_pool

    @property
    def tradeops(self):
        return self._tradeops

    @property
    def regions(self):
        return self._regions

    @property
    def alerts(self):
        return self._alerts

    def set_activity(self, status):
        """
        Enable/disable execution of orders on strategy
        """
        if self._strategy:
            self._strategy.set_activity(status)

    def start(self, options):
        # indicators
        for k, indicator in self._indicators_config.items():
            if indicator.get("status") is not None and indicator.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = indicator.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load indicator %s" % k) 

                self._indicators[k] = Clazz

        # tradeops
        for k, tradeop in self._tradeops_config.items():
            if tradeop.get("status") is not None and tradeop.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = tradeop.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load tradeop %s" % k) 

                self._tradeops[k] = Clazz

        # regions
        for k, region in self._regions_config.items():
            if region.get("status") is not None and region.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = region.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load region %s" % k) 

                self._regions[k] = Clazz

        # alerts
        for k, alert in self._alerts_config.items():
            if alert.get("status") is not None and alert.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = alert.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load alert %s" % k) 

                self._alerts[k] = Clazz

        # strategies
        for k, strategy in self._strategies_config.items():
            if k == "default":
                continue

            if strategy.get("status") is not None and strategy.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = strategy.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load strategy %s" % k)

                self._strategies[k] = Clazz

        if self._watcher_only:
            return

        # and finally strategy
        strategy_profile = self._profile_config.get('strategy')
        if strategy_profile['name'] == "default":
            return

        if self._strategy is not None:
            Terminal.inst().error("Strategy %s already started" % self._strategy.name)
            return

        # overrided strategy parameters
        parameters = strategy_profile.get('parameters', {})

        if not strategy_profile or not strategy_profile.get('name'):
            error_logger.error("Invalid strategy configuration for strategy %s. Ignored !" % strategy_profile['name'])

        Clazz = self._strategies.get(strategy_profile['name'])
        if not Clazz:
            error_logger.error("Unknown strategy name %s. Ignored !" % strategy_profile['name'])
            return

        strategy_inst = Clazz(self, self.watcher_service, self.trader_service, self._profile_config, parameters)
        strategy_inst.set_identifier(strategy_profile.get('id', strategy_profile['name']))

        if strategy_inst.start():
            self._strategy = strategy_inst
        else:
            error_logger.error("Unable to start strategy name %s. Ignored !" % strategy_profile['name'])
            return

        # start the worker pool
        self._worker_pool.start()

    def terminate(self):
        if self._timestep_thread and self._timestep_thread.is_alive():
            # abort backtesting
            self._timestep_thread.abort = True
            self._timestep_thread.join()
            self._timestep_thread = None

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
                    strategy.terminate()
                    strategy.save()
                except Exception as e:
                    error_logger.error(repr(e))
                    error_logger.error(traceback.format_exc())

        # terminate the worker pool
        self._worker_pool.stop()

        self._strategy = None

        self._strategies = {}
        self._indicators = {}
        self._regions = {}
        self._alerts = {}

    def sync(self):
        # start backtesting
        if self._backtesting and not self._backtest:
            go_ready = True

            self._backtest_progress = 0

            if self._strategy:
                strategy = self._strategy
                if not strategy.running or not strategy.ready():
                    go_ready = False

            if go_ready:
                # start the time thread once the strategy instance get its data and are ready
                class TimeStepThread(threading.Thread):

                    def __init__(self, service, s, e, ts, base_tf=0.0, tf=0.0):
                        super().__init__(name="backtest")

                        self.service = service
                        self.abort = False
                        self.s = s
                        self.e = e
                        self.c = s
                        self.ts = ts
                        self.ppc = 0
                        self.tf = tf
                        self.begin_ts = 0
                        self.end_ts = 0
                        self.base_tf = base_tf

                    def run(self):
                        prev = self.c
                        min_limit = 0.0001
                        limit = min_limit  # starts with min limit
                        last_saturation = 0
                        last_sleep = time.time()

                        Terminal.inst().info("Backtesting started...", view='status')

                        strategy = self.service.strategy()
                        trader = strategy.trader() if strategy else None
                        wait = False                      

                        self.begin_ts = time.time()   # bench

                        if strategy and trader:
                            while self.c < self.e + self.ts:
                                # now sync the trader base time
                                trader.set_timestamp(self.c)

                                strategy.backtest_update(self.c, self.e)

                                if self.tf > 0:
                                    # wait factor of time step, so 1 mean realtime simulation, 0 mean as fast as possible
                                    time.sleep((1/self.tf)*self.ts)

                                self.c += self.ts  # add one time step
                                self.service._timestamp = self.c

                                # one more step then we can update trader (limits orders, P/L update...)
                                trader.update()

                                if trader._ping:
                                    trader.pong(time.time(), trader._ping[0], trader._ping[1], trader._ping[2])
                                    trader._ping = None

                                time.sleep(0.000001)  # yield

                                if self.abort:
                                    break

                        self.end_ts = time.time()

                self._timestep_thread = TimeStepThread(self, self._start_ts, self._end_ts, self._timestep, self._timeframe, self._time_factor)
                self._timestep_thread.setDaemon(True)
                self._timestep_thread.start()

                # backtesting started, avoid re-enter
                self._backtest = True               

        if self._backtesting and self._backtest and self._backtest_progress < 100.0:
            progress = 0

            strategy = self._strategy
            if strategy and strategy.running:
                progress += strategy.progress()

            total = self._end_ts - self._start_ts
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
                    int((self._timestep_thread.c - self._timestep_thread.s) / self._timestep_thread.ts),
                    format_delta(self._timestep_thread.end_ts - self._timestep_thread.begin_ts)))

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_STRATEGY, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def command(self, command_type, data):
        results = None

        strategy = self._strategy

        if strategy:
            results = strategy.command(command_type, data)

        return results

    def __gen_command_key(self):
        with self._mutex:
            next_key = self._next_key
            self._next_key += 1

            return next_key

        return -1

    def receiver(self, signal):
        pass

    def indicator(self, name):
        """Return a specific indicator model by its name"""
        return self._indicators.get(name)

    def strategy(self):
        """Return the instancied strategy"""
        return self._strategy

    def strategy_name(self):
        """Returns the name of the loaded strategy"""
        return self._strategy.name if self._strategy else None

    def strategy_identifier(self):
        """Returns the identifier of the loaded strategy"""
        return self._strategy.identifier if self._strategy else None

    @property
    def timestamp(self):
        """Current live or backtesting timestamp"""
        return self._timestamp if self._backtesting else time.time()

    @property
    def backtesting(self):
        """True if backtesting"""
        return self._backtesting

    @property
    def from_date(self):
        """Backtestnig starting datetime"""
        return self._from_date

    @property
    def to_date(self):
        """Backtesting ending datetime"""
        return self._to_date

    @property
    def timeframe(self):
        """Backtesting base timeframe"""
        return self._timeframe

    @property
    def report_path(self):
        """Base path where to store strategy reports"""
        return self._report_path

    def strategy_config(self):
        """Get the strategy configurations as dict"""
        return self._strategies_config

    def indicator_config(self, name):
        """Get the configurations for an indicator as dict"""
        return self._indicators_config.get(name, {})

    def tradeop_config(self, name):
        """Get the configurations for a tradeop as dict"""
        return self._tradeops_config.get(name, {})

    def ping(self, timeout):
        if self._mutex.acquire(timeout=timeout):
            strategy = self._strategy
            if strategy:
                strategy.ping(timeout)

            self._worker_pool.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service, timeout):
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
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (self.name, timeout))
