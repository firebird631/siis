# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader order

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from trader.trader import Trader

from common.keyed import Keyed


class Order(Keyed):
    """
    Order for execution on a trader.

    @todo GTD could be distinct and need an expiry_time field
    """

    __slots__ = "_order_id", "_ref_order_id", "_trader", "_symbol", "_created_time", "_position_id", "_quantity", \
        "_transact_time", "_executed", "_fully_filled", "_avg_price", "_direction", "_order_type", \
        "_price", "_stop_price", "_stop_mode", "_stop_loss", "_take_profit", "_reduce_only", "_hedging", \
        "_post_only", "_close_only", "_price_type", "_margin_trade", "_leverage", "_time_in_force", \
        "_trailing_stop"

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
    TIME_IN_FORCE_GTD = 3  # Good till date

    REASON_OK = 1                     # Order successfully open
    REASON_UNDEFINED = 0              # Undefined
    REASON_INSUFFICIENT_FUNDS = -1    # Insufficient asset quantity to open order (permanent)
    REASON_INSUFFICIENT_MARGIN = -2   # Insufficient margin to open order (permanent)
    REASON_ERROR = -3                 # General error or unspecified (permanent)
    REASON_INVALID_ARGS = -4          # Invalid order arguments (permanent)
    REASON_DENIED = -5                # User or API key or sign not allowed (permanent)
    REASON_UNREACHABLE_SERVICE = -32  # Service is currently or permanently unreachable (temporary)
    REASON_RATE_LIMIT = -33           # API rate limit exceeded (temporary)
    REASON_ORDER_LIMIT = -34          # Number of order limit exceeded (temporary)
    REASON_POSITION_LIMIT = -35       # Number of position limit exceeded (temporary)
    REASON_INVALID_NONCE = -36        # Wrong nonce value (temporary)
    REASON_CANCEL_ONLY = -37          # Cancel only mode (temporary)
    REASON_POST_ONLY = -38            # Post-only mode (temporary)

    def __init__(self, trader: Trader, symbol: str):
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

    #
    # Getters
    #

    @property
    def trader(self) -> Trader:
        return self._trader

    @property
    def quantity(self) -> float:
        return self._quantity

    @property
    def executed(self) -> float:
        return self._executed

    @property
    def avg_price(self) -> float:
        return self._avg_price

    @property
    def fully_filled(self) -> bool:
        return self._fully_filled

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def ref_order_id(self) -> str:
        return self._ref_order_id

    @property
    def position_id(self) -> Union[str, None]:
        return self._position_id

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def direction(self) -> int:
        return self._direction
    
    @property
    def created_time(self) -> float:
        return self._created_time

    @property
    def take_profit(self) -> Union[float, None]:
        return self._take_profit
    
    @property
    def stop_loss(self) -> Union[float, None]:
        return self._stop_loss
    
    @property
    def price(self) -> Union[float, None]:
        return self._price

    @property
    def stop_price(self) -> Union[float, None]:
        return self._stop_price

    @property
    def trailing_stop(self) -> bool:
        return self._trailing_stop
    
    @property
    def leverage(self) -> float:
        return self._leverage

    @property
    def margin_trade(self) -> bool:
        return self._margin_trade

    @property
    def reduce_only(self) -> bool:
        return self._reduce_only

    @property
    def hedging(self) -> bool:
        return self._hedging
    
    @property
    def post_only(self) -> bool:
        return self._post_only
    
    @property
    def order_type(self) -> int:
        return self._order_type
    
    @property
    def transact_time(self) -> float:
        return self._transact_time
    
    @property
    def close_only(self) -> bool:
        return self._close_only
    
    @property
    def price_type(self) -> int:
        return self._price_type

    @property
    def time_in_force(self) -> int:
        return self._time_in_force

    #
    # Setters
    #

    def set_order_id(self, order_id: str):
        """Defines the result order id and set reason as OK."""
        self._order_id = order_id

    def set_ref_order_id(self, ref_order_id: str):
        self._ref_order_id = ref_order_id

    def set_position_id(self, position_id: str):
        self._position_id = position_id

    @quantity.setter
    def quantity(self, quantity: float):
        self._quantity = quantity

    @executed.setter
    def executed(self, executed: float):
        self._executed = executed
    
    @take_profit.setter
    def take_profit(self, take_profit: float):
        self._take_profit = take_profit

    @stop_loss.setter
    def stop_loss(self, stop_loss: float):
        self._stop_loss = stop_loss

    @price.setter
    def price(self, price: float):
        self._price = price

    @stop_price.setter
    def stop_price(self, stop_price: float):
        self._stop_price = stop_price

    @leverage.setter
    def leverage(self, leverage: float):
        self._leverage = leverage

    @margin_trade.setter
    def margin_trade(self, margin_trade: bool):
        self._margin_trade = margin_trade

    @direction.setter
    def direction(self, direction: int):
        self._direction = direction

    @reduce_only.setter
    def reduce_only(self, state: bool):
        self._reduce_only = state

    @hedging.setter
    def hedging(self, state: bool):
        self._hedging = state

    @post_only.setter
    def post_only(self, state: bool):
        self._post_only = state

    @trailing_stop.setter
    def trailing_stop(self, state: bool):
        self._trailing_stop = state

    @close_only.setter
    def close_only(self, state: bool):
        self._close_only = state

    @price_type.setter
    def price_type(self, price_type: int):
        self._price_type = price_type

    @order_type.setter
    def order_type(self, order_type: int):
        self._order_type = order_type

    @transact_time.setter
    def transact_time(self, transact_time: float):
        self._transact_time = transact_time

    @created_time.setter
    def created_time(self, created_time: float):
        self._created_time = created_time

    @time_in_force.setter
    def time_in_force(self, time_in_force: int):
        self._time_in_force = time_in_force

    def set_executed(self, quantity: float, fully_filled: bool, avg_price: float):
        self._executed = quantity
        self._fully_filled = fully_filled
        self._avg_price = avg_price

    #
    # Helpers
    #

    def direction_to_str(self) -> str:
        return 'long' if self._direction == self.LONG else 'short'

    def is_market(self) -> bool:
        """
        Returns true if the order would be executed as market.
        """
        return self._order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT)

    def order_type_to_str(self) -> str:
        return order_type_to_str(self._order_type)

    def time_in_force_to_str(self) -> str:
        if self._time_in_force == Order.TIME_IN_FORCE_GTC:
            return "good-till-cancelled"
        elif self._order_type == Order.TIME_IN_FORCE_GTD:
            return "good-till-date"
        elif self._order_type == Order.TIME_IN_FORCE_FOK:
            return "fill-or-kill"
        elif self._order_type == Order.TIME_IN_FORCE_IOC:
            return "immediate-or-cancel"

        return "unknown"

    def price_type_to_str(self) -> str:
        if self._price_type == Order.PRICE_LAST:
            return "last"
        elif self._price_type == Order.PRICE_INDEX:
            return "index"
        elif self._price_type == Order.PRICE_MARK:
            return "mark"

        return "unknown"

    #
    # persistence
    #

    def dumps(self) -> dict:
        """
        @todo Could humanize str and timestamp into datetime
        @return: dict
        """
        return {
            'id': self._order_id,
            'ref-id': self._ref_order_id,
            'position-id': self._position_id,
            'symbol': self._symbol,
            'quantity': self._quantity,
            'direction': self._direction,
            'created': self._created_time,
            'transact-time': self._transact_time,
            'order-type': self._order_type,
            'price': self._price,
            'stop-price': self._stop_price,
            'stop-mode': self._stop_mode,
            'reduce-only': self._reduce_only,
            'hedging': self._hedging,
            'post-only': self._post_only,
            'close-only': self._close_only,
            'price-type': self._price_type,
            'margin-trade': self._margin_trade,
            'time-in-force': self._time_in_force,
            'executed': self._executed,
            'fully_filled': self._fully_filled,
            'avg-price': self._avg_price,
            'leverage': self._leverage,
            'take-profit-price': self._take_profit,
            'stop-loss-price': self._stop_loss,
            'trailing-stop': self._trailing_stop,
        }

    def loads(self, data: dict):
        self._order_id = data.get('id', "")
        self._ref_order_id = data.get('ref-id', "")
        self._position_id = data.get('position-id', None)

        self._symbol = data.get('symbol', "")
        self._quantity = data.get('quantity', 0.0)
        self._direction = data.get('direction', Order.LONG)

        self._created_time = data.get('created', 0.0)
        self._transact_time = data.get('transact-time', 0.0)

        self._leverage = data.get('leverage', 1.0)
        self._take_profit = data.get('take-profit-price', None)
        self._stop_loss = data.get('stop-loss-price', None)
        self._trailing_stop = data.get('trailing-stop', False)

        self._executed = data.get('executed', 0.0)
        self._fully_filled = data.get('fully-filled', False)
        self._avg_price = data.get('avg-price', 0.0)
        self._order_type = data.get('order-type', Order.ORDER_MARKET)
        self._price = data.get('price', None)
        self._stop_price = data.get('stop-price', None)
        self._stop_mode = data.get('stop-mode', Order.STOP_NONE)
        self._reduce_only = data.get('reduce-only', False)
        self._hedging = data.get('hedging', False)
        self._post_only = data.get('post-only', True)
        self._close_only = data.get('close-only', False)
        self._price_type = data.get('price-type', Order.PRICE_LAST)
        self._margin_trade = data.get('margin-trade', False)
        self._time_in_force = data.get('time-in-force', Order.TIME_IN_FORCE_GTC)


