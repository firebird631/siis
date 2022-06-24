# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy base model and implementation

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union, List, Dict, Type, Tuple, Callable

if TYPE_CHECKING:
    from datetime import datetime

    from watcher.service import WatcherService
    from trader.service import TraderService
    from trader.trader import Trader

    from .strategytrader import StrategyTrader
    from .service import StrategyService
    from .indicator.indicator import Indicator
    from .strategydatafeeder import StrategyDataFeeder

import threading
import time
import collections

from .alert.alert import Alert
from terminal.terminal import Terminal

from common.runnable import Runnable
from common.utils import timeframe_to_str, timeframe_from_str
from config.utils import merge_parameters

from common.signal import Signal
from instrument.instrument import Instrument

from watcher.watcher import Watcher

from database.database import Database

from .process import alphaprocess

from .command.strategycmdexitalltrade import cmd_strategy_exit_all_trade
from .command.strategycmdmodifyall import cmd_strategy_trader_modify_all
from .command.strategycmdcancelallpendingtrade import cmd_strategy_cancel_all_pending_trade
from .command.strategycmdreinvestgain import cmd_strategy_reinvest_gain

from .command.strategycmdstrategytraderinfo import cmd_strategy_trader_info
from .command.strategycmdstrategytradermodify import cmd_strategy_trader_modify
from .command.strategycmdstrategytraderstream import cmd_strategy_trader_stream
from .command.strategycmdstrategytraderrestart import cmd_strategy_trader_restart
from .command.strategycmdstrategytraderrecheck import cmd_strategy_trader_recheck, \
    cmd_strategy_trader_recheck_all
from .command.strategycmdstrategytraderexport import cmd_strategy_trader_export, \
    cmd_strategy_trader_export_all
from .command.strategycmdstrategytraderimport import cmd_strategy_trader_import_all

from .command.strategycmdtradeassign import cmd_trade_assign
from .command.strategycmdtradeclean import cmd_trade_clean
from .command.strategycmdtradeentry import cmd_trade_entry
from .command.strategycmdtradeexit import cmd_trade_exit
from .command.strategycmdtradeinfo import cmd_trade_info
from .command.strategycmdtrademodify import cmd_trade_modify
from .command.strategycmdtradecheck import cmd_trade_check

from .command.strategycmdtraderinfo import cmd_trader_info

from monitor.streamable import Streamable, StreamMemberInt

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')
traceback_logger = logging.getLogger('siis.traceback.strategy')


