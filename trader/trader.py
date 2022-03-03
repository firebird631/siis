# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader base class

import traceback
import time
import copy
import base64
import uuid
import collections

from datetime import datetime, timedelta

from common.signal import Signal

from trader.order import Order
from trader.position import Position

from monitor.streamable import Streamable, StreamMemberInt, StreamMemberTraderBalance
from common.runnable import Runnable

from terminal.terminal import Terminal, Color
from terminal import charmap

import logging
logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


class Trader(Runnable):
    """
    Trader base class to specialize per broker.

    @todo Create sell order for COMMAND_SELL_ALL_ASSET.
    @todo Move table/dataset like as strategy
    @todo Move command to specific files like as strategy
    """

    MAX_SIGNALS = 1000                        # max signals queue size before ignore some market data updates

    PURGE_COMMANDS_DELAY = 180                # 180s keep commands in seconds
    MAX_COMMANDS_QUEUE = 100

    # general command
    COMMAND_INFO = 1
    COMMAND_TRADER_FROZE_ASSET_QUANTITY = 2   # froze a free quantity of an asset that could not be used
    COMMAND_TICKER_MEMSET = 3                 # memorize the last market price for any or a specific ticker

    # order commands
    COMMAND_CLOSE_MARKET = 110                # close a managed or unmanaged position at market now
    COMMAND_CLOSE_ALL_MARKET = 111            # close any positions of this account at market now
    COMMAND_CANCEL_ALL_ORDER = 112            # cancel any pending orders
    COMMAND_SELL_ALL_ASSET = 113              # sell any quantity of asset at market price
    COMMAND_CANCEL_ORDER = 114                # cancel a specific order

    def __init__(self, name, service):
        super().__init__("td-%s" % name)

        self._name = name
        self._service = service 
        self._account = None

        self._watcher = None

        self._activity = True  # trading activity

        self._orders = {}
        self._positions = {}
        self._assets = {}

        self._commands = []
        self._last_alerts = {}

        self._markets = {}

        self._timestamp = 0
        self._signals = collections.deque()  # filtered received signals

        self._streamable = None
        self._heartbeat = 0
        self._balance_streamer = None

        # listen to its service
        self.service.add_listener(self)

        # streaming
        self.setup_streaming()

    def setup_streaming(self):
        self._streamable = Streamable(self.service.monitor_service, Streamable.STREAM_TRADER, "status", self.name)
        self._streamable.add_member(StreamMemberInt('ping'))
        self._streamable.add_member(StreamMemberInt('conn'))

        # account asset/margin balance streams
        self._balance_streamer = Streamable(self.service.monitor_service, Streamable.STREAM_STRATEGY_TRADE,
                                            self.name, self.name)
        self._balance_streamer.add_member(StreamMemberTraderBalance('account-balance'))

    def stream(self):
        if self._streamable:
            self._streamable.publish()

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

    def symbols_ids(self):
        """
        Returns the complete list containing market-ids, their alias and their related symbol name.
        """
        names = []

        with self._mutex:
            for k, market in self._markets.items():
                names.append(market.market_id)

                if market.symbol and market.symbol != market.market_id:
                    names.append(market.symbol)

            names.sort()

        return names

    def find_market(self, symbol_or_market_id):
        """
        Return market from its market-id or name or symbol.
        """
        if not symbol_or_market_id:
            return None

        market = self._markets.get(symbol_or_market_id)
        if market:
            return market

        # or look with mapping of the name
        for k, mark in self._markets.items():
            if symbol_or_market_id == mark.market_id or symbol_or_market_id == mark.symbol:
                return mark

        return None

    def has_market(self, market_id):
        with self._mutex:
            return market_id in self._markets

    #
    # processing
    #

    def pre_run(self):
        Terminal.inst().message("Running trader %s..." % self._name)
        self.connect()

    def post_run(self):
        Terminal.inst().message("Joining trader %s..." % self._name)
        self.disconnect()
        Terminal.inst().message("Trader %s stopped." % self._name)

    def post_update(self):
        if len(self._signals) > Trader.MAX_SIGNALS:
            # saturation of the signal message queue
            Terminal.inst().warning("Trader %s has more than %s waiting signals, could ignore some market data !" % (
                self.name, Trader.MAX_SIGNALS), view='status')

        # streaming
        try:
            now = time.time()
            if now - self._heartbeat >= 1.0:
                if self._streamable:
                    self._streamable.member('ping').update(int(now*1000))

                self._heartbeat = now
        except Exception as e:
            error_logger.error(repr(e))

        self.stream()

    def update(self):
        """
        Update command and position.
        Thread safe method.
        """

        # performed async, but in case of backtesting update is called synchronously to avoid time derivation
        # of the two processes.
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
        # commands processing
        # @deprecated was used to do not have the possibility to trigger manually a social copy signal (expiration)
        #

        if self._commands:
            i = 0
            now = time.time()

            with self._mutex:
                for command in self._commands:
                    # remove commands older than 180 seconds
                    if now - command['timestamp'] > Trader.PURGE_COMMANDS_DELAY:
                        del self._commands[i]

                    i += 1

        return True

    def _purge_commands(self):
        """
        Purge older commands.
        Not trade safe method.
        """
        if len(self._commands) > Trader.MAX_COMMANDS_QUEUE:
            size = len(self._commands) - Trader.MAX_COMMANDS_QUEUE
            self._commands = self._commands[size:]

    def command(self, command_type, data):
        """
        Some parts are mutex some others are not.
        """
        if command_type == Trader.COMMAND_INFO:
            return self.cmd_trader_info(data)
        elif command_type == Trader.COMMAND_TRADER_FROZE_ASSET_QUANTITY:
            return self.cmd_trader_froze_asset_quantity(data)
        elif command_type == Trader.COMMAND_TICKER_MEMSET:
            return self.cmd_trader_ticker_memset(data)
        elif command_type == Trader.COMMAND_CLOSE_MARKET:
            return self.cmd_close_market(data)
        elif command_type == Trader.COMMAND_CLOSE_ALL_MARKET:
            return self.cmd_close_all_market(data)
        elif command_type == Trader.COMMAND_CANCEL_ALL_ORDER:
            return self.cmd_cancel_all_order(data)
        elif command_type == Trader.COMMAND_SELL_ALL_ASSET:
            return self.cmd_sell_all_asset(data)
        elif command_type == Trader.COMMAND_CANCEL_ORDER:
            return self.cmd_cancel_order(data)

        return None

    def ping(self, timeout):
        self._ping = (0, None, True)

    def pong(self, timestamp, pid, watchdog_service, msg):
        if msg:
            # display trader activity
            if self.connected:
                Terminal.inst().action("Trader worker %s is alive %s" % (self._name, msg), view='content')
            else:
                Terminal.inst().action("Trader worker %s is alive but waiting for (re)connection %s" % (
                    self._name, msg), view='content')

        if watchdog_service:
            watchdog_service.service_pong(pid, timestamp, msg)

    #
    # global information
    #

    def has_margin(self, market_id, quantity, price):
        """
        Return True for a margin trading if the account have sufficient free margin.
        """
        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

            if margin:
                return self.account.margin_balance >= margin

        return False

    def has_quantity(self, asset_name, quantity):
        """
        Return True if a given asset has a minimum quantity.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
        to check if an order can be created
        """
        with self._mutex:
            asset = self._assets.get(asset_name)

            if asset:
                return asset.free >= quantity

        return False

    def get_needed_margin(self, market_id, quantity, price):
        """
        Return computed required margin for a particular market, quantity and price.
        """
        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

            return margin

        return 0.0

    #
    # ordering
    #

    def set_ref_order_id(self, order):
        """
        Generate a new reference order id to be setup before calling create order, else a default one wil be generated.
        Generating it before is a preferred way to correctly manange order in strategy.
        @param order A valid or on to set the ref order id.
        @note If the given order already have a ref order id no change is made.
        """
        if order and not order.ref_order_id:
            # order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid5(uuid.NAMESPACE_DNS, 'siis.com').bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            return order.ref_order_id

        return None

    def create_order(self, order, market_or_instrument):
        """
        Create an order. The symbol of the order must be on of the trader instruments.
        @note This call depend of the state of the connector.
        """
        return 0

    def cancel_order(self, order_id, market_or_instrument):
        """
        Cancel an existing order. The symbol of the order must be on of the trader instruments.
        @note This call depend of the state of the connector.
        """
        return 0

    def cancel_all_orders(self, market_or_instrument):
        """
        Cancel any existing order for a specific market.
        """
        return False

    def close_position(self, position_id, market_or_instrument, direction, quantity, market=True, limit_price=None):
        """
        Close an existing position.
        
        @param position_id Unique position identifier on broker.
        @param market_or_instrument Market of Instrument related object.
        @param direction Direction of the position to close.
        @param quantity Quantity of the position to close or reduce.
        @param market If true close at market
        @param limit_price If Not market close at this limit price

        @note This call depend of the state of the connector.
        """
        return False

    def modify_position(self, position_id, market_or_instrument, stop_loss_price=None, take_profit_price=None):
        """
        Modify the stop loss or take profit of a position.
        @note This call depend of the state of the connector.
        """
        return False

    def order_info(self, order_id, market_or_instrument):
        """
        Retrieve the detail of an order.
        """
        return None

    #
    # global accessors
    #

    def orders(self, market_id):
        """
        Get actives order for a market id.
        """
        return []

    def get_order(self, order_id):
        order = None

        with self._mutex:
            order = self._orders.get(order_id)
            if order:
                order = copy.copy(order)

        return order

    def find_order(self, ref_order_id):
        result = None

        with self._mutex:
            for oid, order in self._orders.items():
                if order.ref_order_id == ref_order_id:
                    result = copy.copy(order)
                    break

        return result

    def market(self, market_id, force=False):
        """
        Market data for a market id.
        @param market_id
        @param force True to force request and cache update.
        """
        # with self._mutex:
        return self._markets.get(market_id)

        # return None

    def asset(self, symbol):
        """
        Get asset for symbol.
        """
        # with self._mutex:
        return self._assets.get(symbol)

    def assets_names(self):
        """
        List of managed assets.
        """
        assets = []

        with self._mutex:
            assets = list(self._assets.keys())

        return assets

    def has_asset(self, symbol):
        """
        Is trader has a specific asset.
        """
        return symbol in self._assets

    def positions(self, market_id):
        """
        Get actives positions for a market id.
        @deprecated
        """
        return []

    def get_position(self, position_id):
        """
        Return a copy of the trader position if exists else None.
        """
        position = None

        with self._mutex:
            if self._positions.get(position_id):
                position = copy.copy(self._positions.get(position_id))

        return position

    #
    # signals
    #

    def receiver(self, signal):
        if signal.source == Signal.SOURCE_WATCHER:
            if signal.source_name != self._name:
                # only interested by the watcher of the same name
                return

            if signal.signal_type == Signal.SIGNAL_MARKET_DATA:
                # if not self.has_market(signal.data[0]):
                if not signal.data[0] in self._markets:
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

        elif signal.source == Signal.SOURCE_TRADER:
            # in fact it comes from the DB service but request in self trader name
            if signal.signal_type not in (Signal.SIGNAL_ASSET_DATA, Signal.SIGNAL_ASSET_DATA_BULK):
                # non interested by others signals
                return 

            # signal of interest
            self._signals.append(signal)

    #
    # connection slots
    #

    def on_watcher_connected(self, watcher_name):
        logger.info("Trader %s joined %s watcher connection." % (self.name, watcher_name))

        # stream connectivity status
        if self._streamable:
            self._streamable.member('conn').update(1)

    def on_watcher_disconnected(self, watcher_name):
        logger.warning("Trader %s loosing %s watcher connection." % (self.name, watcher_name))

        # stream connectivity status
        if self._streamable:
            self._streamable.member('conn').update(-1)

    #
    # account slots
    #

    @Runnable.mutexed
    def on_account_updated(self, balance, free_margin, unrealized_pnl, currency, risk_limit):
        """
        Update account details.
        """
        self.account.set_balance(balance)
        # self.account.set_net_worth(balance)
        self.account.set_used_margin(balance - free_margin)
        self.account.set_unrealized_profit_loss(unrealized_pnl)

        if currency:
            self.account.set_currency(currency)

        if risk_limit is not None:
            self.account.set_risk_limit(risk_limit)

        # stream
        self.notify_balance_update(
            self.timestamp,
            self.account.currency, free_margin,
            self.account.margin_balance, balance,
            unrealized_pnl,
            self.account.margin_level)

    #
    # positions slots
    #

    @Runnable.mutexed
    def on_position_opened(self, market_id, position_data, ref_order_id):
        market = self._markets.get(market_id)
        if market is None:
            # not interested by this market
            return

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
        market = self._markets.get(market_id)
        if market is None:
            # not interested by this market
            return

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
        """
        @param market_id str Unique market identifier
        @param order_data dict Normalized object
        @param ref_order_id valid str or None
        """
        market = self._markets.get(market_id)
        if market is None:
            # not interested by this market
            return

        if order_data['id'] not in self._orders:
            # or could be sometimes be added previously during create_order process at success result
            order = Order(self, order_data['symbol'])
            order.set_order_id(order_data['id'])

            if ref_order_id:
                # if a reference order id is defined, take it
                order.set_ref_order_id(ref_order_id)

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
        """
        @param market_id str Unique market identifier
        @param order_data dict Normalized object
        @param ref_order_id valid str or None
        """
        market = self._markets.get(market_id)
        if market is None:
            # not interested by this market
            return

        order = self._orders.get(order_data['id'])
        if order:
            # update price, stop-price, stop-loss, take-profit, quantity if necessary
            order.quantity = order_data['quantity']

            order.price = order_data.get('price')
            order.stop_price = order_data.get('stop-price')

            order.stop_loss = order_data.get('stop-loss')
            order.take_profit = order_data.get('take-profit')

    @Runnable.mutexed
    def on_order_deleted(self, market_id, order_id, ref_order_id):
        """
        @param market_id str Unique market identifier
        @param order_id str Unique order identifier
        @param ref_order_id valid str or None
        """
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_rejected(self, market_id, ref_order_id):
        """
        @param market_id str Unique market identifier
        @param ref_order_id valid str
        """
        pass

    @Runnable.mutexed
    def on_order_canceled(self, market_id, order_id, ref_order_id):
        """
        @param market_id str Unique market identifier
        @param order_id str Unique order identifier
        @param ref_order_id valid str or None
        """
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_traded(self, market_id, order_data, ref_order_id):
        """
        @param market_id str Unique market identifier
        @param order_data dict Normalized object, with updated values
        @param ref_order_id valid str or None
        """
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

            if order_data.get('fully-filled'):
                # fully filled mean deleted too
                del self._orders[order.order_id]

    #
    # asset slots
    #       

    def on_assets_loaded(self, assets):
        pass

    def on_asset_updated(self, asset_name, locked, free):
        # stream
        precision = None
        price = None
        quote = None

        with self._mutex:
            asset = self.asset(asset_name)
            if asset is not None:
                precision = asset.precision
                price = asset.price
                quote = asset.quote

        self.notify_asset_update(self.timestamp, asset_name, free, locked, free+locked, precision, price, quote)

    #
    # market slots
    #

    @Runnable.mutexed
    def on_update_market(self, market_id, tradable, last_update_time, bid, ask, base_exchange_rate,
                         contract_size=None, value_per_pip=None, vol24h_base=None, vol24h_quote=None):
        """
        Update bid, ask, base exchange rate and last update time of a market.
        Take care this method is not thread safe. Use it with the trader mutex or exclusively in the same thread.
        """
        market = self._markets.get(market_id)
        if market is None:
            # not interested by this market
            return

        if bid:
            # defined and not 0
            market.bid = bid

        if ask:
            # defined and not 0
            market.ask = ask

        if base_exchange_rate is not None:
            market.base_exchange_rate = base_exchange_rate

        if last_update_time:
            # defined and not 0
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
        @param market_id str Valid market identifier
        @return float Last watched price or None if missing market.
        """
        price = None

        with self._mutex:
            market = self.market(market_id)
            if market:
                price = market.price

        return price

    def history_price(self, market_id, timestamp=None):
        """
        Return the price for a particular timestamp or the last if not defined.
        @param market_id str Valid market identifier
        @param timestamp flat Valid second timestamp or if None then prefers the method last_price.
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
                logger.warning("Trader %s cannot found price history for %s at %s" % (
                    self._name, market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
        else:
            # last price
            market = self.market(market_id)
            if market:
                price = market.price

            if price is None:
                logger.warning("Trader %s cannot found last price for %s because no market was found" % (
                    self._name, market_id,))

        return price

    #
    # display views
    #

    def markets_table(self, style='', offset=None, limit=None, col_ofs=None, group=None, ordering=None):
        """
        Returns a table of any followed markets.
        """
        columns = ('Market', 'Symbol', 'Base', 'Quote', 'Rate', 'Type', 'Unit', 'Status', 'PipMean', 'PerPip',
                   'Lot', 'Contract', 'Min Size', 'Max Size', 'Step Size', 'Min Price', 'Max Price', 'Step Price',
                   'Min Notional', 'Max Notional', 'Step Notional', 'Leverage', 'Base ER')
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            markets = list(self._markets.values())
            total_size = (len(columns), len(markets))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(markets)

            limit = offset + limit

            markets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)
            markets = markets[offset:limit]

            for market in markets:
                status = Color.colorize_cond("Open" if market.is_open else "Close", market.is_open, style=style,
                                             true=Color.GREEN, false=Color.RED)

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
                    market.min_size or '-',
                    market.max_size or '-',
                    market.step_size or '-',
                    market.min_price or '-',
                    market.max_price or '-',
                    market.step_price or '-',
                    market.min_notional or '-',
                    market.max_notional or '-',
                    market.step_notional or '-',
                    "%.2f" % (1.0 / market.margin_factor if market.margin_factor > 0.0 else 1.0),
                    "%.g" % market.base_exchange_rate
                )

                data.append(row[0:2] + row[2+col_ofs:])

        return columns[0:2] + columns[2+col_ofs:], data, total_size

    def markets_tickers_table(self, style='', offset=None, limit=None, col_ofs=None, prev_timestamp=None,
                              group=None, ordering=None):
        """
        Returns a table of any followed markets tickers.
        """
        columns = ('Market', 'Symbol', 'Mid', 'Bid', 'Ask', 'Spread', 'Vol24h base', 'Vol24h quote',
                   'Time', 'Change(%)')
        total_size = (len(columns), 0)
        data = []
        now = time.time()

        with self._mutex:
            markets = list(self._markets.values())
            total_size = (len(columns), len(markets))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(markets)

            limit = offset + limit

            if group:
                markets.sort(key=lambda x: x.price, reverse=True if ordering else False)
            else:
                markets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)

            markets = markets[offset:limit]

            for market in markets:
                # recent = market.recent(self.timestamp - 0.5 if not prev_timestamp else prev_timestamp)
                recent = market.previous(-2)
                if recent:
                    mid = Color.colorize_updn(market.format_price(market.price), (recent[1]+recent[2])*0.5,
                                              market.price, style=style)
                    bid = Color.colorize_updn(market.format_price(market.bid), recent[1], market.bid, style=style)
                    ask = Color.colorize_updn(market.format_price(market.ask), recent[2], market.ask, style=style)
                    spread = Color.colorize_updn(market.format_spread(market.spread),
                                                 market.spread, recent[2] - recent[1], style=style)
                else:
                    mid = market.format_price(market.price)
                    bid = market.format_price(market.bid)
                    ask = market.format_price(market.ask)
                    spread = market.format_spread(market.spread)

                if market.vol24h_quote:
                    # @todo could be configured
                    low = 0
                    if market.quote in ('USD', 'EUR', 'ZEUR', 'ZUSD', 'ZCAD', 'ZJPY', 'USDT', 'PAX', 'DAI',
                                        'USDC', 'USDS', 'BUSD', 'TUSD'):
                        low = 500000
                    elif market.quote in ('BTC', 'XBT', 'XXBT'):
                        low = 100
                    elif market.quote in ('ETH', 'XETH'):
                        low = 5000
                    elif market.quote in ('BNB',):
                        low = 50000

                    vol24h_quote = Color.colorize_cond("%.2f" % market.vol24h_quote, market.vol24h_quote < low,
                                                       style=style, true=Color.YELLOW, false=Color.WHITE)
                else:
                    vol24h_quote = '-'  # charmap.HOURGLASS

                if market.last_update_time > 0:
                    last_timestamp = datetime.fromtimestamp(market.last_update_time).strftime("%H:%M:%S")

                    # color ticker/depth since last receive (>15m, >30m)
                    if self.timestamp - market.last_update_time > 60*30.0:
                        last_timestamp = Color.colorize(last_timestamp, Color.RED, style)
                    elif self.timestamp - market.last_update_time > 60*15.0:
                        last_timestamp = Color.colorize(last_timestamp, Color.ORANGE, style)
                    else:
                        last_timestamp = Color.colorize(last_timestamp, Color.GREEN, style)
                else:
                    last_timestamp = '-'  # charmap.HOURGLASS

                # relative change in percent
                if not market.last_mem:
                    market.mem_set()

                relative_change = (market.price - market.last_mem) / market.last_mem * 100.0 if market.last_mem else 0

                if relative_change != 0.0:
                    relative_change = Color.colorize_cond("%.2f" % relative_change, relative_change > 0,
                                                          style=style, true=Color.GREEN, false=Color.RED)

                    relative_change += " since %s" % str(timedelta(seconds=int(now - market.last_mem_timestamp)))

                row = (
                     market.market_id,
                     market.symbol,
                     mid,
                     bid,
                     ask,
                     spread,
                     market.format_quantity(market.vol24h_base) if market.vol24h_base else '-',  # charmap.HOURGLASS,
                     vol24h_quote,
                     last_timestamp,
                     relative_change)

                data.append(row[0:2] + row[2+col_ofs:])

        return columns[0:2] + columns[2+col_ofs:], data, total_size

    def assets_table(self, style='', offset=None, limit=None, col_ofs=None, filter_low=True, group=None, ordering=None):
        """
        Returns a table of any non empty assets.
        """
        columns = ('Asset', 'Locked', 'Free', 'Total', 'Avg price', 'Change', 'Change %', 'P/L', 'Quote', 'Pref Market')
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            assets = [asset for asset in self._assets.values() if asset.quantity > 0.0]
            total_size = (len(columns), len(assets))

            if offset is None:
                offset = 0

            if limit is None:
                limit = len(assets)

            limit = offset + limit

            if group:
                assets.sort(key=lambda x: x.quantity, reverse=True if ordering else False)
            else:
                assets.sort(key=lambda x: x.symbol, reverse=True if ordering else False)

            assets = assets[offset:limit]

            for asset in assets:
                # use the most appropriate market
                market_id = asset.market_ids[0] if asset.market_ids else asset.symbol+asset.quote if asset.quote else None
                market = self._markets.get(market_id)

                change = ""
                change_percent = ""
                profit_loss = ""

                if market:
                    locked = market.format_quantity(asset.locked)
                    free = market.format_quantity(asset.free)
                    quantity = market.format_quantity(asset.quantity)

                    if market.bid and asset.price:
                        change = market.format_price(market.bid - asset.price) + market.quote_display or market.quote
                        change_percent = (market.bid - asset.price) / asset.price * 100.0 if asset.price else 0.0

                        if change_percent > 0.0:
                            change_percent = Color.colorize("%.2f" % change_percent, Color.GREEN, style)
                        elif change_percent < 0.0:
                            change_percent = Color.colorize("%.2f" % change_percent, Color.RED, style)
                        else:
                            change_percent = "%.2f" % change_percent

                    if asset.quantity > 0.0:
                        profit_loss = market.format_price(asset.profit_loss)

                        if asset.profit_loss > 0.0:
                            if profit_loss:
                                profit_loss = Color.colorize(profit_loss, Color.GREEN, style)
                        elif asset.profit_loss < 0.0:
                            if profit_loss:
                                profit_loss = Color.colorize(profit_loss, Color.RED, style)

                        profit_loss += market.quote_display or market.quote
                else:
                    locked = "%.8f" % asset.locked
                    free = "%.8f" % asset.free
                    quantity = "%.8f" % asset.quantity

                row = (
                    asset.symbol,
                    locked,
                    free,
                    quantity,
                    "%s%s" % (asset.format_price(asset.price), asset.quote) if asset.price else '-',  # charmap.HOURGLASS,
                    change or '-',
                    change_percent or '-',
                    profit_loss or '-',
                    asset.quote or '-',
                    asset.market_ids[0] if asset.market_ids else '-'
                )

                data.append(row[0:1] + row[1+col_ofs:])

        return columns[0:1] + columns[1+col_ofs:], data, total_size

    def account_table(self, style='', offset=None, limit=None, col_ofs=None):
        """
        Returns a table of any followed markets.
        """
        columns = ('Broker', 'Account', 'Username', 'Email', 'Asset', 'Free Asset', 'Balance', 'Margin',
                   'Level', 'Net worth', 'Risk limit', 'Unrealized P/L', 'Asset U. P/L')
        data = []

        with self._mutex:
            if offset is None:
                offset = 0

            if limit is None:
                limit = 1

            limit = offset + limit

            cd = self.account.currency_display or self.account.currency

            asset_balance = self.account.format_price(self._account.asset_balance) + cd
            free_asset_balance = self.account.format_price(self._account.free_asset_balance) + cd
            balance = self.account.format_price(self._account.balance) + cd
            margin_balance = self.account.format_price(self._account.margin_balance) + cd
            net_worth = self.account.format_price(self._account.net_worth) + cd
            risk_limit = self.account.format_price(self._account.risk_limit) + cd
            upnl = self.account.format_price(self._account.profit_loss) + cd
            asset_upnl = self.account.format_price(self._account.asset_profit_loss) + cd

            if (self.account.currency != self.account.alt_currency and self._account.currency_ratio != 1.0 and
                    self._account.currency_ratio > 0.0):
                acd = self.account.alt_currency_display or self.account.alt_currency

                asset_balance += " (%s)" % self.account.format_price(
                    self._account.asset_balance * self._account.currency_ratio) + acd
                free_asset_balance += " (%s)" % self.account.format_price(
                    self._account.free_asset_balance * self._account.currency_ratio) + acd
                balance += " (%s)" % self.account.format_price(
                    self._account.balance * self._account.currency_ratio) + acd
                margin_balance += " (%s)" % self.account.format_price(
                    self._account.margin_balance * self._account.currency_ratio) + acd
                net_worth += " (%s)" % self.account.format_alt_price(
                    self._account.net_worth * self._account.currency_ratio) + acd
                risk_limit += " (%s)" % self.account.format_price(
                    self._account.risk_limit * self._account.currency_ratio) + acd
                upnl += " (%s)" % self.account.format_alt_price(
                    self._account.profit_loss * self._account.currency_ratio) + acd
                asset_upnl += " (%s)" % self.account.format_alt_price(
                    self._account.asset_profit_loss * self._account.currency_ratio) + acd

            row = (
                self.name,
                self._account.name,
                self._account.username,
                self._account.email,
                asset_balance,
                free_asset_balance,
                balance,
                margin_balance,
                "%.2f%%" % (self.account.margin_level * 100.0),
                net_worth,
                risk_limit,
                upnl,
                asset_upnl
            )

            if offset < 1 and limit > 0:
                data.append(row[0:2] + row[2+col_ofs:])

        return columns[0:2] + columns[2+col_ofs:], data, (len(columns), 1)

    def get_active_orders(self):
        """
        Generate and return an array of all active orders :
            symbol: str market identifier
            id: int order identifier
            refid: int ref order identifier
        """
        results = []

        with self._mutex:
            try:
                for k, order in self._orders.items():
                    market = self._markets.get(order.symbol)
                    if market:
                        results.append({
                            'mid': market.market_id,
                            'sym': market.symbol,
                            'id': order.order_id,
                            'refid': order.ref_order_id,
                            'ct': order.created_time,
                            'tt': order.transact_time,
                            'd': order.direction_to_str(),
                            'ot': order.order_type_to_str(),
                            'l': order.leverage,
                            'q': market.format_quantity(order.quantity),
                            'op': market.format_price(order.price) if order.price else "",
                            'sp': market.format_price(order.stop_price) if order.stop_price else "",
                            'sl': market.format_price(order.stop_loss) if order.stop_loss else "",
                            'tp': market.format_price(order.take_profit) if order.take_profit else "",
                            'tr': "No",
                            'xq': market.format_quantity(order.executed),
                            'ro': order.reduce_only,
                            'he': order.hedging,
                            'po': order.post_only,
                            'co': order.close_only,
                            'mt': order.margin_trade,
                            'tif': order.time_in_force_to_str(),
                            'pt': order.price_type_to_str(),
                            'key': order.key
                        })
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return results

    def get_active_positions(self):
        """
        Generate and return an array of all active positions :
            symbol: str market identifier
            id: int position identifier
            et: float entry UTC timestamp
            xt: float exit UTC timestamp
            d: str 'long' or 'short'
            l: str leverage
            tp: str formatted take-profit price
            sl: str formatted stop-loss price
            tr: str trailing stop distance or None
            rate: float profit/loss rate
            q: float size qty
            aep: average entry price
            axp: average exit price
            pl: position unrealized profit loss rate
            pnl: position unrealized profit loss
            mpl: position unrealized profit loss rate at market
            mpnl: position unrealized profit loss at market
            pnlcur: trade profit loss currency
            key: user key
        """
        results = []

        with self._mutex:
            try:
                for k, position in self._positions.items():
                    market = self._markets.get(position.symbol)
                    if market:
                        results.append({
                            'mid': market.market_id,
                            'sym': market.symbol,
                            'id': position.position_id,
                            'et': position.created_time,
                            'xt': position.closed_time,
                            'd': position.direction_to_str(),
                            'l': position.leverage,
                            'aep': market.format_price(position.entry_price) if position.entry_price else "",
                            'axp': market.format_price(position.exit_price) if position.exit_price else "",
                            'q': market.format_quantity(position.quantity),
                            'tp': market.format_price(position.take_profit) if position.take_profit else "",
                            'sl': market.format_price(position.stop_loss) if position.stop_loss else "",
                            'tr': "Yes" if position.trailing_stop else "No",
                            # 'tr-dist': market.format_price(position.trailing_stop_distance) if position.trailing_stop_distance else None,
                            'pl': position.profit_loss_rate,
                            'pnl': market.format_price(position.profit_loss),
                            'mpl': position.profit_loss_market_rate,
                            'mpnl': market.format_price(position.profit_loss_market),
                            'pnlcur': position.profit_loss_currency,
                            'cost': market.format_quantity(position.position_cost(market)),
                            'margin': market.format_quantity(position.margin_cost(market)),
                            'key': position.key
                        })
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return results

    def positions_stats_table(self, style='', offset=None, limit=None, col_ofs=None, quantities=False,
                              percents=False, datetime_format='%y-%m-%d %H:%M:%S'):
        """
        Returns a table of any active positions.
        """
        columns = ['Symbol', '#', charmap.ARROWUPDN, 'x', 'P/L(%)', 'SL', 'TP', 'TR', 'Entry date', 'Avg EP',
                   'Exit date', 'Avg XP', 'UPNL', 'Cost', 'Margin', 'Key']

        if quantities:
            columns += ['Qty']

        columns = tuple(columns)
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            try:
                positions = self.get_active_positions()
                total_size = (len(columns), len(positions))

                if offset is None:
                    offset = 0

                if limit is None:
                    limit = len(positions)

                limit = offset + limit

                positions.sort(key=lambda x: x['et'])
                positions = positions[offset:limit]

                for t in positions:
                    direction = Color.colorize_cond(charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN,
                                                    t['d'] == "long", style=style, true=Color.GREEN, false=Color.RED)

                    aep = float(t['aep']) if t['aep'] else 0.0
                    sl = float(t['sl']) if t['sl'] else 0.0
                    tp = float(t['tp']) if t['tp'] else 0.0

                    if t['pl'] < 0:  # loss
                        cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.RED, style=style)
                        pnl = Color.colorize("%s%s" % (t['pnl'], t['pnlcur']), Color.RED, style=style)
                    elif t['pl'] > 0:  # profit
                        cr = Color.colorize("%.2f" % (t['pl']*100.0), Color.GREEN, style=style)
                        pnl = Color.colorize("%s%s" % (t['pnl'], t['pnlcur']), Color.GREEN, style=style)
                    else:  # equity
                        cr = "0.0"
                        pnl = "%s%s" % (t['pnl'], t['pnlcur'])

                    if t['d'] == 'long' and aep:
                        slpct = (sl - aep) / aep
                        tppct = (tp - aep) / aep
                    elif t['d'] == 'short' and aep:
                        slpct = (aep - sl) / aep
                        tppct = (aep - tp) / aep
                    else:
                        slpct = 0
                        tppct = 0

                    row = [
                        t['sym'],
                        t['id'],
                        direction,
                        "%.2f" % t['l'] if t['l'] else '-',
                        cr,
                        "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                        "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                        t['tr'],
                        datetime.fromtimestamp(t['et']).strftime(datetime_format) if t['et'] > 0 else "",
                        t['aep'],
                        datetime.fromtimestamp(t['xt']).strftime(datetime_format) if t['xt'] > 0 else "",
                        t['axp'],
                        pnl,
                        t['cost'],
                        t['margin'],
                        t['key']
                    ]

                    # @todo xx / market.base_exchange_rate and pnl_currency

                    if quantities:
                        row.append(t['q'])

                    data.append(row[0:4] + row[4+col_ofs:])

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return columns[0:4] + columns[4+col_ofs:], data, total_size

    def active_orders_table(self, style='', offset=None, limit=None, col_ofs=None, quantities=False,
                            percents=False, datetime_format='%y-%m-%d %H:%M:%S', group=None, ordering=None):
        """
        Returns a table of any active orders.
        """
        columns = ['Symbol', '#', 'ref #', charmap.ARROWUPDN, 'Type', 'x', 'Limit', 'Stop', 'SL', 'TP',
                   'TR', 'Created date', 'Transac date', 'Reduce', 'Post', 'Hedge', 'Close', 'Margin',
                   'TIF', 'Price', 'Key']

        if quantities:
            columns += ['Qty']
            columns += ['Exec']

        columns = tuple(columns)
        total_size = (len(columns), 0)
        data = []

        with self._mutex:
            try:
                orders = self.get_active_orders()
                total_size = (len(columns), len(orders))

                if offset is None:
                    offset = 0

                if limit is None:
                    limit = len(orders)

                limit = offset + limit

                if group:
                    orders.sort(key=lambda x: x['sym'] + str(x['ct']), reverse=True if ordering else False)
                else:
                    orders.sort(key=lambda x: x['ct'], reverse=True if ordering else False)

                orders = orders[offset:limit]

                for t in orders:
                    direction = Color.colorize_cond(
                        charmap.ARROWUP if t['d'] == "long" else charmap.ARROWDN, t['d'] == "long",
                        style=style, true=Color.GREEN, false=Color.RED)

                    op = float(t['op']) if t['op'] else 0.0
                    sl = float(t['sl']) if t['sl'] else 0.0
                    tp = float(t['tp']) if t['tp'] else 0.0

                    if t['d'] == 'long' and op:
                        slpct = (sl - op) / op if sl else 0.0
                        tppct = (tp - op) / op if tp else 0.0
                    elif t['d'] == 'short' and op:
                        slpct = (op - sl) / op if sl else 0.0
                        tppct = (op - tp) / op if tp else 0.0
                    else:
                        slpct = 0
                        tppct = 0

                    row = [
                        t['sym'],
                        t['id'],
                        t['refid'],
                        direction,
                        t['ot'],
                        "%.2f" % t['l'] if t['l'] else '-',
                        t['op'],
                        t['sp'],
                        "%s (%.2f)" % (t['sl'], slpct * 100) if percents else t['sl'],
                        "%s (%.2f)" % (t['tp'], tppct * 100) if percents else t['tp'],
                        t['tr'],
                        datetime.fromtimestamp(t['ct']).strftime(datetime_format) if t['ct'] > 0 else "",
                        datetime.fromtimestamp(t['tt']).strftime(datetime_format) if t['tt'] > 0 else "",
                        "Yes" if t['ro'] else "No",
                        "Yes" if t['po'] else "No",
                        "Yes" if t['he'] else "No",
                        "Yes" if t['co'] else "No",
                        "Yes" if t['mt'] else "No",
                        t['tif'],
                        t['pt'],
                        t['key']
                    ]

                    if quantities:
                        row.append(t['q'])
                        row.append(t['xq'])

                    data.append(row[0:2] + row[2+col_ofs:])

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return columns[0:2] + columns[2+col_ofs:], data, total_size

    #
    # commands
    #

    def cmd_trader_info(self, data):
        """
        Info on the global trader instance.
        """
        results = {
            'messages': [],
            'error': False
        }

        # @todo

        return results

    def cmd_trader_froze_asset_quantity(self, data):
        """
        Lock a quantity of an asset to be not available for trading.
        """
        results = {
            'messages': [],
            'error': False
        }

        asset_name = data.get('asset')
        quantity = data.get('quantity', -1.0)

        if not asset_name:
            Terminal.inst().error("Asset to froze quantity must be specified")

        if quantity < 0.0:
            Terminal.inst().error("Asset quantity to froze must be specified and greater or equal to zero")

        # @todo

        return results

    def cmd_trader_ticker_memset(self, data):
        """
        Memorize the last market price for any or a specific market.
        """
        results = {
            'messages': [],
            'error': False
        }

        market_id = data.get('market-id')

        if market_id:
            market = self.find_market(market_id)

            if market is None:
                results['messages'].append("Market %s not found !" % market_id)
                results['error'] = True
                return results

            with self._mutex:
                market.mem_set()
        else:
            with self._mutex:
                for market_id, market in self._markets.items():
                    market.mem_set()

        return results

    def cmd_close_market(self, data):
        """
        Manually close a specified position at market now.
        """
        results = {
            'messages': [],
            'error': False
        }

        position_id = None
        direction = 0
        quantity = 0.0
        market = None

        with self._mutex:
            for k, position in self._positions.items():
                if position.key == data['key']:
                    position_id = position.position_id
                    direction = position.direction
                    quantity = position.quantity

                    market = self.market(position.symbol)

        if position_id:
            # query close position
            if market:
                try:
                    self.close_position(position_id, market, direction, quantity, True, None)
                    Terminal.inst().action("Closing position %s..." % (position_id, ))
                except Exception as e:
                    error_logger.error(repr(e))
            else:
                Terminal.inst().error("No market found to close position %s" % (position_id, ))
        else:
            Terminal.inst().error("No position found to close for key %s" % (data['key'], ))

        return results

    def cmd_close_all_market(self, data):
        """
        Manually close any positions related to this account/trader at market now.
        """
        results = {
            'messages': [],
            'error': False
        }

        positions = []

        with self._mutex:
            for k, position in self._positions.items():
                market = self.market(position.symbol)

                if market:
                    positions.append((position.position_id, market, position.direction, position.quantity))
                else:
                    Terminal.inst().error("No market found to close position %s..." % position.position_id)

        for position in positions:
            # query close position
            try:
                self.close_position(position[0], position[1], position[2], position[3], True, None)
                Terminal.inst().action("Closing position %s..." % position.position_id)
            except Exception as e:
                error_logger.error(repr(e))

        return results

    def cmd_cancel_all_order(self, data):
        results = {
            'messages': [],
            'error': False
        }

        orders = []

        # None or a specific market only
        market_id = data.get('market-id')
        options = data.get('options')

        with self._mutex:
            for k, order in self._orders.items():
                market = self.market(order.symbol)

                if market is None:
                    Terminal.inst().error("No market found to cancel order %s..." % (order.order_id, ))
                    continue

                if market_id and market_id != market.market_id:
                    # ignored market-id
                    continue

                if options:
                    # ("spot-entry", "spot-exit", "margin-entry", "margin-exit")
                    accept = False

                    if "spot-entry" in options:
                        if market.has_spot and order.direction > 0:
                            accept = True

                    if "spot-exit" in options:
                        if market.has_spot and order.direction < 0:
                            accept = True

                    if "margin-entry" in options:
                        if market.has_margin and not order.reduce_only and not order.close_only:
                            accept = True

                    if "margin-exit" in options:
                        if market.has_margin and order.reduce_only or order.close_only:
                            accept = True

                    if not accept:
                        continue               

                orders.append((order.order_id, market))

        for order in orders:
            # query cancel order
            try:
                if self.cancel_order(order[0], order[1]) > 0:
                    Terminal.inst().action("Cancel order %s..." % order[0])
            except Exception as e:
                error_logger.error(repr(e))

        return results

    def cmd_sell_all_asset(self, data):
        results = {
            'messages': [],
            'error': False
        }

        assets = []

        with self._mutex:
            try:
                for k, asset in self._assets.items():
                    # query create order to sell any asset quantity
                    # try over the primary currency, then over the alt one
                    # user could have to to it in two phase
                    market = None

                    if k == self._account.currency:
                        # don't sell account currency
                        continue

                    for market_id in asset.market_ids:
                        m = self.market(market_id)

                        if m.quote == self._account.currency:
                            market = m  # first choice
                            break

                        # elif m.quote == self._account.alt_currency:
                        #     market = m  # second choice

                    if asset.free <= 0.0:
                        continue

                    if market:
                        assets.append((asset.symbol, market, asset.free))
                    else:
                        Terminal.inst().error("No market found to sell all for asset %s..." % (asset.symbol, ))

                for asset in assets:
                    market = asset[1]

                    order = Order(self, market.market_id)
                    order.direction = Order.SHORT
                    order.order_type = Order.ORDER_MARKET
                    order.quantity = asset[2]

                    # generated a reference order id
                    self.set_ref_order_id(order)

                    if self.create_order(order, market) > 0:
                        Terminal.inst().action("Create order %s to sell all of %s on %s..." % (
                            order.order_id, asset[0], market.market_id))
                    else:
                        Terminal.inst().action("Rejected order to sell all of %s on %s..." % (
                            asset[0], market.market_id))
            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

        return results

    def cmd_cancel_order(self, data):
        orders = []

        market_id = data.get('market-id')
        order_id = data.get('order-id')

        market = self.market(market_id)

        if market is None:
            Terminal.inst().error("No market found to cancel order %s..." % (order_id, ))

        # query cancel order
        try:
            if self.cancel_order(order_id, market) > 0:
                Terminal.inst().action("Cancel order %s..." % order_id)
        except Exception as e:
            error_logger.error(repr(e))

    #
    # stream
    #

    def notify_balance_update(self, timestamp, asset, free, locked, total, upnl=None, margin_level=None):
        if self._balance_streamer:
            try:
                self._balance_streamer.member('account-balance').update({
                    'asset': asset,
                    'type': 'margin',
                    'free': free,
                    'locked': locked,
                    'total': total,
                    'upnl': upnl,
                    'margin-level': margin_level,
                    'precision': 2,  # @todo from account.currency_precision
                }, timestamp)

                self._balance_streamer.publish()
            except Exception as e:
                logger.error(repr(e))

    def notify_asset_update(self, timestamp, asset, free, locked, total, precision, price, quote):
        if self._balance_streamer:
            try:
                self._balance_streamer.member('account-balance').update({
                    'asset': asset,
                    'type': 'asset',
                    'free': free,
                    'locked': locked,
                    'total': total,
                    'upnl': None,
                    'margin-level': None,
                    'precision': precision,
                    'price': price,
                    'quote': quote,
                }, timestamp)

                self._balance_streamer.publish()

            except Exception as e:
                logger.error(repr(e))

    #
    # helpers
    #

    def fetch_assets_balances(self):
        """
        Dumps balance/asset update notify.
        """
        assets = {}

        with self._mutex:
            for k, asset in self._assets.items():
                assets[asset.symbol] = {
                    'type': 'asset',
                    'free': asset.free,
                    'locked': asset.locked,
                    'total': asset.quantity,
                    'upnl': 0.0,
                    'margin-level': 0.0,
                    'precision': asset.precision
                }

            # append account margin if available
            if self.account.account_type & self.account.TYPE_MARGIN == self.account.TYPE_MARGIN:
                assets[self.account.currency] = {
                    'type': 'margin',
                    'free': self.account.margin_balance,
                    'locked': self.account.balance - self.account.margin_balance,
                    'total': self.account.net_worth or self.account.balance,
                    'upnl': self.account.profit_loss,
                    'margin-level': self.account.margin_level,
                    'precision': self.account.currency_precision
                }

            if self.account.account_type & self.account.TYPE_ASSET == self.account.TYPE_ASSET:
                assets['Spot'] = {
                    'type': 'asset',
                    'free': self.account.free_asset_balance,
                    'locked': self.account.asset_balance - self.account.free_asset_balance,
                    'total': self.account.asset_balance,
                    'upnl': 0.0,
                    'margin-level': 0.0,
                    'precision': self.account.currency_precision
                }

        return assets
