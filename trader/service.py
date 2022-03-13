# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# service worker

from config import utils
from common.service import Service
from common.signal import Signal

from terminal.terminal import Terminal
from trader.connector.papertrader.trader import PaperTrader

import logging
logger = logging.getLogger('siis.trader.service')
error_logger = logging.getLogger('siis.trader.service')


class TraderService(Service):
    """
    Trader service is responsible of build, initialize, load configuration, start/stop the trader.
    """

    def __init__(self, watcher_service, monitor_service, options: dict):
        super().__init__("trader", options)

        self._trader = None

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

        # trader config
        self._trader_config = self._init_trader_config(options)

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
    def report_path(self) -> str:
        return self._report_path

    def start(self, options: dict):
        # no trader in watcher only
        if self._watcher_only:
            return

        trader_config = self._trader_config

        if not trader_config:
            Terminal.inst().error("Missing trader config")
            return

        if self._trader is not None:
            Terminal.inst().error("Trader %s already started" % self._trader.name)
            return

        profile_trader_config = self.profile()
        if not profile_trader_config:
            # ignore trader missing from the profile
            return

        if trader_config.get("status") is not None and trader_config.get("status") == "load":
            # retrieve the class-name and instantiate it
            parts = trader_config.get('classpath').split('.')

            module = __import__('.'.join(parts[:-1]), None, locals(), [parts[-1], ], 0)
            Clazz = getattr(module, parts[-1])

            # backtesting always create paper traders
            if self.backtesting or self._paper_mode:
                inst_trader = PaperTrader(self, profile_trader_config['name'])
                paper_mode = trader_config.get('paper-mode', None)

                if paper_mode:
                    inst_trader.account.set_currency(paper_mode.get('currency', 'USD'),
                                                     paper_mode.get('currency-symbol', '$'))
                    inst_trader.account.set_alt_currency(paper_mode.get('alt-currency', 'USD'),
                                                         paper_mode.get('alt-currency-symbol', '$'))

                    # initial fund or asset
                    if paper_mode.get('type', 'margin') == 'margin':
                        inst_trader.account.account_type = inst_trader.account.TYPE_MARGIN
                        inst_trader.account.initial(paper_mode.get('initial', 1000.0), inst_trader.account.currency,
                                                    inst_trader.account.currency_display)

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
                                inst_trader.create_asset(asset['base'], asset['initial'], paper_mode.get('price', 0.0),
                                                         asset['quote'], asset.get('precision', 8))

                if self.backtesting:
                    # no auto-update -> no thread : avoid time deviation
                    self._trader = inst_trader

                elif self._paper_mode:
                    # live but in paper-mode -> thread
                    if inst_trader.start(options):
                        self._trader = inst_trader
            else:
                # live with real trader
                inst_trader = Clazz(self)
                preference = trader_config.get('preference', None)

                if preference:
                    # preferred currency if specified, useful for some spots brokers
                    inst_trader.account.set_currency(preference.get('currency', 'USD'),
                                                     preference.get('currency-symbol', '$'))
                    inst_trader.account.set_alt_currency(preference.get('alt-currency', 'USD'),
                                                         preference.get('alt-currency-symbol', '$'))

                if inst_trader.start(options):
                    self._trader = inst_trader

    def terminate(self):
        if self._trader:
            trader = self._trader

            # stop workers
            if trader.running:
                trader.stop()

            # join them
            if trader.thread.is_alive():
                trader.thread.join()

            self._trader = None

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_TRADER, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def command(self, command_type, data):
        results = None

        trader = self._trader
        if trader:
            results = trader.command(command_type, data)

        return results

    def receiver(self, signal):
        pass

    def trader(self):
        return self._trader

    def trader_name(self):
        return self._trader.name if self._trader else None

    def gen_key(self):
        nkey = -1

        with self._mutex:
            nkey = self._next_trader_key
            self._next_trader_key += 1

        return str(nkey)

    @property
    def backtesting(self) -> bool:
        return self._backtesting

    @property
    def paper_mode(self) -> bool:
        return self._paper_mode

    def ping(self, timeout: float):
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping trader
            if self._trader:
                self._trader.ping(timeout)

            self._mutex.release()
        else:
            Terminal.inst().action("Unable to join service %s for %s seconds" % (self.name, timeout), view='content')

    def watchdog(self, watchdog_service, timeout):
        # try to acquire, see for deadlock
        if self._mutex.acquire(timeout=timeout):
            # if no deadlock lock for service ping trader
            if self._trader:
                self._trader.watchdog(watchdog_service, timeout)

            self._mutex.release()
        else:
            watchdog_service.service_timeout(self.name, "Unable to join service %s for %s seconds" % (self.name, timeout))

    #
    # config
    #

    def identity(self, name):
        return self._identities_config.get(name, {}).get(self._identity)

    def trader_config(self):
        """
        Get the trader configuration as dict.
        """
        return self._trader_config

    def _init_trader_config(self, options):
        """
        Get the profile configuration for a specific trader name.
        """
        if not self._profile_config:
            return {}

        profile_trader_config = self._profile_config.get('trader')

        trader_config = {}

        if not profile_trader_config:
            return {}

        user_trader_config = utils.load_config(options, 'traders/' + profile_trader_config.get('name', "default.json"))
        if user_trader_config:
            if 'paper-mode' in profile_trader_config:
                # paper-mode from profile overrides
                user_trader_config['paper-mode'] = profile_trader_config['paper-mode']

            if 'preference' in profile_trader_config:
                # preference from profile overrides
                user_trader_config['preference'] = profile_trader_config['preference']

            # keep override
            trader_config = user_trader_config

        return trader_config

    def profile(self):
        """
        Get the profile configuration for the trader.
        """
        return self._profile_config.get('trader')
