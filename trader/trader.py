# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader base class

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Dict

if TYPE_CHECKING:
    from watcher.watcher import Watcher
    from .account import Account
    from .market import Market
    from instrument.instrument import Instrument

import time
import copy
import base64
import uuid
import collections

from datetime import datetime

from .command.tradercmdstream import cmd_trader_stream
from .command.tradercmdinfo import cmd_trader_info
from .command.tradercmdfrozeassetquantity import cmd_trader_froze_asset_quantity
from .command.tradercmdtradertickermemset import cmd_trader_ticker_memset
from .command.tradercmdclosemarket import cmd_close_market
from .command.tradercmdcloseallmarket import cmd_close_all_market
from .command.tradercmdcancelallorder import cmd_cancel_all_order
from .command.tradercmdsellallasset import cmd_sell_all_asset
from .command.tradercmdcancelorder import cmd_cancel_order

from common.signal import Signal

from .asset import Asset
from .order import Order
from .position import Position

from monitor.streamable import Streamable, StreamMemberInt, StreamMemberTraderBalance
from common.runnable import Runnable

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


class Trader(Runnable):
    """
    Trader base class to specialize per broker.

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
    COMMAND_EXPORT = 4                        # export trader state (supported for paper-trader only)
    COMMAND_IMPORT = 5                        # import previous trader state (supported for paper-trader only)
    COMMAND_STREAM = 6                        # subscribe/unsubscribe to trade/tick/ohlc/depth/market-update streaming

    # order commands
    COMMAND_CLOSE_MARKET = 110                # close a managed or unmanaged position at market now
    COMMAND_CLOSE_ALL_MARKET = 111            # close any positions of this account at market now
    COMMAND_CANCEL_ALL_ORDER = 112            # cancel any pending orders
    COMMAND_SELL_ALL_ASSET = 113              # sell any quantity of asset at market price
    COMMAND_CANCEL_ORDER = 114                # cancel a specific order

    _orders: Dict[str, Order]
    _positions: Dict[str, Position]
    _assets: Dict[str, Asset]

    def __init__(self, name: str, service):
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
    def account(self) -> Account:
        return self._account
    
    @property
    def service(self):
        return self._service

    @property
    def name(self) -> str:
        return self._name

    @property
    def watcher(self) -> Watcher:
        return self._watcher

    @property
    def paper_mode(self) -> bool:
        """True for not real trader"""
        return False

    def set_timestamp(self, timestamp: float):
        """
        Used on backtesting by the strategy.
        """
        self._timestamp = timestamp

    @property
    def timestamp(self) -> float:
        """
        Current timestamp or backtesting time.
        """
        return time.time()

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self) -> bool:
        return False

    @property
    def authenticated(self) -> bool:
        return False

    def symbols_ids(self) -> List[str]:
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

    def find_market(self, symbol_or_market_id: str) -> Union[Market, None]:
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

    def command(self, command_type: int, data: dict) -> Union[dict, None]:
        """
        Some parts are mutex some others are not.
        """
        if command_type == Trader.COMMAND_INFO:
            return cmd_trader_info(self, data)
        elif command_type == Trader.COMMAND_TRADER_FROZE_ASSET_QUANTITY:
            return cmd_trader_froze_asset_quantity(self, data)
        elif command_type == Trader.COMMAND_TICKER_MEMSET:
            return cmd_trader_ticker_memset(self, data)
        elif command_type == Trader.COMMAND_CLOSE_MARKET:
            return cmd_close_market(self, data)
        elif command_type == Trader.COMMAND_CLOSE_ALL_MARKET:
            return cmd_close_all_market(self, data)
        elif command_type == Trader.COMMAND_CANCEL_ALL_ORDER:
            return cmd_cancel_all_order(self, data)
        elif command_type == Trader.COMMAND_SELL_ALL_ASSET:
            return cmd_sell_all_asset(self, data)
        elif command_type == Trader.COMMAND_CANCEL_ORDER:
            return cmd_cancel_order(self, data)
        elif command_type == Trader.COMMAND_EXPORT:
            return self.cmd_export(data)  # override
        elif command_type == Trader.COMMAND_IMPORT:
            return self.cmd_import(data)  # override
        elif command_type == Trader.COMMAND_STREAM:
            return cmd_trader_stream(self, data)

        return None

    def ping(self, timeout: float):
        self._ping = (0, None, True)

    def pong(self, timestamp: float, pid: int, watchdog_service, msg: str):
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

    def has_margin(self, market_id: str, quantity: float, price: float) -> bool:
        """
        Return True for a margin trading if the account have sufficient free margin.
        """
        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

            if margin:
                return self.account.margin_balance >= margin

        return False

    def has_quantity(self, asset_name: str, quantity: float) -> bool:
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

    def get_needed_margin(self, market_id: str, quantity: float, price: float) -> float:
        """
        Return computed required margin for a particular market, quantity and price.
        """
        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

            return margin

    #
    # ordering
    #

    def set_ref_order_id(self, order: Order) -> Union[str, None]:
        """
        Generate a new reference order id to be setup before calling create order, else a default one wil be generated.
        Generating it before is a preferred way to correctly manage order in strategy.
        @param order A valid or on to set the ref order id.
        @note If the given order already have a ref order id no change is made.
        """
        if order and not order.ref_order_id:
            # order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid5(uuid.NAMESPACE_DNS, 'siis.com').bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('/', '_').replace('+', '0'))
            return order.ref_order_id

        return None

    def create_order(self, order: Order, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Create an order. The symbol of the order must be on of the trader instruments.
        @note This call depend of the state of the connector.
        """
        return 0

    def cancel_order(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Cancel an existing order. The symbol of the order must be on of the trader instruments.
        @note This call depend of the state of the connector.
        """
        return 0

    def cancel_all_orders(self, market_or_instrument: Union[Market, Instrument]) -> bool:
        """
        Cancel any existing order for a specific market.
        """
        return False

    def close_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                       direction: int, quantity: float, market: bool = True,
                       limit_price: Optional[float] = None) -> bool:
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

    def modify_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                        stop_loss_price: Optional[float] = None, take_profit_price: Optional[float] = None) -> bool:
        """
        Modify the stop loss or take profit of a position.
        @note This call depend of the state of the connector.
        """
        return False

    def order_info(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> Union[dict, None]:
        """
        Retrieve the detail of an order.
        """
        return None

    #
    # global accessors
    #

    def orders(self, market_id: str) -> List:
        """
        Get actives order for a market id.
        @deprecated
        """
        return []

    def get_order(self, order_id: str) -> Union[Order, None]:
        """
        Return a copy of the trader order if exists else None.
        @param order_id:
        @return:
        """
        with self._mutex:
            order = self._orders.get(order_id)
            if order:
                order = copy.copy(order)

        return order

    def find_order(self, ref_order_id: str) -> Union[Order, None]:
        """
        @deprecated
        @param ref_order_id: str Reference order id
        @return: Order
        """
        result = None

        with self._mutex:
            for oid, order in self._orders.items():
                if order.ref_order_id == ref_order_id:
                    result = copy.copy(order)
                    break

        return result

    def market(self, market_id: str, force: bool = False) -> Union[Market, None]:
        """
        Market data for a market id.
        @param market_id
        @param force True to force request and cache update.
        @return Market or None
        @note This method is no thread safe.
        """
        # with self._mutex:
        return self._markets.get(market_id)

    def asset(self, symbol: str) -> Union[Asset, None]:
        """
        Get asset for symbol.
        @param symbol str Asset name
        @return Asset or None
        @note This method is no thread safe.
        """
        # with self._mutex:
        return self._assets.get(symbol)

    def assets_names(self) -> List[str]:
        """
        List of managed assets.
        """
        with self._mutex:
            assets = list(self._assets.keys())

        return assets

    def has_asset(self, symbol: str) -> bool:
        """
        Is trader has a specific asset.
        """
        return symbol in self._assets

    def positions(self, market_id: str) -> List[Position]:
        """
        Get actives positions for a market id.
        @deprecated
        """
        return []

    def get_position(self, position_id: str) -> Union[Position, None]:
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

    def receiver(self, signal: Signal):
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

    def on_watcher_connected(self, watcher_name: str):
        logger.info("Trader %s joined %s watcher connection." % (self.name, watcher_name))

        # stream connectivity status
        if self._streamable:
            self._streamable.member('conn').update(1)

    def on_watcher_disconnected(self, watcher_name: str):
        logger.warning("Trader %s loosing %s watcher connection." % (self.name, watcher_name))

        # stream connectivity status
        if self._streamable:
            self._streamable.member('conn').update(-1)

    #
    # account slots
    #

    @Runnable.mutexed
    def on_account_updated(self, balance: float, free_margin: float, unrealized_pnl: float, currency: str,
                           risk_limit: float):
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
    def on_position_opened(self, market_id: str, position_data: dict, ref_order_id: str):
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
    def on_position_updated(self, market_id: str, position_data: dict, ref_order_id: str):
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
    def on_position_amended(self, market_id: str, position_data: dict, ref_order_id: str):
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
    def on_position_deleted(self, market_id: str, position_data: dict, ref_order_id: str):
        # delete the position from the dict
        if self._positions.get(position_data['id']):
            del self._positions[position_data['id']]

    #
    # order slots
    #

    @Runnable.mutexed
    def on_order_opened(self, market_id: str, order_data: dict, ref_order_id: str):
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
    def on_order_updated(self, market_id: str, order_data: dict, ref_order_id: str):
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
    def on_order_deleted(self, market_id: str, order_id: str, ref_order_id: str):
        """
        @param market_id str Unique market identifier
        @param order_id str Unique order identifier
        @param ref_order_id valid str or None
        """
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_rejected(self, market_id: str, ref_order_id: str):
        """
        @param market_id str Unique market identifier
        @param ref_order_id valid str
        """
        pass

    @Runnable.mutexed
    def on_order_canceled(self, market_id: str, order_id: str, ref_order_id: str):
        """
        @param market_id str Unique market identifier
        @param order_id str Unique order identifier
        @param ref_order_id valid str or None
        """
        if order_id in self._orders:
            del self._orders[order_id]

    @Runnable.mutexed
    def on_order_traded(self, market_id: str, order_data: dict, ref_order_id: str):
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

    def on_assets_loaded(self, assets: Union[List[Asset], None]):
        pass

    def on_asset_updated(self, asset_name: str, locked: float, free: float):
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
    def on_update_market(self, market_id: str, tradable: bool, last_update_time: float, bid: float, ask: float,
                         base_exchange_rate: float,
                         contract_size: Optional[float] = None, value_per_pip: Optional[float] = None,
                         vol24h_base: Optional[float] = None, vol24h_quote: Optional[float] = None):
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

    def last_price(self, market_id: str) -> Union[float, None]:
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

    def history_price(self, market_id: str, timestamp: Optional[float] = None) -> Union[float, None]:
        """
        Return the price for a particular timestamp or the last if not defined.
        @param market_id str Valid market identifier
        @param timestamp float Valid second timestamp or if None then prefers the method last_price.
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
    # stream
    #

    def notify_balance_update(self, timestamp: float, asset: str, free: float, locked: float, total: float,
                              upnl: float = None, margin_level: float = None):
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

    def notify_asset_update(self, timestamp: float, asset: str, free: float, locked: float, total: float,
                            precision: int, price: float, quote: str):
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

    #
    # persistence
    #

    def cmd_export(self, data: dict):
        """
        Persistence to file.
        """
        return {}

    def cmd_import(self, data: dict):
        """
        Previous state from file.
        """
        return {}
