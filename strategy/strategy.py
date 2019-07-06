# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy interface

import threading
import time
import collections

from datetime import datetime

from terminal.terminal import Terminal
from common.runnable import Runnable
from monitor.streamable import Streamable, StreamMemberFloat, StreamMemberBool
from common.utils import timeframe_to_str, timeframe_from_str

from notifier.signal import Signal
from instrument.instrument import Instrument

from watcher.watcher import Watcher

from trader.market import Market
from trader.order import Order

from strategy.strategyassettrade import StrategyAssetTrade
from strategy.strategymargintrade import StrategyMarginTrade
from strategy.strategyindmargintrade import StrategyIndMarginTrade

from tabulate import tabulate

import logging
logger = logging.getLogger('siis.strategy')


class Strategy(Runnable):
    """
    Strategy/appliance base class.

    A strategy is the implementation, an the appliance is an instance of a strategy.
    Then when speaking of appliance it always refers to a contextual instance of a strategy,
    and when speaking of strategy it refers to the algorithm, the model, the implementation.

    @todo tabulated might support columns shifting from left, and row offet to be displayed better in the terminal
        after having added the tabulated support directly to terminal (update for current trades, history trades).

    @todo Getting display data are the slow part, causing potential global latency, don't call it too often.
        Maybe a kind of event sourcing will be preferable.

    @todo Move Each COMMAND_ to command/ and have a registry
    """

    MAX_SIGNALS = 2000   # max size of the signals messages queue before ignore some market data (tick, ohlc)

    COMMAND_SHOW_STATS = 1
    COMMAND_SHOW_HISTORY = 2
    COMMAND_INFO = 3

    COMMAND_TRADE_ENTRY = 10    # manually create a new trade
    COMMAND_TRADE_MODIFY = 11   # modify an existing trade
    COMMAND_TRADE_EXIT = 12     # exit (or eventually cancel if not again filled) an existing trade
    COMMAND_TRADE_INFO = 13     # get and display manual trade info (such as listing operations)
    COMMAND_TRADE_ASSIGN = 14   # manually assign a quantity to a new trade

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

        self._parameters = Strategy.parse_parameters(Strategy.merge_parameters(default_parameters, user_parameters))

        self._preset = False       # True once instrument are setup
        self._prefetched = False   # True once strategies are ready

        self._watchers_conf = {}   # name of the followed watchers
        self._trader_conf = None   # name of the followed trader

        self._trader = None        # attached trader

        self._signals = collections.deque()  # filtered received signals

        self._instruments = {}  # mapped instruments
        self._feeders = {}      # feeders mapped by market id
        self._sub_traders = {}  # per instrument strategy data analyser

        # used during backtesting
        self._last_done_ts = 0
        self._timestamp = 0

        self._next_backtest_update = None

        self._cpu_load = 0.0   # global CPU for all the instruments managed by a strategy
        
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

    #
    # monitoring notification (@todo to be cleanup)
    #

    def notify_order(self, trade_id, direction, symbol, price, timestamp, timeframe,
            action='order', rate=None, stop_loss=None, take_profit=None):
        """
        Notify an order execution to the user. It must be called by the sub-trader.
        @param trade_id If -1 then it notify a simple signal unrelated to a trade.
        """
        signal_data = {
            'trade-id': trade_id,
            'trader-name': self._name,
            'identifier': self.identifier,
            'action': action,
            'timestamp': timestamp,
            'timeframe': timeframe,
            'direction': direction,
            'symbol': symbol,
            'price': price,
            'rate': rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit
        }

        self.service.notify(Signal.SIGNAL_STRATEGY_ENTRY_EXIT, self._name, signal_data)

    # def notify(self, notification_type, data):
    # @todo more generic notifier for any trader action on a trade or for different sort of messages
    #       but its fore few message per minute, the traders might diffuse only the strict minimum,
    #       excepted for debug/profiling mode
    #     self.service.notify(Signal.SIGNAL_STRATEGY_xxx, self._name, signal_data)

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

            for k, sub_trader in self._sub_traders.items():
                sub_trader.stream_call()

            self._last_call_ts = now

    def subscribe(self, market_id, timeframe):
        """
        Override to create a specific streamer.
        """
        if market_id not in self._instruments:
            return False

        instrument = self._instruments[market_id]
        sub_trader = self._sub_traders.get(instrument)

        if not sub_trader:
            return False

        return sub_trader.subscribe(timeframe)

    def unsubscribe(self, market_id, timeframe):
        """
        Override to delete a specific streamer.
        """
        if market_id not in self._instruments:
            return False

        instrument = self._instruments[market_id]
        sub_trader = self._sub_trader.get(instrument)

        if not sub_trader:
            return False

        return sub_trader.unsubscribe(timeframe)

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
            if watcher is None or not watcher.connected:
                return False

        return True

    def pre_run(self):
        Terminal.inst().info("Running appliance %s - %s..." % (self._name, self._identifier), view='content')

        # watcher can be already ready in some cases, try it now
        if self.check_watchers() and not self._preset:
            self.preset()

    def post_run(self):
        Terminal.inst().info("Joining appliance %s - %s..." % (self._name, self._identifier), view='content')

    def post_update(self):
        # load of the strategy
        self._cpu_load = len(self._signals) / float(Strategy.MAX_SIGNALS)

        # strategy must consume its signal else there is first a warning, and then some market data could be ignored
        if len(self._signals) > Strategy.MAX_SIGNALS:
            Terminal.inst().warning("Appliance %s has more than %s waiting signals, some market data could be ignored !" % (
                self.name, Strategy.MAX_SIGNALS), view='debug')

        # dont waste the CPU in live mode
        if not self.service.backtesting:
            time.sleep(0.0000001)  # 0.005 * max(1, self._cpu_load))

        # stream call
        self.lock()
    
        self.stream()
        self.stream_call()

        self.unlock()

    def pong(self, msg):
        # display appliance activity
        Terminal.inst().action("Appliance worker %s - %s is alive %s" % (self._name, self._identifier, msg), view='content')

    #
    # sub-traders processing
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
            strategy_symbols = watcher.matching_symbols_set(watcher_conf.get('symbols'), watcher.watched_instruments())

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

                        instrument.trader_quantity = mapped_instrument.get('size', 0)
                        instrument.leverage = mapped_instrument.get('leverage', 1)

                        self._instruments[mapped_symbol] = instrument

                        # and create the sub_trader analyser per instrument
                        strategy_trader = self.create_trader(instrument)
                        if strategy_trader:
                            self._sub_traders[instrument] = strategy_trader
                    else:
                        instrument = self._instruments.get(mapped_symbol)

                    if watcher.has_prices_and_volumes:
                        instrument.add_watcher(Watcher.WATCHER_PRICE_AND_VOLUME, watcher)

                    if watcher.has_buy_sell_signals:
                        instrument.add_watcher(Watcher.WATCHER_BUY_SELL_SIGNAL, watcher)

        self._preset = True

        # now can setup backtest or live mode
        if self.service.backtesting:
            self.setup_backtest(self.service.from_date, self.service.to_date)
        else:
            self.setup_live()

    def save(self):
        """
        For each sub-trader finalize only in live mode.
        """
        self.lock()

        if not self.service.backtesting and not self.trader().paper_mode:
            for k, sub_trader in self._sub_traders.items():
                sub_trader.save()

        self.unlock()

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
            self.lock()
            instrument = self.find_instrument(market_id)
            if instrument:
                sub_trader = self._sub_traders.get(instrument)
                if sub_trader:
                    sub_trader.set_activity(status)
            self.unlock()
        else:
            self.lock()
            for k, sub_trader in self._sub_traders.items():
                sub_trader.set_activity(status)
            self.unlock()

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
        self.lock()

        names = []

        for k, instrument in self._instruments.items():
            names.append(instrument.market_id)

            if instrument.symbol and instrument.symbol != instrument.market_id and instrument.symbol != instrument.alias:
                names.append(instrument.symbol)

            if instrument.alias and instrument.alias != instrument.market_id and instrument.alias != instrument.symbol:
                names.append(instrument.alias)

        self.unlock()

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

        self.lock()

        if feeder.market_id in self._feeders:
            self.unlock()
            raise ValueError("Already defined feeder %s for strategy %s !" % (self.name, feeder.market_id))

        self._feeders[feeder.market_id] = feeder

        self.unlock()

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
        do_update = {}
        count = 0

        while self._signals:
            signal = self._signals.popleft()

            # if source of the signal is itself then it might be for backtesting
            if signal.source == Signal.SOURCE_STRATEGY:
                if signal.signal_type == Signal.SIGNAL_MARKET_INFO_DATA:
                    # incoming market info when backtesting
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    market = signal.data[1]

                    if market:
                        # in backtesting mode set the market object to the paper trader directly
                        if self.service.backtesting:
                            trader = self.trader_service.trader(self._trader_conf['name'])
                            if trader:
                                trader.set_market(market)

                    # retrieve the feeder by the relating instrument market_id or symbol
                    feeder = self._feeders.get(instrument.market_id) or self._feeders.get(instrument.symbol)
                    if feeder:
                        # set instrument once market data are fetched
                        feeder.set_instrument(instrument)

                elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_LIST:
                    # for each trade, add the trade to the corresponding instrument sub
                    for trade in signal.data:
                        # @todo
                        pass

            elif signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                    # interest in tick data

                    # symbol mapping
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    # add the new candle to the instrument in live mode
                    if instrument.ready():
                        instrument.add_tick(signal.data[1])

                    do_update[instrument] = 0

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                    # interest in candle data

                    # symbol mapping
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    # add the new candle to the instrument in live mode
                    if instrument.ready():
                        instrument.add_candle(signal.data[1])

                    if instrument not in do_update:
                        do_update[instrument] = signal.data[1].timeframe
                    else:
                        do_update[instrument] = min(signal.data[1].timeframe, do_update[instrument])

                elif signal.signal_type == Signal.SIGNAL_TICK_DATA_BULK:
                    # incoming bulk of history ticks
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    # initials ticks loaded
                    instrument.ack_timeframe(0)

                    # insert the bulk of ticks into the instrument
                    if signal.data[1]:
                        instrument.add_tick(signal.data[1])
                        do_update[instrument] = 0

                elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA_BULK:
                    # incoming bulk of history candles
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    initial = instrument.ack_timeframe(signal.data[1])

                    # insert the bulk of candles into the instrument
                    if signal.data[2]:
                        # in live mode directly add candles to instrument
                        instrument.add_candle(signal.data[2])

                        # initials candles loaded
                        if initial:
                            sub = self._sub_traders.get(instrument)
                            if sub:
                                sub.on_received_initial_candles(signal.data[1])

                        if instrument not in do_update:
                            do_update[instrument] = signal.data[1]
                        else:
                            do_update[instrument] = min(signal.data[1], do_update[instrument])

                elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                    # update market data state
                    instrument = self.instrument(signal.data[0])
                    if instrument is None:
                        continue

                    # update instrument data
                    instrument.market_open = signal.data[1]

                    if signal.data[1]:
                        instrument.update_time = signal.data[2]
                        instrument.market_bid = signal.data[3]
                        instrument.market_ofr = signal.data[4]

                        instrument.base_exchange_rate = signal.data[5]
                        instrument.vol24h_base = signal.data[8]
                        instrument.vol24h_quote = signal.data[9]

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
                # no more than 10 signals per loop
                break

        # only for normal processing
        if not self.service.backtesting:
            if do_update:
                if len(self._instruments) >= 1:
                    # @todo might not need sync in live mode, so add any jobs directly
                    count_down = None  # self.service.worker_pool.new_count_down(len(self._instruments))

                    for instrument, tf in do_update.items():
                        if instrument.ready():
                            # parallelize jobs on works
                            self.service.worker_pool.add_job(count_down, (self.update_strategy, (tf, instrument,)))

                    # sync before continue
                    # count_down.wait()
                else:
                    # no parallelisation below 4 instruments
                    for instrument, tf in do_update.items():
                        if instrument.ready():
                            self.update_strategy(tf, instrument)
        else:
            # process one more backtest step
            self.lock()
            next_bt_upd = self._next_backtest_update
            self._next_backtest_update = None
            self.unlock()

            if next_bt_upd:
                self.backtest_update(next_bt_upd[0], next_bt_upd[1])

        return True

    def update_strategy(self, tf, instrument):
        """
        Override this method to compute a strategy step per instrument.
        @param tf Smallest unit of time processed.
        """
        pass

    def setup_backtest(self, from_date, to_date):
        """
        Override this method to implement your backtesting strategy data set of instrument and feeders.
        """
        pass

    def query_backtest_update(self, timestamp, total_ts):
        self.lock()
        self._next_backtest_update = (timestamp, total_ts)
        self.unlock()

    def backtest_update_instrument(self, trader, instrument, timestamp):
        # retrieve the feeder by market_id or symbol
        feeder = self._feeders.get(instrument.market_id) or self._feeders.get(instrument.symbol)

        # feed of candles prior equal the timestamp and update if new candles on configured timeframe
        updated = feeder.feed(timestamp)

        if trader:
            if not trader.has_market(instrument.market_id):
                return

            # update market at minor candles
            if updated:
                # update the market instrument data before processing, but we does not have the exact base exchange rate so currency converted
                # prices on backtesting are informals
                # trader.on_update_market(instrument.market_id, True, timestamp, instrument.bid(updated[0]), instrument.ofr(updated[0]), instrument.base_exchange_rate)
                trader.on_update_market(instrument.market_id, True, timestamp, instrument.market_bid, instrument.market_ofr, instrument.base_exchange_rate)

        # update strategy as necessary
        if updated:
            self.update_strategy(updated[0], instrument)

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

        if len(self._instruments) > 3:
            count_down = self.service.worker_pool.new_count_down(len(self._instruments))

            for market_id, instrument in self._instruments.items():
                # parallelize jobs on workers
                self.service.worker_pool.add_job(count_down, (self.backtest_update_instrument, (trader, instrument, timestamp)))

            # sync before continue
            count_down.wait()
        else:
            # no parallelisation below 4 instruments
            for market_id, instrument in self._instruments.items():
                self.backtest_update_instrument(trader, instrument, timestamp)

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
            self.lock()
            prefetched = True

            # need all ready, feeders
            for market_id, feeder in self._feeders.items():
                if not feeder.ready():
                    prefetched = False
                    break

            # and instruments wanted data
            for k, instrument in self._instruments.items():
                if not instrument.ready():
                    prefetched = False
                    break

            self._prefetched = prefetched
            self.unlock()

        return self._running and self._preset and self._prefetched

    def finished(self):
        """
        In backtesting return True once all data are consumed.
        """
        # if not self.is_alive():
        if not self.running:
            return False

        self.lock()
        finished = True

        for market_id, feeder in self._feeders.items():
            if not feeder.finished():
                finished = False
                break

        self.unlock()
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
        pass

    #
    # commands
    #

    def trade_command(self, label, data, func):
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        # retrieve by market-id or mapped symbol
        instrument = self.find_instrument(market_id)

        if instrument:
            sub_trader = self._sub_traders.get(instrument)
            Terminal.inst().notice("Trade %s for strategy %s - %s" % (label, self.name, self.identifier), view='content')

            # retrieve the trade and apply the modification
            results = func(sub_trader, data)

            if results:
                if results['error']:
                    Terminal.inst().info(results['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in results['messages']:
                    Terminal.inst().info(message, view='content')

    def sub_trader_command(self, label, data, func):
        # manually trade modify a trade (add/remove an operation)
        market_id = data.get('market-id')

        # retrieve by market-id or mapped symbol
        instrument = self.find_instrument(market_id)

        if instrument:
            sub_trader = self._sub_traders.get(instrument)
            Terminal.inst().notice("Strategy trader %s for strategy %s - %s %s" % (label, self.name, self.identifier, instrument.market_id), view='content')

            # retrieve the trade and apply the modification
            results = func(sub_trader, data)

            if results:
                if results['error']:
                    Terminal.inst().info(results['messages'][0], view='status')
                else:
                    Terminal.inst().info("Done", view='status')

                for message in results['messages']:
                    Terminal.inst().info(message, view='content')

    def command(self, command_type, data):
        """
        Some parts are mutexed some others are not.
        @todo some command are only display, so could be moved to a displayer, and command could only return an object
        """
        if command_type == Strategy.COMMAND_SHOW_STATS:
            self.cmd_trade_stats(data)
        elif command_type == Strategy.COMMAND_SHOW_HISTORY:
            self.cmd_trade_history(data)
        elif command_type == Strategy.COMMAND_INFO:
            self.cmd_trader_info(data)
        elif command_type == Strategy.COMMAND_TRADE_ENTRY:
            self.trade_command("entry", data, self.cmd_trade_entry)
        elif command_type == Strategy.COMMAND_TRADE_EXIT:
            self.trade_command("exit", data, self.cmd_trade_exit)
        elif command_type == Strategy.COMMAND_TRADE_MODIFY:
            self.trade_command("modify", data, self.cmd_trade_modify)
        elif command_type == Strategy.COMMAND_TRADE_INFO:
            self.trade_command("info", data, self.cmd_trade_info)
        elif command_type == Strategy.COMMAND_TRADE_ASSIGN:
            self.trade_command("assign", data, self.cmd_trade_assign)
        elif command_type == Strategy.COMMAND_TRADER_MODIFY:
            self.sub_trader_command("info", data, self.cmd_sub_trader_modify)
        elif command_type == Strategy.COMMAND_TRADER_INFO:
            self.sub_trader_command("info", data, self.cmd_sub_trader_info)
        elif command_type == Strategy.COMMAND_TRADER_CHART:
            self.sub_trader_command("chart", data, self.cmd_sub_trader_chart)
        elif command_type == Strategy.COMMAND_TRADER_STREAM:
            self.sub_trader_command("stream", data, self.cmd_sub_trader_stream)

    #
    # signals/slots
    #

    def receiver(self, signal):
        """
        Notifiable listener.
        """ 
        if signal.source == Signal.SOURCE_STRATEGY:
            # filter by instrument for tick data
            if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

                if Instrument.TF_TICK != self.base_timeframe():
                    # non interested by this tick data
                    return

            elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

                if signal.data[1].timeframe != self.base_timeframe():
                    # non interested by this candle data
                    return

            # filter by instrument for buy/sell signal
            elif signal.signal_type == Signal.SIGNAL_BUY_SELL_ORDER:
                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

            # signal of interest
            self._signals.append(signal)

        elif signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name not in self._watchers_conf:
                # not interested by this watcher
                return

            # filter by instrument for tick data
            if signal.signal_type == Signal.SIGNAL_TICK_DATA:
                if Instrument.TF_TICK != self.base_timeframe():
                    # non interested by this tick data
                    return

                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_CANDLE_DATA:
                if signal.data[1].timeframe != self.base_timeframe():
                    # non interested by this candle data
                    return

                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

            elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

            # filter by instrument for buy/sell signal
            elif signal.signal_type == Signal.SIGNAL_BUY_SELL_ORDER:
                if signal.data[0] not in self._instruments:
                    # non interested by this instrument/symbol
                    return

            if len(self._signals) > Strategy.MAX_SIGNALS:
                # if strategy message queue saturate its mostly because of market data too many update
                # from the watcher (in live) so then ignore some of those message, the others ones are too important to be ignored
                return

            # signal of interest
            self._signals.append(signal)

        elif signal.source == Signal.SOURCE_TRADER:
            if self._trader_conf and signal.source_name == self._trader_conf['name']:
                # signal of interest
                self._signals.append(signal)

    def position_signal(self, signal_type, data):
        """
        Receive of the position signals. Dispatch if mapped instrument.
        """
        instrument = self._instruments.get(data[0])
        if instrument:
            sub_trader = self._sub_traders.get(instrument)
            if sub_trader:
                sub_trader.position_signal(signal_type, data)

    def order_signal(self, signal_type, data):
        """
        Receive of the order signals. Dispatch if mapped instrument.
        """
        instrument = self._instruments.get(data[0])
        if instrument:
            sub_trader = self._sub_traders.get(instrument)
            if sub_trader:
                sub_trader.order_signal(signal_type, data)

    #
    # display views
    #

    def get_stats(self):
        """
        Generate and return an array of dict with the form :
            symbol: str name of the symbol/market
            rate: float current profit/loss rate 0 based
            perf: float total sum of profit/loss rate 0 based
            trades: list of dict of actives trades
                id: int trade identifier
                ts: float entry UTC timestamp
                d: str 'long' or 'short'
                p: str formatted entry price
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

        @note Its implementation could be overrided but respect at the the described informations.
        @note This method is slow, it need to go through all the sub-trader, and look for any trades,
            it can lock the sub-trader trades processing, can causing global latency when having lot of markets.
        """
        results = []
        trader = self.trader()

        for k, sub_trader in self._sub_traders.items():
            rate = 0.0
            trades = []
            perf = 0.0

            sub_trader.lock()

            perf = sub_trader._stats['perf']
            best = sub_trader._stats['best']
            worst = sub_trader._stats['worst']

            success = len(sub_trader._stats['success'])
            failed = len(sub_trader._stats['failed'])
            roe = len(sub_trader._stats['roe'])

            market = trader.market(sub_trader.instrument.market_id) if trader else None
            if market:
                for trade in sub_trader.trades:
                    # estimation at close price
                    if trade.direction > 0 and trade.entry_price:
                        trade_rate = (market.close_exec_price(trade.direction) - trade.entry_price) / trade.entry_price
                    elif trade.direction < 0 and trade.entry_price:
                        trade_rate = (trade.entry_price - market.close_exec_price(trade.direction)) / trade.entry_price
                    else:
                        trade_rate = 0.0

                    # estimed maker/taker fee rate for entry and exit
                    if trade.get_stats()['entry-maker']:
                        trade_rate -= market.maker_fee
                    else:
                        trade_rate -= market.taker_fee

                    # assume an exit in maker
                    trade_rate -= market.maker_fee

                    # @todo update
                    trades.append({
                        'id': trade.id,
                        'ts': trade.entry_open_time,
                        'd': trade.direction_to_str(),
                        'l': market.format_price(trade.order_price),
                        'p': market.format_price(trade.entry_price),
                        'q': market.format_quantity(trade.order_quantity),
                        'e': market.format_quantity(trade.exec_entry_qty),
                        'x': market.format_quantity(trade.exec_exit_qty),
                        'tp': market.format_price(trade.take_profit),
                        'sl': market.format_price(trade.stop_loss),
                        'rate': trade_rate or trade.profit_loss,
                        'tf': timeframe_to_str(trade.timeframe),
                        's': trade.state_to_str(),
                        'b': market.format_price(trade.best_price()),
                        'w': market.format_price(trade.worst_price()),
                        'bt': trade.best_price_timestamp(),
                        'wt': trade.worst_price_timestamp(),
                        'aep': trade.entry_price,
                        'axp': trade.exit_price
                    })

                    rate += trade_rate or trade.pl

            sub_trader.unlock()

            results.append({
                'symbol': sub_trader.instrument.market_id,
                'rate': rate,
                'perf': perf,
                'trades': trades,
                'worst': worst,
                'best': best,
                'success': success,
                'failed': failed,
                'roe': roe
            })

        return results

    def get_history_stats(self, offset=None, limit=None, col_ofs=None):
        """
        Like as get_stats but only return the array of the trade, and complete history.
        @todo as table
        """
        results = []
        trader = self.trader()

        for k, sub_trader in self._sub_traders.items():
            sub_trader.lock()

            market = trader.market(sub_trader.instrument.market_id) if trader else None
            if market:
                def append_trade(market, trades, trade):
                    trades.append({
                        'symbol': sub_trader.instrument.market_id,
                        'id': trade['id'],
                        'ts': trade['ts'],
                        'd': trade['d'],
                        'p': trade['p'],
                        'q': trade['q'],
                        'e': trade['e'],
                        'x': trade['e'],
                        'tp': trade['tp'],
                        'sl': trade['sl'],
                        'rate': trade['rate'],
                        'tf': trade['tf'],
                        's': trade['s'],
                        'c': trade['c'],
                        'b': trade['b'],
                        'bt': trade['bt'],
                        'w': trade['w'],
                        'wt': trade['wt'],
                        'aep': trade['aep'],
                        'axp': trade['axp']
                    })

                for trade in sub_trader._stats['success']:
                    append_trade(market, results, trade)

                for trade in sub_trader._stats['failed']:
                    append_trade(market, results, trade)

                for trade in sub_trader._stats['roe']:
                    append_trade(market, results, trade)

            sub_trader.unlock()

        results.sort(key=lambda t: -t['id'])

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(results)

        limit = offset + limit

        return results[offset:limit]

    #
    # display formatters
    #

    def formatted_stats(self, results, style='', quantities=False, summ=True):
        markets = []
        pl = []
        perf = []
        worst = []
        best = []
        success = []
        failed = []
        roe = []

        markets2 = []
        trade_id = []
        direction = []
        olp = []
        price = []
        sl = []
        tp = []
        rate = []
        qty = []
        eqty = []
        xqty = []
        status = []
        bests = []
        worsts = []
        entry_times = []
        exit_times = []
        timeframes = []

        pl_sum = 0.0
        perf_sum = 0.0
        worst_sum = 0.0
        best_sum = 0.0
        success_sum = 0
        failed_sum = 0
        roe_sum = 0

        if style == 'uterm' or style == 'curses':
            W = '\033[0m'   # '\\0'
            R = '\033[31m'  # '\\1'
            G = '\033[32m'  # '\\5'
            O = '\033[33m'  # '\\6'
        elif style == 'markdown':
            W = ''
            R = ''
            G = ''
            O = ''
        else:
            W = ''
            R = ''
            G = ''
            O = ''

        for r in results:
            if r['perf'] == 0.0 and not r['trades']:
                continue

            if r['rate'] < 0:
                cr = R + ("%.2f" % ((r['rate']*100.0),)) + W
            elif r['rate'] > 0:
                cr = G + ("%.2f" % ((r['rate']*100.0),)) + W
            else:
                cr = "0.0"

            if r['perf'] < 0:
                cp = R + ("%.2f" % ((r['perf']*100.0),)) + W
            elif r['perf'] > 0:
                cp = G + ("%.2f" % ((r['perf']*100.0),)) + W
            else:
                cp = "0.0"

            markets.append(r['symbol'])
            pl.append(cr)
            perf.append(cp)
            worst.append(r['worst']*100.0)
            best.append(r['best']*100.0)
            success.append(r['success'])
            failed.append(r['failed'])
            roe.append(r['roe'])

            pl_sum += r['rate']
            perf_sum += r['perf']
            worst_sum = min(worst_sum, r['worst'])
            best_sum = max(best_sum, r['best'])
            success_sum += r['success']
            failed_sum += r['failed']
            roe_sum += r['roe']

            for t in r['trades']:
                # @todo direction
                if t['rate'] < 0 and float(t['b']) > float(t['aep']):  # have been profitable but loss
                    cr = O + ("%.2f" % ((t['rate']*100.0),)) + W
                elif t['rate'] < 0:  # loss
                    cr = R + ("%.2f" % ((t['rate']*100.0),)) + W
                elif t['rate'] > 0:  # profit
                    cr = G + ("%.2f" % ((t['rate']*100.0),)) + W
                else:  # equity
                    cr = "0.0"

                # per active trade
                markets2.append(r['symbol'])
                trade_id.append(t['id'])
                direction.append(t['d'])
                olp.append(t['l'])
                price.append(t['p'])
                sl.append(t['sl'])
                tp.append(t['tp'])
                rate.append(cr)
                qty.append(t['q'])
                eqty.append(t['e'])
                xqty.append(t['x'])
                status.append(t['s'])
                bests.append(t['b'])
                worsts.append(t['w'])
                entry_times.append(datetime.fromtimestamp(t['ts']).strftime('%Y-%m-%d %H:%M:%S'))
                timeframes.append(t['tf'])

        #
        # sum
        #

        if summ:
            if pl_sum < 0:
                cpl_sum = R + ("%.2f" % ((pl_sum*100.0),)) + W
            elif pl_sum > 0:
                cpl_sum = G + ("%.2f" % ((pl_sum*100.0),)) + W
            else:
                cpl_sum = "0.0"

            if perf_sum < 0:
                cperf_sum = R + ("%.2f" % ((perf_sum*100.0),)) + W
            elif perf_sum > 0:
                cperf_sum = G + ("%.2f" % ((perf_sum*100.0),)) + W
            else:
                cperf_sum = "0.0"

            markets.append('Total')
            pl.append(cpl_sum)
            perf.append(cperf_sum)
            worst.append(worst_sum*100.0)
            best.append(best_sum*100.0)
            success.append(success_sum)
            failed.append(failed_sum)
            roe.append(roe_sum)

        df = {
            'Market': markets,
            'P/L(%)': pl,
            'Total(%)': perf,
            'Worst': worst,
            'Best': best,
            'Success': success,
            'Failed': failed,
            'ROE': roe
        }

        arr1 = tabulate(df, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f")

        if style == 'uterm' or style == 'curses':
            arr1 = arr1.replace(R, '\\1').replace(G, '\\5').replace(W, '\\0')

        #
        # per trades
        #

        data2 = {
            'Market': markets2,
            'Id': trade_id,
            'Dir': direction,
            'P/L(%)': rate,
            'Limit': olp,
            'Price': price,
            'Entry date': entry_times,
            'TF': timeframes,
            'SL': sl,
            'TP': tp,
            'Best': bests,
            'Worst': worsts
        }

        if quantities:
            data2['Qty'] = qty
            data2['Status'] = status
            data2['Entry Q'] = eqty
            data2['Exit Q'] = xqty

        df = data2

        arr2 = tabulate(df, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        if style == 'uterm' or style == 'curses':
            arr2 = arr2.replace(O, '\\6').replace(R, '\\1').replace(G, '\\5').replace(W, '\\0')

        return arr1, arr2

    # def trades_stats_table(self, style='', offset=None, limit=None, col_ofs=None):
    #     """
    #     Returns a table of any followed markets tickers.
    #     """
    #     columns = ('Market', 'Id', 'P/L(%)', 'Price', 'EP', 'SL', 'TP', 'Best', 'Worst', 'Entry date', 'TF')
    #     data = []

    #     self.lock()

    #     for t in results:
    #         if t['rate'] < 0 and float(t['b']) > float(t['e']):  # have been profitable but loss
    #             cr = O + "%.2f" % ((t['rate']*100.0),) + W            
    #         elif t['rate'] < 0:  # loss
    #             cr = R + "%.2f" % ((t['rate']*100.0),) + W
    #         elif t['rate'] > 0:  # profit
    #             cr = G + "%.2f" % ((t['rate']*100.0),) + W
    #         else:
    #             cr = "0.0"

    #         # per active trade
    #         markets.append(t['symbol'])
    #         trade_id.append(t['id'])
    #         direction.append(t['d'])
    #         price.append(t['p']),
    #         sl.append(t['sl']),
    #         tp.append(t['tp']),
    #         rate.append(cr)
    #         qty.append(t['q']),
    #         eqty.append(t['e']),
    #         xqty.append(t['x']),
    #         status.append(t['s'])
    #         bests.append(t['b'])
    #         worsts.append(t['w'])
    #         entry_times.append(datetime.fromtimestamp(t['ts']).strftime('%Y-%m-%d %H:%M:%S'))
    #         timeframes.append(t['tf'])

    #     markets = list(self._markets.values())

    #     if offset is None:
    #         offset = 0

    #     if limit is None:
    #         limit = len(markets)

    #     limit = offset + limit

    #     trades.sort(key=lambda x: x.market_id)
    #     trades = markets[offset:limit]

    #     for trade in trades:
    #         row = (...
    #         )

    #         data.append(row[col_ofs:])

    #     self.unlock()

    #     return columns[col_ofs:], data, total_size

    def formatted_trade_stats(self, results, style='', quantities=False):
        markets = []
        trade_id = []
        direction = []
        price = []
        sl = []
        tp = []
        rate = []
        qty = []
        eqty = []
        xqty = []
        status = []
        bests = []
        worsts = []
        entry_times = []
        exit_times = []
        timeframes = []

        if style == 'uterm' or style == 'curses':
            W = '\033[0m'   # '\\0'
            R = '\033[31m'  # '\\1'
            G = '\033[32m'  # '\\5'
            O = '\033[33m'  # '\\6'
        elif style == 'markdown':
            W = ''
            R = ''
            G = ''
            O = ''
        else:
            W = ''
            R = ''
            G = ''
            O = ''

        for t in results:
            # @todo direction
            if t['rate'] < 0 and float(t['b']) > float(t['aep']):  # has been profitable but loss
                cr = O + "%.2f" % ((t['rate']*100.0),) + W            
            elif t['rate'] < 0:  # loss
                cr = R + "%.2f" % ((t['rate']*100.0),) + W
            elif t['rate'] > 0:  # profit
                cr = G + "%.2f" % ((t['rate']*100.0),) + W
            else:
                cr = "0.0"

            # color TP in green if hitted, similarely in red for SL
            _tp = (G + t['tp'] + W) if float(t['tp']) > 0 and float(t['axp']) >= float(t['tp']) else t['tp']
            _sl = (R + t['sl'] + W) if float(t['sl']) > 0 and float(t['axp']) <= float(t['sl']) else t['sl']

            # per active trade
            markets.append(t['symbol'])
            trade_id.append(t['id'])
            direction.append(t['d'])
            price.append(t['p']),
            sl.append(_sl),
            tp.append(_tp),
            rate.append(cr)
            qty.append(t['q']),
            eqty.append(t['e']),
            xqty.append(t['x']),
            status.append(t['s'])
            bests.append(t['b'])
            worsts.append(t['w'])
            entry_times.append(datetime.fromtimestamp(t['ts']).strftime('%Y-%m-%d %H:%M:%S'))
            timeframes.append(t['tf'])

        data = {
            'Market': markets,
            'Id': trade_id,
            'Dir': direction,
            'P/L(%)': rate,
            'Price': price,
            'SL': sl,
            'TP': tp,
            'Best': bests,
            'Worst': worsts,
            'Entry date': entry_times,
            'TF': timeframes,
        }

        if quantities:
            data['Qty'] = qty
            data['Entry'] = eqty
            data['Exited'] = xqty
            data['Status'] = status

        arr = tabulate(data, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)

        if style == 'uterm' or style == 'curses':
            arr = arr.replace(O, '\\6').replace(R, '\\1').replace(G, '\\5').replace(W, '\\0')

        return arr

    #
    # trade commands
    #

    def cmd_trade_entry(self, sub_trader, data):
        """
        Create a new trade according data on given sub_trader.
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
        order_leverage = 1.0

        trader = self.trader()
        market = trader.market(sub_trader.instrument.market_id)

        # need a valid price to compute the quantity
        price = limit_price or market.open_exec_price(direction)
        trade = None

        if market.trade == Market.TRADE_BUY_SELL:
            trade = StrategyAssetTrade(timeframe)

            # ajust max quantity according to free asset of quote, and convert in asset base quantity
            if trader.has_asset(market.quote):
                qty = sub_trader.instrument.trader_quantity*quantity_rate

                if trader.has_quantity(market.quote, qty):
                    order_quantity = market.adjust_quantity(qty / price)  # and adjusted to 0/max/step
                else:
                    results['error'] = True
                    results['messages'].append("Not enought free quote asset %s, has %s but need %s" % (
                            market.quote, market.format_quantity(trader.asset(market.quote).free), market.format_quantity(qty)))

        elif market.trade == Market.TRADE_MARGIN:
            trade = StrategyMarginTrade(timeframe)

            if not trader.has_margin(market.margin_cost(sub_trader.instrument.trader_quantity*quantity_rate)):
                results['error'] = True
                results['messages'].append("Not enought margin")

            order_quantity = market.adjust_quantity(sub_trader.instrument.trader_quantity*quantity_rate)

        elif market.trade == Market.TRADE_IND_MARGIN:
            trade = StrategyIndMarginTrade(timeframe)

            if not trader.has_margin(market.margin_cost(sub_trader.instrument.trader_quantity*quantity_rate)):
                results['error'] = True
                results['messages'].append("Not enought margin")

            order_quantity = market.adjust_quantity(sub_trader.instrument.trader_quantity*quantity_rate)

        else:
            results['error'] = True
            results['messages'].append("Unsupported market type")

        if order_quantity <= 0 or order_quantity * price < market.min_notional:
            results['error'] = True
            results['messages'].append("Min notional not reached (%s)" % market.min_notional)

        if results['error']:
            return results

        order_price = float(market.adjust_price(price))

        if trade:
            # user managed trade
            trade.set_user_trade()

            # the new trade must be in the trades list if the event comes before, and removed after only it failed
            sub_trader.add_trade(trade)

            if trade.open(trader, sub_trader.instrument.market_id, direction, order_type, order_price, order_quantity,
                          take_profit, stop_loss, leverage=order_leverage, hedging=True):

                # add a success result message
                results['messages'].append("Created trade %i on %s:%s" % (trade.id, self.identifier, market.market_id))

                # notify @todo would we notify on that case ?
                # self.notify_order(trade.id, trade.dir, sub_trader.instrument.market_id, market.format_price(price),
                #         self.service.timestamp, trade.timeframe, 'entry', None,
                #          market.format_price(trade.sl), market.format_price(trade.tp))

                # want it on the streaming (take care its only the order signal, no the real complete execution)
                # @todo sub_trader._global_streamer.member('buy/sell-entry').update(price, self.timestamp)
            else:
                sub_trader.remove_trade(trade)

                # add an error result message
                results['error'] = True
                results['messages'].append("Rejected trade on %s:%s" % (self.identifier, market.market_id))

        return results

    def cmd_trade_exit(self, sub_trader, data):
        """
        Exit a new trade according data on given sub_trader.

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
        market = trader.market(sub_trader.instrument.market_id)

        sub_trader.lock()

        if trade_id == -1 and sub_trader.trades:
            trade = sub_trader.trades[-1]
        else:
            for t in sub_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            price = market.close_exec_price(trade.direction)

            if not trade.is_active():
                # cancel open
                trade.cancel_open(trader)

                # add a success result message
                results['messages'].append("Cancel trade %i on %s:%s" % (trade.id, self.identifier, market.market_id))
            else:
                # close or cancel
                trade.close(trader, sub_trader.instrument.market_id)

                # add a success result message
                results['messages'].append("Close trade %i on %s:%s at market price %s" % (
                    trade.id, self.identifier, market.market_id, market.format_price(price)))

                # notify @todo would we notify on that case ?
                # self.notify_order(trade.id, trade.dir, sub_trader.instrument.market_id, market.format_price(price),
                #         self.service.timestamp, trade.timeframe, 'exit', None, None, None)

                # want it on the streaming (take care its only the order signal, no the real complete execution)
                # @todo its not really a perfect way...
                # sub_trader._global_streamer.member('buy/sell-exit').update(price, self.timestamp)
        else:
            results['error'] = True
            results['messages'].append("Invalid trade identifier %i" % trade_id)

        sub_trader.unlock()

        return results

    def cmd_trade_modify(self, sub_trader, data):
        """
        Modify a trade according data on given sub_trader.

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

        sub_trader.lock()

        if trade_id == -1 and sub_trader.trades:
            trade = sub_trader.trades[-1]
        else:
            for t in sub_trader.trades:
                if t.id == trade_id:
                    trade = t
                    break

        if trade:
            # modify SL
            if action == 'stop-loss' and 'stop-loss' in data and type(data['stop-loss']) is float:
                if data['stop-loss'] > 0.0:
                    trade.sl = data['stop-loss']
                else:
                    results['error'] = True
                    results['messages'].append("Take-profit must be greater than 0 on trade %i" % trade.id)

            # modify TP
            elif action == 'take-profit' and 'take-profit' in data and type(data['take-profit']) is float:
                if data['take-profit'] > 0.0:
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

                        # and defined the parameters
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

        sub_trader.unlock()

        return results

    def cmd_trade_assign(self, sub_trader, data):
        """
        Assign a free quantity of an asset to a newly created trade according data on given sub_trader.
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
        market = trader.market(sub_trader.instrument.market_id)

        if not trader.has_quantity(market.base, quantity):
            results['messages'].append("No enought free asset quantity.")
            results['error'] = True

        if market.trade != Market.TRADE_BUY_SELL:
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

        sub_trader.add_trade(trade)

        results['messages'].append("Assigned trade %i on %s:%s" % (trade.id, self.identifier, market.market_id))

        return results

    def cmd_trade_info(self, sub_trader, data):
        """
        Get trade info according data on given sub_trader.

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

        sub_trader.lock()

        if trade_id == -1 and sub_trader.trades:
            trade = sub_trader.trades[-1]
        else:
            for t in sub_trader.trades:
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

        sub_trader.unlock()

        return results

    def cmd_trade_stats(self, data):
        results = self.get_stats()

        if results:
            Terminal.inst().notice("Active trades for strategy %s - %s" % (self.name, self.identifier), view='content')

            # tabular formated text
            arr1, arr2 = self.formatted_stats(results, style=Terminal.inst().style(), quantities=True)

            Terminal.inst().info(arr1, view='content')
            Terminal.inst().info(arr2, view='content')

    def cmd_trade_history(self, data):
        results = self.get_history_stats(0, data.get('limit', 50), None)

        if results:
            Terminal.inst().notice("Trade history for strategy %s - %s" % (self.name, self.identifier), view='content')

            # tabular formated text
            arr = self.formatted_trade_stats(results, style=Terminal.inst().style(), quantities=True)

            Terminal.inst().info(arr, view='content')

    def cmd_sub_trader_modify(self, sub_trader, data):
        """
        Modify a sub-trader region or state.
        """        
        results = {
            'messages': [],
            'error': False
        }

        action = ""
        expiry = 0
        timeframe = 0

        sub_trader.lock()

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
                expiry = int(data.get('expiry', 0))

                if 'timeframe' in data and type(data['timeframe']) is str:
                    timeframe = timeframe_from_str(data['timeframe'])

            except ValueError:
                results['error'] = True
                results['messages'].append("Invalid parameters")

            if not results['error']:
                if region_name in self.service.regions:
                    try:
                        # instanciate the region
                        region = self.service.regions[region_name](stage, direction, timeframe)

                        if expiry:
                            region.set_expiry(expiry)

                        # and defined the parameters
                        region.init(data)

                        if region.check():
                            # append the region to the trade
                            sub_trader.add_region(region)
                        else:
                            results['error'] = True
                            results['messages'].append("Region checking error %s" % (op_name,))

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
                if not sub_trader.remove_region(region_id):
                    results['messages'].append("Invalid region identifier")

        elif action == "enable":
            if not sub_trader.activity:
                sub_trader.set_activity(True)
                results['messages'].append("Enabled strategy trader for market %s" % sub.instrument.market_id)
            else:
                results['messages'].append("Already enabled strategy trader for market %s" % sub.instrument.market_id)

        elif action == "disable":
            if sub_trader.activity:
                sub_trader.set_activity(False)
                results['messages'].append("Disabled strategy trader for market %s" % sub.instrument.market_id)
            else:
                results['messages'].append("Already disabled strategy trader for market %s" % sub.instrument.market_id)

        else:
            results['error'] = True
            results['messages'].append("Invalid action")

        sub_trader.unlock()

        return results

    def cmd_sub_trader_info(self, sub_trader, data):
        """
        Get sub-trader info or specific element if detail defined.
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

        sub_trader.lock()

        if detail == "region":
            if region_id >= 0:
                region = None

                for r in sub_trader.regions:
                    if r.id == region_id:
                        region = r
                        break

                if region:
                    results['messages'].append("Stragegy trader %s region details:" % sub_trader.instrument.market_id)
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
                else:
                    results['error'] = True
                    results['messages'].append("Invalid region identifier %i" % region_id)

            else:
                results['messages'].append("Stragegy trader %s, list %i regions:" % (sub_trader.instrument.market_id, len(sub_trader.regions)))

                for region in sub_trader.regions:
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))

        elif detail == "status":
            # status
            results['messages'].append("Activity : %s" % ("enabled" if sub_trader.activity else "disabled"))

        elif not detail:
            # no specific detail
            results['messages'].append("Stragegy trader %s details:" % sub_trader.instrument.market_id)

            # status
            results['messages'].append("Activity : %s" % ("enabled" if sub_trader.activity else "disabled"))

            # regions
            results['messages'].append("List %i regions:" % len(sub_trader.regions))

            for region in sub_trader.regions:
                results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
        else:
            results['error'] = True
            results['messages'].append("Invalid detail type name %s" % detail)

        sub_trader.unlock()

        return results

    def cmd_trader_info(self, data):
        # info on the appliance
        if 'market-id' in data:
            self.lock()

            instrument = self._instruments.get(data['market-id'])
            if instrument in self._sub_traders:
                sub_trader = self._sub_traders[instrument]
                if sub_trader:
                    Terminal.inst().info("Market %s of appliance %s identified by \\2%s\\0 is %s" % (
                        data['market-id'], self.name, self.identifier, "active" if sub_trader.activity else "paused"), view='content')

            self.unlock()
        else:
            Terminal.inst().info("Appliances %s is identified by \\2%s\\0" % (self.name, self.identifier), view='content')

            enabled = []
            disabled = []

            self.lock()

            for k, sub_trader in self._sub_traders.items():
                if sub_trader.activity:
                    enabled.append(k.market_id)
                else:
                    disabled.append(k.market_id)

            self.unlock()

            if enabled:
                enabled = [e if i%10 else e+'\n' for i, e in enumerate(enabled)]
                Terminal.inst().info("Enabled instruments (%i): %s" % (len(enabled), " ".join(enabled)), view='content')

            if disabled:
                disabled = [e if i%10 else e+'\n' for i, e in enumerate(disabled)]
                Terminal.inst().info("Disabled instruments (%i): %s" % (len(disabled), " ".join(disabled)), view='content')

    def cmd_sub_trader_chart(self, sub_trader, data):
        """
        Open as possible a process with chart of a specific sub-tader.
        """
        results = {
            'messages': [],
            'error': False
        }      

        monitor_url = data.get('monitor-url')
        timeframe = data.get('timeframe')

        if results['error']:
            return results

        sub_trader.subscribe(timeframe)

        import subprocess
        import os
        p = subprocess.Popen(["python", "-m", "monitor.client.client", monitor_url[0], monitor_url[1]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.PIPE, preexec_fn=os.setsid)

        return results

    def cmd_sub_trader_stream(self, sub_trader, data):
        """
        Subscribe/Unsubscribe to a market.
        """
        results = {
            'messages': [],
            'error': False
        }      

        timeframe = data.get('timeframe')
        action = data.get('action')

        if action == 'subscribe':
            sub_trader.subscribe(timeframe)
            results['messages'].append("Subscribed for stream %s %s %s" % (self.identifier, sub_trader.instrument.market_id, timeframe or "default"))
        elif action == 'unsubscribe':
            sub_trader.unsubscribe(timeframe)
            results['messages'].append("Unsubscribed from stream %s %s %s" % (self.identifier, sub_trader.instrument.market_id, timeframe or "any"))
        else:
             # unsupported action
            results['error'] = True
            results['messages'].append("Unsupported action on trader %i" % trade.id)

        return results

    #
    # static
    #

    @staticmethod
    def merge_parameters(default, user):
        def merge(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                d = dict(a)
                d.update({k: merge(a.get(k, None), b[k]) for k in b})
                return d

            if isinstance(a, list) and isinstance(b, list):
                return [merge(x, y) for x, y in itertools.zip_longest(a, b)]

            return a if b is None else b

        return merge(default, user)

    @staticmethod
    def parse_parameters(parameters):
        def convert(param, key):
            param.setdefault(key, None)

            if isinstance(param[key], str):
                # convert timeframe code to float in second
                param[key] = timeframe_from_str(param[key])
            elif not isinstance(timeframe[key], (int, float)):
                param[key] = None

        # regulars parameters
        parameters.setdefault('reversal', True)
        parameters.setdefault('max-trades', 1)
        parameters.setdefault('base-timeframe', '4h')
        parameters.setdefault('min-traded-timeframe', '4h')
        parameters.setdefault('max-traded-timeframe', '4h')
        parameters.setdefault('need-update', True)
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

        # for each timeframes
        for k, timeframe in parameters['timeframes'].items():
            timeframe.setdefault('depth', 0)
            timeframe.setdefault('history', 0)

            parameters.setdefault('timeframe', None)
            parameters.setdefault('parent', None)

            convert(timeframe, 'timeframe')
            convert(timeframe, 'parent')

        return parameters
