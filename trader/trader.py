# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader base class

import time
import copy
import base64
import uuid
import collections

from datetime import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.order import Order
from trader.position import Position
from trader.market import Market

from monitor.streamable import Streamable, StreamMemberSerie, StreamMemberFloatSerie
from common.runnable import Runnable
from common.utils import matching_symbols_set

from terminal.terminal import Terminal, Color
from terminal import charmap

from tabulate import tabulate

import logging
logger = logging.getLogger('siis.trader')


class Trader(Runnable):
    """
    Trader base class to specialize per broker.

    @todo use precision formatter for messages where it is missing.
    @todo orders tabulated
    @todo positions tabulated
    @todo tabulated might support columns shifting from left, and row offet to be displayed better in the terminal
        after having added the tabulated support directly to terminal

    @deprecated Older social copy methods that must be move to social strategy (to be continued, very low priority).
    """

    MAX_SIGNALS = 1000                        # max signals queue size before ignore some market data updates

    PURGE_COMMANDS_DELAY = 180                # 180s keep commands in seconds
    MAX_COMMANDS_QUEUE = 100

    # general command
    COMMAND_INFO = 1

    # bases command
    COMMAND_LIST_ORDERS = 104                 # display list active orders
    COMMAND_LIST_POSITIONS = 105              # display list current account positions

    # order commands
    COMMAND_CLOSE_MARKET = 110                # close a managed or unmanaged position at market now
    COMMAND_CLOSE_ALL_MARKET = 111            # close any positions of this account at market now

    COMMAND_SHOW_PERFORMANCE = 130            # display the performance for each markets at trader level (prefers using from strategy level)

    COMMAND_TRIGGER = 150                     # trigger a posted command using its identifier @todo might be moved to social strategy

    def __init__(self, name, service):
        super().__init__("td-%s" % name)

        self._name = name
        self._service = service 
        self._account = None

        self._activity = True  # trading activity

        self._orders = {}
        self._positions = {}
        self._assets = {}

        self._commands = []
        self._last_alerts = {}

        self._markets = {}

        self._timestamp = 0
        self._signals = collections.deque()  # filtered received signals

        # listen to its service
        self.service.add_listener(self)

        # streaming
        self.setup_streaming()

    def setup_streaming(self):
        self._streamable = Streamable(self.service.monitor_service, Streamable.STREAM_TRADER, "status", self.name)

    def stream(self):
        self._streamable.push()

    @property
    def account(self):
        return self._account
    
    @property
    def service(self):
        return self._service

    @property
    def name(self):
        return self._name

    @property
    def watcher(self):
        return self._watcher

    @property
    def paper_mode(self):
        """True for not real trader"""
        return False

    @property
    def activity(self):
        """
        Return True if the order must be executed on the broker.
        """
        return self._activity
    
    def set_activity(self, status):
        """
        Enable/disable execution of orders.
        """
        self._activity = status

    def configured_symbols(self):
        """
        Configured instruments symbols from config of the trader.
        """
        trader_config = self.service.trader_config(self._name)
        if trader_config:
            return trader_config.get('symbols', [])
        else:
            return []

    def matching_symbols_set(self, configured_symbols, available_symbols):
        """
        Special '*' symbol mean every symbol.
        Starting with '!' mean except this symbol.
        Starting with '*' mean every wildchar before the suffix.

        @param available_symbols List containing any supported markets symbol of the broker. Used when a wildchar is defined.
        """
        return matching_symbols_set(configured_symbols, available_symbols)

    def set_timestamp(self, timestamp):
        """
        Used on backtesting by the strategy.
        """
        self._timestamp = timestamp

    @property
    def timestamp(self):
        """
        Current timestamp or backtesting time.
        """
        return time.time()

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self):
        return False

    @property
    def authenticated(self):
        return False

    @classmethod    
    def authentication_required(cls, fn):
        """
        Annotation for methods that require auth.
        """
        def wrapped(self, *args, **kwargs):
            if not self.authenticated:
                msg = "%s trader : You must be authenticated to use this method" % self._name
                raise Exception(msg)  # errors.AuthenticationError(msg) @todo exceptions classes
            else:
                return fn(self, *args, **kwargs)
    
        return wrapped

    def log_report(self):
        pass

    #
    # processing
    #

    def pre_run(self):
        Terminal.inst().info("Running trader %s..." % self._name)
        self.connect()

    def post_run(self):
        Terminal.inst().info("Joining trader %s..." % self._name)
        self.disconnect()

    def post_update(self):
        if len(self._signals) > Trader.MAX_SIGNALS:
            # saturation of the signal message queue
            Terminal.inst().warning("Trader %s has more than %s waiting signals, could ignore some market data !" % (
                self.name, Trader.MAX_SIGNALS), view='status')

        # streaming
        self.stream()

    def update(self):
        """
        Update command and position.
        Thread safe method.
        """

        # performed async, but in case of backtesting update is called synchronously to avoid time derivation of the two processes.
        if self.service.backtesting:
            return True

        #
        # signals processing
        #

        count = 0

        while self._signals:
            signal = self._signals.popleft()

            # only on live mode, because in backtesting watchers are dummies
            if signal.source == Signal.SOURCE_WATCHER:
                if signal.signal_type == Signal.SIGNAL_WATCHER_CONNECTED:
                    self.on_watcher_connected(signal.source_name)
                elif signal.signal_type == Signal.SIGNAL_WATCHER_DISCONNECTED:
                    self.on_watcher_disconnected(signal.source_name)

                elif signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                    # update instrument data during live mode
                    self.on_update_market(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ACCOUNT_DATA:
                    self.on_account_updated(*signal.data)

                elif signal.signal_type == Signal.SIGNAL_POSITION_OPENED:
                    self.on_position_opened(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_POSITION_UPDATED:
                    self.on_position_updated(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_POSITION_DELETED:
                    self.on_position_deleted(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_POSITION_AMENDED:
                    self.on_position_amended(*signal.data)

                elif signal.signal_type == Signal.SIGNAL_ORDER_OPENED:
                    self.on_order_opened(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ORDER_UPDATED:
                    self.on_order_updated(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ORDER_DELETED:
                    self.on_order_deleted(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ORDER_REJECTED:
                    self.on_order_rejected(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ORDER_CANCELED:
                    self.on_order_canceled(*signal.data)
                elif signal.signal_type == Signal.SIGNAL_ORDER_TRADED:
                    self.on_order_traded(*signal.data)

                elif signal.signal_type == Signal.SIGNAL_ASSET_UPDATED:
                    self.on_asset_updated(*signal.data)

            elif signal.source == Signal.SOURCE_TRADER and signal.source_name == self._name:
                if signal.signal_type == Signal.SIGNAL_ASSET_DATA_BULK:
                    self.on_assets_loaded(signal.data)

            if count > 10:
                # no more than per loop
                break

        #
        # commands processing @deprecated was used to do not have the possibility to trigger manually a social copy signal (expiration)
        #

        if self._commands:
            i = 0
            now = time.time()

            self.lock()

            for command in self._commands:
                # remove commands older than 180 seconds
                if now - command['timestamp'] > Trader.PURGE_COMMANDS_DELAY:
                    del self._commands[i]

                i += 1

            self.unlock()

        return True

    def _purge_commands(self):
        """
        Purge olders commands.
        Not trade safe method.
        """
        if len(self._commands) > Trader.MAX_COMMANDS_QUEUE:
            size = len(self._commands) - Trader.MAX_COMMANDS_QUEUE
            self._commands = self._commands[size:]

    def has_market(self, market_id):
        return market_id in self._markets

    def command(self, command_type, data):
        """
        Some parts are mutexed some others are not.
        """
        if command_type == Trader.COMMAND_TRIGGER:
            # this kind of command when its social might be part of the social strategy
            # @todo then must be moved to social strategy using trade etc and not directly on Trader
            for command in self._commands:
                if command['command_trigger']['key'] == data['key']:
                    if command.get('close_position', False):
                        # copy a position exit
                        copied_position = command['copied_position']

                        Terminal.inst().info("Close position %s" % (copied_position.position_id, ), view='info')

                        self.close_position(command['position'].position_id)
                    else:
                        # copy a position entry
                        copied_position = command['copied_position']
                        if copied_position is not None:
                            # social trading position copy
                            Terminal.inst().info("Replicate position %s" % (copied_position.position_id, ), view='info')

                            # @todo auto set a take_profit and stop_loss to account R:R if no TP and if SL is None or >=x%
                            order = Order(self, copied_position.symbol)
                            order.direction = copied_position.direction
                            order.take_profit = copied_position.take_profit
                            order.stop_loss = copied_position.stop_loss

                            # @todo adjust to make leverage...
                            order.leverage = copied_position.leverage
                            order.set_copied_position_id(copied_position.position_id)

                            self.create_order(order)
                        else:
                            # manual or strategy copy
                            Terminal.inst().info("Replicate strategy %s order %s" % (command['strategy'], command['signal_id']), view='info')

                            # @todo auto set a take_profit and stop_loss to account R:R if no TP and if SL is None or >=x%
                            order = Order(self, command['symbol'])
                            order.direction = command['direction']
                            # order.take_profit = @todo a max TP
                            # order.stop_loss = @todo a max default SL according to account properties

                            # @todo adjust to make leverage...
                            order.leverage = command.get('leverage', 1)

                            self.create_order(order)
        
        elif command_type == Trader.COMMAND_LIST_POSITIONS:
            # display the list of ALL positions of the account (managed or not by a strategy)
            if self.connected and self._positions:
                if self.account is None:
                    return

                Terminal.inst().notice("List %i positions for %s" % (len(self._positions.items()), self._name), view='content')

                if 0:  # @todo  
                    columns, table, total_size = self.positions_table(style=Terminal.inst().style())
                    Terminal.inst().table(columns, table, total_size, view='content')
                else:
                    self.lock()

                    # simple text
                    for k, p in self._positions.items():
                        # per position, profit/loss are in base pair currency, need base exchange rate
                        market = self.market(p.symbol)
                        if market is None:
                            continue

                        if p.quantity <= 0:
                            continue

                        if market.unit_type == Market.UNIT_AMOUNT:
                            unit = market.quote
                        elif market.unit_type == Market.UNIT_CONTRACTS:
                            unit = ' contracts'
                        elif market.unit_type == Market.UNIT_SHARES:
                            unit = ' shares'

                        direction = "Long" if p.direction > 0 else "Short"
                        Terminal.inst().info("%s size %s%s on market %s from %s" % (direction, p.quantity, unit, p.symbol, self._name), view='content')

                        # for social position
                        if p.copied_position_id:
                            Terminal.inst().info("Copied id %s from user %s" % (
                                p.copied_position_id, p.author.name if p.author is not None else 'myself'), view='content')

                        margin_factor = 1.0 / p.leverage if p.leverage else market.margin_factor
                        margin = p.margin_cost(market) / market.base_exchange_rate * margin_factor

                        created_date = datetime.fromtimestamp(p.created_time).strftime('%Y-%m-%d %H:%M:%S') if p.created_time else "???"

                        Terminal.inst().info("Quantity %s / Margin %s (x%s)" % (market.format_quantity(p.quantity), margin, 1.0 / margin_factor), view='content')
                        Terminal.inst().info("Created %s / Entry-price %s / Current exit-price %s" % (
                            created_date,
                            market.format_price(p.entry_price),
                            market.format_price(market.close_exec_price(p.direction))), view='content')

                        Terminal.inst().info("Stop-loss %s / Take-profit %s / Trailing-stop %s" % (
                            market.format_price(p.stop_loss) if p.stop_loss else "NO",
                            market.format_price(p.take_profit or 0.0) if p.take_profit else "NO",
                            "YES" if p.trailing_stop else "NO"), view='content')

                        # display unrealized P/L
                        profit_loss_msg = "Profit/Loss %s%s (%.2f%%) [%s%s]" % (
                            market.format_price(p.profit_loss), market.quote_display or market.quote,
                            p.profit_loss_rate*100.0,
                            self.account.format_price(p.profit_loss / market.base_exchange_rate), self.account.currency_display or self.account.currency)

                        profit_loss_msg_at_market = "Profit/Loss at market %s%s (%.2f%%) [%s%s]" % (
                            market.format_price(p.profit_loss_market), market.quote_display or market.quote,
                            p.profit_loss_market_rate*100.0,
                            self.account.format_price(p.profit_loss_market / market.base_exchange_rate), self.account.currency_display or self.account.currency)

                        if p.profit_loss > 0.0:
                            Terminal.inst().high(profit_loss_msg, view='content')
                            Terminal.inst().high(profit_loss_msg_at_market, view='content')
                        elif p.profit_loss < 0.0:
                            Terminal.inst().low(profit_loss_msg, view='content')
                            Terminal.inst().low(profit_loss_msg_at_market, view='content')
                        else:
                            Terminal.inst().info(profit_loss_msg, view='content')
                            Terminal.inst().info(profit_loss_msg_at_market, view='content')

                        if p.key:
                            Terminal.inst().action("To close manually at market use key %s" % p.key, view='content')

                        Terminal.inst().info("", view='content')

                    self.unlock()

        elif command_type == Trader.COMMAND_LIST_ORDERS:
            # display the active orders details
            if self.connected and self._orders:
                Terminal.inst().notice("List %i actives orders for %s" % (len(self._orders), self._name), view='content')
                
                # columns, table, total_size = trader.orders_table(*Terminal.inst().active_content().format())
                # Terminal.inst().table(columns, table, total_size, view='content')

        elif command_type == Trader.COMMAND_INFO:
            # info on the trade
            self.cmd_trader_info(data)

        elif command_type == Trader.COMMAND_CLOSE_MARKET:
            # manually close a specified position at market now
            self.lock()

            for k, position in self._positions.items():
                if position.key == data['key']:
                    # query close position

                    self.unlock()
                    self.close_position(position.position_id)
                    self.lock()

                    Terminal.inst().action("Closing position %s..." % (position.position_id, ), view='info')

                    break

            self.unlock()

        elif command_type == Trader.COMMAND_CLOSE_ALL_MARKET:
            # manually close any position related to this account/trader at market now
            self.lock()

            for k, position in self._positions.items():
                # query close position
                self.unlock()
                self.close_position(position.position_id)
                self.lock()

                Terminal.inst().action("Closing position %s..." % (position.position_id, ), view='info')

                break

            self.unlock()            

        elif command_type == Trader.COMMAND_SHOW_PERFORMANCE:
            results = self.get_live_report()

            if results:
                Terminal.inst().notice("Performance for markets of %s" % self._name, view='content')

                # @todo display in table
                for r in results:
                    Terminal.inst().info("Rate for market %s is %.2f%% / %.4f" % (r[0], r[1]*100, r[2]), view='content')

    def ping(self, timeout):
        self._ping = (0, None, True)

    def pong(self, timestamp, pid, watchdog_service, msg):
        if msg:
            # display trader activity
            if self.connected:
                Terminal.inst().action("Trader worker %s is alive %s" % (self._name, msg), view='content')
            else:
                Terminal.inst().action("Trader worker %s is alive but waiting for (re)connection %s" % (self._name, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    def has_margin(self, margin):
        """
        Return True for a margin trading if the account have suffisient free margin.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
        to check if an order can be created
        """
        return self.account.margin_balance >= margin

    def has_quantity(self, asset_name, quantity):
        """
        Return True if a given asset has a minimum quantity.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
        to check if an order can be created
        """
        result = False

        self.lock()
        asset = self._assets.get(asset_name)
        result = asset and asset.free >= quantity
        self.unlock()

        return result

    def set_ref_order_id(self, order):
        """
        Generate a new reference order id to be setup before calling create order, else a default one wil be generated.
        Generating it before is a prefered way to correctly manange order in strategy.
        @param order A valid or on to set the ref order id.
        @note If the given order already have a ref order id no change is made.
        """
        if order and not order.ref_order_id:
            # order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid5(uuid.NAMESPACE_DNS, 'siis.com').bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            return order.ref_order_id

        return None

    def create_order(self, order):
        """
        Create an order. The symbol of the order must be on of the trader instruments.
        """
        return False

    def cancel_order(self, order_or_id):
        """
        Cancel an existing order. The symbol of the order must be on of the trader instruments.
        """
        return False

    def close_position(self, position_or_id, market=True, limit_price=None):
        """
        Close an existing position.
        Market is default, take care of the fee.
        Limit price can be defined but then it will create a limit order in the opposite direction in some broker
        and modify the position in some other (depends of the mode hedging...).
        """
        if type(position_or_id) is str:
            position = self._positions.get(position_or_id)
        else:
            position = position_or_id

        if position is None or not position.is_opened():
            return False

        # market stop order
        order = Order(self, position.symbol)
        order.direction = position.close_direction()
        order.order_type = Order.ORDER_MARKET
        order.quantity = position.quantity  # fully close
        order.leverage = position.leverage  # same as open

        # simply create an order in the opposite direction
        return self.create_order(order)

    def modify_position(self, position_id, stop_loss_price=None, take_profit_price=None):
        """
        Modifiy the stop loss or take profit of a position.
        Its a bit complicated, it depends of the mode of the broker, and if hedging or not.
        """
        return False

    def orders(self, market_id):
        """
        Get actives order for a market id.
        """
        return []

    def market(self, market_id, force=False):
        """
        Market data for a market id.
        @param force True to force request and cache update.
        """
        return self._markets.get(market_id)

    def asset(self, symbol):
        """
        Get asset for symbol.
        """
        return self._assets.get(symbol)

    def has_asset(self, symbol):
        """
        Is trader has a specific asset.
        """
        return symbol in self._assets

    def positions(self, market_id):
        """
        Get actives positions for a market id.
        """
        return []

    def get_position(self, position_id):
        """
        Return a copy of the trader position if exists else None.
        """
        position = None

        self.lock()
        if self._positions.get(position_id):
            position = copy.copy(self._positions.get(position_id))
        self.unlock()

        return position

    #
    # signals
    #

    def receiver(self, signal):
        """
        Notifiable listener.
        """ 
        if signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name != self._name:
                # only interested by the watcher of the same name
                return

            if signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                if not self.has_market(signal.data[0]):
                    # non interested by this instrument/symbol
                    return

                if len(self._signals) > Trader.MAX_SIGNALS:
                    # if trader message queue saturate its mostly because of market data too many update
                    # then ignore some of those message, the others ones are too important to be ignored
                    return

            elif signal.signal_type not in (
                    Signal.SIGNAL_ACCOUNT_DATA, Signal.SIGNAL_WATCHER_CONNECTED, Signal.SIGNAL_WATCHER_DISCONNECTED,
                    Signal.SIGNAL_POSITION_OPENED, Signal.SIGNAL_POSITION_UPDATED, Signal.SIGNAL_POSITION_DELETED, Signal.SIGNAL_POSITION_AMENDED,
                    Signal.SIGNAL_ORDER_OPENED, Signal.SIGNAL_ORDER_UPDATED, Signal.SIGNAL_ORDER_DELETED, Signal.SIGNAL_ORDER_REJECTED,
                    Signal.SIGNAL_ORDER_CANCELED, Signal.SIGNAL_ORDER_TRADED,
                    Signal.SIGNAL_ASSET_UPDATED):
                return

            # signal of interest
            self._signals.append(signal)

        elif signal.source == Signal.SOURCE_TRADER:  # in fact it comes from the DB service but request in self trader name
            if signal.signal_type not in (Signal.SIGNAL_ASSET_DATA, Signal.SIGNAL_ASSET_DATA_BULK):
                # non interested by others signals
                return 

            # signal of interest
            self._signals.append(signal)

    def on_watcher_connected(self, watcher_name):
        msg = "Trader %s joined %s watcher connection." % (self.name, watcher_name)
        logger.info(msg)
        Terminal.inst().info(msg, view='content')

    def on_watcher_disconnected(self, watcher_name):
        msg = "Trader %s lossing %s watcher connection." % (self.name, watcher_name)
        logger.warning(msg)
        Terminal.inst().info(msg, view='content')

    #
    # account slots
    #

    @Runnable.mutexed
    def on_account_updated(self, balance, free_margin, unrealized_pnl, currency, risk_limit):
        """
        Update account details.
        """
        self.account.set_balance(balance)
        self.account.set_used_margin(balance - free_margin)
        self.account.set_unrealized_profit_loss(unrealized_pnl)

        if currency:
            self.account.set_currency(currency)

        if risk_limit is not None:
            self.account.set_risk_limit(risk_limit)

    #
    # positions slots
    #

    @Runnable.mutexed
    def on_position_opened(self, market_id, position_data, ref_order_id):
        # insert it, erase the previous if necessary
        position = Position(self)
        position.set_position_id(position_data['id'])
        position.set_key(self.service.gen_key())

        position.entry(
            position_data['direction'],
            position_data['symbol'],
            position_data['quantity'],
            position_data.get('take-profit'),
            position_data.get('stop-loss'),
            position_data.get('leverage'),
            position_data.get('trailing-stop'))

        if position_data.get('avg-entry-price') is not None:
            position.entry_price = position_data['avg-entry-price']
        elif position_data.get('avg-price') is not None:
            position.entry_price = position_data['avg-price']
        elif position_data.get('exec-price') is not None:
            position.entry_price = position_data['exec-price']

        # logger.debug("position opened %s size=%s" %(position.symbol, position.quantity))

        self._positions[position.position_id] = position

        market = self.market(position.symbol)
        if market:
            position.update_profit_loss(market)

        if position_data.get('profit-loss') is not None:
            position._profit_loss = position_data.get('profit-loss')
            position._profit_market_loss = position_data.get('profit-loss')

        if position_data.get('profit-loss-rate') is not None:
            position._profit_loss_rate = position_data.get('profit-loss-rate')
            position._profit_loss_market_rate = position_data.get('profit-loss-rate')

    @Runnable.mutexed
    def on_position_updated(self, market_id, position_data, ref_order_id):
        position = self._positions.get(position_data['id'])

        if position:
            # update
            position.entry(
                position_data['direction'],
                position_data['symbol'],
                position_data['quantity'],
                position_data.get('take-profit'),
                position_data.get('stop-loss'),
                position_data.get('leverage'),
                position_data.get('trailing-stop'))

            if position_data.get('avg-entry-price') is not None:
                position.entry_price = position_data['avg-entry-price']
            elif position_data.get('avg-price') is not None:
                position.entry_price = position_data['avg-price']
            elif position_data.get('exec-price') is not None:
                position.entry_price = position_data['exec-price']

            if position_data.get('avg-exit-price') is not None:
                position.exit_price = position_data['avg-exit-price']
        else:
            # not found, insert and change state 
            position = Position(self)
            position.set_position_id(position_data['id'])
            position.set_key(self.service.gen_key())

            position.entry(
                position_data['direction'],
                position_data['symbol'],
                position_data['quantity'],
                position_data.get('take-profit'),
                position_data.get('stop-loss'),
                position_data.get('leverage'),
                position_data.get('trailing-stop'))

            if position_data.get('avg-entry-price') is not None:
                position.entry_price = position_data['avg-entry-price']
            elif position_data.get('avg-price') is not None:
                position.entry_price = position_data['avg-price']
            elif position_data.get('exec-price') is not None:
                position.entry_price = position_data['exec-price']

            if position_data.get('avg-exit-price') is not None:
                position.exit_price = position_data['avg-exit-price']

            self._positions[position.position_id] = position

        market = self.market(position.symbol)
        if market:
            position.update_profit_loss(market)

        if position_data.get('profit-loss') is not None:
            position._profit_loss = position_data.get('profit-loss')
            position._profit_market_loss = position_data.get('profit-loss')

        if position_data.get('profit-loss-rate') is not None:
            position._profit_loss_rate = position_data.get('profit-loss-rate')
            position._profit_loss_market_rate = position_data.get('profit-loss-rate')

    @Runnable.mutexed
    def on_position_amended(self, market_id, position_data, ref_order_id):
        position = self._positions.get(position_data['id'])

        if position:
            if position_data.get('take-profit'):
                position.take_profit = position_data['take-profit']

            if position_data.get('stop-loss'):
                position.stop_loss = position_data['stop-loss']

            if position_data.get('trailing-stop'):
                position.trailing_stop = position_data['trailing-stop']

            if position_data.get('leverage'):
                position.leverage = position_data['leverage']

    @Runnable.mutexed
    def on_position_deleted(self, market_id, position_data, ref_order_id):
        # delete the position from the dict
        if self._positions.get(position_data['id']):
            del self._positions[position_data['id']]

    #
    # order slots
    #

    @Runnable.mutexed
    def on_order_opened(self, market_id, order_data, ref_order_id):
        market = self._markets.get(order_data['symbol'])
        if market is None:
            # not interested by this market
            return

        if order_data['id'] not in self._orders:
            # some are inserted during create_order result
            order = Order(self, order_data['symbol'])
            order.set_order_id(order_data['id'])

            order.created_time = order_data['timestamp']

            order.direction = order_data['direction']
            order.order_type = order_data['type']

            order.quantity = order_data['quantity']

            # depending of the type
            order.price = order_data.get('price')
            order.stop_price = order_data.get('stop-price')
            order.time_in_force = order_data.get('time-in-force', Order.TIME_IN_FORCE_GTC)

            order.close_only = order_data.get('close-only', False)
            order.reduce_only = order_data.get('reduce-only', False)

            order.stop_loss = order_data.get('stop-loss')
            order.take_profit = order_data.get('take-profit')

            self._orders[order_data['id']] = order

    @Runnable.mutexed
    def on_order_updated(self, market_id, order_data, ref_order_id):
        order = self._orders.get(order_data['id'])
        if order:
            # update price, stop-price, stop-loss, take-profit, quantity if necessarry
            order.quantity = order_data['quantity']

            order.price = order_data.get('price')
            order.stop_price = order_data.get('stop-price')

            order.stop_loss = order_data.get('stop-loss')
            order.take_profit = order_data.get('take-profit')

    @Runnable.mutexed
    def on_order_deleted(self, market_id, order_id, ref_order_id):
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_rejected(self, market_id, ref_order_id):
        pass

    @Runnable.mutexed
    def on_order_canceled(self, market_id, order_id, ref_order_id):
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_traded(self, market_id, order_data, ref_order_id):
        order = self._orders.get(order_data['id'])
        if order:
            # update executed qty (depending of the implementation filled or cumulative-filled or both are present)
            if order_data.get('cumulative-filled') is not None:
                order.executed = order_data['cumulative-filled']
            elif order_data.get('filled') is not None:
                order.executed += order_data['filled']

            if order_data.get('timestamp'):
                # keep last transact_time
                order.transact_time = order_data['timestamp']

    #
    # asset slots
    #       

    def on_assets_loaded(self, assets):
        pass

    def on_asset_updated(self, asset_name, locked, free):
        pass

    #
    # market slots
    #

    @Runnable.mutexed
    def on_update_market(self, market_id, tradable, last_update_time, bid, ofr, base_exchange_rate,
            contract_size=None, value_per_pip=None, vol24h_base=None, vol24h_quote=None):
        """
        Update bid, ofr, base exchange rate and last update time of a market.
        Take care this method is not thread safe. Use it with the trader mutex or exclusively in the same thread.
        """
        market = self._markets.get(market_id)
        if market is None:
            # create it but will miss lot of details at this time
            # uses market_id as symbol but its not ideal
            market = Market(market_id, market_id)
            self._markets[market_id] = market

        if bid:
            market.bid = bid

        if ofr:
            market.ofr = ofr

        if base_exchange_rate is not None:
            market.base_exchange_rate = base_exchange_rate

        if last_update_time is not None:
            market.last_update_time = last_update_time

        if tradable is not None:
            market.is_open = tradable

        if contract_size is not None:
            market.contract_size = contract_size

        if value_per_pip is not None:
            market.value_per_pip = value_per_pip

        if vol24h_base is not None:
            market.vol24h_base = vol24h_base

        if vol24h_quote is not None:
            market.vol24h_quote = vol24h_quote

        # push last price to keep a local cache of history
        market.push_price()

    #
    # utils
    #

    def last_price(self, market_id):
        """
        Return the last price for a specific market.
        @param str market_id Valid market identifier
        @return float Last watched price or None if missing market.
        """
        price = None

        self.lock()
        market = self.market(market_id)
        if market:
            price = market.price
        self.unlock()

        return price

    def history_price(self, market_id, timestamp=None):
        """
        Return the price for a particular timestamp or the last if not defined.
        @param str market_id Valid market identifier
        @param float timestamp Valid second timetamp or if None then prefers the method last_price.
        @return float Price or None if not found (market missing or unable to retrieve a price)

        @note Cost an API request when timestamp is defined and if price
            was not found into the local market history (only few values are kept in memory cache).
        """
        price = None

        if timestamp:
            market = self.market(market_id)
            if market:
                # lookup into the local cache
                price = market.recent_price(timestamp)

            if price is None and self._watcher:
                # query the REST API
                price = self._watcher.price_history(market_id, timestamp)

            if price is None:
                logger.warning("Trader %s cannot found price history for %s at %s" % (self._name, market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
        else:
            # last price
            market = self.market(market_id)
            if market:
                price = market.price

            if price is None:
                logger.warning("Trader %s cannot found last price for %s because no market was found" % (self._name, market_id,))

        return price

    #
    # stats
    #

    def get_live_report(self):
        return []

    #
    # data tables
    #

    def markets_table(self, style='', offset=None, limit=None, col_ofs=None):
        """
        Returns a table of any followed markets.
        """
        columns = ('Market', 'Symbol', 'Base', 'Quote', 'Rate', 'Type', 'Unit', 'Status', 'PipMean', 'PerPip', 'Lot', 'Contract', 'Min Size', 'Min Notional')
        data = []

        self.lock()

        markets = list(self._markets.values())
        total_size = (len(columns), len(markets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(markets)

        limit = offset + limit

        markets.sort(key=lambda x: x.market_id)
        markets = markets[offset:limit]

        for market in markets:
            status = Color.colorize_cond("Open" if market.is_open else "Close", market.is_open, style=style, true=Color.GREEN, false=Color.RED)

            row = (
                market.market_id,
                market.symbol,
                market.base,
                market.quote,
                str("%.8f" % market.base_exchange_rate).rstrip('0').rstrip('.'),
                market.market_type_str().capitalize(),
                market.unit_type_str().capitalize(),
                status,
                str("%.8f" % market.one_pip_means).rstrip('0').rstrip('.'),
                str("%.8f" % market.value_per_pip).rstrip('0').rstrip('.'),
                str("%.8f" % market.lot_size).rstrip('0').rstrip('.'),
                str("%.12f" % market.contract_size).rstrip('0').rstrip('.'),
                market.min_size,
                market.min_notional)

            data.append(row[col_ofs:])

        self.unlock()

        return columns[col_ofs:], data, total_size

    def markets_tickers_table(self, style='', offset=None, limit=None, col_ofs=None, prev_timestamp=None):
        """
        Returns a table of any followed markets tickers.
        """
        columns = ('Market', 'Symbol', 'Bid', 'Ofr', 'Spread', 'Vol24h base', 'Vol24h quote', 'Time')
        data = []

        self.lock()

        markets = list(self._markets.values())
        total_size = (len(columns), len(markets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(markets)

        limit = offset + limit

        markets.sort(key=lambda x: x.market_id)
        markets = markets[offset:limit]

        for market in markets:
            recent = market.recent(self.timestamp - 0.5 if not prev_timestamp else prev_timestamp)
            if recent:
                bid = Color.colorize_updn(market.format_price(market.bid), recent[1], market.bid, style=style)
                ofr = Color.colorize_updn(market.format_price(market.ofr), recent[2], market.ofr, style=style)
                spread = Color.colorize_updn(market.format_spread(market.spread), market.spread, recent[2] - recent[1], style=style)
            else:
                bid = market.format_price(market.bid)
                ofr = market.format_price(market.ofr)
                spread = market.format_price(market.spread)

            if market.vol24h_quote:
                # @todo could be configured
                low = 0
                if market.quote in ('USD', 'EUR', 'ZEUR', 'ZUSD', 'USDT', 'PAX', 'USDC', 'USDS', 'BUSD', 'TUSD'):
                    low = 1000000
                elif market.quote in ('BTC'):
                    low = 100
                elif market.quote in ('ETH'):
                    low = 5000
                elif market.quote in ('BNB'):
                    low = 50000

                vol24h_quote = Color.colorize_cond("%.2f" % market.vol24h_quote, market.vol24h_quote < low, style=style, true=Color.YELLOW, false=Color.WHITE)
            else:
                vol24h_quote = charmap.HOURGLASS

            row = (
                 market.market_id,
                 market.symbol,
                 bid,
                 ofr,
                 spread,
                 market.format_quantity(market.vol24h_base) if market.vol24h_base else charmap.HOURGLASS,
                 vol24h_quote,
                 datetime.fromtimestamp(market.last_update_time).strftime("%H:%M:%S") if market.last_update_time else charmap.HOURGLASS)

            data.append(row[col_ofs:])

        self.unlock()

        return columns[col_ofs:], data, total_size

    def assets_table(self, style='', offset=None, limit=None, col_ofs=None, filter_low=True):
        """
        Returns a table of any non empty assets.
        """
        columns = ('Asset', 'Locked', 'Free', 'Total', 'Avg price', 'Change', 'Change %',
                'P/L %s' % self.account.currency, 'P/L %s' % self.account.alt_currency)
        data = []

        self.lock()

        assets = [asset for asset in self._assets.values() if asset.quantity > 0.0]
        total_size = (len(columns), len(assets))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(assets)

        limit = offset + limit

        assets.sort(key=lambda x: x.symbol)
        assets = assets[offset:limit]

        for asset in assets:
            # use the most appropriate market
            market = self.market(asset.symbol+asset.quote)

            change = ""
            change_percent = ""
            profit_loss = ""
            profit_loss_alt = ""

            if market:
                locked = market.format_quantity(asset.locked)
                free = market.format_quantity(asset.free)
                quantity = market.format_quantity(asset.quantity)

                base_exchange_rate = 1.0

                change = market.format_price(market.bid - asset.price) + market.quote_display or market.quote
                change_percent = (market.bid - asset.price) / asset.price * 100.0 if asset.price else 0.0

                if change_percent > 0.0:
                    change_percent = Color.colorize("%.2f" % change_percent, Color.GREEN, style)
                elif change_percent < 0.0:
                    change_percent = Color.colorize("%.2f" % change_percent, Color.RED, style)
                else:
                    change_percent = "%.2f" % change_percent

                quote_market = self.market(market.quote+self.account.currency)
                if quote_market:
                    base_exchange_rate = 1.0 / quote_market.price

                profit_loss = market.format_price(asset.profit_loss) if market.quote == self.account.currency else ""
                profit_loss_alt = market.format_price(asset.profit_loss / base_exchange_rate) if market.quote == self.account.alt_currency else ""

                if asset.profit_loss > 0.0:
                    if profit_loss:
                        profit_loss = Color.colorize(profit_loss, Color.GREEN, style)

                    if profit_loss_alt:
                        profit_loss_alt = Color.colorize(profit_loss_alt, Color.GREEN, style)
                elif asset.profit_loss < 0.0:
                    if profit_loss:
                        profit_loss = Color.colorize(profit_loss, Color.RED, style)

                    if profit_loss_alt:
                        profit_loss_alt = Color.colorize(profit_loss_alt, Color.RED, style)
            else:
                locked = "%.8f" % asset.locked
                free = "%.8f" % asset.free
                quantity = "%.8f" % asset.quantity

            row = (
                asset.symbol,
                locked,
                free,
                quantity,
                asset.format_price(asset.price) if asset.price else charmap.HOURGLASS,
                change or charmap.ROADBLOCK,
                change_percent or charmap.ROADBLOCK,
                profit_loss or charmap.ROADBLOCK,
                profit_loss_alt or charmap.ROADBLOCK,
            )

            data.append(row[col_ofs:])

        self.unlock()

        return columns[col_ofs:], data, total_size

    def account_table(self, style='', offset=None, limit=None, col_ofs=None):
        """
        Returns a table of any followed markets.
        """
        columns = ('Broker', 'Account', 'Username', 'Email', 'Asset', 'Free Asset', 'Balance', 'Margin', 'Net worth', 'Net w. alt',
                   'Risk limit', 'Unrealized P/L', 'U. P/L alt', 'Asset U. P/L', 'Asset U. P/L alt')
        data = []

        self.lock()

        if offset is None:
            offset = 0

        if limit is None:
            limit = 1

        limit = offset + limit

        row = (
            self.name,
            self._account.name,
            self._account.username,
            self._account.email,
            self.account.format_price(self._account.asset_balance) + self.account.currency_display or self.account.currency,
            self.account.format_price(self._account.free_asset_balance) + self.account.currency_display or self.account.currency,
            self.account.format_price(self._account.balance) + self.account.currency_display or self.account.currency,
            self.account.format_price(self._account.margin_balance) + self.account.currency_display or self.account.currency,
            self.account.format_price(self._account.net_worth) + self.account.currency_display or self.account.currency,
            self.account.format_alt_price(self._account.net_worth * self._account.currency_ratio) + self.account.alt_currency_display or self.account.alt_currency,
            self.account.format_price(self._account.risk_limit) + self.account.currency_display or self.account.currency,
            self.account.format_price(self._account.profit_loss) + self.account.currency_display or self.account.currency,
            self.account.format_alt_price(self._account.profit_loss * self._account.currency_ratio) + self.account.alt_currency_display or self.account.alt_currency,
            self.account.format_price(self._account.asset_profit_loss) + self.account.currency_display or self.account.currency,
            self.account.format_alt_price(self._account.asset_profit_loss * self._account.currency_ratio) + self.account.alt_currency_display or self.account.alt_currency,
        )

        if offset < 1 and limit > 0:
            data.append(row[col_ofs:])

        self.unlock()

        return columns[col_ofs:], data, (len(columns), 1)

    #
    # deprecated (previously used for social copy, but now prefer use the social copy strategy, to be removed once done)
    #

    def on_enter_position(self, copied_position, command_trigger):
        """
        Create a position from a command trigger.
        Thread safe method.
        @todo should be strategy part, on_set_order is in a sort of dublicate
        """
        if not self.has_market(copied_position.symbol):
            return

        command = {
            'copied_position': copied_position,
            'order_type': Order.ORDER_MARKET,
            'command_trigger': command_trigger,
            'timestamp': time.time()
        }

        self.lock()
        self._commands.append(command)
        self._purge_commands()
        self.unlock()

    def on_exit_position(self, copied_position, command_trigger):
        """
        Exit a position from a command trigger.
        Thread safe method.
        @todo social position id and mapping might be maintened by the social strategy appliance
        """
        # map shared position_id to self position_id
        self.lock()
        self._position = self._positions.get(copied_position.position_id)
        self.unlock()

        # if the position is currently copied order to close it (manually by message or auto)
        if self_position is None:
            # Terminal.inst().error("Unable to find the copy of position %s for close " % (copied_position.position_id, ), view='status')
            return

        command = {
            'copied_position': copied_position,
            'position': self._position,
            'order_type': Order.ORDER_MARKET,
            'close_position': True,
            'reduce_only': True,
            'command_trigger': command_trigger,
            'timestamp': time.time()
        }

        self.lock()
        self._commands.append(command)
        self._purge_commands()
        self.unlock()

    def on_set_order(self, order, command_trigger):
        """
        Create a new order from a command trigger.
        Thread safe method.
        @todo social position id and mapping might be maintened by the social strategy appliance
        """
        if not self.has_market(order['symbol']):
            return

        command = {
            'copied_position': None,
            'order_type': Order.ORDER_MARKET,
            'command_trigger': command_trigger,
            'symbol': order['symbol'],
            'timestamp': float(order['timestamp']),
            'direction': order['direction'],
            'signal_id': order.get('signal_id', 'undefined'),
            'strategy': order.get('strategy', None),
            'options': order.get('options', {}),            
        }

        self.lock()
        self._commands.append(command)
        self._purge_commands()
        self.unlock()

    #
    # commands
    #

    def cmd_trader_info(self, data):
        # info on the trader
        if 'market-id' in data:
            self.lock()

            market = self._markets.get(data['market-id'])
            if market:
                Terminal.inst().info("Market %s of trader %s is %s." % (
                    data['market-id'], self.name, "active" if market.activity else "paused"),
                    view='content')

            self.unlock()
        else:
            Terminal.inst().info("Trader %s :" % (self.name), view='content')

            enabled = []
            disabled = []

            self.lock()

            for k, market in self._markets.items():
                if market.activity:
                    enabled.append(k)
                else:
                    disabled.append(k)

            self.unlock()

            if enabled:
                enabled = [e if i%10 else e+'\n' for i, e in enumerate(enabled)]
                Terminal.inst().info("Enabled instruments (%i): %s" % (len(enabled), " ".join(enabled)), view='content')

            if disabled:
                disabled = [e if i%10 else e+'\n' for i, e in enumerate(disabled)]
                Terminal.inst().info("Disabled instruments (%i): %s" % (len(disabled), " ".join(disabled)), view='content')
