# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader order

from common.keyed import Keyed


class Order(Keyed):
    """
    Order for execution on a trader.

    @todo GTD could be distinct and need an expiry_time field
    @todo __slots__
    """

    __slots__ = "_order_id", "_ref_order_id", "_trader", "_symbol", "_created_time", "_position_id", "_quantity", \
        "_transact_time", "_executed", "_fully_filled", "_avg_price", "_direction", "_order_type", \
        "_price", "_stop_price", "_stop_mode", "_stop_loss", "_take_profit", "_reduce_only", "_hedging", \
        "_post_only", "_close_only", "_price_type", "_margin_trade", "_leverage", "_time_in_force", \
        "_trailing_stop", "_reason"

    LONG = 1    # long direction
    SHORT = -1  # short direction

    ORDER_MARKET = 0                # market order
    ORDER_LIMIT = 1                 # entry or exit limit
    ORDER_STOP = 2                  # stop at market
    ORDER_STOP_LIMIT = 3            # stop limit order
    ORDER_TAKE_PROFIT = 4           # take profit market
    ORDER_TAKE_PROFIT_LIMIT = 5     # take profit limit
    ORDER_TRAILING_STOP_MARKET = 6  # trailing stop market

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

    REASON_UNDEFINED = 0            # Undefined
    REASON_OK = 1                   # Order successfully open
    REASON_INSUFFICIENT_FUNDS = 2   # Insufficient asset quantity to open order
    REASON_INSUFFICIENT_MARGIN = 3  # Insufficient margin to open order
    REASON_ERROR = 4                # General error or unspecified
    REASON_INVALID_ARGS = 5         # Invalid order arguments
    REASON_DENIED = 6               # User or API key or sign not allowed
    REASON_UNREACHABLE_SERVICE = 7  # Service is currently or permanently unreachable
    REASON_RATE_LIMIT = 8           # API rate limit exceeded
    REASON_ORDER_LIMIT = 9          # Number of order limit exceeded
    REASON_POSITION_LIMIT = 10      # Number of position limit exceeded
    REASON_INVALID_NONCE = 11       # Wrong nonce value
    REASON_CANCEL_ONLY = 12         # Cancel only mode
    REASON_POST_ONLY = 13           # Post-only mode

    def __init__(self, trader, symbol):
        super().__init__()

        self._order_id = ""
        self._ref_order_id = ""

        self._trader = trader
        self._symbol = symbol
        self._created_time = 0.0

        self._position_id = None

        self._quantity = 0.0  # total order quantity to realize

        self._transact_time = 0.0   # last qty execution (traded) timestamp
        self._executed = 0.0        # executed quantity if partially (executed = quantity when completed)
        self._fully_filled = False  # true if executed qty represent the ordered qty (eventually minus fees)
        self._avg_price = 0.0       # average executed price

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

        self._trailing_stop = False
        self._reason = Order.REASON_UNDEFINED

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
    def fully_filled(self):
        return self._fully_filled

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

    @property
    def reason(self):
        return self._reason

    #
    # Setters
    #

    def set_order_id(self, order_id):
        """Defines the result order id and set reason as OK."""
        self._order_id = order_id
        self._reason = Order.REASON_OK

    def set_ref_order_id(self, ref_order_id):
        self._ref_order_id = ref_order_id

    def set_position_id(self, position_id):
        self._position_id = position_id

    @quantity.setter
    def quantity(self, quantity):
        self._quantity = quantity

    @executed.setter
    def executed(self, executed):
        self._executed = executed
    
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

    @reason.setter
    def reason(self, reason):
        self._reason = reason

    def set_executed(self, quantity, fully_filled, avg_price):
        self._executed = quantity
        self._fully_filled = fully_filled
        self._avg_price = avg_price

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

    # def can_retry(self):
    #     """
    #     If the reason of fail to order is a temporary raison return True
    #     """
    #     return self._reason in (
    #         Order.REASON_INVALID_NONCE, Order.REASON_RATE_LIMIT, Order.REASON_UNREACHABLE_SERVICE,
    #         Order.REASON_POST_ONLY, Order.REASON_CANCEL_ONLY)

    def order_type_to_str(self):
        return order_type_to_str(self._order_type)

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

    def reason_to_str(self):
        if self._reason == Order.REASON_UNDEFINED:
            return "undefined"
        elif self._reason == Order.REASON_OK:
            return "success"
        elif self._reason == Order.REASON_INSUFFICIENT_FUNDS:
            return "insufficient-funds"
        elif self._reason == Order.REASON_INSUFFICIENT_MARGIN:
            return "insufficient-margin"
        elif self._reason == Order.REASON_ERROR:
            return "error"
        elif self._reason == Order.REASON_INVALID_ARGS:
            return "invalid-arguments"
        elif self._reason == Order.REASON_DENIED:
            return "denied"
        elif self._reason == Order.REASON_UNREACHABLE_SERVICE:
            return "unreachable"
        elif self._reason == Order.REASON_UNDEFINED:
            return "undefined"
        elif self._reason == Order.REASON_RATE_LIMIT:
            return "rate-limit"
        elif self._reason == Order.REASON_ORDER_LIMIT:
            return "order-limit"
        elif self._reason == Order.REASON_POSITION_LIMIT:
            return "position-limit"
        elif self._reason == Order.REASON_INVALID_NONCE:
            return "invalid-nonce"
        elif self._reason == Order.REASON_POST_ONLY:
            return "post-only"
        elif self._reason == Order.REASON_CANCEL_ONLY:
            return "cancel-only"
        else:
            return "undefined"


def order_type_to_str(order_type):
    if order_type == Order.ORDER_MARKET:
        return "market"
    elif order_type == Order.ORDER_LIMIT:
        return "limit"
    elif order_type == Order.ORDER_STOP:
        return "stop"
    elif order_type == Order.ORDER_STOP_LIMIT:
        return "stop-limit"
    elif order_type == Order.ORDER_TAKE_PROFIT:
        return "take-profit"
    elif order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
        return "take-profit-limit"
    elif order_type == Order.ORDER_TRAILING_STOP_MARKET:
        return "trailing-stop-market"

    return "unknown"
