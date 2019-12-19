# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy interface

import os
import threading
import time
import collections

from datetime import datetime

from terminal.terminal import Terminal, Color
from terminal import charmap

from common.runnable import Runnable
from monitor.streamable import Streamable, StreamMemberFloat, StreamMemberBool
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


class Strategy(Runnable):
    """
    Strategy/appliance base class.

    A strategy is the implementation, an the appliance is an instance of a strategy.
    Then when speaking of appliance it always refers to a contextual instance of a strategy,
    and when speaking of strategy it refers to the algorithm, the model, the implementation.

    @todo Move Each COMMAND_ to command/ and have a registry
    """

    MAX_SIGNALS = 2000   # max size of the signals messages queue before ignore some market data (tick, ohlc)

    COMMAND_INFO = 1

    COMMAND_TRADE_ENTRY = 10    # manually create a new trade
    COMMAND_TRADE_MODIFY = 11   # modify an existing trade
    COMMAND_TRADE_EXIT = 12     # exit (or eventually cancel if not again filled) an existing trade
    COMMAND_TRADE_INFO = 13     # get and display manual trade info (such as listing operations)
    COMMAND_TRADE_ASSIGN = 14   # manually assign a quantity to a new trade
    COMMAND_TRADE_CLEAN = 15    # remove/clean an existing trade without filling the remaining quantity or in case of management issue

    COMMAND_TRADER_MODIFY = 20
    COMMAND_TRADER_INFO = 21
    COMMAND_TRADER_CHART = 22
    COMMAND_TRADER_STREAM = 23

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
        self._condition = threading.Condition()

        if options.get('trader'):
            trader_conf = options['trader']
            if trader_conf.get('name'):
                self._trader_conf = trader_conf

        for watcher_conf in options.get('watcher', []):
            if watcher_conf.get('name'):
                self._watchers_conf[watcher_conf['name']] = watcher_conf

                # retrieve the watcher instance
                watcher = self._watcher_service.watcher(watcher_conf['name'])
                if watcher is None:
                    logger.error("Watcher %s not found during strategy __init__" % watcher_conf['name'])

        self.setup_streaming()

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
        """Unique appliance identifier"""
        return self._identifier

    def set_identifier(self, identifier):
        """Unique appliance identifier"""
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

    # def notify_trade_update(self, timestamp, trade, strategy_trader):
    #     """
    #     Notify a strategy trade update to the user. It must be called by the strategy-trader.
    #     """
    #     if trade:
    #         signal_data = trade.dumps_notify_update(timestamp, strategy_trader)
    #         self.service.notify(Signal.SIGNAL_STRATEGY_TRADE_UPDATE, self._name, signal_data)

    def setup_streaming(self):
        self._streamable = Streamable(self.service.monitor_service, Streamable.STREAM_STRATEGY, "status", self.identifier)

        self._streamable.add_member(StreamMemberFloat('cpu-load'))

        self._last_call_ts = 0.0

    def stream(self):
        pass

    def stream_call(self):
        """
        Process the call for each strategy instrument.
        """
        now = time.time()

        # once per second
        if now - self._last_call_ts >= 1.0:
            self._streamable.member('cpu-load').update(self._cpu_load)
            self._streamable.push()

            for k, strategy_trader in self._strategy_traders.items():
                strategy_trader.stream_call()

            self._last_call_ts = now

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
        Terminal.inst().message("Running appliance %s - %s..." % (self._name, self._identifier), view='content')

        # watcher can be already ready in some cases, try it now
        if self.check_watchers() and not self._preset:
            self.preset()

    def post_run(self):
        Terminal.inst().message("Joining appliance %s - %s..." % (self._name, self._identifier), view='content')

    def post_update(self):
        # load of the strategy
        self._cpu_load = len(self._signals) / float(Strategy.MAX_SIGNALS)

        # strategy must consume its signal else there is first a warning, and then some market data could be ignored
        if len(self._signals) > Strategy.MAX_SIGNALS:
            Terminal.inst().warning("Appliance %s has more than %s waiting signals, some market data could be ignored !" % (
                self.name, Strategy.MAX_SIGNALS), view='debug')

        # stream call
        with self._mutex:
            self.stream()
            self.stream_call()

    def ping(self, timeout):
        if self._condition.acquire(timeout=timeout):
            self._ping = (0, None, True)
            self._condition.notify()
            self._condition.release()
        else:
            Terminal.inst().action("Unable to join appliance %s - %s for %s seconds" % (self._name, self._identifier, timeout,), view='content')

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
            # display appliance activity
            Terminal.inst().action("Appliance worker %s - %s is alive %s" % (self._name, self._identifier, msg), view='content')

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
        self._trader = self.trader_service.trader(self._trader_conf['name'])

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
                        instrument.leverage = mapped_instrument.get('leverage', 1.0)

                        # if self.service.backtesting:
                        #     # no have udpate of this value, to implication to have it
                        #     # instrument.base_exchange_rate = 1.0
                        #     # instrument.contract_size = 1.0
                        #     # instrument.value_per_pip = 1.0

                        market = self._trader.market(symbol)
                        if market:
                            # synchronize initial market data into the instrument, only works in live
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

                        self._instruments[mapped_symbol] = instrument

                        # and create the strategy-trader analyser per instrument
                        strategy_trader = self.create_trader(instrument)
                        if strategy_trader:
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

    def feeder(self, market_id):
        return self._feeders.get(market_id)

    def add_feeder(self, feeder):
        if feeder is None:
            return

        with self._mutex:
            if feeder.market_id in self._feeders:
                raise ValueError("Already defined feeder %s for strategy %s !" % (self.name, feeder.market_id))

            self._feeders[feeder.market_id] = feeder

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
            while not len(self._signals) and self._running and not self._ping:
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
                            trader = self.trader_service.trader(self._trader_conf['name'])
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
                                strategy_trader.loads(data[2], data[3])

            elif signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                    # interest in tick data
                    strategy_trader = self._strategy_traders.get(signal.data[0])
                    if strategy_trader:
                        # add the new candle to the instrument in live mode
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
                                strategy_trader.instrument.add_tick(signal.data[1])

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
                                strategy_trader.instrument.add_candle(signal.data[2])

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

            count += 1
            if count > 10:
                # no more than 10 signals per loop, allow aggregate fast ticks, and don't block the processing
                break

        # only for normal processing
        if not self.service.backtesting:
            if do_update:
                if len(self._strategy_traders) >= 1:
                    for strategy_trader in do_update:
                        if strategy_trader.instrument.ready():
                            # parallelize jobs on workers
                            self.service.worker_pool.add_job(None, (self.update_strategy, (strategy_trader,)))
                else:
                    # no parallelisation below 2 instruments
                    for strategy_trader in do_update:
                        if strategy_trader.instrument.ready():
                            self.update_strategy(strategy_trader)
        else:
            # process one more backtest step
            with self._mutex:
                next_bt_upd = self._next_backtest_update
                self._next_backtest_update = None

            if next_bt_upd:
                self.backtest_update(next_bt_upd[0], next_bt_upd[1])

        return True

    def bootstrap(self, strategy_trader):
        if strategy_trader._bootstraping == 2:
            # in progress
            return

        instrument = strategy_trader.instrument

        # bootstraping in progress, avoid live until complete
        strategy_trader._bootstraping = 2

        # captures all initials candles
        initial_candles = {}

        # compute the begining timestamp
        next_timestamp = self.timestamp

        for tf, sub in strategy_trader.timeframes.items():
            candles = instrument.candles(tf)
            initial_candles[tf] = candles

            # reset, distribute one at time
            instrument._candles[tf] = []

            if candles:
                # get the nearest next candle
                next_timestamp = min(next_timestamp, candles[0].timestamp + sub.depth*sub.timeframe)

        logger.debug("%s bootstrap begin at %s, now is %s" % (instrument.market_id, next_timestamp, self.timestamp))

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

        # bootstraping done, can now branch to live
        strategy_trader._bootstraping = 0
        logger.debug("%s bootstraping done" % instrument.market_id)

    def update_strategy(self, strategy_trader):
        """
        Override this method to compute a strategy step per instrument.
        Default implementation supports bootstrapping.
        @param tf Smallest unit of time processed.
        """
        if strategy_trader:
            # bootstrap using preloaded data history, then live
            if strategy_trader._bootstraping:
                self.bootstrap(strategy_trader)
            else:
                # and process instrument update
                redo = strategy_trader.process(self.timestamp)
                # if redo:
                #     # an update occured during processing, add a new job
                #     self.service.worker_pool.add_job(None, (self.update_strategy, (strategy_trader,)))

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

    def backtest_update(self, timestamp, total_ts):
        """
        Process the backtesting update, for any instrument feeds candles to instruments and does the necessary updates.
        Override only if necessary. This default implementation should suffise.
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

        return self._running and self._preset and self._prefetched

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

    def setup_live(self):
        """
        Override this method to implement your live strategy data setup.
        Do it here dataset preload and other stuff before update be called.
        """

        # load the strategy-traders and traders for this appliance/account
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
            results = func(strategy_trader, data)

            if results:
                if results['error']:
                    Terminal.inst().info(results['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in results['messages']:
                    Terminal.inst().message(message, view='content')

    def strategy_trader_command(self, label, data, func):
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        strategy_trader = self._strategy_traders.get(market_id)
        if strategy_trader:
            Terminal.inst().notice("Strategy trader %s for strategy %s - %s %s" % (label, self.name, self.identifier, market_id), view='content')

            # retrieve the trade and apply the modification
            results = func(strategy_trader, data)

            if results:
                if results['error']:
                    Terminal.inst().info(results['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in results['messages']:
                    Terminal.inst().message(message, view='content')

    def command(self, command_type, data):
        """
        Some parts are mutexed some others are not.
        @todo some command are only display, so could be moved to a displayer, and command could only return an object
        """
        if command_type == Strategy.COMMAND_INFO:
            self.cmd_trader_info(data)
        elif command_type == Strategy.COMMAND_TRADE_ENTRY:
            self.trade_command("entry", data, self.cmd_trade_entry)
        elif command_type == Strategy.COMMAND_TRADE_EXIT:
            self.trade_command("exit", data, self.cmd_trade_exit)
        elif command_type == Strategy.COMMAND_TRADE_CLEAN:
            self.trade_command("clean", data, self.cmd_trade_clean)
        elif command_type == Strategy.COMMAND_TRADE_MODIFY:
            self.trade_command("modify", data, self.cmd_trade_modify)
        elif command_type == Strategy.COMMAND_TRADE_INFO:
            self.trade_command("info", data, self.cmd_trade_info)
        elif command_type == Strategy.COMMAND_TRADE_ASSIGN:
            self.trade_command("assign", data, self.cmd_trade_assign)
        elif command_type == Strategy.COMMAND_TRADER_MODIFY:
            self.strategy_trader_command("info", data, self.cmd_strategy_trader_modify)
        elif command_type == Strategy.COMMAND_TRADER_INFO:
            self.strategy_trader_command("info", data, self.cmd_strategy_trader_info)
        elif command_type == Strategy.COMMAND_TRADER_CHART:
            self.strategy_trader_command("chart", data, self.cmd_strategy_trader_chart)
        elif command_type == Strategy.COMMAND_TRADER_STREAM:
            self.strategy_trader_command("stream", data, self.cmd_strategy_trader_stream)

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

            if len(self._signals) > Strategy.MAX_SIGNALS:
                # if strategy message queue saturate its mostly because of market data too many update
                logger.warning("More than %s signals in strategy %s - %s" % (Strategy.MAX_SIGNALS, self.name, self.identifier))

                # from the watcher (in live) so then ignore some of those message, the others ones are too important to be ignored
                if signal.signal_type in (Signal.SIGNAL_TICK_DATA, Signal.SIGNAL_MARKET_DATA):
                    return

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
    # display views
    #

    def get_all_active_trades(self):
        """
        Generate and return an array of all the actives trades :
            symbol: str market identifier
            id: int trade identifier
            eot: float first entry open UTC timestamp
            xot: float first exit open UTC timestamp
            freot: float first realized trade in entry UTC timestamp
            frxot: float firest realized trade in exit UTC timestamp
            lreot: float last realized trade in entry UTC timestamp
            lrxot: float last realized trade in exit UTC timestamp
            d: str 'long' or 'short'
            l: str formatted order price
            tp: str formatted take-profit price
            sl: str formatted stop-loss price
            rate: float profit/loss rate
            tfs: list of str timeframe generating the trade
            b: best hit price
            w: worst hit price
            bt: best hit price timestamp
            wt: worst hit price timestamp
            q: ordered qty
            e: executed entry qty
            x: executed exit qty
            aep: average entry price
            axp: average exit price
            label: trade label
            upnl: trade unrealized profit loss
            pnlcur: trade profit loss currency
        """
        results = []
        trader = self.trader()

        for k, strategy_trader in self._strategy_traders.items():
            with strategy_trader._mutex:
                for trade in strategy_trader.trades:
                    profit_loss = trade.estimate_profit_loss(strategy_trader.instrument)

                    results.append({
                        'mid': strategy_trader.instrument.market_id,
                        'sym': strategy_trader.instrument.symbol,
                        'id': trade.id,
                        'eot': trade.entry_open_time,
                        'xot': trade.exit_open_time,
                        'freot': trade.first_realized_entry_time,
                        'frxot': trade.first_realized_exit_time,
                        'lreot': trade.last_realized_entry_time,
                        'lrxot': trade.last_realized_exit_time,
                        'd': trade.direction_to_str(),
                        'l': strategy_trader.instrument.format_price(trade.order_price),
                        'aep': strategy_trader.instrument.format_price(trade.entry_price),
                        'axp': strategy_trader.instrument.format_price(trade.exit_price),
                        'q': strategy_trader.instrument.format_quantity(trade.order_quantity),
                        'e': strategy_trader.instrument.format_quantity(trade.exec_entry_qty),
                        'x': strategy_trader.instrument.format_quantity(trade.exec_exit_qty),
                        'tp': strategy_trader.instrument.format_price(trade.take_profit),
                        'sl': strategy_trader.instrument.format_price(trade.stop_loss),
                        'pl': profit_loss,
                        'tf': timeframe_to_str(trade.timeframe),
                        's': trade.state_to_str(),
                        'b': strategy_trader.instrument.format_price(trade.best_price()),
                        'w': strategy_trader.instrument.format_price(trade.worst_price()),
                        'bt': trade.best_price_timestamp(),
                        'wt': trade.worst_price_timestamp(),
                        'label': trade.label,
                        'upnl': strategy_trader.instrument.format_price(trade.unrealized_profit_loss),
                        'pnlcur': trade.profit_loss_currency
                    })

        return results

    def get_agg_trades(self):
        """
        Generate and return an array of :
            mid: str name of the market id
            sym: str name of the symbol
            pl: flaot profit/loss rate
            perf: perf
            worst: worst
            best: best
            success: success
            failed: failed
            roe: roe
        """
        results = []
        trader = self.trader()

        for k, strategy_trader in self._strategy_traders.items():
            pl = 0.0
            perf = 0.0

            with strategy_trader._mutex:
                perf = strategy_trader._stats['perf']
                best = strategy_trader._stats['best']
                worst = strategy_trader._stats['worst']

                success = len(strategy_trader._stats['success'])
                failed = len(strategy_trader._stats['failed'])
                roe = len(strategy_trader._stats['roe'])

                mid = strategy_trader.instrument.market_id
                sym = strategy_trader.instrument.symbol

                num = len(strategy_trader.trades)

                for trade in strategy_trader.trades:
                    pl += trade.estimate_profit_loss(strategy_trader.instrument)

            if pl != 0.0 or num > 0 or success > 0 or failed > 0 or roe > 0:
                results.append({
                    'mid': mid,
                    'sym': sym,
                    'pl': pl,
                    'perf': perf,
                    'best': best,
                    'worst': worst,
                    'success': success,
                    'failed': failed,
                    'roe': roe
                })

        return results

    def get_stats(self):
        """
        Generate and return an array of dict with the form :
            symbol: str name of the symbol/market
            pl: float current profit/loss rate 0 based
            perf: float total sum of profit/loss rate 0 based
            trades: list of dict of actives trades
                id: int trade identifier
                ts: float entry UTC timestamp
                d: str 'long' or 'short'
                l: str formatted order price
                aep: str formatted entry price
                axp: str formatted average exit price
                tp: str formatted take-profit price
                sl: str formatted stop-loss price
                pl: float profit/loss rate
                tfs: list of str timeframe generating the trade
                b: best hit price
                w: worst hit price
                bt: best hit price timestamp
                wt: worst hit price timestamp
                q: ordered qty
                e: executed entry qty
                x: executed exit qty
                label: trade label
                upnl: trade unrealized profit loss
                pnlcur: trade profit loss currency
        """
        results = []

        trader = self.trader()

        for k, strategy_trader in self._strategy_traders.items():
            profit_loss = 0.0
            trades = []
            perf = 0.0

            with strategy_trader._mutex:
                perf = strategy_trader._stats['perf']
                best = strategy_trader._stats['best']
                worst = strategy_trader._stats['worst']

                success = len(strategy_trader._stats['success'])
                failed = len(strategy_trader._stats['failed'])
                roe = len(strategy_trader._stats['roe'])

                market = trader.market(strategy_trader.instrument.market_id) if trader else None
                for trade in strategy_trader.trades:
                    trade_pl = trade.estimate_profit_loss(strategy_trader.instrument)

                    trades.append({
                        'id': trade.id,
                        'eot': trade.entry_open_time,
                        'd': trade.direction_to_str(),
                        'l': strategy_trader.instrument.format_price(trade.order_price),
                        'aep': strategy_trader.instrument.format_price(trade.entry_price),
                        'axp': strategy_trader.instrument.format_price(trade.exit_price),
                        'q': strategy_trader.instrument.format_quantity(trade.order_quantity),
                        'e': strategy_trader.instrument.format_quantity(trade.exec_entry_qty),
                        'x': strategy_trader.instrument.format_quantity(trade.exec_exit_qty),
                        'tp': strategy_trader.instrument.format_price(trade.take_profit),
                        'sl': strategy_trader.instrument.format_price(trade.stop_loss),
                        'pl': trade_pl,
                        'tf': timeframe_to_str(trade.timeframe),
                        's': trade.state_to_str(),
                        'b': strategy_trader.instrument.format_price(trade.best_price()),
                        'w': strategy_trader.instrument.format_price(trade.worst_price()),
                        'bt': trade.best_price_timestamp(),
                        'wt': trade.worst_price_timestamp(),
                        'label': trade.label,
                        'upnl': "%.f" % trade.unrealized_profit_loss,
                        'pnlcur': trade.profit_loss_currency
                    })

                    profit_loss += trade_pl

            results.append({
                'mid': strategy_trader.instrument.market_id,
                'sym': strategy_trader.instrument.symbol,
                'pl': profit_loss,
                'perf': perf,
                'trades': trades,
                'best': best,
                'worst': worst,
                'success': success,
                'failed': failed,
                'roe': roe
            })

        return results

    def get_closed_trades(self):
        """
        Like as get_stats but only return the array of the trade, and complete history.
        """
        results = []

        with self._mutex:
            try:
                for k, strategy_trader in self._strategy_traders.items():
                    with strategy_trader._mutex:
                        def append_trade(market_id, symbol, trades, trade):
                            trades.append({
                                'mid': market_id,
                                'sym': symbol,
                                'id': trade['id'],
                                'eot': trade['eot'],
                                'xot': trade['xot'],
                                'l': trade['l'],
                                'lreot': trade['lreot'],
                                'lrxot': trade['lrxot'],
                                'freot': trade['freot'],
                                'frxot': trade['frxot'],
                                'd': trade['d'],
                                'aep': trade['aep'],
                                'axp': trade['axp'],
                                'q': trade['q'],
                                'e': trade['e'],
                                'x': trade['e'],
                                'tp': trade['tp'],
                                'sl': trade['sl'],
                                'pl': trade['pl'],
                                'tf': trade['tf'],
                                's': trade['s'],
                                'c': trade['c'],
                                'b': trade['b'],
                                'bt': trade['bt'],
                                'w': trade['w'],
                                'wt': trade['wt'],
                                'label': trade['label'],
                                'fees': trade['fees'],
                                'rpnl': trade['rpnl'],
                                'pnlcur': trade['pnlcur']
                            })

                        for trade in strategy_trader._stats['success']:
                            append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

                        for trade in strategy_trader._stats['failed']:
                            append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

                        for trade in strategy_trader._stats['roe']:
                            append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

            except Exception as e:
                error_logger.error(repr(e))

        return results

    #
    # display formatters
    #

    def agg_trades_stats_table(self, style='', offset=None, limit=None, col_ofs=None, summ=True):
        """
        Returns a table of any aggreged active and closes trades.
        """
        columns = ('Market', 'P/L(%)', 'Total(%)', 'Best(%)', 'Worst(%)', 'Success', 'Failed', 'ROE')
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            agg_trades = self.get_agg_trades()
            total_size = (len(columns), len(agg_trades) + (1 if summ else 0))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(agg_trades) + (1 if summ else 0)

            limit = offset + limit

            agg_trades.sort(key=lambda x: x['mid'])

            pl_sum = 0.0
            perf_sum = 0.0
            best_sum = 0.0
            worst_sum = 0.0
            success_sum = 0
            failed_sum = 0
            roe_sum = 0

            # total summ before offset:limit
            if summ:
                for t in agg_trades:
                    pl_sum += t['pl']
                    perf_sum += t['perf']
                    best_sum = max(best_sum, t['best'])
                    worst_sum = min(worst_sum, t['worst'])
                    success_sum += t['success']
                    failed_sum += t['failed']
                    roe_sum += t['roe']

            agg_trades = agg_trades[offset:limit]

            for t in agg_trades:
                cr = Color.colorize_updn("%.2f" % (t['pl']*100.0), 0.0, t['pl'], style=style)
                cp = Color.colorize_updn("%.2f" % (t['perf']*100.0), 0.0, t['perf'], style=style)

                row = (
                    t['mid'],
                    cr,
                    cp,
                    "%.2f" % (t['best']*100.0),
                    "%.2f" % (t['worst']*100.0),
                    t['success'],
                    t['failed'],
                    t['roe']
                )

                data.append(row[col_ofs:])

            #
            # sum
            #

            if summ:
                cpl_sum = Color.colorize_updn("%.2f" % (pl_sum*100.0), 0.0, pl_sum, style=style)
                cperf_sum = Color.colorize_updn("%.2f" % (perf_sum*100.0), 0.0, perf_sum, style=style)

                row = (
                    'Total',
                    cpl_sum,
                    cperf_sum,
                    "%.2f" % (best_sum*100.0),
                    "%.2f" % (worst_sum*100.0),
                    success_sum,
                    failed_sum,
                    roe_sum)

                data.append(row[col_ofs:])

        return columns[col_ofs:], data, total_size

    def trades_stats_table(self, style='', offset=None, limit=None, col_ofs=None, quantities=False, percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
        """
        Returns a table of any active trades.
        """
        columns = ['Market', '#', charmap.ARROWUPDN, 'P/L(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'UPNL']

        if quantities:
            columns += ['Qty', 'Entry Q', 'Exit Q', 'Status']

        columns = tuple(columns)
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            trades = self.get_all_active_trades()
            total_size = (len(columns), len(trades))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(trades)

            limit = offset + limit

            trades.sort(key=lambda x: x['eot'])
            trades = trades[offset:limit]

            for t in trades:
                direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

                aep = float(t['aep'])
                best = float(t['b'])
                worst = float(t['w'])
                op = float(t['l'])
                sl = float(t['sl'])
                tp = float(t['tp'])

                if t['pl'] < 0 and ((t['d'] == 'long' and best > aep) or (t['d'] == 'short' and best < aep)):
                    # has been profitable but loss
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.ORANGE, style=style)
                elif t['pl'] < 0:  # loss
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
                elif t['pl'] > 0:  # profit
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
                else:  # equity
                    cr = "0.0"

                if t['d'] == 'long' and aep > 0 and best > 0 and worst > 0:
                    bpct = (best - aep) / aep
                    wpct = (worst - aep) / aep
                elif t['d'] == 'short' and aep > 0 and best > 0 and worst > 0:
                    bpct = (aep - best) / aep
                    wpct = (aep - worst) / aep
                else:
                    bpct = 0
                    wpct = 0

                if t['d'] == 'long' and (aep or op):
                    slpct = (sl - (aep or op)) / (aep or op)
                    tppct = (tp - (aep or op)) / (aep or op)
                elif t['d'] == 'short' and (aep or op):
                    slpct = ((aep or op) - sl) / (aep or op)
                    tppct = ((aep or op) - tp) / (aep or op)
                else:
                    slpct = 0
                    tppct = 0

                row = [
                    t['mid'],
                    t['id'],
                    direction,
                    cr,
                    t['l'],
                    "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                    "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                    "%s (%.2f)" % (t['b'], bpct * 100) if percents else t['b'],
                    "%s (%.2f)" % (t['w'], wpct * 100) if percents else t['w'],
                    t['tf'],
                    datetime.fromtimestamp(t['eot']).strftime(datetime_format) if t['eot'] > 0 else "",
                    datetime.fromtimestamp(t['freot']).strftime(datetime_format) if t['freot'] > 0 else "",
                    t['aep'],
                    datetime.fromtimestamp(t['lrxot']).strftime(datetime_format) if t['lrxot'] > 0 else "",
                    t['axp'],
                    t['label'],
                    "%s%s" % (t['upnl'], t['pnlcur'])
                ]

                if quantities:
                    row.append(t['q'])
                    row.append(t['e'])
                    row.append(t['x'])
                    row.append(t['s'].capitalize())

                data.append(row[col_ofs:])

        return columns[col_ofs:], data, total_size

    def closed_trades_stats_table(self, style='', offset=None, limit=None, col_ofs=None, quantities=False, percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
        """
        Returns a table of any closed trades.
        """
        columns = ['Market', '#', charmap.ARROWUPDN, 'P/L(%)', 'Fees(%)', 'OP', 'SL', 'TP', 'Best', 'Worst', 'TF', 'Signal date', 'Entry date', 'Avg EP', 'Exit date', 'Avg XP', 'Label', 'RPNL']

        if quantities:
            columns += ['Qty', 'Entry Q', 'Exit Q', 'Status']

        columns = tuple(columns)
        total_size = (len(columns), 0)
        data = []
        
        with self._mutex:
            closed_trades = self.get_closed_trades()
            total_size = (len(columns), len(closed_trades))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(closed_trades)

            limit = offset + limit

            closed_trades.sort(key=lambda x: -x['lrxot'])
            closed_trades = closed_trades[offset:limit]

            for t in closed_trades:
                direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

                # @todo direction
                if t['pl'] < 0 and float(t['b']) > float(t['aep']):  # has been profitable but loss
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.ORANGE, style=style)
                elif t['pl'] < 0:  # loss
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
                elif t['pl'] > 0:  # profit
                    cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
                else:
                    cr = "0.0"

                aep = float(t['aep'])
                sl = float(t['sl'])
                tp = float(t['tp'])

                # color TP in green if hitted, similarely in red for SL
                # @todo not really true, could store the exit reason in trade stats
                if t['d'] == "long":
                    _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) >= tp, style=style, true=Color.GREEN)
                    _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) <= sl, style=style, true=Color.RED)
                    slpct = (sl - aep) / aep
                    tppct = (tp - aep) / aep
                else:
                    _tp = Color.colorize_cond(t['tp'], tp > 0 and float(t['axp']) <= tp, style=style, true=Color.GREEN)
                    _sl = Color.colorize_cond(t['sl'], sl > 0 and float(t['axp']) >= sl, style=style, true=Color.RED)
                    slpct = (aep - sl) / aep
                    tppct = (aep - tp) / aep

                if t['d'] == 'long':
                    bpct = (float(t['b']) - aep) / aep
                    wpct = (float(t['w']) - aep) / aep
                elif t['d'] == 'short':
                    bpct = (aep - float(t['b'])) / aep
                    wpct = (aep - float(t['w'])) / aep

                row = [
                    t['mid'],
                    t['id'],
                    direction,
                    cr,
                    "%.2f%%" % (t['fees'] * 100),
                    t['l'],
                    "%s (%.2f)" % (_sl, slpct * 100) if percents else _sl,
                    "%s (%.2f)" % (_tp, tppct * 100) if percents else _tp,
                    "%s (%.2f)" % (t['b'], bpct * 100) if percents else t['b'],
                    "%s (%.2f)" % (t['w'], wpct * 100) if percents else t['w'],
                    t['tf'],
                    datetime.fromtimestamp(t['eot']).strftime(datetime_format),
                    datetime.fromtimestamp(t['freot']).strftime(datetime_format),
                    t['aep'],
                    datetime.fromtimestamp(t['lrxot']).strftime(datetime_format),
                    t['axp'],
                    t['label'],
                    "%s%s" % (t['rpnl'], t['pnlcur'])
                ]

                if quantities:
                    row.append(t['q'])
                    row.append(t['e'])
                    row.append(t['x'])
                    row.append(t['s'].capitalize())

                data.append(row[col_ofs:])

        return columns[col_ofs:], data, total_size

    #
    # trade commands
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
        timeframe = data.get('timeframe', Instrument.TF_4HOUR)
        leverage = data.get('leverage', 1.0)
        hedging = data.get('hedging', True)
        margin_trade = data.get('margin-trade', False)
        entry_timeout = data.get('entry-timeout', None)

        if quantity_rate <= 0.0:
            results['messages'].append("Missing or empty quantity.")
            results['error'] = True

        if method not in ('market', 'limit', 'trigger'):
            results['messages'].append("Invalid price method (market, limit, trigger).")
            results['error'] = True

        if method != 'market' and not limit_price:
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
        else:
            order_type = Order.ORDER_MARKET

        order_quantity = 0.0

        trader = self.trader()

        # need a valid price to compute the quantity
        price = limit_price or strategy_trader.instrument.open_exec_price(direction)
        trade = None

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

            if not trader.has_margin(strategy_trader.instrument.market_id, strategy_trader.instrument.trade_quantity*quantity_rate, price):
                results['error'] = True
                results['messages'].append("Not enought margin")

            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        elif strategy_trader.instrument.has_margin and strategy_trader.instrument.indivisible_position:
            trade = StrategyIndMarginTrade(timeframe)

            if not trader.has_margin(strategy_trader.instrument.market_id, strategy_trader.instrument.trade_quantity*quantity_rate, price):
                results['error'] = True
                results['messages'].append("Not enought margin")

            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        elif strategy_trader.instrument.has_margin and not strategy_trader.instrument.indivisible_position and not strategy_trader.instrument.has_position:
            trade = StrategyMarginTrade(timeframe)

            if not trader.has_margin(strategy_trader.instrument.market_id, strategy_trader.instrument.trade_quantity*quantity_rate, price):
                results['error'] = True
                results['messages'].append("Not enought margin")

            order_quantity = strategy_trader.instrument.adjust_quantity(strategy_trader.instrument.trade_quantity*quantity_rate)

        else:
            results['error'] = True
            results['messages'].append("Unsupported market type")

        if order_quantity <= 0 or order_quantity * price < strategy_trader.instrument.min_notional:
            results['error'] = True
            results['messages'].append("Min notional not reached (%s)" % strategy_trader.instrument.min_notional)

        if results['error']:
            return results

        order_price = float(strategy_trader.instrument.adjust_price(price))

        if trade:
            # user managed trade
            trade.set_user_trade()

            if entry_timeout:
                # entry timeout expiration defined
                trade.entry_timeout = entry_timeout

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            strategy_trader.add_trade(trade)

            if trade.open(trader, strategy_trader.instrument, direction, order_type, order_price, order_quantity,
                          take_profit, stop_loss, leverage=leverage, hedging=hedging):

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
                if action == 'stop-loss' and 'stop-loss' in data and type(data['stop-loss']) is float:
                    if data['stop-loss'] > 0.0:
                        if trade.has_stop_order() or data.get('force', False):
                            trade.modify_stop_loss(self.trader(), strategy_trader.instrument, data['stop-loss'])
                        else:
                            trade.sl = data['stop-loss']
                    else:
                        results['error'] = True
                        results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

                # modify TP
                elif action == 'take-profit' and 'take-profit' in data and type(data['take-profit']) is float:
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

    def cmd_strategy_trader_modify(self, strategy_trader, data):
        """
        Modify a strategy-trader region or state.
        """        
        results = {
            'messages': [],
            'error': False
        }

        action = ""
        expiry = 0
        timeframe = 0

        with strategy_trader._mutex:
            try:
                region_id = int(data.get('region-id', -1))
                action = data.get('action')
            except Exception:
                results['error'] = True
                results['messages'].append("Invalid trade identifier")

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
                    results['messages'].append("Invalid region identifier")

                if region_id >= 0:
                    if not strategy_trader.remove_region(region_id):
                        results['messages'].append("Invalid region identifier")

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

                try:
                    quantity = float(data.get('quantity', -1))
                except Exception:
                    results['error'] = True
                    results['messages'].append("Invalid quantity")

                if quantity > 0.0:
                    strategy_trader.instrument.trade_quantity = quantity
                    results['messages'].append("Modified trade quantity for %s to %s" % (strategy_trader.instrument.market_id, quantity))

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

            elif detail == "status":
                # status
                results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

            elif not detail or detail == "details":
                # no specific detail
                results['messages'].append("Stragegy trader %s details:" % strategy_trader.instrument.market_id)

                # status
                results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

                # quantity
                results['messages'].append("Trade quantity : %s" % strategy_trader.instrument.trade_quantity)

                # regions
                results['messages'].append("List %i regions:" % len(strategy_trader.regions))

                for region in strategy_trader.regions:
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
            else:
                results['error'] = True
                results['messages'].append("Invalid detail type name %s" % detail)

        return results

    def cmd_trader_info(self, data):
        # info on the appliance
        if 'market-id' in data:
            with self._mutex:
                strategy_trader = self._strategy_traders.get(data['market-id'])
                if strategy_trader:
                    Terminal.inst().message("Market %s of appliance %s identified by \\2%s\\0 is %s. Trade quantity is %s" % (
                        data['market-id'], self.name, self.identifier, "active" if strategy_trader.activity else "paused",
                            strategy_trader.instrument.trade_quantity),
                            view='content')
        else:
            Terminal.inst().message("Appliances %s is identified by \\2%s\\0" % (self.name, self.identifier), view='content')

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

    def cmd_strategy_trader_chart(self, strategy_trader, data):
        """
        Open as possible a process with chart of a specific sub-tader.
        """
        results = {
            'messages': [],
            'error': False
        }      

        monitor_url = data.get('monitor-url')
        timeframe = data.get('timeframe', 15*60)

        if results['error']:
            return results

        strategy_trader.subscribe_stream(timeframe)

        import subprocess
        p = subprocess.Popen(["python", "-m", "monitor.client.client", monitor_url[0], monitor_url[1]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.PIPE, preexec_fn=os.setsid)

        return results

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
                strategy_trader.subscribe_stream(timeframe)
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
                strategy_trader.unsubscribe_stream(timeframe)
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

        # regulars parameters (@todo lets see maybe not all)
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
        for k, timeframe in parameters['timeframes'].items():
            timeframe.setdefault('depth', 0)
            timeframe.setdefault('history', 0)

            parameters.setdefault('timeframe', None)
            
            parameters.setdefault('update-at-close', True)
            parameters.setdefault('signal-at-close', True)

            convert(timeframe, 'timeframe')

        return parameters
