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

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from terminal.terminal import Terminal
from trader.position import Position
from trader.connector.papertrader.trader import PaperTrader


class TraderService(Service):
    """
    Trade service is responsible of build, initialize, load configuration, start/stop traders.

    @note It os more safe to limit at 1 trader per running instance.
    @todo Could limit to a single trader.
    """

    POLICY_COPY_EVERYWHERE = 0       # copy to from any watcher to any trader (as possible symbols)
    POLICY_COPY_SAME_AS_ORIGIN = 1   # copy only from a watcher type to the same trader type

    MAX_COPY_ENTRY_DELAY = 5*60      # filters social trades only lesser than N seconds (5 min)
    MAX_ORDER_COPY_SLIPPAGE = 60     # filters strategy signals only lesser than N seconds (@todo take care must be lasser than Trader.PURGE_COMMANDS_DELAY)

    def __init__(self, watcher_service, monitor_service, options):
        super().__init__("trader", options)

        self._traders = {}
        
        self._keys_map_to_trader = {}
        self._next_trader_key = 1
        self._next_trader_uid = 1

        self._keys_map_to_order = {}
        self._next_key = 1
        self._next_order_uid = 1

        self._policy = TraderService.POLICY_COPY_EVERYWHERE
        self._watcher_service = watcher_service
        self._monitor_service = monitor_service

        self._identity = options.get('identity', 'demo')
        self._report_path = options.get('reports-path', './')
        self._watcher_only = options.get('watcher-only', False)

        # user identities
        self._identities_config = utils.identities(options.get('config-path'))
        self._profile = options.get('profile', 'default')
        self._profile_config = utils.profiles(options.get('config-path')) or {}

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

    def set_activity(self, status):
        """
        Enable/disable execution of orders for all traders.
        """
        for k, trader in self._traders.items():
            trader.set_activity(status)

    def start(self):
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

            trader.log_report()

        self._traders = {}

    def notify(self, signal_type, source_name, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_TRADER, source_name, signal_type, signal_data)

        self._mutex.acquire()
        self._notifier.notify(signal)
        self._mutex.release()

    def command(self, command_type, data):
        for k, trader in self._traders.items():
            trader.command(command_type, data)

    def receiver(self, signal):
        now = time.time()
        command_trigger = {'key': self.gen_key()}

        if signal.signal_type == Signal.SIGNAL_SOCIAL_ENTER:
            # @deprecated @todo its from social trading...
            direction = "long" if signal.data.direction == Position.LONG else "short"

            # here we only assume that because of what 1broker return to us but should be timestamp in the model
            position_timestamp = time.mktime(signal.data.entry_date.timetuple())
            entry_date = signal.data.entry_date + timedelta(hours=2)

            if now - position_timestamp > TraderService.MAX_COPY_ENTRY_DELAY:
                return

            Terminal.inst().high("Trading entry signal on %s :" % (entry_date,))
            Terminal.inst().info("User %s enter %s on %s at %s x%s" % (signal.data.author.name, direction, signal.data.symbol, signal.data.entry_price, signal.data.leverage))
            Terminal.inst().info("Stop loss: %s / Take profit: %s" % (signal.data.stop_loss, signal.data.take_profit))
            Terminal.inst().action("Trigger key %s to copy this signal..." % (key_id))

            for k, trader in self._traders.items():
                if self._policy == TraderService.POLICY_COPY_EVERYWHERE:
                    trader.on_enter_position(signal.data, command_trigger)
                elif trader.name == signal.data.watcher.name:
                    trader.on_enter_position(signal.data, command_trigger)

        elif signal.signal_type == Signal.SIGNAL_SOCIAL_EXIT:
            # @deprecated @todo its from social trading...
            direction = "long" if signal.data.direction == Position.LONG else "short"

            # here we only assume that because of what 1broker return to us but should be timestamp in the model
            position_timestamp = time.mktime(signal.data.exit_date.timetuple())
            exit_date = signal.data.exit_date + timedelta(hours=2)

            if now - position_timestamp > TraderService.MAX_COPY_ENTRY_DELAY:
                return

            Terminal.inst().low("Trading exit signal on %s :" % (exit_date,))
            Terminal.inst().info("User %s exit %s on %s at %s" %  (signal.data.author.name, direction, signal.data.symbol, signal.data.exit_price))

            # @todo profit/loss in account currency (here not good its in unit of...)
            entry_price = float(signal.data.entry_price) if signal.data.entry_price else 0

            margin = entry_price + entry_price * signal.data.profit_loss_rate
            Terminal.inst().info("Profit/Loss %f (%.2f%%)" % (margin, signal.data.profit_loss_rate*100.0))
            Terminal.inst().action("Trigger key %s to copy this signal..." % (key_id))

            for k, trader in self._traders.items():
                if self._policy == TraderService.POLICY_COPY_EVERYWHERE:
                    trader.on_exit_position(signal.data, command_trigger)
                elif trader.name == signal.data.watcher.name:
                    trader.on_exit_position(signal.data, command_trigger)

        elif signal.signal_type == Signal.SIGNAL_SOCIAL_ORDER:
            # @deprecated @todo its from social trading...
            # MAX_ORDER_COPY_SLIPPAGE sec max slippage
            if now - float(signal.data['timestamp']) > TraderService.MAX_ORDER_COPY_SLIPPAGE:
                return          

        #   order_date = datetime.fromtimestamp(float(signal.data['timestamp']))
        #   direction = 'long' if signal.data['direction'] == Position.LONG else 'short' if signal.data['direction'] == Position.SHORT else ''

        #   if signal.data['direction'] == Position.LONG or signal.data['direction'] == Position.SHORT:
        #       Terminal.inst().low("Social trading order signal on %s :" % (order_date,))
        #       Terminal.inst().info("Strategy %s order %s on %s at %s" %  (signal.data['strategy'], direction, signal.data['symbol'], signal.data['price']))
        #       Terminal.inst().action("Trigger key %s to copy this signal..." % (key_id))

        #       for k, trader in self._traders.items():
        #           if self._policy == TraderService.POLICY_COPY_EVERYWHERE:
        #               trader.on_set_order(signal.data, command_trigger)
        #           elif trader.name == signal.data.watcher.name:
        #               trader.on_set_order(signal.data, command_trigger)

    def trader(self, name):
        return self._traders.get(name)

    def traders_names(self):
        return [trader.name for k, trader in self._traders.items()]

    def get_traders(self):
        return list(self._traders.values())

    def gen_key(self):
        self.lock()
        nkey = self._next_trader_key
        self._next_trader_key += 1
        self.unlock()
        return str(nkey)

    @property
    def backtesting(self):
        return self._backtesting

    @property
    def paper_mode(self):
        return self._paper_mode

    def ping(self):
        self._mutex.acquire()
        for k, trader, in self._traders.items():
            trader.ping()
        self._mutex.release()

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
        profile_name = options.get('profile', 'default')

        profile_config = utils.profiles(options.get('config-path')) or {}
        traders_profile = profile_config.get(profile_name, {'traders': {}}).get('traders', {})  # @todo from new profiles conf

        # @todo could rebuild the list of symbols according to what is found in appliances
        traders_config = {}

        for k, profile_trader_config in traders_profile.items():
            user_trader_config = utils.load_config(options, 'traders/' + k)
            if user_trader_config:
                if 'symbols' not in user_trader_config:
                    # at least an empty list of symbols
                    user_trader_config['symbols'] = []

                if 'symbols' in profile_trader_config:
                    # profile overrides any symbols
                    user_trader_config['symbols'] = profile_trader_config['symbols']

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
        profile = self._profile_config.get(self._profile, {'traders': {}}).get('traders', {})
        return profile.get(name, {})
