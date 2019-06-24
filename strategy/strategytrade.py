# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade base class

from notifier.signal import Signal
from common.utils import timeframe_to_str

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

    To have partial TP uses multiples trades with different exit levels. Partial TP must be part of your strategy,
    then for a TP50% use two trade with half of the size, the first having a TP at 50% price.    
    """

    TRADE_BUY_SELL = 0    # spot/asset trade
    TRADE_MARGIN = 1      # individual margin trade position (potentially compatible with hedging markets)
    TRADE_IND_MARGIN = 2  # indivisible margin trade position (incompatible with hedging markets), currently found on crypto

    STATE_NEW = 0
    STATE_REJECTED = 1
    STATE_DELETED = 2
    STATE_CANCELED = 3
    STATE_OPENED = 4
    STATE_PARTIALLY_FILLED = 5
    STATE_FILLED = 6

    MANAGER_NONE = 0
    MANAGER_STRATEGY = 1
    MANAGER_USER = 2

    def __init__(self, trade_type, timeframe):
        self._trade_type = trade_type
        
        self._entry_state = StrategyTrade.STATE_NEW
        self._exit_state = StrategyTrade.STATE_NEW

        self._timeframe = timeframe  # timeframe that have given this trade
        
        self._conditions = {}   # dict containing the conditions giving the trade for data analysis and machine learning
        self._operations = []   # list containing the operation to process during the trade for semi-automated trading
        self._manager = StrategyTrade.MANAGER_STRATEGY   # who is responsible of the TP & SL dynamic adjustement (strategy or user defined operations)

        self._open_time = 0

        self.id = 0      # unique trade identifier
        self.p = 0.0     # entry price (average)
        self.tp = 0.0    # take-profit price
        self.sl = 0.0    # stop-loss price
        self.dir = 0     # direction (1 long, -1 short)
        self.t = 0       # creation timestamp
        self.q = 0.0     # ordered quantity

        self.e = 0.0     # current filled entry quantity
        self.x = 0.0     # current filled exit quantity (a correctly closed trade must have x == f with f <= q and q > 0)

        self.pl = 0.0    # once closed profit/loss in percent (valid once partially or fully closed)

        self._stats = {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-maker': False,
            'exit-maker': False
        }

    #
    # getters
    #

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
    def created_time(self):
        return self.t

    @property
    def quantity(self):
        return self.q

    @property
    def order_quantity(self):
        return self.q

    @property
    def entry_price(self):
        return self.p

    @property
    def take_profit(self):
        return self.tp
    
    @property
    def stop_loss(self):
        return self.sl

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
    def open_time(self):
        return self._open_time

    @property
    def timeframe(self):
        return self._timeframe

    @property
    def manager(self):
        return self._manager

    #
    # processing
    #

    def open(self, trader, market_id, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Order to open a position or to buy an asset.

        @param trader Trader Valid trader handler.
        @param market_id str Valid market identifier.
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
        if self.e >= self.q and self.x >= self.e:
            # entry fully filled and exit too
            return True

        # if self.e <= 0 and (self._entry_state == StrategyTrade.STATE_CANCELED or self._entry_state == StrategyTrade.STATE_DELETED or self._entry_state == StrategyTrade.STATE_REJECTED):
        #     # can delete a non filled canceled, deleted or rejected entry
        #     return True

        if self.e > 0 and self.x < self.e:
            # entry quantity but exit quantity not fully filled
            return False

        if self._entry_state == StrategyTrade.STATE_NEW or self._entry_state == StrategyTrade.STATE_OPENED:
            # buy order not opened or opened but trade still valid till expiry or cancelation
            return False

        if self.e > 0 and (self._exit_state == StrategyTrade.STATE_NEW or self._exit_state == StrategyTrade.STATE_OPENED):
            # have quantity but sell order not filled
            return False

        return True

    def is_active(self):
        """
        Return true if the trade is active (non-null entry qty, and exit quantity non fully completed).
        """
        if self.e > 0 and self.x < self.e:
            return True

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

        if self._exit_state == StrategyTrade.STATE_CANCELED and self.x <= 0:
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
        return self._exit_state == StrategyTrade.STATE_OPENED or self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED

    def is_closed(self):
        """
        Is trade fully closed (all qty sold).
        """
        return self._exit_state == StrategyTrade.STATE_FILLED and self.x >= self.e

    def is_entry_timeout(self, timestamp, timeout):
        """
        Return true if the trade timeout.
        """
        return (self._entry_state == StrategyTrade.STATE_OPENED) and (self.e == 0) and ((timestamp - self.t) >= timeout)

    # def is_exit_timeout(self, timestamp, timeout):
    #     """
    #     Return true if the trade timeout.
    #     """
    #     return (self._exit_state == StrategyTrade.STATE_OPENED) and (self.x == 0) and ((timestamp - self.et) >= timeout)

    def is_valid(self, timestamp, validity):
        """
        Return true if the trade is not expired (signal still acceptable) and entry quantity not fully filled.
        """
        return ((self._entry_state == StrategyTrade.STATE_OPENED or self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED) and
                (self.e < self.q) and ((timestamp - self.created_time) <= validity))

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

    def modify_take_profit(self, trader, market_id, price):
        """
        Create/modify the take-order limit order or position limit.
        """
        return False

    def modify_stop_loss(self, trader, market_id, price):
        """
        Create/modify the stop-loss taker order or position limit.
        """
        return False

    def close(self, trader, market_id):
        """
        Close the position or sell the asset.
        """
        return False

    def order_signal(self, signal_type, data, ref_order_id):
        pass

    def position_signal(self, signal_type, data, ref_order_id):
        pass

    def is_target_order(self, order_id, ref_order_id):
        return False

    def is_target_position(self, position_id, ref_order_id):
        return False

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

    def state_to_str(self):
        """
        Get a string for the state of the trade.

        @note Its not a very precise indicator one some case because we could have partial entry + partial exit.
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
            # an exit order is rejectect but the exit quantity is not fully filled (x < e), this case must be managed
            return 'problem'
        elif self.e < self.q and (self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED or self._entry_state == StrategyTrade.STATE_OPENED):
            # entry order filling until be fully filled or closed (cancel the rest of the entry order, exiting)
            return 'filling'
        elif self.e > 0 and self.x < self.e and (self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED or self._exit_state == StrategyTrade.STATE_OPENED):
            # exit order (close order, take-profit order, stop-loss order) are filling (or position take-profit or position stop-loss)
            return 'closing'
        elif self.e > 0 and self.x >= self.e:
            # exit quantity reached the entry quantity the trade is closed
            return 'closed'
        elif self.e >= self.q:
            # entry quantity reach ordered quantity the entry is filled
            return 'filled'
        elif self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0: 
            return 'canceled'
        else:
            # any others case meaning pending state
            return 'waiting'

    def timeframe_to_str(self):
        return timeframe_to_str(self._timeframe)

    #
    # presistance
    #

    def save(self, trader, market_id):
        """
        Save the trade data to the DB. Related trader and market must be provided.

        @todo Save fields
        @todo Save conditions
        @todo Save statistics
        @todo Save operations
        """
        pass

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
        self._operations.append(trade_operation)

    def remove_operation(self, trade_operation_index):
        del self._operations[trade_operation_index]

    def has_operations(self):
        return len(self._operations) > 0

    #
    # trade signal conditions
    #

    @property
    def conditions(self):
        return self._conditions

    @conditions.setter
    def conditions(self, conditions):
        self._conditions = conditions

    #
    # manager controlling
    #

    @manager.setter
    def manager(self, manager):
        self._manager = manager

    def is_user_managed(self):
        return self._manager == StrategyTrade.MANAGER_USER

    def is_strategy_managed(self):
        return self._manager == StrategyTrade.MANAGER_STRATEGY