def order_type_to_str(order_type: int) -> str:
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


def order_reason_to_str(reason: int) -> str:
    if reason == Order.REASON_OK:
        return "success"
    elif reason == Order.REASON_UNDEFINED:
        return "undefined"
    elif reason == Order.REASON_INSUFFICIENT_FUNDS:
        return "insufficient-funds"
    elif reason == Order.REASON_INSUFFICIENT_MARGIN:
        return "insufficient-margin"
    elif reason == Order.REASON_ERROR:
        return "error"
    elif reason == Order.REASON_INVALID_ARGS:
        return "invalid-arguments"
    elif reason == Order.REASON_DENIED:
        return "denied"
    elif reason == Order.REASON_UNREACHABLE_SERVICE:
        return "unreachable"
    elif reason == Order.REASON_RATE_LIMIT:
        return "rate-limit"
    elif reason == Order.REASON_ORDER_LIMIT:
        return "order-limit"
    elif reason == Order.REASON_POSITION_LIMIT:
        return "position-limit"
    elif reason == Order.REASON_INVALID_NONCE:
        return "invalid-nonce"
    elif reason == Order.REASON_POST_ONLY:
        return "post-only"
    elif reason == Order.REASON_CANCEL_ONLY:
        return "cancel-only"
    else:
        return "undefined"
