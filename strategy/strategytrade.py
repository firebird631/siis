# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade base class

from datetime import datetime

from notifier.signal import Signal
from common.utils import timeframe_to_str, timeframe_from_str

from trader.order import Order

import logging
logger = logging.getLogger('siis.strategy')


class StrategyTrade(object):
    """
    Strategy trade base abstract class. A trade is related to entry and and one or many exit order.
    It can be created from an automated or manual signal, and having some initial conditions, timeframe, expiry,
    and they are managed according to the policy of a strategy trade manager, or from some other operations added manually
    for semi-automated trading.

    It can only have on entry order. The exit works on the entried quantity. When the entry order is not fully filled,
    the exit order are later adjusted.
    """

    __slots__ = '_trade_type', '_entry_state', '_exit_state', '_closing', '_timeframe', '_operations', '_user_trade', '_next_operation_id', \
                'id', 'dir', 'op', 'oq', 'tp', 'sl', 'aep', 'axp', 'eot', 'xot', 'e', 'x', 'pl', '_stats', 'last_tp_ot', 'last_sl_ot', \
                'exit_trades', '_comment', '_expiry', '_dirty', '_extra'

    VERSION = "1.0.0"

    TRADE_UNDEFINED = -1
    TRADE_BUY_SELL = 0    # spot/asset trade
    TRADE_ASSET = 0
    TRADE_SPOT = 0
    TRADE_MARGIN = 1      # individual margin trade position (potentially compatible with hedging markets)
    TRADE_IND_MARGIN = 2  # indivisible margin trade position (incompatible with hedging markets), currently found on crypto

    STATE_UNDEFINED = -1
    STATE_NEW = 0
    STATE_REJECTED = 1
    STATE_DELETED = 2
    STATE_CANCELED = 3
    STATE_OPENED = 4
    STATE_PARTIALLY_FILLED = 5
    STATE_FILLED = 6

    def __init__(self, trade_type, timeframe):
        self._trade_type = trade_type
        
        self._entry_state = StrategyTrade.STATE_NEW
        self._exit_state = StrategyTrade.STATE_NEW
        self._closing = False
        self._dirty = False        # flag set when the quantity of the entry trade increase and then the exit orders must be updated

        self._timeframe = timeframe  # timeframe that have given this trade

        self._operations = []      # list containing the operation to process during the trade for semi-automated trading
        self._user_trade = False   # true if the user is responsible of the TP & SL adjustement else (default) strategy manage it
        self._comment = ""         # optionnal comment (must be few chars)
        self._expiry = 0           # expiration delay in seconde or 0 if never

        self._next_operation_id = 1

        self.id = 0      # unique trade identifier
        self.dir = 0     # direction (1 long, -1 short)

        self.op = 0.0    # ordered price (limit)
        self.oq = 0.0    # ordered quantity

        self.tp = 0.0    # take-profit price
        self.sl = 0.0    # stop-loss price

        self.aep = 0.0   # average entry price
        self.axp = 0.0   # average exit price

        self.eot = 0     # entry order opened timestamp
        self.xot = 0     # exit order opened timestamp

        self.e = 0.0     # current filled entry quantity
        self.x = 0.0     # current filled exit quantity (a correctly closed trade must have x == f with f <= q and q > 0)

        self.pl = 0.0    # once closed profit/loss in percent (valid once partially or fully closed)

        self.last_tp_ot = [0, 0]
        self.last_sl_ot = [0, 0]

        self.exit_trades = {}  # contain each executed exit trades {<orderId< : (<qty<, <price>)}

        self._stats = {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'limit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'conditions': {}
        }

        self._extra = {}

    #
    # getters
    #

    @classmethod
    def version(cls):
        return cls.VERSION

    @property
    def trade_type(self):
        return self._trade_type

    @property
    def entry_state(self):
        return self._entry_state

    @property
    def exit_state(self):
        return self._exit_state   

    @property
    def direction(self):
        return self.dir
    
    def close_direction(self):
        return -self.dir

    @property
    def entry_open_time(self):
        return self.eot

    @property
    def exit_open_time(self):
        return self.xot

    @property
    def order_quantity(self):
        return self.oq

    @property
    def quantity(self):
        """Synonym for order_quantity"""
        return self.oq

    @property  
    def order_price(self):
        return self.op

    @property
    def take_profit(self):
        return self.tp
    
    @property
    def stop_loss(self):
        return self.sl

    @property
    def entry_price(self):
        return self.aep

    @property
    def exit_price(self):
        return self.axp

    @property
    def exec_entry_qty(self):
        return self.e
    
    @property
    def exec_exit_qty(self):
        return self.x

    @property
    def profit_loss(self):
        return self.pl

    @property
    def timeframe(self):
        return self._timeframe

    @property
    def expiry(self):
        return self._expiry
    
    @expiry.setter
    def expiry(self, expiry):
        self._expiry = expiry

    def set_user_trade(self, user_trade=True):
        self._user_trade = user_trade

    def is_user_trade(self):
        return self._user_trade

    @property
    def last_take_profit(self):
        """Last take-profit order creation/modification timestamp"""
        return self.last_tp_ot

    @property
    def last_stop_loss(self):
        """Last stop-loss order creation/modification timestamp"""
        return self.last_sl_ot

    @property
    def comment(self):
        return self._comment
    
    @comment.setter
    def comment(self, comment):
        self._comment = comment

    @property
    def is_dirty(self):
        return self._dirty

    #
    # processing
    #

    def open(self, trader, instrument, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Order to open a position or to buy an asset.

        @param trader Trader Valid trader handler.
        @param instrument Instrument object.
        @param direction int Order direction (1 or -1)
        @param order_type int Order type (market, limit...)
        @param order_price float Limit order price or None for market
        @param quantity float Quantity in unit of quantity
        @param take_profit float Initial take-profit price or None
        @param stop_loss float Initial stop-loss price or None
        @param leverage float For some brokers leverage multiplier else unused
        @param hedging boolean On margin market if True could open positions of opposites directions
        """
        return False

    def remove(self, trader):
        """
        Remove the trade and related remaining orders.
        """
        pass

    def can_delete(self):
        """
        Because of the slippage once a trade is closed deletion can only be done once all the quantity of the
        asset or the position are executed.
        """
        if self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are fully filled
            return True

        if self._entry_state == StrategyTrade.STATE_REJECTED:
            # entry rejected
            return True

        if (self._entry_state == StrategyTrade.STATE_CANCELED or self._entry_state == StrategyTrade.STATE_DELETED) and self.e <= 0:
            # entry canceled or deleted and empty
            return True

        return False

    def is_active(self):
        """
        Return true if the trade is active (non-null entry qty, and exit quantity non fully completed).
        """
        if self._exit_state == StrategyTrade.STATE_FILLED:
            return False

        return self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED or self._entry_state == StrategyTrade.STATE_FILLED

    def is_opened(self):
        """
        Return true if the entry trade is opened but no qty filled at this moment time.
        """
        return self._entry_state == StrategyTrade.STATE_OPENED

    def is_canceled(self):
        """
        Return true if the trade is not active, canceled or rejected.
        """
        if self._entry_state == StrategyTrade.STATE_REJECTED:
            return True

        if self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0:
            return True

        return False

    def is_opening(self):
        """
        Is entry order in progress.
        """
        return self._entry_state == StrategyTrade.STATE_OPENED or self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED

    def is_closing(self):
        """
        Is close order in progress.
        """
        return self._closing and self._exit_state != StrategyTrade.STATE_FILLED

    def is_closed(self):
        """
        Is trade fully closed (all qty sold).
        """
        return self._exit_state == StrategyTrade.STATE_FILLED

    def is_entry_timeout(self, timestamp, timeout):
        """
        Return true if the trade entry timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return (self._entry_state == StrategyTrade.STATE_OPENED) and (self.e == 0) and (self.eot > 0) and ((timestamp - self.eot) >= timeout)

    def is_trade_timeout(self, timestamp):
        """
        Return true if the trade timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return (
                (self._entry_state in (StrategyTrade.STATE_PARTIALLY_FILLED, StrategyTrade.STATE_FILLED)) and
                (self._expiry > 0.0) and (self.e > 0) and (self.eot > 0) and ((timestamp - self.eot) >= self._expiry)
            )

    def is_valid(self, timestamp, validity):
        """
        Return true if the trade is not expired (signal still acceptable) and entry quantity not fully filled.
        """
        return (
                ((self._entry_state == StrategyTrade.STATE_OPENED or self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED) and
                (validity > 0.0) and ((timestamp - self.entry_open_time) <= validity))
            )

    def cancel_open(self, trader):
        """
        Cancel the entiere or remaining open order.
        """
        return False

    def cancel_close(self, trader):
        """
        Cancel the entiere or remaining close order.
        """
        return False

    def modify_take_profit(self, trader, instrument, price):
        """
        Create/modify the take-order limit order or position limit.
        """
        return False

    def modify_stop_loss(self, trader, instrument, price):
        """
        Create/modify the stop-loss taker order or position limit.
        """
        return False

    def close(self, trader, instrument):
        """
        Close the position or sell the asset.
        """
        return False

    def has_stop_order(self):
        """
        Overrides, must return true if the trade have a broker side stop order, else local trigger stop.
        """
        return False

    def has_limit_order(self):
        """
        Overrides, must return true if the trade have a broker side limit order, else local take-profit stop
        """
        return False

    def has_oco_order(self):
        """
        Overrides, must return true if the trade have a broker side OCO order
        """
        return False

    def support_both_order(self):
        """
        Overrides, must return true if the trader support stop and limit order at the same time
        """
        return False

    #
    # signals
    #

    def order_signal(self, signal_type, data, ref_order_id, instrument):
        pass

    def position_signal(self, signal_type, data, ref_order_id, instrument):
        pass

    def is_target_order(self, order_id, ref_order_id):
        return False

    def is_target_position(self, position_id, ref_order_id):
        return False

    def update_dirty(self):
        pass

    #
    # Helpers
    #

    def direction_to_str(self):
        if self.dir > 0:
            return 'long'
        elif self.dir < 0:
            return 'short'
        else:
            return ''

    def direction_from_str(self, direction):
        if direction == 'long':
            self.dir = 1
        elif direction == 'short':
            self.dir = -1
        else:
            self.dir = 0

    def state_to_str(self):
        """
        Get a string for the state of the trade (only for display usage).
        """
        if self._entry_state == StrategyTrade.STATE_NEW:
            # entry is new, not ordered
            return 'new'
        elif self._entry_state == StrategyTrade.STATE_OPENED:
            # the entry order is created, waiting for filling
            return 'opened'
        elif self._entry_state == StrategyTrade.STATE_REJECTED:
            # the entry order is rejected, trade must be deleted
            return 'rejected'
        elif self._exit_state == StrategyTrade.STATE_REJECTED and self.e > self.x:
            # exit order is rejectect but the exit quantity is not fully filled (x < e), this case must be managed
            return 'problem'
        elif self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # entry order filling until complete
            return 'filling'
        elif self._entry_state == StrategyTrade.STATE_FILLED:
            # entry order completed
            return 'filled'
        elif self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # exit order filling until complete
            return 'closing'           
        elif self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are completed
            return 'closed'
        elif self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0: 
            return 'canceled'
        else:
            # any others case meaning pending state
            return 'waiting'

    def timeframe_to_str(self):
        return timeframe_to_str(self._timeframe)

    def trade_type_to_str(self):
        if self._trade_type == StrategyTrade.TRADE_ASSET:
            return 'asset'
        elif self._trade_type == StrategyTrade.TRADE_MARGIN:
            return 'margin'
        elif self._trade_type == StrategyTrade.TRADE_MARGIN:
            return 'indisible-margin'
        else:
            return "undefined"

    @staticmethod
    def trade_type_from_str(self, trade_type):
        if trade_type == 'asset':
            return StrategyTrade.TRADE_ASSET
        elif trade_type == 'margin':
            return StrategyTrade.TRADE_MARGIN
        elif trade_type == 'ind-margin':
            return StrategyTrade.TRADE_IND_MARGIN
        else:
            return StrategyTrade.TRADE_UNDEFINED

    def trade_state_to_str(self, trade_state):
        if trade_state == StrategyTrade.STATE_NEW:
            return 'new'
        elif self._trade_type == StrategyTrade.STATE_REJECTED:
            return 'rejected'
        elif self._trade_type == StrategyTrade.STATE_DELETED:
            return 'deleted'
        elif self._trade_type == StrategyTrade.STATE_CANCELED:
            return 'canceled'
        elif self._trade_type == StrategyTrade.STATE_OPENED:
            return 'opened'
        elif self._trade_type == StrategyTrade.STATE_PARTIALLY_FILLED:
            return 'partially-filled'
        elif self._trade_type == StrategyTrade.STATE_FILLED:
            return 'filled'
        else:
            return "undefined"

    @staticmethod
    def trade_state_from_str(self, trade_state):
        if trade_state == 'new':
            return StrategyTrade.STATE_NEW
        elif self._trade_type == 'rejected':
            return StrategyTrade.STATE_REJECTED
        elif self._trade_type == 'deleted':
            return StrategyTrade.STATE_DELETED
        elif self._trade_type == 'canceled':
            return StrategyTrade.STATE_CANCELED
        elif self._trade_type == 'opened':
            return StrategyTrade.STATE_OPENED
        elif self._trade_type == 'partially-filled':
            return StrategyTrade.STATE_PARTIALLY_FILLED
        elif self._trade_type == 'filled':
            return StrategyTrade.STATE_FILLED
        else:
            return StrategyTrade.STATE_UNDEFINED

    #
    # presistance
    #

    def dump_timestamp(self, timestamp):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%f')

    def load_timestamp(self, datetime_str):
        if datetime_str:
            return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%f').timestamp()
        else:
            return 0

    def dumps(self):
        """
        Override this method to make a dumps for the persistance.
        @return dict with at least as defined in this method.
        """
        return {
            'version': self.version(),
            'id': self.id,
            'trade': self._trade_type,  #  self.trade_type_to_str(),
            'entry-state': self._entry_state,  #  self.trade_state_to_str(self._entry_state),
            'exit-state': self._exit_state,  # self.trade_state_to_str(self._exit_state),
            'closing': self._closing,
            'timeframe': self._timeframe,  # self.timeframe_to_str(),
            'user-trade': self._user_trade,
            'comment': self._comment,
            'avg-entry-price': self.aep,
            'avg-exit-price': self.axp,
            'take-profit-price': self.tp,
            'stop-loss-price': self.sl,
            'direction': self.dir, # self.direction_to_str(),
            'entry-open-time': self.eot,  # self.dump_timestamp(self.eot),
            'exit-open-time': self.xot,  # self.dump_timestamp(self.xot),
            'order-qty': self.oq,
            'filled-entry-qty': self.e,
            'filled-exit-qty': self.x,
            'profit-loss-rate': self.pl,
            'exit-trades': self.exit_trades,
            'last-take-profit-order-time': self.last_tp_ot,
            'last-stop-loss-order-time': self.last_sl_ot,
            'statistics': self._stats,
            'extra': self._extra,
        }

    def loads(self, data):
        """
        Override this method to make a loads for the persistance model.
        @return True if success.
        """
        self.id = data.get('id', -1)
        self._trade_type = data.get('trade', 0)  # self.trade_type_from_str(data.get('type', ''))
        self._entry_state = data.get('entry-state', 0)  # self.trade_state_from_str(data.get('entry-state', ''))
        self._exit_state = data.get('exit-state', 0)  # self.trade_state_from_str(data.get('exit-state', ''))
        self._closing = data.get('closing', False)
        self._timeframe =  data.get('timeframe', 0)  # timeframe_from_str(data.get('timeframe', '4h'))
        self._user_trade = data.get('user-trade')
        self._comment = data.get('comment', "")

        self._operations = []
        self._next_operation_id = -1

        self.dir = data.get('direction', 0)  # self.direction_from_str(data.get('direction', ''))
        self.oq = data.get('order-qty', 0.0)

        self.tp = data.get('take-profit-price', None)
        self.sl = data.get('stop-loss-price', None)

        self.aep = data.get('avg-entry-price', 0.0)
        self.axp = data.get('avg-exit-price', 0.0)
       
        self.eot = data.get('entry-open-time', 0)  # self.load_timestamp(data.get('entry-open-datetime'))
        self.xot = data.get('exit-open-time', 0)  # self.load_timestamp(data.get('exit-open-datetime'))

        self.e = data.get('filled-entry-qty', 0.0)
        self.x = data.get('filled-exit-qty', 0.0)

        self.pl = data.get('profit-loss-rate', 0.0)

        self.last_tp_ot = data.get('last-take-profit-order-time')
        self.last_sl_ot = data.get('last-stop-loss-order-time')

        self.exit_trades = data.get('exit-trades', {})

        self._stats = data.get('statistics', {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'limit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'conditions': {}
        })

        self._extra = data.get('extra', {})

        return True

    #
    # stats
    #

    def update_stats(self, last_price, timestamp):
        if self.is_active():
            if self.dir > 0:
                if last_price > self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price < self._stats['worst-price'] or not self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

            elif self.dir < 0:
                if last_price < self._stats['best-price'] or not self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price > self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

    def best_price(self):
        return self._stats['best-price']

    def worst_price(self):
        return self._stats['worst-price']

    def best_price_timestamp(self):
        return self._stats['best-timestamp']

    def worst_price_timestamp(self):
        return self._stats['worst-timestamp']

    def get_stats(self):
        return self._stats

    def add_condition(self, name, data):
        self._stats['conditions'][name] = data

    def get_conditions(self):
        return self._stats['conditions']

    def entry_fees(self):
        """Realized entry fees cost (not rate)"""
        return self._stats['entry-fees']

    def entry_fees_rate(self):
        """Realized entry fees rate"""
        if self.e > 0:
            return self._stats['entry-fees'] / self.e

        return 0.0

    def exit_fees(self):
        """Realized exit fees cost (not rate)"""
        return self._stats['exit-fees']

    def exit_fees_rate(self):
        """Realized entry fees rate"""
        if self.x > 0:
            return self._stats['exit-fees'] / self.x

        return 0.0

    def estimate_profit_loss(self, instrument):
        """
        During the trade open, compute an estimation of the unrealized profit/loss rate.
        """
        # estimation at close price
        if self.direction > 0 and self.entry_price > 0:
            profit_loss = (instrument.close_exec_price(self.direction) - self.entry_price) / self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            profit_loss = (self.entry_price - instrument.close_exec_price(self.direction)) / self.entry_price
        else:
            profit_loss = 0.0

        # minus realized entry fees rate
        profit_loss -= self.entry_fees_rate()

        # count the exit fees related to limit order type
        if self._stats['limit-order-type'] in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            profit_loss -= instrument.maker_fee
        elif self._stats['limit-order-type'] in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            profit_loss -= instrument.taker_fee

        return profit_loss

    #
    # extra
    #

    def set(self, key, value):
        """
        Add a key:value paire in the extra member dict of the trade.
        It allow to add you internal trade data, states you want to keep during the live of the trade and even in persistency
        """
        self._extra[key] = value

    def unset(self, key):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)

    #
    # operations
    #

    @property
    def operations(self):
        """
        List all pending/peristants operations
        """
        return self._operations

    def cleanup_operations(self):
        """
        Regenerate the list of operations by removing the finished operations.
        """
        ops = []

        for operation in self._operations:
            if not operation.can_delete():
                ops.append(operation)

        # replace the operations list
        self._operations = ops

    def add_operation(self, trade_operation):
        trade_operation.set_id(self._next_operation_id)
        self._next_operation_id += 1

        self._operations.append(trade_operation)

    def remove_operation(self, trade_operation_id):
        for operation in self._operations:
            if operation.id == trade_operation_id:
                self._operations.remove(operation)
                return True

        return False

    def has_operations(self):
        return len(self._operations) > 0
