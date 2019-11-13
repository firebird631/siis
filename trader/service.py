# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker

import time
import threading

from datetime import datetime, timedelta
from importlib import import_module

from config import utils
from common.service import Service
from common.signal import Signal

from terminal.terminal import Terminal
from trader.position import Position
from trader.connector.papertrader.trader import PaperTrader
from trader.traderexception import TraderServiceException


class TraderService(Service):
    """
    Trade service is responsible of build, initialize, load configuration, start/stop traders.

    @note It os more safe to limit at 1 trader per running instance.
    @todo Could limit to a single trader.
    """

    def __init__(self, watcher_service, monitor_service, options):
        super().__init__("trader", options)

        self._traders = {}
        
        self._keys_map_to_trader = {}
        self._next_trader_key = 1
        self._next_trader_uid = 1

        self._keys_map_to_order = {}
        self._next_key = 1
        self._next_order_uid = 1

        self._watcher_service = watcher_service
        self._monitor_service = monitor_service

        self._identity = options.get('identity', 'demo')
        self._report_path = options.get('reports-path', './')
        self._watcher_only = options.get('watcher-only', False)

        # user identities
        self._identities_config = utils.identities(options.get('config-path'))
        self._profile = options.get('profile', 'default')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        # traders config
        self._traders_config = self._init_traders_config(options)

        # backtesting options
        self._backtesting = options.get('backtesting', False)
        self._start_timestamp = options['from'].timestamp() if options.get('from') else 0
        self._end_timestamp = options['to'].timestamp() if options.get('to') else 0

        # enable/disable execution of order/position (play/pause)
        self._activity = True

        # paper mode options
        self._paper_mode = options.get('paper-mode', False)

    @property
    def watcher_service(self):
        return self._watcher_service

    @property
    def monitor_service(self):
        return self._monitor_service

    @property
    def report_path(self):
        return self._report_path

    def start(self, options):
        # no traders in watcher only
        if self._watcher_only:
            return

        for k, trader in self._traders_config.items():
            if k == "default":
                continue

            if self._traders.get(k) is not None:
                Terminal.inst().error("Trader %s already started" % k)
                continue

            profile_trader_config = self.profile(k)
            if not profile_trader_config:
                # ignore trader missing from the profile
                continue

            if trader.get("status") is not None and trader.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = trader.get('classpath').split('.')

                module = __import__('.'.join(parts[:-1]), None, locals(), [parts[-1],], 0)
                Clazz = getattr(module, parts[-1])

                # backtesting always create paper traders
                if self.backtesting or self._paper_mode:
                    inst_trader = PaperTrader(self, k)
                    paper_mode = trader.get('paper-mode', None)

                    if paper_mode:
                        inst_trader.account.set_currency(paper_mode.get('currency', 'USD'), paper_mode.get('currency-symbol', '$'))
                        inst_trader.account.set_alt_currency(paper_mode.get('alt-currency', 'USD'), paper_mode.get('alt-currency-symbol', '$'))

                        # initial fund or asset
                        if paper_mode.get('type', 'margin') == 'margin':
                            inst_trader.account.account_type = inst_trader.account.TYPE_MARGIN
                            inst_trader.account.initial(paper_mode.get('initial', 1000.0), inst_trader.account.currency, inst_trader.account.currency_display)

                        elif paper_mode.get('type', 'margin') == 'asset':
                            inst_trader.account.account_type = inst_trader.account.TYPE_ASSET

                            assets = paper_mode.get('assets', [{
                                'base': inst_trader.account.currency,
                                'quote': inst_trader.account.alt_currency,
                                'initial': 1000.0,
                                'precision': 8
                            }])

                            for asset in assets:
                                if asset.get('base') and asset.get('quote') and asset.get('initial'):
                                    inst_trader.create_asset(asset['base'], asset['initial'], paper_mode.get('price', 0.0), asset['quote'], asset.get('precision', 8))

                    if self.backtesting:
                        # no auto-update -> no thread : avoid time deviation
                        self._traders[k] = inst_trader

                    elif self._paper_mode:
                        # live but in paper-mode -> thread
                        if inst_trader.start():
                            self._traders[k] = inst_trader
                else:
                    # live with real trader
                    inst_trader = Clazz(self)

                    if inst_trader.start():
                        self._traders[k] = inst_trader

    def terminate(self):
        for k, trader in self._traders.items():
            # stop workers
            if trader.running:
                trader.stop()

        for k, trader in self._traders.items():
            # join them
            if trader.thread.is_alive():
                trader.thread.join()

        self._traders = {}

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_TRADER, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def command(self, command_type, data):
        for k, trader in self._traders.items():
            trader.command(command_type, data)

    def receiver(self, signal):
        pass

    def trader(self, name):
        return self._traders.get(name)

    def traders_names(self):
        return [trader.name for k, trader in self._traders.items()]

    def get_traders(self):
        return list(self._traders.values())

    def gen_key(self):
        nkey = -1

        with self._mutex:
            nkey = self._next_trader_key
            self._next_trader_key += 1

        return str(nkey)

    @property
    def backtesting(self):
        return self._backtesting

    @property
    def paper_mode(self):
        return self._paper_mode

    def ping(self, timeout):
        if self._mutex.acquire(timeout=timeout):
            for k, trader, in self._traders.items():
                trader.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service, timeout):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping traders
            for k, trader, in self._traders.items():
                trader.watchdog(watchdog_service, timeout)

            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (self.name, timeout))

    #
    # config
    #

    def identity(self, name):
        return self._identities_config.get(name, {}).get(self._identity)

    def trader_config(self, name):
        """
        Get the configurations for a trader as dict.
        """
        return self._traders_config.get(name, {})

    def _init_traders_config(self, options):
        """
        Get the profile configuration for a specific trader name.
        """
        traders_profile = self._profile_config.get('traders', {})

        traders_config = {}

        for k, profile_trader_config in traders_profile.items():
            user_trader_config = utils.load_config(options, 'traders/' + k)
            if user_trader_config:
                if 'paper-mode' in profile_trader_config:
                    # paper-mode from profile overrides
                    user_trader_config['paper-mode'] = profile_trader_config['paper-mode']

                # keep overrided
                traders_config[k] = user_trader_config

        return traders_config

    def profile(self, name):
        """
        Get the profile configuration for a specific trader name.
        """
        profile = self._profile_config.get('traders', {})
        return profile.get(name, {})
