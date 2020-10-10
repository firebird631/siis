# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy interface

import os
import threading
import time
import collections

from datetime import datetime

from terminal.terminal import Terminal

from common.runnable import Runnable
from common.utils import timeframe_to_str, timeframe_from_str
from config.utils import merge_parameters

from common.signal import Signal
from instrument.instrument import Instrument

from watcher.watcher import Watcher

from trader.market import Market
from trader.order import Order

from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategypositiontrade import StrategyPositionTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade

from database.database import Database

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')
traceback_logger = logging.getLogger('siis.traceback.strategy')


class Strategy(Runnable):
    """
    Strategy base class.

    @todo Move Each COMMAND_ to command/ and have a registry
    @todo Add possibility to insert/delete a strategy trader during runtime only in live mode.

    @note In backtesting the method backtest_update don't mutex the strategy_traders list because
        in that case the dict never changes.
    """

    MAX_SIGNALS = 2000   # max size of the signals messages queue before ignore some market data (tick, ohlc)
    MAX_SIGNALS_DELAY = 5.0     # alert only when max signal is reach for a period of 5 seconds

    COMMAND_INFO = 1
    COMMAND_TRADE_EXIT_ALL = 2  # close any trade for any market or only for a specific market-id

    COMMAND_TRADE_ENTRY = 10    # manually create a new trade
    COMMAND_TRADE_MODIFY = 11   # modify an existing trade
    COMMAND_TRADE_EXIT = 12     # exit (or eventually cancel if not again filled) an existing trade
    COMMAND_TRADE_INFO = 13     # get and display manual trade info (such as listing operations)
    COMMAND_TRADE_ASSIGN = 14   # manually assign a quantity to a new trade
    COMMAND_TRADE_CLEAN = 15    # remove/clean an existing trade without filling the remaining quantity or in case of management issue

    COMMAND_TRADER_MODIFY = 20
    COMMAND_TRADER_INFO = 21
    COMMAND_TRADER_STREAM = 22

    def __init__(self, name, strategy_service, watcher_service, trader_service, options, default_parameters=None, user_parameters=None):
        super().__init__("st-%s" % name)

        self._name = name
        self._strategy_service = strategy_service
        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._identifier = None

        self._parameters = Strategy.parse_parameters(merge_parameters(default_parameters, user_parameters))

        self._preset = False       # True once instrument are setup
        self._prefetched = False   # True once strategies are ready

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
    def name(self):
        return self._name

    @property
    def watcher_service(self):
        return self._watcher_service
    
    @property
    def trader_service(self):
        return self._trader_service

    @property
    def service(self):
        return self._strategy_service

    @property
    def identifier(self):
        """Unique strategy identifier"""
        return self._identifier

    def set_identifier(self, identifier):
        """Unique strategy identifier"""
        self._identifier = identifier

    @property
    def parameters(self):
        """Configuration default merge with users"""
        return self._parameters

    def specific_parameters(self, market_id):
        """Strategy trader parameters overloaded by per market-id specific if exists"""
        if market_id in self._parameters['markets']:
            return merge_parameters(self._parameters, self._parameters['markets'][market_id])
        else:
            return self._parameters

    #
    # monitoring notification
    #

    def notify_signal(self, timestamp, signal, strategy_trader):
        """
        Notify a strategy signal (entry/take-profit) to the user. It must be called by the strategy-trader.
        """
        if signal:
            signal_data = signal.dumps_notify(timestamp, strategy_trader)

            # entry or exit signal
            if signal.signal > 0:
                self.service.notify(Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY, self._name, signal_data)
            elif signal.signal < 0:
                self.service.notify(Signal.SIGNAL_STRATEGY_SIGNAL_EXIT, self._name, signal_data)

    def notify_signal_exit(self, timestamp, signal, strategy_trader):
        """
        Notify a strategy signal (entry/take-profit) to the user. It must be called by the strategy-trader.
        """
        if signal:
            signal_data = signal.dumps_notify(timestamp, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_SIGNAL_EXIT, self._name, signal_data)

    def notify_trade_entry(self, timestamp, trade, strategy_trader):
        """
        Notify a strategy trade entry to the user. It must be called by the strategy-trader.
        """
        if trade:
            signal_data = trade.dumps_notify_entry(timestamp, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_ENTRY, self._name, signal_data)

    def notify_trade_exit(self, timestamp, trade, strategy_trader):
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

    def notify_alert(self, timestamp, alert, result, strategy_trader):
        """
        Notify a strategy alert to the user. It must be called by the strategy-trader.
        """
        if alert:
            signal_data = alert.dumps_notify(timestamp, result, strategy_trader)
            self.service.notify(Signal.SIGNAL_STRATEGY_ALERT, self._name, signal_data)

    def subscribe_stream(self, market_id, timeframe):
        """
        Override to create a specific streamer.
        """
        strategy_trader = self._strategy_traders.get(market_id)

        if not strategy_trader:
            return False

        return strategy_trader.subscribe_stream(timeframe)

    def unsubscribe_stream(self, market_id, timeframe):
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
    def timestamp(self):
        """
        Current time or last time if backtesting
        """
        if self.service.backtesting:
            return self._timestamp
        else:
            return time.time()

    @property
    def cpu_load(self):
        return self._cpu_load

    def check_watchers(self):
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

        # watcher can be already ready in some cases, try it now
        if self.check_watchers() and not self._preset:
            self.preset()

    def post_run(self):
        Terminal.inst().message("Joining strategy %s - %s..." % (self._name, self._identifier), view='content')

    def post_update(self):
        # load of the strategy
        self._cpu_load = len(self._signals) / float(Strategy.MAX_SIGNALS)

        # strategy must consume its signal else there is first a warning, and then some market data could be ignored
        if len(self._signals) > Strategy.MAX_SIGNALS:
            now = time.time()

            # but noly after a delay
            if self._overload_timestamp == 0.0:
                self._overload_timestamp = now

            elif time.time() - self._overload_timestamp > Strategy.MAX_SIGNALS_DELAY:
                Terminal.inst().warning("Strategy %s has more than %s waiting signals for the last %i seconds !" % (
                    self.name, Strategy.MAX_SIGNALS, Strategy.MAX_SIGNALS_DELAY), view='debug')

                self._overload_timestamp = now

    def ping(self, timeout):
        if self._condition.acquire(timeout=timeout):
            self._ping = (0, None, True)
            self._condition.notify()
            self._condition.release()
        else:
            Terminal.inst().action("Unable to join strategy %s - %s for %s seconds" % (self._name, self._identifier, timeout,), view='content')

    def watchdog(self, watchdog_service, timeout):
        if self._condition.acquire(timeout=timeout):
            self._ping = (watchdog_service.gen_pid(self._thread.name if self._thread else "unknown"), watchdog_service, False)
            self._condition.notify()
            self._condition.release()
        else:
            watchdog_service.service_timeout(self._thread.name if self._thread else "unknown",
                    "Unable to join appaliance %s - %s for %s seconds" % (self._name, self._identifier, timeout))

    def pong(self, timestamp, pid, watchdog_service, msg):
        if msg:
            # display strategy activity
            Terminal.inst().action("Strategy worker %s - %s is alive %s" % (self._name, self._identifier, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    #
    # strategy-trader processing
    #

    def create_trader(self, instrument):
        """
        To be overrided. Must return an instance of StrategyTrader specific for the strategy and instrument.
        """
        return None

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

            # help with watcher matching method
            strategy_symbols = watcher.matching_symbols_set(watcher_conf.get('symbols'), watcher.available_instruments())

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
                        instrument = Instrument(symbol, self.symbol_for_market_id(mapped_symbol) or symbol,
                                market_id=mapped_symbol, alias=mapped_instrument.get('alias'))

                        instrument.trade_quantity = mapped_instrument.get('size', 0.0)
                        instrument.trade_max_factor = mapped_instrument.get('max-factor', 1)

                        trade_qty_mode = mapped_instrument.get('size-mode', None)
                        if trade_qty_mode:
                            if trade_qty_mode == "quote-to-base":
                                instrument.trade_quantity_mode = Instrument.TRADE_QUANTITY_QUOTE_TO_BASE

                        instrument.leverage = mapped_instrument.get('leverage', 1.0)

                        market = self._trader.market(symbol)
                        if market:
                            # synchronize initial market data into the instrument
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
                            instrument.set_notional_limits(market.min_notional, market.max_notional, market.step_notional)
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

        self._preset = True

        # now can setup backtest or live mode
        if self.service.backtesting:
            self.setup_backtest(self.service.from_date, self.service.to_date, self.service.timeframe)
        else:
            self.setup_live()

    def stop(self):
        if self._running:
            self._running = False

            with self._condition:
                # wake up the update
                self._condition.notify()

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
        For each strategy-trader finalize to be done only in live mode.
        """
        with self._mutex:
            if not self.service.backtesting and not self.trader().paper_mode:
                for k, strategy_trader in self._strategy_traders.items():
                    strategy_trader.save()

    def indicator(self, name):
        """
        Get an indicator by its name
        """
        return self._strategy_service.indicator(name)

    def set_activity(self, status, market_id=None):
        """
        Enable/disable execution of orders (create_order, stop_loss) for any of the strategy traders or 
        a specific instrument if market_id is defined.
        """
        if market_id:
            with self._mutex:
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

    def mapped_instrument(self, symbol):
        """
        Return the string name of the market-id relating the symbol.
        """
        if self._trader_conf is None or not self._trader_conf.get('instruments'):
            return None

        if self._trader_conf['instruments'].get(symbol):
            return self._trader_conf['instruments'][symbol]

        # or already a mapped name
        for k, instrument in self._trader_conf['instruments'].items():
            if instrument.get('market-id', '') == symbol:
                return instrument

            # wildchar mapping of the instrument name
            if k.startswith('*'):
                if symbol.endswith(k[1:]):
                    return instrument

        return None

    #
    # symbols/instruments accessors
    #

    def symbols_ids(self):
        """
        Returns the complete list containing market-ids, theirs alias and theirs related symbol name.
        """
        with self._mutex:
            names = []

            for k, instrument in self._instruments.items():
                names.append(instrument.market_id)

                if instrument.symbol and instrument.symbol != instrument.market_id and instrument.symbol != instrument.alias:
                    names.append(instrument.symbol)

                if instrument.alias and instrument.alias != instrument.market_id and instrument.alias != instrument.symbol:
                    names.append(instrument.alias)

            names.sort()

        return names

    def instruments_ids(self):
        """
        Returns the complete list containing market-ids (instruments only).
        """
        with self._mutex:
            names = []

            for k, instrument in self._instruments.items():
                names.append(instrument.market_id)

            names.sort()

        return names

    def instrument(self, symbol_or_market_id):
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

    def symbol_for_market_id(self, market_id):
        if self._trader_conf is None or not self._trader_conf.get('instruments'):
            return None

        # or already a mapped name
        for k, instrument in self._trader_conf['instruments'].items():
            if instrument.get('market-id', '') == market_id:
                return k

        return None

    def find_instrument(self, symbol_or_market_id):
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
            if symbol_or_market_id == instr.name or symbol_or_market_id == instr.symbol or symbol_or_market_id == instr.alias:
                return instr

        return None

    #
    # strategy-trader profiles/context
    #

    def contexts_ids(self, market_id):
        contexts_ids = []

        if not market_id:
            return []

        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return []

        with strategy_trader._mutex:
            try:
                contexts_ids = strategy_trader.contexts_ids()              
            except Exception as e:
                error_logger.error(repr(e))

        return contexts_ids

    def dumps_context(self, market_id, context_id):
        context = None

        if not market_id or not context_id:
            return None

        strategy_trader = self._strategy_traders.get(market_id)
        if not strategy_trader:
            return None

        with strategy_trader._mutex:
            try:
                context = strategy_trader.dumps_context(context_id)
            except Exception as e:
                error_logger.error(repr(e))

        return context

    #
    # feeder for backtesting
    #

    def feeder(self, market_id):
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
    def base_timeframe(self):
        """
        Return the base timeframe at which the strategy process, and accept ticks or candles data from signals.
        Default returns at tick level. Override this method to change this value.
        """
        return Instrument.TF_TICK

    def update(self):
        """
        Does not override this method. Internal update mecanism.
        """
        with self._condition:
            # running cancel wait, ping too, normal case is a signal to process
            while (not len(self._signals) or not self._ping) and self._running:
                self._condition.wait()

        count = 0
        do_update = set()

        while self._signals:
            signal = self._signals.popleft()

            if signal.source == Signal.SOURCE_STRATEGY:
                if signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                    # incoming market info if backtesting
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    market = signal.data[1]

                    if market and strategy_trader:
                        # in backtesting mode set the market object to the paper trader directly because there is no watcher
                        if self.service.backtesting:
                            trader = self.trader_service.trader()
                            if trader:
                                trader.set_market(market)

                            with strategy_trader._mutex:
                                instrument = strategy_trader.instrument

                                # put interesting market data into the instrument
                                instrument.trade = market.trade
                                instrument.orders = market.orders
                                instrument.hedging = market.hedging
                                instrument.tradeable = market.is_open
                                instrument.expiry = market.expiry

                                instrument.set_base(market.base)
                                instrument.set_quote(market.quote)

                                instrument.set_price_limits(market.min_price, market.max_price, market.step_price)
                                instrument.set_notional_limits(market.min_notional, market.max_notional, market.step_notional)
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
                    for data in signal.data:
                        strategy_trader = self._strategy_traders.get(data[0])

                        # instantiate the trade and add it
                        if strategy_trader:
                            with strategy_trader._mutex:
                                strategy_trader.loads_trade(data[1], data[2], data[3], data[4])

                        # clear once done (@todo or by trade...)
                        trader = self.trader()
                        Database.inst().clear_user_trades(trader.name, trader.account.name, self.identifier)

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADER_LIST:
                    # for each market load the corresponding settings and regions to the strategy trader
                    for data in signal.data:
                        strategy_trader = self._strategy_traders.get(data[0])

                        # load strategy-trader data
                        if strategy_trader:
                            with strategy_trader._mutex:
                                strategy_trader.set_activity(data[1])
                                strategy_trader.loads(data[2], data[3], data[4])

            elif signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                    # interest in tick data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # add the new tick to the instrument in live mode
                        with strategy_trader._mutex:
                            if strategy_trader.instrument.ready():
                                strategy_trader.instrument.add_tick(signal.data[1])

                                do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                    # interest in candle data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # add the new candle to the instrument in live mode
                        with strategy_trader._mutex:
                            if strategy_trader.instrument.ready():
                                strategy_trader.instrument.add_candle(signal.data[1])

                                do_update.add(strategy_trader)

                if signal.signal_type == Signal.SIGNAL_TICK_DATA_BULK:
                    # incoming bulk of history ticks
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # initials ticks loaded
                        with strategy_trader._mutex:
                            strategy_trader.instrument.ack_timeframe(0)

                        # insert the bulk of ticks into the instrument
                        if signal.data[1]:
                            with strategy_trader._mutex:
                                # can accum before ready status
                                strategy_trader.instrument.add_ticks(signal.data[1])

                                do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA_BULK:
                    # incoming bulk of history candles
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        with strategy_trader._mutex:
                            initial = strategy_trader.instrument.ack_timeframe(signal.data[1])

                        # insert the bulk of candles into the instrument
                        if signal.data[2]:
                            # in live mode directly add candles to instrument
                            with strategy_trader._mutex:
                                strategy_trader.instrument.add_candles(signal.data[2])

                            # initials candles loaded
                            if initial:
                                instrument = strategy_trader.instrument

                                logger.debug("Retrieved %s OHLCs for %s in %s" % (len(signal.data[2]), instrument.market_id, timeframe_to_str(signal.data[1])))

                                # append the current OHLC from the watcher on live mode
                                if not self.service.backtesting:
                                    with strategy_trader._mutex:
                                        instrument.add_candle(instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME).current_ohlc(instrument.market_id, signal.data[1]))

                                strategy_trader.on_received_initial_candles(signal.data[1])                           

                            do_update.add(strategy_trader)

                elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                    # update market data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # update instrument data
                        with strategy_trader._mutex:
                            instrument = strategy_trader.instrument
                            instrument.tradeable = signal.data[1]

                            if signal.data[1]:
                                # only if valid field
                                if signal.data[2]:
                                    instrument.last_update_time = signal.data[2]

                                if signal.data[3]:
                                    instrument.market_bid = signal.data[3]
                                if signal.data[4]:
                                    instrument.market_ofr = signal.data[4]

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
                            with strategy_trader._mutex:
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
                                instrument.set_notional_limits(market.min_notional, market.max_notional, market.step_notional)
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
                    if self.check_watchers() and not self._preset:
                        self.preset()

                elif signal.signal_type == Signal.SIGNAL_WATCHER_DISCONNECTED:
                    # do we want to clean-up and wait connection signal to reinitiate ?
                    pass

                elif Signal.SIGNAL_POSITION_OPENED <= signal.signal_type <= Signal.SIGNAL_POSITION_AMENDED:
                    # position signal
                    self.position_signal(signal.signal_type, signal.data)

                elif Signal.SIGNAL_ORDER_OPENED <= signal.signal_type <= Signal.SIGNAL_ORDER_TRADED:
                    # trade signal
                    self.order_signal(signal.signal_type, signal.data)

            # count += 1
            # if count > 10:
            #     # no more than 10 signals per loop, allow aggregate fast ticks, and don't block the processing
            #     break

        if self.service.backtesting:
            # process one more backtest step
            with self._mutex:
                next_bt_upd = self._next_backtest_update
                self._next_backtest_update = None

            if next_bt_upd:
                self.backtest_update(next_bt_upd[0], next_bt_upd[1])
        else:
            # normal processing
            if do_update:
                if len(self._strategy_traders) >= 1:
                    # always aync update process
                    for strategy_trader in do_update:
                        if strategy_trader.instrument.ready():
                            # parallelize jobs on workers
                            self.service.worker_pool.add_job(None, (self.async_update_strategy, (strategy_trader,)))
                else:
                    # no parallelisation for single instrument
                    for strategy_trader in do_update:
                        if strategy_trader.instrument.ready():
                            self.update_strategy(strategy_trader)

        return True

    def bootstrap(self, strategy_trader):
        """
        Process the bootstrap of the strategy trader until complete using the preloaded OHLCs.
        Any received updates are ignored until the bootstrap is completed.
        """
        if strategy_trader._bootstraping == 2:
            # in progress
            return

        # bootstraping in progress, avoid live until complete
        strategy_trader._bootstraping = 2

        try:
            if strategy_trader.is_timeframes_based:
                self.timeframe_based_bootstrap(strategy_trader)
            elif strategy_trader.is_tickbars_based:
                self.tickbar_based_bootstrap(strategy_trader)
        except Error as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        # bootstraping done, can now branch to live
        strategy_trader._bootstraping = 0

    def timeframe_based_bootstrap(self, strategy_trader):
        # captures all initials candles
        initial_candles = {}

        # compute the begining timestamp
        next_timestamp = self.timestamp

        instrument = strategy_trader.instrument

        for tf, sub in strategy_trader.timeframes.items():
            candles = instrument.candles(tf)
            initial_candles[tf] = candles

            # reset, distribute one at time
            instrument._candles[tf] = []

            if candles:
                # get the nearest next candle
                next_timestamp = min(next_timestamp, candles[0].timestamp + sub.depth*sub.timeframe)

        logger.debug("%s timeframes bootstrap begin at %s, now is %s" % (instrument.market_id, next_timestamp, self.timestamp))

        # initials candles
        lower_timeframe = 0

        for tf, sub in strategy_trader.timeframes.items():
            candles = initial_candles[tf]

            # feed with the initials candles
            while candles and next_timestamp >= candles[0].timestamp:
                candle = candles.pop(0)

                instrument._candles[tf].append(candle)

                # and last is closed
                sub._last_closed = True

                # keep safe size
                if(len(instrument._candles[tf])) > sub.depth:
                    instrument._candles[tf].pop(0)

                # prev and last price according to the lower timeframe close
                if not lower_timeframe or tf < lower_timeframe:
                    lower_timeframe = tf
                    strategy_trader.prev_price = strategy_trader.last_price
                    strategy_trader.last_price = candle.close  # last mid close

            sub.next_timestamp = next_timestamp  # + lower_timeframe
            # logger.debug("%s for %s and time is %s rest=%s" % (len(instrument._candles[tf]), tf, sub.next_timestamp, len(initial_candles[tf])))

        # process one lowest candle at time
        while 1:
            num_candles = 0
            strategy_trader.bootstrap(next_timestamp)

            # at least of lower timeframe
            base_next_timestamp = 0.0
            lower_timeframe = 0

            # increment by the lower available timeframe
            for tf, sub in strategy_trader.timeframes.items():
                if initial_candles[tf]:
                    if not base_next_timestamp:
                        # initiate with the first
                        base_next_timestamp = initial_candles[tf][0].timestamp

                    elif initial_candles[tf][0].timestamp < base_next_timestamp:
                        # found a lower
                        base_next_timestamp = initial_candles[tf][0].timestamp

            for tf, sub in strategy_trader.timeframes.items():
                candles = initial_candles[tf]

                # feed with the next candle
                if candles and base_next_timestamp >= candles[0].timestamp:
                    candle = candles.pop(0)

                    instrument._candles[tf].append(candle)

                    # and last is closed
                    sub._last_closed = True

                    # keep safe size
                    if(len(instrument._candles[tf])) > sub.depth:
                        instrument._candles[tf].pop(0)

                    if not lower_timeframe or tf < lower_timeframe:
                        lower_timeframe = tf
                        strategy_trader.prev_price = strategy_trader.last_price
                        strategy_trader.last_price = candle.close  # last mid close

                    num_candles += 1

            # logger.info("next is %s (delta=%s) / now %s (n=%i) (low=%s)" % (base_next_timestamp, base_next_timestamp-next_timestamp, self.timestamp, num_candles, lower_timeframe))
            next_timestamp = base_next_timestamp

            if not num_candles:
                # no more candles to process
                break

        logger.debug("%s timeframes bootstraping done" % instrument.market_id)

    def tickbar_based_bootstrap(self, strategy_trader):
        # captures all initials candles
        initial_ticks = []

        # compute the begining timestamp
        next_timestamp = self.timestamp

        instrument = strategy_trader.instrument

        logger.debug("%s tickbars bootstrap begin at %s, now is %s" % (instrument.market_id, next_timestamp, self.timestamp))

        # @todo need tickstreamer, and call strategy_trader.bootstrap(next_timestamp) at per bulk of ticks (temporal size defined)

        logger.debug("%s tickbars bootstraping done" % instrument.market_id)

    def update_strategy(self, strategy_trader):
        """
        Override this method to compute a strategy step per instrument.
        Default implementation supports bootstrapping.
        @param strategy_trader StrategyTrader Instance of the strategy trader to process.
        @note Non thread-safe method.
        """
        if strategy_trader:
            strategy_trader._processing = True

            if strategy_trader._bootstraping:
                # bootstrap using preloaded data history
                self.bootstrap(strategy_trader)
            else:
                # until process instrument update
                strategy_trader.process(self.timestamp)

            strategy_trader._processing = False

    def async_update_strategy(self, strategy_trader):
        """
        Override this method to compute a strategy step per instrument.
        Default implementation supports bootstrapping.
        @param strategy_trader StrategyTrader Instance of the strategy trader to process.
        @note Thread-safe method.
        """
        if strategy_trader:
            # process only if previous job was completed
            process = False

            with strategy_trader._mutex:
                if not strategy_trader._processing:
                    # can process
                    process = strategy_trader._processing = True

            if process:
                if strategy_trader._bootstraping:
                    self.bootstrap(strategy_trader)
                else:
                    strategy_trader.process(self.timestamp)

                with strategy_trader._mutex:
                    # process complete
                    strategy_trader._processing = False

    #
    # backtesting
    #

    def setup_backtest(self, from_date, to_date, base_timeframe=Instrument.TF_TICK):
        """
        Override this method to implement your backtesting strategy data set of instrument and feeders.
        """
        pass

    def query_backtest_update(self, timestamp, total_ts):
        with self._mutex:
            self._next_backtest_update = (timestamp, total_ts)

    def backtest_update_instrument(self, trader, strategy_trader, timestamp):
        # retrieve the feeder by market_id
        instrument = strategy_trader.instrument

        feeder = self._feeders.get(instrument.market_id)

        # feed of candles prior equal the timestamp and update if new candles on configured timeframe
        updated = feeder.feed(timestamp)

        if trader and updated:
            # update the market instrument data before processing
            # but we does not have the exact base exchange rate and contract size, its emulated in the paper trader

            # the feeder update the instrument price data, so use them directly
            trader.on_update_market(instrument.market_id, True, instrument.last_update_time,
                    instrument.market_bid, instrument.market_ofr, None)

        # update strategy as necessary
        if updated:
            self.update_strategy(strategy_trader)
            # self.async_update_strategy(strategy_trader)

    def backtest_update(self, timestamp, total_ts):
        """
        Process the backtesting update, for any instrument feeds candles to instruments and does the necessary updates.
        Override only if necessary. This default implementation should suffise.

        The strategy_trader list here is not mutexed, because it backtesting context we never could add or remove one.
        """
        trader = self.trader()

        if not self.ready():
            return

        # processing timestamp
        self._timestamp = timestamp

        if len(self._strategy_traders) > 3:
            count_down = self.service.worker_pool.new_count_down(len(self._strategy_traders))

            for market_id, strategy_trader in self._strategy_traders.items():
                # parallelize jobs on workers
                self.service.worker_pool.add_job(count_down, (self.backtest_update_instrument, (trader, strategy_trader, timestamp)))

            # sync before continue
            count_down.wait()
        else:
            # no parallelisation below 4 instruments
            for market_id, strategy_trader in self._strategy_traders.items():
                self.backtest_update_instrument(trader, strategy_trader, timestamp)

        # last done timestamp, to manage progression
        self._last_done_ts = timestamp


    def reset(self):
        # backtesting only, the last processed timestamp
        self._last_done_ts = 0
        self._timestamp = 0

    #
    # setup and processing state and condition
    #

    def ready(self):
        """
        Must return True once the strategy is ready te begin.
        Override only if necessary. This default implementation should suffise.
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

        self._ready = self._running and self._preset and self._prefetched

        return self._ready

    def finished(self):
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

    def progress(self):
        """
        During backtesting return the last processed timestamp.
        """
        # if not self.is_alive():
        if not self.running:
            return 0

        return self._last_done_ts

    #
    # live setup
    #

    def setup_live(self):
        """
        Override this method to implement your live strategy data setup.
        Do it here dataset preload and other stuff before update be called.
        """

        # load the strategy-traders and traders for this strategy/account
        trader = self.trader()

        Database.inst().load_user_trades(self.service, self, trader.name,
                trader.account.name, self.identifier)

        Database.inst().load_user_traders(self.service, self, trader.name,
                trader.account.name, self.identifier)

    #
    # commands
    #

    def trade_command(self, label, data, func):
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)
        if strategy_trader:
            Terminal.inst().notice("Trade %s for strategy %s - %s" % (label, self.name, self.identifier), view='content')

            # retrieve the trade and apply the modification
            result = func(strategy_trader, data)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

                return result

        return None

    def exit_all_trade_command(self, data):
        # manually trade modify a trade or any trades (add/remove an operation)
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)
        if strategy_trader and strategy_trader.has_trades():
            Terminal.inst().notice("Multi trade exit for strategy %s - %s" % (self.name, self.identifier), view='content')

            # retrieve any trades
            trades = []

            # if there is some trade, cancel or close them, else goes to the next trader
            if strategy_trader.has_trades():
                trades.extend([(strategy_trader.instrument.market_id, trade_id) for trade_id in strategy_trader.list_trades()])

            # multi command
            results = []

            for trade in trades:
                # retrieve the trade and apply the modification
                strategy_trader = self._strategy_traders.get(trade[0])
                data['trade-id'] = trade[1]

                result = self.cmd_trade_exit(strategy_trader, data)

                if result:
                    if result['error']:
                        Terminal.inst().info(result['messages'][0], view='status')
                    else:
                        Terminal.inst().info("Done", view='status')

                    for message in result['messages']:
                        Terminal.inst().message(message, view='content')

                results.append(result)

            return results
        else:
            Terminal.inst().notice("Multi trade exit for strategy %s - %s" % (self.name, self.identifier), view='content')

            # retrieve any trades for any traders
            trades = []

            with self._mutex:
                for market_id, strategy_trader in self._strategy_traders.items():
                    # if there is some trade, cancel or close them, else goes to the next trader
                    if strategy_trader.has_trades():
                        trades.extend([(strategy_trader.instrument.market_id, trade_id) for trade_id in strategy_trader.list_trades()])

            # multi command
            results = []

            for trade in trades:
                # retrieve the trade and apply the modification
                strategy_trader = self._strategy_traders.get(trade[0])
                data['trade-id'] = trade[1]

                result = self.cmd_trade_exit(strategy_trader, data)

                if result:
                    if result['error']:
                        Terminal.inst().info(result['messages'][0], view='status')
                    else:
                        Terminal.inst().info("Done", view='status')

                    for message in result['messages']:
                        Terminal.inst().message(message, view='content')

                results.append(result)

            return results

    def strategy_trader_command(self, label, data, func):
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)
        if strategy_trader:
            Terminal.inst().notice("Strategy trader %s for strategy %s - %s %s" % (label, self.name, self.identifier, market_id), view='content')

            # retrieve the trade and apply the modification
            result = func(strategy_trader, data)

            if result:
                if result['error']:
                    Terminal.inst().info(result['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in result['messages']:
                    Terminal.inst().message(message, view='content')

            return result

        return None

    def command(self, command_type, data):
        """
        Apply a command to the strategy and return a results dict or an array of dict or None.
        """
        if command_type == Strategy.COMMAND_INFO:
            return self.cmd_trader_info(data)

        elif command_type == Strategy.COMMAND_TRADE_EXIT_ALL:
            return self.exit_all_trade_command(data)

        elif command_type == Strategy.COMMAND_TRADE_ENTRY:
            return self.trade_command("entry", data, self.cmd_trade_entry)
        elif command_type == Strategy.COMMAND_TRADE_EXIT:
            return self.trade_command("exit", data, self.cmd_trade_exit)
        elif command_type == Strategy.COMMAND_TRADE_CLEAN:
            return self.trade_command("clean", data, self.cmd_trade_clean)
        elif command_type == Strategy.COMMAND_TRADE_MODIFY:
            return self.trade_command("modify", data, self.cmd_trade_modify)
        elif command_type == Strategy.COMMAND_TRADE_INFO:
            return self.trade_command("info", data, self.cmd_trade_info)
        elif command_type == Strategy.COMMAND_TRADE_ASSIGN:
            return self.trade_command("assign", data, self.cmd_trade_assign)

        elif command_type == Strategy.COMMAND_TRADER_MODIFY:
            return self.strategy_trader_command("info", data, self.cmd_strategy_trader_modify)
        elif command_type == Strategy.COMMAND_TRADER_INFO:
            return self.strategy_trader_command("info", data, self.cmd_strategy_trader_info)
        elif command_type == Strategy.COMMAND_TRADER_STREAM:
            return self.strategy_trader_command("stream", data, self.cmd_strategy_trader_stream)

        return None

    #
    # signals/slots
    #

    def _add_signal(self, signal):
        with self._condition:
            self._signals.append(signal)
            self._condition.notify()

    def receiver(self, signal):
        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

                # signal of interest
                self._add_signal(signal)

        elif signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name not in self._watchers_conf:
                # not interested by this watcher
                return

            # filter by instrument for tick data
            if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                if Instrument.TF_TICK != self.base_timeframe:
                    # must be equal to the base timeframe only
                    return

                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                if signal.data[1].timeframe != self.base_timeframe:
                    # must be of equal to the base timeframe only
                    return

                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

            # filter by instrument for buy/sell signal
            elif signal.signal_type == Signal.SIGNAL_BUY_SELL_ORDER:
                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                if signal.data[0] not in self._strategy_traders:
                    # non interested by this instrument/symbol
                    return

            # if len(self._signals) > Strategy.MAX_SIGNALS:
            #     # from the watcher (in live) so then ignore some of those message, the others ones are too important to be ignored
            #     if signal.signal_type in (Signal.SIGNAL_TICK_DATA, Signal.SIGNAL_MARKET_DATA):
            #         return

            # signal of interest
            self._add_signal(signal)

        elif signal.source == Signal.SOURCE_TRADER:
            if self._trader_conf and signal.source_name == self._trader_conf['name']:
                # signal of interest
                self._add_signal(signal)

    def position_signal(self, signal_type, data):
        """
        Receive of the position signals. Dispatch if mapped instrument.
        """
        strategy_trader = self._strategy_traders.get(data[0])
        if strategy_trader:
            strategy_trader.position_signal(signal_type, data)

    def order_signal(self, signal_type, data):
        """
        Receive of the order signals. Dispatch if mapped instrument.
        """
        strategy_trader = self._strategy_traders.get(data[0])
        if strategy_trader:
            strategy_trader.order_signal(signal_type, data)

    #
    # helpers
    #

    def dumps_trades_update(self):
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

    def dumps_trades_history(self):
        """
        Dumps trade records of any historical trades of any strategy traders.
        """
        trades = []

        with self._mutex:
            for k, strategy_trader in self._strategy_traders.items():
                try:
                    trades += strategy_trader.dumps_trades_history()
                except Exception as e:
                    error_logger.error(repr(e))

        return trades

    #
    # trade commands (@todo to be moved to decicated command/file.py)
    #

    def cmd_trade_entry(self, strategy_trader, data):
        """
        Create a new trade according data on given strategy_trader.
        """
        results = {
            'messages': [],
            'error': False
        }

        # command data
        direction = data.get('direction', Order.LONG)
        method = data.get('method', 'market')
        limit_price = data.get('limit-price')
        trigger_price = data.get('trigger-price')
        quantity_rate = data.get('quantity-rate', 1.0)
        stop_loss = data.get('stop-loss', 0.0)
        take_profit = data.get('take-profit', 0.0)
        stop_loss_price_mode = data.get('stop-loss-price-mode', 'price')
        take_profit_price_mode = data.get('take-profit-price-mode', 'price')
        timeframe = data.get('timeframe', Instrument.TF_4HOUR)
        leverage = data.get('leverage', 1.0)
        hedging = data.get('hedging', True)
        margin_trade = data.get('margin-trade', False)
        entry_timeout = data.get('entry-timeout', None)
        context = data.get('context', None)

        if quantity_rate <= 0.0:
            results['messages'].append("Missing or empty quantity.")
            results['error'] = True

        if method not in ('market', 'limit', 'trigger', 'best-1', 'best+1'):
            results['messages'].append("Invalid price method (market, limit, trigger, best-1, best+1).")
            results['error'] = True

        if method == 'limit' and not limit_price:
            results['messages'].append("Price is missing.")
            results['error'] = True

        if results['error']:
            return results

        if method == 'market':
            order_type = Order.ORDER_MARKET
        
        elif method == 'limit':
            order_type = Order.ORDER_LIMIT
        
        elif method == 'trigger':
            order_type = Order.ORDER_STOP
        
        elif method == 'best-1':
            # limit : first ask price in long, first bid price in short
            order_type = Order.ORDER_LIMIT
            limit_price = strategy_trader.instrument.close_exec_price(direction)

        elif method == 'best-2':
            # limit : second ask price in long, second bid price in short
            order_type = Order.ORDER_LIMIT
            limit_price = strategy_trader.instrument.close_exec_price(direction)

        elif method == 'best+1':
            # limit if supported by broker : first bid price in long, first ask price in short
            order_type = Order.ORDER_LIMIT
            limit_price = strategy_trader.instrument.open_exec_price(direction)

        elif method == 'best+2':
            # limit if supported by broker : second bid price in long, second ask price in short
            order_type = Order.ORDER_LIMIT
            limit_price = strategy_trader.instrument.open_exec_price(direction)

        else:
            order_type = Order.ORDER_MARKET

        order_quantity = 0.0

        trader = self.trader()

        # need a valid price to compute the quantity
        price = limit_price or strategy_trader.instrument.open_exec_price(direction)
        trade = None

        if price <= 0.0:
            results['error'] = True
            results['messages'].append("Not price found for %s" % (strategy_trader.instrument.market_id,))
            return results

        if strategy_trader.instrument.has_spot and not margin_trade:
            # market support spot and margin option is not defined
            trade = StrategyAssetTrade(timeframe)

            # ajust max quantity according to free asset of quote, and convert in asset base quantity
            if trader.has_asset(strategy_trader.instrument.quote):
                qty = strategy_trader.instrument.trade_quantity*quantity_rate

                if trader.has_quantity(strategy_trader.instrument.quote, qty):
                    order_quantity = strategy_trader.instrument.adjust_quantity(qty / price)  # and adjusted to 0/max/step
                else:
                    results['error'] = True
                    results['messages'].append("Not enought free quote asset %s, has %s but need %s" % (
                            strategy_trader.instrument.quote,
                            strategy_trader.instrument.format_quantity(trader.asset(strategy_trader.instrument.quote).free),
                            strategy_trader.instrument.format_quantity(qty)))

        elif strategy_trader.instrument.has_margin and strategy_trader.instrument.has_position:
            trade = StrategyPositionTrade(timeframe)

            if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
            else:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

            if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
                results['error'] = True
                results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

        elif strategy_trader.instrument.has_margin and strategy_trader.instrument.indivisible_position:
            trade = StrategyIndMarginTrade(timeframe)

            if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
            else:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

            if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
                results['error'] = True
                results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

        elif strategy_trader.instrument.has_margin and not strategy_trader.instrument.indivisible_position and not strategy_trader.instrument.has_position:
            trade = StrategyMarginTrade(timeframe)

            if strategy_trader.instrument.trade_quantity_mode == Instrument.TRADE_QUANTITY_QUOTE_TO_BASE:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate/price)
            else:
                order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

            if not trader.has_margin(strategy_trader.instrument.market_id, order_quantity, price):
                results['error'] = True
                results['messages'].append("Not enought margin, need %s" % (trader.get_needed_margin(strategy_trader.instrument.market_id, order_quantity, price),))

        else:
            results['error'] = True
            results['messages'].append("Unsupported market type")

        if order_quantity <= 0 or order_quantity * price < strategy_trader.instrument.min_notional:
            results['error'] = True
            results['messages'].append("Min notional not reached (%s)" % strategy_trader.instrument.min_notional)

        if results['error']:
            return results

        order_price = strategy_trader.instrument.adjust_price(price)

        #
        # compute stop-loss and take-profit price depending of their respective mode
        #

        if stop_loss_price_mode == "percent":
            if direction > 0:
                stop_loss = strategy_trader.instrument.adjust_price(order_price * (1.0 - stop_loss * 0.01))
            elif direction < 0:
                stop_loss = strategy_trader.instrument.adjust_price(order_price * (1.0 + stop_loss * 0.01))

        elif stop_loss_price_mode == "pip":
            if direction > 0:
                stop_loss = strategy_trader.instrument.adjust_price(order_price - stop_loss * strategy_trader.instrument.value_per_pip)
            elif direction < 0:
                stop_loss = strategy_trader.instrument.adjust_price(order_price + stop_loss * strategy_trader.instrument.value_per_pip)

        if take_profit_price_mode == "percent":
            if direction > 0:
                take_profit = strategy_trader.instrument.adjust_price(order_price * (1.0 + take_profit * 0.01))
            elif direction < 0:
                take_profit = strategy_trader.instrument.adjust_price(order_price * (1.0 - take_profit * 0.01))

        elif take_profit_price_mode == "pip":
            if direction > 0:
                take_profit = strategy_trader.instrument.adjust_price(order_price + take_profit * strategy_trader.instrument.value_per_pip)
            elif direction < 0:
                take_profit = strategy_trader.instrument.adjust_price(order_price - take_profit * strategy_trader.instrument.value_per_pip)

        #
        # check stop-loss and take-profit and reject if not consistent
        #

        if stop_loss < 0.0:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the stop-loss is negative" % (self.identifier, strategy_trader.instrument.market_id))

            return results

        if take_profit < 0.0:
            results['error'] = True
            results['messages'].append("Rejected trade on %s:%s because the take-profit is negative" % (self.identifier, strategy_trader.instrument.market_id))

            return results

        if direction > 0:
            if stop_loss > order_price:
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s because the stop-loss is above the entry price" % (self.identifier, strategy_trader.instrument.market_id))

                return results

            if take_profit < order_price:
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s because the take-profit is below the entry price" % (self.identifier, strategy_trader.instrument.market_id))

                return results

        elif direction < 0:
            if stop_loss < order_price:
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s because the stop-loss is below the entry price" % (self.identifier, strategy_trader.instrument.market_id))

                return results

            if take_profit > order_price:
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s because the take-profit is above the entry price" % (self.identifier, strategy_trader.instrument.market_id))

                return results

        if trade:
            # user managed trade
            trade.set_user_trade()

            if entry_timeout:
                # entry timeout expiration defined (could be overrided by trade context if specified)
                trade.entry_timeout = entry_timeout

            if context:
                if not strategy_trader.set_trade_context(trade, context):
                    # add an error result message
                    results['error'] = True
                    results['messages'].append("Rejected trade on %s:%s because the context was not found" % (self.identifier, strategy_trader.instrument.market_id))

                    return results

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            strategy_trader.add_trade(trade)

            if trade.open(trader, strategy_trader.instrument, direction, order_type, order_price, order_quantity,
                          take_profit, stop_loss, leverage=leverage, hedging=hedging):

                # notifications and stream
                strategy_trader.notify_trade_entry(self.timestamp, trade)

                # add a success result message
                results['messages'].append("Created trade %i on %s:%s" % (trade.id, self.identifier, strategy_trader.instrument.market_id))
            else:
                strategy_trader.remove_trade(trade)

                # add an error result message
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s" % (self.identifier, strategy_trader.instrument.market_id))

        return results

    def cmd_trade_exit(self, strategy_trader, data):
        """
        Exit an existing trade according data on given strategy_trader.

        @note If trade-id is -1 assume the last trade.
        """
        results = {
            'messages': [],
            'error': False
        }

        # retrieve the trade
        trade_id = -1

        try:
            trade_id = int(data.get('trade-id'))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid trade identifier")

        if results['error']:
            return results

        trade = None

        trader = self.trader()

        with strategy_trader._mutex:
            if trade_id == -1 and strategy_trader.trades:
                trade = strategy_trader.trades[-1]
            else:
                for t in strategy_trader.trades:
                    if t.id == trade_id:
                        trade = t
                        break

            if trade:
                price = strategy_trader.instrument.close_exec_price(trade.direction)

                if not trade.is_active():
                    # cancel open
                    trade.cancel_open(trader, strategy_trader.instrument)

                    # add a success result message
                    results['messages'].append("Cancel trade %i on %s:%s" % (trade.id, self.identifier, strategy_trader.instrument.market_id))
                else:
                    # close or cancel
                    trade.close(trader, strategy_trader.instrument)

                    # add a success result message
                    results['messages'].append("Close trade %i on %s:%s at market price %s" % (
                        trade.id, self.identifier, strategy_trader.instrument.market_id, strategy_trader.instrument.format_price(price)))
            else:
                results['error'] = True
                results['messages'].append("Invalid trade identifier %i" % trade_id)

        return results

    def cmd_trade_clean(self, strategy_trader, data):
        """
        Clean an existing trade according data on given strategy_trader.

        @note If trade-id is -1 assume the last trade.
        """
        results = {
            'messages': [],
            'error': False
        }

        # retrieve the trade
        trade_id = -1

        try:
            trade_id = int(data.get('trade-id'))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid trade identifier")

        if results['error']:
            return results

        trade = None
        trader = self.trader()

        with strategy_trader._mutex:
            if trade_id == -1 and strategy_trader.trades:
                trade = strategy_trader.trades[-1]
            else:
                for t in strategy_trader.trades:
                    if t.id == trade_id:
                        trade = t
                        break

            if trade:
                # remove orders
                trade.remove(trader, strategy_trader.instrument)

                # and the trade, don't keet it for history because unqualifiable
                strategy_trader.remove_trade(trade)

                # add a success result message
                results['messages'].append("Force remove trade %i on %s:%s" % (trade.id, self.identifier, strategy_trader.instrument.market_id))
            else:
                results['error'] = True
                results['messages'].append("Invalid trade identifier %i" % trade_id)

        return results

    def cmd_trade_modify(self, strategy_trader, data):
        """
        Modify a trade according data on given strategy_trader.

        @note If trade-id is -1 assume the last trade.
        """
        results = {
            'messages': [],
            'error': False
        }

        # retrieve the trade
        trade_id = -1
        action = ""

        try:
            trade_id = int(data.get('trade-id'))
            action = data.get('action')
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid trade identifier")

        if results['error']:
            return results

        trade = None

        with strategy_trader._mutex:
            if trade_id == -1 and strategy_trader.trades:
                trade = strategy_trader.trades[-1]
            else:
                for t in strategy_trader.trades:
                    if t.id == trade_id:
                        trade = t
                        break

            if trade:
                # modify SL
                if action == 'stop-loss' and 'stop-loss' in data and type(data['stop-loss']) in (float, int):
                    if data['stop-loss'] > 0.0:
                        if trade.has_stop_order() or data.get('force', False):
                            trade.modify_stop_loss(self.trader(), strategy_trader.instrument, data['stop-loss'])
                        else:
                            trade.sl = data['stop-loss']
                    else:
                        results['error'] = True
                        results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

                # modify TP
                elif action == 'take-profit' and 'take-profit' in data and type(data['take-profit']) in (float, int):
                    if data['take-profit'] > 0.0:
                        if trade.has_limit_order() or data.get('force', False):
                            trade.modify_take_profit(self.trader(), strategy_trader.instrument, data['take-profit'])
                        else:
                            trade.tp = data['take-profit']
                    else:
                        results['error'] = True
                        results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

                # add operation
                elif action == 'add-op':
                    op_name = data.get('operation', "")

                    if op_name in self.service.tradeops:
                        try:
                            # instanciate the operation
                            operation = self.service.tradeops[op_name]()

                            # and define the parameters
                            operation.init(data)

                            if operation.check(trade):
                                # append the operation to the trade
                                trade.add_operation(operation)
                            else:
                                results['error'] = True
                                results['messages'].append("Operation checking error %s on trade %i" % (op_name, trade.id))

                        except Exception as e:
                            results['error'] = True
                            results['messages'].append(repr(e))
                    else:
                        results['error'] = True
                        results['messages'].append("Unsupported operation %s on trade %i" % (op_name, trade.id))

                # remove operation
                elif action == 'del-op':
                    trade_operation_id = -1

                    if 'operation-id' in data and type(data.get('operation-id')) is int:
                        trade_operation_id = data['operation-id']

                    if not trade.remove_operation(trade_operation_id):
                        results['error'] = True
                        results['messages'].append("Unknown operation-id on trade %i" % trade.id)
                else:
                    # unsupported action
                    results['error'] = True
                    results['messages'].append("Unsupported action on trade %i" % trade.id)

            else:
                results['error'] = True
                results['messages'].append("Invalid trade identifier %i" % trade_id)

        return results

    def cmd_trade_assign(self, strategy_trader, data):
        """
        Assign a free quantity of an asset to a newly created trade according data on given strategy_trader.
        """
        results = {
            'messages': [],
            'error': False
        }

        # command data
        direction = data.get('direction', Order.LONG)
        entry_price = data.get('entry-price', 0.0)
        quantity = data.get('quantity', 0.0)
        stop_loss = data.get('stop-loss', 0.0)
        take_profit = data.get('take-profit', 0.0)
        timeframe = data.get('timeframe', Instrument.TF_4HOUR)

        if quantity <= 0.0:
            results['messages'].append("Missing or empty quantity.")
            results['error'] = True

        if entry_price <= 0:
            results['messages'].append("Invalid entry price.")
            results['error'] = True

        if stop_loss and stop_loss > entry_price:
            results['messages'].append("Stop-loss price must be lesser than entry price.")
            results['error'] = True

        if take_profit and take_profit < entry_price:
            results['messages'].append("Take-profit price must be greater then entry price.")
            results['error'] = True

        if direction != Order.LONG:
            results['messages'].append("Only trade long direction is allowed.")
            results['error'] = True

        trader = self.trader()

        if not trader.has_quantity(strategy_trader.instrument.base, quantity):
            results['messages'].append("No enought free asset quantity.")
            results['error'] = True

        # @todo trade type
        if not strategy_trader.instrument.has_spot:
            results['messages'].append("Only allowed on a spot market.")
            results['error'] = True

        if results['error']:
            return results

        trade = StrategyAssetTrade(timeframe)

        # user managed trade
        trade.set_user_trade()

        trade._entry_state = StrategyAssetTrade.STATE_FILLED
        trade._exit_state = StrategyAssetTrade.STATE_NEW
        
        trade.dir = Order.LONG
        trade.op = entry_price
        trade.oq = quantity

        trade.tp = take_profit
        trade.sl = stop_loss        

        trade.eot = time.time()

        trade.aep = entry_price

        trade.e = quantity

        strategy_trader.add_trade(trade)

        results['messages'].append("Assigned trade %i on %s:%s" % (trade.id, self.identifier, strategy_trader.instrument.market_id))

        return results

    def cmd_trade_info(self, strategy_trader, data):
        """
        Get trade info according data on given strategy_trader.

        @note If trade-id is -1 assume the last trade.
        """        
        results = {
            'messages': [],
            'error': False
        }

        trade_id = -1

        try:
            trade_id = int(data.get('trade-id'))
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid trade identifier")

        if results['error']:
            return results

        trade = None

        with strategy_trader._mutex:
            if trade_id == -1 and strategy_trader.trades:
                trade = strategy_trader.trades[-1]
            else:
                for t in strategy_trader.trades:
                    if t.id == trade_id:
                        trade = t
                        break

            if trade:
                results['messages'].append("Trade %i, list %i operations:" % (trade.id, len(trade.operations)))

                # @todo or as table using operation.parameters() dict
                for operation in trade.operations:
                    results['messages'].append(" - #%i: %s" % (operation.id, operation.str_info()))
            else:
                results['error'] = True
                results['messages'].append("Invalid trade identifier %i" % trade_id)

        return results

    def cmd_trade_close_all(self, strategy_trader, data):
        """
        Close any active trade for the strategy trader, at market, deleted related orders.
        """
        results = {
            'messages': [],
            'error': False
        }

        # @todo

        return results

    def cmd_trade_sell_all(self, strategy_trader, data):
        """
        Assign a free quantity of an asset to a newly created trade according data on given strategy_trader.
        """
        results = {
            'messages': [],
            'error': False
        }

        # @todo

        return results

    def cmd_strategy_trader_modify(self, strategy_trader, data):
        """
        Modify a strategy-trader state, a region or an alert.
        """        
        results = {
            'messages': [],
            'error': False
        }

        action = ""
        expiry = 0
        countdown = -1
        timeframe = 0

        with strategy_trader._mutex:
            try:
                action = data.get('action')
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid trader action")

            if action == "add-region":
                region_name = data.get('region', "")

                try:
                    stage = int(data.get('stage', 0))
                    direction = int(data.get('direction', 0))
                    created = float(data.get('created', 0.0))
                    expiry = float(data.get('expiry', 0.0))

                    if 'timeframe' in data and type(data['timeframe']) is str:
                        timeframe = timeframe_from_str(data['timeframe'])

                except ValueError:
                    results['error'] = True
                    results['messages'].append("Invalid parameters")

                if not results['error']:
                    if region_name in self.service.regions:
                        try:
                            # instanciate the region
                            region = self.service.regions[region_name](created, stage, direction, timeframe)

                            if expiry:
                                region.set_expiry(expiry)

                            # and defined the parameters
                            region.init(data)

                            if region.check():
                                # append the region to the strategy trader
                                strategy_trader.add_region(region)
                            else:
                                results['error'] = True
                                results['messages'].append("Region checking error %s" % (region_name,))

                        except Exception as e:
                            results['error'] = True
                            results['messages'].append(repr(e))
                    else:
                        results['error'] = True
                        results['messages'].append("Unsupported region %s" % (region_name,))

            elif action == "del-region":
                try:
                    region_id = int(data.get('region-id', -1))
                except Exception:
                    results['error'] = True
                    results['messages'].append("Invalid region identifier format")

                if region_id >= 0:
                    if not strategy_trader.remove_region(region_id):
                        results['messages'].append("Invalid region identifier")

            elif action == 'add-alert':
                alert_name = data.get('alert', "")

                try:
                    created = float(data.get('created', 0.0))
                    expiry = float(data.get('expiry', 0.0))
                    countdown = int(data.get('countdown', -1))
                    timeframe = 0

                    if 'timeframe' in data:
                        if type(data['timeframe']) is str:
                            timeframe = timeframe_from_str(data['timeframe'])
                        elif type(data['timeframe']) in (float, int):
                            timeframe = data['timeframe']

                except ValueError:
                    results['error'] = True
                    results['messages'].append("Invalid parameters")

                if not results['error']:
                    if alert_name in self.service.alerts:
                        try:
                            # instanciate the alert
                            alert = self.service.alerts[alert_name](created, timeframe)
                            alert.set_countdown(countdown)

                            if expiry:
                                alert.set_expiry(expiry)                         

                            # and defined the parameters
                            alert.init(data)

                            if alert.check():
                                # append the alert to the strategy trader
                                strategy_trader.add_alert(alert)
                            else:
                                results['error'] = True
                                results['messages'].append("Alert checking error %s" % (alert_name,))

                        except Exception as e:
                            results['error'] = True
                            results['messages'].append(repr(e))
                    else:
                        results['error'] = True
                        results['messages'].append("Unsupported alert %s" % (alert_name,))

            elif action == 'del-alert':
                try:
                    alert_id = int(data.get('alert-id', -1))
                except Exception:
                    results['error'] = True
                    results['messages'].append("Invalid alert identifier format")

                if alert_id >= 0:
                    if not strategy_trader.remove_alert(alert_id):
                        results['messages'].append("Invalid alert identifier")

            elif action == "enable":
                if not strategy_trader.activity:
                    strategy_trader.set_activity(True)
                    results['messages'].append("Enabled strategy trader for market %s" % strategy_trader.instrument.market_id)
                else:
                    results['messages'].append("Already enabled strategy trader for market %s" % strategy_trader.instrument.market_id)

            elif action == "disable":
                if strategy_trader.activity:
                    strategy_trader.set_activity(False)
                    results['messages'].append("Disabled strategy trader for market %s" % strategy_trader.instrument.market_id)
                else:
                    results['messages'].append("Already disabled strategy trader for market %s" % strategy_trader.instrument.market_id)

            elif action == "set-quantity":
                quantity = 0.0
                max_factor = 1

                try:
                    quantity = float(data.get('quantity', -1))
                except Exception:
                    results['error'] = True
                    results['messages'].append("Invalid quantity")

                try:
                    max_factor = int(data.get('max-factor', 1))
                except Exception:
                    results['error'] = True
                    results['messages'].append("Invalid max factor")

                if quantity < 0.0:
                    results['error'] = True
                    results['messages'].append("Quantity must be greater than zero")

                if max_factor <= 0:
                    results['error'] = True
                    results['messages'].append("Max factor must be greater than zero")

                if quantity > 0.0 and strategy_trader.instrument.trade_quantity != quantity:
                    strategy_trader.instrument.trade_quantity = quantity
                    results['messages'].append("Modified trade quantity for %s to %s" % (strategy_trader.instrument.market_id, quantity))

                if max_factor > 0 and strategy_trader.instrument.trade_max_factor != max_factor:
                    strategy_trader.instrument.trade_max_factor = max_factor
                    results['messages'].append("Modified trade quantity max factor for %s to %s" % (strategy_trader.instrument.market_id, max_factor))

            else:
                results['error'] = True
                results['messages'].append("Invalid action")

        return results

    def cmd_strategy_trader_info(self, strategy_trader, data):
        """
        Get strategy-trader info or specific element if detail defined.
        """        
        results = {
            'messages': [],
            'error': False
        }

        detail = data.get('detail', "")
        region_id = -1

        if detail == "region":
            try:
                region_id = int(data.get('region-id'))
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid region identifier")

        if results['error']:
            return results

        trade = None

        with strategy_trader._mutex:
            if detail == "region":
                if region_id >= 0:
                    region = None

                    for r in strategy_trader.regions:
                        if r.id == region_id:
                            region = r
                            break

                    if region:
                        results['messages'].append("Stragegy trader %s region details:" % strategy_trader.instrument.market_id)
                        results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
                    else:
                        results['error'] = True
                        results['messages'].append("Invalid region identifier %i" % region_id)

                else:
                    results['messages'].append("Stragegy trader %s, list %i regions:" % (strategy_trader.instrument.market_id, len(strategy_trader.regions)))

                    for region in strategy_trader.regions:
                        results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))

            elif detail == "alert":
                # @todo
                pass

            elif detail == "status":
                # status
                results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

            elif not detail or detail == "details":
                # no specific detail
                results['messages'].append("Stragegy trader %s details:" % strategy_trader.instrument.market_id)

                # status
                results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

                # quantity
                results['messages'].append("Trade quantity : %s, max factor is x%s, mode is %s" % (
                    strategy_trader.instrument.trade_quantity,
                    strategy_trader.instrument.trade_max_factor,
                    strategy_trader.instrument.trade_quantity_mode_to_str()
                ))

                # regions
                results['messages'].append("List %i regions:" % len(strategy_trader.regions))

                for region in strategy_trader.regions:
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
            else:
                results['error'] = True
                results['messages'].append("Invalid detail type name %s" % detail)

        return results

    def cmd_trader_info(self, data):
        # info on the strategy
        if 'market-id' in data:
            with self._mutex:
                strategy_trader = self._strategy_traders.get(data['market-id'])
                if strategy_trader:
                    Terminal.inst().message("Market %s of strategy %s identified by \\2%s\\0 is %s. Trade quantity is %s x%s" % (
                        data['market-id'], self.name, self.identifier, "active" if strategy_trader.activity else "paused",
                            strategy_trader.instrument.trade_quantity, strategy_trader.instrument.trade_max_factor),
                            view='content')
        else:
            Terminal.inst().message("Strategy %s is identified by \\2%s\\0" % (self.name, self.identifier), view='content')

            enabled = []
            disabled = []

            with self._mutex:
                for k, strategy_trader in self._strategy_traders.items():
                    if strategy_trader.activity:
                        enabled.append(k)
                    else:
                        disabled.append(k)

            if enabled:
                enabled = [e if i%10 else e+'\n' for i, e in enumerate(enabled)]
                Terminal.inst().message("Enabled instruments (%i): %s" % (len(enabled), " ".join(enabled)), view='content')

            if disabled:
                disabled = [e if i%10 else e+'\n' for i, e in enumerate(disabled)]
                Terminal.inst().message("Disabled instruments (%i): %s" % (len(disabled), " ".join(disabled)), view='content')

    def cmd_strategy_trader_stream(self, strategy_trader, data):
        """
        Stream subscribe/unsubscribe to a market.
        """
        results = {
            'messages': [],
            'error': False
        }      

        timeframe = data.get('timeframe', None)
        action = data.get('action', "")
        typename = data.get('type', "")

        if action == "subscribe":
            if typename == "chart":
                strategy_trader.subscribe_stream(timeframe_from_str(timeframe))
                results['messages'].append("Subscribed for stream %s %s %s" % (self.identifier, strategy_trader.instrument.market_id, timeframe or "default"))
            elif typename == "info":
                strategy_trader.subscribe_info()
                results['messages'].append("Subscribed for stream info %s %s" % (self.identifier, strategy_trader.instrument.market_id))
            else:
                # unsupported type
                results['error'] = True
                results['messages'].append("Unsupported stream %s for trader %s" % (typename, strategy_trader.instrument.market_id))

        elif action == "unsubscribe":
            if typename == "chart":            
                strategy_trader.unsubscribe_stream(timeframe_from_str(timeframe))
                results['messages'].append("Unsubscribed from stream %s %s %s" % (self.identifier, strategy_trader.instrument.market_id, timeframe or "any"))
            elif typename == "info":
                strategy_trader.unsubscribe_info()
                results['messages'].append("Unsubscribed from stream info %s %s" % (self.identifier, strategy_trader.instrument.market_id))
            else:
                # unsupported type
                results['error'] = True
                results['messages'].append("Unsupported stream %s for trader %s" % (typename, strategy_trader.instrument.market_id))

        else:
             # unsupported action
            results['error'] = True
            results['messages'].append("Unsupported stream action %s for trader %s" % (action, strategy_trader.instrument.market_id))

        return results

    #
    # static
    #

    @staticmethod
    def parse_parameters(parameters):
        def convert(param, key):
            param.setdefault(key, None)

            if isinstance(param[key], str):
                # convert timeframe code to float in second
                param[key] = timeframe_from_str(param[key])
            elif not isinstance(param[key], (int, float)):
                param[key] = None

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

            parameters.setdefault('timeframe', None)
            
            parameters.setdefault('update-at-close', True)
            parameters.setdefault('signal-at-close', True)

            convert(timeframe, 'timeframe')

        return parameters
