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

from terminal.terminal import Terminal
from strategy.strategy import Strategy
from strategy.strategyexception import StrategyServiceException

from config import utils

import logging
logger = logging.getLogger('siis.strategy.service')
error_logger = logging.getLogger('siis.strategy.service')


class StrategyService(Service):

    def __init__(self, watcher_service, trader_service, monitor_service, options):
        super().__init__("strategy", options)

        self._strategies = {}
        self._indicators = {}
        self._appliances = {}
        self._tradeops = {}
        self._regions = {}

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
        self._strategies_config = utils.load_config(options, 'strategies')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        # backtesting options
        self._backtesting = options.get('backtesting', False)
        self._from_date = options.get('from')  # UTC tz
        self._to_date = options.get('to')  # UTC tz
        self._timestep = options.get('timestep', 60.0)

        self._timestamp = 0  # in backtesting current processed timestamp

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

    def set_activity(self, status):
        """
        Enable/disable execution of orders for all appliances.
        """
        for k, appliance in self._appliances.items():
            appliance.set_activity(status)

    def start(self, options):
        # indicators
        for k, indicators in self._indicators_config.items():
            if indicators.get("status") is not None and indicators.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = indicators.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load indicator %s" % k) 

                self._indicators[k] = Clazz

        # tradeops
        for k, tradeops in self._tradeops_config.items():
            if tradeops.get("status") is not None and tradeops.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = tradeops.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load tradeop %s" % k) 

                self._tradeops[k] = Clazz

        # regions
        for k, regions in self._regions_config.items():
            if regions.get("status") is not None and regions.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = regions.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise StrategyServiceException("Cannot load region %s" % k) 

                self._regions[k] = Clazz

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

        # no appliance in watcher only
        if self._watcher_only:
            return

        # and finally appliances
        for k in self._profile_config.get('appliances', []):
            appl = utils.load_config(options, "appliances/%s" % k)

            if k == "default":
                continue

            if self._appliances.get(k) is not None:
                error_logger.error("Strategy appliance %s already started. Ignored !" % k)
                continue

            if appl.get("status") is not None and appl.get("status") == "enabled":
                # retrieve the classname and instanciate it
                strategy = appl.get('strategy')

                # overrided strategy parameters
                parameters = strategy.get('parameters', {})

                if not strategy or not strategy.get('name'):
                    error_logger.error("Invalid strategy configuration for appliance %s. Ignored !" % k)

                Clazz = self._strategies.get(strategy['name'])
                if not Clazz:
                    error_logger.error("Unknown strategy name %s for appliance %s. Ignored !" % (strategy['name'], k))
                    continue

                appl_inst = Clazz(self, self.watcher_service, self.trader_service, appl, parameters)
                appl_inst.set_identifier(k)

                if appl_inst.start():
                    self._appliances[k] = appl_inst
                else:
                    error_logger.error("Unable to start strategy name %s for appliance %s. Ignored !" % (strategy['name'], k))
                    continue

        # start the worker pool
        if self._backtesting:
            # only if there is more than 1 appliance
            if len(self._appliances) > 1:
                self._worker_pool.start()
        else:
            self._worker_pool.start()

    def terminate(self):
        if self._timestep_thread and self._timestep_thread.is_alive():
            # abort backtesting
            self._timestep_thread.abort = True
            self._timestep_thread.join()
            self._timestep_thread = None

        for k, appl in self._appliances.items():
            if not appl:
                continue

            # stop all workers
            if appl.running:
                appl.stop()

        for k, appl in self._appliances.items():
            if not appl:
                continue

            # join them
            if appl.thread.is_alive():
                appl.thread.join()

            # and save state to database
            if not self.backtesting and (appl.trader() and not appl.trader().paper_mode):
                try:
                    appl.terminate()
                    appl.save()
                except Exception as e:
                    error_logger.error(repr(e))
                    error_logger.error(traceback.format_exc())

        # terminate the worker pool
        self._worker_pool.stop()

        self._appliances = {}
        self._strategies = {}
        self._indicators = {}

    def sync(self):
        # start backtesting
        if self._backtesting and not self._backtest:
            go_ready = True

            self._mutex.acquire()
            self._backtest_progress = 0

            for k, appl, in self._appliances.items():
                self._mutex.release()
                if not appl.running or not appl.ready():
                    go_ready = False
                    self._mutex.acquire()
                    break
                else:
                    self._mutex.acquire()

            self._mutex.release()

            if go_ready:
                # start the time thread once all appliance get theirs data and are ready
                class TimeStepThread(threading.Thread):

                    def __init__(self, service, s, e, ts, tf=0.0):
                        super().__init__(name="backtest")

                        self.service = service
                        self.abort = False
                        self.s = s
                        self.e = e
                        self.c = s
                        self.ts = ts
                        self.ppc = 0
                        self.tf = tf

                    def run(self):
                        prev = self.c
                        min_limit = 0.0001
                        limit = min_limit  # starts with min limit
                        last_saturation = 0
                        last_sleep = time.time()

                        Terminal.inst().info("Backtesting started...", view='status')

                        appliances = self.service._appliances.values()
                        traders = []
                        wait = False

                        appl = None

                        # get the list of used traders, to sync them after each pass
                        for appl in appliances:
                            if appl.trader() and appl.trader() not in traders:
                                traders.append(appl.trader())

                        if len(appliances) == 1:
                            # a single appliance, don't need to parellelize, and to sync, python sync suxx a lot, avoid the overload in most of the
                            # backtesting usage
                            while self.c < self.e + self.ts:
                                # now sync the trader base time
                                for trader in traders:
                                    trader.set_timestamp(self.c)

                                appl.backtest_update(self.c, self.e)

                                if self.tf > 0:
                                    # wait factor of time step, so 1 mean realtime simulation, 0 mean as fast as possible
                                    time.sleep((1/self.tf)*self.ts)

                                self.c += self.ts  # add one time step
                                self.service._timestamp = self.c

                                # one more step then we can update traders (limits orders, P/L update...)
                                for trader in traders:
                                    trader.update()

                                    if trader._ping:
                                        trader.pong(time.time(), trader._ping[0], trader._ping[1], trader._ping[2])
                                        trader._ping = None

                                time.sleep(0.000001)  # yield

                                if self.abort:
                                    break
                        else:
                            # multiple appliances, parallelise them
                            while self.c < self.e + self.ts:
                                if not wait:
                                    # now sync the trader base time
                                    for trader in traders:
                                        # @todo it could be better if we add two step, one update the market and then the strategy computation
                                        # to avoid to update multiple time the same market and potentially with different ut... but not really an issue
                                        trader.set_timestamp(self.c)

                                    # query async update per appliance
                                    for appl in appliances:
                                        appl.query_backtest_update(self.c, self.e)

                                # @todo could use a semaphore or condition counter
                                wait = False
                                for appl in appliances:
                                    # appl.backtest_update(self.c, self.e)
                                    # wait all appliance did theirs jobs
                                    if appl._last_done_ts < self.c:
                                        wait = True
                                        break

                                if not wait:
                                    if self.tf > 0:
                                        # wait factor of time step, so 1 mean realtime simulation, 0 mean as fast as possible
                                        time.sleep((1/self.tf)*self.ts)

                                    self.c += self.ts  # add one time step
                                    self.service._timestamp = self.c

                                    # one more step then we can update traders (limits orders, P/L update...)
                                    for trader in traders:
                                        trader.update()

                                        if trader._ping:
                                            trader.pong(time.time(), trader._ping[0], trader._ping[1], trader._ping[2])
                                            trader._ping = None

                                time.sleep(0)  # yield

                                if self.abort:
                                    break

                self._timestep_thread = TimeStepThread(self, self._start_ts, self._end_ts, self._timestep, self._time_factor)
                self._timestep_thread.setDaemon(True)
                self._timestep_thread.start()

                # backtesting started, avoid re-enter
                self._backtest = True               

        if self._backtesting and self._backtest and self._backtest_progress < 100.0:
            progress = 0

            self._mutex.acquire()
            for k, appl, in self._appliances.items():
                if appl.running:
                    progress += appl.progress()

            if self._appliances:
                progress /= float(len(self._appliances))

            self._mutex.release()

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

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_STRATEGY, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def command(self, command_type, data):
        if command_type == Strategy.COMMAND_INFO:
            # any or specific commands
            appliance_identifier = data.get('appliance')

            if appliance_identifier:
                # for a specific appliance
                appliance = self._appliances.get(appliance_identifier)
                if appliance:
                    appliance.command(command_type, data)
            else:
                # or any
                for k, appliance in self._appliances.items():
                    appliance.command(command_type, data)
        else:
            # specific commands
            appliance_identifier = data.get('appliance')
            appliance = None

            if appliance_identifier:
                appliance = self._appliances.get(appliance_identifier)

            if appliance:
                appliance.command(command_type, data)

    def __gen_command_key(self):
        with self._mutex:
            next_key = self._next_key
            self._next_key += 1

            return next_key

        return -1

    def receiver(self, signal):
        pass

    def indicator(self, name):
        return self._indicators.get(name)

    def strategy(self, name):
        return self._strategies.get(name)

    def appliance(self, name):
        return self._appliances.get(name)

    def get_appliances(self):
        return list(self._appliances.values())

    def appliances_identifiers(self):
        return [app.identifier for k, app in self._appliances.items()]

    @property
    def timestamp(self):
        return self._timestamp if self._backtesting else time.time()

    @property
    def backtesting(self):
        return self._backtesting

    @property
    def from_date(self):
        return self._from_date

    @property
    def to_date(self):
        return self._to_date

    @property
    def report_path(self):
        return self._report_path

    def profile_has_appliance(self, name):
        """
        Check if an appliance is allowed for the current loaded profile.
        """
        appliances = self._profile_config.get('appliances', [])

        for app_name in appliances:
            if app_name.startswith('!'):
                if app_name[1:] == name:
                    # ignored
                    return False

            if app_name == '*':
                # any except ignored
                return True

            if app_name == name:
                return True

        return False

    def strategy_config(self, name):
        """
        Get the configurations for a strategy as dict.
        """
        return self._strategies_config.get(name, {})

    def indicator_config(self, name):
        """
        Get the configurations for an indicator as dict.
        """
        return self._indicators_config.get(name, {})

    def tradeop_config(self, name):
        """
        Get the configurations for a tradeop as dict.
        """
        return self._tradeops_config.get(name, {})

    def ping(self, timeout):
        if self._mutex.acquire(timeout=timeout):
            for k, appl, in self._appliances.items():
                appl.ping(timeout)

            self._worker_pool.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service, timeout):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping appliances
            for k, appl, in self._appliances.items():
                appl.watchdog(watchdog_service, timeout)

            # and workers
            self._worker_pool.watchdog(watchdog_service, timeout)

            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (self.name, timeout))