class Strategy(Runnable):
    """
    Strategy base model and implementation.

    @todo Having a commands registry (trade cmd, trader cmd, strategy cmd)
    @todo Add possibility to insert/delete a strategy-trader and instrument during runtime only in live mode.

    @note In backtesting the method backtest_update don't mutex the strategy_traders list because
        in that case the dict never changes.
    """

    MAX_SIGNALS = 2000   # max size of the signals messages queue before ignore some market data (tick, ohlc)
    MAX_SIGNALS_DELAY = 5.0     # alert only when max signal is reach for a period of 5 seconds

    COMMAND_INFO = 1
    COMMAND_TRADE_EXIT_ALL = 2  # close any trade for any market or only for a specific market-id
    COMMAND_TRADE_CANCEL_ALL_PENDING = 3  # cancel any trade with empty realized quantity for any markets or specific
    COMMAND_QUANTITY_GLOBAL_SHARE = 4     # global share quantity

    COMMAND_TRADE_ENTRY = 10    # manually create a new trade
    COMMAND_TRADE_MODIFY = 11   # modify an existing trade
    COMMAND_TRADE_EXIT = 12     # exit (or eventually cancel if not again filled) an existing trade
    COMMAND_TRADE_INFO = 13     # get and display manual trade info (such as listing operations)
    COMMAND_TRADE_ASSIGN = 14   # manually assign a quantity to a new trade
    COMMAND_TRADE_CLEAN = 15    # remove an existing trade without filling remaining quantity neither exiting
    COMMAND_TRADE_CHECK = 16    # recheck a trade status

    COMMAND_TRADER_MODIFY = 20
    COMMAND_TRADER_INFO = 21
    COMMAND_TRADER_STREAM = 22
    COMMAND_TRADER_MODIFY_ALL = 23
    COMMAND_TRADER_RESTART = 24
    COMMAND_TRADER_RECHECK = 25
    COMMAND_TRADER_RECHECK_ALL = 26
    COMMAND_TRADER_EXPORT = 27
    COMMAND_TRADER_EXPORT_ALL = 28
    COMMAND_TRADER_IMPORT_ALL = 29

    _name: str
    _strategy_service: StrategyService
    _watcher_service: WatcherService
    _trader_service: TraderService
    _identifier: Union[str, None]

    _parameters: Dict[str, Union[str, int, float, Tuple, Dict]]

    _setup_backtest: Union[Callable[[Strategy, datetime, datetime, float], None], None]
    _setup_live: Union[Callable[[Strategy], None], None]

    _update_strategy: Union[Callable[[Strategy, StrategyTrader], None], None]
    _async_update_strategy: Union[Callable[[Strategy, StrategyTrader], None], None]

    _preset: bool
    _prefetched: bool

    _watchers_conf: Union[Dict, None]
    _trader_conf: Union[Dict, None]
    _trader: Union[Trader, None]
    _signals: collections.deque

    _instruments: Dict[str, Instrument]
    _feeders: Dict[str, StrategyDataFeeder]
    _strategy_traders: Dict[str, StrategyTrader]

    _last_done_ts: float
    _timestamp: float
    _next_backtest_update: Union[Tuple[float, float], None]
    _cpu_load: float
    _overload_timestamp: float
    _streamable: Union[Streamable, None]
    _heartbeat: float
    _condition: threading.Condition

    def __init__(self, name: str,
                 strategy_service: StrategyService,
                 watcher_service: WatcherService,
                 trader_service: TraderService,
                 strategy_trader_clazz: Type[StrategyTrader],
                 options: dict,
                 default_parameters: Optional[dict] = None,
                 user_parameters: Optional[dict] = None,
                 processor=alphaprocess):

        super().__init__("st-%s" % name)

        self._name = name
        self._strategy_service = strategy_service
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._identifier = None

        self._strategy_trader_clazz = strategy_trader_clazz
        self._parameters = Strategy.parse_parameters(merge_parameters(default_parameters, user_parameters))

        #
        # composite processing inner methods
        #

        self._setup_backtest = None
        self._setup_live = None
        
        self._update_strategy = None
        self._async_update_strategy = None

        # default use alpha processor (support bootstrap but no preprocessing)
        processor.setup_process(self)

        #
        # states and parameters
        #

        self._preset = False       # True once instrument are setup in both modes
        self._prefetched = False   # True once strategies are ready in backtesting mode

        self._watchers_conf = {}   # name of the followed watchers
        self._trader_conf = None   # name of the followed trader

        self._trader = None        # trader proxy

        self._signals = collections.deque()  # filtered received signals

        self._instruments = {}       # mapped instruments
        self._feeders = {}           # feeders mapped by market id
        self._strategy_traders = {}  # per market id strategy data analyser

        # used during backtesting
        self._last_done_ts = 0
        self._timestamp = 0

        self._next_backtest_update = None

        self._cpu_load = 0.0   # global CPU for all the instruments managed by a strategy
        self._overload_timestamp = 0.0

        self._streamable = None
        self._heartbeat = 0

        self._condition = threading.Condition()

        if options.get('trader'):
            trader_conf = options['trader']
            if trader_conf.get('name'):
                self._trader_conf = trader_conf

        for k, watcher_conf in options.get('watchers', {}).items():
            self._watchers_conf[k] = watcher_conf

            # retrieve the watcher instance
            watcher = self._watcher_service.watcher(k)
            if watcher is None:
                logger.error("Watcher %s not found during strategy __init__" % k)

    @property
    def name(self) -> str:
        return self._name

    @property
    def watcher_service(self) -> WatcherService:
        return self._watcher_service
    
    @property
    def trader_service(self) -> TraderService:
        return self._trader_service

    @property
    def service(self) -> StrategyService:
        return self._strategy_service

    @property
    def identifier(self) -> str:
        """Unique strategy identifier"""
        return self._identifier

    def set_identifier(self, identifier: str):
        """Unique strategy identifier"""
        self._identifier = identifier

    @property
    def parameters(self) -> dict:
        """Configuration default merge with users"""
        return self._parameters

    def specific_parameters(self, market_id: str) -> dict:
        """Strategy trader parameters overloaded by per market-id specific if exists"""
        if market_id in self._parameters['markets']:
            return merge_parameters(self._parameters, self._parameters['markets'][market_id])
        else:
            return self._parameters

    @property
    def strategy_traders(self) -> Dict[str, StrategyTrader]:
        return self._strategy_traders

    def strategy_trader(self, market_id: str) -> Union[StrategyTrader, None]:
        """Retrieve a strategy trader according to its unique market-id."""
        return self._strategy_traders.get(market_id)

    #
    # monitoring notification
    #

    def notify_signal(self, timestamp: float, signal, strategy_trader):
        """
        Notify a strategy signal (entry/exit) to the user. It must be called by the strategy-trader.
        """
        if signal:
            signal_data = signal.dumps_notify(timestamp, strategy_trader)

            # entry or exit signal
            if signal.signal > 0:
                self.service.notify(Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY, self._name, signal_data)
            elif signal.signal < 0:
                self.service.notify(Signal.SIGNAL_STRATEGY_SIGNAL_EXIT, self._name, signal_data)

    def notify_trade_entry(self, timestamp: float, trade, strategy_trader):
        """
        Notify a strategy trade entry to the user. It must be called by the strategy-trader.
        """
        if trade:
            signal_data = trade.dumps_notify_entry(timestamp, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_ENTRY, self._name, signal_data)

    def notify_trade_exit(self, timestamp: float, trade, strategy_trader):
        """
        Notify a strategy trade exit to the user. It must be called by the strategy-trader.
        """
        if trade:
            signal_data = trade.dumps_notify_exit(timestamp, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_EXIT, self._name, signal_data)

    def notify_trade_update(self, timestamp, trade, strategy_trader):
        """
        Notify a strategy trade update to the user. It must be called by the strategy-trader.
        """
        if trade:
            signal_data = trade.dumps_notify_update(timestamp, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_UPDATE, self._name, signal_data)

    def notify_trade_error(self, timestamp: float, trade_id: int, strategy_trader):
        """
        Notify a strategy trade update to cause an unmanageable error to the user.
        It must be called by the strategy-trader.
        """
        if trade_id:
            signal_data = {
                'trade-id': trade_id,
                'market-id': strategy_trader.instrument.market_id,
                'symbol': strategy_trader.instrument.symbol,
                'timestamp': timestamp,
            }
            self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_ERROR, self._name, signal_data)

    def notify_alert(self, timestamp: float, alert: Alert, result: dict, strategy_trader):
        """
        Notify a strategy alert to the user. It must be called by the strategy-trader.
        """
        if alert:
            signal_data = alert.dumps_notify(timestamp, result, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_ALERT, self._name, signal_data)

    def subscribe_stream(self, market_id: str, timeframe: float) -> bool:
        """
        Override to create a specific streamer.
        """
        strategy_trader = self._strategy_traders.get(market_id)

        if not strategy_trader:
            return False

        return strategy_trader.subscribe_stream(timeframe)

    def unsubscribe_stream(self, market_id: str, timeframe: float) -> bool:
        """
        Override to delete a specific streamer.
        """
        strategy_trader = self._strategy_traders.get(market_id)

        if not strategy_trader:
            return False

        return strategy_trader.unsubscribe_stream(timeframe)

    #
    # processing
    #

    @property
    def timestamp(self) -> float:
        """
        Current time or last time if backtesting
        """
        if self.service.backtesting:
            return self._timestamp
        else:
            return time.time()

    @property
    def cpu_load(self) -> float:
        return self._cpu_load

    def check_watchers(self) -> bool:
        """
        Returns true if all watchers are retrieved and connected.
        """
        for watcher_name, watcher_conf in self._watchers_conf.items():
            # retrieve the watcher instance
            watcher = self._watcher_service.watcher(watcher_name)
            if watcher is None or not watcher.connected or not watcher.ready:
                return False

        return True

    def pre_run(self):
        Terminal.inst().message("Running strategy %s - %s..." % (self._name, self._identifier), view='content')

        self.setup_streaming()

        # watcher can be already ready in some cases, try it now
        if self.check_watchers():
            if not self._preset:
                self.preset()

    def post_run(self):
        Terminal.inst().message("Joining strategy %s - %s..." % (self._name, self._identifier), view='content')

        self.close_streaming()

    def post_update(self):
        # load of the strategy
        self._cpu_load = len(self._signals) / float(Strategy.MAX_SIGNALS)

        # strategy must consume its signal else there is first a warning, and then some market data could be ignored
        if len(self._signals) > Strategy.MAX_SIGNALS:
            now = time.time()

            # but only after a delay
            if self._overload_timestamp == 0.0:
                self._overload_timestamp = now

            elif now - self._overload_timestamp > Strategy.MAX_SIGNALS_DELAY:
                Terminal.inst().warning("Strategy %s has more than %s waiting signals for the last %i seconds !" % (
                    self.name, Strategy.MAX_SIGNALS, Strategy.MAX_SIGNALS_DELAY), view='debug')

                self._overload_timestamp = now

    def setup_streaming(self):
        self._streamable = Streamable(self.service.monitor_service, Streamable.STREAM_STRATEGY, "status", self.name)
        self._streamable.add_member(StreamMemberInt('ping'))

    def close_streaming(self):
        self._streamable = None

    def ping(self, timeout: float):
        if self._condition.acquire(timeout=timeout):
            self._ping = (0, None, True)
            self._condition.notify()
            self._condition.release()
        else:
            Terminal.inst().action("Unable to join strategy %s - %s for %s seconds" % (
                self._name, self._identifier, timeout,), view='content')

    def watchdog(self, watchdog_service, timeout):
        if self._condition.acquire(timeout=timeout):
            self._ping = (watchdog_service.gen_pid(self._thread.name if self._thread else "unknown"),
                          watchdog_service, False)
            self._condition.notify()
            self._condition.release()
        else:
            watchdog_service.service_timeout(self._thread.name if self._thread else "unknown",
                                             "Unable to join appliance %s - %s for %s seconds" % (
                                                 self._name, self._identifier, timeout))

    def pong(self, timestamp: float, pid: int, watchdog_service, msg: str):
        if msg:
            # display strategy activity
            Terminal.inst().action("Strategy worker %s - %s is alive %s" % (
                self._name, self._identifier, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    #
    # strategy-trader processing
    #

    def create_trader(self, instrument: Instrument):
        return self._strategy_trader_clazz(self, instrument, self.specific_parameters(instrument.market_id))

    def preset(self):
        """
        Called once all watchers are connected.
        """
        if self._preset:
            # don't process if already preset
            return

        # get the related trader
        self._trader = self.trader_service.trader()

        for watcher_name, watcher_conf in self._watchers_conf.items():
            # retrieve the watcher instance
            watcher = self.watcher_service.watcher(watcher_name)
            if watcher is None:
                logger.error("Watcher %s not found during strategy initialize" % watcher_name)
                continue

            # help with watcher matching method, symbols match to the broker market-id or
            # string mapping with placeholder
            strategy_symbols = watcher.matching_symbols_set(watcher_conf.get('symbols'),
                                                            watcher.available_instruments())

            # create an instrument per mapped symbol where to locally store received data
            for symbol in strategy_symbols:
                # mapped name into the instrument as market_id
                mapped_instrument = self.mapped_instrument(symbol)

                if mapped_instrument:
                    # can contain a {} placeholder for the symbol
                    mapped_symbol = mapped_instrument['market-id'].format(symbol)
                else:
                    mapped_symbol = None

                # add missing instruments
                if mapped_symbol:
                    if self._instruments.get(mapped_symbol) is None:
                        # create managed instruments not already got from watcher (backtesting...)
                        instrument = Instrument(
                                market_id=mapped_symbol,
                                symbol=self.symbol_for_market_id(mapped_symbol) or symbol,
                                alias=mapped_instrument.get('alias'))

                        instrument.trade_quantity = mapped_instrument.get('size', 0.0)

                        trade_qty_mode = mapped_instrument.get('size-mode', None)
                        if trade_qty_mode:
                            if trade_qty_mode == "quote-to-base":
                                instrument.trade_quantity_mode = Instrument.TRADE_QUANTITY_QUOTE_TO_BASE

                        instrument.leverage = mapped_instrument.get('leverage', 1.0)

                        market = self._trader.market(symbol)
                        if market:
                            # synchronize initial market data into the instrument
                            instrument.symbol = market.symbol

                            instrument.trade = market.trade
                            instrument.orders = market.orders
                            instrument.hedging = market.hedging
                            instrument.tradeable = market.is_open
                            instrument.expiry = market.expiry

                            instrument.value_per_pip = market.value_per_pip
                            instrument.one_pip_means = market.one_pip_means

                            instrument.set_base(market.base)
                            instrument.set_quote(market.quote)

                            instrument.set_price_limits(market.min_price, market.max_price, market.step_price)
                            instrument.set_notional_limits(market.min_notional, market.max_notional,
                                                           market.step_notional)
                            instrument.set_size_limits(market.min_size, market.max_size, market.step_size)

                            instrument.set_fees(market.maker_fee, market.taker_fee)
                            instrument.set_commissions(market.maker_commission, market.taker_commission)

                        self._instruments[mapped_symbol] = instrument

                        # and create the strategy-trader analyser per instrument
                        strategy_trader = self.create_trader(instrument)
                        if strategy_trader:
                            with self._mutex:
                                self._strategy_traders[instrument.market_id] = strategy_trader

                            # initial market info only in live mode else market data are not complete at this time
                            if not self.service.backtesting:
                                strategy_trader.on_market_info()
                    else:
                        instrument = self._instruments.get(mapped_symbol)

                    if watcher.has_prices_and_volumes:
                        instrument.add_watcher(Watcher.WATCHER_PRICE_AND_VOLUME, watcher)

                    if watcher.has_buy_sell_signals:
                        instrument.add_watcher(Watcher.WATCHER_BUY_SELL_SIGNAL, watcher)

        # now can setup backtest or live mode global states and loads previous trades
        if self.service.backtesting:
            self._setup_backtest(self, self.service.from_date, self.service.to_date, self.service.timeframe)
        else:
            self._setup_live(self)

        # one done once after startup and first connection
        self._preset = True

    def start(self, options: dict) -> bool:
        if super().start(options):
            # reset data
            self.reset()

            # listen to watchers and strategy signals
            self.watcher_service.add_listener(self)
            self.service.add_listener(self)

            return True
        else:
            return False

    def stop(self):
        if self._running:
            self._running = False

            with self._condition:
                self._signals.append(None)  # empty signal to wake-up and break loop
                self._condition.notify()

        # reset data
        self.reset()

    def terminate(self):
        """
        For each strategy-trader terminate to be done only in live mode.
        """
        with self._mutex:
            if not self.service.backtesting and not self.trader().paper_mode:
                for k, strategy_trader in self._strategy_traders.items():
                    strategy_trader.terminate()

    def save(self):
        """
        For each strategy-trader save to be done only in live mode.
        """
        with self._mutex:
            if not self.service.backtesting and not self.trader().paper_mode:
                for k, strategy_trader in self._strategy_traders.items():
                    strategy_trader.save()

    def indicator(self, name: str) -> Union[Type[Indicator], None]:
        """
        Get an indicator by its name
        """
        return self._strategy_service.indicator(name)

    def set_activity(self, status: bool, market_id: Optional[str] = None):
        """
        Enable/disable execution of orders (create_order, stop_loss) for any of the strategy traders or 
        a specific instrument if market_id is defined.

        @param status: bool New activity status.
        @param market_id: str Market id or symbol or None for any.
        """
        if market_id:
            with self._mutex:
                instrument = self.find_instrument(market_id)
                market_id = instrument.market_id if instrument else None

                strategy_trader = self._strategy_traders.get(market_id)
                if strategy_trader:
                    strategy_trader.set_activity(status)
        else:
            with self._mutex:
                for k, strategy_trader in self._strategy_traders.items():
                    strategy_trader.set_activity(status)

    def trader(self):
        """
        Return the instance of the trader. In paper mode and backtesting might returns a paper trader.
        """
        return self._trader

    def mapped_instrument(self, symbol: str) -> Union[dict, None]:
        """
        Return the string name of the market-id relating the symbol.
        """
        if self._trader_conf is None or not self._trader_conf.get('instruments'):
            return None

        if self._trader_conf['instruments'].get(symbol):
            return self._trader_conf['instruments'][symbol]

        # or already a mapped name
        for k, mapped_symbol in self._trader_conf['instruments'].items():
            if mapped_symbol.get('market-id', '') == symbol:
                return mapped_symbol

            # wildcard mapping of the instrument name
            if k.startswith('*'):
                if symbol.endswith(k[1:]):
                    return mapped_symbol

        return None

    #
    # symbols/instruments accessors
    #

    def symbols_ids(self) -> List[str]:
        """
        Returns the complete list containing market-ids, theirs alias and theirs related symbol name.
        """
        with self._mutex:
            names = []

            for k, instrument in self._instruments.items():
                names.append(instrument.market_id)

                if (instrument.symbol and instrument.symbol != instrument.market_id and
                        instrument.symbol != instrument.alias):
                    names.append(instrument.symbol)

                if (instrument.alias and instrument.alias != instrument.market_id and
                        instrument.alias != instrument.symbol):
                    names.append(instrument.alias)

            names.sort()

        return names

    def instruments_ids(self) -> List[str]:
        """
        Returns the complete list containing market-ids (instruments only).
        """
        with self._mutex:
            names = []

            for k, instrument in self._instruments.items():
                names.append(instrument.market_id)

            names.sort()

        return names

    def instrument(self, symbol_or_market_id: str) -> Union[Instrument, None]:
        """
        Return the mapped instrument data from the watcher/strategy adapted to the trader
        """
        if not symbol_or_market_id:
            return None

        instrument = self._instruments.get(symbol_or_market_id)
        if instrument:
            return instrument

        # or look with mapping of the name
        mapped_symbol = self.mapped_instrument(symbol_or_market_id)
        if mapped_symbol:
            instrument = self._instruments.get(mapped_symbol['market-id'])
            if instrument:
                return instrument

        return None

    def symbol_for_market_id(self, market_id: str) -> Union[str, None]:
        if self._trader_conf is None or not self._trader_conf.get('instruments'):
            return None

        # or already a mapped name
        for k, instrument in self._trader_conf['instruments'].items():
            if instrument.get('market-id', '') == market_id:
                return k

        return None

    def find_instrument(self, symbol_or_market_id: str) -> Union[Instrument, None]:
        """
        Return instrument from its market-id or name or symbol or alias.
        """
        if not symbol_or_market_id:
            return None

        instrument = self._instruments.get(symbol_or_market_id)
        if instrument:
            return instrument

        # or look with mapping of the name
        for k, instr in self._instruments.items():
            if (symbol_or_market_id == instr.market_id or symbol_or_market_id == instr.symbol or
                    symbol_or_market_id == instr.alias):
                return instr

        return None

    #
    # strategy-trader profiles/context
    #

    def contexts_ids(self, market_id: str) -> List[str]:
        contexts_ids = []

        if not market_id:
            return []

        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return []

        with strategy_trader.mutex:
            try:
                contexts_ids = strategy_trader.contexts_ids()              
            except Exception as e:
                error_logger.error(repr(e))

        return contexts_ids

    def dumps_context(self, market_id: str, context_id: str):
        context = None

        if not market_id or not context_id:
            return None

        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return None

        with strategy_trader.mutex:
            try:
                context = strategy_trader.dumps_context(context_id)
            except Exception as e:
                error_logger.error(repr(e))

        return context

    #
    # feeder for backtesting
    #

    def feeder(self, market_id: str):
        return self._feeders.get(market_id)

    def add_feeder(self, feeder):
        if feeder is None:
            return

        with self._mutex:
            if feeder.market_id in self._feeders:
                raise ValueError("Already defined feeder %s for strategy %s !" % (self.name, feeder.market_id))

            self._feeders[feeder.market_id] = feeder

    #
    # processing
    #

    @property
    def base_timeframe(self) -> float:
        """
        Return the base timeframe at which the strategy process, and accept ticks or candles data from signals.
        Default returns at tick level. Override this method to change this value.
        """
        return Instrument.TF_TICK

    def send_initialize_strategy_trader(self, market_id: str):
        """
        Force to wake up a strategy-trader. This could be useful when the market is sleeping and there is
        a user operation to perform.
        """
        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return

        signal = Signal(Signal.SOURCE_STRATEGY, self.identifier, Signal.SIGNAL_STRATEGY_INITIALIZE, market_id)

        # and signal for an update
        if self._condition.acquire(timeout=1.0):
            self._condition.notify()
            self._add_signal(signal)
            self._condition.release()
        else:
            self._add_signal(signal)

    def send_update_strategy_trader(self, market_id: str):
        """
        Force to wake-up a strategy-trader. This could be useful when the market is sleeping and there is
        a user operation to perform.
        """
        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return

        signal = Signal(Signal.SOURCE_STRATEGY, self.identifier, Signal.SIGNAL_STRATEGY_UPDATE, market_id)

        # and signal for an update
        if self._condition.acquire(timeout=1.0):
            self._condition.notify()
            self._add_signal(signal)
            self._condition.release()
        else:
            self._add_signal(signal)

    def update(self) -> bool:
        """
        Does not override this method. Internal update mechanism.
        """
        if not self._running:
            return False

        if self._condition.acquire(timeout=1.0):
            # running cancel wait, ping too, normal case is a signal to process
            while not len(self._signals) and not self._ping:
                self._condition.wait(1.0)

                # ping on stream
                self.stream_ping()

            self._condition.release()

        # with self._condition:
        #     # running cancel wait, ping too, normal case is a signal to process
        #     while (not len(self._signals) or not self._ping):
        #         self._condition.wait()

        do_update = set()

        while self._signals:
            signal = self._signals.popleft()
            if signal is None:
                continue

            if signal.source == Signal.SOURCE_STRATEGY:
                if signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                    # incoming market info if backtesting
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    market = signal.data[1]

                    if market and strategy_trader:
                        # in backtesting mode set the market object to the paper trader directly because
                        # there is no watcher
                        if self.service.backtesting:
                            trader = self.trader_service.trader()
                            if trader:
                                trader.set_market(market)

                            with strategy_trader.mutex:
                                instrument = strategy_trader.instrument

                                # put interesting market data into the instrument
                                instrument.trade = market.trade
                                instrument.orders = market.orders
                                instrument.hedging = market.hedging
                                instrument.tradeable = market.is_open
                                instrument.expiry = market.expiry

                                instrument.set_base(market.base)
                                instrument.set_quote(market.quote)

                                instrument.value_per_pip = market.value_per_pip
                                instrument.one_pip_means = market.one_pip_means

                                instrument.set_price_limits(market.min_price, market.max_price, market.step_price)
                                instrument.set_notional_limits(market.min_notional, market.max_notional,
                                                               market.step_notional)
                                instrument.set_size_limits(market.min_size, market.max_size, market.step_size)

                                instrument.set_fees(market.maker_fee, market.taker_fee)
                                instrument.set_commissions(market.maker_commission, market.taker_commission)

                            strategy_trader.on_market_info()

                    if self.service.backtesting:
                        # retrieve the feeder by the relating instrument market_id or symbol
                        feeder = self._feeders.get(signal.data[0])
                        if feeder:
                            # set instrument once market data are fetched
                            feeder.set_instrument(strategy_trader.instrument)

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_LIST:
                    # for each market load the corresponding trades to the strategy trader
                    logger.debug("Received signal data for strategy list of trades data. Processing data...")

                    for data in signal.data:
                        strategy_trader = self._strategy_traders.get(data[0])
                        if strategy_trader:
                            with strategy_trader.mutex:
                                strategy_trader.loads_trade(data[1], data[2], data[3], data[4], check=True)
                                time.sleep(2)

                    # clear once done (@todo or by trade...)
                    trader = self.trader()
                    Database.inst().clear_user_trades(trader.name, trader.account.name, self.identifier)

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADER_LIST:
                    # for each market load the corresponding settings and regions to the strategy trader
                    logger.debug("Received signal data for strategy traders data. Processing data...")

                    for data in signal.data:
                        strategy_trader = self._strategy_traders.get(data[0])
                        if strategy_trader:
                            with strategy_trader.mutex:
                                # activity, trader-data, regions-data, alerts-data
                                strategy_trader.set_activity(data[1])
                                strategy_trader.loads(data[2], data[3], data[4])

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_INITIALIZE:
                    # interest in initialize
                    strategy_trader = self._strategy_traders.get(signal.data)
                    if strategy_trader:
                        do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_UPDATE:
                    # interest in force update (after modifying something on trader of trades)
                    strategy_trader = self._strategy_traders.get(signal.data)
                    if strategy_trader:
                        do_update.add(strategy_trader)

            elif signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                    # interest in tick data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # add the new tick to the instrument in live mode
                        with strategy_trader.mutex:
                            if strategy_trader.instrument.ready():
                                strategy_trader.instrument.add_tick(signal.data[1])

                                do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                    # interest in candle data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # add the new candle to the instrument in live mode
                        with strategy_trader.mutex:
                            if strategy_trader.instrument.ready():
                                strategy_trader.instrument.add_candle(signal.data[1])

                                do_update.add(strategy_trader)

                if signal.signal_type == Signal.SIGNAL_TICK_DATA_BULK:
                    # incoming bulk of history ticks
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        with strategy_trader.mutex:
                            initial = strategy_trader.instrument.is_want_timeframe(0)

                        # insert the bulk of ticks into the instrument
                        if signal.data[1]:
                            with strategy_trader.mutex:
                                # can accumulate before ready status
                                strategy_trader.instrument.add_ticks(signal.data[1])

                                if initial:
                                    # ticks acquired
                                    strategy_trader.instrument.ack_timeframe(0)

                                do_update.add(strategy_trader)
                        else:
                            with strategy_trader.mutex:
                                if initial:
                                    # empty ticks acquired
                                    strategy_trader.instrument.ack_timeframe(0)

                                do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA_BULK:
                    # incoming bulk of history candles
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        with strategy_trader.mutex:
                            initial = strategy_trader.instrument.is_want_timeframe(signal.data[1])

                        # insert the bulk of candles into the instrument
                        if signal.data[2]:
                            # in live mode directly add candles to instrument
                            with strategy_trader.mutex:
                                strategy_trader.instrument.add_candles(signal.data[2])

                            # initials candles loaded
                            if initial:
                                instrument = strategy_trader.instrument

                                logger.debug("Retrieved %s OHLCs for %s in %s" % (
                                    len(signal.data[2]), instrument.market_id, timeframe_to_str(signal.data[1])))

                                # append the current OHLC from the watcher on live mode
                                with strategy_trader.mutex:
                                    if not self.service.backtesting:
                                        instrument.add_candle(instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
                                                              .current_ohlc(instrument.market_id, signal.data[1]))

                                    # timeframe acquired
                                    instrument.ack_timeframe(signal.data[1])

                                strategy_trader.on_received_initial_candles(signal.data[1])

                            do_update.add(strategy_trader)
                        else:
                            # initials candles loaded but empty results
                            if initial:
                                instrument = strategy_trader.instrument

                                logger.debug("Retrieved no OHLCs for %s in %s" % (
                                    instrument.market_id, timeframe_to_str(signal.data[1])))

                                with strategy_trader.mutex:
                                    # timeframe acquired
                                    instrument.ack_timeframe(signal.data[1])

                                # necessary call for strategy complete initialization
                                strategy_trader.on_received_initial_candles(signal.data[1])

                            do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                    # update market data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # update instrument data
                        with strategy_trader.mutex:
                            instrument = strategy_trader.instrument
                            instrument.tradeable = signal.data[1]

                            if signal.data[1]:
                                # only if valid field
                                if signal.data[2]:
                                    instrument.last_update_time = signal.data[2]

                                if signal.data[3]:
                                    instrument.market_bid = signal.data[3]
                                if signal.data[4]:
                                    instrument.market_ask = signal.data[4]

                                # if signal.data[5]:
                                #     instrument.base_exchange_rate = signal.data[5]

                                if signal.data[7]:
                                    instrument.value_per_pip = signal.data[7]

                                if signal.data[8]:
                                    instrument.vol24h_base = signal.data[8]
                                if signal.data[9]:
                                    instrument.vol24h_quote = signal.data[9]

                elif signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                    # update market info data
                    market = signal.data[1]
                    if market:
                        strategy_trader = self._strategy_traders.get(signal.data[0])
                        if strategy_trader:
                            with strategy_trader.mutex:
                                instrument = strategy_trader.instrument

                                # put interesting market data into the instrument @todo using message data
                                instrument.trade = market.trade
                                instrument.orders = market.orders
                                instrument.hedging = market.hedging
                                instrument.tradeable = market.is_open
                                instrument.expiry = market.expiry

                                instrument.set_base(market.base)
                                instrument.set_quote(market.quote)

                                instrument.set_price_limits(market.min_price, market.max_price, market.step_price)
                                instrument.set_notional_limits(market.min_notional, market.max_notional,
                                                               market.step_notional)
                                instrument.set_size_limits(market.min_size, market.max_size, market.step_size)

                                instrument.set_fees(market.maker_fee, market.taker_fee)
                                instrument.set_commissions(market.maker_commission, market.taker_commission)

                            strategy_trader.on_market_info()

                elif signal.signal_type == Signal.SIGNAL_LIQUIDATION_DATA:
                    # interest in liquidation data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        strategy_trader.on_received_liquidation(signal.data)

                        do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_WATCHER_CONNECTED:
                    # initiate the strategy prefetch initial data, only once all watchers are ready
                    market = signal.data[1]
                    if market:
                        if self.check_watchers():
                            strategy_trader = self._strategy_traders.get(signal.data[0])
                            if strategy_trader:
                                with strategy_trader.mutex:
                                    # force to reinitialize
                                    # @todo could be done only after a certain delay
                                    # strategy_trader._initialized = 1

                                    # force to recheck the trades
                                    strategy_trader._checked = 1

                                do_update.add(strategy_trader)
                    else:
                        # any markets are affected, only for initial after first connection
                        if self.check_watchers():
                            if not self._preset:
                                self.preset()

                            # need to reinitialize and recheck the traces
                            for k, strategy_trader in self._strategy_traders.items():
                                with strategy_trader.mutex:
                                    # force to reinitialize
                                    # @todo could be done only after a certain delay
                                    # strategy_trader._initialized = 1

                                    # force to recheck the trades
                                    strategy_trader._checked = 1
 
                                do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_WATCHER_DISCONNECTED:
                    # do we want to clean-up and wait connection signal to reinitialize ?
                    pass

                elif Signal.SIGNAL_POSITION_OPENED <= signal.signal_type <= Signal.SIGNAL_POSITION_AMENDED:
                    # position signal
                    self.position_signal(signal.signal_type, signal.data)

                elif Signal.SIGNAL_ORDER_OPENED <= signal.signal_type <= Signal.SIGNAL_ORDER_TRADED:
                    # trade signal
                    self.order_signal(signal.signal_type, signal.data)

        # if self.service.backtesting:
        #     # process one more backtest step
        #     with self._mutex:
        #         next_bt_upd = self._next_backtest_update
        #         self._next_backtest_update = None
        #
        #     if next_bt_upd:
        #         self.backtest_update(next_bt_upd[0], next_bt_upd[1])
        if not self.service.backtesting:  # else:
            # normal processing
            if do_update:
                if len(self._strategy_traders) >= 1:
                    # always async update process
                    for strategy_trader in do_update:
                        # parallelize jobs on workers
                        self.service.worker_pool.add_job(None, (self._async_update_strategy, (self, strategy_trader,)))
                else:
                    # no parallelization for single instrument
                    for strategy_trader in do_update:
                        self._update_strategy(self, strategy_trader)

        return True

    def stream_ping(self):
        try:
            now = time.time()
            if now - self._heartbeat >= 1.0:
                if self._streamable:
                    self._streamable.member('ping').update(int(now*1000))
                    self._streamable.publish()

                self._heartbeat = now
        except Exception as e:
            error_logger.error(repr(e))

    #
    # backtesting
    #

    def query_backtest_update(self, timestamp: float, total_ts: float):
        with self._mutex:
            self._next_backtest_update = (timestamp, total_ts)

    def backtest_update_instrument(self, trader: Trader, strategy_trader: StrategyTrader, timestamp: float):
        # retrieve the feeder by market_id
        instrument = strategy_trader.instrument

        feeder = self._feeders.get(instrument.market_id)

        # feed of candles prior equal the timestamp and update if new candles on configured timeframe
        updated = feeder.feed(timestamp)

        if trader and updated:
            # update the market instrument data before processing,
            # but we do not have the exact base exchange rate and contract size, it is emulated in the paper trader

            # the feeder update the instrument price data, so use them directly
            trader.on_update_market(instrument.market_id, True, instrument.last_update_time,
                                    instrument.market_bid, instrument.market_ask, None)

        # update strategy as necessary
        if updated:
            self._update_strategy(self, strategy_trader)

    def backtest_update(self, timestamp: float, total_ts: float):

        """
        Process the backtesting update, for any instrument feeds candles to instrument and does the necessary updates.
        Override only if necessary. This default implementation should suffice.

        The strategy_trader list here is not mutex, because it backtesting context we never could add or remove one.
        """
        trader = self.trader()

        if not self.backtest_ready():
            return

        # processing timestamp
        self._timestamp = timestamp

        if len(self._strategy_traders) > 3:
            count_down = self.service.worker_pool.new_count_down(len(self._strategy_traders))

            for market_id, strategy_trader in self._strategy_traders.items():
                # parallelize jobs on workers
                self.service.worker_pool.add_job(count_down, (
                    self.backtest_update_instrument, (trader, strategy_trader, timestamp)))

            # sync before continue
            count_down.wait()
        else:
            # no parallelization below 4 instruments
            for market_id, strategy_trader in self._strategy_traders.items():
                self.backtest_update_instrument(trader, strategy_trader, timestamp)

        # last done timestamp, to manage progression
        self._last_done_ts = timestamp

    def reset(self):
        # backtesting only, the last processed timestamp
        self._last_done_ts = 0
        self._timestamp = 0

    def backtest_ready(self) -> bool:
        """
        Must return True once the strategy is ready te begin for the backtesting.
        Override only if necessary. This default implementation should suffice.
        """
        if self._preset and not self._prefetched:
            with self._mutex:
                prefetched = True

                # need all ready, feeders
                for market_id, feeder in self._feeders.items():
                    if not feeder.ready():
                        prefetched = False
                        break

                # and instruments wanted data
                for k, strategy_trader in self._strategy_traders.items():
                    if not strategy_trader.instrument.ready():
                        prefetched = False
                        break

                self._prefetched = prefetched

        return self._running and self._preset and self._prefetched

    #
    # setup and processing state and condition
    #

    def finished(self) -> bool:
        """
        In backtesting return True once all data are consumed.
        """
        # if not self.is_alive():
        if not self.running:
            return False

        with self._mutex:
            finished = True

            for market_id, feeder in self._feeders.items():
                if not feeder.finished():
                    finished = False
                    break

        return finished

    def progress(self) -> float:
        """
        During backtesting return the last processed timestamp.
        """
        # if not self.is_alive():
        if not self.running:
            return 0

        return self._last_done_ts

    #
    # signals/slots
    #

    def _add_signal(self, signal: Signal):
        if self._condition.acquire(timeout=1.0):
            self._signals.append(signal)
            self._condition.notify()
            self._condition.release()
        else:
            self._signals.append(signal)

        # with self._condition:
        #     self._signals.append(signal)
        #     self._condition.notify()

    def receiver(self, signal: Signal):
        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # not interested in this instrument/symbol
                    return

                # any others are a signal of interest
                self._add_signal(signal)

            elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_LIST:
                # signal of interest
                self._add_signal(signal)

            elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADER_LIST:
                # signal of interest
                self._add_signal(signal)

            # elif signal.signal_type == Signal.SIGNAL_STRATEGY_INITIALIZE:
            #     # signal of interest (directly managed buy the caller method)
            #     self._add_signal(signal)

            # elif signal.signal_type == Signal.SIGNAL_STRATEGY_UPDATE:
            #     # signal of interest (directly managed buy the caller method)
            #     self._add_signal(signal)

        elif signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name not in self._watchers_conf:
                # not interested in this watcher
                return

            # filter by instrument for tick data
            if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                if Instrument.TF_TICK != self.base_timeframe:
                    # must be equal to the base timeframe only
                    return

                if signal.data[0] not in self._strategy_traders:
                    # non interested in this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                if signal.data[1].timeframe != self.base_timeframe:
                    # must be of equal to the base timeframe only
                    return

                if signal.data[0] not in self._strategy_traders:
                    # non interested in this instrument/symbol
                    return

            # filter by instrument for buy/sell signal
            elif signal.signal_type == Signal.SIGNAL_BUY_SELL_ORDER:
                if signal.data[0] not in self._strategy_traders:
                    # non interested in this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # non interested in this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # non interested in this instrument/symbol
                    return

            # if len(self._signals) > Strategy.MAX_SIGNALS:
            #     # from the watcher (in live) so then ignore some of those message, the others ones
            #     # are too important to be ignored
            #     if signal.signal_type in (Signal.SIGNAL_TICK_DATA, Signal.SIGNAL_MARKET_DATA):
            #         return

            # signal of interest
            self._add_signal(signal)

        elif signal.source == Signal.SOURCE_TRADER:
            if self._trader_conf and signal.source_name == self._trader_conf['name']:
                # signal of interest
                self._add_signal(signal)

    def position_signal(self, signal_type: int, data: dict):
        """
        Receive of the position signals. Dispatch if mapped instrument.
        """
        strategy_trader = self._strategy_traders.get(data[0])
        if strategy_trader:
            strategy_trader.position_signal(signal_type, data)

    def order_signal(self, signal_type: int, data: dict):
        """
        Receive of the order signals. Dispatch if mapped instrument.
        """
        strategy_trader = self._strategy_traders.get(data[0])
        if strategy_trader:
            strategy_trader.order_signal(signal_type, data)

    #
    # helpers
    #

    def dumps_trades_update(self) -> List[dict]:
        """
        Dumps trade update notify of any trades of any strategy traders.
        """
        trades = []

        with self._mutex:
            for k, strategy_trader in self._strategy_traders.items():
                try:
                    trades += strategy_trader.dumps_trades_update()
                except Exception as e:
                    error_logger.error(repr(e))

        return trades

    def dumps_trades_history(self) -> List[dict]:
        """
        Dumps trade records of any historical trades of any strategy traders. Not sorted.
        """
        trades = []

        with self._mutex:
            for k, strategy_trader in self._strategy_traders.items():
                try:
                    trades += strategy_trader.dumps_trades_history()
                except Exception as e:
                    error_logger.error(repr(e))

        return trades

    def dumps_active_alerts(self) -> List[dict]:
        """
        Dumps actives alerts of any strategy traders. Not sorted.
        """
        alerts = []

        with self._mutex:
            for k, strategy_trader in self._strategy_traders.items():
                try:
                    alerts += strategy_trader.dumps_active_alerts()
                except Exception as e:
                    error_logger.error(repr(e))

        return alerts

    def dumps_regions(self) -> List[dict]:
        """
        Dumps regions of any strategy traders. Not sorted.
        """
        regions = []

        with self._mutex:
            for k, strategy_trader in self._strategy_traders.items():
                try:
                    regions += strategy_trader.dumps_regions()
                except Exception as e:
                    error_logger.error(repr(e))

        return regions

    #
    # commands
    #

    def command(self, command_type: int, data: dict) -> Union[dict, None]:
        """
        Apply a command to the strategy and return a results dict or an array of dict or None.
        """
        if command_type == Strategy.COMMAND_INFO:
            return cmd_trader_info(self, data)

        elif command_type == Strategy.COMMAND_TRADE_EXIT_ALL:
            return cmd_strategy_exit_all_trade(self, data)
        elif command_type == Strategy.COMMAND_TRADE_CANCEL_ALL_PENDING:
            return cmd_strategy_cancel_all_pending_trade(self, data)
        elif command_type == Strategy.COMMAND_QUANTITY_GLOBAL_SHARE:
            return cmd_strategy_reinvest_gain(self, data)

        elif command_type == Strategy.COMMAND_TRADE_ENTRY:
            return self.trade_command("entry", data, cmd_trade_entry)
        elif command_type == Strategy.COMMAND_TRADE_EXIT:
            return self.trade_command("exit", data, cmd_trade_exit)
        elif command_type == Strategy.COMMAND_TRADE_CLEAN:
            return self.trade_command("clean", data, cmd_trade_clean)
        elif command_type == Strategy.COMMAND_TRADE_MODIFY:
            return self.trade_command("modify", data, cmd_trade_modify)
        elif command_type == Strategy.COMMAND_TRADE_INFO:
            return self.trade_command("info", data, cmd_trade_info)
        elif command_type == Strategy.COMMAND_TRADE_ASSIGN:
            return self.trade_command("assign", data, cmd_trade_assign)
        elif command_type == Strategy.COMMAND_TRADE_CHECK:
            return self.trade_command("check", data, cmd_trade_check)

        elif command_type == Strategy.COMMAND_TRADER_MODIFY:
            return self.strategy_trader_command("modify", data, cmd_strategy_trader_modify)
        elif command_type == Strategy.COMMAND_TRADER_INFO:
            return self.strategy_trader_command("info", data, cmd_strategy_trader_info)
        elif command_type == Strategy.COMMAND_TRADER_STREAM:
            return self.strategy_trader_command("stream", data, cmd_strategy_trader_stream)
        elif command_type == Strategy.COMMAND_TRADER_RESTART:
            return self.strategy_trader_command("restart", data, cmd_strategy_trader_restart)
        elif command_type == Strategy.COMMAND_TRADER_RECHECK:
            return self.strategy_trader_command("recheck", data, cmd_strategy_trader_recheck)
        elif command_type == Strategy.COMMAND_TRADER_EXPORT:
            return self.strategy_trader_command("export", data, cmd_strategy_trader_export)

        elif command_type == Strategy.COMMAND_TRADER_MODIFY_ALL:
            return cmd_strategy_trader_modify_all(self, data)
        elif command_type == Strategy.COMMAND_TRADER_RECHECK_ALL:
            return cmd_strategy_trader_recheck_all(self, data)
        elif command_type == Strategy.COMMAND_TRADER_EXPORT_ALL:
            return cmd_strategy_trader_export_all(self, data)
        elif command_type == Strategy.COMMAND_TRADER_IMPORT_ALL:
            return cmd_strategy_trader_import_all(self, data)

        return None

    def strategy_trader_command(self, label: str, data: dict, func: callable) -> Union[dict, None]:
        # manually trade modify a trader state, or manage alerts
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)

        if not strategy_trader:
            # lookup by symbol name
            instrument = self.find_instrument(market_id)
            market_id = instrument.market_id if instrument else None

            strategy_trader = self._strategy_traders.get(market_id)

        if strategy_trader:
            Terminal.inst().notice("Strategy trader %s for strategy %s - %s %s" % (
                label, self.name, self.identifier, market_id), view='content')

            # retrieve the trade and apply the modification
            result = func(self, strategy_trader, data)

            # if result:
            #     if result['error']:
            #         Terminal.inst().info(result['messages'][0], view='status')
            #     else:
            #         Terminal.inst().info("Done", view='status')
            #
            #     for message in result['messages']:
            #         Terminal.inst().message(message, view='content')

            return result

        return None

    def trade_command(self, label: name, data: dict, func: callable) -> Union[dict, None]:
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)

        if not strategy_trader:
            # lookup by symbol name
            instrument = self.find_instrument(market_id)
            market_id = instrument.market_id if instrument else None

            strategy_trader = self._strategy_traders.get(market_id)

        if strategy_trader:
            Terminal.inst().notice("Trade %s for strategy %s - %s" % (
                label, self.name, self.identifier), view='content')

            # retrieve the trade and apply the modification
            result = func(self, strategy_trader, data)

            # if result:
            #     if result['error']:
            #         Terminal.inst().info(result['messages'][0], view='status')
            #     else:
            #         Terminal.inst().info("Done", view='status')
            #
            #     for message in result['messages']:
            #         Terminal.inst().message(message, view='content')

            return result

        return None

    #
    # static
    #

    @staticmethod
    def parse_parameters(parameters: dict) -> dict:
        def convert(_param, _key):
            _param.setdefault(_key, None)

            # convert timeframe code to float in second
            if isinstance(_param[_key], str):
                _param[_key] = timeframe_from_str(_param[_key])
            elif not isinstance(_param[_key], (int, float)):
                _param[_key] = None

        parameters.setdefault('reversal', True)
        parameters.setdefault('market-type', 0)
        parameters.setdefault('max-trades', 1)
        parameters.setdefault('min-traded-timeframe', '4h')
        parameters.setdefault('max-traded-timeframe', '4h')
        parameters.setdefault('min-vol24h', 0.0)
        parameters.setdefault('min-price', 0.0)
        parameters.setdefault('region-allow', True)

        # parse timeframes based values
        for k, param in parameters.items():
            # each key ending with -timeframe
            if k.endswith('-timeframe'):
                convert(parameters, k)

        # timeframes
        parameters.setdefault('timeframes', {})

        # markets specifics
        parameters.setdefault('markets', {})

        # for each timeframes
        removed_timeframes = []

        for k, timeframe in parameters['timeframes'].items():
            if timeframe is None:
                removed_timeframes.append(k)

        for rtf in removed_timeframes:
            del parameters['timeframes'][rtf]

        for k, timeframe in parameters['timeframes'].items():
            timeframe.setdefault('depth', 0)
            timeframe.setdefault('history', 0)

            timeframe.setdefault('timeframe', None)

            timeframe.setdefault('update-at-close', False)
            timeframe.setdefault('signal-at-close', False)

            convert(timeframe, 'timeframe')

        return parameters
