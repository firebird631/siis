# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Watcher service

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Dict

if TYPE_CHECKING:
    from monitor.service import MonitorService
    from .fetcher import Fetcher

from importlib import import_module

from terminal.terminal import Terminal

from config import utils
from common.service import Service

from common.signal import Signal
from config.utils import merge_parameters

from watcher.watcher import Watcher

import logging
logger = logging.getLogger('siis.service.watcher')


class WatcherService(Service):
    """
    Watcher service.
    """

    _monitor_service: Union[MonitorService, None]
    _watchers: Dict[str, Watcher]

    def __init__(self, monitor_service: Union[MonitorService, None], options: dict):
        super().__init__("watcher", options)

        self._monitor_service = monitor_service

        self._watchers = {}

        self._identity = options.get('identity', 'demo')
        self._backtesting = options.get('backtesting', False)

        # fetchers config
        self._fetchers_config = utils.load_config(options, 'fetchers')

        # user identities
        self._identities_config = utils.identities(options.get('config-path'))
        self._profile = options.get('profile', 'default')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        # watchers config
        self._watchers_config = self._init_watchers_config(options)

        # backtesting options
        self._backtesting = options.get('backtesting', False)
        self._start_timestamp = options['from'].timestamp() if options.get('from') else 0
        self._end_timestamp = options['to'].timestamp() if options.get('to') else 0

        # store OHLCs into the DB during watcher process, default is False
        self._store_ohlc = options.get('store-ohlc', False)

        # process the initial data fetch at each instrument subscription, default is False
        self._initial_fetch = options.get('initial-fetch', False)

        # store trade/tick/quote during watcher process, default is False
        self._store_trade = options.get('store-trade', False)

        # paper mode options to subscribe only to public part of data
        self._paper_mode = options.get('paper-mode', False)

    @property
    def monitor_service(self) -> Union[MonitorService, None]:
        return self._monitor_service

    def create_fetcher(self, options: dict, watcher_name: str) -> Union[Fetcher, None]:
        fetcher = self._fetchers_config.get(watcher_name)
        if not fetcher:
            logger.error("Fetcher %s not found !" % watcher_name)
            return None

        # additional configuration and user specifications
        specific_config = utils.load_config(options, 'fetchers/' + watcher_name)
        fetcher = merge_parameters(fetcher, specific_config)

        # force fetcher config
        self._fetchers_config[watcher_name] = fetcher

        # retrieve the class-name and instantiate it
        parts = fetcher.get('classpath').split('.')

        module = import_module('.'.join(parts[:-1]))
        Clazz = getattr(module, parts[-1])

        return Clazz(self)

    def create_watcher(self, options: dict, watcher_name: str, markets: List[str]) -> Union[Watcher, None]:
        watcher_config = utils.load_config(options, 'watchers/' + watcher_name)
        if not watcher_config:
            logger.error("Watcher %s not found !" % watcher_name)
            return None

        if markets:
            watcher_config['symbols'] = markets

        # force watcher config
        self._watchers_config[watcher_name] = watcher_config

        # retrieve the class-name and instantiate it
        parts = watcher_config.get('classpath').split('.')

        module = import_module('.'.join(parts[:-1]))
        Clazz = getattr(module, parts[-1])

        return Clazz(self)

    def start(self, options: dict):
        from watcher.connector.dummywatcher.watcher import DummyWatcher

        for k, watcher in self._watchers_config.items():
            ignore = False

            if k == "default":
                continue

            profile_watcher_config = self.profile(k)
            if (not profile_watcher_config or not profile_watcher_config.get('status', None) or
                    profile_watcher_config['status'] != 'enabled'):
                # ignore watcher missing or disabled from the profile
                continue

            if self._watchers.get(k) is not None:
                logger.error("Watcher %s already started" % k)
                continue

            if watcher.get("status") is not None and watcher.get("status") == "load":
                # retrieve the class-name and instantiate it
                parts = watcher.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                # dummy watcher in backtesting
                if self.backtesting:
                    inst_watcher = DummyWatcher(self, k)
                else:
                    inst_watcher = Clazz(self)

                if inst_watcher.start(options):
                    self._watchers[k] = inst_watcher

    def terminate(self):
        for k, watcher in self._watchers.items():
            # stop workers
            if watcher.running:
                watcher.stop()

        for k, watcher in self._watchers.items():
            # join them
            if watcher.thread.is_alive():
                watcher.thread.join()

        self._watchers = {}

    def notify(self, signal_type: int, source_name: str, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_WATCHER, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def find_author(self, watcher_name: str, author_id: str):
        watcher = self._watchers.get(watcher_name)
        if watcher:
            author = watcher.find_author(author_id)
            if author:
                return author

        return None

    def watcher(self, name: str) -> Union[Watcher, None]:
        return self._watchers.get(name)

    def watchers_ids(self) -> List[str]:
        return list(self._watchers.keys())

    @property
    def backtesting(self) -> bool:
        return self._backtesting

    @property
    def paper_mode(self) -> bool:
        return self._paper_mode

    def command(self, command_type: int, data: dict) -> Union[dict, None]:
        results = None

        if command_type == Watcher.COMMAND_INFO:
            # any or specific commands
            watcher_name = data.get('watcher')

            if watcher_name:
                # for a specific watcher
                watcher = self._watchers.get(watcher_name)
                if watcher:
                    results = watcher.command(command_type, data)
            else:
                # or any, with an array of results
                results = []

                for k, watcher in self._watchers.items():
                    results.append(watcher.command(command_type, data))
        else:
            # specific commands
            watcher_name = data.get('watcher')
            watcher = None

            if watcher_name:
                watcher = self._watchers.get(watcher_name)

            if watcher:
                results = watcher.command(command_type, data)

        return results

    def ping(self, timeout: float):
        if self._mutex.acquire(timeout=timeout):
            for k, watcher, in self._watchers.items():
                watcher.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service, timeout: float):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping watchers
            for k, watcher, in self._watchers.items():
                watcher.watchdog(watchdog_service, timeout)

            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (
                self.name, timeout))

    def reconnect(self, name: Optional[str] = None):
        # force disconnection for it will auto-reconnect
        if name and name in self._watchers:
            watcher = self._watchers[name]

            watcher.disconnect()
        else:
            for k, watcher in self._watchers.items():
                watcher.disconnect()

    #
    # preferences
    #

    @property
    def store_ohlc(self) -> bool:
        return self._store_ohlc

    @property
    def initial_fetch(self) -> bool:
        return self._initial_fetch

    @property
    def store_trade(self) -> bool:
        return self._store_trade

    #
    # config
    #

    def identity(self, name: str) -> dict:
        return self._identities_config.get(name, {}).get(self._identity)

    def fetcher_config(self, name: str) -> dict:
        """
        Get the configurations for a fetcher as dict.
        """
        return self._fetchers_config.get(name, {})

    def watcher_config(self, name: str) -> dict:
        """
        Get the configurations for a watcher as dict.
        """
        return self._watchers_config.get(name, {})

    def _init_watchers_config(self, options: dict) -> dict:
        """
        Get the profile configuration for a specific watcher name.
        """
        if not self._profile_config:
            return {}

        watchers_profile = self._profile_config.get('watchers', {})

        # @todo could rebuild the list of symbols according to what is found in strategy
        watchers_config = {}

        if not watchers_profile:
            return {}

        for k, profile_watcher_config in watchers_profile.items():
            user_watcher_config = utils.load_config(options, 'watchers/' + k)
            if user_watcher_config:
                if 'symbols' not in user_watcher_config:
                    # at least an empty list of symbols
                    user_watcher_config['symbols'] = []

                if 'symbols' in profile_watcher_config:
                    # profile overrides any symbols
                    user_watcher_config['symbols'] = profile_watcher_config['symbols']

                # keep override
                watchers_config[k] = user_watcher_config

        return watchers_config

    def profile(self, name: str) -> dict:
        """
        Get the profile configuration for a specific watcher name.
        """
        profile = self._profile_config.get('watchers', {})
        return profile.get(name, {})
