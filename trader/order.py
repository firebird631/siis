# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader order

from common.keyed import Keyed


class Order(Keyed):
    """
    Order for execution on a trader.

    @deprecated copied_position_id must be managed at social strategy level.
    """

    LONG = 1    # long direction
    SHORT = -1  # short direction

    ORDER_MARKET = 0             # market order
    ORDER_LIMIT = 1              # entry or exit limit
    ORDER_STOP = 2               # stop at market
    ORDER_STOP_LIMIT = 3         # stop limit order
    ORDER_TAKE_PROFIT = 4        # take profit market
    ORDER_TAKE_PROFIT_LIMIT = 5  # take profit limit

    STOP_NONE = 0
    STOP_TRAILING = 1    # trailing stop
    STOP_GUARANTEED = 2  # guaranteed stop

    PRICE_LAST = 0
    PRICE_INDEX = 1
    PRICE_MARK = 2

    TIME_IN_FORCE_GTC = 0  # Good till cancelled
    TIME_IN_FORCE_IOC = 1  # Immediate or cancel
    TIME_IN_FORCE_FOK = 2  # Fill or kill
    TIME_IN_FORCE_GTD = 3  # Good til date

    def __init__(self, trader, symbol):
        super().__init__()

        self._order_id = ""
        self._ref_order_id = ""

        self._trader = trader
        self._symbol = symbol
        self._created_time = 0.0

        self._author = None
        self._copied_position_id = None

        self._position_id = None

        self._quantity = 0.0  # total order quantity to realize

        self._transact_time = 0.0   # last qty execution (traded) timestamp
        self._executed = 0.0        # executed quantity if partially (executed = quantity when completed)

        self._direction = 0
        self._order_type = Order.ORDER_MARKET
        self._price = None       # limit price
        self._stop_price = None  # stop price (for stop, stop limit, take profit, take profit limit orders types)

        self._stop_mode = Order.STOP_NONE
        self._stop_loss = None
        self._take_profit = None

        self._reduce_only = False
        self._hedging = False
        self._post_only = True
        self._close_only = False
        self._price_type = Order.PRICE_LAST

        self._margin_trade = False
        self._leverage = 1.0

        self._time_in_force = Order.TIME_IN_FORCE_GTC

    #
    # Getters
    #

    @property
    def quantity(self):
        return self._quantity
    
    @property
    def executed(self):
        return self._executed
    
    @property
    def order_id(self):
        return self._order_id

    @property
    def ref_order_id(self):
        return self._ref_order_id

    @property
    def position_id(self):
        return self._position_id

    @property
    def copied_position_id(self):
        return self._copied_position_id
    
    @property
    def author(self):
        return self._author

    @property
    def symbol(self):
        return self._symbol

    @property
    def direction(self):
        return self._direction
    
    @property
    def created_time(self):
        return self._created_time

    @property
    def take_profit(self):
        return self._take_profit
    
    @property
    def stop_loss(self):
        return self._stop_loss
    
    @property
    def price(self):
        return self._price

    @property
    def stop_price(self):
        return self._stop_price

    @property
    def trailing_stop(self):
        return self._trailing_stop
    
    @property
    def leverage(self):
        return self._leverage

    @property
    def margin_trade(self):
        return self._margin_trade

    @property
    def reduce_only(self):
        return self._reduce_only

    @property
    def hedging(self):
        return self._hedging
    
    @property
    def post_only(self):
        return self._post_only
    
    @property
    def order_type(self):
        return self._order_type
    
    @property
    def transact_time(self):
        return self._transact_time
    
    @property
    def close_only(self):
        return self._close_only
    
    @property
    def price_type(self):
        return self._price_type

    @property
    def time_in_force(self):
        return self._time_in_force

    #
    # Setters
    #

    def set_order_id(self, order_id):
        self._order_id = order_id

    def set_ref_order_id(self, ref_order_id):
        self._ref_order_id = ref_order_id

    def set_copied_position_id(self, position_id):
        self._copied_position_id = position_id

    def set_position_id(self, position_id):
        self._position_id = position_id

    @quantity.setter
    def quantity(self, quantity):
        self._quantity = quantity

    @executed.setter
    def executed(self, executed):
        self._executed = executed

    @author.setter
    def author(self, author):
        self._author = author
    
    @take_profit.setter
    def take_profit(self, take_profit):
        self._take_profit = take_profit

    @stop_loss.setter
    def stop_loss(self, stop_loss):
        self._stop_loss = stop_loss

    @price.setter
    def price(self, price):
        self._price = price

    @stop_price.setter
    def stop_price(self, stop_price):
        self._stop_price = stop_price

    @leverage.setter
    def leverage(self, leverage):
        self._leverage = leverage

    @margin_trade.setter
    def margin_trade(self, margin_trade):
        self._margin_trade = margin_trade

    @direction.setter
    def direction(self, direction):
        self._direction = direction

    @reduce_only.setter
    def reduce_only(self, state):
        self._reduce_only = state

    @hedging.setter
    def hedging(self, state):
        self._hedging = state

    @post_only.setter
    def post_only(self, state):
        self._post_only = state

    @trailing_stop.setter
    def trailing_stop(self, state):
        self._trailing_stop = state

    @close_only.setter
    def close_only(self, state):
        self._close_only = state
 
    @price_type.setter
    def price_type(self, price_type):
        self._price_type = price_type

    @order_type.setter
    def order_type(self, order_type):
        self._order_type = order_type

    @transact_time.setter
    def transact_time(self, transact_time):
        self._transact_time = transact_time

    @created_time.setter
    def created_time(self, created_time):
        self._created_time = created_time

    @time_in_force.setter
    def time_in_force(self, time_in_force):
        self._time_in_force = time_in_force

    #
    # Helpers
    #

    def direction_to_str(self):
        return 'long' if self._direction == self.LONG else 'short'

    def is_market(self):
        """
        Returns true if the order would be executed as market.
        """
        return self._order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT)

    def order_type_to_str(self):
        if self._order_type == Order.ORDER_MARKET:
            return "market"
        elif self._order_type == Order.ORDER_LIMIT:
            return "limit"
        elif self._order_type == Order.ORDER_STOP:
            return "stop"
        elif self._order_type == Order.ORDER_STOP_LIMIT:
            return "stop-limit"
        elif self._order_type == Order.ORDER_TAKE_PROFIT:
            return "take-profit"
        elif self._order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            return "take-profit-limit"

        return "unknown"

    def time_in_force_to_str(self):
        if self._time_in_force == Order.TIME_IN_FORCE_GTC:
            return "good-till-cancelled"
        elif self._order_type == Order.TIME_IN_FORCE_GTD:
            return "good-till-date"
        elif self._order_type == Order.TIME_IN_FORCE_FOK:
            return "fill-or-kill"
        elif self._order_type == Order.TIME_IN_FORCE_IOC:
            return "immediate-or-cancel"

        return "unknown"

    def price_type_to_str(self):
        if self._price_type == Order.PRICE_LAST:
            return "last"
        elif self._price_type == Order.PRICE_INDEX:
            return "index"
        elif self._price_type == Order.PRICE_MARK:
            return "mark"

        return "unknown"
